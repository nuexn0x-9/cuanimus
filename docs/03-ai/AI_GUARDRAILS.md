# AI FAILURE POLICY & OPERATIONAL GUARDRAILS

**Version:** 1.0.0  
**Status:** ACTIVE PROTOCOL

---

## 1. FAILURE MATRIX & FALLBACK BEHAVIOR

When an external AI call encounters an anomaly, the CUANIMUS engine enforces the following deterministic policy:

| Failure Scenario | Sidecar Behavior | Fallback Contract | Strategy Execution Action |
| :--- | :--- | :--- | :--- |
| **HTTP Timeout (> 5.0s)** | Terminate request, log warning | `macro_bias = UNAVAILABLE`<br>`status = UNAVAILABLE` | Ignore AI bias; follow pure deterministic technical rules. |
| **HTTP 429 Rate Limit** | Increment fail counter; trigger circuit breaker | `macro_bias = UNAVAILABLE`<br>`status = DEGRADED` | Ignore AI bias; continue normal technical execution. |
| **Malformed / Invalid JSON** | Reject payload; schema validation fails | `macro_bias = UNAVAILABLE`<br>`failure_reason = "SCHEMA_ERROR"` | Ignore AI bias; flag for log analysis. |
| **Stale Result (TTL Expired)** | Discard cached record | `macro_bias = UNAVAILABLE`<br>`status = UNAVAILABLE` | Ignore AI bias until fresh contract is generated. |
| **Network Outage / Offline** | Catch network error; return fallback | `macro_bias = UNAVAILABLE`<br>`status = UNAVAILABLE` | Deterministic offline operation proceeds unaffected. |

---

## 2. GOLDEN RULE: NEVER GUESS BIAS

> [!CAUTION]
> If AI is unavailable or failing, the trading engine MUST NEVER default to `BULLISH` or `BEARISH`.
> The only permitted fallback state is `UNAVAILABLE`.
> The deterministic strategy must treat `UNAVAILABLE` as "no AI veto and no AI boost", executing strictly according to mathematical technical indicators.

---

## 3. OBSERVABILITY & TELEMETRY REQUIREMENTS

All AI interactions must emit telemetry records containing:
- Request and response timestamps (ISO-8601 UTC)
- End-to-end roundtrip latency in milliseconds
- Provider name and model version
- Token usage count (prompt tokens, completion tokens) when reported by provider
- Cache hit vs cache miss flag
- Schema validation outcome (Passed / Failed)
- Circuit breaker status (Active / Inactive)

> [!IMPORTANT]
> Under no circumstances may API keys, secrets, or internal user tokens be logged in observability records.
