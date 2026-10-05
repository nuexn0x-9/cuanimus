"""
CUANIMUS Dynamic Stop Loss & Take Profit Calculators.
"""
from enum import Enum
from typing import Optional
from cuanimus.common.types import SignalDirection

class StopLossModel(str, Enum):
    ATR = "ATR"
    STRUCTURE = "STRUCTURE"
    VOLATILITY_BAND = "VOLATILITY_BAND"
    HYBRID = "HYBRID"

def compute_stop_loss(
    direction: SignalDirection,
    entry_price: float,
    atr_value: float,
    atr_multiplier: float = 2.0,
    swing_low: Optional[float] = None,
    swing_high: Optional[float] = None,
    model: StopLossModel = StopLossModel.HYBRID,
) -> float:
    assert entry_price > 0, "Entry price must be positive"
    assert atr_value > 0, "ATR value must be positive"

    atr_distance = atr_value * atr_multiplier

    if direction == SignalDirection.LONG:
        atr_stop = entry_price - atr_distance

        if model == StopLossModel.ATR:
            return round(atr_stop, 4)

        if model == StopLossModel.STRUCTURE and swing_low is not None:
            return round(swing_low * 0.998, 4)

        if model == StopLossModel.HYBRID:
            if swing_low is not None:
                struct_stop = swing_low * 0.998
                min_safe_stop = entry_price - (atr_value * 1.2)
                chosen = min(struct_stop, min_safe_stop)
                max_stop = entry_price - (atr_distance * 1.5)
                return round(max(chosen, max_stop), 4)
            return round(atr_stop, 4)

        return round(atr_stop, 4)

    elif direction == SignalDirection.SHORT:
        atr_stop = entry_price + atr_distance

        if model == StopLossModel.ATR:
            return round(atr_stop, 4)

        if model == StopLossModel.STRUCTURE and swing_high is not None:
            return round(swing_high * 1.002, 4)

        if model == StopLossModel.HYBRID:
            if swing_high is not None:
                struct_stop = swing_high * 1.002
                min_safe_stop = entry_price + (atr_value * 1.2)
                chosen = max(struct_stop, min_safe_stop)
                max_stop = entry_price + (atr_distance * 1.5)
                return round(min(chosen, max_stop), 4)
            return round(atr_stop, 4)

        return round(atr_stop, 4)

    else:
        raise ValueError(f"Cannot compute stop loss for direction: {direction}")

def compute_take_profit(
    direction: SignalDirection,
    entry_price: float,
    stop_loss_price: float,
    risk_reward_ratio: float = 2.0,
) -> float:
    risk_distance = abs(entry_price - stop_loss_price)
    reward_distance = risk_distance * risk_reward_ratio

    if direction == SignalDirection.LONG:
        return round(entry_price + reward_distance, 4)
    elif direction == SignalDirection.SHORT:
        return round(entry_price - reward_distance, 4)
    else:
        raise ValueError(f"Invalid direction for take profit: {direction}")

