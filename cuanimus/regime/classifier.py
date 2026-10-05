"""
CUANIMUS Quantitative Market Regime Classifier.
"""
from typing import Dict, Any, Optional
from cuanimus.common.types import MarketRegimeType, RegimeContext

class MarketRegimeClassifier:
    def __init__(
        self,
        adx_trend_threshold: float = 25.0,
        adx_ranging_threshold: float = 20.0,
        high_volatility_quantile: float = 90.0,
        low_volatility_quantile: float = 15.0,
    ):
        self.adx_trend_threshold = adx_trend_threshold
        self.adx_ranging_threshold = adx_ranging_threshold
        self.high_volatility_quantile = high_volatility_quantile
        self.low_volatility_quantile = low_volatility_quantile

    def classify(
        self,
        close_price: float,
        adx_1h: float,
        atr_15m: float,
        atr_percentile: float,
        bb_width_percentile: float,
        ema50_1h: float,
        ema200_1h: float,
        ema50_4h: float,
        ema200_4h: float,
        ai_context: Optional[Dict[str, Any]] = None,
    ) -> RegimeContext:
        if atr_percentile >= self.high_volatility_quantile:
            return RegimeContext(
                regime=MarketRegimeType.HIGH_VOLATILITY,
                trend_strength_adx=adx_1h,
                volatility_atr=atr_15m,
                volatility_percentile=atr_percentile,
                htf_bias="VOLATILE_CHOP",
                confidence=85.0,
            )

        if bb_width_percentile <= self.low_volatility_quantile:
            return RegimeContext(
                regime=MarketRegimeType.LOW_VOLATILITY,
                trend_strength_adx=adx_1h,
                volatility_atr=atr_15m,
                volatility_percentile=atr_percentile,
                htf_bias="COMPRESSION",
                confidence=80.0,
            )

        is_trending = adx_1h >= self.adx_trend_threshold
        htf_4h_bull = ema50_4h > ema200_4h
        htf_4h_bear = ema50_4h < ema200_4h
        local_1h_bull = close_price > ema50_1h and ema50_1h > ema200_1h
        local_1h_bear = close_price < ema50_1h and ema50_1h < ema200_1h

        if is_trending and htf_4h_bull and local_1h_bull:
            confidence = min(95.0, 50.0 + (adx_1h - 25.0) * 1.5)
            return RegimeContext(
                regime=MarketRegimeType.TRENDING_BULL,
                trend_strength_adx=adx_1h,
                volatility_atr=atr_15m,
                volatility_percentile=atr_percentile,
                htf_bias="BULLISH",
                confidence=confidence,
            )

        if is_trending and htf_4h_bear and local_1h_bear:
            confidence = min(95.0, 50.0 + (adx_1h - 25.0) * 1.5)
            return RegimeContext(
                regime=MarketRegimeType.TRENDING_BEAR,
                trend_strength_adx=adx_1h,
                volatility_atr=atr_15m,
                volatility_percentile=atr_percentile,
                htf_bias="BEARISH",
                confidence=confidence,
            )

        if adx_1h < self.adx_ranging_threshold:
            return RegimeContext(
                regime=MarketRegimeType.RANGING,
                trend_strength_adx=adx_1h,
                volatility_atr=atr_15m,
                volatility_percentile=atr_percentile,
                htf_bias="SIDEWAYS",
                confidence=75.0,
            )

        return RegimeContext(
            regime=MarketRegimeType.UNCERTAIN,
            trend_strength_adx=adx_1h,
            volatility_atr=atr_15m,
            volatility_percentile=atr_percentile,
            htf_bias="CONFLICTING",
            confidence=40.0,
        )

