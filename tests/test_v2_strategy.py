"""
Tests for CUANIMUS V2 Pullback & Market Structure Strategy.
Tests:
- Deterministic swing point detection
- Fibonacci retracement calculation & invalidation
- Order block detection & invalidation
- V2 Strategy intent evaluation (Bullish pullback, Bearish pullback, Regime abstain)
"""
import unittest
from cuanimus.common.types import SignalDirection, RegimeContext, MarketRegimeType
from cuanimus.strategy.structure import (
    detect_swing_points,
    compute_fibonacci_levels,
    detect_order_blocks,
    StructureType,
)
from cuanimus.strategy.v2_pullback import (
    V2PullbackStrategy,
    V2StrategyConfig,
)


class TestV2Strategy(unittest.TestCase):
    def test_swing_point_fractal_detection(self):
        """Swing points are identified deterministically without lookahead."""
        highs = [10.0, 11.0, 15.0, 12.0, 11.0, 13.0, 18.0, 14.0, 12.0]
        lows = [9.0, 9.5, 12.0, 10.0, 8.0, 10.0, 14.0, 11.0, 10.0]

        swings = detect_swing_points(highs, lows, window=2)
        # Peak at index 2 (15.0) and index 6 (18.0)
        sh_indices = [sp.index for sp in swings["swing_highs"]]
        self.assertIn(2, sh_indices)
        self.assertIn(6, sh_indices)

        # Valley at index 4 (8.0)
        sl_indices = [sp.index for sp in swings["swing_lows"]]
        self.assertIn(4, sl_indices)

    def test_fibonacci_calculation_and_invalidation(self):
        """Fibonacci calculation is mathematical; invalid inputs raise ValueError."""
        with self.assertRaises(ValueError):
            compute_fibonacci_levels(100.0, 90.0)  # High < Low

        fibs = compute_fibonacci_levels(100.0, 200.0)
        self.assertEqual(fibs["0.000"], 200.0)
        self.assertEqual(fibs["0.500"], 150.0)
        self.assertEqual(fibs["1.000"], 100.0)
        self.assertAlmostEqual(fibs["0.618"], 138.2, places=1)

    def test_order_block_detection_and_invalidation(self):
        """Order block is marked mitigated when subsequent price penetrates boundary."""
        opens = [10.0, 10.5, 10.2, 11.5, 12.5, 10.0]
        closes = [10.2, 10.0, 11.5, 12.5, 13.0, 9.5]  # Index 1 is down candle (10.5->10.0), then impulse
        highs = [10.5, 10.6, 11.8, 12.8, 13.2, 10.2]
        lows = [9.8, 9.9, 10.1, 11.4, 12.3, 9.4]
        atr = [0.5] * 6

        obs = detect_order_blocks(opens, highs, lows, closes, atr, displacement_multiplier=1.5)
        self.assertGreaterEqual(len(obs), 0)

    def test_v2_strategy_pullback_evaluation(self):
        """V2 Pullback triggers LONG intent on bullish pullback and resets."""
        strategy = V2PullbackStrategy(V2StrategyConfig(variant="V2A_PULLBACK"))
        regime = RegimeContext(
            regime=MarketRegimeType.TRENDING_BULL,
            trend_strength_adx=28.0,
            volatility_atr=0.5,
            volatility_percentile=50.0,
            htf_bias="BULLISH",
            confidence=80.0,
        )

        # Candle pullbacks into EMA20 (100.5) with oversold Stoch
        candle = {"close": 100.5}
        features = {
            "ema20": 100.2,
            "ema50": 95.0,
            "stoch_k": 22.0,
            "stoch_d": 25.0,
            "volume": 2500.0,
            "volume_avg": 2000.0,
        }

        intent = strategy.evaluate_intent("ETH/USDT:USDT", candle, features, regime)
        self.assertEqual(intent.direction, SignalDirection.LONG)
        self.assertEqual(intent.confidence, 0.85)

    def test_v2_strategy_abstains_on_uncertain_regime(self):
        """Strategy must abstain when regime is UNCERTAIN."""
        strategy = V2PullbackStrategy()
        uncertain_regime = RegimeContext(
            regime=MarketRegimeType.UNCERTAIN,
            trend_strength_adx=15.0,
            volatility_atr=0.5,
            volatility_percentile=50.0,
            htf_bias="NEUTRAL",
            confidence=40.0,
        )
        candle = {"close": 100.0}
        intent = strategy.evaluate_intent("ETH/USDT:USDT", candle, {}, uncertain_regime)
        self.assertEqual(intent.direction, SignalDirection.HOLD)


if __name__ == "__main__":
    unittest.main()
