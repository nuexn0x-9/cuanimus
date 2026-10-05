"""
CUANIMUS MCP Trading Session Automation Tools.
Enables agents to manage PAPER_AUTO and TESTNET_AUTO sessions,
inspect state machines, track error budgets, and invoke emergency kill switches.
"""
from typing import Dict, Any, Optional
from cuanimus.agent.identity import AgentPermission
from cuanimus.mcp.registry import McpRegistry
from cuanimus.agent.session import (
    TradingSessionManager,
    SessionMode,
    SessionState,
)


_global_session_manager = TradingSessionManager()


def tool_session_create(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Creates a new automated trading session."""
    agent_id = context.get("agent_id", "mcp-agent")
    raw_mode = args.get("mode", "PAPER_AUTO").upper()
    try:
        mode = SessionMode(raw_mode)
    except ValueError:
        raise ValueError(f"Invalid session mode '{raw_mode}'. Must be PAPER_AUTO or TESTNET_AUTO.")

    max_duration = int(args.get("max_duration_seconds", 3600))
    max_trades = int(args.get("max_trades", 20))
    error_budget = int(args.get("error_budget", 3))

    session = _global_session_manager.create_session(
        agent_id=agent_id,
        mode=mode,
        max_duration_seconds=max_duration,
        max_trades=max_trades,
        error_budget=error_budget,
    )

    return session.to_dict()


def tool_session_start(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Starts an existing trading session."""
    session_id = args.get("session_id")
    if not session_id:
        raise ValueError("Missing 'session_id'")

    session = _global_session_manager.start_session(session_id)
    return session.to_dict()


def tool_session_pause(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Pauses an active trading session."""
    session_id = args.get("session_id")
    reason = args.get("reason", "Agent requested pause")
    if not session_id:
        raise ValueError("Missing 'session_id'")

    session = _global_session_manager.pause_session(session_id, reason=reason)
    return session.to_dict()


def tool_session_resume(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Resumes a paused trading session."""
    session_id = args.get("session_id")
    if not session_id:
        raise ValueError("Missing 'session_id'")

    session = _global_session_manager.resume_session(session_id)
    return session.to_dict()


def tool_session_stop(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Stops a trading session cleanly."""
    session_id = args.get("session_id")
    reason = args.get("reason", "Agent requested clean termination")
    if not session_id:
        raise ValueError("Missing 'session_id'")

    session = _global_session_manager.stop_session(session_id, reason=reason)
    return session.to_dict()


def tool_session_get_status(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Returns status, health, and metrics for a specific or all sessions."""
    session_id = args.get("session_id")
    if session_id:
        sess = _global_session_manager.get_session(session_id)
        if not sess:
            raise KeyError(f"Session {session_id} not found")
        health = _global_session_manager.evaluate_session_health(session_id)
        return {
            "session": sess.to_dict(),
            "health": health,
        }
    else:
        return {
            "sessions": _global_session_manager.list_sessions(),
        }


def tool_session_emergency_stop(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Immediately halts sessions and locks the Risk Engine."""
    session_id = args.get("session_id")
    reason = args.get("reason", "Operator Emergency Stop")
    return _global_session_manager.emergency_stop(session_id=session_id, reason=reason)


def register_session_tools() -> None:
    McpRegistry.register_tool(
        name="session.create",
        description="Create an automated PAPER_AUTO or TESTNET_AUTO trading session.",
        input_schema={
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["PAPER_AUTO", "TESTNET_AUTO"]},
                "max_duration_seconds": {"type": "integer"},
                "max_trades": {"type": "integer"},
                "error_budget": {"type": "integer"},
            },
        },
        permission_required=AgentPermission.MANAGE_SESSION,
        handler=tool_session_create,
    )
    McpRegistry.register_tool(
        name="session.start",
        description="Start an initialized trading session.",
        input_schema={
            "type": "object",
            "required": ["session_id"],
            "properties": {"session_id": {"type": "string"}},
        },
        permission_required=AgentPermission.MANAGE_SESSION,
        handler=tool_session_start,
    )
    McpRegistry.register_tool(
        name="session.pause",
        description="Pause an active trading session temporarily.",
        input_schema={
            "type": "object",
            "required": ["session_id"],
            "properties": {
                "session_id": {"type": "string"},
                "reason": {"type": "string"},
            },
        },
        permission_required=AgentPermission.MANAGE_SESSION,
        handler=tool_session_pause,
    )
    McpRegistry.register_tool(
        name="session.resume",
        description="Resume a paused trading session.",
        input_schema={
            "type": "object",
            "required": ["session_id"],
            "properties": {"session_id": {"type": "string"}},
        },
        permission_required=AgentPermission.MANAGE_SESSION,
        handler=tool_session_resume,
    )
    McpRegistry.register_tool(
        name="session.stop",
        description="Cleanly terminate an active trading session.",
        input_schema={
            "type": "object",
            "required": ["session_id"],
            "properties": {
                "session_id": {"type": "string"},
                "reason": {"type": "string"},
            },
        },
        permission_required=AgentPermission.MANAGE_SESSION,
        handler=tool_session_stop,
    )
    McpRegistry.register_tool(
        name="session.get_status",
        description="Get live status, error budget, and health for trading sessions.",
        input_schema={
            "type": "object",
            "properties": {"session_id": {"type": "string"}},
        },
        permission_required=AgentPermission.MANAGE_SESSION,
        handler=tool_session_get_status,
    )
    McpRegistry.register_tool(
        name="session.emergency_stop",
        description="CRITICAL KILL-SWITCH: Instantly halt sessions and engage RiskEngine emergency stop.",
        input_schema={
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "reason": {"type": "string"},
            },
        },
        permission_required=AgentPermission.EMERGENCY_STOP,
        handler=tool_session_emergency_stop,
    )
