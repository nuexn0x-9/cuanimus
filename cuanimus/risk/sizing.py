"""
CUANIMUS Position Sizing Engine.
Calculates risk-adjusted position sizes based on wallet balance, risk parameters,
and dynamic exchange symbol precision filters (tick_size, step_size, min_notional).
"""
import math
import logging
from typing import Dict, Any, Optional

from cuanimus.exchange.binance_adapter import get_binance_adapter

logger = logging.getLogger(__name__)


def quantize_value(value: float, step: float) -> float:
    """Quantizes a value down to the nearest multiple of step."""
    if step <= 0:
        return value
    precision = max(0, int(round(-math.log10(step)))) if step < 1.0 else 0
    quantized = math.floor(round(value / step, 8)) * step
    return round(quantized, precision)


def calculate_position_size(
    wallet_balance: float,
    risk_per_trade_pct: float,
    entry_price: float,
    stop_loss_price: float,
    leverage: float,
    min_notional: float = 5.0,
    max_margin_ratio: float = 0.25,
    step_size: float = 0.001,
    tick_size: float = 0.01,
    min_qty: float = 0.001,
    symbol: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Computes position size constrained by risk budget, max margin ratio,
    leverage, and dynamic exchange filters.
    """
    if wallet_balance <= 0:
        return {"approved": False, "reason": "NON_POSITIVE_WALLET_BALANCE"}
    if entry_price <= 0 or stop_loss_price <= 0:
        return {"approved": False, "reason": "INVALID_PRICE_LEVEL"}
    if leverage < 1.0:
        return {"approved": False, "reason": "LEVERAGE_LESS_THAN_ONE"}

    # Load dynamic Binance exchange filters if symbol is provided
    if symbol:
        try:
            filters = get_binance_adapter().get_symbol_filter(symbol)
            if filters:
                step_size = filters.get("step_size", step_size)
                min_notional = filters.get("min_notional", min_notional)
                tick_size = filters.get("tick_size", tick_size)
                min_qty = filters.get("min_qty", min_qty)
        except Exception as e:
            logger.debug(f"Using default sizing filters for {symbol}: {e}")

    sl_distance_fraction = abs(entry_price - stop_loss_price) / entry_price
    if sl_distance_fraction < 0.002:
        return {"approved": False, "reason": "STOP_LOSS_TOO_TIGHT"}

    max_loss_usdt = wallet_balance * (risk_per_trade_pct / 100.0)
    desired_notional = max_loss_usdt / sl_distance_fraction
    required_margin = desired_notional / leverage

    max_allowed_margin = wallet_balance * max_margin_ratio
    if required_margin > max_allowed_margin:
        required_margin = max_allowed_margin
        desired_notional = required_margin * leverage
        max_loss_usdt = desired_notional * sl_distance_fraction

    if desired_notional < min_notional:
        return {"approved": False, "reason": f"NOTIONAL_{desired_notional:.2f}_BELOW_MIN_{min_notional}"}

    raw_contracts = desired_notional / entry_price
    quantized_contracts = quantize_value(raw_contracts, step_size)

    if quantized_contracts < min_qty or quantized_contracts <= 0:
        return {"approved": False, "reason": "QUANTIZED_CONTRACTS_BELOW_MIN"}

    actual_notional = quantize_value(quantized_contracts * entry_price, 0.01)
    if actual_notional < min_notional:
        return {"approved": False, "reason": f"NOTIONAL_{actual_notional:.2f}_BELOW_MIN_{min_notional}"}

    precision = max(0, int(round(-math.log10(step_size)))) if step_size < 1.0 else 0

    return {
        "approved": True,
        "stake_amount": round(required_margin, 2),
        "contracts": round(quantized_contracts, precision),
        "notional_value": actual_notional,
        "max_risk_usdt": round(max_loss_usdt, 2),
        "sl_distance_pct": round(sl_distance_fraction * 100, 2),
        "step_size": step_size,
        "tick_size": tick_size,
        "min_notional": min_notional,
    }
