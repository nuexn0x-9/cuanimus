"""
CUANIMUS Quantitative Market Structure & Order Block Engine.
Provides deterministic definitions for Swing Fractals, Fibonacci Retracement,
and Bullish/Bearish Order Blocks with explicit mathematical invalidation rules.
"""
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from enum import Enum


class StructureType(str, Enum):
    SWING_HIGH = "SWING_HIGH"
    SWING_LOW = "SWING_LOW"
    ORDER_BLOCK_BULLISH = "ORDER_BLOCK_BULLISH"
    ORDER_BLOCK_BEARISH = "ORDER_BLOCK_BEARISH"


@dataclass
class SwingPoint:
    index: int
    confirmed_index: int
    price: float
    point_type: StructureType
    is_broken: bool = False


@dataclass
class OrderBlock:
    index: int
    confirmed_index: int
    top_price: float
    bottom_price: float
    block_type: StructureType
    is_mitigated: bool = False
    invalidation_price: float = 0.0


def detect_swing_points(
    highs: List[float],
    lows: List[float],
    window: int = 2,
) -> Dict[str, List[SwingPoint]]:
    """
    Deterministic swing fractal detection.
    A swing high requires 'window' bars to the left and right with strictly lower highs.
    A swing low requires 'window' bars to the left and right with strictly higher lows.
    Causal confirmation: A swing at index i is ONLY confirmed at index (i + window).
    """
    n = len(highs)
    swing_highs = []
    swing_lows = []

    for i in range(window, n - window):
        h = highs[i]
        l = lows[i]

        # Check Swing High
        is_sh = True
        for offset in range(-window, window + 1):
            if offset != 0 and highs[i + offset] >= h:
                is_sh = False
                break
        if is_sh:
            swing_highs.append(SwingPoint(
                index=i,
                confirmed_index=i + window,
                price=h,
                point_type=StructureType.SWING_HIGH,
            ))

        # Check Swing Low
        is_sl = True
        for offset in range(-window, window + 1):
            if offset != 0 and lows[i + offset] <= l:
                is_sl = False
                break
        if is_sl:
            swing_lows.append(SwingPoint(
                index=i,
                confirmed_index=i + window,
                price=l,
                point_type=StructureType.SWING_LOW,
            ))

    return {"swing_highs": swing_highs, "swing_lows": swing_lows}


def filter_confirmed_swings(
    swings: Dict[str, List[SwingPoint]],
    current_index: int,
) -> Dict[str, List[SwingPoint]]:
    """Strictly filters out any swing points whose confirmation index is in the future (> current_index)."""
    return {
        "swing_highs": [sp for sp in swings.get("swing_highs", []) if sp.confirmed_index <= current_index],
        "swing_lows": [sp for sp in swings.get("swing_lows", []) if sp.confirmed_index <= current_index],
    }



def compute_fibonacci_levels(
    swing_low: float,
    swing_high: float,
) -> Dict[str, float]:
    """
    Computes standard mathematical Fibonacci retracement levels.
    Invalidation: swing_high <= swing_low raises ValueError.
    """
    if swing_high <= swing_low:
        raise ValueError(f"Swing high ({swing_high}) must be strictly greater than swing low ({swing_low})")

    diff = swing_high - swing_low
    return {
        "0.000": round(swing_high, 4),
        "0.382": round(swing_high - (0.382 * diff), 4),
        "0.500": round(swing_high - (0.500 * diff), 4),
        "0.618": round(swing_high - (0.618 * diff), 4),
        "0.786": round(swing_high - (0.786 * diff), 4),
        "1.000": round(swing_low, 4),
    }


def detect_order_blocks(
    opens: List[float],
    highs: List[float],
    lows: List[float],
    closes: List[float],
    atr_values: List[float],
    displacement_multiplier: float = 1.5,
) -> List[OrderBlock]:
    """
    Deterministic Order Block detection:
    - Bullish Order Block: The last down-close candle (close < open) before an upward displacement
      where subsequent 2-bar move exceeds displacement_multiplier * ATR.
    - Invalidation: Candle close penetrates below the bottom of the Order Block.
    """
    n = len(closes)
    order_blocks = []

    for i in range(1, n - 2):
        atr = atr_values[i] if i < len(atr_values) else (closes[i] * 0.015)
        # Bullish OB check
        is_down_candle = closes[i] < opens[i]
        displacement = closes[i + 2] - closes[i]

        if is_down_candle and displacement >= (atr * displacement_multiplier):
            ob = OrderBlock(
                index=i,
                confirmed_index=i + 2,
                top_price=highs[i],
                bottom_price=lows[i],
                block_type=StructureType.ORDER_BLOCK_BULLISH,
                invalidation_price=lows[i],
            )
            # Check subsequent bars for mitigation/invalidation
            for j in range(i + 3, n):
                if closes[j] < ob.invalidation_price:
                    ob.is_mitigated = True
                    break
            if not ob.is_mitigated:
                order_blocks.append(ob)

    return order_blocks


def filter_confirmed_order_blocks(
    order_blocks: List[OrderBlock],
    current_index: int,
) -> List[OrderBlock]:
    """Strictly filters out any order blocks whose confirmation index is in the future (> current_index)."""
    return [ob for ob in order_blocks if ob.confirmed_index <= current_index]

