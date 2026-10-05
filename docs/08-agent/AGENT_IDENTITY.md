# CUANIMUS Agent Identity & Authentication

## 1. Identity Model

Every autonomous or assistant entity connecting to CUANIMUS possesses a distinct `AgentIdentity`:

```python
@dataclass
class AgentIdentity:
    agent_id: str
    name: str
    role: AgentRole
    permissions: Set[AgentPermission]
    auth_token_hash: Optional[str]
    created_at: datetime
    is_active: bool
```

---

## 2. Agent Roles

| Role | Intended Usage | Key Capabilities |
| :--- | :--- | :--- |
| `ADVISORY` | Market analyst, configuration assistant | Read telemetry, analyze strategies, propose configs. Cannot trade. |
| `TRADER` | Autonomous execution bot | Execute paper/testnet trade intents, cancel orders, close positions. |
| `RISK_AUDITOR` | Independent oversight agent | Monitor drawdowns, audit exposures, activate emergency stop. |
| `OPERATOR` | Session manager | Orchestrate sessions, trigger kill switches, pause/resume execution. |
| `SUPERVISOR` | Full-platform automated agent | Full capabilities across paper/testnet automation. Live trading prohibited. |

---

## 3. Authentication & Token Management

1. **Local Stdio Connections**: When operating locally over pipes (Antigravity CLI or local subprocess), the identity defaults to the configured local profile or supervisor.
2. **Networked HTTP Connections**: Requires Bearer token authentication:
   ```http
   Authorization: Bearer <secret_token>
   ```
3. **Zero Secret Leakage**: CUANIMUS stores strictly salted SHA-256 hashes of agent tokens (`auth_token_hash`). Tokens are never persisted in cleartext.
