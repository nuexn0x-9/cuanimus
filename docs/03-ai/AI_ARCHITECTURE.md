# AI INTELLIGENCE DECOUPLING ARCHITECTURE

**Version:** 1.0.0  
**Status:** IMPLEMENTED & DECOUPLED  
**Core Principle:** AI is an Optional Market Intelligence Advisory Layer, NEVER an Order Authority.

---

## 1. ARCHITECTURAL ISOLATION PRINCIPLE

In the CUANIMUS architecture, Artificial Intelligence (LLM) is strictly prevented from:
1. Submitting or modifying orders directly to exchanges.
2. Bypassing the `RiskEngine` or overriding risk circuit breakers.
3. Specifying position sizing or leverage parameters.
4. Overriding emergency kill switches or daily loss caps.

### System Decoupling Topology:
```text
┌────────────────────────────────────────────────────────┐
│               DETERMINISTIC CORE ENGINE                │
│                                                        │
│  [Market OHLCV] ──> [Feature Pipeline] ──> [Strategy]   │
│                                                 │      │
│                                           (Intent)     │
│                                                 ▼      │
│                                           [RiskEngine] │
│                                                 │      │
│                                           (Order Req)  │
│                                                 ▼      │
│                                           [Execution]  │
└───────────────────────▲────────────────────────────────┘
                        │ Read Cached Contract
                        │ (Non-Blocking)
┌───────────────────────┴────────────────────────────────┐
│           AI INTELLIGENCE SIDECAR WORKER               │
│                                                        │
│  [Thread-Safe In-Memory Cache] <── [TTL: 15m Eviction] │
│          ▲                                             │
│          │ Async Poll / On-Demand Request              │
│  [Circuit Breaker (3 Fails -> 5m Cooldown)]            │
│          ▲                                             │
│          │ Normalized Contract                         │
│  [AIProvider Interface]                                │
│     ├── MockAIProvider (Testing & CI)                  │
│     ├── GeminiRestProvider (Google HTTP API)           │
│     └── FutureProvider (Claude / OpenAI / Local LLM)   │
└────────────────────────────────────────────────────────┘
```

---

## 2. EVALUATION OF SIDECAR ARCHITECTURAL DESIGNS

| Architectural Option | Complexity | Network Latency | Fault Isolation | Verdict |
| :--- | :---: | :---: | :---: | :--- |
| **In-Process Async Worker** | **Low** | **0 ms (In-Memory)** | **High (Thread & Try/Except)** | **SELECTED (Current)**: Zero operational overhead, no open ports, non-blocking candle loop. |
| **Separate Worker with Redis** | High | 1 - 5 ms | High (Separate process) | **REJECTED**: Introduces Redis infra dependency without functional justification for single instance. |
| **FastAPI Microservice Sidecar** | Medium | 2 - 10 ms | High (HTTP Boundary) | **OPTIONAL FUTURE**: Can be adopted seamlessly via `AIProvider` subclass if distributed scaling is required. |

---

## 3. ASYNCHRONOUS SIDECAR LIFECYCLE & CACHING

1. **Non-Blocking Operation:** The trading engine never performs a blocking HTTP network call inside the candle evaluation loop.
2. **TTL Caching:** Intelligence responses are cached with a configurable Time-To-Live (default: 15 minutes, matching the 15m execution timeframe).
3. **Graceful Fallback:** If the cache misses or expires and the provider is unresponsive, the worker returns an `UNAVAILABLE` fallback contract immediately without waiting.
4. **Circuit Breaker:** If 3 consecutive failures occur (timeouts, HTTP 429 rate limits, malformed JSON), the sidecar trips its circuit breaker for 300 seconds (5 minutes), shielding external APIs and logging alerts.
