# CUANIMUS Decision Trace & Explainability

## 1. Traceability Architecture

Every algorithmic or autonomous action taken by an AI agent generates an append-only **Decision Trace**:

- **Timestamp & Event Clock**: ISO 8601 UTC timestamp.
- **Intent Identity**: UUID linking intent creation, validation outcome, and execution order.
- **Quantitative Rationale**: Strategy indicators, Fibonacci levels, ATR volatility metrics, and market regime context.
- **Policy Check Audit**: Verification results for symbol whitelist, leverage caps, and rate limits.
- **Risk Assessment Snapshot**: Portfolio equity, drawdown percentage, consecutive loss tally, calculated position size, and stop-loss price.

---

## 2. Decision Inspection Endpoint

Operators and auditing agents can inspect decision traces using:

```bash
# Via MCP tool call
tools/call: trading.get_decision_trace({"intent_id": "int_9b4e72a1"})
```

The resulting payload provides full explainability for human oversight, proving causality and regulatory compliance.
