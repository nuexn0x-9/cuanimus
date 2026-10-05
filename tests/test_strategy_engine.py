"""
Unit Tests for CUANIMUS Strategy Engine & Composable Features.
"""
import unittest

from cuanimus.common.types import SignalDirection, RegimeContext, MarketRegimeType
from cuanimus.strategy.features import (
    evaluate_trend_feature,
    evaluate_pullback_feature,
    evaluate_volume_feature,
)
from cuanimus.strategy.baseline_v0 import BaselineV0Strategy

class TestStrategyEngine(unittest.TestCase):
    def setUp(self):
        self.v0_strategy = BaselineV0Strategy()
        self.bull_regime = RegimeContext(
            regime=MarketRegimeType.TRENDING_BULL,
            trend_strength_adx=28.0,
            volatility_atr=0.015,
            volatility_percentile=50.0,
            htf_bias="BULLISH",
            confidence=80.0,
        )

    def test_trend_feature_detection(self):
        bull = evaluate_trend_feature(ema_fast=105.0, ema_slow=100.0)
        self.assertEqual(bull["trend"], "BULLISH")
        self.assertAlmostEqual(bull["strength"], 5.0)

        bear = evaluate_trend_feature(ema_fast=95.0, ema_slow=100.0)
        self.assertEqual(bear["trend"], "BEARISH")

        flat = evaluate_trend_feature(ema_fast=100.1, ema_slow=100.0, threshold_pct=0.3)
        self.assertEqual(flat["trend"], "FLAT")

    def test_pullback_feature_detection(self):
        is_dip = evaluate_pullback_feature(
            close_price=100.2,
            ema_fast=100.0,
            trend="BULLISH",
            stoch_k=22.0,
            stoch_d=24.0,
        )
        self.assertTrue(is_dip)

        is_extended = evaluate_pullback_feature(
            close_price=105.0,
            ema_fast=100.0,
            trend="BULLISH",
            stoch_k=85.0,
            stoch_d=80.0,
        )
        self.assertFalse(is_extended)

    def test_volume_feature_confirmation(self):
        self.assertTrue(evaluate_volume_feature(volume=1500.0, volume_avg=1000.0, multiplier=1.2))
        self.assertFalse(evaluate_volume_feature(volume=1100.0, volume_avg=1000.0, multiplier=1.2))

    def test_baseline_v0_long_signal(self):
        intent = self.v0_strategy.evaluate_intent(
            symbol="ADA/USDT:USDT",
            current_candle={"close": 0.5000},
            features={
                "ema20": 0.5100,
                "ema50": 0.5000,
                "rsi": 65.0,
                "adx": 30.0,
                "btc_rsi": 55.0,
                "eth_rsi": 55.0,
            },
            regime=self.bull_regime,
        )
        self.assertEqual(intent.direction, SignalDirection.LONG)
        self.assertEqual(intent.suggested_stop_loss, round(0.5000 * 0.985, 4))

    def test_baseline_v0_hold_when_conditions_unmet(self):
        intent = self.v0_strategy.evaluate_intent(
            symbol="ADA/USDT:USDT",
            current_candle={"close": 0.5000},
            features={
                "ema20": 0.5010,
                "ema50": 0.5000,
                "rsi": 50.0,
                "adx": 15.0,
                "btc_rsi": 50.0,
                "eth_rsi": 50.0,
            },
            regime=self.bull_regime,
        )
        self.assertEqual(intent.direction, SignalDirection.HOLD)

if __name__ == "__main__":
    unittest.main()

