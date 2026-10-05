"""
CUANIMUS V0 Baseline Strategy Implementation.
"""
from datetime import datetime
from typing import Dict, Any

from cuanimus.common.types import TradeIntent, SignalDirection, RegimeContext, MarketRegimeType
from cuanimus.strategy.base import BaseStrategy

class BaselineV0Strategy(BaseStrategy):
    @property
    def strategy_id(self) -> str:
        return "V0_BASELINE_SNIPER"

    @property
    def timeframe(self) -> str:
        return "15m"

    def evaluate_intent(
        self,
        symbol: str,
        current_candle: Dict[str, float],
        features: Dict[str, float],
        regime: RegimeContext,
    ) -> TradeIntent:
        now = datetime.utcnow()
        close = current_candle.get("close", 1.0)
        ema20 = features.get("ema20", close)
        ema50 = features.get("ema50", close)
        rsi = features.get("rsi", 50.0)
        adx = features.get("adx", 20.0)
        btc_rsi = features.get("btc_rsi", 50.0)
        eth_rsi = features.get("eth_rsi", 50.0)

        trend_bull = ema20 > (ema50 * 1.003)
        trend_bear = ema20 < (ema50 * 0.997)

        long_cond = (
            regime.regime != MarketRegimeType.TRENDING_BEAR
            and btc_rsi < 70
            and eth_rsi < 70
            and trend_bull
            and rsi > 62
            and adx > 25
        )

        short_cond = (
            regime.regime != MarketRegimeType.TRENDING_BULL
            and btc_rsi > 30
            and eth_rsi > 30
            and trend_bear
            and rsi < 38
            and rsi > 30
            and adx > 25
        )

        if long_cond:
            return TradeIntent(
                intent_id=f"INT_V0_{symbol}_{int(now.timestamp())}",
                symbol=symbol,
                direction=SignalDirection.LONG,
                timestamp=now,
                strategy_id=self.strategy_id,
                entry_price_target=close,
                features_snapshot={"rsi": rsi, "adx": adx, "ema20": ema20, "ema50": ema50},
                suggested_stop_loss=round(close * 0.985, 4),
            )
        elif short_cond:
            return TradeIntent(
                intent_id=f"INT_V0_{symbol}_{int(now.timestamp())}",
                symbol=symbol,
                direction=SignalDirection.SHORT,
                timestamp=now,
                strategy_id=self.strategy_id,
                entry_price_target=close,
                features_snapshot={"rsi": rsi, "adx": adx, "ema20": ema20, "ema50": ema50},
                suggested_stop_loss=round(close * 1.015, 4),
            )

        return TradeIntent(
            intent_id=f"INT_V0_HOLD_{symbol}_{int(now.timestamp())}",
            symbol=symbol,
            direction=SignalDirection.HOLD,
            timestamp=now,
            strategy_id=self.strategy_id,
            entry_price_target=close,
        )

