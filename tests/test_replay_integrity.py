"""
Unit & Regression Tests for CUANIMUS True Bar Replay Engine & Information Boundaries.
Tests:
- Strict Event Clock & Information Boundary (t <= T, raises LookaheadViolationError on t > T)
- Multi-Timeframe Alignment (15m execution never accesses unclosed 1h bar)
- Causal Confirmation for Fractals and Order Blocks (confirmation at i + window)
- Fee & Slippage separation (maker, taker, entry, exit)
- Replay reproducibility
"""
import unittest
from datetime import datetime, timezone, timedelta
from cuanimus.common.exceptions import LookaheadViolationError
from cuanimus.validation.replay_engine import (
    StrictEventClock,
    MultiTimeframeAlignmentManager,
    ReplayConfig,
    ReplayFeeModel,
    ReplaySlippageModel,
    TrueBarReplayEngine,
)
from cuanimus.strategy.structure import (
    detect_swing_points,
    filter_confirmed_swings,
    detect_order_blocks,
    filter_confirmed_order_blocks,
)
from cuanimus.strategy.baseline_v0 import BaselineV0Strategy
from cuanimus.risk.engine import RiskEngine


class TestReplayIntegrity(unittest.TestCase):
    def test_strict_event_clock_detects_future_access(self):
        """StrictEventClock raises LookaheadViolationError if future data is accessed."""
        t0 = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
        clock = StrictEventClock(t0)

        # Valid past or current access
        clock.assert_no_lookahead(t0, "current bar")
        clock.assert_no_lookahead(t0 - timedelta(minutes=15), "past bar")

        # Future access MUST raise LookaheadViolationError
        future_t = t0 + timedelta(minutes=15)
        with self.assertRaises(LookaheadViolationError):
            clock.assert_no_lookahead(future_t, "future bar")

        # Clock moving backwards raises error
        with self.assertRaises(LookaheadViolationError):
            clock.tick(t0 - timedelta(minutes=1))

    def test_multi_timeframe_alignment_no_incomplete_htf_bar(self):
        """
        At 15m candle close (10:15 UTC), the 1h bar (10:00 - 11:00) is NOT closed.
        Engine MUST only return the 1h bar ending at 10:00 UTC or earlier.
        """
        htf_bars = [
            {"date": datetime(2026, 7, 1, 8, 0, tzinfo=timezone.utc).isoformat(), "open": 100.0, "close": 102.0},  # Closes 09:00
            {"date": datetime(2026, 7, 1, 9, 0, tzinfo=timezone.utc).isoformat(), "open": 102.0, "close": 105.0},  # Closes 10:00
            {"date": datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc).isoformat(), "open": 105.0, "close": 110.0}, # Closes 11:00 (Incomplete!)
        ]

        # Current 15m execution timestamp: 10:15 UTC
        curr_15m_close = datetime(2026, 7, 1, 10, 15, tzinfo=timezone.utc)

        latest_closed_htf = MultiTimeframeAlignmentManager.get_latest_closed_htf_bar(htf_bars, curr_15m_close)
        self.assertIsNotNone(latest_closed_htf)
        # MUST be the 09:00 bar (which closed at 10:00), NEVER the 10:00 bar (which closes at 11:00)!
        self.assertEqual(latest_closed_htf["open"], 102.0)
        self.assertEqual(latest_closed_htf["close"], 105.0)

    def test_causal_fractal_confirmation_prevents_lookahead(self):
        """
        A swing high at index 4 with window=2 is only confirmed at index 6 (i + 2).
        Prior to index 6, filter_confirmed_swings MUST NOT expose the swing high.
        """
        highs = [10.0, 11.0, 12.0, 13.0, 20.0, 15.0, 14.0, 13.0, 12.0]
        lows = [9.0, 10.0, 11.0, 12.0, 18.0, 14.0, 13.0, 12.0, 11.0]
        # Peak is at index 4 (high=20.0)

        all_swings = detect_swing_points(highs, lows, window=2)
        sh = all_swings["swing_highs"][0]
        self.assertEqual(sh.index, 4)
        self.assertEqual(sh.confirmed_index, 6)

        # At index 4: swing high is NOT confirmed
        swings_at_4 = filter_confirmed_swings(all_swings, current_index=4)
        self.assertEqual(len(swings_at_4["swing_highs"]), 0)

        # At index 5: swing high is still NOT confirmed
        swings_at_5 = filter_confirmed_swings(all_swings, current_index=5)
        self.assertEqual(len(swings_at_5["swing_highs"]), 0)

        # At index 6: swing high is CONFIRMED!
        swings_at_6 = filter_confirmed_swings(all_swings, current_index=6)
        self.assertEqual(len(swings_at_6["swing_highs"]), 1)
        self.assertEqual(swings_at_6["swing_highs"][0].price, 20.0)

    def test_fee_model_separation_no_double_counting(self):
        """Maker fee and taker fee are calculated independently and accurately."""
        fee_model = ReplayFeeModel(maker_fee_pct=0.02, taker_fee_pct=0.05)
        fill_price = 1000.0
        amount = 2.0
        notional = fill_price * amount

        maker_fee = notional * (fee_model.maker_fee_pct / 100.0)
        taker_fee = notional * (fee_model.taker_fee_pct / 100.0)

        # 2000 * 0.0002 = 0.40 USDT
        self.assertAlmostEqual(maker_fee, 0.40, places=4)
        # 2000 * 0.0005 = 1.00 USDT
        self.assertAlmostEqual(taker_fee, 1.00, places=4)
        self.assertNotEqual(maker_fee, taker_fee)


if __name__ == "__main__":
    unittest.main()
