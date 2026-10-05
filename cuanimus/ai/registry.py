"""
CUANIMUS AI Provider Registry & Decoupled Factory.
Ensures that the trading platform operates with 100% deterministic capability when AI is disabled,
and routes to the appropriate provider (Mock, Gemini, FutureProvider) when enabled.
"""
from typing import Dict, Any, Type, Optional, List
from cuanimus.ai.provider import AIProvider, MockAIProvider, GeminiRestProvider
from cuanimus.ai.contract import AIDecisionContract, AIServiceStatus, AIMacroBias
from cuanimus.config.models import AIConfig
from datetime import datetime, timezone

GeminiAIProvider = GeminiRestProvider


class DisabledAIProvider(AIProvider):
    """Fallback provider when AI intelligence layer is turned OFF in configuration."""
    def evaluate_market_intelligence(
        self,
        symbol: str,
        timeframe: str,
        technical_summary: Dict[str, Any],
        ttl_minutes: int = 15,
    ) -> AIDecisionContract:
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()
        return AIDecisionContract(
            macro_bias=AIMacroBias.NEUTRAL,
            detected_regime="DETERMINISTIC_ONLY",
            confidence_score=0.0,
            context=["AI Intelligence layer is disabled in configuration. Trading with deterministic strategy."],
            timestamp_utc=now_str,
            valid_until_utc=now_str,
            provider_name="DisabledAIProvider",
            model_version="none",
            prompt_version="none",
            latency_ms=0.0,
            status=AIServiceStatus.DISABLED,
            failure_reason="AI_DISABLED_IN_CONFIG",
        )


class AIProviderRegistry:
    """Registry for AI Intelligence providers."""
    _providers: Dict[str, Type[AIProvider]] = {}

    @classmethod
    def register(cls, name: str, provider_cls: Type[AIProvider]):
        cls._providers[name.lower()] = provider_cls

    @classmethod
    def get_provider(cls, config: AIConfig) -> AIProvider:
        """Instantiates provider according to configuration."""
        if not config.enabled:
            return DisabledAIProvider()

        provider_key = config.provider.lower()
        if provider_key not in cls._providers:
            raise KeyError(f"AI provider '{config.provider}' not registered. Available: {list(cls._providers.keys())}")

        prov_cls = cls._providers[provider_key]
        if prov_cls is GeminiAIProvider:
            return GeminiAIProvider(model_name=config.model_name, timeout_seconds=config.timeout_seconds)
        elif prov_cls is MockAIProvider:
            return MockAIProvider()
        return prov_cls()

    @classmethod
    def list_providers(cls) -> List[str]:
        return list(cls._providers.keys())


# Register built-in providers
AIProviderRegistry.register("mock", MockAIProvider)
AIProviderRegistry.register("gemini", GeminiAIProvider)
AIProviderRegistry.register("disabled", DisabledAIProvider)
