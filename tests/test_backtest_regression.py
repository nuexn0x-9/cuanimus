"""
Backtest Regression Test for CUANIMUS.
"""
import os
import sqlite3
import unittest

from cuanimus.validation.metrics import compute_performance_metrics

class TestBacktestRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture_path = os.path.join(os.path.dirname(__file__), "fixtures", "tradesv3.dryrun.sqlite")
        if not os.path.exists(fixture_path):
            raise unittest.SkipTest(f"Fixture not found at {fixture_path}")

        conn = sqlite3.connect(fixture_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, pair, open_date, close_date, close_profit, close_profit_abs,
                   stake_amount, fee_open_cost, fee_close_cost, funding_fees
            FROM trades
            WHERE is_open = 0
            ORDER BY close_date ASC
        """)
        rows = cursor.fetchall()
        conn.close()

        cls.trades = []
        for r in rows:
            cls.trades.append({
                "trade_id": r[0],
                "symbol": r[1],
                "open_date": r[2],
                "close_date": r[3],
                "profit_pct": r[4] * 100.0,
                "profit_abs": r[5],
                "stake_amount": r[6],
                "fee_cost": (r[7] or 0.0) + (r[8] or 0.0),
                "funding_cost": r[9] or 0.0,
            })

    def test_total_trades_count_matches_audit(self):
        self.assertEqual(len(self.trades), 733)

    def test_performance_metrics_exact_match(self):
        metrics = compute_performance_metrics(self.trades, initial_capital=65.0)

        self.assertEqual(metrics["win_count"], 270)
        self.assertEqual(metrics["loss_count"], 463)
        self.assertAlmostEqual(metrics["win_rate"], 36.83, places=1)
        self.assertAlmostEqual(metrics["total_net_pnl"], -38.27, places=1)
        self.assertAlmostEqual(metrics["profit_factor"], 0.564, places=2)
        self.assertAlmostEqual(metrics["expectancy_pct"], -0.527, places=2)
        self.assertEqual(metrics["max_consecutive_losses"], 13)
        self.assertAlmostEqual(metrics["max_drawdown_pct"], 58.87, places=1)

if __name__ == "__main__":
    unittest.main()

