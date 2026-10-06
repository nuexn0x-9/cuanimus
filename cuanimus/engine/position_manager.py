"""
CUANIMUS Autonomous Position & Order Lifecycle Manager.
Monitors active paper/testnet positions, enforces Stop Loss & Take Profit exits,
prevents duplicate entries, and maintains trade history in SQLite/PostgreSQL.
"""
import uuid
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from cuanimus.core.database import DatabaseManager
from cuanimus.api.telegram import TelegramNotifier

logger = logging.getLogger(__name__)


class PositionManager:
    """Manages open position lifecycle, SL/TP monitoring, and trade history recording."""

    def __init__(self, db: Optional[DatabaseManager] = None, telegram: Optional[TelegramNotifier] = None):
        self.db = db or DatabaseManager.get_instance()
        self.telegram = telegram or TelegramNotifier()
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Ensures trades and orders tables exist."""
        sql_trades = """
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pair VARCHAR(32) NOT NULL,
            is_open INTEGER NOT NULL DEFAULT 0,
            fee_open REAL DEFAULT 0,
            fee_close REAL DEFAULT 0,
            open_rate REAL NOT NULL,
            close_rate REAL,
            amount REAL NOT NULL,
            stake_amount REAL NOT NULL,
            open_date VARCHAR(64) NOT NULL,
            close_date VARCHAR(64),
            open_order_id VARCHAR(64),
            stop_loss REAL,
            initial_stop_loss REAL,
            max_rate REAL,
            min_rate REAL,
            exit_reason VARCHAR(64),
            exit_order_status VARCHAR(32),
            close_profit REAL,
            close_profit_abs REAL,
            strategy VARCHAR(64) NOT NULL,
            timeframe VARCHAR(16) DEFAULT '15m',
            created_at VARCHAR(64)
        );
        """
        sql_orders = """
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ft_trade_id INTEGER,
            ft_order_side VARCHAR(16) NOT NULL,
            ft_pair VARCHAR(32) NOT NULL,
            ft_is_open INTEGER NOT NULL DEFAULT 1,
            ft_amount REAL NOT NULL,
            ft_price REAL NOT NULL,
            order_id VARCHAR(64) UNIQUE,
            status VARCHAR(32) NOT NULL,
            symbol VARCHAR(32) NOT NULL,
            order_type VARCHAR(16) NOT NULL,
            side VARCHAR(16) NOT NULL,
            price REAL,
            average REAL,
            amount REAL,
            filled REAL,
            remaining REAL,
            cost REAL,
            order_date VARCHAR(64) NOT NULL,
            order_filled_date VARCHAR(64),
            order_update_date VARCHAR(64),
            ft_fee_base REAL DEFAULT 0
        );
        """
        try:
            self.db.execute(sql_trades)
            self.db.execute(sql_orders)
        except Exception as e:
            logger.warning(f"Could not ensure trades/orders schema: {e}")

    def get_open_positions(self, symbol: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns open positions from database."""
        if symbol:
            return self.db.query(
                "SELECT * FROM trades WHERE is_open = 1 AND pair = ? ORDER BY id DESC",
                (symbol,),
            )
        return self.db.query("SELECT * FROM trades WHERE is_open = 1 ORDER BY id DESC")

    def count_trades_today(self, symbol: Optional[str] = None) -> int:
        """Returns number of trades executed today UTC."""
        today_start = datetime.now(timezone.utc).strftime("%Y-%m-%d 00:00:00")
        if symbol:
            r = self.db.query_one(
                "SELECT COUNT(*) as cnt FROM trades WHERE pair = ? AND open_date >= ?",
                (symbol, today_start),
            )
        else:
            r = self.db.query_one(
                "SELECT COUNT(*) as cnt FROM trades WHERE open_date >= ?",
                (today_start,),
            )
        return int(r["cnt"]) if r else 0

    def record_entry(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        stop_loss: float,
        take_profit: Optional[float],
        strategy_id: str,
        timeframe: str = "15m",
        order_id: Optional[str] = None,
    ) -> int:
        """
        Records new opened position and entry order into database.
        Returns trade ID.
        """
        now_dt = datetime.now(timezone.utc)
        now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")
        oid = order_id or f"ORD_AUT_{uuid.uuid4().hex[:10]}"
        stake_amount = round(amount * price, 4)

        # Inspect available table columns to adapt dynamically
        cols_info = self.db.query("PRAGMA table_info(trades)")
        avail_cols = {c["name"] for c in cols_info} if cols_info else set()

        trade_data = {
            "pair": symbol,
            "is_open": 1,
            "fee_open": 0.0,
            "fee_close": 0.0,
            "open_rate": price,
            "close_rate": price,
            "amount": amount,
            "stake_amount": stake_amount,
            "open_date": now_str,
            "stop_loss": stop_loss,
            "initial_stop_loss": stop_loss,
            "max_rate": price,
            "min_rate": price,
            "strategy": strategy_id,
            "timeframe": timeframe,
        }
        if "exchange" in avail_cols:
            trade_data["exchange"] = "binance"
        if "is_short" in avail_cols:
            trade_data["is_short"] = 1 if side.lower() in ("sell", "short") else 0
        if "is_stop_loss_trailing" in avail_cols:
            trade_data["is_stop_loss_trailing"] = 0
        if "interest_rate" in avail_cols:
            trade_data["interest_rate"] = 0.0
        if "record_version" in avail_cols:
            trade_data["record_version"] = 1
        if "enter_tag" in avail_cols:
            trade_data["enter_tag"] = oid
        if "open_order_id" in avail_cols:
            trade_data["open_order_id"] = oid

        cols = list(trade_data.keys())
        placeholders = ", ".join(["?"] * len(cols))
        col_names = ", ".join(cols)
        sql_trade = f"INSERT INTO trades ({col_names}) VALUES ({placeholders})"
        self.db.execute(sql_trade, tuple(trade_data.values()))

        # Fetch inserted trade ID
        r = None
        if "enter_tag" in avail_cols:
            r = self.db.query_one("SELECT id FROM trades WHERE enter_tag = ? ORDER BY id DESC", (oid,))
        elif "open_order_id" in avail_cols:
            r = self.db.query_one("SELECT id FROM trades WHERE open_order_id = ? ORDER BY id DESC", (oid,))
        if not r:
            r = self.db.query_one("SELECT MAX(id) as id FROM trades")
        trade_id = r["id"] if r else 1

        # 2. Insert order with valid ft_trade_id
        order_cols_info = self.db.query("PRAGMA table_info(orders)")
        avail_order_cols = {c["name"] for c in order_cols_info} if order_cols_info else set()
        order_data = {
            "ft_trade_id": trade_id,
            "ft_order_side": side.lower(),
            "ft_pair": symbol,
            "ft_is_open": 0,
            "ft_amount": amount,
            "ft_price": price,
            "order_id": oid,
            "status": "FILLED",
            "symbol": symbol,
            "order_type": "LIMIT",
            "side": side.upper(),
            "price": price,
            "average": price,
            "amount": amount,
            "filled": amount,
            "remaining": 0.0,
            "cost": stake_amount,
            "order_date": now_str,
            "order_filled_date": now_str,
            "ft_fee_base": 0.0,
        }
        filtered_order_data = {k: v for k, v in order_data.items() if not avail_order_cols or k in avail_order_cols}
        o_cols = list(filtered_order_data.keys())
        o_placeholders = ", ".join(["?"] * len(o_cols))
        o_col_names = ", ".join(o_cols)
        sql_order = f"INSERT INTO orders ({o_col_names}) VALUES ({o_placeholders})"
        self.db.execute(sql_order, tuple(filtered_order_data.values()))

        logger.info(f"[PositionManager] Recorded trade entry #{trade_id} for {symbol} @ {price:.4f}, SL={stop_loss:.4f}")
        return trade_id

    def check_and_execute_exits(self, current_prices: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Checks all open positions against latest market prices.
        Triggers STOP_LOSS or TAKE_PROFIT exits automatically.
        """
        open_trades = self.get_open_positions()
        exits_executed = []
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        for tr in open_trades:
            pair = tr["pair"]
            cur_price = current_prices.get(pair)
            if cur_price is None or cur_price <= 0:
                continue

            trade_id = tr["id"]
            open_rate = float(tr["open_rate"] or 0.0)
            sl = float(tr.get("stop_loss") or (open_rate * 0.985))
            initial_sl = float(tr.get("initial_stop_loss") or sl)
            amount = float(tr["amount"] or 1.0)
            strategy = tr.get("strategy", "hybrid_v2c")

            # Default take-profit heuristic: 2x risk from initial SL
            risk_dist = abs(open_rate - initial_sl)
            tp = open_rate + (risk_dist * 2.0)

            # Update high/low watermarks
            max_rate = max(float(tr.get("max_rate") or open_rate), cur_price)
            min_rate = min(float(tr.get("min_rate") or open_rate), cur_price)
            self.db.execute(
                "UPDATE trades SET close_rate = ?, max_rate = ?, min_rate = ? WHERE id = ?",
                (cur_price, max_rate, min_rate, trade_id),
            )

            # Check Stop Loss & Take Profit (Long position assumed)
            exit_triggered = False
            exit_reason = ""

            if cur_price <= sl:
                exit_triggered = True
                exit_reason = "stop_loss"
            elif cur_price >= tp:
                exit_triggered = True
                exit_reason = "take_profit"

            if exit_triggered:
                profit_pct = (cur_price - open_rate) / open_rate
                profit_abs = (cur_price - open_rate) * amount

                # Close trade in database
                sql_close = """
                UPDATE trades SET
                    is_open = 0,
                    close_rate = ?,
                    close_date = ?,
                    close_profit = ?,
                    close_profit_abs = ?,
                    exit_reason = ?,
                    exit_order_status = 'FILLED'
                WHERE id = ?
                """
                self.db.execute(sql_close, (
                    cur_price, now_str, profit_pct, profit_abs, exit_reason, trade_id
                ))

                # Create exit order
                exit_oid = f"ORD_EXIT_{uuid.uuid4().hex[:10]}"
                sql_exit_order = """
                INSERT INTO orders (
                    ft_trade_id, ft_order_side, ft_pair, ft_is_open, ft_amount, ft_price,
                    order_id, status, symbol, order_type, side,
                    price, average, amount, filled, remaining, cost,
                    order_date, order_filled_date, ft_fee_base
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                self.db.execute(sql_exit_order, (
                    trade_id, "sell", pair, 0, amount, cur_price,
                    exit_oid, "FILLED", pair, "MARKET", "SELL",
                    cur_price, cur_price, amount, amount, 0.0, amount * cur_price,
                    now_str, now_str, 0.0
                ))

                exit_info = {
                    "trade_id": trade_id,
                    "symbol": pair,
                    "exit_reason": exit_reason,
                    "entry_price": open_rate,
                    "exit_price": cur_price,
                    "profit_abs": round(profit_abs, 4),
                    "profit_pct": round(profit_pct * 100.0, 2),
                    "strategy": strategy,
                    "closed_at": now_str,
                }
                exits_executed.append(exit_info)
                logger.info(f"[PositionManager] Closed trade #{trade_id} via {exit_reason} for {pair}: {profit_abs:+.4f} USDT ({profit_pct * 100.0:+.2f}%)")

                # Send Telegram notification
                try:
                    icon = "🎯" if profit_abs >= 0 else "🛑"
                    tg_msg = (
                        f"{icon} <b>CUANIMUS POSITION EXIT</b>\n\n"
                        f"• <b>Pair:</b> <code>{pair}</code>\n"
                        f"• <b>Reason:</b> <code>{exit_reason.upper()}</code>\n"
                        f"• <b>Entry:</b> <code>{open_rate:.4f}</code>\n"
                        f"• <b>Exit:</b> <code>{cur_price:.4f}</code>\n"
                        f"• <b>PnL:</b> <b>{profit_abs:+.2f} USDT ({profit_pct * 100.0:+.2f}%)</b>\n"
                        f"• <b>Strategy:</b> <code>{strategy}</code>\n"
                        f"• <b>Time:</b> <code>{now_str}</code>"
                    )
                    self.telegram.send_alert(tg_msg)
                except Exception as tg_err:
                    logger.warning(f"Failed to dispatch Telegram exit notification: {tg_err}")

        return exits_executed
