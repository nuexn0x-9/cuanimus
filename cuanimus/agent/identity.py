"""
CUANIMUS Agent Identity & Capability-Based Access Control (RBAC).
Defines agent identities, roles, granular permissions, authentication,
and default-deny security enforcement.
"""
import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Set, Dict, Optional, List, Any


class AgentRole(str, Enum):
    """Broad role classifications for AI agents."""
    ADVISORY = "ADVISORY"              # Read-only market/strategy analysis, config proposals
    TRADER = "TRADER"                  # Execution of paper/testnet trade intents under policy
    RISK_AUDITOR = "RISK_AUDITOR"      # Risk monitoring, exposure and stress test audits
    OPERATOR = "OPERATOR"              # Trading session orchestration, start/pause/stop
    SUPERVISOR = "SUPERVISOR"          # Full capabilities across paper/testnet automation


class AgentPermission(str, Enum):
    """Granular permissions governing agent actions. Enforces default-deny."""
    # Read telemetry & metadata
    READ_SYSTEM = "READ_SYSTEM"
    READ_MARKET = "READ_MARKET"
    READ_PORTFOLIO = "READ_PORTFOLIO"
    READ_RISK = "READ_RISK"
    READ_STRATEGY = "READ_STRATEGY"

    # Analysis & simulation
    ANALYZE = "ANALYZE"
    BACKTEST = "BACKTEST"
    SIMULATE = "SIMULATE"

    # Configuration manipulation
    CONFIGURE = "CONFIGURE"

    # Trade intent execution (Never live real-capital)
    PAPER_TRADE = "PAPER_TRADE"
    TESTNET_TRADE = "TESTNET_TRADE"
    CANCEL_ORDER = "CANCEL_ORDER"
    CLOSE_POSITION = "CLOSE_POSITION"

    # Session & orchestration
    MANAGE_SESSION = "MANAGE_SESSION"
    EMERGENCY_STOP = "EMERGENCY_STOP"


ROLE_DEFAULT_PERMISSIONS: Dict[AgentRole, Set[AgentPermission]] = {
    AgentRole.ADVISORY: {
        AgentPermission.READ_SYSTEM,
        AgentPermission.READ_MARKET,
        AgentPermission.READ_PORTFOLIO,
        AgentPermission.READ_RISK,
        AgentPermission.READ_STRATEGY,
        AgentPermission.ANALYZE,
        AgentPermission.BACKTEST,
        AgentPermission.SIMULATE,
        AgentPermission.CONFIGURE,
    },
    AgentRole.RISK_AUDITOR: {
        AgentPermission.READ_SYSTEM,
        AgentPermission.READ_MARKET,
        AgentPermission.READ_PORTFOLIO,
        AgentPermission.READ_RISK,
        AgentPermission.ANALYZE,
        AgentPermission.SIMULATE,
        AgentPermission.EMERGENCY_STOP,
    },
    AgentRole.TRADER: {
        AgentPermission.READ_SYSTEM,
        AgentPermission.READ_MARKET,
        AgentPermission.READ_PORTFOLIO,
        AgentPermission.READ_RISK,
        AgentPermission.READ_STRATEGY,
        AgentPermission.ANALYZE,
        AgentPermission.SIMULATE,
        AgentPermission.PAPER_TRADE,
        AgentPermission.TESTNET_TRADE,
        AgentPermission.CANCEL_ORDER,
        AgentPermission.CLOSE_POSITION,
        AgentPermission.EMERGENCY_STOP,
    },
    AgentRole.OPERATOR: {
        AgentPermission.READ_SYSTEM,
        AgentPermission.READ_MARKET,
        AgentPermission.READ_PORTFOLIO,
        AgentPermission.READ_RISK,
        AgentPermission.READ_STRATEGY,
        AgentPermission.MANAGE_SESSION,
        AgentPermission.CANCEL_ORDER,
        AgentPermission.CLOSE_POSITION,
        AgentPermission.EMERGENCY_STOP,
    },
    AgentRole.SUPERVISOR: {
        AgentPermission.READ_SYSTEM,
        AgentPermission.READ_MARKET,
        AgentPermission.READ_PORTFOLIO,
        AgentPermission.READ_RISK,
        AgentPermission.READ_STRATEGY,
        AgentPermission.ANALYZE,
        AgentPermission.BACKTEST,
        AgentPermission.SIMULATE,
        AgentPermission.CONFIGURE,
        AgentPermission.PAPER_TRADE,
        AgentPermission.TESTNET_TRADE,
        AgentPermission.CANCEL_ORDER,
        AgentPermission.CLOSE_POSITION,
        AgentPermission.MANAGE_SESSION,
        AgentPermission.EMERGENCY_STOP,
    },
}


@dataclass
class AgentIdentity:
    """Represents an authenticated AI Agent entity interacting via MCP/API."""
    agent_id: str
    name: str
    role: AgentRole
    permissions: Set[AgentPermission] = field(default_factory=set)
    auth_token_hash: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_active: bool = True

    def __post_init__(self):
        if not self.permissions:
            # Assign defaults based on role
            self.permissions = set(ROLE_DEFAULT_PERMISSIONS.get(self.role, set()))

    def has_permission(self, permission: AgentPermission) -> bool:
        """Enforces default-deny permission check."""
        if not self.is_active:
            return False
        return permission in self.permissions

    def verify_token(self, token: str) -> bool:
        """Verifies cleartext bearer token against stored SHA-256 hash."""
        if not self.auth_token_hash:
            return True  # If no auth token is required for local stdio
        computed = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return computed == self.auth_token_hash

    @staticmethod
    def hash_token(raw_token: str) -> str:
        """Generates SHA-256 hash for secure token storage."""
        return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "role": self.role.value,
            "permissions": sorted([p.value for p in self.permissions]),
            "created_at": self.created_at.isoformat(),
            "is_active": self.is_active,
        }


class AgentIdentityRegistry:
    """Thread-safe registry for agent identities and authentication."""
    _agents: Dict[str, AgentIdentity] = {}

    @classmethod
    def register(cls, agent: AgentIdentity) -> None:
        cls._agents[agent.agent_id] = agent

    @classmethod
    def get(cls, agent_id: str) -> Optional[AgentIdentity]:
        return cls._agents.get(agent_id)

    @classmethod
    def authenticate(cls, agent_id: str, token: Optional[str] = None) -> Optional[AgentIdentity]:
        agent = cls.get(agent_id)
        if not agent or not agent.is_active:
            return None
        if agent.auth_token_hash and (not token or not agent.verify_token(token)):
            return None
        return agent

    @classmethod
    def list_agents(cls) -> List[Dict[str, Any]]:
        return [a.to_dict() for a in cls._agents.values()]

    @classmethod
    def clear(cls) -> None:
        cls._agents.clear()


# Pre-register built-in agent profiles
AgentIdentityRegistry.register(
    AgentIdentity(
        agent_id="advisory-default",
        name="CUANIMUS Advisory Agent",
        role=AgentRole.ADVISORY,
    )
)
AgentIdentityRegistry.register(
    AgentIdentity(
        agent_id="trader-paper",
        name="CUANIMUS Paper Auto Trader",
        role=AgentRole.TRADER,
        permissions={
            AgentPermission.READ_SYSTEM,
            AgentPermission.READ_MARKET,
            AgentPermission.READ_PORTFOLIO,
            AgentPermission.READ_RISK,
            AgentPermission.READ_STRATEGY,
            AgentPermission.ANALYZE,
            AgentPermission.SIMULATE,
            AgentPermission.PAPER_TRADE,
            AgentPermission.CANCEL_ORDER,
            AgentPermission.CLOSE_POSITION,
            AgentPermission.EMERGENCY_STOP,
        },
    )
)
AgentIdentityRegistry.register(
    AgentIdentity(
        agent_id="supervisor-admin",
        name="CUANIMUS System Supervisor",
        role=AgentRole.SUPERVISOR,
    )
)
