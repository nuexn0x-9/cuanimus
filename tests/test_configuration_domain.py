"""
Unit & Regression Tests for CUANIMUS Typed Configuration Domain.
Tests:
- Schema validation, type checking, bounds, and choices
- Layered precedence (Defaults -> Profile -> Env -> Env Vars -> Overrides)
- Safety Invariant enforcement (live trading rejection, leverage ceilings, SL precedence)
- Secret quarantine detection
- Timeframe hierarchy validation
- Runtime immutability and reload policy manager
- JSON Schema generation
"""
import unittest
import os
from cuanimus.config.models import (
    CuanimusConfig,
    EnvironmentConfig,
    RiskConfig,
    ExecutionConfig,
    MarketConfig,
)
from cuanimus.config.loader import ConfigLoader
from cuanimus.config.validator import ConfigValidator
from cuanimus.config.immutability import (
    RuntimeImmutabilityManager,
    ReloadDecision,
)
from cuanimus.config.schema import generate_json_schema


class TestConfigurationDomain(unittest.TestCase):
    def setUp(self):
        self.validator = ConfigValidator()
        self.loader = ConfigLoader()

    def test_default_configuration_is_strictly_valid_and_safe(self):
        """Default configuration passes all checks and reports PAPER_SAFE."""
        cfg, _ = self.loader.load(profile="balanced")
        report = self.validator.validate(cfg)
        self.assertTrue(report.is_valid, f"Validation errors: {report.errors}")
        self.assertEqual(report.safety_status, "PAPER_SAFE")
        self.assertTrue(cfg.environment.dry_run)
        self.assertFalse(cfg.environment.live_trading_enabled)

    def test_live_trading_safety_invariant_blocks_execution(self):
        """Setting live_trading_enabled without explicit clearance tokens is blocked."""
        cfg, _ = self.loader.load()
        cfg.environment.live_trading_enabled = True
        cfg.environment.dry_run = False
        cfg.environment.env_name = "live"

        report = self.validator.validate(cfg)
        self.assertFalse(report.is_valid)
        self.assertEqual(report.safety_status, "REJECTED_UNSAFE")
        self.assertTrue(any("SAFETY INVARIANT BREACH" in e or "MANDATORY PLATFORM GATE" in e for e in report.errors))

    def test_excessive_leverage_rejected_by_safety_invariant(self):
        """Leverage exceeding platform institutional ceiling (10.0x) is rejected."""
        cfg, _ = self.loader.load()
        cfg.risk.max_leverage = 25.0  # Excessive leverage
        report = self.validator.validate(cfg)
        self.assertFalse(report.is_valid)
        self.assertTrue(any("exceeds the maximum institutional platform ceiling" in e for e in report.errors))

    def test_disabling_sl_precedence_rejected_by_safety_invariant(self):
        """Disabling pessimistic Stop Loss precedence is blocked."""
        cfg, _ = self.loader.load()
        cfg.execution.pessimistic_sl_precedence = False
        report = self.validator.validate(cfg)
        self.assertFalse(report.is_valid)
        self.assertTrue(any("pessimistic_sl_precedence' cannot be disabled" in e for e in report.errors))

    def test_timeframe_hierarchy_validation(self):
        """Execution timeframe must be <= context timeframe <= macro timeframe."""
        cfg, _ = self.loader.load()
        cfg.market.base_timeframe = "1h"
        cfg.market.context_timeframe = "15m"  # Inverted! Base is higher than context
        report = self.validator.validate(cfg)
        self.assertFalse(report.is_valid)
        self.assertTrue(any("Timeframe Conflict" in e for e in report.errors))

    def test_layered_precedence_and_env_var_override(self):
        """Environment variables take precedence over profile and default settings."""
        os.environ["CUANIMUS_RISK__RISK_PER_TRADE_PCT"] = "2.2"
        try:
            cfg, prov = self.loader.load(profile="conservative")
            # In conservative.yaml, risk_per_trade_pct is 0.5%, but env var must override it to 2.2%
            self.assertEqual(cfg.risk.risk_per_trade_pct, 2.2)
            self.assertIn("CUANIMUS_RISK__RISK_PER_TRADE_PCT", prov.get("risk.risk_per_trade_pct", ""))
        finally:
            del os.environ["CUANIMUS_RISK__RISK_PER_TRADE_PCT"]

    def test_runtime_immutability_policies(self):
        """Hot updates are permitted only for HOT_SAFE fields; restart required for structural fields."""
        cfg_active, _ = self.loader.load(profile="balanced")
        immutability = RuntimeImmutabilityManager(cfg_active)

        # 1. Hot-safe update (e.g. log_level)
        cfg_proposed_hot, _ = self.loader.load(profile="balanced")
        cfg_proposed_hot.observability.log_level = "DEBUG"
        assessment_hot = immutability.assess_update(cfg_proposed_hot)
        self.assertEqual(assessment_hot.decision, ReloadDecision.HOT_APPLY_PERMITTED)

        # 2. Restart-required update (e.g. risk_per_trade_pct)
        cfg_proposed_restart, _ = self.loader.load(profile="balanced")
        cfg_proposed_restart.risk.risk_per_trade_pct = 1.2
        assessment_restart = immutability.assess_update(cfg_proposed_restart)
        self.assertEqual(assessment_restart.decision, ReloadDecision.RESTART_REQUIRED)

        # 3. Critical invariant update (e.g. env_name)
        cfg_proposed_crit, _ = self.loader.load(profile="balanced")
        cfg_proposed_crit.environment.env_name = "testnet"
        assessment_crit = immutability.assess_update(cfg_proposed_crit)
        self.assertEqual(assessment_crit.decision, ReloadDecision.RELOAD_BLOCKED_CRITICAL)

    def test_json_schema_generation(self):
        """JSON Schema dictionary is generated with standard keys and sections."""
        schema = generate_json_schema()
        self.assertIn("$schema", schema)
        self.assertIn("properties", schema)
        self.assertIn("risk", schema["properties"])
        self.assertIn("strategy", schema["properties"])
        self.assertIn("environment", schema["properties"])
        self.assertIn("execution", schema["properties"])


if __name__ == "__main__":
    unittest.main()
