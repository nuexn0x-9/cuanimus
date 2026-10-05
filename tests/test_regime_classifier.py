"""
Unit Tests for CUANIMUS Market Regime Classifier.
"""
import unittest

from cuanimus.common.types import MarketRegimeType
from cuanimus.regime.classifier import MarketRegimeClassifier

class TestMarketRegimeClassifier(unittest.TestCase):
    def setUp(self):
        self.classifier = MarketRegimeClassifier(
            adx_trend_threshold=25.0,
            adx_ranging_threshold=20.0,
            high_volatility_quantile=90.0,
            low_volatility_quantile=15.0,
        )

    def test_trending_bull_classification(self):
        regime = self.classifier.classify(
            close_price=105.0,
            adx_1h=32.0,
            atr_15m=1.2,
            atr_percentile=60.0,
            bb_width_percentile=50.0,
            ema50_1h=102.0,
            ema200_1h=98.0,
            ema50_4h=100.0,
            ema200_4h=95.0,
        )
        self.assertEqual(regime.regime, MarketRegimeType.TRENDING_BULL)
        self.assertEqual(regime.htf_bias, "BULLISH")
        self.assertGreaterEqual(regime.confidence, 60.0)

    def test_trending_bear_classification(self):
        regime = self.classifier.classify(
            close_price=90.0,
            adx_1h=30.0,
            atr_15m=1.5,
            atr_percentile=65.0,
            bb_width_percentile=55.0,
            ema50_1h=92.0,
            ema200_1h=96.0,
            ema50_4h=94.0,
            ema200_4h=98.0,
        )
        self.assertEqual(regime.regime, MarketRegimeType.TRENDING_BEAR)
        self.assertEqual(regime.htf_bias, "BEARISH")

    def test_ranging_classification(self):
        regime = self.classifier.classify(
            close_price=100.0,
            adx_1h=16.0,
            atr_15m=0.8,
            atr_percentile=40.0,
            bb_width_percentile=45.0,
            ema50_1h=100.2,
            ema200_1h=99.8,
            ema50_4h=100.0,
            ema200_4h=100.0,
        )
        self.assertEqual(regime.regime, MarketRegimeType.RANGING)

    def test_high_volatility_preemption(self):
        regime = self.classifier.classify(
            close_price=105.0,
            adx_1h=35.0,
            atr_15m=4.5,
            atr_percentile=95.0,
            bb_width_percentile=90.0,
            ema50_1h=102.0,
            ema200_1h=98.0,
            ema50_4h=100.0,
            ema200_4h=95.0,
        )
        self.assertEqual(regime.regime, MarketRegimeType.HIGH_VOLATILITY)

    def test_low_volatility_compression(self):
        regime = self.classifier.classify(
            close_price=100.0,
            adx_1h=22.0,
            atr_15m=0.3,
            atr_percentile=12.0,
            bb_width_percentile=10.0,
            ema50_1h=100.1,
            ema200_1h=99.9,
            ema50_4h=100.0,
            ema200_4h=100.0,
        )
        self.assertEqual(regime.regime, MarketRegimeType.LOW_VOLATILITY)

if __name__ == "__main__":
    unittest.main()

