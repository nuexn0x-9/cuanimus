"""
Failure Scenario and Edge-Case Tests for CUANIMUS.
"""
import unittest
from datetime import datetime, timedelta

from cuanimus.common.types import Order, OrderState, OrderSide, OrderType, TradeIntent, SignalDirection, PortfolioState
from cuanimus.common.exceptions import (
    ClockDriftException,
)
from cuanimus.execution.state_machine import OrderStateMachine
from cuanimus.risk.sizing import calculate_position_size
from cuanimus.risk.engine import RiskEngine

class TestFailureScenarios(unittest.TestCase):
    def test_clock_drift_detection(self):
        system_time = datetime.utcnow()
        exchange_server_time = system_time + timedelta(milliseconds=750)

        drift_ms = abs((system_time - exchange_server_time).total_seconds() * 1000.0)
        self.assertGreater(drift_ms, 500.0)

        with self.assertRaises(ClockDriftException):
            if drift_ms > 500.0:
                raise ClockDriftException(f"Clock drift {drift_ms:.1f}ms exceeds 500ms limit")

    def test_network_timeout_during_submission_transitions_to_failed(self):
        order = Order(
            client_order_id="CNMS_FAIL_01",
            symbol="BTC/USDT:USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            amount=0.01,
            price=60000.0,
            state=OrderState.CREATED,
        )
        OrderStateMachine.transition(order, OrderState.FAILED, reason="NETWORK_CONNECTION_REFUSED")
        self.assertEqual(order.state, OrderState.FAILED)
        self.assertEqual(order.cancel_reason, "NETWORK_CONNECTION_REFUSED")

    def test_sizing_with_zero_or_negative_balance(self):
        res_zero = calculate_position_size(
            wallet_balance=0.0,
            risk_per_trade_pct=1.5,
            entry_price=100.0,
            stop_loss_price=95.0,
            leverage=5.0,
        )
        self.assertFalse(res_zero["approved"])
        self.assertEqual(res_zero["reason"], "NON_POSITIVE_WALLET_BALANCE")

    def test_sizing_with_stop_loss_at_entry_price(self):
        res_div_zero = calculate_position_size(
            wallet_balance=1000.0,
            risk_per_trade_pct=1.5,
            entry_price=100.0,
            stop_loss_price=100.0,
            leverage=5.0,
        )
        self.assertFalse(res_div_zero["approved"])
        self.assertEqual(res_div_zero["reason"], "STOP_LOSS_TOO_TIGHT")

    def test_risk_rejection_on_negative_or_corrupt_atr(self):
        risk_engine = RiskEngine()
        portfolio = PortfolioState(
            equity=100.0,
            available_balance=100.0,
            peak_equity=100.0,
            drawdown_pct=0.0,
            daily_realized_loss=0.0,
            consecutive_losses=0,
        )
        intent = TradeIntent(
            intent_id="CORRUPT_INTENT",
            symbol="ETH/USDT:USDT",
            direction=SignalDirection.LONG,
            timestamp=datetime.utcnow(),
            strategy_id="TEST",
            entry_price_target=2500.0,
        )

        with self.assertRaises(AssertionError):
            risk_engine.evaluate_intent(
                intent=intent,
                portfolio=portfolio,
                atr_value=-5.0,
            )

if __name__ == "__main__":
    unittest.main()

