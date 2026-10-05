# Nous Hermes Agent Integration Guide

## 1. Overview

**Hermes** is an autonomous trading agent designed for specialized order block and execution simulations. Under CUANIMUS, Hermes operates under the `paper_auto` policy profile, enforcing strict stop-loss rules.

---

## 2. Agent Identity & Permissions

- **Agent ID:** `hermes-agent`
- **Role:** `TRADER`
- **Allowed Domains:** `READ`, `ANALYZE`, `EXECUTE` (Note: `CONFIG` is blocked; Hermes cannot alter risk thresholds or system configurations).
- **Trading Modes:** `PAPER_AUTO`, `TESTNET_AUTO`

To inspect or rotate the Hermes token:

```bash
./cuanimus-cli agent token-list
./cuanimus-cli agent token-rotate --agent hermes-agent
```

---

## 3. Configuration Setup

### Hermes YAML Configuration (`config/agents/hermes.yaml`):

```yaml
agent_id: hermes-agent
name: Hermes Autonomous Trading Agent
role: TRADER
allowed_environments:
  - paper
  - testnet
allowed_symbols:
  - BTC/USDT:USDT
  - ETH/USDT:USDT
allowed_strategies:
  - v2_pullback
max_risk_per_trade_pct: 1.0
max_leverage: 3.0
max_daily_loss_pct: 2.5
max_orders_per_minute: 5
require_two_step_intent: true
require_mandatory_stop_loss: true
```

### Environment Configuration:

```bash
export CUANIMUS_MCP_URL="http://127.0.0.1:8888/mcp"
export CUANIMUS_BEARER_TOKEN="<YOUR_HERMES_TOKEN>"
```

---

## 4. Verification

Test connection:

```bash
./cuanimus-cli agent test-connection --agent hermes-agent
```
