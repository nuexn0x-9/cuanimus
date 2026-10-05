"""
CUANIMUS Strategy Plugin Registry & Extension Contract.
Decouples strategy algorithms from Core Engine, Risk Engine, Execution FSM, and Exchange.

Extension Contract:
1. Strategy plugins inherit from BaseStrategy.
2. Strategy consumes MarketSnapshot / Features / RegimeContext and outputs TradeIntent.
3. Strategy CANNOT:
   - Submit orders directly to exchange.
   - Bypass or override Risk Engine limits.
   - Force final position leverage.
   - Deactivate kill switches or emergency stops.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Type, Optional, List, Tuple
import logging

from cuanimus.strategy.base import BaseStrategy
from cuanimus.strategy.baseline_v0 import BaselineV0Strategy
from cuanimus.strategy.v2_pullback import V2PullbackStrategy, V2StrategyConfig
from cuanimus.config.fields import ConfigField

logger = logging.getLogger(__name__)


@dataclass
class StrategyMetadata:
    strategy_id: str
    name: str
    version: str
    description: str
    author: str = "CUANIMUS Core"
    supported_markets: List[str] = field(default_factory=lambda: ["futures", "spot"])
    supported_timeframes: List[str] = field(default_factory=lambda: ["1m", "5m", "15m", "1h", "4h"])
    long_enabled: bool = True
    short_enabled: bool = False
    parameter_specs: Dict[str, ConfigField] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "supported_markets": self.supported_markets,
            "supported_timeframes": self.supported_timeframes,
            "long_enabled": self.long_enabled,
            "short_enabled": self.short_enabled,
            "parameter_specs": {k: v.to_schema_dict() for k, v in self.parameter_specs.items()},
        }


class StrategyRegistry:
    """Central registry for strategy plugins."""
    _registry: Dict[str, Tuple[Type[BaseStrategy], StrategyMetadata, Dict[str, Any]]] = {}

    @classmethod
    def register(
        cls,
        strategy_id: str,
        strategy_class: Type[BaseStrategy],
        metadata: StrategyMetadata,
        default_init_kwargs: Optional[Dict[str, Any]] = None,
        overwrite: bool = False,
    ):
        """Registers a new strategy plugin."""
        if not issubclass(strategy_class, BaseStrategy):
            raise TypeError(f"Strategy class '{strategy_class.__name__}' must inherit from BaseStrategy")

        if strategy_id in cls._registry and not overwrite:
            raise ValueError(f"Strategy with ID '{strategy_id}' is already registered! Duplicate IDs are rejected.")

        cls._registry[strategy_id] = (strategy_class, metadata, default_init_kwargs or {})
        logger.debug(f"Strategy plugin registered: {strategy_id} ({metadata.name} v{metadata.version})")

    @classmethod
    def get(cls, strategy_id: str, config_parameters: Optional[Dict[str, Any]] = None) -> BaseStrategy:
        """Instantiates a registered strategy plugin with optional parameter overrides."""
        if strategy_id not in cls._registry:
            raise KeyError(f"Strategy '{strategy_id}' not found in registry. Registered: {list(cls._registry.keys())}")

        strat_cls, metadata, default_kwargs = cls._registry[strategy_id]
        merged_kwargs = dict(default_kwargs)
        if config_parameters:
            merged_kwargs.update(config_parameters)

        try:
            return strat_cls(**merged_kwargs)
        except TypeError:
            # Fallback if strategy takes no kwargs
            return strat_cls()

    @classmethod
    def get_metadata(cls, strategy_id: str) -> StrategyMetadata:
        """Retrieves metadata for a registered strategy."""
        if strategy_id not in cls._registry:
            raise KeyError(f"Strategy '{strategy_id}' not found in registry.")
        return cls._registry[strategy_id][1]

    @classmethod
    def list_strategies(cls) -> List[Dict[str, Any]]:
        """Lists all registered strategies with summaries."""
        results = []
        for s_id, (_, meta, _) in cls._registry.items():
            results.append(meta.to_dict())
        return results

    @classmethod
    def clear(cls):
        """Resets the registry (useful for testing)."""
        cls._registry.clear()


# Helper wrapper for V2 Pullback variants
class _V2APullbackWrapper(V2PullbackStrategy):
    def __init__(self, **kwargs):
        cfg = V2StrategyConfig(variant="V2A_PULLBACK", **kwargs)
        super().__init__(config=cfg)


class _V2BStructureWrapper(V2PullbackStrategy):
    def __init__(self, **kwargs):
        cfg = V2StrategyConfig(variant="V2B_STRUCTURE", **kwargs)
        super().__init__(config=cfg)


class _V2CHybridWrapper(V2PullbackStrategy):
    def __init__(self, **kwargs):
        cfg = V2StrategyConfig(variant="V2C_PULLBACK_STRUCTURE", **kwargs)
        super().__init__(config=cfg)


# Register Built-in CUANIMUS Strategies
def register_builtin_strategies():
    # 1. Baseline V0
    StrategyRegistry.register(
        strategy_id="baseline_v0",
        strategy_class=BaselineV0Strategy,
        metadata=StrategyMetadata(
            strategy_id="baseline_v0",
            name="Baseline V0 Sniper Trend",
            version="1.0.0",
            description="Legacy dual EMA trend with RSI and ADX momentum triggers",
            long_enabled=True,
            short_enabled=True,
        ),
        overwrite=True,
    )

    # 2. V1 ATR Stop
    StrategyRegistry.register(
        strategy_id="atr_v1",
        strategy_class=BaselineV0Strategy,
        metadata=StrategyMetadata(
            strategy_id="atr_v1",
            name="V1 Dynamic ATR Stop Strategy",
            version="1.1.0",
            description="Baseline V0 entries with dynamic volatility-adjusted ATR stop loss",
            long_enabled=True,
            short_enabled=True,
        ),
        overwrite=True,
    )

    # 3. V2A Pullback
    StrategyRegistry.register(
        strategy_id="pullback_v2a",
        strategy_class=_V2APullbackWrapper,
        metadata=StrategyMetadata(
            strategy_id="pullback_v2a",
            name="V2A Pullback & Stochastic Reset",
            version="2.0.0",
            description="Trend continuation entry upon shallow retest of EMA20 with Stochastic reset",
            long_enabled=True,
            short_enabled=True,
        ),
        overwrite=True,
    )

    # 4. V2B Structure
    StrategyRegistry.register(
        strategy_id="structure_v2b",
        strategy_class=_V2BStructureWrapper,
        metadata=StrategyMetadata(
            strategy_id="structure_v2b",
            name="V2B Market Structure & Fibonacci Retest",
            version="2.0.0",
            description="Causal fractal swing detection with Fibonacci golden pocket retest",
            long_enabled=True,
            short_enabled=False,
        ),
        overwrite=True,
    )

    # 5. V2C Hybrid
    StrategyRegistry.register(
        strategy_id="hybrid_v2c",
        strategy_class=_V2CHybridWrapper,
        metadata=StrategyMetadata(
            strategy_id="hybrid_v2c",
            name="V2C Hybrid Pullback & Structure",
            version="2.0.0",
            description="Confluence of EMA20 pullback, Stochastic reset, and unmitigated order block retest",
            long_enabled=True,
            short_enabled=False,
        ),
        overwrite=True,
    )


# Automatically initialize built-in registry
register_builtin_strategies()
