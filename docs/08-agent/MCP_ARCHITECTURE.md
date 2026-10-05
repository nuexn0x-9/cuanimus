# CUANIMUS Model Context Protocol (MCP) Architecture

## 1. Overview & Specification Compliance

The CUANIMUS Model Context Protocol server implements the official **Model Context Protocol (MCP)** specification (2024-11-05 revision) and standard **JSON-RPC 2.0**.

It delivers zero-bloat, native Python 3.10 standard library implementation with zero external transport dependencies.

---

## 2. Supported Transports

CUANIMUS supports dual transport layers:

### Transport 1: `stdio` (Standard Input / Output)
Used by command-line agents, Antigravity CLI, Claude Desktop, and local subprocess managers.
- Requests arrive as newline-delimited JSON strings on `stdin`.
- Responses emit as newline-delimited JSON strings on `stdout`.
- Server diagnostics and audit logs are emitted strictly to `stderr` or local log files, ensuring standard JSON stream purity.

```bash
# Launching via stdio
./cuanimus-cli mcp start --transport stdio
```

### Transport 2: `http` (HTTP JSON-RPC POST)
Used by web UIs, remote agents, and networked sidecars.
- Endpoint: `POST http://<host>:<port>/` or `/mcp`
- Headers: `Content-Type: application/json`, optional `Authorization: Bearer <token>`
- Health probe: `GET /health` or `GET /`

```bash
# Launching HTTP listener on port 8000
./cuanimus-cli mcp start --transport http --port 8000
```

---

## 3. Protocol Message Lifecycle

### Handshake (`initialize`)
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "initialize",
  "params": {
    "protocolVersion": "2024-11-05",
    "capabilities": {},
    "clientInfo": { "name": "antigravity", "version": "1.0.0" }
  }
}
```
**Response:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "protocolVersion": "2024-11-05",
    "capabilities": {
      "tools": {},
      "resources": {},
      "prompts": {}
    },
    "serverInfo": {
      "name": "cuanimus-mcp-server",
      "version": "1.0.0"
    }
  }
}
```

### Notifications (`notifications/initialized`)
Acknowledges successful client initialization without returning an RPC response payload.

### Ping (`ping`)
Heartbeat health check returning an empty result object `{}`.
