# CUANIMUS Security Architecture & Threat Defense

## 1. Threat Defense Model

| Threat Vector | Mitigation Strategy | Verification Status |
| :--- | :--- | :--- |
| **Prompt Injection** | LLMs cannot execute shell commands or code directly. All actions pass through strict typed JSON schemas validated by `ConfigValidator`. | **VERIFIED** |
| **Secret Exfiltration** | Sensitive keys (Binance, Gemini, Telegram) are quarantined and scrubbed by `redact_sensitive_data()` in memory and audit logs. | **VERIFIED** |
| **Rogue Agent Over-Leveraging** | Hard platform ceiling of 10.0x leverage enforced at policy and risk engine levels. Any request exceeding 10x is vetoed. | **VERIFIED** |
| **Unauthorized Live Trading** | Live trading requires multiple explicit offline tokens. Invariant 2.1 in `ConfigValidator` strictly rejects live enablement. | **VERIFIED** |
| **API Denial-of-Service / Order Loops** | Sliding window rate limiter (max 10 orders/min per agent) prevents infinite request spam. | **VERIFIED** |
| **Loss of Control** | Independent human kill switch works asynchronously to halt sessions without requiring agent consent. | **VERIFIED** |

---

## 2. Immutable Audit Trail

All tool calls, policy checks, and trade orders are written to an append-only JSON Lines audit file:
`logs/agent_audit.jsonl`

Audit entries include caller identity, event type, arguments (redacted of secrets), execution timestamp, and status.
