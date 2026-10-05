"""
Unit Tests for CUANIMUS Order State Machine & Timeout Manager.
"""
import unittest
from datetime import datetime, timedelta

from cuanimus.common.types import Order, OrderState, OrderSide, OrderType
from cuanimus.common.exceptions import InvalidOrderStateTransition
from cuanimus.execution.state_machine import OrderStateMachine, generate_client_order_id
from cuanimus.execution.timeout_manager import OrderTimeoutManager

class TestOrderStateMachine(unittest.TestCase):
    def setUp(self):
        self.order = Order(
            client_order_id="CNMS_TEST_ADA_001",
            symbol="ADA/USDT:USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            amount=100.0,
            price=0.5000,
            state=OrderState.CREATED,
        )

    def test_valid_lifecycle_progression(self):
        OrderStateMachine.transition(self.order, OrderState.SUBMITTED)
        self.assertEqual(self.order.state, OrderState.SUBMITTED)

        OrderStateMachine.apply_fill(self.order, filled_qty=40.0, fill_price=0.5000, fee_cost=0.01)
        self.assertEqual(self.order.state, OrderState.PARTIALLY_FILLED)
        self.assertEqual(self.order.filled, 40.0)
        self.assertEqual(self.order.remaining, 60.0)

        OrderStateMachine.apply_fill(self.order, filled_qty=60.0, fill_price=0.5002, fee_cost=0.015)
        self.assertEqual(self.order.state, OrderState.FILLED)
        self.assertEqual(self.order.filled, 100.0)
        self.assertEqual(self.order.remaining, 0.0)
        self.assertAlmostEqual(self.order.fee_cost, 0.025, places=4)

    def test_illegal_state_transition_raises_exception(self):
        with self.assertRaises(InvalidOrderStateTransition):
            OrderStateMachine.transition(self.order, OrderState.FILLED)

    def test_cancellation_race_condition(self):
        OrderStateMachine.transition(self.order, OrderState.SUBMITTED)
        OrderStateMachine.transition(self.order, OrderState.CANCELLING, reason="TIMEOUT")
        OrderStateMachine.transition(self.order, OrderState.FILLED, reason="EXCHANGE_FILLED_BEFORE_CANCEL")
        self.assertEqual(self.order.state, OrderState.FILLED)

    def test_timeout_manager_sweeps_hanging_orders(self):
        now = datetime.utcnow()
        old_time = now - timedelta(minutes=15)

        hanging_order = Order(
            client_order_id="CNMS_ZOMBIE_XRP_529",
            symbol="XRP/USDT:USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            amount=47.2,
            price=1.0585,
            state=OrderState.SUBMITTED,
            created_at=old_time,
        )

        fresh_order = Order(
            client_order_id="CNMS_FRESH_ETH_001",
            symbol="ETH/USDT:USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            amount=0.5,
            price=2700.0,
            state=OrderState.SUBMITTED,
            created_at=now - timedelta(minutes=2),
        )

        manager = OrderTimeoutManager(default_timeout_minutes=10.0)
        actions = manager.sweep_expired_orders([hanging_order, fresh_order], current_time=now)

        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0][0].client_order_id, "CNMS_ZOMBIE_XRP_529")
        self.assertEqual(hanging_order.state, OrderState.CANCELLING)
        self.assertEqual(fresh_order.state, OrderState.SUBMITTED)

    def test_idempotent_client_order_id_generation(self):
        cid = generate_client_order_id("SNIPER_V1", "XRP/USDT:USDT")
        self.assertTrue(cid.startswith("CNMS_SNIP_XRPUSD"))
        self.assertGreater(len(cid), 20)

if __name__ == "__main__":
    unittest.main()

