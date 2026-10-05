# AI DECISION CONTRACT & SCHEMA SPECIFICATION

**Version:** 1.0.0  
**Specification:** JSON Schema & Python Dataclass `AIDecisionContract`

---

## 1. STRUCTURED JSON SCHEMA

Every AI intelligence response must adhere strictly to the following contract:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "AIDecisionContract",
  "type": "object",
  "properties": {
    "macro_bias": {
      "type": "string",
      "enum": ["BULLISH", "BEARISH", "NEUTRAL", "UNAVAILABLE"]
    },
    "detected_regime": {
      "type": "string",
      "enum": [
        "TRENDING_BULL",
        "TRENDING_BEAR",
        "RANGING",
        "HIGH_VOLATILITY",
        "LOW_VOLATILITY",
        "UNCERTAIN"
      ]
    },
    "confidence_score": {
      "type": "number",
      "minimum": 0.0,
      "maximum": 100.0
    },
    "context": {
      "type": "array",
      "items": { "type": "string" }
    },
    "timestamp_utc": {
      "type": "string",
      "format": "date-time"
    },
    "valid_until_utc": {
      "type": "string",
      "format": "date-time"
    },
    "provider_name": { "type": "string" },
    "model_version": { "type": "string" },
    "prompt_version": { "type": "string" },
    "latency_ms": { "type": "number" },
    "status": {
      "type": "string",
      "enum": ["HEALTHY", "DEGRADED", "UNAVAILABLE"]
    },
    "failure_reason": {
      "type": ["string", "null"]
    }
  },
  "required": [
    "macro_bias",
    "detected_regime",
    "confidence_score",
    "timestamp_utc",
    "valid_until_utc",
    "provider_name",
    "model_version",
    "prompt_version",
    "status"
  ]
}
```

---

## 2. STRICT VALIDATION RULES

1. **TTL Expiration:** If `current_time > valid_until_utc`, the contract is considered expired and discarded.
2. **Confidence Range:** Values outside `[0.0, 100.0]` fail validation immediately.
3. **Enum Integrity:** Any unrecognized bias or regime values trigger an automatic transition to `UNAVAILABLE`.
4. **No Side-Effects:** The contract contains only descriptive intelligence; it contains no trade quantity, price target, or order side orders.
