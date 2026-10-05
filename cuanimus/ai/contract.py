"""
CUANIMUS AI Decision Contract.
Defines the strictly typed schema and validation rules for external AI intelligence.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import List, Dict, Any, Optional
import json


class AIMacroBias(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"
    UNAVAILABLE = "UNAVAILABLE"


class AIServiceStatus(str, Enum):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"
    DISABLED = "DISABLED"


@dataclass
class AIDecisionContract:
    macro_bias: AIMacroBias
    detected_regime: str
    confidence_score: float
    context: List[str]
    timestamp_utc: str
    valid_until_utc: str
    provider_name: str
    model_version: str
    prompt_version: str
    latency_ms: float = 0.0
    status: AIServiceStatus = AIServiceStatus.HEALTHY
    failure_reason: Optional[str] = None

    def is_expired(self, current_time: Optional[datetime] = None) -> bool:
        """Returns True if contract validity TTL has lapsed."""
        now = current_time or datetime.now(timezone.utc)
        try:
            valid_until = datetime.fromisoformat(self.valid_until_utc.replace("Z", "+00:00"))
            return now > valid_until
        except Exception:
            return True

    def validate(self) -> bool:
        """Validates schema boundaries and sanity constraints."""
        if self.status == AIServiceStatus.UNAVAILABLE or self.macro_bias == AIMacroBias.UNAVAILABLE:
            return False
        if not (0.0 <= self.confidence_score <= 100.0):
            return False
        if not self.valid_until_utc or not self.timestamp_utc:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "macro_bias": self.macro_bias.value,
            "detected_regime": self.detected_regime,
            "confidence_score": round(self.confidence_score, 2),
            "context": self.context,
            "timestamp_utc": self.timestamp_utc,
            "valid_until_utc": self.valid_until_utc,
            "provider_name": self.provider_name,
            "model_version": self.model_version,
            "prompt_version": self.prompt_version,
            "latency_ms": round(self.latency_ms, 2),
            "status": self.status.value,
            "failure_reason": self.failure_reason,
        }

    @classmethod
    def fallback_unavailable(cls, reason: str, provider: str = "SYSTEM_FALLBACK") -> "AIDecisionContract":
        """Deterministic safety fallback when AI is degraded, timing out, or invalid."""
        now_str = datetime.now(timezone.utc).isoformat()
        return cls(
            macro_bias=AIMacroBias.UNAVAILABLE,
            detected_regime="UNCERTAIN",
            confidence_score=0.0,
            context=["Fallback activated: Deterministic engine ignores AI bias"],
            timestamp_utc=now_str,
            valid_until_utc=now_str,
            provider_name=provider,
            model_version="none",
            prompt_version="v0",
            status=AIServiceStatus.UNAVAILABLE,
            failure_reason=reason,
        )
