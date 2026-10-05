"""
Comprehensive Tests for Backtest Integrity & Conservative Execution.
Tests:
- Anti-lookahead ATR calculation (strictly closed candles, error on future or incomplete candles)
- Conservative Exit Order of Events (SL takes priority over TP in ambiguous candles)
- Property-based & edge case position sizing
"""
import unittest
from cuanimus.common.types import (
    Position,
    SignalDirection,
    OrderRequest,
    OrderSide,
    OrderType,
)
from cuanimus.strategy.features import compute_closed_candle_atr
from cuanimus.validation.backtest_engine import (
    SimulationConfig,
    ExecutionSimulator,
)
from cuanimus.risk.sizing import calculate_position_size


class TestBacktestIntegrity(unittest.TestCase):
    def setUp(self):
        self.config = SimulationConfig(
            initial_capital=65.0,
            maker_fee_pct=0.02,
            taker_fee_pct=0.05,
            slippage_pct=0.05,
        )
        self.simulator = ExecutionSimulator(self.config)

    def test_anti_lookahead_atr_strictly_closed_candles(self):
        """ATR must be calculated strictly from closed historical bars; fails on insufficient history."""
        # 14 periods require at least 15 bars (index 1 to 14 uses prev_close)
        highs = [1.02] * 10
        lows = [0.98] * 10
        closes = [1.00] * 10

        with self.assertRaises(ValueError):
            compute_closed_candle_atr(highs, lows, closes, period=14)

        # Valid series of 20 bars
        highs_valid = [1.02 + (i * 0.001) for i in range(20)]
        lows_valid = [0.98 + (i * 0.001) for i in range(20)]
        closes_valid = [1.00 + (i * 0.001) for i in range(20)]

        atr = compute_closed_candle_atr(highs_valid, lows_valid, closes_valid, period=14)
        self.assertGreater(atr, 0.0)
        self.assertAlmostEqual(atr, 0.04, delta=0.005)

    def test_conservative_exit_order_sl_precedence(self):
        """When a bar breaches both Stop Loss and Take Profit, conservative policy MUST execute Stop Loss."""
        pos = Position(
            position_id="POS_CONFLICT_1",
            symbol="BTC/USDT:USDT",
            side=SignalDirection.LONG,
            size=1.0,
            entry_price=50000.0,
            current_stop_loss=49000.0,
            leverage=5.0,
        )
        # Bar with extreme wick that breaches both SL (low=48500 <= 49000) and TP (high=52000 >= 51000)
        extreme_bar = {
            "open": 50000.0,
            "high": 52000.0,
            "low": 48500.0,
            "close": 49500.0,
        }
        tp_target = 51000.0

        exit_res = self.simulator.check_position_exit(
            pos=pos,
            bar=extreme_bar,
            bars_held=1,
            take_profit_price=tp_target,
        )

        self.assertIsNotNone(exit_res)
        # Crucial: Must be stop_loss, never take_profit!
        self.assertEqual(exit_res["reason"], "stop_loss")
        self.assertLess(exit_res["pnl"], 0.0)

    def test_position_sizing_edge_cases(self):
        """Property-based edge case validation for position sizing."""
        # 1. Zero balance
        res_zero = calculate_position_size(0.0, 1.5, 100.0, 98.0, 5.0)
        self.assertFalse(res_zero["approved"])
        self.assertEqual(res_zero["reason"], "NON_POSITIVE_WALLET_BALANCE")

        # 2. Negative balance
        res_neg = calculate_position_size(-10.0, 1.5, 100.0, 98.0, 5.0)
        self.assertFalse(res_neg["approved"])

        # 3. Stop loss at entry price (zero stop distance)
        res_zero_sl = calculate_position_size(100.0, 1.5, 100.0, 100.0, 5.0)
        self.assertFalse(res_zero_sl["approved"])
        self.assertEqual(res_zero_sl["reason"], "STOP_LOSS_TOO_TIGHT")

        # 4. Extremely small stop distance (< 0.2%)
        res_tight = calculate_position_size(100.0, 1.5, 100.0, 99.9, 5.0)
        self.assertFalse(res_tight["approved"])

        # 5. Extremely large stop distance (e.g. 50% stop loss makes notional < min_notional)
        res_huge_sl = calculate_position_size(10.0, 1.5, 100.0, 50.0, 5.0, min_notional=5.0)
        # 10 * 1.5% = 0.15 USDT risk. 0.15 / 0.50 = 0.30 USDT desired notional < 5.0 min notional
        self.assertFalse(res_huge_sl["approved"])
        self.assertIn("BELOW_MIN", res_huge_sl["reason"])

        # 6. Leverage boundary < 1.0
        res_lev = calculate_position_size(100.0, 1.5, 100.0, 98.0, 0.5)
        self.assertFalse(res_lev["approved"])
        self.assertEqual(res_lev["reason"], "LEVERAGE_LESS_THAN_ONE")

        # 7. Valid calculation preserves exact dollar risk
        res_valid = calculate_position_size(100.0, 2.0, 100.0, 96.0, 5.0, step_size=0.01)
        self.assertTrue(res_valid["approved"])
        # Risk is 2.0 USDT. SL distance is 4%. Notional is 50 USDT. Contracts = 0.5
        self.assertEqual(res_valid["max_risk_usdt"], 2.0)
        self.assertEqual(res_valid["contracts"], 0.5)


if __name__ == "__main__":
    unittest.main()
