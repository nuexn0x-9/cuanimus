"""
CUANIMUS Configuration Validator & Safety Invariant Auditor.
Inspects configuration instances against:
- Typed schema constraints (types, minimums, maximums, choices)
- Cross-section dependency rules (timeframe hierarchies, exchange market compatibility)
- Safety invariants (live trading clearance, maximum leverage ceiling, SL precedence)
- Secret quarantine (detects accidental hardcoded secrets in configuration files)
"""
import os
import re
from typing import Dict, Any, List, Tuple
from dataclasses import dataclass, field

from cuanimus.config.models import CuanimusConfig
from cuanimus.config.fields import ConfigField, RiskLevel


@dataclass
class ValidationReport:
    is_valid: bool
    safety_status: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "safety_status": self.safety_status,
            "errors": self.errors,
            "warnings": self.warnings,
        }


class ConfigValidator:
    TIMEFRAME_ORDER = {
        "1m": 1,
        "3m": 3,
        "5m": 5,
        "15m": 15,
        "30m": 30,
        "1h": 60,
        "2h": 120,
        "4h": 240,
        "6h": 360,
        "8h": 480,
        "12h": 720,
        "1d": 1440,
        "1w": 10080,
    }

    def validate(self, config: CuanimusConfig) -> ValidationReport:
        errors: List[str] = []
        warnings: List[str] = []

        # 1. Field-by-Field Specification Validation
        all_specs = CuanimusConfig.get_all_field_specs()
        cfg_dict = config.to_dict()

        for full_path, spec in all_specs.items():
            sec, param = full_path.split(".", 1)
            val = cfg_dict.get(sec, {}).get(param)
            if val is not None:
                field_errors = spec.validate_value(val, full_path)
                errors.extend(field_errors)

        # 2. Safety Invariant Audits (NON-NEGOTIABLE)
        env = config.environment
        risk = config.risk
        exec_cfg = config.execution

        # Invariant 2.1: Real-Capital Live Trading Lock
        if env.live_trading_enabled:
            # Multi-condition clearance assertion
            safety_token = os.environ.get("CUANIMUS_ALLOW_REAL_CAPITAL", "")
            if safety_token != "I_UNDERSTAND_THE_RISKS":
                errors.append(
                    "SAFETY INVARIANT BREACH: 'environment.live_trading_enabled' is True, but mandatory environment variable "
                    "CUANIMUS_ALLOW_REAL_CAPITAL='I_UNDERSTAND_THE_RISKS' is missing! Live capital trading is blocked."
                )
            if env.dry_run:
                errors.append(
                    "SAFETY INVARIANT BREACH: 'environment.live_trading_enabled' is True while 'environment.dry_run' is also True. "
                    "Conflicting state."
                )
            if env.env_name != "live":
                errors.append(
                    f"SAFETY INVARIANT BREACH: 'environment.live_trading_enabled' is True while 'environment.env_name' is '{env.env_name}'."
                )
            # Live Capital Credential Preflight
            from cuanimus.exchange.binance_private import get_binance_credentials
            live_key, live_sec = get_binance_credentials("live")
            if not live_key or not live_sec:
                errors.append(
                    "PREFLIGHT ERROR: 'environment.live_trading_enabled' is True, but Binance LIVE API credentials "
                    "(BINANCE_LIVE_API_KEY / BINANCE_LIVE_API_SECRET) are missing or invalid!"
                )

        # Invariant 2.2: Stop-Loss Precedence
        if not exec_cfg.pessimistic_sl_precedence:
            errors.append(
                "SAFETY INVARIANT BREACH: 'execution.pessimistic_sl_precedence' cannot be disabled! "
                "Pessimistic intra-bar stop-loss precedence is mandatory to prevent optimistic fill bias."
            )

        # Invariant 2.3: Leverage Limits
        if risk.max_leverage > 10.0:
            errors.append(
                f"SAFETY INVARIANT BREACH: 'risk.max_leverage' ({risk.max_leverage}x) exceeds the maximum institutional platform ceiling of 10.0x."
            )
        elif risk.max_leverage > 5.0:
            warnings.append(
                f"Elevated Leverage Warning: 'risk.max_leverage' is set to {risk.max_leverage}x. High volatility liquidations possible."
            )

        # Invariant 2.4: Emergency Stop
        if not risk.emergency_stop_enabled:
            errors.append(
                "SAFETY INVARIANT BREACH: 'risk.emergency_stop_enabled' must be True. Operator kill switches cannot be deactivated."
            )

        # 3. Cross-Section Dependencies
        # Timeframe Monotonicity
        market = config.market
        base_tf_mins = self.TIMEFRAME_ORDER.get(market.base_timeframe, 15)
        ctx_tf_mins = self.TIMEFRAME_ORDER.get(market.context_timeframe, 60)
        macro_tf_mins = self.TIMEFRAME_ORDER.get(market.macro_timeframe, 240)

        if base_tf_mins > ctx_tf_mins:
            errors.append(
                f"Timeframe Conflict: 'market.base_timeframe' ({market.base_timeframe}) is higher than "
                f"'market.context_timeframe' ({market.context_timeframe}). Execution timeframe must be <= context timeframe."
            )
        if ctx_tf_mins > macro_tf_mins:
            errors.append(
                f"Timeframe Conflict: 'market.context_timeframe' ({market.context_timeframe}) is higher than "
                f"'market.macro_timeframe' ({market.macro_timeframe})."
            )

        # Pair List Validation
        if not market.pairs or len(market.pairs) == 0:
            errors.append("Market Configuration Error: 'market.pairs' cannot be empty.")

        # Risk Sensibility Checks
        if risk.risk_per_trade_pct > 2.5:
            warnings.append(
                f"High Risk Alert: 'risk.risk_per_trade_pct' = {risk.risk_per_trade_pct}% is unusually aggressive (recommended <= 1.5%)."
            )
        if risk.max_pair_exposure_pct > 40.0:
            warnings.append(
                f"Concentration Warning: 'risk.max_pair_exposure_pct' = {risk.max_pair_exposure_pct}% allows heavy asset concentration."
            )

        # 4. Secret Quarantine & Leakage Check
        secret_findings = self._scan_for_secrets(cfg_dict)
        if secret_findings:
            for s_warn in secret_findings:
                errors.append(f"SECURITY LEAKAGE VIOLATION: {s_warn}")

        # 5. Determine Overall Safety Status
        if errors:
            safety_status = "REJECTED_UNSAFE"
        elif env.env_name == "research":
            safety_status = "RESEARCH_ONLY"
        elif env.env_name == "backtest":
            safety_status = "SIMULATED_BACKTEST"
        elif env.env_name == "paper":
            safety_status = "PAPER_SAFE"
        elif env.env_name == "testnet":
            safety_status = "TESTNET_FORWARD"
        elif env.env_name == "live":
            safety_status = "LIVE_CLEARANCE"
        else:
            safety_status = "UNKNOWN_ENV"

        return ValidationReport(
            is_valid=(len(errors) == 0),
            safety_status=safety_status,
            errors=errors,
            warnings=warnings,
        )

    def _scan_for_secrets(self, data: Dict[str, Any], path: str = "") -> List[str]:
        """Scans configuration dictionary for patterns resembling leaked API keys."""
        findings = []
        secret_regex = re.compile(r"^[A-Za-z0-9]{32,64}$")

        for k, v in data.items():
            curr_path = f"{path}.{k}" if path else k
            if isinstance(v, dict):
                findings.extend(self._scan_for_secrets(v, curr_path))
            elif isinstance(v, str):
                # Check for explicit keywords or suspiciously long high-entropy tokens
                low = v.lower()
                if any(kw in low for kw in ("api_secret", "private_key", "secret_key")) and not low.startswith("user_data"):
                    findings.append(f"Potential secret literal detected at '{curr_path}'")
                elif any(kw in curr_path.lower() for kw in ("secret", "token", "password", "key")) and len(v) > 20:
                    if secret_regex.match(v) and not v.startswith("sqlite"):
                        findings.append(f"Suspected API key or token found in configuration field '{curr_path}'. Move to environment variables!")

        return findings
