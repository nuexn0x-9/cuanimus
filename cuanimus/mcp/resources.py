"""
CUANIMUS MCP Resources.
Exposes read-only standard MCP resources for system status, configuration schemas,
and active risk limits.
"""
import json
from cuanimus.mcp.registry import McpRegistry
from cuanimus.config.loader import ConfigLoader
from cuanimus.config.schema import generate_json_schema
from cuanimus.agent.audit import redact_sensitive_data


def res_config_current(context) -> str:
    loader = ConfigLoader()
    _, raw = loader.load()
    return json.dumps(redact_sensitive_data(raw), indent=2)


def res_config_schema(context) -> str:
    schema = generate_json_schema()
    return json.dumps(schema, indent=2)


def res_system_status(context) -> str:
    loader = ConfigLoader()
    cfg, _ = loader.load()
    status = {
        "platform": "CUANIMUS",
        "environment": cfg.environment.env_name,
        "dry_run": cfg.environment.dry_run,
        "live_trading_enabled": cfg.environment.live_trading_enabled,
        "strategy": cfg.strategy.strategy_id,
        "risk_profile": cfg.risk.profile_name,
    }
    return json.dumps(status, indent=2)


def register_all_resources() -> None:
    McpRegistry.register_resource(
        uri="cuanimus://config/current",
        name="Current Active Configuration",
        description="Active merged configuration with credentials sanitized.",
        mime_type="application/json",
        handler=res_config_current,
    )
    McpRegistry.register_resource(
        uri="cuanimus://config/schema",
        name="Configuration JSON Schema",
        description="Full JSON Schema describing valid configuration parameters.",
        mime_type="application/json",
        handler=res_config_schema,
    )
    McpRegistry.register_resource(
        uri="cuanimus://system/status",
        name="System Status & Safety Locks",
        description="Current operational status, safety locks, and active profile.",
        mime_type="application/json",
        handler=res_system_status,
    )
