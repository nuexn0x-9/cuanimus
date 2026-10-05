"""
Test Suite for Agent Trade Intent Pipeline, Two-Step Execution, Idempotency, and Risk Guardrails.
"""
import unittest
from datetime import datetime, timezone, timedelta

from cuanimus.agent.intent import (
    IntentPipeline,
    AgentTradeIntent,
    IntentStatus,
)
from cuanimus.agent.policy import AgentTradingPolicy
from cuanimus.risk.engine import RiskEngine
from cuanimus.execution.paper_safety import PaperExecutionSafetyGuard
from cuanimus.common.types import PortfolioState


class TestAgentTradingPipeline(unittest.TestCase):
    def setUp(self):
        self.policy = AgentTradingPolicy(
            policy_name="test_pipeline_policy",
            allowed_environments=["paper"],
            allowed_symbols=["ETH/USDT:USDT", "BTC/USDT:USDT"],
            allowed_strategies=["v2_pullback", "baseline_v0"],
            max_risk_per_trade_pct=2.0,
            max_leverage=5.0,
            require_mandatory_stop_loss=True,
        )
        self.risk_engine = RiskEngine(
            base_risk_pct=1.5,
            max_leverage=5.0,
            max_daily_loss_pct=3.0,
            max_drawdown_pct=15.0,
        )
        self.safety_guard = PaperExecutionSafetyGuard(dry_run=True)
        self.pipeline = IntentPipeline(
            policy=self.policy,
            risk_engine=self.risk_engine,
            safety_guard=self.safety_guard,
        )

    def test_two_step_intent_lifecycle(self):
        """Full end-to-end intent progression: create -> validate -> execute."""
        # Step 1: Create Intent
        intent = self.pipeline.create_intent(
            agent_id="test_trader",
            idempotency_key="idemp_101",
            symbol="ETH/USDT:USDT",
            direction="LONG",
            entry_price=3100.0,
            stop_loss=3000.0,
            leverage=3.0,
            stake_usdt=150.0,
            strategy_id="v2_pullback",
            reasoning="Valid pullback to 0.618 Fib with volume absorption",
        )
        self.assertEqual(intent.status, IntentStatus.CREATED)
        self.assertFalse(intent.is_expired())

        # Step 2: Validate Intent
        val_res = self.pipeline.validate_intent(intent.intent_id)
        self.assertTrue(val_res.is_valid)
        self.assertTrue(val_res.policy_passed)
        self.assertTrue(val_res.risk_passed)
        self.assertEqual(intent.status, IntentStatus.VALIDATED)
        self.assertGreater(val_res.approved_contracts, 0.0)

        # Step 3: Execute Intent
        exec_res = self.pipeline.execute_intent(intent.intent_id, idempotency_key="idemp_101")
        self.assertEqual(exec_res["status"], "FILLED_SIMULATED")
        self.assertEqual(intent.status, IntentStatus.EXECUTED)
        self.assertTrue(exec_res["order"]["is_paper"])

    def test_idempotency_prevents_duplicate_submission(self):
        """Duplicate intent requests with identical idempotency key return cached instance without re-executing."""
        # Create first
        intent1 = self.pipeline.create_intent(
            agent_id="test_trader",
            idempotency_key="unique_key_999",
            symbol="ETH/USDT:USDT",
            direction="LONG",
            entry_price=3100.0,
            stop_loss=3000.0,
        )

        # Create second with same key
        intent2 = self.pipeline.create_intent(
            agent_id="test_trader",
            idempotency_key="unique_key_999",
            symbol="ETH/USDT:USDT",
            direction="LONG",
            entry_price=3100.0,
            stop_loss=3000.0,
        )

        self.assertEqual(intent1.intent_id, intent2.intent_id)

        # Validate and execute
        self.pipeline.validate_intent(intent1.intent_id)
        exec1 = self.pipeline.execute_intent(intent1.intent_id, idempotency_key="unique_key_999")
        # Second execution attempt with same idempotency key returns identical result without submitting duplicate order
        exec2 = self.pipeline.execute_intent(intent1.intent_id, idempotency_key="unique_key_999")
        self.assertEqual(exec1, exec2)
        self.assertEqual(self.safety_guard.telemetry.limit_orders_submitted, 1)

    def test_intent_ttl_expiration_blocks_execution(self):
        """Expired intents are rejected and cannot be validated or executed."""
        intent = self.pipeline.create_intent(
            agent_id="test_trader",
            idempotency_key="idemp_expired",
            symbol="ETH/USDT:USDT",
            direction="LONG",
            entry_price=3100.0,
            stop_loss=3000.0,
            ttl_seconds=-10,  # Expired in past
        )
        self.assertTrue(intent.is_expired())

        val_res = self.pipeline.validate_intent(intent.intent_id)
        self.assertFalse(val_res.is_valid)
        self.assertEqual(intent.status, IntentStatus.EXPIRED)

        with self.assertRaises(TimeoutError):
            self.pipeline.execute_intent(intent.intent_id, idempotency_key="idemp_expired")

    def test_policy_veto_on_unwhitelisted_symbol(self):
        """Intent targeting unwhitelisted symbol is vetoed by Policy before RiskEngine."""
        intent = self.pipeline.create_intent(
            agent_id="test_trader",
            idempotency_key="idemp_veto_sym",
            symbol="DOGE/USDT:USDT",
            direction="LONG",
            entry_price=0.15,
            stop_loss=0.14,
        )
        val_res = self.pipeline.validate_intent(intent.intent_id)
        self.assertFalse(val_res.is_valid)
        self.assertFalse(val_res.policy_passed)
        self.assertTrue(any("POLICY_VETO" in r for r in val_res.rejection_reasons))

    def test_risk_engine_veto_on_max_portfolio_drawdown(self):
        """RiskEngine vetoes intent when portfolio drawdown breaches threshold."""
        stressed_portfolio = PortfolioState(
            equity=8000.0,
            available_balance=8000.0,
            peak_equity=10000.0,
            drawdown_pct=20.0,  # > 15.0% threshold
            daily_realized_loss=0.0,
            consecutive_losses=0,
        )
        intent = self.pipeline.create_intent(
            agent_id="test_trader",
            idempotency_key="idemp_veto_dd",
            symbol="ETH/USDT:USDT",
            direction="LONG",
            entry_price=3100.0,
            stop_loss=3000.0,
        )
        val_res = self.pipeline.validate_intent(intent.intent_id, portfolio_state=stressed_portfolio)
        self.assertFalse(val_res.is_valid)
        self.assertTrue(val_res.policy_passed)
        self.assertFalse(val_res.risk_passed)
        self.assertTrue(any("RISK_VETO: MAX_PORTFOLIO_DRAWDOWN_BREACHED" in r for r in val_res.rejection_reasons))

    def test_execution_blocked_when_risk_emergency_stop_triggered(self):
        """Emergency kill switch immediately vetoes all pending and new trade intents."""
        self.risk_engine.trigger_emergency_stop(reason="Operator killed execution")

        intent = self.pipeline.create_intent(
            agent_id="test_trader",
            idempotency_key="idemp_veto_kill",
            symbol="ETH/USDT:USDT",
            direction="LONG",
            entry_price=3100.0,
            stop_loss=3000.0,
        )
        val_res = self.pipeline.validate_intent(intent.intent_id)
        self.assertFalse(val_res.is_valid)
        self.assertFalse(val_res.risk_passed)
        self.assertTrue(any("EMERGENCY_STOP_ACTIVE" in r for r in val_res.rejection_reasons))
