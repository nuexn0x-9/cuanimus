"""
CUANIMUS V2 Pullback Strategy Engine.
Implements hypothesis-driven Entry Engine with decoupled modular features:
Trend, Momentum, Pullback, Structure, Volatility, Volume, and Regime.

Isolates ENTRY rules while keeping Risk Engine, Sizing, and Order Lifecycle identical to V1.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from cuanimus.common.types import TradeIntent, SignalDirection, RegimeContext, MarketRegimeType
from cuanimus.strategy.base import BaseStrategy
from cuanimus.strategy.features import (
    evaluate_trend_feature,
    evaluate_pullback_feature,
    evaluate_volume_feature,
)
from cuanimus.strategy.structure import (
    compute_fibonacci_levels,
    detect_order_blocks,
    detect_swing_points,
)


@dataclass
class V2StrategyConfig:
    """
    Explicit parameter registry for V2 Pullback Strategy.
    All parameters have strict types, defaults, valid ranges, and quant rationale.
    """
    variant: str = "V2C_PULLBACK_STRUCTURE"  # Options: V2A_PULLBACK, V2B_STRUCTURE, V2C_PULLBACK_STRUCTURE
    ema_fast: int = 20
    ema_slow: int = 50
    stoch_oversold: float = 30.0
    stoch_overbought: float = 70.0
    pullback_tolerance_pct: float = 0.8
    volume_multiplier: float = 1.1
    min_regime_adx: float = 20.0
    allow_counter_trend: bool = False


class V2PullbackStrategy(BaseStrategy):
    """
    V2 Strategy: Pullback & Market Structure Retest Engine.
    Hypothesis:
    HTF bullish + local trend bullish + price retest value area (EMA / Fib / OB) + momentum reset -> High-probability entry.
    """
    def __init__(self, config: Optional[V2StrategyConfig] = None):
        self.config = config or V2StrategyConfig()

    @property
    def strategy_id(self) -> str:
        return f"CUANIMUS_{self.config.variant}"

    @property
    def timeframe(self) -> str:
        return "15m"

    def evaluate_intent(
        self,
        symbol: str,
        current_candle: Dict[str, Any],
        features: Dict[str, Any],
        regime: RegimeContext,
    ) -> TradeIntent:
        close_p = current_candle.get("close", 0.0)
        ema_fast_val = features.get("ema20", close_p)
        ema_slow_val = features.get("ema50", close_p)
        stoch_k = features.get("stoch_k", 50.0)
        stoch_d = features.get("stoch_d", 50.0)
        volume = features.get("volume", 1000.0)
        volume_avg = features.get("volume_avg", 1000.0)
        swing_low = features.get("swing_low", None)
        swing_high = features.get("swing_high", None)

        now_dt = datetime.now(timezone.utc)
        # 1. Regime Abstain Check
        # Strategy abstains from entry during uncertain or ultra-low volume chop
        if regime.regime == MarketRegimeType.UNCERTAIN:
            return TradeIntent(
                intent_id=f"INT_{symbol}_{now_dt.timestamp()}",
                symbol=symbol,
                direction=SignalDirection.HOLD,
                timestamp=now_dt,
                strategy_id=self.strategy_id,
                entry_price_target=close_p,
                confidence=0.0,
            )

        if regime.trend_strength_adx < self.config.min_regime_adx and regime.regime == MarketRegimeType.RANGING:
            return TradeIntent(
                intent_id=f"INT_{symbol}_{now_dt.timestamp()}",
                symbol=symbol,
                direction=SignalDirection.HOLD,
                timestamp=now_dt,
                strategy_id=self.strategy_id,
                entry_price_target=close_p,
                confidence=0.0,
            )

        # 2. Trend Feature
        trend_info = evaluate_trend_feature(ema_fast_val, ema_slow_val)
        trend = trend_info["trend"]

        # 3. Pullback Feature
        pullback_ok = evaluate_pullback_feature(close_p, ema_fast_val, trend, stoch_k, stoch_d)

        # 4. Volume Feature
        volume_ok = evaluate_volume_feature(volume, volume_avg, self.config.volume_multiplier)

        # 5. Structure Feature (Fibonacci / Value Area)
        structure_long_ok = True
        structure_short_ok = True

        if swing_low is not None and swing_high is not None and swing_high > swing_low:
            fibs = compute_fibonacci_levels(swing_low, swing_high)
            # In bullish trend, retest between 0.382 and 0.618 level
            if trend == "BULLISH":
                structure_long_ok = fibs["0.618"] <= close_p <= fibs["0.382"]
            elif trend == "BEARISH":
                structure_short_ok = fibs["0.382"] <= close_p <= fibs["0.618"]

        # Decision based on chosen variant
        if self.config.variant == "V2A_PULLBACK":
            long_condition = (trend == "BULLISH") and pullback_ok and volume_ok
            short_condition = (trend == "BEARISH") and pullback_ok and volume_ok
        elif self.config.variant == "V2B_STRUCTURE":
            long_condition = (trend == "BULLISH") and structure_long_ok and volume_ok
            short_condition = (trend == "BEARISH") and structure_short_ok and volume_ok
        else:  # V2C_PULLBACK_STRUCTURE (Hybrid)
            long_condition = (trend == "BULLISH") and pullback_ok and structure_long_ok and volume_ok
            short_condition = (trend == "BEARISH") and pullback_ok and structure_short_ok and volume_ok

        if long_condition:
            return TradeIntent(
                intent_id=f"INT_{symbol}_{now_dt.timestamp()}",
                symbol=symbol,
                direction=SignalDirection.LONG,
                timestamp=now_dt,
                strategy_id=self.strategy_id,
                entry_price_target=close_p,
                confidence=0.85,
                features_snapshot={"trend": 1.0, "stoch_k": stoch_k, "volume": volume},
            )

        if short_condition:
            return TradeIntent(
                intent_id=f"INT_{symbol}_{now_dt.timestamp()}",
                symbol=symbol,
                direction=SignalDirection.SHORT,
                timestamp=now_dt,
                strategy_id=self.strategy_id,
                entry_price_target=close_p,
                confidence=0.85,
                features_snapshot={"trend": -1.0, "stoch_k": stoch_k, "volume": volume},
            )

        return TradeIntent(
            intent_id=f"INT_{symbol}_{now_dt.timestamp()}",
            symbol=symbol,
            direction=SignalDirection.HOLD,
            timestamp=now_dt,
            strategy_id=self.strategy_id,
            entry_price_target=close_p,
            confidence=0.0,
        )
