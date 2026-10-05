# CUANIMUS Integration Guide for Codex & OpenAI Tool Use

## 1. Overview

Codex and OpenAI-compatible tool calling agents can interact with CUANIMUS either directly via the Model Context Protocol (MCP) or through standard JSON-RPC HTTP POST gateways.

---

## 2. Configuration Setup

Add CUANIMUS to your agent configuration:

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

---

## 3. Recommended Workflow

1. **System Health Check**: Call `system.get_status` and `system.get_safety_status`.
2. **Read Active Configuration**: Call `config.get_current`.
3. **Assisted Tuning**: When instructed by the user, propose changes using `config.preview`.
4. **Market & Strategy Analysis**: Call `market.get_regime` and `strategy.evaluate`.
5. **Trade Preparation**: Call `trading.create_intent` and `trading.validate_intent`.
