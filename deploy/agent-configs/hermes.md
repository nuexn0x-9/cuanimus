# CUANIMUS — Hermes Autonomous Agent MCP Connection Guide

**Agent Identity:** `hermes-agent`  
**Default Preset:** `paper_auto` (READ + ANALYZE + EXECUTE)  
**Safety Policy:** Real Capital Trading STRICTLY DISABLED.  

---

## 1. Overview
Hermes is an autonomous AI agent capable of long-running market surveillance and autonomous trade execution. When connected to CUANIMUS via MCP, Hermes operates within strict server-side risk boundaries and error budgets.

---

## 2. Configuration (`hermes.yaml`)

Add CUANIMUS to your Hermes configuration file:

```yaml
mcp_servers:
  cuanimus:
    url: "http://127.0.0.1:8000/"
    headers:
      Authorization: "Bearer ${CUANIMUS_MCP_TOKEN}"
    timeout: 30
```

> [!TIP]
> Retrieve or rotate your Hermes token using:
> ```bash
> ./cuanimus-cli agent token-rotate hermes-agent
> ```
> Export the token as an environment variable in your shell:
> ```bash
> export CUANIMUS_MCP_TOKEN="<your-token>"
> ```

---

## 3. Autonomous Execution Prompts

1. **Continuous Surveillance & Entry:**
   > *"Monitor BTC and ETH for structural pullback entries on 15m timeframe. If RiskEngine approves, submit limit orders."*

2. **Autonomous Risk Management:**
   > *"Monitor open positions, track ATR trailing stops, and trigger session pause if daily loss exceeds 1.5%."*
