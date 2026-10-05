# CUANIMUS Assisted Configuration & Proposal Engine

## 1. Conversational Configuration Workflow

CUANIMUS provides a safe, structured mechanism for AI assistants to help users configure the platform without editing Python core code directly.

```mermaid
flowchart TD
    User["User: 'Configure conservative risk for ETH and BTC'"] --> Agent["AI Assistant"]
    Agent --> ToolCall["config.preview(modifications, rationale)"]
    ToolCall --> ProposalEngine["Proposal Engine"]
    ProposalEngine --> DiffEngine["Deep Structural Delta Diff"]
    ProposalEngine --> InvariantCheck["Pre-Flight Invariant Auditor"]
    InvariantCheck --> Validation{"Invariants Valid?"}
    Validation -- No --> Reject["Status: INVALID (Errors Reported)"]
    Validation -- Yes --> Review["Status: VALID (Pending Human Approval)"]
    Review --> Operator["Human Operator Review"]
    Operator --> Apply["config.apply(proposal_id)"]
    Apply --> Disk["cuanimus.user.yaml (Persisted)"]
```

---

## 2. Impact Level Classification

Every modified field is classified according to operational risk:

- `SAFE`: Non-critical parameters such as descriptions, logging levels, or cosmetic presets.
- `NOTICE`: Risk limits, capital allocation, cooldown hours, or drawdown thresholds.
- `CRITICAL`: Changes involving live trading flags, stop-loss mechanics, leverage ceilings, or API credentials.

---

## 3. Pre-Flight Safety Verification

Before any proposal is surfaced for approval, `ProposalEngine` instantiates the target configuration and runs `ConfigValidator`. If any invariant is breached (e.g., attempt to enable live trading, leverage $> 10\text{x}$, or disable stop-loss), the proposal is immediately flagged `INVALID` with exact remediation advice.
