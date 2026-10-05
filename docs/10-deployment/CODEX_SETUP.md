# OpenAI Codex Agent Integration Guide

## 1. Overview

**Codex** operates primarily under the `advisory` agent policy within CUANIMUS. It provides quantitative code inspection, backtest replay assistance, parameter optimization proposals, and market regime analysis without executing autonomous trades directly.

---

## 2. Agent Identity & Scoped Token

Codex connects with the following pre-configured identity:
- **Agent ID:** `codex-agent`
- **Role:** `ADVISORY`
- **Allowed Domains:** `READ`, `ANALYZE`, `CONFIG`
- **Execution Clearance:** Strictly blocked from `EXECUTE` domain tools.

To view or rotate Codex's bearer token:

```bash
./cuanimus-cli agent token-list
./cuanimus-cli agent token-rotate --agent codex-agent
```

---

## 3. Client Configuration

### Option A: HTTP Transport (Recommended for Remote Workstations)

Add the following to your Codex agent configuration:

```json
{
  "mcpServers": {
    "cuanimus": {
      "url": "http://127.0.0.1:8888/mcp",
      "headers": {
        "Authorization": "Bearer <YOUR_CODEX_TOKEN>"
      }
    }
  }
}
```

### Option B: Local Stdio Transport

If Codex is executed directly on the server host:

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
      "cwd": "/home/zero/ai-gemini-futures-bot"
    }
  }
}
```

---

## 4. Verification

Test connection:

```bash
./cuanimus-cli agent test-connection --agent codex-agent
```

Expected output:
```text
============================================================
   CONNECTION TEST: AGENT 'codex-agent'
============================================================
Status:            [PASS] ACTIVE & AUTHENTICATED
Agent ID:          codex-agent
Preset:            advisory
Allowed Domains:   READ, ANALYZE, CONFIG
Safety Mode:       PAPER SAFE (Real Capital Prohibited)
Rate Limiting:     READ: 60/m | ANALYZE: 30/m | CONFIG: 15/m | EXECUTE: 5/m
============================================================
```
