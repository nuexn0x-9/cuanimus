"""
Unit and Integration Tests for CUANIMUS Web Control Center & REST Control Plane.
Verifies:
- All REST API endpoints and data contracts in ControlPlaneAPI
- Order FSM tracking and Decision Trace causality
- Multi-Asset Market Regime matrix and Candle generator
- Risk limits, exposure gauges, and circuit breaker status
- AI Agent sessions, watchdog state, and session controls
- AI-assisted configuration generation and JSON Schema dynamic form support
- Telegram notification service status and test dispatch
- Global Human Emergency Kill Switch and reset invariants
- Multi-threaded HTTP daemon request routing and static asset serving
"""
import os
import sys
import json
import time
import threading
import unittest
import urllib.request
import urllib.error

from cuanimus.api.control_plane import ControlPlaneAPI
from cuanimus.api.http_server import HttpServerDaemon
from cuanimus.api.telegram import TelegramNotifier


class TestControlPlaneAPI(unittest.TestCase):
    """Verifies all programmatic endpoints in ControlPlaneAPI."""

    def setUp(self):
        self.api = ControlPlaneAPI(base_dir=".")

    def test_system_status_and_safety_locks(self):
        status = self.api.get_system_status()
        self.assertIn("environment", status)
        self.assertIn("safety_status", status)
        self.assertIn("subsystems", status)
        self.assertTrue(status["dry_run"])
        self.assertFalse(status["live_trading_enabled"])
        self.assertIn("risk_engine", status["subsystems"])
        self.assertIn("telegram", status["subsystems"])

    def test_trading_positions_and_orders(self):
        positions = self.api.get_positions()
        self.assertIsInstance(positions, list)
        self.assertGreater(len(positions), 0)
        p0 = positions[0]
        self.assertIn("symbol", p0)
        self.assertIn("entry_price", p0)
        self.assertIn("mark_price", p0)
        self.assertIn("stop_loss", p0)
        self.assertIn("take_profit", p0)
        self.assertEqual(p0["risk_status"], "PROTECTED")

        orders = self.api.get_orders()
        self.assertIsInstance(orders, list)
        self.assertGreater(len(orders), 0)
        o0 = orders[0]
        self.assertIn("client_order_id", o0)
        self.assertIn("status", o0)

    def test_decision_traces_causality(self):
        traces = self.api.get_decision_traces()
        self.assertIsInstance(traces, list)
        self.assertGreater(len(traces), 0)
        t0 = traces[0]
        self.assertIn("steps", t0)
        stages = [s["stage"] for s in t0["steps"]]
        self.assertTrue(any("Request" in s for s in stages))
        self.assertTrue(any("Regime" in s or "Context" in s for s in stages))
        self.assertTrue(any("Risk" in s for s in stages))
        self.assertTrue(any("Execution" in s for s in stages))

    def test_markets_watchlist_and_regimes(self):
        watchlist = self.api.get_market_watchlist()
        self.assertIsInstance(watchlist, list)
        self.assertGreater(len(watchlist), 0)
        w0 = watchlist[0]
        self.assertIn("symbol", w0)
        self.assertIn("price", w0)
        self.assertIn("regime", w0)
        self.assertIn("current_signal", w0)

        regimes = self.api.get_market_regimes()
        self.assertIn("matrix", regimes)
        self.assertGreater(len(regimes["matrix"]), 0)

    def test_candles_fetching_and_indicator_calculation(self):
        data = self.api.get_candles(symbol="ETH/USDT:USDT", timeframe="15m", limit=30)
        self.assertIn("candles", data)
        self.assertIn("indicators", data)
        self.assertEqual(len(data["candles"]), 30)
        c0 = data["candles"][-1]
        self.assertIn("open", c0)
        self.assertIn("high", c0)
        self.assertIn("low", c0)
        self.assertIn("close", c0)
        self.assertIn("ema20", c0)
        self.assertIn("ema50", c0)

    def test_risk_status_and_exposure_meters(self):
        risk = self.api.get_risk_status()
        self.assertIn("equity", risk)
        self.assertIn("daily_loss", risk)
        self.assertIn("portfolio_drawdown", risk)
        self.assertIn("total_exposure", risk)
        self.assertIn("current_pct", risk["daily_loss"])
        self.assertIn("limit_pct", risk["daily_loss"])
        self.assertFalse(risk["emergency_stop_active"])

    def test_emergency_stop_and_reset(self):
        # Trigger emergency stop
        stop_res = self.api.trigger_emergency_stop(reason="Unit Test Flash Crash")
        self.assertTrue(stop_res["emergency_stop_triggered"])
        self.assertTrue(self.api.risk_engine.emergency_stop_active)

        status = self.api.get_system_status()
        self.assertTrue(status["emergency_stop_active"])

        # Reset emergency stop
        reset_res = self.api.reset_emergency_stop()
        self.assertFalse(reset_res["emergency_stop_active"])
        self.assertFalse(self.api.risk_engine.emergency_stop_active)

    def test_agent_sessions_and_lifecycle_controls(self):
        sess = self.api.create_paper_session(agent_id="test-copilot", max_duration=3600, max_trades=10)
        sess_id = sess["session_id"]
        self.assertEqual(sess["state"], "RUNNING")

        # Pause
        p_res = self.api.manage_agent_session(sess_id, "pause")
        self.assertEqual(p_res["status"], "PAUSED")

        # Resume
        r_res = self.api.manage_agent_session(sess_id, "resume")
        self.assertEqual(r_res["status"], "RUNNING")

        # Stop
        s_res = self.api.manage_agent_session(sess_id, "stop")
        self.assertEqual(s_res["status"], "STOPPED")

    def test_ai_assisted_configuration_proposal(self):
        res = self.api.propose_agent_config("Setup conservative ETH paper trading with 0.5% risk and structure_v2b")
        self.assertIn("proposed_configuration", res)
        self.assertIn("diff", res)
        cfg = res["proposed_configuration"]
        self.assertEqual(cfg["environment"]["env_name"], "paper")
        self.assertEqual(cfg["risk"]["risk_per_trade_pct"], 0.5)
        self.assertIn("ETH/USDT:USDT", cfg["strategy"]["pairs"])

    def test_telegram_notifier_service(self):
        tg = TelegramNotifier(enabled=False)
        status = tg.get_status()
        self.assertIn("enabled", status)
        self.assertIn("is_configured", status)
        self.assertIn("bot_token_masked", status)

        # Dispatch should cleanly report skipped disabled
        res = tg.send_message("Test Ping")
        self.assertFalse(res["success"])
        self.assertEqual(res["reason"], "Telegram integration is disabled in configuration")


class TestHttpServerDaemonIntegration(unittest.TestCase):
    """Verifies live HTTP server routing, JSON endpoints, and static asset delivery."""

    @classmethod
    def setUpClass(cls):
        cls.port = 8991
        cls.daemon = HttpServerDaemon(host="127.0.0.1", port=cls.port, base_dir=".")
        cls.thread = threading.Thread(target=cls.daemon.start, kwargs={"blocking": True}, daemon=True)
        cls.thread.start()
        time.sleep(0.5)  # Allow socket to bind

    @classmethod
    def tearDownClass(cls):
        cls.daemon.stop()
        time.sleep(0.2)

    def _get(self, path: str):
        url = f"http://127.0.0.1:{self.port}{path}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = resp.read()
            return resp.status, resp.headers.get_content_type(), data

    def _post(self, path: str, json_body: dict):
        url = f"http://127.0.0.1:{self.port}{path}"
        data_bytes = json.dumps(json_body).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = resp.read()
            return resp.status, resp.headers.get_content_type(), data

    def test_http_get_system_status(self):
        status, ctype, body = self._get("/api/system/status")
        self.assertEqual(status, 200)
        self.assertEqual(ctype, "application/json")
        data = json.loads(body.decode("utf-8"))
        self.assertIn("SAFE", data["safety_status"])
        self.assertIn("subsystems", data)

    def test_http_get_positions_and_risk(self):
        status, ctype, body = self._get("/api/trading/positions")
        self.assertEqual(status, 200)
        data = json.loads(body.decode("utf-8"))
        self.assertIn("positions", data)

        status, ctype, body = self._get("/api/risk/status")
        self.assertEqual(status, 200)
        risk_data = json.loads(body.decode("utf-8"))
        self.assertIn("equity", risk_data)

    def test_http_post_emergency_stop_lifecycle(self):
        # Trigger kill switch over HTTP
        status, ctype, body = self._post("/api/system/emergency-stop", {"reason": "HTTP Integration Test"})
        self.assertEqual(status, 200)
        res = json.loads(body.decode("utf-8"))
        self.assertTrue(res["emergency_stop_triggered"])

        # Reset kill switch over HTTP
        status, ctype, body = self._post("/api/system/reset-emergency-stop", {})
        self.assertEqual(status, 200)
        reset_res = json.loads(body.decode("utf-8"))
        self.assertFalse(reset_res["emergency_stop_active"])

    def test_http_serve_static_index_html(self):
        status, ctype, body = self._get("/")
        self.assertEqual(status, 200)
        self.assertEqual(ctype, "text/html")
        content = body.decode("utf-8")
        self.assertIn("CUANIMUS", content)
        self.assertIn("Trading Control Center", content)

    def test_http_serve_static_css_and_js(self):
        status, ctype, body = self._get("/css/app.css")
        self.assertEqual(status, 200)
        self.assertEqual(ctype, "text/css")

        status, ctype, body = self._get("/js/app.js")
        self.assertEqual(status, 200)
        self.assertIn("javascript", ctype)


if __name__ == "__main__":
    unittest.main()
