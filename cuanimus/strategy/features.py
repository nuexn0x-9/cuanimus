"""
CUANIMUS Composable Quantitative Features.
"""
from typing import Dict, Any

def evaluate_trend_feature(ema_fast: float, ema_slow: float, threshold_pct: float = 0.3) -> Dict[str, Any]:
    ratio = (ema_fast - ema_slow) / ema_slow * 100.0
    if ratio > threshold_pct:
        return {"trend": "BULLISH", "strength": ratio}
    elif ratio < -threshold_pct:
        return {"trend": "BEARISH", "strength": abs(ratio)}
    else:
        return {"trend": "FLAT", "strength": abs(ratio)}

def evaluate_pullback_feature(
    close_price: float,
    ema_fast: float,
    trend: str,
    stoch_k: float,
    stoch_d: float
) -> bool:
    if trend == "BULLISH":
        is_near_ema = abs(close_price - ema_fast) / close_price < 0.008
        is_oversold = stoch_k < 30 and stoch_d < 30
        return is_near_ema and is_oversold
    elif trend == "BEARISH":
        is_near_ema = abs(close_price - ema_fast) / close_price < 0.008
        is_overbought = stoch_k > 70 and stoch_d > 70
        return is_near_ema and is_overbought
    return False

def evaluate_volume_feature(volume: float, volume_avg: float, multiplier: float = 1.2) -> bool:
    if volume_avg <= 0:
        return True
    return volume >= (volume_avg * multiplier)


def compute_closed_candle_atr(
    highs: list,
    lows: list,
    closes: list,
    period: int = 14,
) -> float:
    """
    Computes ATR(period) strictly from closed historical candles without lookahead bias.
    Input lists must contain only completed closed candles.
    """
    if len(highs) != len(lows) or len(lows) != len(closes):
        raise ValueError("High, Low, and Close sequences must have identical lengths")
    if len(closes) < period + 1:
        raise ValueError(f"Insufficient history: required {period + 1} closed bars, got {len(closes)}")

    true_ranges = []
    # Calculate TR from index 1 onwards using previous close
    for i in range(1, len(closes)):
        h = highs[i]
        l = lows[i]
        prev_c = closes[i - 1]
        tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
        true_ranges.append(tr)

    # Wilder's Smoothing / RMA over historical true ranges
    atr = sum(true_ranges[:period]) / float(period)
    for tr in true_ranges[period:]:
        atr = ((atr * (period - 1)) + tr) / float(period)

    return round(atr, 6)


def compute_closed_candle_rsi(closes: list, period: int = 14) -> float:
    """Computes RSI(period) strictly from closed candles."""
    if len(closes) < period + 1:
        return 50.0
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0.0 for d in deltas]
    losses = [-d if d < 0 else 0.0 for d in deltas]

    avg_gain = sum(gains[:period]) / float(period)
    avg_loss = sum(losses[:period]) / float(period)

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / float(period)
        avg_loss = (avg_loss * (period - 1) + losses[i]) / float(period)

    if avg_loss == 0.0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return round(100.0 - (100.0 / (1.0 + rs)), 2)


def compute_closed_candle_adx(highs: list, lows: list, closes: list, period: int = 14) -> float:
    """Computes ADX(period) strictly from closed candles."""
    if len(closes) < period * 2:
        return 20.0
    plus_dm = []
    minus_dm = []
    tr = []
    for i in range(1, len(closes)):
        h = highs[i]
        l = lows[i]
        prev_h = highs[i - 1]
        prev_l = lows[i - 1]
        prev_c = closes[i - 1]
        up_move = h - prev_h
        down_move = prev_l - l
        p_dm = up_move if (up_move > down_move and up_move > 0) else 0.0
        m_dm = down_move if (down_move > up_move and down_move > 0) else 0.0
        plus_dm.append(p_dm)
        minus_dm.append(m_dm)
        tr.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))

    atr_w = sum(tr[:period]) / float(period)
    p_dm_w = sum(plus_dm[:period]) / float(period)
    m_dm_w = sum(minus_dm[:period]) / float(period)

    dx_list = []
    for i in range(period, len(tr)):
        atr_w = (atr_w * (period - 1) + tr[i]) / float(period)
        p_dm_w = (p_dm_w * (period - 1) + plus_dm[i]) / float(period)
        m_dm_w = (m_dm_w * (period - 1) + minus_dm[i]) / float(period)
        plus_di = (p_dm_w / atr_w * 100.0) if atr_w > 0 else 0.0
        minus_di = (m_dm_w / atr_w * 100.0) if atr_w > 0 else 0.0
        di_sum = plus_di + minus_di
        dx = (abs(plus_di - minus_di) / di_sum * 100.0) if di_sum > 0 else 0.0
        dx_list.append(dx)

    if len(dx_list) < period:
        return round(dx_list[-1], 2) if dx_list else 20.0
    adx = sum(dx_list[:period]) / float(period)
    for dx in dx_list[period:]:
        adx = (adx * (period - 1) + dx) / float(period)
    return round(adx, 2)



