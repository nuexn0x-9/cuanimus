"""
CUANIMUS Trading Session Lifecycle & Autonomous Automation Engine.
Governs execution sessions in PAPER_AUTO and TESTNET_AUTO modes.
Provides strict runtime state machines, session duration bounds, error budgets,
heartbeat health checks, and independent human kill-switch override.
"""
import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, Any, Optional, List

from cuanimus.risk.engine import RiskEngine
from cuanimus.execution.paper_safety import PaperExecutionSafetyGuard, FatalSafetyViolationError

logger = logging.getLogger(__name__)


class SessionMode(str, Enum):
    PAPER_AUTO = "PAPER_AUTO"
    TESTNET_AUTO = "TESTNET_AUTO"


class SessionState(str, Enum):
    CREATED = "CREATED"
    VALIDATING = "VALIDATING"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPING = "STOPPING"
    STOPPED = "STOPPED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


# Valid state machine transitions
VALID_STATE_TRANSITIONS: Dict[SessionState, List[SessionState]] = {
    SessionState.CREATED: [SessionState.VALIDATING, SessionState.STOPPED, SessionState.FAILED],
    SessionState.VALIDATING: [SessionState.RUNNING, SessionState.STOPPED, SessionState.FAILED],
    SessionState.RUNNING: [SessionState.PAUSED, SessionState.STOPPING, SessionState.STOPPED, SessionState.EXPIRED, SessionState.FAILED],
    SessionState.PAUSED: [SessionState.RUNNING, SessionState.STOPPING, SessionState.STOPPED, SessionState.EXPIRED],
    SessionState.STOPPING: [SessionState.STOPPED, SessionState.FAILED],
    SessionState.STOPPED: [],
    SessionState.EXPIRED: [],
    SessionState.FAILED: [],
}


@dataclass
class TradingSession:
    """Represents an active or historical autonomous trading session."""
    session_id: str
    agent_id: str
    mode: SessionMode
    state: SessionState = SessionState.CREATED
    max_duration_seconds: int = 3600
    max_trades: int = 20
    error_budget: int = 3
    heartbeat_timeout_seconds: int = 60

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    stopped_at: Optional[datetime] = None
    last_heartbeat: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    trade_count: int = 0
    error_count: int = 0
    stop_reason: Optional[str] = None
    emergency_stopped: bool = False

    def transition_to(self, new_state: SessionState, reason: Optional[str] = None) -> None:
        """Transitions state according to deterministic lifecycle graph."""
        allowed = VALID_STATE_TRANSITIONS.get(self.state, [])
        if new_state not in allowed:
            raise ValueError(f"Illegal session state transition from {self.state.value} to {new_state.value}")
        self.state = new_state
        if reason:
            self.stop_reason = reason
        if new_state in [SessionState.STOPPED, SessionState.EXPIRED, SessionState.FAILED]:
            self.stopped_at = datetime.now(timezone.utc)

    def is_active(self) -> bool:
        return self.state in [SessionState.RUNNING, SessionState.PAUSED]

    def check_expired(self) -> bool:
        """Checks if session has exceeded its maximum allocated duration."""
        if not self.started_at:
            return False
        elapsed = (datetime.now(timezone.utc) - self.started_at).total_seconds()
        return elapsed >= self.max_duration_seconds

    def check_heartbeat_timeout(self) -> bool:
        """Checks if agent heartbeat has gone silent."""
        elapsed = (datetime.now(timezone.utc) - self.last_heartbeat).total_seconds()
        return elapsed >= self.heartbeat_timeout_seconds

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "mode": self.mode.value,
            "state": self.state.value,
            "max_duration_seconds": self.max_duration_seconds,
            "max_trades": self.max_trades,
            "trade_count": self.trade_count,
            "error_count": self.error_count,
            "error_budget": self.error_budget,
            "is_active": self.is_active(),
            "emergency_stopped": self.emergency_stopped,
            "stop_reason": self.stop_reason,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "stopped_at": self.stopped_at.isoformat() if self.stopped_at else None,
            "last_heartbeat": self.last_heartbeat.isoformat(),
        }


class TradingSessionManager:
    """
    Manages active trading sessions, life-cycle transitions,
    health checks, and operator emergency stop mechanisms.
    """
    def __init__(self, risk_engine: Optional[RiskEngine] = None):
        self.risk_engine = risk_engine or RiskEngine()
        self._sessions: Dict[str, TradingSession] = {}

    def create_session(
        self,
        agent_id: str,
        mode: SessionMode = SessionMode.PAPER_AUTO,
        max_duration_seconds: int = 3600,
        max_trades: int = 20,
        error_budget: int = 3,
        heartbeat_timeout_seconds: int = 60,
    ) -> TradingSession:
        """Instantiates a new trading session in CREATED state."""
        # Enforce that LIVE trading is NEVER accepted
        if isinstance(mode, str) and mode.upper() == "LIVE":
            raise FatalSafetyViolationError("FATAL RISK VIOLATION: LIVE session mode is strictly forbidden!")

        session_id = f"sess_{uuid.uuid4().hex[:8]}"
        session = TradingSession(
            session_id=session_id,
            agent_id=agent_id,
            mode=mode,
            max_duration_seconds=max_duration_seconds,
            max_trades=max_trades,
            error_budget=error_budget,
            heartbeat_timeout_seconds=heartbeat_timeout_seconds,
        )
        self._sessions[session_id] = session
        return session

    def start_session(self, session_id: str) -> TradingSession:
        """Validates prerequisites and transitions session to RUNNING."""
        sess = self._sessions.get(session_id)
        if not sess:
            raise KeyError(f"Session {session_id} not found")

        # Step 1: Validating
        sess.transition_to(SessionState.VALIDATING)

        # Check risk engine emergency stop
        if self.risk_engine.emergency_stop_active:
            sess.transition_to(SessionState.FAILED, reason="RiskEngine emergency stop is active")
            raise RuntimeError("Cannot start session: Global RiskEngine emergency stop is active")

        # Step 2: Running
        sess.transition_to(SessionState.RUNNING)
        sess.started_at = datetime.now(timezone.utc)
        sess.last_heartbeat = datetime.now(timezone.utc)
        return sess

    def pause_session(self, session_id: str, reason: str = "Operator requested pause") -> TradingSession:
        sess = self._sessions.get(session_id)
        if not sess:
            raise KeyError(f"Session {session_id} not found")
        sess.transition_to(SessionState.PAUSED, reason=reason)
        return sess

    def resume_session(self, session_id: str) -> TradingSession:
        sess = self._sessions.get(session_id)
        if not sess:
            raise KeyError(f"Session {session_id} not found")
        sess.transition_to(SessionState.RUNNING)
        sess.last_heartbeat = datetime.now(timezone.utc)
        return sess

    def stop_session(self, session_id: str, reason: str = "Operator requested stop") -> TradingSession:
        sess = self._sessions.get(session_id)
        if not sess:
            raise KeyError(f"Session {session_id} not found")
        if sess.state != SessionState.STOPPED:
            sess.transition_to(SessionState.STOPPED, reason=reason)
        return sess

    def emergency_stop(self, session_id: Optional[str] = None, reason: str = "Human Kill-Switch Activated") -> Dict[str, Any]:
        """
        Global or session-specific kill switch. Halts sessions immediately and trips RiskEngine.
        Works independently without requiring agent agreement.
        """
        self.risk_engine.trigger_emergency_stop(reason=reason)
        halted = []

        target_sessions = [self._sessions[session_id]] if (session_id and session_id in self._sessions) else self._sessions.values()

        for s in target_sessions:
            if s.is_active() or s.state in [SessionState.CREATED, SessionState.VALIDATING]:
                s.emergency_stopped = True
                s.transition_to(SessionState.STOPPED, reason=f"EMERGENCY_STOP: {reason}")
                halted.append(s.session_id)

        logger.critical(f"EMERGENCY KILL SWITCH ACTIVATED. Halted sessions: {halted}. Reason: {reason}")
        return {
            "emergency_stop_triggered": True,
            "risk_engine_locked": True,
            "halted_sessions": halted,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def record_heartbeat(self, session_id: str) -> bool:
        """Records agent presence heartbeat."""
        sess = self._sessions.get(session_id)
        if not sess or not sess.is_active():
            return False
        sess.last_heartbeat = datetime.now(timezone.utc)
        return True

    def evaluate_session_health(self, session_id: str) -> Dict[str, Any]:
        """Runs automated watchdog checks on an active session."""
        sess = self._sessions.get(session_id)
        if not sess:
            raise KeyError(f"Session {session_id} not found")

        if not sess.is_active():
            return {"healthy": False, "state": sess.state.value, "reason": "Session not active"}

        # 1. Check max duration
        if sess.check_expired():
            sess.transition_to(SessionState.EXPIRED, reason="Session max duration reached")
            return {"healthy": False, "state": sess.state.value, "reason": "Max duration reached"}

        # 2. Check trade count limit
        if sess.trade_count >= sess.max_trades:
            sess.transition_to(SessionState.STOPPED, reason=f"Max trade count reached ({sess.max_trades})")
            return {"healthy": False, "state": sess.state.value, "reason": "Max trade count reached"}

        # 3. Check error budget
        if sess.error_count >= sess.error_budget:
            sess.transition_to(SessionState.FAILED, reason=f"Error budget exhausted ({sess.error_count}/{sess.error_budget})")
            return {"healthy": False, "state": sess.state.value, "reason": "Error budget exhausted"}

        # 4. Check heartbeat timeout
        if sess.check_heartbeat_timeout():
            sess.transition_to(SessionState.FAILED, reason=f"Heartbeat timed out after {sess.heartbeat_timeout_seconds}s")
            return {"healthy": False, "state": sess.state.value, "reason": "Heartbeat timed out"}

        return {"healthy": True, "state": sess.state.value}

    def record_step(self, session_id: str, is_error: bool = False, trade_executed: bool = False) -> None:
        """Records iteration progress and checks health."""
        sess = self._sessions.get(session_id)
        if not sess:
            return
        if is_error:
            sess.error_count += 1
        if trade_executed:
            sess.trade_count += 1
        self.evaluate_session_health(session_id)

    def get_session(self, session_id: str) -> Optional[TradingSession]:
        return self._sessions.get(session_id)

    def list_sessions(self) -> List[Dict[str, Any]]:
        return [s.to_dict() for s in self._sessions.values()]
