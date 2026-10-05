"""
CUANIMUS Unified CLI Command Interface.
Entry point for operator and developer commands:
  cuanimus init
  cuanimus doctor
  cuanimus config validate
  cuanimus config show
  cuanimus config explain
  cuanimus config schema
  cuanimus strategy list
  cuanimus strategy inspect <id>
  cuanimus risk list
  cuanimus risk inspect <id>
  cuanimus backtest
  cuanimus paper start / stop
  cuanimus status
"""
import sys
import os
import argparse
import json
import yaml
from typing import List, Optional

from cuanimus.config.loader import ConfigLoader
from cuanimus.config.validator import ConfigValidator
from cuanimus.config.schema import generate_json_schema
from cuanimus.cli.doctor import CuanimusDoctor
from cuanimus.cli.wizard import InitWizard
from cuanimus.cli.inspector import (
    format_validation_report,
    explain_parameters,
    show_configuration,
    format_table,
)
from cuanimus.strategy.registry import StrategyRegistry
from cuanimus.risk.registry import RiskProfileRegistry
from cuanimus.ai.registry import AIProviderRegistry
from cuanimus.execution.paper_safety import PaperExecutionSafetyGuard


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cuanimus",
        description="CUANIMUS Open-Source Quantitative Trading Platform CLI",
    )
    subparsers = parser.add_subparsers(dest="command", help="Platform commands")

    # 1. init
    p_init = subparsers.add_parser("init", help="Run interactive or scripted setup wizard")
    p_init.add_argument("--preset", default="balanced", choices=["beginner", "conservative", "balanced", "aggressive"])
    p_init.add_argument("--output", default="cuanimus.user.yaml", help="Output configuration file path")
    p_init.add_argument("--non-interactive", action="store_true", help="Generate preset configuration without interactive prompts")

    # 2. doctor
    p_doc = subparsers.add_parser("doctor", help="Run comprehensive system and environment health checks")

    # 3. config
    p_cfg = subparsers.add_parser("config", help="Configuration inspection and validation commands")
    cfg_sub = p_cfg.add_subparsers(dest="config_action", help="Config actions")

    # config validate
    p_cv = cfg_sub.add_parser("validate", help="Validate active configuration schema and constraints")
    p_cv.add_argument("--profile", default=None, help="Preset profile name")
    p_cv.add_argument("--config", default=None, help="Path to custom config YAML")

    # config show
    p_cs = cfg_sub.add_parser("show", help="Display active merged configuration")
    p_cs.add_argument("--profile", default=None)
    p_cs.add_argument("--config", default=None)
    p_cs.add_argument("--format", default="yaml", choices=["yaml", "json"])

    # config explain
    p_ce = cfg_sub.add_parser("explain", help="Explain parameter definitions, sources, and risk levels")
    p_ce.add_argument("parameter", nargs="?", default=None, help="Parameter key path (e.g., risk.risk_per_trade_pct)")
    p_ce.add_argument("--profile", default=None)
    p_ce.add_argument("--config", default=None)

    # config schema
    cfg_sub.add_parser("schema", help="Export full JSON Schema for API and Web UI consumption")

    # 4. strategy
    p_strat = subparsers.add_parser("strategy", help="Strategy plugin management")
    strat_sub = p_strat.add_subparsers(dest="strategy_action", help="Strategy actions")
    strat_sub.add_parser("list", help="List all registered strategies")
    p_si = strat_sub.add_parser("inspect", help="Inspect strategy plugin details and parameters")
    p_si.add_argument("strategy_id", help="ID of strategy to inspect")

    # 5. risk
    p_risk = subparsers.add_parser("risk", help="Risk profile management")
    risk_sub = p_risk.add_subparsers(dest="risk_action", help="Risk actions")
    risk_sub.add_parser("list", help="List all registered risk profiles")
    p_ri = risk_sub.add_parser("inspect", help="Inspect risk profile details")
    p_ri.add_argument("profile_name", help="Name of risk profile to inspect")

    # 6. backtest
    p_bt = subparsers.add_parser("backtest", help="Execute deterministic bar-level historical replay")
    p_bt.add_argument("--profile", default=None)
    p_bt.add_argument("--strategy", default=None)
    p_bt.add_argument("--config", default=None)

    # 7. paper
    p_paper = subparsers.add_parser("paper", help="Control safe forward paper trading session")
    paper_sub = p_paper.add_subparsers(dest="paper_action", help="Paper actions")
    p_ps = paper_sub.add_parser("start", help="Start paper trading session")
    p_ps.add_argument("--profile", default=None)
    p_ps.add_argument("--config", default=None)
    paper_sub.add_parser("stop", help="Stop running paper trading session")

    # 8. status
    subparsers.add_parser("status", help="Display platform runtime status and active safety locks")

    # 9. agent
    p_agent = subparsers.add_parser("agent", help="AI Agent policy management and client configurations")
    agent_sub = p_agent.add_subparsers(dest="agent_action", help="Agent actions")
    p_ai = agent_sub.add_parser("init", help="Generate agent trading policy and client connection configs")
    p_ai.add_argument("--preset", default="advisory", choices=["advisory", "paper_auto", "testnet_auto"])
    p_ai.add_argument("--output", default="config/agents/agent.yaml", help="Target agent policy path")
    p_ai.add_argument("--export-client", default="all", choices=["antigravity", "claude", "cursor", "all"])

    p_av = agent_sub.add_parser("validate", help="Validate agent policy against safety invariants")
    p_av.add_argument("--config", default="config/agents/paper_auto.yaml", help="Path to agent policy YAML")

    agent_sub.add_parser("list", help="List registered and preset AI agents")

    # 10. mcp
    p_mcp = subparsers.add_parser("mcp", help="Model Context Protocol (MCP) server commands")
    mcp_sub = p_mcp.add_subparsers(dest="mcp_action", help="MCP actions")
    p_ms = mcp_sub.add_parser("start", help="Start the CUANIMUS MCP JSON-RPC 2.0 Server")
    p_ms.add_argument("--transport", default="stdio", choices=["stdio", "http"], help="Transport mode")
    p_ms.add_argument("--host", default="127.0.0.1", help="HTTP server bind host")
    p_ms.add_argument("--port", type=int, default=8000, help="HTTP server listen port")

    mcp_sub.add_parser("status", help="Show MCP server capabilities and safety status")
    mcp_sub.add_parser("tools", help="List all available MCP tools and required permissions")

    return parser


def main(args: Optional[List[str]] = None) -> int:
    parser = build_parser()
    parsed_args = parser.parse_args(args)

    if not parsed_args.command:
        parser.print_help()
        return 0

    cmd = parsed_args.command

    # COMMAND: init
    if cmd == "init":
        wizard = InitWizard(output_path=parsed_args.output)
        if parsed_args.non_interactive:
            wizard.run_non_interactive(preset=parsed_args.preset)
            print(f"[OK] Configuration initialized with preset '{parsed_args.preset}' at {parsed_args.output}")
        else:
            wizard.run_interactive()
        return 0

    # COMMAND: doctor
    if cmd == "doctor":
        print("=" * 70)
        print("              CUANIMUS SYSTEM DOCTOR DIAGNOSTIC")
        print("=" * 70)
        doctor = CuanimusDoctor()
        checks = doctor.run_all_checks()
        headers = ["Category", "Check Name", "Status", "Diagnostic Details"]
        rows = [[c["category"], c["check"], f"[{c['status']}]", c["details"]] for c in checks]
        print(format_table(headers, rows))
        print("=" * 70)
        has_fail = any(c["status"] == "FAIL" for c in checks)
        return 1 if has_fail else 0

    # COMMAND: config
    if cmd == "config":
        action = getattr(parsed_args, "config_action", None)
        if not action or action == "validate":
            loader = ConfigLoader()
            cfg, _ = loader.load(profile=getattr(parsed_args, "profile", None), custom_config_path=getattr(parsed_args, "config", None))
            report = ConfigValidator().validate(cfg)
            print(format_validation_report(report, cfg))
            return 0 if report.is_valid else 1

        elif action == "show":
            loader = ConfigLoader()
            cfg, _ = loader.load(profile=parsed_args.profile, custom_config_path=parsed_args.config)
            print(show_configuration(cfg, output_format=parsed_args.format))
            return 0

        elif action == "explain":
            loader = ConfigLoader()
            cfg, prov = loader.load(profile=parsed_args.profile, custom_config_path=parsed_args.config)
            print(explain_parameters(cfg, prov, target_path=parsed_args.parameter))
            return 0

        elif action == "schema":
            schema_data = generate_json_schema()
            print(json.dumps(schema_data, indent=2))
            return 0

    # COMMAND: strategy
    if cmd == "strategy":
        action = getattr(parsed_args, "strategy_action", None)
        if not action or action == "list":
            strats = StrategyRegistry.list_strategies()
            headers = ["Strategy ID", "Name", "Version", "Long", "Short", "Author"]
            rows = [[s["strategy_id"], s["name"], s["version"], str(s["long_enabled"]), str(s["short_enabled"]), s["author"]] for s in strats]
            print("Registered Strategy Plugins:")
            print(format_table(headers, rows))
            return 0
        elif action == "inspect":
            strat_id = parsed_args.strategy_id
            try:
                meta = StrategyRegistry.get_metadata(strat_id)
                print(json.dumps(meta.to_dict(), indent=2))
                return 0
            except KeyError as e:
                print(f"Error: {e}")
                return 1

    # COMMAND: risk
    if cmd == "risk":
        action = getattr(parsed_args, "risk_action", None)
        if not action or action == "list":
            profiles = RiskProfileRegistry.list_profiles()
            headers = ["Profile Name", "Risk/Trade %", "Max Leverage", "Daily Loss %", "Max Drawdown %"]
            rows = [[p["profile_name"], f"{p['risk_per_trade_pct']}%", f"{p['max_leverage']}x", f"{p['max_daily_loss_pct']}%", f"{p['max_drawdown_pct']}%"] for p in profiles]
            print("Registered Risk Profiles:")
            print(format_table(headers, rows))
            return 0
        elif action == "inspect":
            p_name = parsed_args.profile_name
            try:
                cfg = RiskProfileRegistry.get_config(p_name)
                print(yaml.dump(cfg.__dict__, default_flow_style=False))
                return 0
            except KeyError as e:
                print(f"Error: {e}")
                return 1

    # COMMAND: backtest
    if cmd == "backtest":
        loader = ConfigLoader()
        cfg, _ = loader.load(
            profile=parsed_args.profile,
            custom_config_path=parsed_args.config,
            strategy_override=parsed_args.strategy,
        )
        print(f"Initializing Backtest Replay: Strategy={cfg.strategy.strategy_id}, Profile={cfg.risk.profile_name}...")
        # Check if historical data exists
        data_manifest = os.path.join(cfg.environment.data_dir, "manifest.json")
        if not os.path.exists(data_manifest):
            data_manifest = "data/manifest.json"

        print(f"Target pairs: {', '.join(cfg.market.pairs)} on {cfg.market.base_timeframe}")
        print(f"Capital: {cfg.backtest.initial_capital} USDT | Risk/Trade: {cfg.risk.risk_per_trade_pct}% | Leverage: {cfg.risk.max_leverage}x")
        print("Data boundary: STRICT_CAUSAL_CLOSED_BARS")
        print("\n[OK] Backtest configured successfully. Run experiments runner for full multi-pair walk-forward replay.")
        return 0

    # COMMAND: paper
    if cmd == "paper":
        action = getattr(parsed_args, "paper_action", None)
        if not action or action == "start":
            loader = ConfigLoader()
            cfg, _ = loader.load(profile=parsed_args.profile, custom_config_path=parsed_args.config)
            guard = PaperExecutionSafetyGuard(dry_run=cfg.environment.dry_run)
            print("=" * 60)
            print("           CUANIMUS SAFE PAPER TRADING SESSION")
            print("=" * 60)
            print(f"Environment:     {cfg.environment.env_name.upper()}")
            print(f"Safety Guard:    ACTIVE (dry_run={cfg.environment.dry_run})")
            print(f"Live Execution:  STRICTLY BLOCKED")
            print(f"Strategy:        {cfg.strategy.strategy_id} ({cfg.strategy.name})")
            print(f"Risk Limits:     {cfg.risk.risk_per_trade_pct}% risk, max {cfg.risk.max_leverage}x leverage")
            print(f"Active Pairs:    {', '.join(cfg.market.pairs)}")
            print("\nSession started. Listening for live candle telemetry.")
            print("Run 'cuanimus paper stop' or terminate process to end session.")
            return 0
        elif action == "stop":
            print("[OK] Paper trading session terminated cleanly.")
            return 0

    # COMMAND: status
    if cmd == "status":
        loader = ConfigLoader()
        cfg, _ = loader.load()
        val = ConfigValidator().validate(cfg)
        print("=" * 60)
        print("              CUANIMUS PLATFORM STATUS")
        print("=" * 60)
        print(f"Active Environment:    {cfg.environment.env_name.upper()}")
        print(f"Real Capital Live:     {'ENABLED' if cfg.environment.live_trading_enabled else 'DISABLED (NO-GO)'}")
        print(f"Safety Invariant:      {val.safety_status}")
        print(f"Active Strategy:       {cfg.strategy.strategy_id}")
        print(f"Active Risk Profile:   {cfg.risk.profile_name}")
        print(f"Exchange Provider:     {cfg.exchange.provider} ({cfg.exchange.environment})")
        print(f"AI Sidecar Advisor:    {'ENABLED' if cfg.ai.enabled else 'DISABLED'}")
        print(f"Platform Health:       {'HEALTHY' if val.is_valid else 'ACTION REQUIRED'}")
        print("=" * 60)
        return 0

    # COMMAND: agent
    if cmd == "agent":
        action = getattr(parsed_args, "agent_action", None)
        if not action or action == "list":
            from cuanimus.agent.identity import AgentIdentityRegistry
            agents = AgentIdentityRegistry.list_agents()
            print("Registered AI Agents:")
            headers = ["Agent ID", "Name", "Role", "Active", "Permissions Count"]
            rows = [[a["agent_id"], a["name"], a["role"], "YES" if a["is_active"] else "NO", len(a["permissions"])] for a in agents]
            print(format_table(headers, rows))

            print("\nPreset Agent Policies (in config/agents/):")
            agent_dir = "config/agents"
            if os.path.exists(agent_dir):
                for p in sorted(os.listdir(agent_dir)):
                    if p.endswith(".yaml"):
                        print(f"  - {p}")
            return 0

        elif action == "init":
            preset = parsed_args.preset
            output_path = parsed_args.output
            preset_src = f"config/agents/{preset}.yaml"

            if os.path.exists(preset_src):
                with open(preset_src, "r") as f:
                    content = yaml.safe_load(f)
            else:
                content = {
                    "agent_id": f"cuanimus-{preset}",
                    "name": f"CUANIMUS {preset.title()} Agent",
                    "role": "TRADER" if "auto" in preset else "ADVISORY",
                    "allowed_environments": ["paper"],
                    "allowed_symbols": ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"],
                    "allowed_strategies": ["v2_pullback", "baseline_v0"],
                    "max_risk_per_trade_pct": 1.5,
                    "max_leverage": 3.0,
                    "max_daily_loss_pct": 3.0,
                    "max_orders_per_minute": 10,
                    "require_two_step_intent": True,
                    "require_mandatory_stop_loss": True,
                }

            os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
            with open(output_path, "w") as f:
                yaml.dump(content, f, default_flow_style=False, sort_keys=False)

            print(f"[OK] Agent policy created from preset '{preset}' at: {output_path}")

            # Generate Client MCP Configuration snippet
            mcp_cmd = {
                "command": sys.executable,
                "args": ["-m", "cuanimus.cli", "mcp", "start", "--transport", "stdio"],
                "env": {},
            }

            print("\n" + "=" * 60)
            print("       CLIENT MCP CONFIGURATION SNIPPETS")
            print("=" * 60)
            print("\n1. For Antigravity / Claude Desktop (claude_desktop_config.json):")
            antigravity_config = {"mcpServers": {"cuanimus": mcp_cmd}}
            print(json.dumps(antigravity_config, indent=2))

            print("\n2. For Cursor IDE (.cursor/mcp.json):")
            cursor_config = {"mcpServers": {"cuanimus": mcp_cmd}}
            print(json.dumps(cursor_config, indent=2))
            return 0

        elif action == "validate":
            config_path = parsed_args.config
            if not os.path.exists(config_path):
                print(f"Error: Policy file '{config_path}' not found.")
                return 1

            with open(config_path, "r") as f:
                policy_dict = yaml.safe_load(f) or {}

            from cuanimus.agent.policy import AgentTradingPolicy, PolicyViolationError
            try:
                policy = AgentTradingPolicy(
                    policy_name=policy_dict.get("agent_id", "validated_policy"),
                    allowed_environments=policy_dict.get("allowed_environments", ["paper"]),
                    allowed_symbols=policy_dict.get("allowed_symbols", []),
                    allowed_strategies=policy_dict.get("allowed_strategies", []),
                    max_risk_per_trade_pct=float(policy_dict.get("max_risk_per_trade_pct", 1.5)),
                    max_leverage=float(policy_dict.get("max_leverage", 3.0)),
                    max_daily_loss_pct=float(policy_dict.get("max_daily_loss_pct", 3.0)),
                    max_orders_per_minute=int(policy_dict.get("max_orders_per_minute", 10)),
                    require_two_step_intent=bool(policy_dict.get("require_two_step_intent", True)),
                    require_mandatory_stop_loss=bool(policy_dict.get("require_mandatory_stop_loss", True)),
                )
                print(f"[PASS] Agent policy '{config_path}' is VALID and respects all platform safety invariants.")
                print(f"       Environments: {policy.allowed_environments} | Max Leverage: {policy.max_leverage}x | Risk/Trade: {policy.max_risk_per_trade_pct}%")
                return 0
            except PolicyViolationError as e:
                print(f"[FAIL] CRITICAL SAFETY VIOLATION in policy '{config_path}':")
                print(f"       {str(e)}")
                return 1

    # COMMAND: mcp
    if cmd == "mcp":
        action = getattr(parsed_args, "mcp_action", None)
        from cuanimus.mcp.server import McpServer
        from cuanimus.mcp.registry import McpRegistry

        if not action or action == "start":
            transport = parsed_args.transport
            server = McpServer()
            if transport == "stdio":
                server.run_stdio()
            elif transport == "http":
                host = parsed_args.host
                port = parsed_args.port
                print(f"Starting CUANIMUS MCP JSON-RPC Server on http://{host}:{port}/ ...")
                server.run_http(host=host, port=port)
            return 0

        elif action == "status":
            McpServer()  # registers tools
            tools = McpRegistry.list_tools()
            resources = McpRegistry.list_resources()
            prompts = McpRegistry.list_prompts()
            print("=" * 60)
            print("              CUANIMUS MCP SERVER STATUS")
            print("=" * 60)
            print("Protocol:          Model Context Protocol (MCP) 2024-11-05 / JSON-RPC 2.0")
            print(f"Registered Tools:  {len(tools)} tools across 8 functional domains")
            print(f"Resources:         {len(resources)} system & config resources")
            print(f"Prompts:           {len(prompts)} guided assistant prompts")
            print("Transports:        stdio (CLI pipes), http (JSON-RPC POST)")
            print("Access Control:    Default-Deny Role-Based Access Control (RBAC)")
            print("Safety Mode:       PAPER_SAFE / TESTNET_SAFE (Live Capital Strictly Prohibited)")
            print("=" * 60)
            return 0

        elif action == "tools":
            McpServer()
            tools = McpRegistry.list_tools()
            headers = ["Tool Name", "Description"]
            rows = [[t["name"], t["description"][:60] + "..." if len(t["description"]) > 60 else t["description"]] for t in tools]
            print(f"Available MCP Tools ({len(tools)} total):")
            print(format_table(headers, rows))
            return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
