"""
Test Suite for Trading Session Lifecycle, Automation Modes, and Watchdog Protection.
"""
import unittest
from datetime import datetime, timezone, timedelta

from cuanimus.agent.session import (
    TradingSessionManager,
    TradingSession,
    SessionMode,
    SessionState,
)
from cuanimus.risk.engine import RiskEngine
from cuanimus.execution.paper_safety import FatalSafetyViolationError


class TestTradingSessionAutomation(unittest.TestCase):
    def setUp(self):
        self.risk_engine = RiskEngine()
        self.manager = TradingSessionManager(risk_engine=self.risk_engine)

    def test_session_lifecycle_progression(self):
        """Session transitions through CREATED -> VALIDATING -> RUNNING -> PAUSED -> RUNNING -> STOPPED."""
        sess = self.manager.create_session(
            agent_id="auto_trader",
            mode=SessionMode.PAPER_AUTO,
            max_duration_seconds=3600,
        )
        self.assertEqual(sess.state, SessionState.CREATED)

        # Start session
        self.manager.start_session(sess.session_id)
        self.assertEqual(sess.state, SessionState.RUNNING)
        self.assertTrue(sess.is_active())
        self.assertIsNotNone(sess.started_at)

        # Pause session
        self.manager.pause_session(sess.session_id, reason="Market volatility spike")
        self.assertEqual(sess.state, SessionState.PAUSED)
        self.assertTrue(sess.is_active())

        # Resume session
        self.manager.resume_session(sess.session_id)
        self.assertEqual(sess.state, SessionState.RUNNING)

        # Stop session
        self.manager.stop_session(sess.session_id, reason="End of trading day")
        self.assertEqual(sess.state, SessionState.STOPPED)
        self.assertFalse(sess.is_active())
        self.assertIsNotNone(sess.stopped_at)

    def test_illegal_session_transition_raises_error(self):
        """Illegal state transitions (e.g. STOPPED -> RUNNING) raise ValueError."""
        sess = self.manager.create_session(
            agent_id="auto_trader",
            mode=SessionMode.PAPER_AUTO,
        )
        self.manager.start_session(sess.session_id)
        self.manager.stop_session(sess.session_id)

        # Attempt illegal resume from STOPPED
        with self.assertRaises(ValueError) as ctx:
            sess.transition_to(SessionState.RUNNING)
        self.assertIn("Illegal session state transition", str(ctx.exception))

    def test_live_trading_mode_is_strictly_forbidden(self):
        """Attempting to instantiate a session in LIVE mode throws FatalSafetyViolationError."""
        with self.assertRaises(FatalSafetyViolationError) as ctx:
            self.manager.create_session(
                agent_id="rogue_agent",
                mode="LIVE",
            )
        self.assertIn("FATAL RISK VIOLATION", str(ctx.exception))

    def test_watchdog_exhausted_error_budget_fails_session(self):
        """When an automated session exceeds its error budget, watchdog halts it in FAILED state."""
        sess = self.manager.create_session(
            agent_id="fragile_agent",
            mode=SessionMode.PAPER_AUTO,
            error_budget=2,
        )
        self.manager.start_session(sess.session_id)

        # Step 1 error
        self.manager.record_step(sess.session_id, is_error=True)
        self.assertEqual(sess.state, SessionState.RUNNING)

        # Step 2 error (exhausts budget)
        self.manager.record_step(sess.session_id, is_error=True)
        self.assertEqual(sess.state, SessionState.FAILED)
        self.assertIn("Error budget exhausted", sess.stop_reason)

    def test_watchdog_max_trades_safely_halts_session(self):
        """When session reaches max_trades cap, it is cleanly stopped."""
        sess = self.manager.create_session(
            agent_id="capped_trader",
            mode=SessionMode.PAPER_AUTO,
            max_trades=3,
        )
        self.manager.start_session(sess.session_id)

        self.manager.record_step(sess.session_id, trade_executed=True)
        self.manager.record_step(sess.session_id, trade_executed=True)
        self.assertEqual(sess.state, SessionState.RUNNING)

        # 3rd trade reaches cap
        self.manager.record_step(sess.session_id, trade_executed=True)
        self.assertEqual(sess.state, SessionState.STOPPED)
        self.assertIn("Max trade count reached", sess.stop_reason)

    def test_watchdog_heartbeat_timeout(self):
        """When agent heartbeat stops, watchdog detects silent agent and fails session."""
        sess = self.manager.create_session(
            agent_id="silent_agent",
            mode=SessionMode.PAPER_AUTO,
            heartbeat_timeout_seconds=10,
        )
        self.manager.start_session(sess.session_id)

        # Simulate time jump past heartbeat timeout
        sess.last_heartbeat = datetime.now(timezone.utc) - timedelta(seconds=20)
        health = self.manager.evaluate_session_health(sess.session_id)

        self.assertFalse(health["healthy"])
        self.assertEqual(sess.state, SessionState.FAILED)
        self.assertIn("Heartbeat timed out", sess.stop_reason)

    def test_independent_human_kill_switch_overrides_all(self):
        """Operator emergency stop halts active sessions and locks RiskEngine without agent consent."""
        sess1 = self.manager.create_session(agent_id="bot_1", mode=SessionMode.PAPER_AUTO)
        sess2 = self.manager.create_session(agent_id="bot_2", mode=SessionMode.PAPER_AUTO)
        self.manager.start_session(sess1.session_id)
        self.manager.start_session(sess2.session_id)

        # Activate Emergency Stop
        kill_res = self.manager.emergency_stop(reason="Flash crash alert - human kill switch")

        self.assertTrue(kill_res["emergency_stop_triggered"])
        self.assertTrue(kill_res["risk_engine_locked"])
        self.assertTrue(self.risk_engine.emergency_stop_active)

        self.assertEqual(sess1.state, SessionState.STOPPED)
        self.assertEqual(sess2.state, SessionState.STOPPED)
        self.assertTrue(sess1.emergency_stopped)
        self.assertTrue(sess2.emergency_stopped)
