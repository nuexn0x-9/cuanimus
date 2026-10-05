"""
Unit tests for CUANIMUS Binance Exchange Adapter and new ControlPlaneAPI endpoints.
"""
import unittest
from unittest.mock import patch, MagicMock
from cuanimus.exchange.binance_adapter import (
    to_binance_symbol,
    from_binance_symbol,
    BinancePublicAdapter,
    BinanceAPIError,
    get_binance_adapter,
)
from cuanimus.api.control_plane import ControlPlaneAPI


class TestBinanceAdapter(unittest.TestCase):
    """Verifies symbol conversions and public adapter behavior."""

    def test_symbol_conversions(self):
        self.assertEqual(to_binance_symbol("ETH/USDT:USDT"), "ETHUSDT")
        self.assertEqual(to_binance_symbol("BTC/USDT:USDT"), "BTCUSDT")
        self.assertEqual(to_binance_symbol("SOL/USDT:USDT"), "SOLUSDT")
        self.assertEqual(from_binance_symbol("ETHUSDT"), "ETH/USDT:USDT")
        self.assertEqual(from_binance_symbol("BTCUSDT"), "BTC/USDT:USDT")

    def test_normalize_ticker(self):
        adapter = BinancePublicAdapter()
        raw = {
            "symbol": "ETHUSDT",
            "lastPrice": "2716.50",
            "priceChangePercent": "2.45",
            "volume": "10500.5",
            "quoteVolume": "28525000.0",
            "highPrice": "2750.0",
            "lowPrice": "2680.0",
            "count": 45200,
            "closeTime": 1728120000000,
        }
        normalized = adapter._normalize_ticker(raw, "ETH/USDT:USDT")
        self.assertEqual(normalized["symbol"], "ETH/USDT:USDT")
        self.assertEqual(normalized["binance_symbol"], "ETHUSDT")
        self.assertEqual(normalized["price"], 2716.50)
        self.assertEqual(normalized["change_24h_pct"], 2.45)
        self.assertEqual(normalized["high_24h"], 2750.0)
        self.assertEqual(normalized["low_24h"], 2680.0)

    @patch.object(BinancePublicAdapter, "_get")
    def test_mocked_get_klines(self, mock_get):
        mock_get.return_value = [
            [1728120000000, "2700.0", "2720.0", "2695.0", "2715.0", "150.0", 1728120899999, "407000.0", 1200, "75.0", "203000.0", "0"]
        ]
        adapter = BinancePublicAdapter()
        klines = adapter.get_klines("ETH/USDT:USDT", "15m", 1)
        self.assertEqual(len(klines), 1)
        k = klines[0]
        self.assertEqual(k["open"], 2700.0)
        self.assertEqual(k["high"], 2720.0)
        self.assertEqual(k["low"], 2695.0)
        self.assertEqual(k["close"], 2715.0)


class TestNewControlPlaneEndpoints(unittest.TestCase):
    """Verifies new market, AI, and MCP methods in ControlPlaneAPI."""

    def setUp(self):
        self.api = ControlPlaneAPI(base_dir=".")

    def test_market_pairs(self):
        res = self.api.get_market_pairs()
        self.assertIn("pairs", res)
        self.assertIn("total", res)
        self.assertIsInstance(res["pairs"], list)

    def test_ai_config_get_and_test(self):
        ai_cfg = self.api.get_ai_config()
        self.assertIn("enabled", ai_cfg)
        self.assertIn("provider", ai_cfg)
        self.assertIn("has_api_key", ai_cfg)

        # Test mock provider connection
        test_res = self.api.test_ai_connection({"provider": "mock", "model_name": "mock-model"})
        self.assertEqual(test_res["status"], "CONNECTED")
        self.assertGreater(test_res["latency_ms"], 0)

    def test_list_mcp_tools(self):
        tools = self.api.list_mcp_tools()
        self.assertIsInstance(tools, list)
        self.assertGreater(len(tools), 0)
        tool_names = [t["name"] for t in tools]
        self.assertIn("market.get_snapshot", tool_names)


if __name__ == "__main__":
    unittest.main()
