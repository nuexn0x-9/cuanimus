# Production Operations & Disaster Recovery Guide

## 1. Daemon Management

CUANIMUS provides both a native process supervisor and systemd service units for daemon orchestration.

### Native Process Supervisor (Default for Local / Containerized Environments)

```bash
# Start Web UI in background (default port 8888)
./cuanimus-cli ui start --daemon

# Stop Web UI
./cuanimus-cli ui stop

# Check Web UI status
./cuanimus-cli ui status

# Start Standalone MCP Server in background
./cuanimus-cli mcp start --transport http --host 127.0.0.1 --port 8000 --daemon

# Stop Standalone MCP Server
./cuanimus-cli mcp stop
```

### Systemd Service Management (Standard Linux VPS)

```bash
# Install unit files
sudo cp deploy/systemd/cuanimus-web.service /etc/systemd/system/
sudo cp deploy/systemd/cuanimus-mcp.service /etc/systemd/system/
sudo systemctl daemon-reload

# Start and enable services
sudo systemctl enable --now cuanimus-web
sudo systemctl enable --now cuanimus-mcp

# Inspect status and logs
sudo systemctl status cuanimus-web
sudo journalctl -u cuanimus-web -f
```

---

## 2. Automated Backups & Disaster Recovery

CUANIMUS provides the `BackupManager` engine to create atomic, SHA256-hashed backups of SQLite databases, active user profiles, and configuration files.

### Creating a Backup:

```bash
./cuanimus-cli backup create --tag periodic_backup
```

### Verifying Backup Integrity:

Backups are verified bit-by-bit against their recorded SHA256 cryptographic fingerprints:

```bash
# Verify the latest snapshot
./cuanimus-cli backup verify

# Verify a specific snapshot by ID
./cuanimus-cli backup verify --id backup_20261005_043746_pre_deployment
```

### Listing Available Snapshots:

```bash
./cuanimus-cli backup list
```

---

## 3. Log Locations & Monitoring

| Service | Log Location | Description |
| :--- | :--- | :--- |
| Web Control Center | `.cuanimus/ui.log` | Access logs, errors, and daemon lifecycle events. |
| MCP Daemon | `.cuanimus/mcp.log` | JSON-RPC calls, token authorizations, tool invocations. |
| Agent Audit Trail | `user_data/logs/agent_audit.jsonl` | Immutable log of all AI agent tool calls and parameters. |
| Replay & Quant | `user_data/logs/replay.log` | Historical bar processing and trade execution traces. |

---

## 4. Bounded Resource Ceilings

To operate reliably in constrained VPS environments (e.g., 1 vCPU / 1GB RAM):
- The Python HTTP daemon maintains a memory ceiling of `< 50MB`.
- Systemd units configure `MemoryHigh=250M` and `MemoryMax=350M`.
- No Node.js or JavaScript runtime is executed on the server.
