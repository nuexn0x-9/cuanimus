"""
Tests for CUANIMUS AI Intelligence Decoupling.
Tests:
- AIProvider interface & MockAIProvider
- AIDecisionContract schema validation & TTL expiration
- AISidecarWorker caching, non-blocking execution, and circuit breaker
- Deterministic fallback on provider failure (AI = UNAVAILABLE)
"""
import unittest
import time
from datetime import datetime, timedelta, timezone
from cuanimus.ai.contract import (
    AIDecisionContract,
    AIMacroBias,
    AIServiceStatus,
)
from cuanimus.ai.provider import (
    MockAIProvider,
    GeminiRestProvider,
)
from cuanimus.ai.sidecar import (
    AISidecarWorker,
    AISidecarConfig,
)


class TestAIDecoupling(unittest.TestCase):
    def test_contract_schema_validation(self):
        """AIDecisionContract validates confidence ranges and TTL expiry."""
        now = datetime.now(timezone.utc)
        valid_until = now + timedelta(minutes=15)

        valid_contract = AIDecisionContract(
            macro_bias=AIMacroBias.BULLISH,
            detected_regime="TRENDING_BULL",
            confidence_score=85.0,
            context=["Context 1"],
            timestamp_utc=now.isoformat(),
            valid_until_utc=valid_until.isoformat(),
            provider_name="TestProvider",
            model_version="v1",
            prompt_version="p1",
        )
        self.assertTrue(valid_contract.validate())
        self.assertFalse(valid_contract.is_expired(now))

        # Check expired contract
        past_time = now + timedelta(minutes=20)
        self.assertTrue(valid_contract.is_expired(past_time))

        # Out-of-bounds confidence
        invalid_contract = AIDecisionContract(
            macro_bias=AIMacroBias.BULLISH,
            detected_regime="TRENDING_BULL",
            confidence_score=150.0,  # Invalid > 100
            context=[],
            timestamp_utc=now.isoformat(),
            valid_until_utc=valid_until.isoformat(),
            provider_name="TestProvider",
            model_version="v1",
            prompt_version="p1",
        )
        self.assertFalse(invalid_contract.validate())

    def test_sidecar_caching_and_cache_hits(self):
        """Sidecar returns cached intelligence on subsequent calls within TTL."""
        provider = MockAIProvider(injected_bias=AIMacroBias.BULLISH, latency_ms=10.0)
        sidecar = AISidecarWorker(provider, AISidecarConfig(ttl_minutes=15))

        res1 = sidecar.get_intelligence("BTC/USDT:USDT", "15m", {"close": 50000.0})
        self.assertEqual(res1.macro_bias, AIMacroBias.BULLISH)

        res2 = sidecar.get_intelligence("BTC/USDT:USDT", "15m", {"close": 50100.0})
        self.assertEqual(res2.macro_bias, AIMacroBias.BULLISH)

        metrics = sidecar.get_observability_metrics()["metrics"]
        self.assertEqual(metrics["total_requests"], 2)
        self.assertEqual(metrics["cache_hits"], 1)
        self.assertEqual(metrics["cache_misses"], 1)

    def test_sidecar_failure_fallback_and_circuit_breaker(self):
        """Simulated provider failure immediately yields UNAVAILABLE and trips circuit breaker."""
        failing_provider = MockAIProvider(simulated_failure="timeout")
        sidecar = AISidecarWorker(failing_provider, AISidecarConfig(circuit_breaker_max_fails=3, cooldown_seconds=60.0))

        # Fails 1, 2, 3
        for _ in range(3):
            contract = sidecar.get_intelligence("ETH/USDT:USDT", "15m", {})
            self.assertEqual(contract.macro_bias, AIMacroBias.UNAVAILABLE)
            self.assertEqual(contract.status, AIServiceStatus.UNAVAILABLE)

        obs = sidecar.get_observability_metrics()
        self.assertTrue(obs["circuit_breaker_active"])
        self.assertEqual(obs["metrics"]["circuit_breaker_trips"], 1)

        # Subsequent call during cooldown returns circuit breaker fallback
        cb_contract = sidecar.get_intelligence("ETH/USDT:USDT", "15m", {})
        self.assertEqual(cb_contract.macro_bias, AIMacroBias.UNAVAILABLE)
        self.assertIn("CIRCUIT_BREAKER", cb_contract.failure_reason)


if __name__ == "__main__":
    unittest.main()
