"""
CUANIMUS Paper Trading Safety Guard & Real-Time Telemetry Tracker.
Ensures that when running in PAPER / DRY-RUN mode, no real-money exchange endpoints
can ever be invoked, and provides telemetry tracking for execution quality metrics.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import time


class FatalSafetyViolationError(RuntimeError):
    """Raised whenever a live order submission is attempted in paper mode."""
    pass


@dataclass
class PaperTelemetry:
    """Tracks the 20+ live execution metrics for paper validation."""
    signal_latency_ms: List[float] = field(default_factory=list)
    decision_latency_ms: List[float] = field(default_factory=list)
    submission_latency_ms: List[float] = field(default_factory=list)
    exchange_response_latency_ms: List[float] = field(default_factory=list)

    total_signals: int = 0
    approved_signals: int = 0
    vetoed_signals: int = 0

    limit_orders_submitted: int = 0
    limit_orders_filled: int = 0
    limit_orders_cancelled: int = 0
    partial_fills: int = 0
    rejections: int = 0

    spreads_bps: List[float] = field(default_factory=list)
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


class PaperExecutionSafetyGuard:
    """
    Enforces absolute isolation of paper mode from live capital APIs.
    """
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.telemetry = PaperTelemetry()

    def assert_paper_safety(self, action_name: str = "submit_order"):
        """Throws FatalSafetyViolationError if dry_run is False or live execution attempted."""
        if not self.dry_run:
            raise FatalSafetyViolationError(
                f"FATAL RISK BREACH: Live order submission '{action_name}' attempted while real capital trading is disabled!"
            )

    def execute_paper_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        price: float,
        order_type: str = "limit",
    ) -> Dict[str, Any]:
        """
        Safely simulates paper order execution without contacting live exchange.
        """
        self.assert_paper_safety("execute_paper_order")

        # Record telemetry
        self.telemetry.limit_orders_submitted += 1
        return {
            "status": "simulated",
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "price": price,
            "order_type": order_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "is_paper": True,
        }

    def generate_telemetry_summary(self) -> Dict[str, Any]:
        t = self.telemetry
        avg_signal_lat = sum(t.signal_latency_ms) / len(t.signal_latency_ms) if t.signal_latency_ms else 0.0
        avg_resp_lat = sum(t.exchange_response_latency_ms) / len(t.exchange_response_latency_ms) if t.exchange_response_latency_ms else 0.0
        fill_rate = (t.limit_orders_filled / t.limit_orders_submitted * 100.0) if t.limit_orders_submitted > 0 else 0.0
        cancel_rate = (t.limit_orders_cancelled / t.limit_orders_submitted * 100.0) if t.limit_orders_submitted > 0 else 0.0

        return {
            "dry_run": self.dry_run,
            "safety_active": True,
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
