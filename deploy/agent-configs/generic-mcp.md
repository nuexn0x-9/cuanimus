# CUANIMUS — Generic MCP Client Integration Guide (Claude Desktop / Cursor)

**Protocol Version:** Model Context Protocol (MCP) 2024-11-05 / JSON-RPC 2.0  
**Transport Modes:** `stdio` (local process) & `http` (JSON-RPC POST)  

---

## 1. Claude Desktop (`claude_desktop_config.json`)

On macOS / Linux (`~/.config/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "cuanimus": {
      "command": "python3",
      "args": [
        "-m",
        "cuanimus.cli",
        "mcp",
        "start",
        "--transport",
        "stdio"
      ],
      "env": {}
    }
  }
}
```

---

## 2. Cursor IDE (`.cursor/mcp.json`)

Inside your workspace `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "cuanimus": {
      "command": "python3",
      "args": [
        "-m",
        "cuanimus.cli",
        "mcp",
        "start",
        "--transport",
        "stdio"
      ],
      "env": {}
    }
  }
}
```

---

## 3. Remote HTTP MCP Client (Python / Node / cURL)

To send an MCP JSON-RPC call over HTTP:

```bash
curl -X POST http://127.0.0.1:8000/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${CUANIMUS_MCP_TOKEN}" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "system.get_safety_status",
      "arguments": {}
    }
  }'
```
