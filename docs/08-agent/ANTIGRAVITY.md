# CUANIMUS Integration Guide for Antigravity

## 1. Overview

Google Antigravity natively interfaces with CUANIMUS through the Model Context Protocol (MCP) over `stdio` pipes.

---

## 2. Setting Up in Antigravity

To register CUANIMUS in your Antigravity agent settings:

```json
{
  "mcpServers": {
    "cuanimus": {
      "command": "/usr/bin/python3",
      "args": ["-m", "cuanimus.cli", "mcp", "start", "--transport", "stdio"],
      "env": {}
    }
  }
}
```

---

## 3. Natural Language Assisted Configuration Examples

You can interact with Antigravity using natural language prompts:

- *"Audit our CUANIMUS risk settings and tell me if we are compliant with paper trading rules."*
  $\rightarrow$ Invokes `system.get_safety_status` and `risk.get_limits`.
- *"Propose a new configuration setting risk per trade to 0.75% and base timeframe to 1h."*
  $\rightarrow$ Invokes `config.preview`, displaying deep delta diffs and invariant verification.
- *"Scan ETH and BTC for v2 pullback setups and simulate execution costs."*
  $\rightarrow$ Invokes `trading.find_setup` and `trading.simulate_trade`.
- *"Start a 1-hour paper trading session with an error budget of 3."*
  $\rightarrow$ Invokes `session.create` and `session.start`.
