# CUANIMUS Production Deployment Quickstart

Welcome to the **CUANIMUS Production Deployment & Operations Guide**. This guide provides the complete onboarding procedure to deploy the Web Control Center, start the Model Context Protocol (MCP) server, bootstrap administrative credentials, and connect autonomous AI agents.

---

## 1. Architectural Invariants

Before starting, take note of the platform's core safety invariants:

```text
+-------------------------------------------------------------------------+
|                  CORE PLATFORM SAFETY INVARIANTS                         |
+-------------------------------------------------------------------------+
|  [x] REAL CAPITAL LIVE TRADING  : STRICTLY DISABLED (NO-GO)             |
|  [x] ALLOWED TRADING MODES     : PAPER_AUTO, TESTNET_AUTO               |
|  [x] RISK ENGINE AUTHORITY     : ABSOLUTE & NON-BYPASSABLE              |
|  [x] HUMAN KILL-SWITCH         : INDEPENDENT & ASYNCHRONOUS OVERRIDE    |
|  [x] AUTHENTICATION            : SALTED PBKDF2 (100,000 ROUNDS) + RBAC  |
|  [x] MCP AGENT TOKENS          : CRYPTOGRAPHICALLY SCOPED + RATE-LIMITED|
+-------------------------------------------------------------------------+
```

---

## 2. Server Prerequisites

- **Operating System:** Linux (Ubuntu 20.04+, Debian 11+, RHEL/Rocky 8+, or WSL2).
- **Python:** Python 3.10+ standard library. Zero external framework dependencies required for server execution (no Node.js, no Redis, no PostgreSQL).
- **RAM Footprint:** ~35–50 MB active resident memory.
- **Port Allocation:**
  - `127.0.0.1:8888` - CUANIMUS Web Control Center, REST Control Plane API, Autonomous Engine & integrated `/mcp` proxy (chosen to avoid conflicts with Freqtrade on `8080` and Apache on `80`).
  - `127.0.0.1:8889` - Dedicated Standalone MCP HTTP Daemon (`cuanimus-mcp`).
  - `127.0.0.1:5432` - PostgreSQL 16 Relational Database (`cuanimus-db`).

---

## 3. Step-by-Step Deployment

### Step 1: Pre-Deployment Backup

Always create an atomic, SHA256-verified backup of existing configuration and databases before modifying services:

```bash
./cuanimus-cli backup create --tag pre_deployment
./cuanimus-cli backup verify
```

### Step 2: Configure Super Admin Credentials (.env Auto-Sync)

CUANIMUS automatically provisions and synchronizes administrative credentials directly from `.env` on daemon startup:

```bash
# In your .env file:
API_SERVER_USERNAME=admin_gemini
API_SERVER_PASSWORD=change_this_to_secure_password
```

On server boot, the system hashes this password with **PBKDF2-HMAC-SHA256 (100,000 iterations)** with a cryptographic salt and persists the user into the database with `ADMIN` role.

Alternatively, you can manually bootstrap a standalone operator account via CLI:

```bash
./cuanimus-cli ui bootstrap
```

*Output example:*
```text
============================================================
       CUANIMUS WEB CONTROL CENTER ADMIN BOOTSTRAP
============================================================
Status:   INITIALIZED
Username: admin
Password: <generated_secure_password>
Role:     ADMIN
Stored:   /home/zero/ai-gemini-futures-bot/.cuanimus/auth_users.json
Note:     Change this password immediately upon first login.
============================================================
```

> **Security Note:** The bootstrap mechanism generates a unique 16-character cryptographic password. Passwords are never stored in plaintext and are salted with PBKDF2-HMAC-SHA256 across 100,000 iterations.

### Step 3: Start the Web Control Center Daemon

Start the background service using the native process runner:

```bash
./cuanimus-cli ui start --daemon --host 127.0.0.1 --port 8888
```

Verify service status:

```bash
./cuanimus-cli ui status
```

Or for systemd-managed Linux VPS servers, enable the systemd unit:

```bash
sudo cp deploy/systemd/cuanimus-web.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cuanimus-web
sudo systemctl status cuanimus-web
```

### Step 4: Verify Health and Security Endpoints

Check system status:

```bash
curl -s http://127.0.0.1:8888/health
```

Expected response:
```json
{
  "status": "HEALTHY",
  "service": "cuanimus-control-plane",
  "timestamp": "2026-10-05T04:48:00+00:00",
  "real_capital_live": "STRICTLY_DISABLED"
}
```

### Step 5: Connect AI Agents

List available agent tokens:

```bash
./cuanimus-cli agent token-list
```

Test connection for your preferred agent:

```bash
./cuanimus-cli agent test-connection --agent antigravity-agent
```

---

## 4. Next Guides

- [Web Access & Security Model](file:///home/zero/ai-gemini-futures-bot/docs/10-deployment/WEB_ACCESS.md)
- [MCP Architecture & Token Policies](file:///home/zero/ai-gemini-futures-bot/docs/10-deployment/MCP_SETUP.md)
- [Connecting Google Antigravity](file:///home/zero/ai-gemini-futures-bot/docs/10-deployment/ANTIGRAVITY_SETUP.md)
- [Connecting OpenAI Codex](file:///home/zero/ai-gemini-futures-bot/docs/10-deployment/CODEX_SETUP.md)
- [Connecting Nous Hermes](file:///home/zero/ai-gemini-futures-bot/docs/10-deployment/HERMES_SETUP.md)
- [Operations & Disaster Recovery](file:///home/zero/ai-gemini-futures-bot/docs/10-deployment/OPERATIONS.md)
