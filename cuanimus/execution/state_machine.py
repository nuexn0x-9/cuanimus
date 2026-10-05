"""
CUANIMUS Order State Machine.
"""
import uuid
import time
import logging
from datetime import datetime
from typing import Set, Dict, Optional

from cuanimus.common.types import Order, OrderState, OrderSide, OrderType
from cuanimus.common.exceptions import InvalidOrderStateTransition

logger = logging.getLogger(__name__)

PERMITTED_TRANSITIONS: Dict[OrderState, Set[OrderState]] = {
    OrderState.CREATED: {OrderState.SUBMITTED, OrderState.FAILED},
    OrderState.SUBMITTED: {
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.CANCELLING,
        OrderState.REJECTED,
        OrderState.EXPIRED,
        OrderState.FAILED,
    },
    OrderState.PARTIALLY_FILLED: {
        OrderState.PARTIALLY_FILLED,
        OrderState.FILLED,
        OrderState.CANCELLING,
        OrderState.EXPIRED,
        OrderState.FAILED,
    },
    OrderState.CANCELLING: {OrderState.CANCELLED, OrderState.FILLED},
    OrderState.FILLED: set(),
    OrderState.CANCELLED: set(),
    OrderState.REJECTED: set(),
    OrderState.EXPIRED: set(),
    OrderState.FAILED: set(),
}

def generate_client_order_id(strategy_id: str, symbol: str) -> str:
    clean_sym = symbol.replace("/", "").replace(":", "")[:6]
    strat_pref = strategy_id.replace("_", "")[:4].upper()
    epoch_ms = int(time.time() * 1000)
    uid = uuid.uuid4().hex[:6]
    return f"CNMS_{strat_pref}_{clean_sym}_{epoch_ms}_{uid}"

class OrderStateMachine:
    @staticmethod
    def transition(
        order: Order,
        new_state: OrderState,
        reason: Optional[str] = None,
        now: Optional[datetime] = None,
    ) -> Order:
        current_state = order.state
        allowed = PERMITTED_TRANSITIONS.get(current_state, set())

        if new_state not in allowed:
            raise InvalidOrderStateTransition(current_state.value, new_state.value)

        order.state = new_state
        order.updated_at = now or datetime.utcnow()
        if reason:
            order.cancel_reason = reason

        logger.info(f"[{order.symbol}] Order {order.client_order_id}: {current_state.value} -> {new_state.value} ({reason or 'OK'})")
        return order

    @staticmethod
    def apply_fill(
        order: Order,
        filled_qty: float,
        fill_price: float,
        fee_cost: float = 0.0,
        now: Optional[datetime] = None,
    ) -> Order:
        assert filled_qty > 0, "Fill quantity must be positive"
        assert fill_price > 0, "Fill price must be positive"

        previous_filled = order.filled
        new_filled = previous_filled + filled_qty

        if previous_filled == 0:
            order.average_fill_price = fill_price
        else:
            total_cost = (previous_filled * (order.average_fill_price or fill_price)) + (filled_qty * fill_price)
            order.average_fill_price = round(total_cost / new_filled, 4)

        order.filled = round(new_filled, 6)
        order.remaining = max(0.0, round(order.amount - order.filled, 6))
        order.fee_cost += fee_cost
        order.updated_at = now or datetime.utcnow()

        if order.remaining <= 1e-6:
            order.remaining = 0.0
            OrderStateMachine.transition(order, OrderState.FILLED, reason="COMPLETE_FILL", now=now)
        else:
            OrderStateMachine.transition(order, OrderState.PARTIALLY_FILLED, reason="PARTIAL_SLICE_FILL", now=now)

        return order

