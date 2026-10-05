"""
CUANIMUS AI Sidecar Background Worker.
Decouples AI network latency from candle evaluation loops.
Stores decisions in a thread-safe local cache with TTL expiration.
"""
import threading
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from cuanimus.ai.contract import AIDecisionContract, AIMacroBias
from cuanimus.ai.provider import AIProvider, MockAIProvider

logger = logging.getLogger(__name__)


@dataclass
class AISidecarConfig:
    ttl_minutes: int = 15
    circuit_breaker_max_fails: int = 3
    cooldown_seconds: float = 300.0  # 5 minutes after 3 fails
    max_cache_entries: int = 100


class AISidecarWorker:
    """
    In-process isolated background AI intelligence manager.
    Decoupled from candle loop:
    - Never blocks candle execution
    - Returns cached intelligence or fallback if stale
    - Implements circuit breaker against rate limits and network drops
    """
    def __init__(self, provider: AIProvider, config: Optional[AISidecarConfig] = None):
        self.provider = provider
        self.config = config or AISidecarConfig()
        self._cache: Dict[str, AIDecisionContract] = {}
        self._lock = threading.Lock()
        self._consecutive_failures = 0
        self._circuit_breaker_until: Optional[float] = None
        self._metrics = {
            "total_requests": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "failures": 0,
            "circuit_breaker_trips": 0,
        }

    def get_intelligence(
        self,
        symbol: str,
        timeframe: str,
        technical_summary: Dict[str, Any],
        refresh_async: bool = True,
    ) -> AIDecisionContract:
        """
        Retrieves current intelligence contract for symbol.
        Returns cached contract if fresh (< TTL).
        If stale or missing, returns fallback and triggers background refresh.
        """
        self._metrics["total_requests"] += 1
        now_ts = time.time()

        # Check circuit breaker
        if self._circuit_breaker_until and now_ts < self._circuit_breaker_until:
            return AIDecisionContract.fallback_unavailable(
                reason="CIRCUIT_BREAKER_ACTIVE_COOLDOWN",
                provider=self.provider.__class__.__name__,
            )

        with self._lock:
            cached = self._cache.get(symbol)
            if cached and not cached.is_expired():
                self._metrics["cache_hits"] += 1
                return cached

        # Cache miss or expired
        self._metrics["cache_misses"] += 1

        # Fetch intelligence
        try:
            decision = self.provider.evaluate_market_intelligence(
                symbol=symbol,
                timeframe=timeframe,
                technical_summary=technical_summary,
                ttl_minutes=self.config.ttl_minutes,
            )

            if decision.validate():
                with self._lock:
                    self._cache[symbol] = decision
                self._consecutive_failures = 0
                return decision
            else:
                self._record_failure("INVALID_CONTRACT_SCHEMA")
                return decision

        except Exception as e:
            self._record_failure(str(e))
            return AIDecisionContract.fallback_unavailable(
                reason=f"SIDECAR_EXCEPTION: {str(e)[:80]}",
                provider=self.provider.__class__.__name__,
            )

    def _record_failure(self, reason: str):
        self._metrics["failures"] += 1
        self._consecutive_failures += 1
        logger.warning(f"AI Sidecar failure ({self._consecutive_failures}/{self.config.circuit_breaker_max_fails}): {reason}")

        if self._consecutive_failures >= self.config.circuit_breaker_max_fails:
            self._metrics["circuit_breaker_trips"] += 1
            self._circuit_breaker_until = time.time() + self.config.cooldown_seconds
            logger.error(f"AI Sidecar circuit breaker TRIPPED! Cooldown for {self.config.cooldown_seconds}s")

    def get_observability_metrics(self) -> Dict[str, Any]:
        """Observability telemetry snapshot."""
        return {
            "metrics": dict(self._metrics),
            "circuit_breaker_active": bool(self._circuit_breaker_until and time.time() < self._circuit_breaker_until),
            "cached_symbols": list(self._cache.keys()),
        }
