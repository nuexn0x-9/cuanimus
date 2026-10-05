"""
Integration & Exchange Adapter Tests for CUANIMUS.
"""
import unittest
from typing import Dict, Any

from cuanimus.common.types import Order, OrderSide, OrderType, OrderState
from cuanimus.execution.state_machine import OrderStateMachine

class MockExchangeAdapter:
    def __init__(self, initial_balance: float = 1000.0):
        self.balance = initial_balance
        self.orders: Dict[str, Dict[str, Any]] = {}

    def create_order(
        self,
        symbol: str,
        order_type: str,
        side: str,
        amount: float,
        price: float,
        client_order_id: str,
    ) -> Dict[str, Any]:
        if client_order_id in self.orders:
            return self.orders[client_order_id]

        order_record = {
            "id": f"EXCH_{len(self.orders) + 1000}",
            "client_order_id": client_order_id,
            "symbol": symbol,
            "type": order_type,
            "side": side,
            "amount": amount,
            "price": price,
            "status": "open",
            "filled": 0.0,
            "remaining": amount,
        }
        self.orders[client_order_id] = order_record
        return order_record

    def cancel_order(self, client_order_id: str) -> Dict[str, Any]:
        if client_order_id not in self.orders:
            raise ValueError(f"Order {client_order_id} not found")
        order = self.orders[client_order_id]
        order["status"] = "canceled"
        return order

    def simulate_fill(self, client_order_id: str, fill_qty: float) -> Dict[str, Any]:
        order = self.orders[client_order_id]
        order["filled"] += fill_qty
        order["remaining"] = max(0.0, order["amount"] - order["filled"])
        if order["remaining"] == 0:
            order["status"] = "closed"
        return order

    def fetch_balance(self) -> Dict[str, float]:
        return {"free": self.balance, "total": self.balance}

class TestExchangeAdapter(unittest.TestCase):
    def setUp(self):
        self.adapter = MockExchangeAdapter(initial_balance=500.0)

    def test_order_creation_and_idempotency(self):
        res1 = self.adapter.create_order(
            symbol="ADA/USDT:USDT",
            order_type="limit",
            side="buy",
            amount=50.0,
            price=0.5000,
            client_order_id="CNMS_TEST_DUP_01",
        )
        self.assertEqual(res1["status"], "open")
        self.assertTrue(res1["id"].startswith("EXCH_"))

        res2 = self.adapter.create_order(
            symbol="ADA/USDT:USDT",
            order_type="limit",
            side="buy",
            amount=50.0,
            price=0.5000,
            client_order_id="CNMS_TEST_DUP_01",
        )
        self.assertEqual(res1["id"], res2["id"])

    def test_order_cancellation(self):
        self.adapter.create_order(
            symbol="ETH/USDT:USDT",
            order_type="limit",
            side="buy",
            amount=0.1,
            price=2700.0,
            client_order_id="CNMS_CANCEL_01",
        )
        res = self.adapter.cancel_order("CNMS_CANCEL_01")
        self.assertEqual(res["status"], "canceled")

    def test_exchange_fill_updates_local_order(self):
        order = Order(
            client_order_id="CNMS_SYNC_01",
            symbol="XRP/USDT:USDT",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            amount=100.0,
            price=1.0000,
            state=OrderState.SUBMITTED,
        )

        self.adapter.create_order(
            symbol="XRP/USDT:USDT",
            order_type="limit",
            side="buy",
            amount=100.0,
            price=1.0000,
            client_order_id="CNMS_SYNC_01",
        )

        fill_res = self.adapter.simulate_fill("CNMS_SYNC_01", 100.0)
        self.assertEqual(fill_res["status"], "closed")

        OrderStateMachine.apply_fill(order, filled_qty=100.0, fill_price=1.0000, fee_cost=0.05)
        self.assertEqual(order.state, OrderState.FILLED)
        self.assertEqual(order.remaining, 0.0)

if __name__ == "__main__":
    unittest.main()

