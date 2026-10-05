"""
CUANIMUS Position Sizing Engine.
"""
import math
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def calculate_position_size(
    wallet_balance: float,
    risk_per_trade_pct: float,
    entry_price: float,
    stop_loss_price: float,
    leverage: float,
    min_notional: float = 5.0,
    max_margin_ratio: float = 0.25,
    step_size: float = 0.001
) -> Dict[str, Any]:
    if wallet_balance <= 0:
        return {"approved": False, "reason": "NON_POSITIVE_WALLET_BALANCE"}
    if entry_price <= 0 or stop_loss_price <= 0:
        return {"approved": False, "reason": "INVALID_PRICE_LEVEL"}
    if leverage < 1.0:
        return {"approved": False, "reason": "LEVERAGE_LESS_THAN_ONE"}

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

    raw_contracts = round(desired_notional / entry_price, 8)
    quantized_contracts = math.floor(round(raw_contracts / step_size, 8)) * step_size

    if quantized_contracts <= 0:
        return {"approved": False, "reason": "QUANTIZED_CONTRACTS_ZERO"}

    return {
        "approved": True,
        "stake_amount": round(required_margin, 2),
        "contracts": round(quantized_contracts, 6),
        "notional_value": round(quantized_contracts * entry_price, 2),
        "max_risk_usdt": round(max_loss_usdt, 2),
        "sl_distance_pct": round(sl_distance_fraction * 100, 2)
    }

