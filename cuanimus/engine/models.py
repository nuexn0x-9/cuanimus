"""
CUANIMUS Autonomous Trading Engine Data Models & Schemas.
Defines Trading Profiles, Decision Modes, Execution Modes, Autonomous Sessions,
and Structured AI Decision Schemas.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional, List
import uuid
import json


class DecisionMode(str, Enum):
    """The 3 official decision modes of CUANIMUS."""
    STRATEGY = "strategy"      # Mode A: Strategy Template -> Signal -> Policy -> Risk -> Execution
    AI_AGENT = "ai_agent"      # Mode B: Market Context -> AI Agent Decision -> Policy -> Risk -> Execution
    HYBRID = "hybrid"          # Mode C: Strategy Filter -> AI Confirmation -> Policy -> Risk -> Execution


class ExecutionMode(str, Enum):
    """Execution targets."""
    PAPER = "paper"            # Simulated paper execution (Default & Safe)
    TESTNET = "testnet"        # Binance Futures Testnet


class SessionStatus(str, Enum):
    """Status lifecycle for Autonomous Trading Sessions."""
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    FAILED = "FAILED"


@dataclass
class TradingProfile:
    """
    User-configured Trading Profile representing an autonomous trading setup.
    Defines pair, timeframe, decision mode, strategy/agent, risk rules, and execution mode.
    """
    profile_id: str
    name: str
    symbol: str                                    # e.g. "ADA/USDT:USDT" or "ADAUSDT"
    timeframe: str = "15m"                         # 5m, 15m, 1h, 4h
    decision_mode: DecisionMode = DecisionMode.STRATEGY
    strategy_id: Optional[str] = "hybrid_v2c"      # Template from StrategyRegistry
    strategy_params: Dict[str, Any] = field(default_factory=dict)
    agent_id: Optional[str] = "trader-paper"       # Agent from AgentIdentityRegistry
    risk_profile: str = "conservative"             # conservative, balanced, aggressive
    execution_mode: ExecutionMode = ExecutionMode.PAPER
    max_open_positions: int = 1
    max_trades_per_day: int = 10
    stop_loss_pct: float = 1.5                     # 1.5%
    take_profit_pct: float = 3.0                   # 3.0%
    trailing_stop_pct: float = 0.0
    enabled: bool = True
    auto_start: bool = True
    is_running: bool = False
    last_processed_candle: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "profile_id": self.profile_id,
            "name": self.name,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "decision_mode": self.decision_mode.value if isinstance(self.decision_mode, DecisionMode) else str(self.decision_mode),
            "strategy_id": self.strategy_id,
            "strategy_params": self.strategy_params or {},
            "agent_id": self.agent_id,
            "risk_profile": self.risk_profile,
            "execution_mode": self.execution_mode.value if isinstance(self.execution_mode, ExecutionMode) else str(self.execution_mode),
            "max_open_positions": int(self.max_open_positions),
            "max_trades_per_day": int(self.max_trades_per_day),
            "stop_loss_pct": float(self.stop_loss_pct),
            "take_profit_pct": float(self.take_profit_pct),
            "trailing_stop_pct": float(self.trailing_stop_pct),
            "enabled": bool(self.enabled),
            "auto_start": bool(self.auto_start),
            "is_running": bool(self.is_running),
            "last_processed_candle": self.last_processed_candle,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TradingProfile":
        dmode = data.get("decision_mode", "strategy")
        if isinstance(dmode, str):
            try:
                dmode = DecisionMode(dmode)
            except ValueError:
                dmode = DecisionMode.STRATEGY

        emode = data.get("execution_mode", "paper")
        if isinstance(emode, str):
            try:
                emode = ExecutionMode(emode)
            except ValueError:
                emode = ExecutionMode.PAPER

        strat_params = data.get("strategy_params")
        if isinstance(strat_params, str):
            try:
                strat_params = json.loads(strat_params)
            except Exception:
                strat_params = {}
        elif not isinstance(strat_params, dict):
            strat_params = {}

        return cls(
            profile_id=str(data.get("profile_id", f"prof_{uuid.uuid4().hex[:8]}")),
            name=str(data.get("name", "Default Profile")),
            symbol=str(data.get("symbol", "ETH/USDT:USDT")),
            timeframe=str(data.get("timeframe", "15m")),
            decision_mode=dmode,
            strategy_id=data.get("strategy_id", "hybrid_v2c"),
            strategy_params=strat_params,
            agent_id=data.get("agent_id", "trader-paper"),
            risk_profile=str(data.get("risk_profile", "conservative")),
            execution_mode=emode,
            max_open_positions=int(data.get("max_open_positions", 1)),
            max_trades_per_day=int(data.get("max_trades_per_day", 10)),
            stop_loss_pct=float(data.get("stop_loss_pct", 1.5)),
            take_profit_pct=float(data.get("take_profit_pct", 3.0)),
            trailing_stop_pct=float(data.get("trailing_stop_pct", 0.0)),
            enabled=bool(data.get("enabled", True)),
            auto_start=bool(data.get("auto_start", True)),
            is_running=bool(data.get("is_running", False)),
            last_processed_candle=data.get("last_processed_candle"),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            updated_at=data.get("updated_at", datetime.now(timezone.utc).isoformat()),
        )


@dataclass
class AgentDecisionResult:
    """
    Strictly validated structured response schema from AI Agent in Mode B and Mode C.
    Free-form text is never accepted directly as order instructions.
    """
    decision: str                           # "LONG", "SHORT", "HOLD", "APPROVE", "REJECT"
    confidence: float                       # 0.0 to 1.0
    entry_reason: str
    stop_loss_pct: float                    # Suggested SL distance (e.g. 0.015 = 1.5%)
    take_profit_pct: float                  # Suggested TP distance (e.g. 0.03 = 3.0%)
    time_horizon: str = "short"             # "scalp", "short", "swing"
    invalidation_reason: str = ""
    strategy_context: str = ""
    risk_notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "confidence": round(self.confidence, 4),
            "entry_reason": self.entry_reason,
            "stop_loss_pct": round(self.stop_loss_pct, 4),
            "take_profit_pct": round(self.take_profit_pct, 4),
            "time_horizon": self.time_horizon,
            "invalidation_reason": self.invalidation_reason,
            "strategy_context": self.strategy_context,
            "risk_notes": self.risk_notes,
        }


@dataclass
class AutonomousSession:
    """Telemetry and execution metrics for an active or past Autonomous Trading Session."""
    session_id: str
    profile_id: str
    status: SessionStatus = SessionStatus.CREATED
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    stopped_at: Optional[str] = None
    heartbeat: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    processed_candles: int = 0
    signals_detected: int = 0
    signals_rejected: int = 0
    orders_created: int = 0
    orders_filled: int = 0
    errors_count: int = 0
    realized_pnl: float = 0.0
    last_decision: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "profile_id": self.profile_id,
            "status": self.status.value if isinstance(self.status, SessionStatus) else str(self.status),
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "heartbeat": self.heartbeat,
            "processed_candles": self.processed_candles,
            "signals_detected": self.signals_detected,
            "signals_rejected": self.signals_rejected,
            "orders_created": self.orders_created,
            "orders_filled": self.orders_filled,
            "errors_count": self.errors_count,
            "realized_pnl": round(self.realized_pnl, 4),
            "last_decision": self.last_decision,
            "error_message": self.error_message,
        }


@dataclass
class DecisionTraceRecord:
    """Full causal provenance record for an autonomous trading decision."""
    trace_id: str
    profile_id: str
    session_id: str
    symbol: str
    timeframe: str
    candle_timestamp: str
    decision_timestamp: str
    market_price: float
    decision_mode: str
    strategy_signal: str                    # "LONG", "SHORT", "HOLD", "N/A"
    ai_decision: str                        # "LONG", "SHORT", "HOLD", "APPROVE", "REJECT", "N/A"
    ai_confidence: float
    policy_result: str                      # "APPROVED", "VETOED"
    risk_result: str                        # "APPROVED", "VETOED"
    execution_status: str                   # "EXECUTED", "REJECTED", "ABSTAINED"
    order_id: Optional[str] = None
    raw_trace: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "profile_id": self.profile_id,
            "session_id": self.session_id,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "candle_timestamp": self.candle_timestamp,
            "decision_timestamp": self.decision_timestamp,
            "market_price": self.market_price,
            "decision_mode": self.decision_mode,
            "strategy_signal": self.strategy_signal,
            "ai_decision": self.ai_decision,
            "ai_confidence": self.ai_confidence,
            "policy_result": self.policy_result,
            "risk_result": self.risk_result,
            "execution_status": self.execution_status,
            "order_id": self.order_id,
            "raw_trace": self.raw_trace,
        }
