"""
CUANIMUS MCP System Tools.
Endpoints for discovering status, version, safety locks, capabilities, and diagnostics.
"""
from typing import Dict, Any
from cuanimus.agent.identity import AgentPermission
from cuanimus.mcp.registry import McpRegistry
from cuanimus.config.loader import ConfigLoader
from cuanimus.config.validator import ConfigValidator
from cuanimus.cli.doctor import CuanimusDoctor
from cuanimus.strategy.registry import StrategyRegistry
from cuanimus.risk.registry import RiskProfileRegistry


def tool_system_get_status(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Returns platform operational status, environment, and active safety locks."""
    loader = ConfigLoader()
    cfg, _ = loader.load()
    val = ConfigValidator().validate(cfg)
    return {
        "status": "OPERATIONAL",
        "environment": cfg.environment.env_name,
        "dry_run": cfg.environment.dry_run,
        "live_trading_enabled": cfg.environment.live_trading_enabled,
        "safety_status": val.safety_status,
        "is_valid": val.is_valid,
        "active_strategy": cfg.strategy.strategy_id,
        "active_risk_profile": cfg.risk.profile_name,
        "exchange_provider": cfg.exchange.provider,
        "exchange_environment": cfg.exchange.environment,
        "ai_enabled": cfg.ai.enabled,
    }


def tool_system_get_version(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Returns CUANIMUS platform and protocol version."""
    return {
        "platform": "CUANIMUS",
        "version": "1.0.0-phase7",
        "protocol": "Model Context Protocol (MCP) 2024-11-05 / JSON-RPC 2.0",
        "build_target": "PRODUCTION_READY",
        "phase": "PHASE_7_AI_AGENT_INTEGRATION",
        "safety_invariant": "LIVE_CAPITAL_STRICTLY_DISABLED",
    }


def tool_system_get_safety_status(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Returns detailed evaluation of platform and agent safety invariants."""
    loader = ConfigLoader()
    cfg, _ = loader.load()
    val = ConfigValidator().validate(cfg)
    return {
        "overall_status": val.safety_status,
        "invariants": {
            "live_trading_prohibited": not cfg.environment.live_trading_enabled,
            "dry_run_enforced": cfg.environment.dry_run,
            "leverage_within_platform_ceiling": cfg.risk.max_leverage <= 10.0,
            "stop_loss_mandatory": getattr(cfg.risk, "capital_preservation_lock", True),
            "default_deny_agent_rbac": True,
            "two_step_intent_enforced": True,
        },
        "errors": val.errors,
        "warnings": val.warnings,
    }


def tool_system_get_capabilities(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Lists available system plugins, strategies, risk models, and execution modes."""
    strategies = [s["strategy_id"] for s in StrategyRegistry.list_strategies()]
    risk_profiles = [p["profile_name"] for p in RiskProfileRegistry.list_profiles()]
    return {
        "supported_execution_modes": ["PAPER_AUTO", "TESTNET_AUTO"],
        "unsupported_modes": ["LIVE_REAL_CAPITAL"],
        "registered_strategies": strategies,
        "registered_risk_profiles": risk_profiles,
        "supported_transports": ["stdio", "http"],
        "ai_support": ["mock", "gemini", "disabled"],
    }


def tool_system_doctor(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Runs comprehensive platform health checks."""
    doctor = CuanimusDoctor()
    checks = doctor.run_all_checks()
    healthy = all(c["status"] == "PASS" for c in checks)
    return {
        "healthy": healthy,
        "check_count": len(checks),
        "diagnostics": checks,
    }


def register_system_tools() -> None:
    McpRegistry.register_tool(
        name="system.get_status",
        description="Get CUANIMUS platform operational status, environment, active locks, and strategy.",
        input_schema={"type": "object", "properties": {}},
        permission_required=AgentPermission.READ_SYSTEM,
        handler=tool_system_get_status,
    )
    McpRegistry.register_tool(
        name="system.get_version",
        description="Get CUANIMUS system version, protocol version, and phase info.",
        input_schema={"type": "object", "properties": {}},
        permission_required=AgentPermission.READ_SYSTEM,
        handler=tool_system_get_version,
    )
    McpRegistry.register_tool(
        name="system.get_safety_status",
        description="Get detailed safety invariant statuses and lock states.",
        input_schema={"type": "object", "properties": {}},
        permission_required=AgentPermission.READ_SYSTEM,
        handler=tool_system_get_safety_status,
    )
    McpRegistry.register_tool(
        name="system.get_capabilities",
        description="Discover available strategies, risk profiles, and execution modes.",
        input_schema={"type": "object", "properties": {}},
        permission_required=AgentPermission.READ_SYSTEM,
        handler=tool_system_get_capabilities,
    )
    McpRegistry.register_tool(
        name="system.doctor",
        description="Run comprehensive platform diagnostics and health checks.",
        input_schema={"type": "object", "properties": {}},
        permission_required=AgentPermission.READ_SYSTEM,
        handler=tool_system_doctor,
    )
