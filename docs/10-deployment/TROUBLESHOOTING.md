# Production Troubleshooting Guide

## 1. Common Issues & Solutions

### Issue 1: Port Conflict on Port 8080 or Port 80
- **Symptom:** `OSError: [Errno 98] Address already in use`.
- **Cause:** Port 8080 is bound by Freqtrade container; Port 80 is bound by Apache.
- **Solution:** CUANIMUS is pre-configured to bind to port **8888** for Web UI and port **8000** for standalone MCP. Do not attempt to bind port 8080.
  ```bash
  ./cuanimus-cli ui start --daemon --port 8888
  ```

---

### Issue 2: Forgotten Administrator Password or Lockout
- **Symptom:** User cannot log in to the Web Control Center or is locked out after 5 failed attempts.
- **Solution:** Run the bootstrap command with the `--force` flag to rotate credentials:
  ```bash
  ./cuanimus-cli ui bootstrap --force
  ```
  This immediately generates a new temporary password and unlocks the administrator account.

---

### Issue 3: Agent Receives 401 Unauthorized on MCP Endpoints
- **Symptom:** Agent tool call fails with `401 Unauthorized` or `Invalid token`.
- **Solution:**
  1. Verify token status:
     ```bash
     ./cuanimus-cli agent token-list
     ```
  2. If the token was revoked or corrupted, rotate it:
     ```bash
     ./cuanimus-cli agent token-rotate --agent <agent-id>
     ```
  3. Ensure the `Authorization` header is formatted correctly:
     ```text
     Authorization: Bearer <TOKEN>
     ```

---

### Issue 4: Agent Receives 429 Too Many Requests
- **Symptom:** Agent receives `Rate limit exceeded for domain 'EXECUTE': Max 5 req/min`.
- **Solution:** This is intentional protective behavior. Instruct the agent to back off and avoid tight execution polling loops.

---

### Issue 5: Stale PID File
- **Symptom:** `Daemon 'ui' is already running with PID ...` but process is dead.
- **Solution:** The CLI automatically cleans up dead PIDs. Simply invoke stop:
  ```bash
  ./cuanimus-cli ui stop
  ./cuanimus-cli ui start --daemon
  ```

---

### Issue 6: Emergency Stop Tripped
- **Symptom:** All trading sessions halted, `Emergency Stop: LOCKED`.
- **Solution:** Reset the emergency stop via Web UI after reviewing system alarms, or via CLI:
  ```bash
  ./cuanimus-cli paper stop
  ```
