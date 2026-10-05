"""
Unit and System Tests for CUANIMUS Risk Engine.
"""
import unittest
from datetime import datetime

from cuanimus.common.types import (
    TradeIntent,
    SignalDirection,
    PortfolioState,
)
from cuanimus.risk.engine import RiskEngine
from cuanimus.risk.sizing import calculate_position_size
from cuanimus.risk.stop_loss import compute_stop_loss, compute_take_profit, StopLossModel

class TestRiskEngine(unittest.TestCase):
    def setUp(self):
        self.risk_engine = RiskEngine(
            base_risk_pct=1.5,
            max_leverage=5.0,
            max_daily_loss_pct=3.0,
            max_drawdown_pct=15.0,
            max_pair_exposure_pct=30.0,
            max_total_exposure_pct=80.0,
            consecutive_loss_pair_threshold=3,
            consecutive_loss_portfolio_threshold=5,
        )

        self.valid_portfolio = PortfolioState(
            equity=100.0,
            available_balance=100.0,
            peak_equity=100.0,
            drawdown_pct=0.0,
            daily_realized_loss=0.0,
            consecutive_losses=0,
            pair_consecutive_losses={"ADA/USDT:USDT": 0},
            active_exposures={"ADA/USDT:USDT": 0.0},
            total_exposure_notional=0.0,
        )

        self.intent_long = TradeIntent(
            intent_id="TEST_INT_1",
            symbol="ADA/USDT:USDT",
            direction=SignalDirection.LONG,
            timestamp=datetime.utcnow(),
            strategy_id="TEST_STRAT",
            entry_price_target=0.5000,
        )

    def test_position_sizing_mathematics(self):
        res = calculate_position_size(
            wallet_balance=100.0,
            risk_per_trade_pct=1.5,
            entry_price=0.5000,
            stop_loss_price=0.4850,
            leverage=5.0,
        )
        self.assertTrue(res["approved"])
        self.assertEqual(res["max_risk_usdt"], 1.50)
        self.assertEqual(res["sl_distance_pct"], 3.0)
        self.assertEqual(res["stake_amount"], 10.0)
        self.assertEqual(res["notional_value"], 50.0)
        self.assertEqual(res["contracts"], 100.0)

    def test_risk_veto_on_emergency_stop(self):
        self.risk_engine.trigger_emergency_stop("Test emergency")
        eval_res = self.risk_engine.evaluate_intent(
            intent=self.intent_long,
            portfolio=self.valid_portfolio,
            atr_value=0.0100,
        )
        self.assertFalse(eval_res.is_approved)
        self.assertEqual(eval_res.veto_reason, "EMERGENCY_STOP_ACTIVE")

    def test_risk_veto_on_max_daily_loss(self):
        portfolio = PortfolioState(
            equity=100.0,
            available_balance=95.0,
            peak_equity=100.0,
            drawdown_pct=5.0,
            daily_realized_loss=3.50,
            consecutive_losses=2,
        )
        eval_res = self.risk_engine.evaluate_intent(
            intent=self.intent_long,
            portfolio=portfolio,
            atr_value=0.0100,
        )
        self.assertFalse(eval_res.is_approved)
        self.assertIn("DAILY_LOSS_LIMIT_REACHED", eval_res.veto_reason)

    def test_risk_veto_on_max_portfolio_drawdown(self):
        portfolio = PortfolioState(
            equity=80.0,
            available_balance=80.0,
            peak_equity=100.0,
            drawdown_pct=20.0,
            daily_realized_loss=0.0,
            consecutive_losses=1,
        )
        eval_res = self.risk_engine.evaluate_intent(
            intent=self.intent_long,
            portfolio=portfolio,
            atr_value=0.0100,
        )
        self.assertFalse(eval_res.is_approved)
        self.assertIn("MAX_PORTFOLIO_DRAWDOWN_BREACHED", eval_res.veto_reason)

    def test_consecutive_losses_trigger_cooldown(self):
        portfolio = PortfolioState(
            equity=100.0,
            available_balance=100.0,
            peak_equity=100.0,
            drawdown_pct=3.0,
            daily_realized_loss=1.0,
            consecutive_losses=3,
            pair_consecutive_losses={"ADA/USDT:USDT": 3},
        )
        eval_res = self.risk_engine.evaluate_intent(
            intent=self.intent_long,
            portfolio=portfolio,
            atr_value=0.0100,
        )
        self.assertFalse(eval_res.is_approved)
        self.assertIn("CONSECUTIVE_LOSSES_3_TRIGGERED_COOLDOWN", eval_res.veto_reason)

    def test_adaptive_leverage_scaling_in_moderate_drawdown(self):
        portfolio = PortfolioState(
            equity=89.0,
            available_balance=89.0,
            peak_equity=100.0,
            drawdown_pct=11.0,
            daily_realized_loss=0.5,
            consecutive_losses=1,
        )
        eval_res = self.risk_engine.evaluate_intent(
            intent=self.intent_long,
            portfolio=portfolio,
            atr_value=0.0100,
        )
        self.assertTrue(eval_res.is_approved)
        self.assertEqual(eval_res.approved_leverage, 2.0)
        self.assertAlmostEqual(eval_res.max_loss_usdt, 89.0 * 0.0075, delta=0.1)

if __name__ == "__main__":
    unittest.main()

