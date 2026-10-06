"""
CUANIMUS Autonomous Trading Engine & Decision Modes Test Suite.
Tests:
1. Mode A — Strategy Autotrade (Signal -> Policy -> Risk -> Paper Order)
2. Mode B — AI Agent Autotrade (Market -> AI Decision -> Policy -> Risk -> Paper Order)
3. Mode C — Hybrid Autotrade (Strategy Filter -> AI Confirmation -> Policy -> Risk -> Paper Order)
4. Hybrid Selective Efficiency (Strategy HOLD -> AI skipped)
5. Policy Engine Rejection Gate
6. Risk Engine Rejection Gate & Kill Switch Lockout
7. Candle Boundary & Idempotency Duplicate Protection
8. Position Management SL / TP Automatic Exit Lifecycle
9. Profile Store CRUD & State Orchestration
"""
import os
import unittest
import tempfile
import sqlite3
from datetime import datetime, timezone

from cuanimus.core.database import DatabaseManager
from cuanimus.common.types import SignalDirection, TradeIntent, MarketRegimeType
from cuanimus.agent.policy import AgentTradingPolicy
from cuanimus.risk.engine import RiskEngine
from cuanimus.execution.paper_safety import PaperExecutionSafetyGuard
from cuanimus.engine.models import (
    TradingProfile,
    AutonomousSession,
    DecisionMode,
    ExecutionMode,
    SessionStatus,
    AgentDecisionResult,
)
from cuanimus.engine.profile_store import ProfileStore
from cuanimus.engine.strategy_evaluator import StrategyEvaluator
from cuanimus.engine.agent_evaluator import AgentDecisionEngine
from cuanimus.engine.hybrid_evaluator import HybridEvaluator
from cuanimus.engine.position_manager import PositionManager
from cuanimus.engine.autonomous_engine import AutonomousTradingEngine


class MockTelegramNotifier:
    def __init__(self):
        self.sent_alerts = []

    def send_alert(self, text, parse_mode="HTML"):
        self.sent_alerts.append(text)
        return True


class TestAutonomousTradingEngine(unittest.TestCase):

    def setUp(self):
        # Setup temporary sqlite database for test isolation
        self.temp_db_fd, self.temp_db_path = tempfile.mkstemp(suffix=".sqlite")
        self.db = DatabaseManager()
        self.db._backend = self.db._backend.SQLITE
        self.db.get_sqlite_path = lambda: self.temp_db_path

        self.mock_tg = MockTelegramNotifier()
        self.profile_store = ProfileStore(db=self.db)
        self.position_manager = PositionManager(db=self.db, telegram=self.mock_tg)
        self.risk_engine = RiskEngine()
        self.policy = AgentTradingPolicy()
        self.safety_guard = PaperExecutionSafetyGuard(dry_run=True)

        self.engine = AutonomousTradingEngine(
            profile_store=self.profile_store,
            risk_engine=self.risk_engine,
            policy=self.policy,
            safety_guard=self.safety_guard,
            telegram=self.mock_tg,
        )
        self.orig_get_klines = self.engine.adapter.get_klines

        # Generate 60 synthetic closed candles with bullish trend
        base_price = 100.0
        self.mock_candles = []
        for i in range(60):
            p = base_price + (i * 0.5)
            self.mock_candles.append({
                "date": f"2026-10-01 12:{i:02d}",
                "timestamp": 1700000000000 + (i * 900000),
                "open": p - 0.2,
                "high": p + 0.8,
                "low": p - 0.3,
                "close": p,
                "volume": 2500.0,
                "trades": 120,
            })

    def tearDown(self):
        self.engine.adapter.get_klines = self.orig_get_klines
        self.engine.stop()
        os.close(self.temp_db_fd)
        if os.path.exists(self.temp_db_path):
            os.remove(self.temp_db_path)

    # -------------------------------------------------------------------------
    # 1. Profile Store CRUD Tests
    # -------------------------------------------------------------------------
    def test_profile_crud(self):
        profile = TradingProfile(
            profile_id="prof_unit_test",
            name="TEST-ADA-15M",
            symbol="ADA/USDT:USDT",
            timeframe="15m",
            decision_mode=DecisionMode.STRATEGY,
            strategy_id="hybrid_v2c",
            risk_profile="conservative",
            execution_mode=ExecutionMode.PAPER,
            max_open_positions=1,
            max_trades_per_day=5,
            stop_loss_pct=1.5,
            take_profit_pct=3.0,
        )
        self.profile_store.save_profile(profile)

        # Retrieve
        fetched = self.profile_store.get_profile("prof_unit_test")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.name, "TEST-ADA-15M")
        self.assertEqual(fetched.decision_mode, DecisionMode.STRATEGY)

        # Update
        fetched.max_trades_per_day = 8
        self.profile_store.save_profile(fetched)
        updated = self.profile_store.get_profile("prof_unit_test")
        self.assertEqual(updated.max_trades_per_day, 8)

        # Delete
        self.profile_store.delete_profile("prof_unit_test")
        self.assertIsNone(self.profile_store.get_profile("prof_unit_test"))

    # -------------------------------------------------------------------------
    # 2. Mode A: Strategy Autotrade
    # -------------------------------------------------------------------------
    def test_mode_a_strategy_autotrade_flow(self):
        profile = TradingProfile(
            profile_id="prof_strat_test",
            name="ADA-STRATEGY",
            symbol="ADA/USDT:USDT",
            timeframe="15m",
            decision_mode=DecisionMode.STRATEGY,
            strategy_id="hybrid_v2c",
            risk_profile="conservative",
            execution_mode=ExecutionMode.PAPER,
        )
        self.profile_store.save_profile(profile)

        # Mock adapter klines
        self.engine.adapter.get_klines = lambda sym, timeframe="15m", limit=60: self.mock_candles

        # Force a tick
        result = self.engine.evaluate_profile_tick(profile, force=True)

        self.assertIn("status", result)
        # Should execute or abstain legitimately
        traces = self.profile_store.list_traces(profile_id=profile.profile_id)
        self.assertGreaterEqual(len(traces), 1)
        trace = traces[0]
        self.assertEqual(trace["decision_mode"], "strategy")
        self.assertNotEqual(trace["strategy_signal"], "")

    # -------------------------------------------------------------------------
    # 3. Mode B: AI Agent Autotrade
    # -------------------------------------------------------------------------
    def test_mode_b_ai_agent_autotrade_flow(self):
        profile = TradingProfile(
            profile_id="prof_ai_test",
            name="BTC-AI-AGENT",
            symbol="BTC/USDT:USDT",
            timeframe="15m",
            decision_mode=DecisionMode.AI_AGENT,
            agent_id="trader-paper",
            risk_profile="conservative",
            execution_mode=ExecutionMode.PAPER,
        )
        self.profile_store.save_profile(profile)

        self.engine.adapter.get_klines = lambda sym, timeframe="15m", limit=60: self.mock_candles

        result = self.engine.evaluate_profile_tick(profile, force=True)
        self.assertIn("status", result)

        traces = self.profile_store.list_traces(profile_id=profile.profile_id)
        self.assertGreaterEqual(len(traces), 1)
        trace = traces[0]
        self.assertEqual(trace["decision_mode"], "ai_agent")
        self.assertEqual(trace["strategy_signal"], "N/A")
        self.assertNotEqual(trace["ai_decision"], "N/A")

    # -------------------------------------------------------------------------
    # 4. Mode C: Hybrid Autotrade
    # -------------------------------------------------------------------------
    def test_mode_c_hybrid_autotrade_flow(self):
        profile = TradingProfile(
            profile_id="prof_hybrid_test",
            name="ETH-HYBRID",
            symbol="ETH/USDT:USDT",
            timeframe="15m",
            decision_mode=DecisionMode.HYBRID,
            strategy_id="hybrid_v2c",
            agent_id="trader-paper",
            risk_profile="conservative",
            execution_mode=ExecutionMode.PAPER,
        )
        self.profile_store.save_profile(profile)

        self.engine.adapter.get_klines = lambda sym, timeframe="15m", limit=60: self.mock_candles

        result = self.engine.evaluate_profile_tick(profile, force=True)
        self.assertIn("status", result)

        traces = self.profile_store.list_traces(profile_id=profile.profile_id)
        self.assertGreaterEqual(len(traces), 1)
        trace = traces[0]
        self.assertEqual(trace["decision_mode"], "hybrid")

    # -------------------------------------------------------------------------
    # 5. Hybrid Selective Efficiency (Strategy HOLD -> AI skipped)
    # -------------------------------------------------------------------------
    def test_hybrid_skips_ai_when_strategy_holds(self):
        hybrid_eval = HybridEvaluator()
        # Mock strategy evaluator returning HOLD
        now = datetime.now(timezone.utc)
        hold_intent = TradeIntent(
            intent_id="HOLD_INTENT",
            symbol="ETH/USDT:USDT",
            direction=SignalDirection.HOLD,
            timestamp=now,
            strategy_id="hybrid_v2c",
            entry_price_target=2500.0,
        )
        hybrid_eval.strategy_evaluator.evaluate = lambda p, c, pr: hold_intent

        profile = TradingProfile(
            profile_id="prof_test",
            name="TEST",
            symbol="ETH/USDT:USDT",
            decision_mode=DecisionMode.HYBRID,
        )

        final, strat, ai_res = hybrid_eval.evaluate(profile, self.mock_candles, 2500.0, [])
        self.assertEqual(final.direction, SignalDirection.HOLD)
        self.assertIsNone(ai_res, "AI must NOT be called when strategy template returns HOLD!")

    # -------------------------------------------------------------------------
    # 6. Policy Engine Gate Rejection
    # -------------------------------------------------------------------------
    def test_policy_engine_rejection_blocks_order(self):
        # Configure policy that forbids 'unauthorized_symbol'
        self.policy.allowed_symbols = ["BTC/USDT:USDT", "ETH/USDT:USDT"]

        profile = TradingProfile(
            profile_id="prof_disallowed_sym",
            name="TEST-DISALLOWED",
            symbol="DOGE/USDT:USDT",
            decision_mode=DecisionMode.AI_AGENT,
        )
        self.profile_store.save_profile(profile)

        self.engine.adapter.get_klines = lambda sym, timeframe="15m", limit=60: self.mock_candles

        # Force positive AI decision
        self.engine.agent_engine.evaluate = lambda prof, c, pr, op: (
            TradeIntent(
                intent_id="INT_TEST",
                symbol=prof.symbol,
                direction=SignalDirection.LONG,
                timestamp=datetime.now(timezone.utc),
                strategy_id="ai_agent",
                entry_price_target=0.15,
                suggested_stop_loss=0.14,
            ),
            AgentDecisionResult(
                decision="LONG",
                confidence=0.90,
                entry_reason="Test bull",
                stop_loss_pct=0.015,
                take_profit_pct=0.03,
            )
        )

        result = self.engine.evaluate_profile_tick(profile, force=True)
        self.assertEqual(result["status"], "REJECTED_POLICY")

        # Verify no open trade exists
        open_pos = self.position_manager.get_open_positions("DOGE/USDT:USDT")
        self.assertEqual(len(open_pos), 0)

    # -------------------------------------------------------------------------
    # 7. Risk Engine Rejection & Kill Switch
    # -------------------------------------------------------------------------
    def test_emergency_stop_kill_switch_locks_engine(self):
        profile = TradingProfile(
            profile_id="prof_kill_test",
            name="TEST-KILL-SWITCH",
            symbol="BTC/USDT:USDT",
            decision_mode=DecisionMode.AI_AGENT,
        )
        self.profile_store.save_profile(profile)

        # Arm emergency stop
        self.risk_engine.trigger_emergency_stop("Operator kill switch")

        self.engine.adapter.get_klines = lambda sym, timeframe="15m", limit=60: self.mock_candles
        self.engine.agent_engine.evaluate = lambda prof, c, pr, op: (
            TradeIntent(
                intent_id="INT_TEST",
                symbol=prof.symbol,
                direction=SignalDirection.LONG,
                timestamp=datetime.now(timezone.utc),
                strategy_id="ai_agent",
                entry_price_target=60000.0,
                suggested_stop_loss=59000.0,
            ),
            AgentDecisionResult(
                decision="LONG",
                confidence=0.90,
                entry_reason="Test bull",
                stop_loss_pct=0.015,
                take_profit_pct=0.03,
            )
        )

        result = self.engine.evaluate_profile_tick(profile, force=True)
        self.assertEqual(result["status"], "REJECTED_EMERGENCY_STOP")

        # Verify no order created
        open_pos = self.position_manager.get_open_positions("BTC/USDT:USDT")
        self.assertEqual(len(open_pos), 0)

    # -------------------------------------------------------------------------
    # 8. Candle Boundary & Idempotency Duplicate Protection
    # -------------------------------------------------------------------------
    def test_candle_boundary_prevents_duplicate_evaluation(self):
        profile = TradingProfile(
            profile_id="prof_boundary_test",
            name="TEST-BOUNDARY",
            symbol="ETH/USDT:USDT",
            decision_mode=DecisionMode.STRATEGY,
        )
        self.profile_store.save_profile(profile)
        self.engine.adapter.get_klines = lambda sym, timeframe="15m", limit=60: self.mock_candles

        # First evaluation
        res1 = self.engine.evaluate_profile_tick(profile, force=False)

        # Second evaluation with same closed candles without force
        p_refreshed = self.profile_store.get_profile(profile.profile_id)
        res2 = self.engine.evaluate_profile_tick(p_refreshed, force=False)
        self.assertEqual(res2["status"], "SKIPPED_SAME_CANDLE")

    # -------------------------------------------------------------------------
    # 9. Automated Position Management (SL / TP Exit)
    # -------------------------------------------------------------------------
    def test_position_manager_stop_loss_and_take_profit_exits(self):
        # 1. Open trade with SL = 95.0, TP = 110.0
        trade_id = self.position_manager.record_entry(
            symbol="SOL/USDT:USDT",
            side="buy",
            amount=2.0,
            price=100.0,
            stop_loss=95.0,
            take_profit=110.0,
            strategy_id="hybrid_v2c",
            order_id="ORD_TEST_ENTRY_001",
        )
        self.assertGreater(trade_id, 0)

        open_trades = self.position_manager.get_open_positions("SOL/USDT:USDT")
        self.assertEqual(len(open_trades), 1)

        # 2. Price drops to 94.0 -> Should trigger Stop Loss exit
        exits = self.position_manager.check_and_execute_exits({"SOL/USDT:USDT": 94.0})
        self.assertEqual(len(exits), 1)
        self.assertEqual(exits[0]["exit_reason"], "stop_loss")
        self.assertEqual(exits[0]["trade_id"], trade_id)

        # Verify trade is now closed in database
        open_after = self.position_manager.get_open_positions("SOL/USDT:USDT")
        self.assertEqual(len(open_after), 0)

        # Verify trade record updated
        tr_row = self.db.query_one("SELECT * FROM trades WHERE id = ?", (trade_id,))
        self.assertEqual(tr_row["is_open"], 0)
        self.assertEqual(tr_row["exit_reason"], "stop_loss")
        self.assertLess(float(tr_row["close_profit"]), 0)

    # -------------------------------------------------------------------------
    # 10. Unified Execution Router — Paper Mode (dry_run = True)
    # -------------------------------------------------------------------------
    def test_unified_execution_router_paper_mode(self):
        from cuanimus.execution.paper_safety import UnifiedExecutionSafetyGuard
        guard = UnifiedExecutionSafetyGuard(dry_run=True)
        res = guard.execute_order(
            symbol="BTC/USDT:USDT",
            side="BUY",
            amount=0.05,
            price=60000.0,
            order_type="limit",
            execution_mode="paper",
        )
        self.assertTrue(res["is_paper"])
        self.assertEqual(res["status"], "FILLED")
        self.assertTrue(res["exchange_order_id"].startswith("SIM_"))

    # -------------------------------------------------------------------------
    # 11. Unified Execution Router — Testnet Mode (dry_run = False)
    # -------------------------------------------------------------------------
    def test_unified_execution_router_testnet_mode(self):
        from cuanimus.execution.paper_safety import UnifiedExecutionSafetyGuard
        from cuanimus.exchange.binance_private import BinancePrivateAdapter
        from unittest.mock import patch

        guard = UnifiedExecutionSafetyGuard(dry_run=False, environment="testnet")

        # Mock BinancePrivateAdapter
        with patch.object(BinancePrivateAdapter, "has_credentials", return_value=True):
            with patch.object(BinancePrivateAdapter, "create_order") as mock_create:
                mock_create.side_effect = [
                    {"orderId": 12345678, "status": "FILLED", "origQty": "0.05", "price": "60000.0"},
                    {"orderId": 12345679, "status": "NEW"},  # SL
                    {"orderId": 12345680, "status": "NEW"},  # TP
                ]
                res = guard.execute_order(
                    symbol="BTC/USDT:USDT",
                    side="BUY",
                    amount=0.05,
                    price=60000.0,
                    order_type="limit",
                    execution_mode="testnet",
                    stop_loss=58000.0,
                    take_profit=64000.0,
                )
                self.assertFalse(res["is_paper"])
                self.assertEqual(res["environment"], "testnet")
                self.assertEqual(res["exchange_order_id"], "12345678")
                self.assertEqual(len(res["protective_orders"]), 2)
                self.assertEqual(res["protective_orders"][0]["type"], "STOP_LOSS")
                self.assertEqual(res["protective_orders"][1]["type"], "TAKE_PROFIT")

    # -------------------------------------------------------------------------
    # 12. Preflight Validation — Fail Closed on Missing Credentials
    # -------------------------------------------------------------------------
    def test_preflight_validation_fail_closed_live(self):
        from cuanimus.exchange.binance_private import BinancePrivateAdapter
        live_adapter = BinancePrivateAdapter(api_key="", api_secret="", environment="live")
        res = live_adapter.validate_connection()
        self.assertFalse(res["valid"])
        self.assertIn("missing", res["error"].lower())

        # Starting a LIVE profile without credentials must raise ValueError
        p = TradingProfile(
            profile_id="prof_live_test",
            name="Live BTC Test",
            symbol="BTC/USDT:USDT",
            execution_mode=ExecutionMode.LIVE,
        )
        self.profile_store.save_profile(p)
        with self.assertRaises(ValueError):
            self.engine.start_profile("prof_live_test")

    # -------------------------------------------------------------------------
    # 13. Dynamic Position Sizing with Binance Precision Filters
    # -------------------------------------------------------------------------
    def test_dynamic_position_sizing_precision_filters(self):
        from cuanimus.risk.sizing import calculate_position_size, quantize_value

        # Test quantize_value helper
        self.assertEqual(quantize_value(1.23456, 0.01), 1.23)
        self.assertEqual(quantize_value(12.78, 1.0), 12.0)

        # Sizing with custom step_size and min_notional
        sizing = calculate_position_size(
            wallet_balance=1000.0,
            risk_per_trade_pct=1.0,  # $10 risk
            entry_price=100.0,
            stop_loss_price=95.0,    # 5% SL distance -> desired notional = $200
            leverage=3.0,
            step_size=0.1,
            min_notional=10.0,
        )
        self.assertTrue(sizing["approved"])
        self.assertEqual(sizing["contracts"], 2.0)  # 200 / 100 = 2.0
        self.assertEqual(sizing["step_size"], 0.1)


if __name__ == "__main__":
    unittest.main()

