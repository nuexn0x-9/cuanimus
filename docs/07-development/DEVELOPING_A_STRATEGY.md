# Developer Guide: Building a Strategy Plugin

**Document Version:** 1.0.0  
**Target Audience:** Quantitative Researchers & Community Contributors  
**Status:** COMPLETE  
**Date:** October 2026  

---

## 1. Overview

In CUANIMUS, strategies are pure mathematical and algorithmic signal generators. A strategy does **not** handle order execution, position sizing, exchange websockets, database persistence, or risk management.

Your strategy consumes pre-calculated, causal candle features and emits an intention ([`TradeIntent`](file:///home/zero/ai-gemini-futures-bot/cuanimus/common/types.py)).

---

## 2. Step-by-Step Implementation

### Step 1: Create Strategy Class
Create a new file in `cuanimus/strategy/` or in your custom workspace:

```python
from datetime import datetime, timezone
from typing import Dict, Any

from cuanimus.strategy.base import BaseStrategy
from cuanimus.common.types import TradeIntent, SignalDirection, RegimeContext, MarketRegimeType

class SupertrendStrategy(BaseStrategy):
    def __init__(self, multiplier: float = 3.0, period: int = 10):
        self.multiplier = multiplier
        self.period = period

    @property
    def strategy_id(self) -> str:
        return "supertrend_v1"

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
        now_dt = datetime.now(timezone.utc)

        # 1. Check regime filter (e.g. abstain during uncertain chop)
        if regime.regime == MarketRegimeType.UNCERTAIN:
            return TradeIntent(
                intent_id=f"INT_HOLD_{symbol}",
                symbol=symbol,
                direction=SignalDirection.HOLD,
                timestamp=now_dt,
                strategy_id=self.strategy_id,
                entry_price_target=close_p,
            )

        # 2. Evaluate strategy signals
        ema_fast = features.get("ema20", close_p)
        ema_slow = features.get("ema50", close_p)

        is_bullish = close_p > ema_fast and ema_fast > ema_slow
        is_bearish = close_p < ema_fast and ema_fast < ema_slow

        if is_bullish:
            return TradeIntent(
                intent_id=f"INT_LONG_{symbol}",
                symbol=symbol,
                direction=SignalDirection.LONG,
                timestamp=now_dt,
                strategy_id=self.strategy_id,
                entry_price_target=close_p,
                confidence=0.80,
                suggested_stop_loss=round(close_p * 0.985, 4),
            )
        elif is_bearish:
            return TradeIntent(
                intent_id=f"INT_SHORT_{symbol}",
                symbol=symbol,
                direction=SignalDirection.SHORT,
                timestamp=now_dt,
                strategy_id=self.strategy_id,
                entry_price_target=close_p,
                confidence=0.80,
                suggested_stop_loss=round(close_p * 1.015, 4),
            )

        return TradeIntent(
            intent_id=f"INT_HOLD_{symbol}",
            symbol=symbol,
            direction=SignalDirection.HOLD,
            timestamp=now_dt,
            strategy_id=self.strategy_id,
            entry_price_target=close_p,
        )
```

---

### Step 2: Register Strategy Plugin
Register the plugin with metadata and parameter specifications:

```python
from cuanimus.strategy.registry import StrategyRegistry, StrategyMetadata
from cuanimus.config.fields import ConfigField

StrategyRegistry.register(
    strategy_id="supertrend_v1",
    strategy_class=SupertrendStrategy,
    metadata=StrategyMetadata(
        strategy_id="supertrend_v1",
        name="Supertrend Indicator Strategy",
        version="1.0.0",
        description="Trend following based on Supertrend bands and EMA confirmation",
        author="Your Name",
        supported_markets=["futures"],
        supported_timeframes=["15m", "1h"],
        long_enabled=True,
        short_enabled=True,
        parameter_specs={
            "multiplier": ConfigField(
                name="multiplier", field_type="float", default=3.0,
                minimum=1.0, maximum=10.0, description="ATR multiplier"
            ),
            "period": ConfigField(
                name="period", field_type="int", default=10,
                minimum=3, maximum=50, description="Lookback period"
            ),
        }
    )
)
```

---

### Step 3: Add Strategy Configuration YAML
Create `config/strategies/supertrend_v1.yaml`:

```yaml
strategy:
  strategy_id: supertrend_v1
  name: "Supertrend Indicator Strategy"
  version: "1.0.0"
  long_enabled: true
  short_enabled: true
  parameters:
    multiplier: 3.0
    period: 10
```

---

### Step 4: Validate and Test
```bash
# Verify strategy appears in registered list:
./cuanimus-cli strategy list

# Inspect strategy metadata:
./cuanimus-cli strategy inspect supertrend_v1

# Test configuration validation:
./cuanimus-cli config validate --strategy supertrend_v1

# Run historical backtest:
./cuanimus-cli backtest --strategy supertrend_v1 --profile balanced
```
