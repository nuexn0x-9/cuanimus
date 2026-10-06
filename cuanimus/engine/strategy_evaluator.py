"""
CUANIMUS Mode A — Strategy Autotrade Evaluator.
Evaluates template strategies from StrategyRegistry using strictly closed Binance candles.
Enforces zero future leakage and causal closed-bar boundary.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

from cuanimus.common.types import TradeIntent, SignalDirection, RegimeContext, MarketRegimeType
from cuanimus.strategy.registry import StrategyRegistry
from cuanimus.strategy.v2_pullback import V2PullbackStrategy, V2StrategyConfig
from cuanimus.strategy.features import (
    compute_closed_candle_atr,
    compute_closed_candle_rsi,
    compute_closed_candle_adx,
)
from cuanimus.engine.models import TradingProfile

logger = logging.getLogger(__name__)


class StrategyEvaluator:
    """Evaluates Mode A (Strategy Template Autotrade) against closed market bars."""

    @staticmethod
    def extract_features(closed_candles: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Computes technical features strictly from closed historical bars.
        closed_candles must contain at least 20 historical bars.
        """
        if not closed_candles:
            return {}

        closes = [float(c["close"]) for c in closed_candles]
        highs = [float(c["high"]) for c in closed_candles]
        lows = [float(c["low"]) for c in closed_candles]
        volumes = [float(c["volume"]) for c in closed_candles]

        last_close = closes[-1]

        # EMA 20
        period_fast = 20
        if len(closes) >= period_fast:
            multiplier = 2.0 / (period_fast + 1)
            ema20 = sum(closes[:period_fast]) / period_fast
            for price in closes[period_fast:]:
                ema20 = (price - ema20) * multiplier + ema20
        else:
            ema20 = last_close

        # EMA 50
        period_slow = 50
        if len(closes) >= period_slow:
            multiplier = 2.0 / (period_slow + 1)
            ema50 = sum(closes[:period_slow]) / period_slow
            for price in closes[period_slow:]:
                ema50 = (price - ema50) * multiplier + ema50
        elif len(closes) >= 20:
            ema50 = sum(closes[:20]) / 20.0
        else:
            ema50 = last_close

        # Stochastic (14, 3)
        stoch_period = 14
        if len(closes) >= stoch_period:
            recent_lows = lows[-stoch_period:]
            recent_highs = highs[-stoch_period:]
            lowest_low = min(recent_lows)
            highest_high = max(recent_highs)
            stoch_k = ((last_close - lowest_low) / (highest_high - lowest_low) * 100.0) if highest_high > lowest_low else 50.0
        else:
            stoch_k = 50.0
        stoch_d = stoch_k  # Smoothing approximation

        # Volume Average
        vol_window = min(len(volumes), 20)
        volume_avg = (sum(volumes[-vol_window:]) / vol_window) if vol_window > 0 else volumes[-1]

        # ATR
        try:
            atr = compute_closed_candle_atr(highs, lows, closes, period=14)
        except Exception:
            atr = round(last_close * 0.015, 4)

        # ADX
        try:
            adx = compute_closed_candle_adx(highs, lows, closes, period=14)
        except Exception:
            adx = 22.0

        return {
            "close": last_close,
            "ema20": round(ema20, 6),
            "ema50": round(ema50, 6),
            "stoch_k": round(stoch_k, 2),
            "stoch_d": round(stoch_d, 2),
            "volume": volumes[-1],
            "volume_avg": round(volume_avg, 2),
            "atr": atr,
            "adx": adx,
        }

    @staticmethod
    def classify_regime(features: Dict[str, Any]) -> RegimeContext:
        """Classifies market regime causal context from closed candle indicators."""
        close_p = features.get("close", 0.0)
        ema20 = features.get("ema20", close_p)
        ema50 = features.get("ema50", close_p)
        adx = features.get("adx", 20.0)
        atr = features.get("atr", 10.0)

        is_bull = close_p > ema20 and ema20 > ema50
        is_bear = close_p < ema20 and ema20 < ema50

        if is_bull and adx >= 20:
            reg = MarketRegimeType.TRENDING_BULL
            htf = "BULLISH"
            conf = 85.0
        elif is_bear and adx >= 20:
            reg = MarketRegimeType.TRENDING_BEAR
            htf = "BEARISH"
            conf = 80.0
        elif adx < 18:
            reg = MarketRegimeType.COMPRESSION
            htf = "NEUTRAL"
            conf = 70.0
        else:
            reg = MarketRegimeType.RANGING
            htf = "NEUTRAL"
            conf = 60.0

        return RegimeContext(
            regime=reg,
            trend_strength_adx=adx,
            volatility_atr=atr,
            volatility_percentile=50.0,
            htf_bias=htf,
            confidence=conf,
        )

    def evaluate(
        self,
        profile: TradingProfile,
        closed_candles: List[Dict[str, Any]],
        current_market_price: float,
    ) -> TradeIntent:
        """
        Executes Mode A strategy evaluation.
        Returns a normalized TradeIntent (Direction: LONG, SHORT, or HOLD).
        """
        now = datetime.now(timezone.utc)
        symbol = profile.symbol

        if len(closed_candles) < 20:
            return TradeIntent(
                intent_id=f"INT_{profile.profile_id}_{now.timestamp()}",
                symbol=symbol,
                direction=SignalDirection.HOLD,
                timestamp=now,
                strategy_id=profile.strategy_id or "hybrid_v2c",
                entry_price_target=current_market_price,
                confidence=0.0,
            )

        features = self.extract_features(closed_candles)
        regime = self.classify_regime(features)
        last_candle = closed_candles[-1]

        strat_id = profile.strategy_id or "hybrid_v2c"

        # Obtain strategy from StrategyRegistry
        try:
            strat = StrategyRegistry.get(strat_id)
        except Exception:
            # Fallback to V2PullbackStrategy with profile params
            params = profile.strategy_params or {}
            cfg = V2StrategyConfig(
                variant="V2C_PULLBACK_STRUCTURE",
                ema_fast=int(params.get("ema_fast", 20)),
                ema_slow=int(params.get("ema_slow", 50)),
                stoch_oversold=float(params.get("stoch_oversold", 30.0)),
                stoch_overbought=float(params.get("stoch_overbought", 70.0)),
                pullback_tolerance_pct=float(params.get("pullback_tolerance_pct", 0.8)),
                volume_multiplier=float(params.get("volume_multiplier", 1.1)),
                min_regime_adx=float(params.get("min_regime_adx", 20.0)),
            )
            strat = V2PullbackStrategy(config=cfg)

        # Run strategy evaluation
        intent = strat.evaluate_intent(
            symbol=symbol,
            current_candle=last_candle,
            features=features,
            regime=regime,
        )

        # Override entry price target with current market price if filled immediately
        if intent.direction != SignalDirection.HOLD:
            intent.entry_price_target = current_market_price
            # Configure SL / TP according to profile overrides if set
            sl_pct = profile.stop_loss_pct / 100.0
            tp_pct = profile.take_profit_pct / 100.0
            if intent.direction == SignalDirection.LONG:
                intent.suggested_stop_loss = round(current_market_price * (1.0 - sl_pct), 6)
                intent.suggested_take_profit = round(current_market_price * (1.0 + tp_pct), 6)
            elif intent.direction == SignalDirection.SHORT:
                intent.suggested_stop_loss = round(current_market_price * (1.0 + sl_pct), 6)
                intent.suggested_take_profit = round(current_market_price * (1.0 - tp_pct), 6)

        return intent
