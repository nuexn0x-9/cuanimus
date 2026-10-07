# CUANIMUS Web Control Center Access & Security Model

## 1. Overview

The **CUANIMUS Web Control Center** provides an operator-grade web dashboard and control plane designed for low-latency observation, manual intervention, and AI agent monitoring.

```text
Operator Browser / Remote Client
               │
      [ Encrypted SSH Tunnel ]
               │
               ▼
       127.0.0.1:8888 (CUANIMUS HTTP Daemon)
               │
    ┌──────────┴──────────┐
    │  Security Gateway   │
    │  - PBKDF2 Auth      │
    │  - Anti-Brute Force │
    │  - CSRF Defense     │
    │  - RBAC Engine      │
    └──────────┬──────────┘
               │
    ┌──────────┴──────────┐
    │ Control Plane Core  │
    │ - Position Monitor  │
    │ - Kill Switch       │
    │ - Replay & Config   │
    └─────────────────────┘
```

---

## 2. Port Architecture & Isolation

| Component | Bind Address | Port | Rationale |
| :--- | :--- | :--- | :--- |
| **CUANIMUS Web UI & API** | `0.0.0.0` / `127.0.0.1` | **8888** | Avoids port 80 (Apache) and port 8080 (Freqtrade container). Includes integrated `/mcp` proxy. |
| **CUANIMUS Dedicated MCP** | `0.0.0.0` / `127.0.0.1` | **8889** | Dedicated standalone JSON-RPC 2.0 daemon (`cuanimus-mcp`). |
| **CUANIMUS PostgreSQL** | `0.0.0.0` / `127.0.0.1` | **5432** | Quantitative database ledger (`cuanimus-db`). |
| **Apache 2** | `0.0.0.0` | 80 | Existing web server (untouched). |
| **Freqtrade Container**| `0.0.0.0` | 8080 | Pre-existing futures test bot (untouched). |

---

## 3. Remote Access via Secure SSH Tunnel

Since CUANIMUS can be run locally or bound to localhost/container networks, remote access from developer workstations is conducted through an encrypted SSH tunnel or direct port mapping:

### Command for Operator Workstations:

```bash
ssh -N -L 8888:127.0.0.1:8888 <user>@<server-ip>
```

Once the tunnel is active:
1. Open your web browser.
2. Navigate to: `http://localhost:8888/`
3. Enter your configured credentials:
   - **Default Super Admin (.env):** `admin_gemini` / `change_this_to_secure_password`
   - Or bootstrapped admin account.

---

## 4. Authentication & Security Engine

### 4.1 Cryptographic Password Hashing
- **Algorithm:** PBKDF2 with HMAC-SHA256.
- **Rounds:** 100,000 iterations.
- **Salt:** 16 bytes of cryptographically secure random bytes (`secrets.token_bytes(16)`).
- **Comparison:** Constant-time `secrets.compare_digest` to prevent timing attacks.

### 4.2 Anti-Brute Force Protection
- Failed login attempts are tracked per IP and username.
- If **5 failed attempts** occur within 60 seconds, the account/IP is locked out for **60 seconds**.
- Successful login clears failed counters immediately.

### 4.3 Anti-CSRF Protection
- Stateful sessions receive an anti-CSRF token upon login.
- Mutating endpoints (`POST`, `PUT`, `DELETE`) require the `X-CSRF-Token` header.

### 4.4 Role-Based Access Control (RBAC)

CUANIMUS implements three explicit user roles:

| Permission | VIEWER | OPERATOR | ADMIN |
| :--- | :---: | :---: | :---: |
| View System & Telemetry (`view:read`) | YES | YES | YES |
| Session Control (`trading:session:control`) | NO | YES | YES |
| Paper Trade Execution (`trading:paper:execute`) | NO | YES | YES |
| Configuration Modification (`config:write`) | NO | NO | YES |
| Emergency Kill Switch (`system:emergency_stop`) | NO | NO | YES |
| User & Auth Management (`auth:manage`) | NO | NO | YES |

---

## 5. Security Headers

Every HTTP response from the Control Center includes hardened HTTP response headers:

```http
Content-Security-Policy: default-src 'self'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; font-src 'self' https://cdn.jsdelivr.net; connect-src 'self'; img-src 'self' data:;
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin
```
