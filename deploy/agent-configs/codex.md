# CUANIMUS — Codex MCP Connection Guide

**Agent Identity:** `codex-agent`  
**Default Preset:** `advisory` (READ + ANALYZE + CONFIG)  
**Safety Policy:** Real Capital Trading STRICTLY DISABLED.  

---

## 1. Overview
Codex connects to CUANIMUS via the Model Context Protocol (MCP) HTTP JSON-RPC endpoint. In advisory mode, Codex can inspect market regimes, evaluate strategy setups, assess risk parameters, and propose validated configuration diffs.

---

## 2. Configuration Parameters

| Parameter | Value |
| :--- | :--- |
| **Endpoint URL** | `http://127.0.0.1:8000/` (or via remote reverse proxy `https://<your-domain>/mcp`) |
| **Transport** | HTTP JSON-RPC 2.0 (POST) |
| **Auth Header** | `Authorization: Bearer ${CUANIMUS_MCP_TOKEN}` |
| **Rate Limit** | READ: 60/min, ANALYZE: 30/min, CONFIG: 15/min |

---

## 3. Client Registration Example

Add CUANIMUS to your Codex MCP configuration file:

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

> [!IMPORTANT]
> Never commit your raw token to version control. Replace `${CUANIMUS_MCP_TOKEN}` with the token generated via:
> ```bash
> ./cuanimus-cli agent token-rotate codex-agent
> ```

---

## 4. Example Prompts for Codex

1. **Market & Regime Intelligence:**
   > *"Analyze the current ETH/USDT:USDT 15m market regime and check if any bullish order blocks are forming."*

2. **Risk Assessment:**
   > *"Inspect current CUANIMUS risk boundaries, drawdown limits, and daily loss utilization."*

3. **Assisted Configuration Proposal:**
   > *"Propose a conservative configuration for ETH and BTC using the structure_v2b strategy with 0.5% risk."*
