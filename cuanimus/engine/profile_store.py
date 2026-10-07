"""
CUANIMUS Trading Profile & Autonomous Session Database Store.
Provides schema creation and persistence for SQLite and PostgreSQL.
"""
import os
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from cuanimus.core.database import DatabaseManager
from cuanimus.engine.models import TradingProfile, AutonomousSession, SessionStatus, DecisionTraceRecord, DecisionMode, ExecutionMode

logger = logging.getLogger(__name__)


class ProfileStore:
    """Manages CRUD and persistence for TradingProfiles and AutonomousSessions."""

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager.get_instance()
        self._ensure_schema()
        self._seed_default_profiles_if_empty()

    def _ensure_schema(self) -> None:
        """Creates tables for profiles, sessions, and traces if they do not exist."""
        sql_profiles = """
        CREATE TABLE IF NOT EXISTS trading_profiles (
            profile_id VARCHAR(64) PRIMARY KEY,
            name VARCHAR(128) NOT NULL,
            symbol VARCHAR(32) NOT NULL,
            timeframe VARCHAR(16) NOT NULL DEFAULT '15m',
            decision_mode VARCHAR(32) NOT NULL DEFAULT 'strategy',
            strategy_id VARCHAR(64),
            strategy_params TEXT,
            agent_id VARCHAR(64),
            risk_profile VARCHAR(32) NOT NULL DEFAULT 'conservative',
            execution_mode VARCHAR(32) NOT NULL DEFAULT 'paper',
            max_open_positions INTEGER DEFAULT 1,
            max_trades_per_day INTEGER DEFAULT 10,
            stop_loss_pct REAL DEFAULT 1.5,
            take_profit_pct REAL DEFAULT 3.0,
            trailing_stop_pct REAL DEFAULT 0.0,
            enabled INTEGER DEFAULT 1,
            auto_start INTEGER DEFAULT 0,
            is_running INTEGER DEFAULT 0,
            last_processed_candle VARCHAR(64),
            created_at VARCHAR(64),
            updated_at VARCHAR(64)
        );
        """

        sql_sessions = """
        CREATE TABLE IF NOT EXISTS autonomous_sessions (
            session_id VARCHAR(64) PRIMARY KEY,
            profile_id VARCHAR(64),
            status VARCHAR(32) NOT NULL,
            started_at VARCHAR(64),
            stopped_at VARCHAR(64),
            heartbeat VARCHAR(64),
            processed_candles INTEGER DEFAULT 0,
            signals_detected INTEGER DEFAULT 0,
            signals_rejected INTEGER DEFAULT 0,
            orders_created INTEGER DEFAULT 0,
            orders_filled INTEGER DEFAULT 0,
            errors_count INTEGER DEFAULT 0,
            realized_pnl REAL DEFAULT 0.0,
            last_decision TEXT,
            error_message TEXT
        );
        """

        sql_traces = """
        CREATE TABLE IF NOT EXISTS decision_traces (
            trace_id VARCHAR(64) PRIMARY KEY,
            profile_id VARCHAR(64),
            session_id VARCHAR(64),
            symbol VARCHAR(32) NOT NULL,
            timeframe VARCHAR(16) NOT NULL,
            candle_timestamp VARCHAR(64) NOT NULL,
            decision_timestamp VARCHAR(64) NOT NULL,
            market_price REAL NOT NULL,
            decision_mode VARCHAR(32) NOT NULL,
            strategy_signal VARCHAR(32),
            ai_decision VARCHAR(32),
            ai_confidence REAL,
            policy_result VARCHAR(32),
            risk_result VARCHAR(32),
            execution_status VARCHAR(32),
            order_id VARCHAR(64),
            raw_trace TEXT
        );
        """

        try:
            self.db.execute(sql_profiles)
            self.db.execute(sql_sessions)
            self.db.execute(sql_traces)
        except Exception as e:
            logger.error(f"Failed to ensure autonomous engine schema: {e}")

        # Migration: ensure auto_start column exists for existing tables
        try:
            self.db.execute("ALTER TABLE trading_profiles ADD COLUMN auto_start INTEGER DEFAULT 0;")
        except Exception:
            pass

    def _seed_default_profiles_if_empty(self) -> None:
        """Seeds default profiles across the 3 decision modes if table is empty."""
        try:
            cnt = self.db.query_one("SELECT COUNT(*) as c FROM trading_profiles")
            count = cnt["c"] if cnt else 0
            if count == 0:
                now_str = datetime.now(timezone.utc).isoformat()
                defaults = [
                    TradingProfile(
                        profile_id="prof_ada_15m_strategy",
                        name="ADA-15M-HYBRID-V2C",
                        symbol="ADA/USDT:USDT",
                        timeframe="15m",
                        decision_mode=DecisionMode.STRATEGY,
                        strategy_id="hybrid_v2c",
                        strategy_params={
                            "ema_fast": 20,
                            "ema_slow": 50,
                            "stoch_oversold": 30,
                            "stoch_overbought": 70,
                            "pullback_tolerance_pct": 0.8,
                            "volume_multiplier": 1.1,
                            "min_regime_adx": 20,
                        },
                        risk_profile="conservative",
                        execution_mode=ExecutionMode.PAPER,
                        max_open_positions=1,
                        max_trades_per_day=10,
                        stop_loss_pct=1.5,
                        take_profit_pct=3.0,
                        enabled=True,
                        is_running=False,
                        created_at=now_str,
                        updated_at=now_str,
                    ),
                    TradingProfile(
                        profile_id="prof_btc_15m_ai",
                        name="BTC-15M-AI-ANALYST",
                        symbol="BTC/USDT:USDT",
                        timeframe="15m",
                        decision_mode=DecisionMode.AI_AGENT,
                        agent_id="trader-paper",
                        risk_profile="conservative",
                        execution_mode=ExecutionMode.PAPER,
                        max_open_positions=1,
                        max_trades_per_day=5,
                        stop_loss_pct=1.5,
                        take_profit_pct=3.0,
                        enabled=True,
                        is_running=False,
                        created_at=now_str,
                        updated_at=now_str,
                    ),
                    TradingProfile(
                        profile_id="prof_eth_15m_hybrid",
                        name="ETH-15M-HYBRID-COPILOT",
                        symbol="ETH/USDT:USDT",
                        timeframe="15m",
                        decision_mode=DecisionMode.HYBRID,
                        strategy_id="hybrid_v2c",
                        strategy_params={
                            "ema_fast": 20,
                            "ema_slow": 50,
                            "stoch_oversold": 30,
                            "stoch_overbought": 70,
                        },
                        agent_id="trader-paper",
                        risk_profile="conservative",
                        execution_mode=ExecutionMode.PAPER,
                        max_open_positions=1,
                        max_trades_per_day=8,
                        stop_loss_pct=1.5,
                        take_profit_pct=3.0,
                        enabled=True,
                        is_running=False,
                        created_at=now_str,
                        updated_at=now_str,
                    ),
                ]
                for p in defaults:
                    self.save_profile(p)
                logger.info("Seeded 3 default trading profiles into database.")
        except Exception as e:
            logger.warning(f"Could not seed default profiles: {e}")

    # --- Profile Operations ---

    def list_profiles(self) -> List[TradingProfile]:
        """Returns all trading profiles."""
        rows = self.db.query("SELECT * FROM trading_profiles ORDER BY created_at ASC")
        return [TradingProfile.from_dict(r) for r in rows]

    def get_profile(self, profile_id: str) -> Optional[TradingProfile]:
        """Returns a single trading profile by ID."""
        row = self.db.query_one("SELECT * FROM trading_profiles WHERE profile_id = ?", (profile_id,))
        if row:
            return TradingProfile.from_dict(row)
        return None

    def save_profile(self, profile: TradingProfile) -> None:
        """Inserts or updates a trading profile."""
        now_str = datetime.now(timezone.utc).isoformat()
        profile.updated_at = now_str
        p_dict = profile.to_dict()

        existing = self.get_profile(profile.profile_id)
        if existing:
            sql = """
            UPDATE trading_profiles SET
                name = ?,
                symbol = ?,
                timeframe = ?,
                decision_mode = ?,
                strategy_id = ?,
                strategy_params = ?,
                agent_id = ?,
                risk_profile = ?,
                execution_mode = ?,
                max_open_positions = ?,
                max_trades_per_day = ?,
                stop_loss_pct = ?,
                take_profit_pct = ?,
                trailing_stop_pct = ?,
                enabled = ?,
                auto_start = ?,
                is_running = ?,
                last_processed_candle = ?,
                updated_at = ?
            WHERE profile_id = ?
            """
            params = (
                p_dict["name"],
                p_dict["symbol"],
                p_dict["timeframe"],
                p_dict["decision_mode"],
                p_dict["strategy_id"],
                json.dumps(p_dict["strategy_params"]),
                p_dict["agent_id"],
                p_dict["risk_profile"],
                p_dict["execution_mode"],
                p_dict["max_open_positions"],
                p_dict["max_trades_per_day"],
                p_dict["stop_loss_pct"],
                p_dict["take_profit_pct"],
                p_dict["trailing_stop_pct"],
                1 if p_dict["enabled"] else 0,
                1 if p_dict.get("auto_start") else 0,
                1 if p_dict["is_running"] else 0,
                p_dict["last_processed_candle"],
                now_str,
                profile.profile_id,
            )
            self.db.execute(sql, params)
        else:
            sql = """
            INSERT INTO trading_profiles (
                profile_id, name, symbol, timeframe, decision_mode,
                strategy_id, strategy_params, agent_id, risk_profile,
                execution_mode, max_open_positions, max_trades_per_day,
                stop_loss_pct, take_profit_pct, trailing_stop_pct,
                enabled, auto_start, is_running, last_processed_candle,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                profile.profile_id,
                p_dict["name"],
                p_dict["symbol"],
                p_dict["timeframe"],
                p_dict["decision_mode"],
                p_dict["strategy_id"],
                json.dumps(p_dict["strategy_params"]),
                p_dict["agent_id"],
                p_dict["risk_profile"],
                p_dict["execution_mode"],
                p_dict["max_open_positions"],
                p_dict["max_trades_per_day"],
                p_dict["stop_loss_pct"],
                p_dict["take_profit_pct"],
                p_dict["trailing_stop_pct"],
                1 if p_dict["enabled"] else 0,
                1 if p_dict.get("auto_start") else 0,
                1 if p_dict["is_running"] else 0,
                p_dict["last_processed_candle"],
                p_dict["created_at"],
                now_str,
            )
            self.db.execute(sql, params)

    def delete_profile(self, profile_id: str) -> bool:
        """Deletes a trading profile and cleans up associated records."""
        rc = self.db.execute("DELETE FROM trading_profiles WHERE profile_id = ?", (profile_id,))
        return rc > 0

    def update_profile_running_state(self, profile_id: str, is_running: bool, last_candle: Optional[str] = None) -> None:
        """Updates runtime execution flag and latest processed candle timestamp."""
        now_str = datetime.now(timezone.utc).isoformat()
        if last_candle is not None:
            self.db.execute(
                "UPDATE trading_profiles SET is_running = ?, last_processed_candle = ?, updated_at = ? WHERE profile_id = ?",
                (1 if is_running else 0, last_candle, now_str, profile_id),
            )
        else:
            self.db.execute(
                "UPDATE trading_profiles SET is_running = ?, updated_at = ? WHERE profile_id = ?",
                (1 if is_running else 0, now_str, profile_id),
            )

    # --- Session Operations ---

    def list_sessions(self, limit: int = 50) -> List[AutonomousSession]:
        """Returns recent autonomous sessions."""
        rows = self.db.query("SELECT * FROM autonomous_sessions ORDER BY started_at DESC LIMIT ?", (limit,))
        sessions = []
        for r in rows:
            last_dec = None
            if r.get("last_decision"):
                try:
                    last_dec = json.loads(r["last_decision"])
                except Exception:
                    pass
            sessions.append(AutonomousSession(
                session_id=r["session_id"],
                profile_id=r["profile_id"],
                status=SessionStatus(r["status"]) if r.get("status") in SessionStatus._value2member_map_ else SessionStatus.STOPPED,
                started_at=r["started_at"],
                stopped_at=r.get("stopped_at"),
                heartbeat=r.get("heartbeat", r["started_at"]),
                processed_candles=int(r.get("processed_candles") or 0),
                signals_detected=int(r.get("signals_detected") or 0),
                signals_rejected=int(r.get("signals_rejected") or 0),
                orders_created=int(r.get("orders_created") or 0),
                orders_filled=int(r.get("orders_filled") or 0),
                errors_count=int(r.get("errors_count") or 0),
                realized_pnl=float(r.get("realized_pnl") or 0.0),
                last_decision=last_dec,
                error_message=r.get("error_message"),
            ))
        return sessions

    def get_session(self, session_id: str) -> Optional[AutonomousSession]:
        """Returns session by ID."""
        r = self.db.query_one("SELECT * FROM autonomous_sessions WHERE session_id = ?", (session_id,))
        if not r:
            return None
        last_dec = None
        if r.get("last_decision"):
            try:
                last_dec = json.loads(r["last_decision"])
            except Exception:
                pass
        return AutonomousSession(
            session_id=r["session_id"],
            profile_id=r["profile_id"],
            status=SessionStatus(r["status"]) if r.get("status") in SessionStatus._value2member_map_ else SessionStatus.STOPPED,
            started_at=r["started_at"],
            stopped_at=r.get("stopped_at"),
            heartbeat=r.get("heartbeat", r["started_at"]),
            processed_candles=int(r.get("processed_candles") or 0),
            signals_detected=int(r.get("signals_detected") or 0),
            signals_rejected=int(r.get("signals_rejected") or 0),
            orders_created=int(r.get("orders_created") or 0),
            orders_filled=int(r.get("orders_filled") or 0),
            errors_count=int(r.get("errors_count") or 0),
            realized_pnl=float(r.get("realized_pnl") or 0.0),
            last_decision=last_dec,
            error_message=r.get("error_message"),
        )

    def get_active_session_for_profile(self, profile_id: str) -> Optional[AutonomousSession]:
        """Returns current running session for profile if any."""
        r = self.db.query_one(
            "SELECT * FROM autonomous_sessions WHERE profile_id = ? AND status = ? ORDER BY started_at DESC LIMIT 1",
            (profile_id, SessionStatus.RUNNING.value),
        )
        if not r:
            return None
        return self.get_session(r["session_id"])

    def save_session(self, session: AutonomousSession) -> None:
        """Inserts or updates an autonomous session."""
        last_dec_str = json.dumps(session.last_decision) if session.last_decision else None
        existing = self.db.query_one("SELECT session_id FROM autonomous_sessions WHERE session_id = ?", (session.session_id,))
        if existing:
            sql = """
            UPDATE autonomous_sessions SET
                status = ?,
                stopped_at = ?,
                heartbeat = ?,
                processed_candles = ?,
                signals_detected = ?,
                signals_rejected = ?,
                orders_created = ?,
                orders_filled = ?,
                errors_count = ?,
                realized_pnl = ?,
                last_decision = ?,
                error_message = ?
            WHERE session_id = ?
            """
            self.db.execute(sql, (
                session.status.value,
                session.stopped_at,
                session.heartbeat,
                session.processed_candles,
                session.signals_detected,
                session.signals_rejected,
                session.orders_created,
                session.orders_filled,
                session.errors_count,
                session.realized_pnl,
                last_dec_str,
                session.error_message,
                session.session_id,
            ))
        else:
            sql = """
            INSERT INTO autonomous_sessions (
                session_id, profile_id, status, started_at, stopped_at,
                heartbeat, processed_candles, signals_detected, signals_rejected,
                orders_created, orders_filled, errors_count, realized_pnl,
                last_decision, error_message
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            self.db.execute(sql, (
                session.session_id,
                session.profile_id,
                session.status.value,
                session.started_at,
                session.stopped_at,
                session.heartbeat,
                session.processed_candles,
                session.signals_detected,
                session.signals_rejected,
                session.orders_created,
                session.orders_filled,
                session.errors_count,
                session.realized_pnl,
                last_dec_str,
                session.error_message,
            ))

    # --- Decision Trace Operations ---

    def save_trace(self, trace: DecisionTraceRecord) -> None:
        """Saves a full causal decision trace."""
        sql = """
        INSERT INTO decision_traces (
            trace_id, profile_id, session_id, symbol, timeframe,
            candle_timestamp, decision_timestamp, market_price, decision_mode,
            strategy_signal, ai_decision, ai_confidence, policy_result,
            risk_result, execution_status, order_id, raw_trace
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        raw_str = json.dumps(trace.raw_trace) if trace.raw_trace else None
        self.db.execute(sql, (
            trace.trace_id,
            trace.profile_id,
            trace.session_id,
            trace.symbol,
            trace.timeframe,
            trace.candle_timestamp,
            trace.decision_timestamp,
            trace.market_price,
            trace.decision_mode,
            trace.strategy_signal,
            trace.ai_decision,
            trace.ai_confidence,
            trace.policy_result,
            trace.risk_result,
            trace.execution_status,
            trace.order_id,
            raw_str,
        ))

    def list_traces(self, limit: int = 50, profile_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns recent decision traces."""
        if profile_id:
            rows = self.db.query(
                "SELECT * FROM decision_traces WHERE profile_id = ? ORDER BY decision_timestamp DESC LIMIT ?",
                (profile_id, limit),
            )
        else:
            rows = self.db.query(
                "SELECT * FROM decision_traces ORDER BY decision_timestamp DESC LIMIT ?",
                (limit,),
            )
        result = []
        for r in rows:
            raw = {}
            if r.get("raw_trace"):
                try:
                    raw = json.loads(r["raw_trace"])
                except Exception:
                    pass
            item = dict(r)
            item["raw_trace"] = raw
            result.append(item)
        return result
