"""
CUANIMUS AI Intelligence Decoupling Package.
Decouples external LLM intelligence from deterministic trading execution.
"""
from cuanimus.ai.contract import (
    AIMacroBias,
    AIDecisionContract,
    AIServiceStatus,
)
from cuanimus.ai.provider import (
    AIProvider,
    MockAIProvider,
    GeminiRestProvider,
)
from cuanimus.ai.sidecar import (
    AISidecarWorker,
    AISidecarConfig,
)

__all__ = [
    "AIMacroBias",
    "AIDecisionContract",
    "AIServiceStatus",
    "AIProvider",
    "MockAIProvider",
    "GeminiRestProvider",
    "AISidecarWorker",
    "AISidecarConfig",
]
