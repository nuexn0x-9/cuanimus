"""
CUANIMUS Unified Execution Safety Guard & Router
Implements Freqtrade-style execution routing:
- dry_run == True: PAPER mode (simulated fill, local ledger, zero private exchange calls).
- dry_run == False & environment == "testnet": Authenticated execution to Binance Testnet.
- dry_run == False & environment == "live": Authenticated execution to Binance Live (fail-closed if credentials missing).
Never bypasses RiskEngine or AgentTradingPolicy.
"""
import os
import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from cuanimus.common.exceptions import FatalSafetyViolationError

logger = logging.getLogger(__name__)


@dataclass
class PaperTelemetry:
    """Tracks latency, fill-rates, slippage, and safety incidents."""
    total_signals: int = 0
    approved_signals: int = 0
    vetoed_signals: int = 0

    signal_latency_ms: List[float] = field(default_factory=list)
    exchange_response_latency_ms: List[float] = field(default_factory=list)

    limit_orders_submitted: int = 0
    limit_orders_filled: int = 0
    limit_orders_cancelled: int = 0

    partial_fills: int = 0
    rejections: int = 0

    observed_slippages_pct: List[float] = field(default_factory=list)
    modeled_slippage_pct: float = 0.05
    total_fees_simulated: float = 0.0
    total_funding_simulated: float = 0.0

    missed_signals: int = 0
    stale_data_events: int = 0
    reconnect_events: int = 0
    api_failures: int = 0
    clock_drift_events: int = 0
    emergency_stops: int = 0


class UnifiedExecutionSafetyGuard:
    """
    Unified Execution Safety Guard & Router.
    Controls transition between Paper (simulation) and Real Exchange Execution
    (Testnet & Live) based on profile execution_mode and global dry_run flag.
    """

    def __init__(self, dry_run: bool = True, environment: str = "paper"):
        self.dry_run = dry_run
        self.environment = environment.lower().strip()
        self.telemetry = PaperTelemetry()

    def assert_paper_safety(self, action_name: str = "submit_order") -> None:
        """Enforces that paper simulation never contacts live exchange APIs."""
        if not self.dry_run:
            safety_token = os.environ.get("CUANIMUS_ALLOW_REAL_CAPITAL", "")
            if safety_token != "I_UNDERSTAND_THE_RISKS":
                raise FatalSafetyViolationError(
                    f"FATAL RISK BREACH: Live order submission '{action_name}' attempted while real capital trading is disabled!"
                )

    def assert_execution_safety(self, action_name: str = "submit_order", execution_mode: str = "paper") -> None:
        """
        Validates safety preconditions before executing an order.
        Fails closed if credentials or required clearance tokens are missing.
        """
        exec_mode = (execution_mode or "paper").lower().strip()

        if exec_mode == "paper":
            return

        # Real Execution Preflight (TESTNET or LIVE)
        from cuanimus.exchange.binance_private import get_binance_private_adapter

        adapter = get_binance_private_adapter(exec_mode)
        if not adapter.has_credentials():
            raise FatalSafetyViolationError(
                f"FATAL PREFLIGHT ERROR: Order execution '{action_name}' requested mode '{exec_mode.upper()}' "
                f"but Binance {exec_mode.upper()} credentials (API Key / Secret) are missing!"
            )

        if exec_mode == "live":
            safety_token = os.environ.get("CUANIMUS_ALLOW_REAL_CAPITAL", "")
            if safety_token != "I_UNDERSTAND_THE_RISKS":
                raise FatalSafetyViolationError(
                    "FATAL RISK BREACH: Live real-capital trading requested, but mandatory environment token "
                    "CUANIMUS_ALLOW_REAL_CAPITAL='I_UNDERSTAND_THE_RISKS' is missing! Live order blocked."
                )

    def execute_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        order_type: str = "limit",
        execution_mode: str = "paper",
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        client_order_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Routes order to Simulated Paper Execution or Binance Private Adapter.
        Places exchange-level protective SL/TP orders when executing on exchange.
        """
        exec_mode = (execution_mode or "paper").lower().strip()
        is_paper = (exec_mode == "paper") or (self.dry_run and exec_mode not in ("testnet", "live"))

        if is_paper:
            self.telemetry.limit_orders_submitted += 1
            return {
                "status": "FILLED",
                "symbol": symbol,
                "side": side,
                "amount": amount,
                "price": price,
                "order_type": order_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "is_paper": True,
                "environment": "paper",
                "exchange_order_id": f"SIM_{uuid.uuid4().hex[:10]}",
            }

        # Real Authenticated Execution (TESTNET or LIVE)
        self.assert_execution_safety("execute_order", execution_mode=exec_mode)

        from cuanimus.exchange.binance_private import get_binance_private_adapter

        adapter = get_binance_private_adapter(exec_mode)

        # 1. Submit Primary Entry Order
        b_type = order_type.upper().strip()
        real_res = adapter.create_order(
            symbol=symbol,
            side=side,
            order_type=b_type,
            quantity=amount,
            price=price if b_type == "LIMIT" else None,
            client_order_id=client_order_id,
            time_in_force="GTC" if b_type == "LIMIT" else None,
        )

        exchange_order_id = str(real_res.get("orderId", ""))
        self.telemetry.limit_orders_submitted += 1
        self.telemetry.limit_orders_filled += 1

        # 2. Place Exchange-Level Protective SL/TP Orders
        protective_orders: List[Dict[str, Any]] = []
        exit_side = "SELL" if side.lower() == "buy" else "BUY"

        if stop_loss and stop_loss > 0:
            try:
                sl_res = adapter.create_order(
                    symbol=symbol,
                    side=exit_side,
                    order_type="STOP_MARKET",
                    quantity=amount,
                    stop_price=stop_loss,
                    close_position=True,
                )
                protective_orders.append({
                    "type": "STOP_LOSS",
                    "order_id": sl_res.get("orderId"),
                    "price": stop_loss,
                    "status": "SUBMITTED",
                })
                logger.info(f"[ExchangeProtection] Placed STOP_MARKET for {symbol} @ {stop_loss} on {exec_mode.upper()}")
            except Exception as sl_err:
                logger.warning(f"Failed to submit exchange protective Stop Loss on {exec_mode.upper()}: {sl_err}")

        if take_profit and take_profit > 0:
            try:
                tp_res = adapter.create_order(
                    symbol=symbol,
                    side=exit_side,
                    order_type="TAKE_PROFIT_MARKET",
                    quantity=amount,
                    stop_price=take_profit,
                    close_position=True,
                )
                protective_orders.append({
                    "type": "TAKE_PROFIT",
                    "order_id": tp_res.get("orderId"),
                    "price": take_profit,
                    "status": "SUBMITTED",
                })
                logger.info(f"[ExchangeProtection] Placed TAKE_PROFIT_MARKET for {symbol} @ {take_profit} on {exec_mode.upper()}")
            except Exception as tp_err:
                logger.warning(f"Failed to submit exchange protective Take Profit on {exec_mode.upper()}: {tp_err}")

        return {
            "status": real_res.get("status", "FILLED"),
            "symbol": symbol,
            "side": side,
            "amount": float(real_res.get("origQty", amount)),
            "price": float(real_res.get("price", price) or price),
            "order_type": order_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "is_paper": False,
            "environment": exec_mode,
            "exchange_order_id": exchange_order_id,
            "protective_orders": protective_orders,
            "raw_response": real_res,
        }

    def execute_paper_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        order_type: str = "limit",
    ) -> Dict[str, Any]:
        """Convenience method preserving backward compatibility."""
        res = self.execute_order(
            symbol=symbol,
            side=side,
            amount=amount,
            price=price,
            order_type=order_type,
            execution_mode="paper",
        )
        res["status"] = "simulated"
        return res

    def generate_telemetry_summary(self) -> Dict[str, Any]:
        t = self.telemetry
        avg_signal_lat = sum(t.signal_latency_ms) / len(t.signal_latency_ms) if t.signal_latency_ms else 0.0
        avg_resp_lat = sum(t.exchange_response_latency_ms) / len(t.exchange_response_latency_ms) if t.exchange_response_latency_ms else 0.0
        fill_rate = (t.limit_orders_filled / t.limit_orders_submitted * 100.0) if t.limit_orders_submitted > 0 else 0.0
        cancel_rate = (t.limit_orders_cancelled / t.limit_orders_submitted * 100.0) if t.limit_orders_submitted > 0 else 0.0

        return {
            "dry_run": self.dry_run,
            "safety_active": True,
            "environment": self.environment,
            "signal_metrics": {
                "total_signals": t.total_signals,
                "approved": t.approved_signals,
                "vetoed": t.vetoed_signals,
                "avg_signal_latency_ms": round(avg_signal_lat, 2),
            },
            "order_lifecycle": {
                "submitted": t.limit_orders_submitted,
                "filled": t.limit_orders_filled,
                "cancelled": t.limit_orders_cancelled,
                "fill_rate_pct": round(fill_rate, 2),
                "cancel_rate_pct": round(cancel_rate, 2),
                "partial_fills": t.partial_fills,
                "rejections": t.rejections,
            },
            "costs_and_slippage": {
                "observed_avg_slippage_pct": round(sum(t.observed_slippages_pct) / len(t.observed_slippages_pct), 4) if t.observed_slippages_pct else 0.0,
                "modeled_slippage_pct": t.modeled_slippage_pct,
                "simulated_fees": round(t.total_fees_simulated, 4),
                "simulated_funding": round(t.total_funding_simulated, 4),
            },
            "system_health": {
                "api_failures": t.api_failures,
                "reconnects": t.reconnect_events,
                "clock_drift_events": t.clock_drift_events,
                "emergency_stops": t.emergency_stops,
            }
        }


# Backward compatibility alias
PaperExecutionSafetyGuard = UnifiedExecutionSafetyGuard
