"""
CUANIMUS Order Timeout & Stale Order Manager.
"""
import logging
from typing import List, Tuple
from datetime import datetime

from cuanimus.common.types import Order, OrderState
from cuanimus.execution.state_machine import OrderStateMachine

logger = logging.getLogger(__name__)

class OrderTimeoutManager:
    def __init__(self, default_timeout_minutes: float = 10.0):
        self.default_timeout_minutes = default_timeout_minutes

    def sweep_expired_orders(
        self,
        active_orders: List[Order],
        current_time: datetime,
    ) -> List[Tuple[Order, str]]:
        expired_actions = []

        for order in active_orders:
            if order.state not in (OrderState.SUBMITTED, OrderState.PARTIALLY_FILLED):
                continue

            order_age = (current_time - order.created_at).total_seconds() / 60.0

            if order_age >= self.default_timeout_minutes:
                logger.warning(
                    f"Order {order.client_order_id} ({order.symbol}) reached timeout "
                    f"({order_age:.1f}m >= {self.default_timeout_minutes}m). Cancelling."
                )
                try:
                    OrderStateMachine.transition(
                        order=order,
                        new_state=OrderState.CANCELLING,
                        reason=f"UNFILLED_TIMEOUT_{order_age:.1f}M",
                        now=current_time,
                    )
                    expired_actions.append((order, "CANCEL_DISPATCHED"))
                except Exception as e:
                    logger.error(f"Failed to cancel expired order {order.client_order_id}: {str(e)}")

        return expired_actions

