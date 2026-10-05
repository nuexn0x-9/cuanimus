# CUANIMUS — Google Antigravity MCP Connection Guide

**Agent Identity:** `antigravity-agent`  
**Default Preset:** `paper_auto` (READ + ANALYZE + CONFIG + EXECUTE)  
**Safety Policy:** Real Capital Trading STRICTLY DISABLED.  

---

## 1. Overview
Google Antigravity connects directly to the CUANIMUS MCP server via standard input/output (`stdio`) pipes or HTTP JSON-RPC. In `paper_auto` mode, Antigravity has full authority to inspect market regimes, evaluate strategy setups, assess risk parameters, generate trade intents, and monitor autonomous paper trading sessions without per-trade human confirmation.

---

## 2. Configuration Options

### Option A: Local Process Stdio (Fastest & Most Secure)
Add to Antigravity's MCP configuration (`~/.gemini/antigravity/mcp_config.json` or `.agents/mcp_config.json`):

```json
{
  "mcpServers": {
    "cuanimus": {
      "command": "python3",
      "args": ["-m", "cuanimus.cli", "mcp", "start", "--transport", "stdio"],
      "env": {}
    }
  }
}
```

### Option B: HTTP Server Mode
For remote or daemonized access:

```json
{
  "mcpServers": {
    "cuanimus": {
      "url": "http://127.0.0.1:8000/",
      "headers": {
        "Authorization": "Bearer ${CUANIMUS_MCP_TOKEN}"
      }
    }
  }
}
```

---

## 3. Example Autonomous Prompts for Antigravity

1. **Autonomous Session Orchestration:**
   > *"Start an automated paper trading session for ETH/USDT:USDT for 4 hours with conservative risk and maximum 10 trades."*

2. **Causal Decision Inspection:**
   > *"Explain why the last trade was executed and show the causal decision trace from market regime to execution."*

3. **Session Interventions:**
   > *"Check session health, error budget, and pause trading if volatility is high."*
