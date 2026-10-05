"""
CUANIMUS Unified Database Abstraction & Persistence Manager.
Provides zero-dependency SQLite by default, with seamless dynamic switching
to PostgreSQL (containerized or external) at any time.
"""
import os
import sys
import sqlite3
import re
import logging
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class DatabaseBackend(str, Enum):
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"


class DatabaseManager:
    """
    Unified database manager for CUANIMUS trading telemetry, orders, and state.
    Defaults to SQLite for zero-configuration, zero-dependency local operation.
    Enables user-selectable transition to PostgreSQL with automated data migration.
    """

    _instance: Optional["DatabaseManager"] = None

    def __init__(self, base_dir: Optional[str] = None):
        self.base_dir = base_dir or os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..")
        )
        self._pg_conn_params: Optional[Dict[str, Any]] = None
        self._sqlite_path: str = os.path.join(
            self.base_dir, "user_data", "tradesv3.dryrun.sqlite"
        )
        self._backend: DatabaseBackend = self._detect_backend()

    @classmethod
    def get_instance(cls, base_dir: Optional[str] = None) -> "DatabaseManager":
        if cls._instance is None:
            cls._instance = DatabaseManager(base_dir=base_dir)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        cls._instance = None

    def _detect_backend(self) -> DatabaseBackend:
        """
        Determines the active database backend according to the hierarchy:
        1. Explicit DB_BACKEND env var ('sqlite' | 'postgres' | 'postgresql')
        2. DB_URL / DATABASE_URL starting with 'postgresql://' or 'postgres://'
        3. Config in cuanimus.user.yaml or config/defaults.yaml
        4. Default: SQLite (tradesv3.dryrun.sqlite)
        """
        env_backend = os.environ.get("DB_BACKEND", "").lower().strip()
        if env_backend in ("postgres", "postgresql"):
            return DatabaseBackend.POSTGRESQL
        elif env_backend == "sqlite":
            return DatabaseBackend.SQLITE

        db_url = os.environ.get("DB_URL", "") or os.environ.get("DATABASE_URL", "")
        if not db_url:
            # Check cuanimus.user.yaml
            user_yaml = os.path.join(self.base_dir, "cuanimus.user.yaml")
            if os.path.exists(user_yaml):
                try:
                    import yaml
                    with open(user_yaml, "r") as f:
                        data = yaml.safe_load(f) or {}
                        db_url = data.get("environment", {}).get("db_url", "")
                except Exception:
                    pass

        if db_url.startswith("postgresql://") or db_url.startswith("postgres://"):
            return DatabaseBackend.POSTGRESQL

        return DatabaseBackend.SQLITE

    @property
    def backend(self) -> DatabaseBackend:
        return self._backend

    @property
    def is_postgres(self) -> bool:
        return self._backend == DatabaseBackend.POSTGRESQL

    @property
    def is_sqlite(self) -> bool:
        return self._backend == DatabaseBackend.SQLITE

    def get_sqlite_path(self) -> str:
        # Check if tradesv3.dryrun.sqlite exists, otherwise check cuanimus.sqlite
        p1 = os.path.join(self.base_dir, "user_data", "tradesv3.dryrun.sqlite")
        p2 = os.path.join(self.base_dir, "user_data", "cuanimus.sqlite")
        if os.path.exists(p1):
            return p1
        if os.path.exists(p2):
            return p2
        return p1

    def _get_postgres_params(self) -> Dict[str, Any]:
        """Parses PostgreSQL connection parameters from env or URL."""
        db_url = os.environ.get("DB_URL", "") or os.environ.get("DATABASE_URL", "")
        if db_url and (db_url.startswith("postgresql://") or db_url.startswith("postgres://")):
            from urllib.parse import urlparse
            u = urlparse(db_url)
            return {
                "dbname": u.path.lstrip("/") or "cuanimus",
                "user": u.username or "cuanimus",
                "password": u.password or "cuanimus_secret_pass",
                "host": u.hostname or "localhost",
                "port": u.port or 5432,
            }

        return {
            "dbname": os.environ.get("DB_NAME", "cuanimus"),
            "user": os.environ.get("DB_USER", "cuanimus"),
            "password": os.environ.get("DB_PASSWORD", "cuanimus_secret_pass"),
            "host": os.environ.get("DB_HOST", "localhost"),
            "port": int(os.environ.get("DB_PORT", 5432)),
        }

    @contextmanager
    def get_connection(self):
        """
        Context manager returning (conn, cursor) with dict-like row access.
        Automatically manages commit/rollback and connection cleanup.
        """
        if self.is_postgres:
            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor
            except ImportError:
                raise RuntimeError(
                    "PostgreSQL driver 'psycopg2' is not installed in the current environment. "
                    "Install via 'pip install psycopg2-binary' or run CUANIMUS via Docker where it is pre-installed."
                )

            params = self._get_postgres_params()
            conn = psycopg2.connect(**params)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            try:
                yield conn, cur
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()
                conn.close()
        else:
            path = self.get_sqlite_path()
            os.makedirs(os.path.dirname(path), exist_ok=True)
            conn = sqlite3.connect(path)
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            try:
                yield conn, cur
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                cur.close()
                conn.close()

    def _normalize_sql(self, sql: str) -> str:
        """Adapts SQL parameter placeholders (? to %s) if running on PostgreSQL."""
        if self.is_postgres:
            return sql.replace("?", "%s")
        return sql

    def query(self, sql: str, params: Tuple = ()) -> List[Dict[str, Any]]:
        """Executes a SELECT query and returns rows as a list of dicts."""
        norm_sql = self._normalize_sql(sql)
        with self.get_connection() as (_, cur):
            cur.execute(norm_sql, params)
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def query_one(self, sql: str, params: Tuple = ()) -> Optional[Dict[str, Any]]:
        """Executes a SELECT query and returns a single row as dict, or None."""
        norm_sql = self._normalize_sql(sql)
        with self.get_connection() as (_, cur):
            cur.execute(norm_sql, params)
            row = cur.fetchone()
            return dict(row) if row else None

    def execute(self, sql: str, params: Tuple = ()) -> int:
        """Executes INSERT/UPDATE/DELETE and returns affected row count."""
        norm_sql = self._normalize_sql(sql)
        with self.get_connection() as (_, cur):
            cur.execute(norm_sql, params)
            return cur.rowcount

    def get_status(self) -> Dict[str, Any]:
        """Returns comprehensive diagnostic and connectivity status."""
        active_backend = self._backend.value
        status: Dict[str, Any] = {
            "backend": active_backend,
            "is_default": self._backend == DatabaseBackend.SQLITE,
            "connected": False,
            "source": "",
            "tables": {},
            "error": None,
        }

        try:
            if self.is_postgres:
                params = self._get_postgres_params()
                status["source"] = f"postgresql://{params['user']}@{params['host']}:{params['port']}/{params['dbname']}"
            else:
                status["source"] = self.get_sqlite_path()

            with self.get_connection() as (_, cur):
                status["connected"] = True
                for tbl in ["trades", "orders", "wallet_history", "agent_sessions", "audit_logs"]:
                    try:
                        cur.execute(f"SELECT COUNT(*) as cnt FROM {tbl}")
                        r = cur.fetchone()
                        cnt = r["cnt"] if isinstance(r, dict) else r[0]
                        status["tables"][tbl] = cnt
                    except Exception:
                        status["tables"][tbl] = 0
        except Exception as e:
            status["error"] = str(e)

        return status

    def switch_backend(self, target: str, url: Optional[str] = None) -> Dict[str, Any]:
        """
        Switches the database backend dynamically by updating cuanimus.user.yaml.
        target: 'sqlite' or 'postgres' / 'postgresql'
        """
        target_norm = target.lower().strip()
        if target_norm in ("postgres", "postgresql"):
            new_backend = DatabaseBackend.POSTGRESQL
            target_url = url or "postgresql://cuanimus:cuanimus_secret_pass@localhost:5432/cuanimus"
        elif target_norm == "sqlite":
            new_backend = DatabaseBackend.SQLITE
            target_url = url or "sqlite:///user_data/tradesv3.dryrun.sqlite"
        else:
            raise ValueError(f"Unknown database backend: '{target}'. Choose 'sqlite' or 'postgres'.")

        user_yaml = os.path.join(self.base_dir, "cuanimus.user.yaml")
        import yaml
        cfg = {}
        if os.path.exists(user_yaml):
            try:
                with open(user_yaml, "r") as f:
                    cfg = yaml.safe_load(f) or {}
            except Exception:
                pass

        if "environment" not in cfg:
            cfg["environment"] = {}
        cfg["environment"]["db_url"] = target_url

        with open(user_yaml, "w") as f:
            yaml.dump(cfg, f, default_flow_style=False, sort_keys=False)

        os.environ["DB_BACKEND"] = new_backend.value
        os.environ["DB_URL"] = target_url
        self._backend = new_backend

        return {
            "status": "SUCCESS",
            "active_backend": new_backend.value,
            "db_url": target_url,
            "config_file": user_yaml,
            "message": f"Switched database backend to {new_backend.value.upper()}."
        }

    def migrate_sqlite_to_postgres(self) -> Dict[str, Any]:
        """
        Migrates all existing trades, orders, and wallet records from SQLite to PostgreSQL.
        Safe and idempotent.
        """
        try:
            import psycopg2
            from psycopg2.extras import execute_batch
        except ImportError:
            raise RuntimeError(
                "psycopg2 is required for migration. Install via 'pip install psycopg2-binary' or run via Docker."
            )

        sqlite_path = self.get_sqlite_path()
        if not os.path.exists(sqlite_path):
            return {"status": "SKIPPED", "message": f"SQLite database not found at {sqlite_path}"}

        s_conn = sqlite3.connect(sqlite_path)
        s_conn.row_factory = sqlite3.Row
        s_cur = s_conn.cursor()

        pg_params = self._get_postgres_params()
        p_conn = psycopg2.connect(**pg_params)
        p_cur = p_conn.cursor()

        counts = {"trades": 0, "orders": 0, "wallet_history": 0}

        try:
            # 1. Migrate trades
            s_cur.execute("SELECT * FROM trades")
            trades = [dict(r) for r in s_cur.fetchall()]
            for t in trades:
                p_cur.execute("""
                    INSERT INTO trades (
                        id, pair, is_open, fee_open, fee_close, open_rate, close_rate,
                        amount, stake_amount, open_date, close_date,
                        stop_loss, initial_stop_loss, max_rate, min_rate, exit_reason,
                        exit_order_status, close_profit, close_profit_abs, strategy, timeframe
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s
                    ) ON CONFLICT (id) DO NOTHING
                """, (
                    t.get("id"), t.get("pair"), bool(t.get("is_open")),
                    float(t.get("fee_open") or 0.0), float(t.get("fee_close") or 0.0),
                    float(t.get("open_rate") or 0.0), t.get("close_rate"),
                    float(t.get("amount") or 0.0), float(t.get("stake_amount") or 0.0),
                    t.get("open_date"), t.get("close_date"),
                    t.get("stop_loss"), t.get("initial_stop_loss"),
                    t.get("max_rate"), t.get("min_rate"),
                    t.get("exit_reason"), t.get("exit_order_status"),
                    t.get("close_profit"), t.get("close_profit_abs"),
                    t.get("strategy") or "v2_pullback",
                    t.get("timeframe") or "15m"
                ))
            counts["trades"] = len(trades)

            # 2. Migrate orders
            s_cur.execute("SELECT * FROM orders")
            orders = [dict(r) for r in s_cur.fetchall()]
            for o in orders:
                p_cur.execute("""
                    INSERT INTO orders (
                        id, ft_trade_id, ft_order_side, ft_pair, ft_is_open, ft_amount,
                        ft_price, order_id, status, symbol, order_type, side, price,
                        average, amount, filled, remaining, cost, order_date,
                        order_filled_date, order_update_date, ft_fee_base
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s
                    ) ON CONFLICT (id) DO NOTHING
                """, (
                    o.get("id"), o.get("ft_trade_id"), (o.get("ft_order_side") or "buy").lower(),
                    o.get("ft_pair") or "ETH/USDT:USDT", bool(o.get("ft_is_open")),
                    float(o.get("ft_amount") or 0.0), float(o.get("ft_price") or 0.0),
                    o.get("order_id"), o.get("status") or "closed",
                    o.get("symbol") or o.get("ft_pair") or "ETH/USDT:USDT",
                    (o.get("order_type") or "limit").lower(), (o.get("side") or "buy").lower(),
                    o.get("price"), o.get("average"), float(o.get("amount") or 0.0),
                    float(o.get("filled") or 0.0), float(o.get("remaining") or 0.0),
                    float(o.get("cost") or 0.0), o.get("order_date"),
                    o.get("order_filled_date"), o.get("order_update_date"),
                    float(o.get("ft_fee_base") or 0.0)
                ))
            counts["orders"] = len(orders)

            # 3. Migrate wallet_history
            s_cur.execute("SELECT * FROM wallet_history")
            wallets = [dict(r) for r in s_cur.fetchall()]
            for w in wallets:
                bal = float(w.get("balance") or 0.0)
                p_cur.execute("""
                    INSERT INTO wallet_history (
                        id, timestamp, currency, balance, available, locked, is_live
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s
                    ) ON CONFLICT (id) DO NOTHING
                """, (
                    w.get("id"), w.get("timestamp"), w.get("currency") or "USDT",
                    bal, bal, 0.0, False
                ))
            counts["wallet_history"] = len(wallets)

            # Update sequences
            p_cur.execute("SELECT setval('trades_id_seq', (SELECT COALESCE(MAX(id), 1) FROM trades));")
            p_cur.execute("SELECT setval('orders_id_seq', (SELECT COALESCE(MAX(id), 1) FROM orders));")
            p_cur.execute("SELECT setval('wallet_history_id_seq', (SELECT COALESCE(MAX(id), 1) FROM wallet_history));")

            p_conn.commit()
            return {
                "status": "SUCCESS",
                "migrated": counts,
                "message": f"Successfully migrated {counts['trades']} trades, {counts['orders']} orders, and {counts['wallet_history']} wallet records to PostgreSQL."
            }
        except Exception as e:
            p_conn.rollback()
            raise RuntimeError(f"Database migration error: {str(e)}")
        finally:
            s_cur.close()
            s_conn.close()
            p_cur.close()
            p_conn.close()
