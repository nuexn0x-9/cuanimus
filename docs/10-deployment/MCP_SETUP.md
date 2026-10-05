# Model Context Protocol (MCP) Architecture & Setup

## 1. Overview

CUANIMUS exposes its analytical, configuration, and execution engines via the **Model Context Protocol (MCP)** specification (Protocol version `2024-11-05`), utilizing standard JSON-RPC 2.0.

This enables external autonomous and semi-autonomous AI agents (e.g., Google Antigravity, OpenAI Codex, Nous Hermes, Claude Desktop, Cursor) to interact with CUANIMUS safely under bounded risk policies.

---

## 2. Transports

CUANIMUS provides two distinct MCP transport mechanisms:

1. **`stdio` Transport (Local / Pipe):**
   - Launched by parent agent IDE processes via CLI subprocess invocation.
   - Ideal for local development with Cursor or Claude Desktop running on the same server.
   ```bash
   ./cuanimus-cli mcp start --transport stdio
   ```

2. **`http` Transport (Remote / Daemon):**
   - HTTP POST JSON-RPC 2.0 daemon listening on `127.0.0.1:8000` (or proxied via `127.0.0.1:8888/mcp`).
   - Requires Bearer token authentication in HTTP request headers.
   ```bash
   ./cuanimus-cli mcp start --transport http --host 127.0.0.1 --port 8000 --daemon
   ```

---

## 3. Scoped Bearer Token Isolation

Agent tokens are stored in `.cuanimus/mcp_tokens.json` outside of source control. Each token has:
- `agent_id`: Identifier for the client agent (e.g. `antigravity-agent`).
- `preset`: Policy preset (`advisory`, `paper_auto`, `testnet_auto`).
- `allowed_domains`: Array of permitted functional domains.
- `status`: `ACTIVE` or `REVOKED`.

### Token Management Commands:

```bash
# List all registered tokens (with masked secrets)
./cuanimus-cli agent token-list

# Rotate an agent's token
./cuanimus-cli agent token-rotate --agent antigravity-agent

# Instantly revoke an agent's token
./cuanimus-cli agent token-revoke --agent rogue-agent

# Test cryptographic authentication
./cuanimus-cli agent test-connection --agent antigravity-agent
```

---

## 4. Per-Domain Rate Limiting

To prevent runaway loops, model hallucinations, or denial-of-service, CUANIMUS enforces sliding-window rate limits segmented by domain:

| Domain | Rate Limit | Examples of Included Tools |
| :--- | :---: | :--- |
| **READ** | **60 req/min** | `market.get_ticker`, `market.get_candles`, `portfolio.get_positions`, `system.get_safety_status` |
| **ANALYZE** | **30 req/min** | `strategy.evaluate`, `market.analyze_order_blocks`, `trading.simulate_fill`, `risk.assess_trade` |
| **CONFIG** | **15 req/min** | `config.validate`, `config.preview`, `config.apply` |
| **EXECUTE** | **5 req/min** | `trading.create_intent`, `trading.execute_intent`, `session.start`, `session.stop` |

When a limit is reached, CUANIMUS responds with HTTP `429 Too Many Requests` or JSON-RPC error code `-32000`, logging the event into the agent audit trail.

---

## 5. Security Invariant

> [!IMPORTANT]
> The MCP server has **no code path** to execute live real-capital orders. All trade intents are dispatched strictly through `PaperExecutionSafetyGuard` and `RiskEngine`.
