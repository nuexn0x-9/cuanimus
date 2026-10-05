# Autonomous Agent Trading Lifecycle & Safety Invariants

## 1. Overview

In CUANIMUS, AI agents (Antigravity, Codex, Hermes) do not have direct socket access or API key access to trading exchanges. Instead, all autonomous actions must follow a strict, multi-stage approval and validation lifecycle.

```text
       AI Agent Decision
               │
               ▼
   1. Create Trade Intent (Draft)
               │
               ▼
   2. Two-Step Schema Validation
               │
               ▼
   3. RiskEngine Pre-Trade Clearance
      - Account balance verification
      - Leverage ceiling check (<= 3.0x)
      - Max daily drawdown check (<= 3.0%)
      - Mandatory Stop-Loss enforcement
               │
       [ RISK PASS ]
               │
               ▼
   4. PaperExecutionSafetyGuard
      - Dry-run verification
      - Strict block on live real-capital
               │
               ▼
   5. Virtual Order Execution FSM
               │
               ▼
   6. Watchdog Heartbeat & Error Budget
```

---

## 2. Invariant Rules

### Rule 1: Real Capital Live Trading = STRICTLY DISABLED (NO-GO)
Any attempt by an agent or human operator to initiate a live real-capital order triggers an immediate `FatalSafetyViolationError` and activates the system-wide emergency lock.

### Rule 2: RiskEngine is the Absolute Authority
Even if an AI model produces a trade intent with high confidence, the `RiskEngine` will veto the trade if:
- Margin required exceeds current free balance.
- Leverage exceeds maximum allowable multiplier.
- Max daily loss limit has been breached.
- Position sizing exceeds max risk percentage.

### Rule 3: Independent Human Kill-Switch
A human operator can trip the emergency stop at any time via:
1. Web Control Center button.
2. CLI command: `./cuanimus-cli status`
3. MCP tool: `emergency_stop`

When tripped, the kill-switch halts all active trading sessions immediately, closes paper positions, and locks the RiskEngine. AI agents **cannot** unfreeze or reset the kill-switch.

---

## 3. Two-Step Intent Pattern

All trade execution requires two distinct tool calls:
1. `trading.create_intent`: Generates a draft order with pair, direction, entry, stop loss, and rationale.
2. `trading.execute_intent`: Confirms execution after reviewing simulated fill metrics and risk assessment.
