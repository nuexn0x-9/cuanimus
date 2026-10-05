# CUANIMUS Plugin Architecture & Extension Contracts

**Document Version:** 1.0.0  
**Phase:** 6C Extension Platform  
**Status:** IMPLEMENTED & VERIFIED  
**Date:** October 2026  

---

## 1. Executive Summary

CUANIMUS is engineered so open-source contributors can add **Strategies, Risk Models, AI Intelligence Providers, and Exchange Adapters** without understanding or modifying the trading engine core (`cuanimus/execution/`, `cuanimus/risk/engine.py`, `cuanimus/validation/`).

---

## 2. Extension Point 1: Strategy Plugins

Strategies are pure signal generators that evaluate market conditions and emit intention signals (`TradeIntent`).

### 2.1 Extension Contract
```
[Market Candlestick Data]
           │
           ▼
[Feature Engine (Causal Indicators)]
           │
           ▼
[Strategy Plugin (evaluate_intent)]
           │
           ▼
     [TradeIntent]
           │
           ▼
     [Risk Engine]  <--- Validates capital, drawdown, cooldown, sizing
           │
           ▼
[Order Lifecycle FSM]
```

### 2.2 Strict Invariants for Strategy Plugins
Strategy plugins **CANNOT**:
1. Directly submit, alter, or cancel orders on an exchange.
2. Bypass, relax, or override Risk Engine sizing or drawdown limits.
3. Dictate final leverage multiplier (leverage is determined by the Risk Engine).
4. Deactivate emergency stops or manual kill switches.

### 2.3 Registering a Custom Strategy
```python
from cuanimus.strategy.base import BaseStrategy
from cuanimus.strategy.registry import StrategyRegistry, StrategyMetadata
from cuanimus.common.types import TradeIntent, SignalDirection

class BreakoutStrategy(BaseStrategy):
    @property
    def strategy_id(self) -> str:
        return "custom_breakout"

    @property
    def timeframe(self) -> str:
        return "15m"

    def evaluate_intent(self, symbol, current_candle, features, regime) -> TradeIntent:
        # Strategy calculation
        return TradeIntent(
            intent_id=f"INT_{symbol}_{current_candle['date']}",
            symbol=symbol,
            direction=SignalDirection.LONG,
            timestamp=current_candle["date"],
            strategy_id=self.strategy_id,
            entry_price_target=current_candle["close"],
        )

# Register with platform
StrategyRegistry.register(
    strategy_id="custom_breakout",
    strategy_class=BreakoutStrategy,
    metadata=StrategyMetadata(
        strategy_id="custom_breakout",
        name="Custom 15m Breakout",
        version="1.0.0",
        description="Volatility breakout on 15m candles",
        author="Contributor Name",
    )
)
```

---

## 3. Extension Point 2: Risk Profile Registry

The Risk Engine operates as an independent authority. Operators can configure custom risk profiles or register custom risk rules through [`RiskProfileRegistry`](file:///home/zero/ai-gemini-futures-bot/cuanimus/risk/registry.py):

```python
from cuanimus.risk.registry import RiskProfileRegistry
from cuanimus.config.models import RiskConfig

RiskProfileRegistry.register(
    "micro_risk",
    RiskConfig(
        profile_name="micro_risk",
        risk_per_trade_pct=0.25,
        max_leverage=2.0,
        max_daily_loss_pct=1.0,
        max_drawdown_pct=5.0,
    )
)
```

---

## 4. Extension Point 3: AI Intelligence Providers

AI providers operate strictly as **optional sidecar advisors**. When AI is disabled (`enabled: false`), the core engine utilizes [`DisabledAIProvider`](file:///home/zero/ai-gemini-futures-bot/cuanimus/ai/registry.py) and executes with 100% deterministic strategy logic.

To integrate a new LLM provider (e.g. Anthropic Claude, DeepSeek):
1. Inherit from [`AIProvider`](file:///home/zero/ai-gemini-futures-bot/cuanimus/ai/provider.py).
2. Implement `evaluate_market_intelligence(symbol, timeframe, technical_summary, ttl_minutes) -> AIDecisionContract`.
3. Register in `AIProviderRegistry.register("deepseek", DeepSeekProvider)`.
