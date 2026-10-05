"""
CUANIMUS Zombie Order Reconciliation Script.
Safely reconciles hanging unfilled limit orders without destructive row deletions.
"""
import sqlite3
import os
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DB_PATH = "user_data/tradesv3.dryrun.sqlite"

def reconcile_zombie_orders(db_path: str = DB_PATH):
    if not os.path.exists(db_path):
        logger.error(f"Database not found: {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Find open trades with zero filled amount and hanging orders
    cursor.execute("""
        SELECT t.id, t.pair, t.open_date, o.id, o.order_id, o.amount, o.filled, o.status
        FROM trades t
        JOIN orders o ON o.ft_trade_id = t.id
        WHERE t.is_open = 1 AND t.amount = 0.0 AND o.ft_is_open = 1 AND o.filled = 0.0
    """)
    zombies = cursor.fetchall()
    logger.info(f"Found {len(zombies)} hanging unfilled zombie trade(s)")

    for t_id, pair, open_date, o_id, order_id, amount, filled, status in zombies:
        logger.info(f"Reconciling Trade #{t_id} ({pair}) | Order #{o_id} ({order_id})")

        # 1. Non-destructively cancel the order
        reconcile_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
            UPDATE orders
            SET ft_is_open = 0,
                status = 'canceled',
                ft_cancel_reason = 'unfilled_timeout_reconciled',
                order_update_date = ?
            WHERE id = ?
        """, (reconcile_time, o_id))

        # 2. Close the zero-amount trade record
        cursor.execute("""
            UPDATE trades
            SET is_open = 0,
                close_date = ?,
                exit_reason = 'cancelled',
                exit_order_status = 'canceled',
                realized_profit = 0.0,
                close_profit = 0.0,
                close_profit_abs = 0.0
            WHERE id = ?
        """, (reconcile_time, t_id))

        logger.info(f"Successfully reconciled Trade #{t_id} and Order #{o_id}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    reconcile_zombie_orders()
