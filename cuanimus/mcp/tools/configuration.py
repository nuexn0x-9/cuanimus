"""
CUANIMUS MCP Configuration Tools.
Allows agents to read schemas, explain parameters, validate proposed configs,
and generate safe preview diffs via the Configuration Proposal Engine.
"""
from typing import Dict, Any, Optional
from cuanimus.agent.identity import AgentPermission
from cuanimus.mcp.registry import McpRegistry
from cuanimus.config.loader import ConfigLoader
from cuanimus.config.validator import ConfigValidator
from cuanimus.config.schema import generate_json_schema
from cuanimus.agent.proposal import ProposalEngine, ProposalStatus
from cuanimus.agent.audit import redact_sensitive_data
from cuanimus.cli.inspector import explain_parameters


_global_proposal_engine = ProposalEngine()


def tool_config_get_schema(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Returns the JSON Schema describing CUANIMUS configuration."""
    return generate_json_schema()


def tool_config_get_current(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Returns active merged configuration with all credentials sanitized."""
    profile = args.get("profile")
    loader = ConfigLoader()
    _, raw_cfg = loader.load(profile=profile)
    return redact_sensitive_data(raw_cfg)


def tool_config_validate(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Validates arbitrary configuration payload against schema and invariants."""
    raw_cfg = args.get("config", {})
    loader = ConfigLoader()
    validator = ConfigValidator()
    try:
        cfg_obj = loader._build_config_instance(raw_cfg)
        report = validator.validate(cfg_obj)
        return report.to_dict()
    except Exception as e:
        return {
            "is_valid": False,
            "safety_status": "ERROR",
            "errors": [f"Configuration build error: {str(e)}"],
            "warnings": [],
        }


def tool_config_explain(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Explains a configuration parameter or domain section."""
    param_path = args.get("parameter")
    loader = ConfigLoader()
    _, raw_cfg = loader.load()
    explanation = explain_parameters(raw_cfg, param_path)
    return {"parameter": param_path, "explanation": explanation}


def tool_config_get_profiles(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Lists pre-packaged environment, strategy, and risk configuration profiles."""
    loader = ConfigLoader()
    profiles = loader.list_available_profiles()
    return {"available_profiles": profiles}


def tool_config_preview(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Creates a non-destructive Configuration Proposal.
    Calculates deep delta diff and runs safety invariant validation.
    """
    modifications = args.get("modifications", {})
    rationale = args.get("rationale", "Agent assisted parameter tuning")
    base_profile = args.get("base_profile")
    agent_id = context.get("agent_id", "mcp-agent")

    proposal = _global_proposal_engine.create_proposal(
        agent_id=agent_id,
        rationale=rationale,
        modifications=modifications,
        base_profile=base_profile,
    )

    return proposal.to_dict()


def tool_config_apply(args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Applies an approved or valid Configuration Proposal to cuanimus.user.yaml.
    """
    proposal_id = args.get("proposal_id")
    target_file = args.get("target_file", "cuanimus.user.yaml")
    if not proposal_id:
        raise ValueError("Missing required 'proposal_id'")

    return _global_proposal_engine.apply_proposal(proposal_id, target_file)


def register_configuration_tools() -> None:
    McpRegistry.register_tool(
        name="config.get_schema",
        description="Get the full JSON Schema definition for CUANIMUS configuration.",
        input_schema={"type": "object", "properties": {}},
        permission_required=AgentPermission.READ_SYSTEM,
        handler=tool_config_get_schema,
    )
    McpRegistry.register_tool(
        name="config.get_current",
        description="Get active configuration (credentials securely redacted).",
        input_schema={
            "type": "object",
            "properties": {"profile": {"type": "string", "description": "Optional preset profile name"}},
        },
        permission_required=AgentPermission.READ_SYSTEM,
        handler=tool_config_get_current,
    )
    McpRegistry.register_tool(
        name="config.validate",
        description="Validate a candidate configuration dictionary against schema and safety invariants.",
        input_schema={
            "type": "object",
            "required": ["config"],
            "properties": {"config": {"type": "object", "description": "Configuration dictionary to validate"}},
        },
        permission_required=AgentPermission.CONFIGURE,
        handler=tool_config_validate,
    )
    McpRegistry.register_tool(
        name="config.explain",
        description="Explain the purpose, allowed range, and risk impact of a config parameter or path.",
        input_schema={
            "type": "object",
            "properties": {"parameter": {"type": "string", "description": "e.g. risk.risk_per_trade_pct"}},
        },
        permission_required=AgentPermission.READ_SYSTEM,
        handler=tool_config_explain,
    )
    McpRegistry.register_tool(
        name="config.get_profiles",
        description="List all available preset profiles (beginner, conservative, balanced, aggressive).",
        input_schema={"type": "object", "properties": {}},
        permission_required=AgentPermission.READ_SYSTEM,
        handler=tool_config_get_profiles,
    )
    McpRegistry.register_tool(
        name="config.preview",
        description="Propose configuration modifications. Returns delta diff and invariant verification without applying.",
        input_schema={
            "type": "object",
            "required": ["modifications"],
            "properties": {
                "modifications": {"type": "object", "description": "Nested dictionary of modified fields"},
                "rationale": {"type": "string", "description": "Reasoning for the change"},
                "base_profile": {"type": "string", "description": "Optional base profile"},
            },
        },
        permission_required=AgentPermission.CONFIGURE,
        handler=tool_config_preview,
    )
    McpRegistry.register_tool(
        name="config.apply",
        description="Apply an approved configuration proposal to the user configuration file.",
        input_schema={
            "type": "object",
            "required": ["proposal_id"],
            "properties": {
                "proposal_id": {"type": "string", "description": "ID returned by config.preview"},
                "target_file": {"type": "string", "description": "Destination file path"},
            },
        },
        permission_required=AgentPermission.CONFIGURE,
        handler=tool_config_apply,
    )
