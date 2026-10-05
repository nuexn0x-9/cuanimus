"""
CUANIMUS Agent Integration & Autonomous Automation Subsystem.
Provides identity, policy enforcement, configuration proposal generation,
two-step trade intents, session automation, and immutable audit logging.
"""
from cuanimus.agent.identity import AgentIdentity, AgentRole, AgentPermission
from cuanimus.agent.policy import AgentTradingPolicy, PolicyEvaluationResult
from cuanimus.agent.proposal import ConfigurationProposal, ProposalStatus
from cuanimus.agent.intent import AgentTradeIntent, IntentValidationResult
from cuanimus.agent.session import (
    TradingSession,
    TradingSessionManager,
    SessionState,
    SessionMode,
)
from cuanimus.agent.audit import AgentAuditLogger

__all__ = [
    "AgentIdentity",
    "AgentRole",
    "AgentPermission",
    "AgentTradingPolicy",
    "PolicyEvaluationResult",
    "ConfigurationProposal",
    "ProposalStatus",
    "AgentTradeIntent",
    "IntentValidationResult",
    "TradingSession",
    "TradingSessionManager",
    "SessionState",
    "SessionMode",
    "AgentAuditLogger",
]
