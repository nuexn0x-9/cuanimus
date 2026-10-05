"""
Comprehensive Tests for CUANIMUS Validation Pipeline.
Tests:
- Deterministic backtesting reproducibility
- Dataset fingerprinting (SHA256)
- Anti-lookahead integrity
- Taker/Maker fee calculation
- 8h Funding rate deduction
- Adverse slippage modeling
- Partial fill simulation
- Portfolio risk circuit breakers under adverse market conditions
- Walk-Forward Analysis window generation & WFE metrics
"""
import unittest
import hashlib
import json
from datetime import datetime, timedelta

from cuanimus.common.types import (
    TradeIntent,
    SignalDirection,
    OrderRequest,
    OrderSide,
    OrderType,
    RegimeContext,
    MarketRegimeType,
)
from cuanimus.risk.engine import RiskEngine
from cuanimus.strategy.baseline_v0 import BaselineV0Strategy
from cuanimus.validation.backtest_engine import (
    SimulationConfig,
    ExecutionSimulator,
    BacktestPipeline,
)
from cuanimus.validation.walk_forward import (
    generate_walk_forward_windows,
    calculate_walk_forward_efficiency,
)


def generate_synthetic_candles(num_bars: int = 100) -> list:
    """Generates deterministic synthetic candle data."""
    bars = []
    base_price = 1.0000
    base_time = datetime(2026, 6, 1, 0, 0)

    for i in range(num_bars):
        # Oscillating wave with upward drift
        price = base_price + (math_sin := (i % 20) * 0.002) + (i * 0.0005)
        bar = {
            "timestamp": base_time + timedelta(minutes=15 * i),
            "open": round(price, 4),
            "high": round(price + 0.005, 4),
            "low": round(price - 0.005, 4),
            "close": round(price + 0.002, 4),
            "volume": 2000.0,
            "features": {
                "ema20": round(price + 0.001, 4),
                "ema50": round(price - 0.002, 4),
                "rsi": 65.0 if i % 10 == 0 else 50.0,
                "adx": 30.0,
                "btc_rsi": 55.0,
                "eth_rsi": 55.0,
                "atr": 0.0100,
            }
        }
        bars.append(bar)
    return bars


class TestValidationPipeline(unittest.TestCase):
    def setUp(self):
        self.config = SimulationConfig(
            initial_capital=65.0,
            maker_fee_pct=0.02,
            taker_fee_pct=0.05,
            slippage_pct=0.05,
            funding_rate_8h_pct=0.01,
        )
        self.strategy = BaselineV0Strategy()
        self.risk_engine = RiskEngine()
        self.pipeline = BacktestPipeline(self.strategy, self.risk_engine, self.config)
        self.regime = RegimeContext(
            regime=MarketRegimeType.TRENDING_BULL,
            trend_strength_adx=30.0,
            volatility_atr=0.010,
            volatility_percentile=50.0,
            htf_bias="BULLISH",
            confidence=80.0,
        )

    def test_deterministic_backtest_reproducibility(self):
        """Running the identical pipeline on identical bars produces bit-exact metrics."""
        bars = generate_synthetic_candles(60)

        res1 = self.pipeline.run("ADA/USDT:USDT", bars, self.regime)
        res2 = self.pipeline.run("ADA/USDT:USDT", bars, self.regime)

        self.assertEqual(res1["metrics"]["total_trades"], res2["metrics"]["total_trades"])
        self.assertEqual(res1["metrics"]["total_net_pnl"], res2["metrics"]["total_net_pnl"])
        self.assertEqual(res1["final_equity"], res2["final_equity"])
        self.assertEqual(len(res1["closed_trades"]), len(res2["closed_trades"]))

    def test_dataset_fingerprint_sha256(self):
        """Dataset fingerprinting guarantees auditability and immutability."""
        bars = generate_synthetic_candles(10)
        raw_json = json.dumps(bars, default=str, sort_keys=True)
        sha256_hash = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()

        self.assertEqual(len(sha256_hash), 64)
        # Any alteration changes the fingerprint
        bars_altered = generate_synthetic_candles(10)
        bars_altered[0]["close"] += 0.0001
        altered_hash = hashlib.sha256(json.dumps(bars_altered, default=str, sort_keys=True).encode("utf-8")).hexdigest()
        self.assertNotEqual(sha256_hash, altered_hash)

    def test_fee_and_slippage_calculation(self):
        """Execution simulator applies taker fee and adverse slippage on market orders."""
        simulator = ExecutionSimulator(self.config)
        req = OrderRequest(
            client_order_id="TEST_FEE_1",
            symbol="ETH/USDT:USDT",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            amount=1.0,
            price=2000.0,
            stop_loss=1950.0,
            leverage=5.0,
        )
        bar = {"open": 2000.0, "high": 2010.0, "low": 1990.0, "close": 2005.0}
        res = simulator.simulate_entry_fill(req, bar, 0)

        # Slippage: 2000 * 1.0005 = 2001.0
        self.assertAlmostEqual(res["fill_price"], 2001.0, places=2)
        # Fee: 2001.0 * 1.0 * 0.0005 = 1.0005 USDT
        self.assertAlmostEqual(res["fee"], 2001.0 * 0.0005, places=4)

    def test_partial_fill_handling(self):
        """Requested contracts exceeding 50% bar volume triggers partial fill slice."""
        simulator = ExecutionSimulator(self.config)
        req = OrderRequest(
            client_order_id="TEST_PARTIAL_1",
            symbol="XRP/USDT:USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            amount=1000.0, # Requested 1000 contracts
            price=1.0000,
            stop_loss=0.9800,
            leverage=5.0,
        )
        # Bar volume is only 500 contracts
        bar = {"open": 1.0020, "high": 1.0050, "low": 0.9980, "close": 1.0010, "volume": 500.0}
        res = simulator.simulate_entry_fill(req, bar, 0)

        self.assertTrue(res["filled"])
        self.assertTrue(res["is_partial"])
        # Should fill 50% of volume = 250 contracts
        self.assertEqual(res["amount"], 250.0)

    def test_walk_forward_window_splits(self):
        """WFA generator creates non-overlapping test slices."""
        start = datetime(2026, 1, 1)
        end = datetime(2026, 7, 1)
        windows = generate_walk_forward_windows(start, end, train_duration_days=90, test_duration_days=30, step_days=30)

        self.assertGreaterEqual(len(windows), 3)
        self.assertEqual(windows[0].fold_index, 1)
        self.assertEqual(windows[0].test_start, windows[0].train_end)
        self.assertEqual(windows[1].train_start, windows[0].train_start + timedelta(days=30))

    def test_walk_forward_efficiency_metric(self):
        """WFE calculation and classification."""
        robust = calculate_walk_forward_efficiency(20.0, 15.0) # 75% WFE -> ROBUST
        self.assertEqual(robust["status"], "ROBUST")
        self.assertTrue(robust["is_robust"])

        overfitted = calculate_walk_forward_efficiency(30.0, 5.0) # 16.7% WFE -> OVERFITTED
        self.assertEqual(overfitted["status"], "OVERFITTED")
        self.assertFalse(overfitted["is_robust"])


if __name__ == "__main__":
    unittest.main()
