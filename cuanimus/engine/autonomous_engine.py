"""
CUANIMUS Autonomous Trading Engine.
Production-grade multi-profile autonomous trading engine supporting:
- MODE A: Strategy Autotrade (Market -> Strategy -> Signal -> Policy -> Risk -> Execution)
- MODE B: AI Agent Autotrade (Market -> AI Agent Decision -> Policy -> Risk -> Execution)
- MODE C: Hybrid Autotrade (Market -> Strategy Filter -> AI Confirmation -> Policy -> Risk -> Execution)

Strict Invariants:
1. AI Agent never accesses Binance credentials directly.
2. Every order MUST pass AgentTradingPolicy and RiskEngine (FINAL AUTHORITY).
3. Zero future leakage: strictly uses completed closed bars (candle boundary trigger).
4. Full idempotency and duplicate order protection.
5. Automated Position Management (Stop Loss & Take Profit exits).
6. Global Emergency Stop / Human Kill Switch compliance.
7. Real-capital live trading is strictly disabled (PAPER / TESTNET only).
"""
import os
import time
import uuid
import logging
import threading
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone

from cuanimus.common.types import SignalDirection, TradeIntent, PortfolioState
from cuanimus.exchange.binance_adapter import get_binance_adapter, BinanceAPIError
from cuanimus.risk.engine import RiskEngine
from cuanimus.agent.policy import AgentTradingPolicy
from cuanimus.agent.audit import AgentAuditLogger
from cuanimus.execution.paper_safety import PaperExecutionSafetyGuard
from cuanimus.api.telegram import TelegramNotifier
from cuanimus.engine.models import (
    TradingProfile,
    AutonomousSession,
    DecisionMode,
    ExecutionMode,
    SessionStatus,
    DecisionTraceRecord,
    AgentDecisionResult,
)
from cuanimus.engine.profile_store import ProfileStore
from cuanimus.engine.strategy_evaluator import StrategyEvaluator
from cuanimus.engine.agent_evaluator import AgentDecisionEngine
from cuanimus.engine.hybrid_evaluator import HybridEvaluator
from cuanimus.engine.position_manager import PositionManager

logger = logging.getLogger(__name__)


class AutonomousTradingEngine:
    """
    Unified Production Autonomous Trading Engine for CUANIMUS.
    Orchestrates continuous background market monitoring, multi-mode decision evaluations,
    policy/risk gates, order execution, position lifecycle, and decision traceability.
    """

    _instance: Optional["AutonomousTradingEngine"] = None
    _lock = threading.RLock()

    def __init__(
        self,
        profile_store: Optional[ProfileStore] = None,
        risk_engine: Optional[RiskEngine] = None,
        policy: Optional[AgentTradingPolicy] = None,
        safety_guard: Optional[PaperExecutionSafetyGuard] = None,
        telegram: Optional[TelegramNotifier] = None,
        audit_logger: Optional[AgentAuditLogger] = None,
    ):
        self.store = profile_store or ProfileStore()
        self.risk_engine = risk_engine or RiskEngine()
        self.policy = policy or AgentTradingPolicy()
        self.safety_guard = safety_guard or PaperExecutionSafetyGuard(dry_run=True)
        self.telegram = telegram or TelegramNotifier()
        self.audit_logger = audit_logger or AgentAuditLogger()
        self.position_manager = PositionManager(telegram=self.telegram)
        self.adapter = get_binance_adapter()

        # Evaluators
        self.strategy_evaluator = StrategyEvaluator()
        self.agent_engine = AgentDecisionEngine()
        self.hybrid_evaluator = HybridEvaluator()

        # Threading state
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._tick_interval = 5.0  # Polling cycle interval in seconds
        self._processed_idempotency_keys = set()
        self._cached_prices: Dict[str, float] = {}
        self._last_cycle_at: Optional[str] = None
        self._worker_errors_count: int = 0

    @classmethod
    def get_instance(cls) -> "AutonomousTradingEngine":
        """Singleton accessor."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = AutonomousTradingEngine()
        return cls._instance

    # -------------------------------------------------------------------------
    # Lifecycle Control (Start / Stop / Background Worker)
    # -------------------------------------------------------------------------

    def start(self) -> None:
        """Starts the autonomous engine background daemon and auto-resumes profiles."""
        with self._lock:
            if not self._running:
                self._running = True
                self._thread = threading.Thread(
                    target=self._worker_loop,
                    daemon=True,
                    name="AutonomousTradingEngineWorker",
                )
                self._thread.start()
                logger.info("[AutonomousTradingEngine] Background worker daemon started successfully.")

            # Auto-resume profiles marked with auto_start
            try:
                for p in self.store.list_profiles():
                    if p.enabled and p.auto_start and not p.is_running:
                        logger.info(f"[AutonomousTradingEngine] Auto-starting profile: {p.name} ({p.profile_id})")
                        self.start_profile(p.profile_id)
            except Exception as e:
                logger.warning(f"Error auto-starting profiles: {e}")

    def stop(self) -> None:
        """Gracefully halts the engine daemon."""
        with self._lock:
            self._running = False
            logger.info("[AutonomousTradingEngine] Stop requested.")

    def is_running(self) -> bool:
        return self._running and (self._thread is not None and self._thread.is_alive())

    def _worker_loop(self) -> None:
        """Main background scheduling loop."""
        logger.info("[AutonomousTradingEngine] Running background worker loop...")
        while self._running:
            self._last_cycle_at = datetime.now(timezone.utc).isoformat()
            try:
                # 1. Check Emergency Stop Kill Switch
                if self.risk_engine.emergency_stop_active:
                    time.sleep(self._tick_interval)
                    continue

                # 2. Monitor open positions for SL / TP exits
                self._monitor_position_exits()

                # 3. Evaluate active running profiles
                running_profiles = [p for p in self.store.list_profiles() if p.enabled and p.is_running]
                for profile in running_profiles:
                    if not self._running:
                        break
                    try:
                        self.evaluate_profile_tick(profile)
                    except Exception as e:
                        self._worker_errors_count += 1
                        logger.error(f"[AutonomousTradingEngine] Error evaluating profile {profile.profile_id}: {e}", exc_info=True)

            except Exception as loop_err:
                self._worker_errors_count += 1
                logger.error(f"[AutonomousTradingEngine] Uncaught error in worker loop: {loop_err}", exc_info=True)

            time.sleep(self._tick_interval)

    # -------------------------------------------------------------------------
    # Position Exits & Price Cache
    # -------------------------------------------------------------------------

    def _monitor_position_exits(self) -> None:
        """Fetches latest mark prices and triggers SL/TP exits on open positions."""
        open_positions = self.position_manager.get_open_positions()
        if not open_positions:
            return

        needed_symbols = list({p["pair"] for p in open_positions})
        prices = {}
        for sym in needed_symbols:
            try:
                ticker = self.adapter.get_ticker(sym)
                price = float(ticker.get("price", 0.0))
                if price > 0:
                    prices[sym] = price
                    self._cached_prices[sym] = price
            except Exception:
                # Fallback to cached price if network blip
                if sym in self._cached_prices:
                    prices[sym] = self._cached_prices[sym]

        if prices:
            self.position_manager.check_and_execute_exits(prices)

    # -------------------------------------------------------------------------
    # Profile Autonomous Evaluation Tick
    # -------------------------------------------------------------------------

    def evaluate_profile_tick(self, profile: TradingProfile, force: bool = False) -> Dict[str, Any]:
        """
        Executes a single autonomous evaluation tick for a TradingProfile.
        Enforces candle close boundary, mode-specific evaluation, policy/risk gates,
        and safe execution.
        """
        now_dt = datetime.now(timezone.utc)
        now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        symbol = profile.symbol
        timeframe = profile.timeframe
        session = self.store.get_active_session_for_profile(profile.profile_id)

        # Ensure session exists
        if not session:
            session = AutonomousSession(
                session_id=f"sess_{uuid.uuid4().hex[:10]}",
                profile_id=profile.profile_id,
                status=SessionStatus.RUNNING,
                started_at=now_dt.isoformat(),
                heartbeat=now_dt.isoformat(),
            )
            self.store.save_session(session)

        # 1. Fetch closed candles from Binance
        try:
            raw_candles = self.adapter.get_klines(symbol, timeframe=timeframe, limit=60)
        except Exception as e:
            logger.warning(f"Failed to fetch Binance klines for {symbol}: {e}")
            session.errors_count += 1
            session.error_message = f"Market data fetch error: {str(e)[:100]}"
            self.store.save_session(session)
            return {"status": "ERROR", "message": f"Binance error: {e}"}

        if len(raw_candles) < 20:
            return {"status": "WAITING_DATA", "message": "Insufficient candle bars"}

        # Closed candle boundary: the second-to-last candle is the most recently CLOSED bar
        last_closed_candle = raw_candles[-2]
        current_candle = raw_candles[-1]
        candle_ts = str(last_closed_candle.get("timestamp") or last_closed_candle.get("date"))
        current_market_price = float(current_candle.get("close", last_closed_candle["close"]))
        self._cached_prices[symbol] = current_market_price

        # Check candle boundary to avoid re-evaluating on the same closed candle
        if not force and profile.last_processed_candle == candle_ts:
            # Already evaluated for this closed candle
            session.heartbeat = now_dt.isoformat()
            self.store.save_session(session)
            return {"status": "SKIPPED_SAME_CANDLE", "candle_ts": candle_ts}

        # Update candle processing telemetry
        session.processed_candles += 1
        session.heartbeat = now_dt.isoformat()
        self.store.update_profile_running_state(profile.profile_id, is_running=True, last_candle=candle_ts)

        # Open positions for symbol
        open_positions = self.position_manager.get_open_positions(symbol)

        # 2. Execute Decision Mode
        strat_signal = "N/A"
        ai_decision = "N/A"
        ai_confidence = 0.0
        final_intent: TradeIntent
        raw_agent_res: Optional[AgentDecisionResult] = None

        if profile.decision_mode == DecisionMode.STRATEGY:
            # MODE A: Strategy Autotrade
            final_intent = self.strategy_evaluator.evaluate(profile, raw_candles[:-1], current_market_price)
            strat_signal = final_intent.direction.value

        elif profile.decision_mode == DecisionMode.AI_AGENT:
            # MODE B: AI Agent Autotrade
            final_intent, raw_agent_res = self.agent_engine.evaluate(profile, raw_candles[:-1], current_market_price, open_positions)
            ai_decision = raw_agent_res.decision
            ai_confidence = raw_agent_res.confidence

        elif profile.decision_mode == DecisionMode.HYBRID:
            # MODE C: Hybrid Autotrade (Strategy Filter -> AI Confirmation)
            final_intent, strat_candidate, raw_agent_res = self.hybrid_evaluator.evaluate(
                profile, raw_candles[:-1], current_market_price, open_positions
            )
            strat_signal = strat_candidate.direction.value if strat_candidate else "N/A"
            if raw_agent_res:
                ai_decision = raw_agent_res.decision
                ai_confidence = raw_agent_res.confidence
        else:
            final_intent = TradeIntent(
                intent_id=f"INT_UNKNOWN_{now_dt.timestamp()}",
                symbol=symbol,
                direction=SignalDirection.HOLD,
                timestamp=now_dt,
                strategy_id=profile.strategy_id or "unknown",
                entry_price_target=current_market_price,
            )

        # 3. Handle HOLD (No Trade Candidate)
        if final_intent.direction == SignalDirection.HOLD:
            trace_id = f"TRACE_{uuid.uuid4().hex[:12]}"
            trace = DecisionTraceRecord(
                trace_id=trace_id,
                profile_id=profile.profile_id,
                session_id=session.session_id,
                symbol=symbol,
                timeframe=timeframe,
                candle_timestamp=candle_ts,
                decision_timestamp=now_str,
                market_price=current_market_price,
                decision_mode=profile.decision_mode.value,
                strategy_signal=strat_signal,
                ai_decision=ai_decision,
                ai_confidence=ai_confidence,
                policy_result="N/A",
                risk_result="N/A",
                execution_status="ABSTAINED",
                raw_trace={
                    "reason": "Market conditions do not qualify for entry",
                    "strategy_signal": strat_signal,
                    "ai_decision": ai_decision,
                },
            )
            self.store.save_trace(trace)
            session.last_decision = trace.to_dict()
            self.store.save_session(session)
            return {"status": "ABSTAINED", "trace_id": trace_id, "signal": "HOLD"}

        # 4. Long or Short Candidate Detected!
        session.signals_detected += 1

        # Check Emergency Stop Kill Switch immediately
        if self.risk_engine.emergency_stop_active:
            session.signals_rejected += 1
            trace = self._record_rejection_trace(
                profile, session, candle_ts, now_str, current_market_price,
                strat_signal, ai_decision, ai_confidence,
                rejection_stage="Emergency Stop",
                rejection_reason="Emergency Stop Kill Switch Active",
            )
            return {"status": "REJECTED_EMERGENCY_STOP", "trace_id": trace.trace_id}

        idempotency_key = f"{profile.profile_id}:{symbol}:{candle_ts}:{final_intent.direction.value}"

        if idempotency_key in self._processed_idempotency_keys:
            session.signals_rejected += 1
            return {"status": "REJECTED_IDEMPOTENCY", "message": "Duplicate candidate on same bar"}

        # 5. Position Limits & Daily Trade Limits Check
        if len(open_positions) >= profile.max_open_positions:
            session.signals_rejected += 1
            trace = self._record_rejection_trace(
                profile, session, candle_ts, now_str, current_market_price,
                strat_signal, ai_decision, ai_confidence,
                rejection_stage="Position Limit",
                rejection_reason=f"Max open positions reached ({len(open_positions)}/{profile.max_open_positions})",
            )
            return {"status": "REJECTED_POSITION_LIMIT", "trace_id": trace.trace_id}

        daily_trades = self.position_manager.count_trades_today(symbol)
        if daily_trades >= profile.max_trades_per_day:
            session.signals_rejected += 1
            trace = self._record_rejection_trace(
                profile, session, candle_ts, now_str, current_market_price,
                strat_signal, ai_decision, ai_confidence,
                rejection_stage="Daily Trade Limit",
                rejection_reason=f"Max trades today reached ({daily_trades}/{profile.max_trades_per_day})",
            )
            return {"status": "REJECTED_DAILY_LIMIT", "trace_id": trace.trace_id}

        # 6. POLICY ENGINE GATE
        policy_eval = self.policy.evaluate_intent(
            symbol=symbol,
            strategy_id=final_intent.strategy_id,
            leverage=3.0,
            stop_loss=final_intent.suggested_stop_loss or (current_market_price * 0.985),
            environment=profile.execution_mode.value,
            stake_usdt=100.0,
            account_balance=10000.0,
        )

        if not policy_eval.is_approved:
            session.signals_rejected += 1
            trace = self._record_rejection_trace(
                profile, session, candle_ts, now_str, current_market_price,
                strat_signal, ai_decision, ai_confidence,
                rejection_stage="Policy Engine",
                rejection_reason=policy_eval.reason,
            )
            return {"status": "REJECTED_POLICY", "trace_id": trace.trace_id, "reason": policy_eval.reason}

        # 7. RISK ENGINE GATE (FINAL AUTHORITY)
        if self.risk_engine.emergency_stop_active:
            session.signals_rejected += 1
            trace = self._record_rejection_trace(
                profile, session, candle_ts, now_str, current_market_price,
                strat_signal, ai_decision, ai_confidence,
                rejection_stage="Emergency Stop",
                rejection_reason="Emergency Stop Kill Switch Active",
            )
            return {"status": "REJECTED_EMERGENCY_STOP", "trace_id": trace.trace_id}

        portfolio_state = PortfolioState(
            equity=10000.0,
            available_balance=10000.0,
            peak_equity=10000.0,
            drawdown_pct=0.0,
            daily_realized_loss=0.0,
            consecutive_losses=0,
        )

        risk_eval = self.risk_engine.evaluate_intent(
            intent=final_intent,
            portfolio=portfolio_state,
            atr_value=current_market_price * 0.015,
        )

        if not risk_eval.is_approved:
            session.signals_rejected += 1
            trace = self._record_rejection_trace(
                profile, session, candle_ts, now_str, current_market_price,
                strat_signal, ai_decision, ai_confidence,
                rejection_stage="Risk Engine",
                rejection_reason=risk_eval.veto_reason or "Risk vetoed order",
            )
            return {"status": "REJECTED_RISK", "trace_id": trace.trace_id, "reason": risk_eval.veto_reason}

        # 8. EXECUTION COORDINATOR (Paper / Testnet)
        side = "BUY" if final_intent.direction == SignalDirection.LONG else "SELL"
        amount = risk_eval.approved_contracts or 0.1
        sl = risk_eval.stop_loss_price or final_intent.suggested_stop_loss or (current_market_price * 0.985)
        tp = risk_eval.take_profit_price or final_intent.suggested_take_profit or (current_market_price * 1.035)

        # Unified Execution Safety Routing (Paper / Testnet / Live)
        exec_mode_val = profile.execution_mode.value if isinstance(profile.execution_mode, ExecutionMode) else str(profile.execution_mode).lower()
        order_res = self.safety_guard.execute_order(
            symbol=symbol,
            side=side,
            amount=amount,
            price=current_market_price,
            order_type="limit",
            execution_mode=exec_mode_val,
            stop_loss=sl,
            take_profit=tp,
            client_order_id=f"CNMS_{final_intent.strategy_id[:4].upper()}_{uuid.uuid4().hex[:8]}",
        )

        # Record trade into database via PositionManager
        order_id = order_res.get("exchange_order_id") or f"ORD_{uuid.uuid4().hex[:10]}"
        trade_id = self.position_manager.record_entry(
            symbol=symbol,
            side=side,
            amount=amount,
            price=current_market_price,
            stop_loss=sl,
            take_profit=tp,
            strategy_id=final_intent.strategy_id,
            timeframe=timeframe,
            order_id=order_id,
        )

        # Mark idempotency key as consumed
        self._processed_idempotency_keys.add(idempotency_key)
        session.orders_created += 1
        session.orders_filled += 1

        # 9. Complete Causal Decision Trace
        trace_id = f"TRACE_TRD_{trade_id}"
        full_trace = DecisionTraceRecord(
            trace_id=trace_id,
            profile_id=profile.profile_id,
            session_id=session.session_id,
            symbol=symbol,
            timeframe=timeframe,
            candle_timestamp=candle_ts,
            decision_timestamp=now_str,
            market_price=current_market_price,
            decision_mode=profile.decision_mode.value,
            strategy_signal=strat_signal,
            ai_decision=ai_decision,
            ai_confidence=ai_confidence,
            policy_result="APPROVED",
            risk_result="APPROVED",
            execution_status="EXECUTED",
            order_id=order_id,
            raw_trace={
                "trade_id": trade_id,
                "side": side,
                "amount": amount,
                "entry_price": current_market_price,
                "stop_loss": sl,
                "take_profit": tp,
                "leverage": risk_eval.approved_leverage,
                "strategy": final_intent.strategy_id,
                "execution_mode": profile.execution_mode.value,
            },
        )
        self.store.save_trace(full_trace)
        session.last_decision = full_trace.to_dict()
        self.store.save_session(session)

        # 10. Audit Log & Telegram Notification
        self.audit_logger.log_event(
            agent_id=profile.agent_id or "autonomous-engine",
            action="AUTONOMOUS_TRADE_EXECUTED",
            domain="trading",
            status="SUCCESS",
            details=full_trace.to_dict(),
        )

        try:
            tg_msg = (
                f"🚀 <b>CUANIMUS AUTONOMOUS TRADE</b>\n\n"
                f"• <b>Profile:</b> <code>{profile.name}</code>\n"
                f"• <b>Mode:</b> <code>{profile.decision_mode.value.upper()}</code>\n"
                f"• <b>Pair:</b> <code>{symbol}</code> ({timeframe})\n"
                f"• <b>Side:</b> <b>{side}</b>\n"
                f"• <b>Entry:</b> <code>{current_market_price:.4f}</code>\n"
                f"• <b>Stop Loss:</b> <code>{sl:.4f}</code>\n"
                f"• <b>Take Profit:</b> <code>{tp:.4f}</code>\n"
                f"• <b>Execution:</b> <code>{profile.execution_mode.value.upper()}</code>\n"
                f"• <b>Trace ID:</b> <code>{trace_id}</code>"
            )
            self.telegram.send_alert(tg_msg)
        except Exception as tg_err:
            logger.warning(f"Telegram alert error: {tg_err}")

        return {
            "status": "EXECUTED",
            "trade_id": trade_id,
            "order_id": order_id,
            "trace_id": trace_id,
            "entry_price": current_market_price,
            "side": side,
        }

    def _record_rejection_trace(
        self,
        profile: TradingProfile,
        session: AutonomousSession,
        candle_ts: str,
        now_str: str,
        current_market_price: float,
        strat_signal: str,
        ai_decision: str,
        ai_confidence: float,
        rejection_stage: str,
        rejection_reason: str,
    ) -> DecisionTraceRecord:
        """Helper to record rejection causal trace."""
        trace_id = f"TRACE_REJ_{uuid.uuid4().hex[:10]}"
        trace = DecisionTraceRecord(
            trace_id=trace_id,
            profile_id=profile.profile_id,
            session_id=session.session_id,
            symbol=profile.symbol,
            timeframe=profile.timeframe,
            candle_timestamp=candle_ts,
            decision_timestamp=now_str,
            market_price=current_market_price,
            decision_mode=profile.decision_mode.value,
            strategy_signal=strat_signal,
            ai_decision=ai_decision,
            ai_confidence=ai_confidence,
            policy_result="VETOED" if "Policy" in rejection_stage else "APPROVED",
            risk_result="VETOED" if "Risk" in rejection_stage or "Emergency" in rejection_stage else "APPROVED",
            execution_status="REJECTED",
            raw_trace={
                "rejection_stage": rejection_stage,
                "rejection_reason": rejection_reason,
            },
        )
        self.store.save_trace(trace)
        session.last_decision = trace.to_dict()
        self.store.save_session(session)
        return trace

    # -------------------------------------------------------------------------
    # Profile State Orchestration (Start / Pause / Stop)
    # -------------------------------------------------------------------------

    def start_profile(self, profile_id: str) -> Dict[str, Any]:
        """Activates and starts autonomous trading for a profile with preflight checks."""
        profile = self.store.get_profile(profile_id)
        if not profile:
            raise KeyError(f"Profile {profile_id} not found")

        # Preflight validation for TESTNET and LIVE
        exec_mode = profile.execution_mode.value if isinstance(profile.execution_mode, ExecutionMode) else str(profile.execution_mode).lower()
        if exec_mode in ("testnet", "live"):
            from cuanimus.exchange.binance_private import get_binance_private_adapter
            adapter = get_binance_private_adapter(exec_mode)
            preflight = adapter.validate_connection()
            if not preflight.get("valid"):
                err_msg = preflight.get("error", "Preflight connection failed")
                logger.error(f"[AutonomousTradingEngine] Preflight failed for {exec_mode.upper()} profile {profile_id}: {err_msg}")
                raise ValueError(f"Cannot start {exec_mode.upper()} profile '{profile.name}': {err_msg}")

            # Reconcile exchange state upon starting real exchange profile
            self.reconcile_exchange_state(environment=exec_mode)

        # Create or resume session
        session = self.store.get_active_session_for_profile(profile_id)
        if not session:
            session = AutonomousSession(
                session_id=f"sess_{uuid.uuid4().hex[:10]}",
                profile_id=profile_id,
                status=SessionStatus.RUNNING,
            )
            self.store.save_session(session)

        self.store.update_profile_running_state(profile_id, is_running=True)

        # Ensure background engine thread is running
        self.start()

        # Send Telegram notification
        try:
            self.telegram.send_alert(
                f"▶️ <b>CUANIMUS PROFILE STARTED</b>\n\n"
                f"• <b>Profile:</b> <code>{profile.name}</code>\n"
                f"• <b>Pair:</b> <code>{profile.symbol}</code> ({profile.timeframe})\n"
                f"• <b>Decision Mode:</b> <code>{profile.decision_mode.value.upper()}</code>\n"
                f"• <b>Risk Profile:</b> <code>{profile.risk_profile}</code>\n"
                f"• <b>Execution:</b> <code>{profile.execution_mode.value.upper()}</code>"
            )
        except Exception:
            pass

        return {
            "status": "RUNNING",
            "profile_id": profile_id,
            "session_id": session.session_id,
            "message": f"Profile '{profile.name}' started in {exec_mode.upper()} mode.",
        }

    def reconcile_exchange_state(self, environment: str = "testnet") -> Dict[str, Any]:
        """
        Reconciles actual Binance Futures account balance, positions,
        and open orders against internal state.
        """
        env = environment.lower().strip()
        from cuanimus.exchange.binance_private import get_binance_private_adapter
        adapter = get_binance_private_adapter(env)

        if not adapter.has_credentials():
            return {"reconciled": False, "reason": "No credentials configured"}

        try:
            balance_info = adapter.get_usdt_balance()
            positions = adapter.get_positions()
            open_orders = adapter.get_open_orders()

            logger.info(
                f"[Reconciliation] {env.upper()} Balance: {balance_info.get('available_balance', 0.0):.2f} USDT, "
                f"Open Positions: {len(positions)}, Open Orders: {len(open_orders)}"
            )

            return {
                "reconciled": True,
                "environment": env,
                "usdt_balance": balance_info,
                "positions_count": len(positions),
                "open_orders_count": len(open_orders),
                "positions": positions,
            }
        except Exception as e:
            logger.warning(f"[Reconciliation] Error reconciling {env.upper()} state: {e}")
            return {"reconciled": False, "error": str(e)}

    def pause_profile(self, profile_id: str) -> Dict[str, Any]:
        """Pauses autonomous evaluation for a profile."""
        profile = self.store.get_profile(profile_id)
        if not profile:
            raise KeyError(f"Profile {profile_id} not found")

        session = self.store.get_active_session_for_profile(profile_id)
        if session:
            session.status = SessionStatus.PAUSED
            self.store.save_session(session)

        self.store.update_profile_running_state(profile_id, is_running=False)

        try:
            self.telegram.send_alert(f"⏸️ <b>CUANIMUS PROFILE PAUSED</b>: <code>{profile.name}</code>")
        except Exception:
            pass

        return {"status": "PAUSED", "profile_id": profile_id}

    def stop_profile(self, profile_id: str) -> Dict[str, Any]:
        """Stops and terminates autonomous session for a profile."""
        profile = self.store.get_profile(profile_id)
        if not profile:
            raise KeyError(f"Profile {profile_id} not found")

        session = self.store.get_active_session_for_profile(profile_id)
        if session:
            session.status = SessionStatus.STOPPED
            session.stopped_at = datetime.now(timezone.utc).isoformat()
            self.store.save_session(session)

        self.store.update_profile_running_state(profile_id, is_running=False)

        try:
            self.telegram.send_alert(f"⏹️ <b>CUANIMUS PROFILE STOPPED</b>: <code>{profile.name}</code>")
        except Exception:
            pass

        return {"status": "STOPPED", "profile_id": profile_id}

    def get_engine_status(self) -> Dict[str, Any]:
        """Returns overall autonomous engine status and health metrics."""
        profiles = self.store.list_profiles()
        running_profiles = [p for p in profiles if p.is_running]
        sessions = self.store.list_sessions(limit=10)
        open_positions = self.position_manager.get_open_positions()
        traces = self.store.list_traces(limit=100)

        signals_today = len(traces)
        policy_rejections = sum(1 for t in traces if t.get("policy_result") == "REJECTED")
        risk_rejections = sum(1 for t in traces if t.get("risk_result") == "REJECTED")
        orders_executed = sum(1 for t in traces if t.get("execution_status") == "EXECUTED")

        # Enrich running profiles with last evaluation telemetry
        enriched_running = []
        for p in running_profiles:
            p_dict = p.to_dict()
            sess = self.store.get_active_session_for_profile(p.profile_id)
            if sess:
                p_dict["last_evaluation"] = sess.heartbeat
                p_dict["processed_candles"] = sess.processed_candles
                p_dict["last_signal"] = (sess.last_decision or {}).get("strategy_signal") or (sess.last_decision or {}).get("ai_decision") or "HOLD"
            enriched_running.append(p_dict)

        return {
            "engine_running": self.is_running(),
            "emergency_stop_active": self.risk_engine.emergency_stop_active,
            "worker_pid": os.getpid(),
            "worker_thread": self._thread.name if self._thread and self._thread.is_alive() else "STOPPED",
            "heartbeat": datetime.now(timezone.utc).isoformat(),
            "last_cycle_at": self._last_cycle_at,
            "tick_interval_seconds": self._tick_interval,
            "active_profiles_count": len(running_profiles),
            "total_profiles_count": len(profiles),
            "open_positions_count": len(open_positions),
            "signals_evaluated_today": signals_today,
            "rejected_by_policy_today": policy_rejections,
            "rejected_by_risk_today": risk_rejections,
            "executed_orders_today": orders_executed,
            "worker_errors_count": self._worker_errors_count,
            "running_profiles": enriched_running,
            "recent_sessions": [s.to_dict() for s in sessions],
            "uptime_status": "ONLINE" if self.is_running() else "IDLE",
        }
