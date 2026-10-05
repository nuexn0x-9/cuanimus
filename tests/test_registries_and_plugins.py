"""
Unit & Regression Tests for CUANIMUS Strategy, Risk, and AI Registries.
Tests:
- Strategy plugin registration, retrieval, and metadata inspection
- Duplicate strategy ID rejection
- Strategy extension contract enforcement (pure intent, no exchange order submission)
- Risk profile registry and engine builder
- AI Provider registry: deterministic fallback when disabled, provider routing when enabled
"""
import unittest
from datetime import datetime, timezone

from cuanimus.strategy.base import BaseStrategy
from cuanimus.strategy.registry import StrategyRegistry, StrategyMetadata
from cuanimus.common.types import TradeIntent, SignalDirection, RegimeContext, MarketRegimeType
from cuanimus.risk.registry import RiskProfileRegistry
from cuanimus.risk.engine import RiskEngine
from cuanimus.ai.registry import AIProviderRegistry, DisabledAIProvider
from cuanimus.ai.provider import MockAIProvider
from cuanimus.ai.contract import AIServiceStatus
from cuanimus.config.models import AIConfig


class DummyCommunityStrategy(BaseStrategy):
    """A test community strategy plugin."""
    @property
    def strategy_id(self) -> str:
        return "community_breakout"

    @property
    def timeframe(self) -> str:
        return "15m"

    def evaluate_intent(self, symbol, current_candle, features, regime):
        return TradeIntent(
            intent_id="COMM_INT_1",
            symbol=symbol,
            direction=SignalDirection.LONG,
            timestamp=datetime.now(timezone.utc),
            strategy_id=self.strategy_id,
            entry_price_target=current_candle.get("close", 100.0),
        )


class TestRegistriesAndPlugins(unittest.TestCase):
    def test_strategy_plugin_registration_and_retrieval(self):
        """Custom strategy plugins can be registered and retrieved dynamically."""
        meta = StrategyMetadata(
            strategy_id="community_breakout",
            name="Community Breakout Strategy",
            version="1.0.0",
            description="Open-source breakout plugin",
            author="Community Contributor",
        )
        StrategyRegistry.register(
            strategy_id="community_breakout",
            strategy_class=DummyCommunityStrategy,
            metadata=meta,
            overwrite=True,
        )

        strat_instance = StrategyRegistry.get("community_breakout")
        self.assertIsInstance(strat_instance, DummyCommunityStrategy)
        self.assertEqual(strat_instance.strategy_id, "community_breakout")

        retrieved_meta = StrategyRegistry.get_metadata("community_breakout")
        self.assertEqual(retrieved_meta.author, "Community Contributor")

    def test_duplicate_strategy_id_rejection(self):
        """Registering a strategy with an already registered ID without overwrite raises ValueError."""
        meta = StrategyMetadata(
            strategy_id="baseline_v0",
            name="Duplicate Baseline",
            version="1.0.0",
            description="Duplicate attempt",
        )
        with self.assertRaises(ValueError):
            StrategyRegistry.register(
                strategy_id="baseline_v0",
                strategy_class=DummyCommunityStrategy,
                metadata=meta,
                overwrite=False,
            )

    def test_strategy_extension_contract_isolation(self):
        """Strategy evaluates MarketSnapshot and produces TradeIntent without exchange access."""
        strat = StrategyRegistry.get("hybrid_v2c")
        intent = strat.evaluate_intent(
            symbol="ETH/USDT:USDT",
            current_candle={"close": 2000.0},
            features={"ema20": 2005.0, "ema50": 1950.0, "stoch_k": 25.0, "stoch_d": 25.0, "volume": 5000.0, "volume_avg": 4000.0},
            regime=RegimeContext(
                regime=MarketRegimeType.TRENDING_BULL,
                trend_strength_adx=30.0,
                volatility_atr=20.0,
                volatility_percentile=50.0,
                htf_bias="BULLISH",
                confidence=80.0,
            ),
        )
        self.assertIsInstance(intent, TradeIntent)
        self.assertIn(intent.direction, (SignalDirection.LONG, SignalDirection.HOLD, SignalDirection.SHORT))
        # Ensure strategy object has no direct order dispatch methods
        self.assertFalse(hasattr(strat, "submit_exchange_order"))
        self.assertFalse(hasattr(strat, "cancel_exchange_order"))

    def test_risk_profile_registry_and_engine_factory(self):
        """Risk profiles instantiate functional RiskEngine instances with correct limits."""
        profiles = RiskProfileRegistry.list_profiles()
        self.assertGreaterEqual(len(profiles), 3)

        bal_cfg = RiskProfileRegistry.get_config("balanced")
        self.assertEqual(bal_cfg.risk_per_trade_pct, 1.0)
        self.assertEqual(bal_cfg.max_leverage, 5.0)

        engine = RiskProfileRegistry.build_engine(bal_cfg)
        self.assertIsInstance(engine, RiskEngine)
        self.assertEqual(engine.base_risk_pct, 1.0)
        self.assertEqual(engine.max_leverage, 5.0)

    def test_ai_provider_registry_deterministic_fallback(self):
        """When AI is disabled, registry returns DisabledAIProvider with pure deterministic status."""
        cfg_disabled = AIConfig(enabled=False)
        provider = AIProviderRegistry.get_provider(cfg_disabled)
        self.assertIsInstance(provider, DisabledAIProvider)

        contract = provider.evaluate_market_intelligence("BTC/USDT", "15m", {})
        self.assertEqual(contract.status, AIServiceStatus.DISABLED)
        self.assertEqual(contract.confidence_score, 0.0)

    def test_ai_provider_registry_routes_to_mock_when_enabled(self):
        """When AI is enabled with provider 'mock', MockAIProvider is instantiated."""
        cfg_mock = AIConfig(enabled=True, provider="mock")
        provider = AIProviderRegistry.get_provider(cfg_mock)
        self.assertIsInstance(provider, MockAIProvider)

        contract = provider.evaluate_market_intelligence("BTC/USDT", "15m", {})
        self.assertEqual(contract.status, AIServiceStatus.HEALTHY)


if __name__ == "__main__":
    unittest.main()
