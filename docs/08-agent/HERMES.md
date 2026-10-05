# CUANIMUS Integration Guide for Hermes & Autonomous Bots

## 1. Overview

Hermes and autonomous background worker agents can orchestrate CUANIMUS sessions over HTTP JSON-RPC POST or standard CLI pipelines.

---

## 2. Background HTTP Connection Setup

Start the CUANIMUS MCP server as a background service:

```bash
./cuanimus-cli mcp start --transport http --port 8000 &
```

Then configure Hermes to point its tool endpoint to:
`http://127.0.0.1:8000/mcp`

---

## 3. Autonomous Execution Guardrails

When running headless trading bots:
1. Always set `mode: "PAPER_AUTO"` (or `"TESTNET_AUTO"`).
2. Set `max_duration_seconds` to prevent unmonitored overnight loops.
3. Establish an explicit `error_budget` (e.g., 3). If unexpected network failures or exchange drops occur, the watchdog will automatically halt the session.
4. Keep the human kill switch available: `./cuanimus-cli paper stop` or emergency stop tool calls will instantly lock the risk engine.
