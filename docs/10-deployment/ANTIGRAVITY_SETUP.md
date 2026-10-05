# Google Antigravity Agent Integration Guide

## 1. Overview

**Antigravity** operates as a high-capability quantitative agent with full authorization for autonomous paper and testnet trading under the `paper_auto` policy profile.

---

## 2. Agent Identity & Permissions

- **Agent ID:** `antigravity-agent`
- **Role:** `TRADER` / `SUPERVISOR`
- **Allowed Domains:** `READ`, `ANALYZE`, `CONFIG`, `EXECUTE`
- **Trading Modes:** `PAPER_AUTO`, `TESTNET_AUTO` (Live Real Capital Strictly Forbidden)
- **Ceilings:**
  - Max Risk per Trade: 1.5%
  - Max Leverage: 3.0x
  - Max Orders per Minute: 10
  - Two-Step Intent Requirement: ACTIVE

To inspect or rotate the Antigravity token:

```bash
./cuanimus-cli agent token-list
./cuanimus-cli agent token-rotate --agent antigravity-agent
```

---

## 3. Client Configuration

### Claude Desktop / Antigravity Agent Configuration (`claude_desktop_config.json`)

```json
{
  "mcpServers": {
    "cuanimus": {
      "url": "http://127.0.0.1:8888/mcp",
      "headers": {
        "Authorization": "Bearer <YOUR_ANTIGRAVITY_TOKEN>"
      }
    }
  }
}
```

Or for Stdio transport:

```json
{
  "mcpServers": {
    "cuanimus": {
      "command": "/usr/bin/python3",
      "args": [
        "-m",
        "cuanimus.cli",
        "mcp",
        "start",
        "--transport",
        "stdio"
      ],
      "cwd": "/home/zero/ai-gemini-futures-bot",
      "env": {
        "CUANIMUS_AGENT_ID": "antigravity-agent"
      }
    }
  }
}
```

---

## 4. Verification

Test connection:

```bash
./cuanimus-cli agent test-connection --agent antigravity-agent
```

Antigravity can test invoking MCP tools:
- `system.get_safety_status`: Returns current system health and invariants.
- `market.get_ticker`: Returns current live ticker for BTC, ETH, or SOL.
- `strategy.evaluate`: Evaluates V2 Pullback strategy rules on historical bars.
- `trading.create_intent`: Generates a paper trading intent for validation.
