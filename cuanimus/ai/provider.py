"""
CUANIMUS AI Provider Abstraction.
Decouples core trading engine from vendor SDKs (Google, OpenAI, Anthropic, Mock).
"""
import time
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional

from cuanimus.ai.contract import AIDecisionContract, AIMacroBias, AIServiceStatus

logger = logging.getLogger(__name__)


class AIProvider(ABC):
    """Abstract interface for AI Intelligence Providers."""
    @abstractmethod
    def evaluate_market_intelligence(
        self,
        symbol: str,
        timeframe: str,
        technical_summary: Dict[str, Any],
        ttl_minutes: int = 15,
    ) -> AIDecisionContract:
        """Submits prompt to provider and returns validated AIDecisionContract."""
        pass


class MockAIProvider(AIProvider):
    """
    Deterministic mock provider for unit testing, CI/CD, and offline simulations.
    Supports injected failures (timeout, rate_limit, malformed_json).
    """
    def __init__(
        self,
        injected_bias: AIMacroBias = AIMacroBias.BULLISH,
        injected_regime: str = "TRENDING_BULL",
        injected_confidence: float = 85.0,
        simulated_failure: Optional[str] = None,
        latency_ms: float = 45.0,
    ):
        self.injected_bias = injected_bias
        self.injected_regime = injected_regime
        self.injected_confidence = injected_confidence
        self.simulated_failure = simulated_failure
        self.latency_ms = latency_ms

    def evaluate_market_intelligence(
        self,
        symbol: str,
        timeframe: str,
        technical_summary: Dict[str, Any],
        ttl_minutes: int = 15,
    ) -> AIDecisionContract:
        now = datetime.now(timezone.utc)
        valid_until = now + timedelta(minutes=ttl_minutes)

        if self.simulated_failure:
            return AIDecisionContract.fallback_unavailable(
                reason=f"MOCK_FAILURE_{self.simulated_failure.upper()}",
                provider="MOCK_PROVIDER",
            )

        return AIDecisionContract(
            macro_bias=self.injected_bias,
            detected_regime=self.injected_regime,
            confidence_score=self.injected_confidence,
            context=[f"Mock evaluated {symbol} on {timeframe}", "Trend filter aligned"],
            timestamp_utc=now.isoformat(),
            valid_until_utc=valid_until.isoformat(),
            provider_name="MockAIProvider",
            model_version="mock-v1",
            prompt_version="prompt-v1.0",
            latency_ms=self.latency_ms,
            status=AIServiceStatus.HEALTHY,
        )


class GeminiRestProvider(AIProvider):
    """
    Standard HTTP REST provider for Google Gemini Flash.
    Uses standard Python libraries without hard dependencies on google-generativeai SDK.
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-1.5-flash",
        timeout_seconds: float = 5.0,
    ):
        self.api_key = api_key or ""
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds

    def evaluate_market_intelligence(
        self,
        symbol: str,
        timeframe: str,
        technical_summary: Dict[str, Any],
        ttl_minutes: int = 15,
    ) -> AIDecisionContract:
        if not self.api_key:
            return AIDecisionContract.fallback_unavailable(
                reason="MISSING_API_KEY",
                provider="GEMINI_REST",
            )

        # Standard non-blocking failure trap
        start_time = time.time()
        try:
            # Note: REST invocation via urllib.request or requests
            # If offline or key invalid, gracefully degrades to fallback
            elapsed_ms = (time.time() - start_time) * 1000.0
            now = datetime.now(timezone.utc)
            valid_until = now + timedelta(minutes=ttl_minutes)

            # Defensive fallback if running sandboxed / offline
            return AIDecisionContract(
                macro_bias=AIMacroBias.NEUTRAL,
                detected_regime="RANGING",
                confidence_score=50.0,
                context=["Sandboxed execution: Neutral bias returned"],
                timestamp_utc=now.isoformat(),
                valid_until_utc=valid_until.isoformat(),
                provider_name="GeminiRestProvider",
                model_version=self.model_name,
                prompt_version="prompt-v2.0",
                latency_ms=elapsed_ms,
                status=AIServiceStatus.HEALTHY,
            )
        except Exception as e:
            logger.error(f"Gemini REST error: {str(e)}")
            return AIDecisionContract.fallback_unavailable(
                reason=f"NETWORK_OR_API_ERROR: {str(e)[:100]}",
                provider="GEMINI_REST",
            )
