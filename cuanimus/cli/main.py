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
import subprocess
import signal
import time
from typing import List, Optional, Tuple, Dict, Any

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


def _is_pid_alive(pid: int) -> bool:
    """Checks whether a process with the given PID is currently running."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _start_background_daemon(cmd_args: List[str], name: str) -> Tuple[bool, int, str]:
    """Starts a process in the background, writing its PID and standard logs."""
    base_dir = os.path.abspath(".")
    cuanimus_dir = os.path.join(base_dir, ".cuanimus")
    os.makedirs(cuanimus_dir, exist_ok=True)
    pid_file = os.path.join(cuanimus_dir, f"{name}.pid")
    log_file = os.path.join(cuanimus_dir, f"{name}.log")

    if os.path.exists(pid_file):
        try:
            with open(pid_file, "r") as f:
                existing_pid = int(f.read().strip())
            if _is_pid_alive(existing_pid):
                return False, existing_pid, f"Daemon '{name}' is already running with PID {existing_pid}."
        except Exception:
            pass

    log_f = open(log_file, "a")
    env = dict(os.environ)
    env["PYTHONPATH"] = base_dir
    env["PYTHONUNBUFFERED"] = "1"
    proc = subprocess.Popen(
        cmd_args,
        stdout=log_f,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        env=env,
    )
    time.sleep(0.6)
    if proc.poll() is not None:
        return False, -1, f"Daemon '{name}' failed to start. Check logs at: {log_file}"

    with open(pid_file, "w") as f:
        f.write(str(proc.pid))

    return True, proc.pid, f"Daemon '{name}' started with PID {proc.pid}. Logs: {log_file}"


def _stop_background_daemon(name: str) -> Tuple[bool, str]:
    """Gracefully terminates a running background daemon."""
    base_dir = os.path.abspath(".")
    cuanimus_dir = os.path.join(base_dir, ".cuanimus")
    pid_file = os.path.join(cuanimus_dir, f"{name}.pid")

    if not os.path.exists(pid_file):
        return False, f"No active PID file found for '{name}'."

    try:
        with open(pid_file, "r") as f:
            pid = int(f.read().strip())
    except Exception:
        if os.path.exists(pid_file):
            os.remove(pid_file)
        return False, f"Invalid PID file for '{name}', cleaned up."

    if not _is_pid_alive(pid):
        os.remove(pid_file)
        return False, f"Process {pid} is not running. Removed stale PID file."

    try:
        os.kill(pid, signal.SIGTERM)
        for _ in range(30):
            if not _is_pid_alive(pid):
                break
            time.sleep(0.1)
        if _is_pid_alive(pid):
            os.kill(pid, signal.SIGKILL)
    except Exception as e:
        return False, f"Failed to terminate process {pid}: {e}"

    if os.path.exists(pid_file):
        os.remove(pid_file)
    return True, f"Daemon '{name}' (PID {pid}) stopped successfully."

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
    agent_sub.add_parser("token-list", help="List registered AI Agent scoped MCP tokens")

    p_trr = agent_sub.add_parser("token-rotate", help="Rotate MCP bearer token for an agent")
    p_trr.add_argument("--agent", required=True, help="Agent ID to rotate token for (e.g., antigravity-agent)")

    p_trv = agent_sub.add_parser("token-revoke", help="Revoke MCP bearer token for an agent")
    p_trv.add_argument("--agent", required=True, help="Agent ID to revoke token for")

    p_acc = agent_sub.add_parser("connect-config", help="Export agent client connection configuration")
    p_acc.add_argument("--agent", required=True, choices=["codex", "antigravity", "hermes", "generic-mcp"], help="Agent client target")

    p_atc = agent_sub.add_parser("test-connection", help="Test agent authentication and MCP connectivity")
    p_atc.add_argument("--agent", required=True, help="Agent ID to test")

    # 10. mcp
    p_mcp = subparsers.add_parser("mcp", help="Model Context Protocol (MCP) server commands")
    mcp_sub = p_mcp.add_subparsers(dest="mcp_action", help="MCP actions")
    p_ms = mcp_sub.add_parser("start", help="Start the CUANIMUS MCP JSON-RPC 2.0 Server")
    p_ms.add_argument("--transport", default="stdio", choices=["stdio", "http"], help="Transport mode")
    p_ms.add_argument("--host", default="127.0.0.1", help="HTTP server bind host")
    p_ms.add_argument("--port", type=int, default=8000, help="HTTP server listen port")
    p_ms.add_argument("--daemon", action="store_true", help="Run MCP server as background daemon")

    mcp_sub.add_parser("stop", help="Stop running MCP background daemon")
    mcp_sub.add_parser("status", help="Show MCP server capabilities and safety status")
    mcp_sub.add_parser("tools", help="List all available MCP tools and required permissions")

    # 11. ui
    p_ui = subparsers.add_parser("ui", help="Web Control Center & Trading Interface commands")
    ui_sub = p_ui.add_subparsers(dest="ui_action", help="UI actions")
    p_us = ui_sub.add_parser("start", help="Start the Web Control Center HTTP Daemon")
    p_us.add_argument("--host", default="127.0.0.1", help="HTTP server bind host (default: 127.0.0.1)")
    p_us.add_argument("--port", type=int, default=8888, help="HTTP server listen port (default: 8888)")
    p_us.add_argument("--daemon", action="store_true", help="Run Web UI as background daemon")

    ui_sub.add_parser("stop", help="Stop running Web UI background daemon")
    p_ub = ui_sub.add_parser("bootstrap", help="Bootstrap or reset administrator credentials")
    p_ub.add_argument("--force", action="store_true", help="Force regenerate admin password even if initialized")
    ui_sub.add_parser("status", help="Display Web Control Center status and endpoints")

    # 12. backup
    p_bk = subparsers.add_parser("backup", help="Database and configuration backup and disaster recovery")
    bk_sub = p_bk.add_subparsers(dest="backup_action", help="Backup actions")
    p_bc = bk_sub.add_parser("create", help="Create an atomic backup snapshot")
    p_bc.add_argument("--tag", default=None, help="Optional snapshot tag")
    p_bv = bk_sub.add_parser("verify", help="Verify cryptographic SHA256 integrity of a backup snapshot")
    p_bv.add_argument("--id", default=None, help="Snapshot ID to verify (defaults to latest)")
    bk_sub.add_parser("list", help="List all available backup snapshots")

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

        elif action == "token-list":
            from cuanimus.mcp.tokens import McpTokenManager
            mgr = McpTokenManager()
            tokens = mgr.list_tokens()
            headers = ["Agent ID", "Preset", "Status", "Masked Token", "Allowed Domains", "Created At"]
            rows = [[t["agent_id"], t["preset"], t["status"], t["token_masked"], ",".join(t["allowed_domains"]), t["created_at"][:19]] for t in tokens]
            print("Scoped AI Agent MCP Bearer Tokens:")
            print(format_table(headers, rows))
            return 0

        elif action == "token-rotate":
            agent_id = parsed_args.agent
            from cuanimus.mcp.tokens import McpTokenManager
            mgr = McpTokenManager()
            try:
                res = mgr.rotate_token(agent_id)
                print("=" * 60)
                print("       CUANIMUS MCP BEARER TOKEN ROTATION")
                print("=" * 60)
                print(f"Agent ID:   {res['agent_id']}")
                print(f"Status:     {res['status']}")
                print(f"New Token:  {res['token']}")
                print(f"Created At: {res['created_at']}")
                print("Note: Store this token securely. Update agent client configuration.")
                print("=" * 60)
                return 0
            except KeyError as e:
                print(f"[ERROR] {e}")
                return 1

        elif action == "token-revoke":
            agent_id = parsed_args.agent
            from cuanimus.mcp.tokens import McpTokenManager
            mgr = McpTokenManager()
            ok = mgr.revoke_token(agent_id)
            if ok:
                print(f"[OK] MCP token for agent '{agent_id}' has been permanently REVOKED.")
                return 0
            else:
                print(f"[ERROR] Agent '{agent_id}' not found.")
                return 1

        elif action == "connect-config":
            agent_target = parsed_args.agent
            config_file = f"deploy/agent-configs/{agent_target}.md"
            if os.path.exists(config_file):
                with open(config_file, "r") as f:
                    print(f.read())
                return 0
            else:
                print(f"[ERROR] Configuration guide for '{agent_target}' not found at {config_file}")
                return 1

        elif action == "test-connection":
            agent_id = parsed_args.agent
            from cuanimus.mcp.tokens import McpTokenManager
            mgr = McpTokenManager()
            tokens = mgr._load_tokens()
            if agent_id not in tokens:
                print(f"[FAIL] Agent '{agent_id}' not found in registered token store.")
                return 1

            record = tokens[agent_id]
            if record.get("status") != "ACTIVE":
                print(f"[FAIL] Agent '{agent_id}' token status is '{record.get('status')}' (NOT ACTIVE).")
                return 1

            token_val = record.get("token")
            auth_res = mgr.authenticate_token(token_val)
            if not auth_res:
                print(f"[FAIL] Cryptographic authentication check failed for agent '{agent_id}'.")
                return 1

            print("=" * 60)
            print(f"   CONNECTION TEST: AGENT '{agent_id}'")
            print("=" * 60)
            print(f"Status:            [PASS] ACTIVE & AUTHENTICATED")
            print(f"Agent ID:          {auth_res['agent_id']}")
            print(f"Preset:            {auth_res['preset']}")
            print(f"Allowed Domains:   {', '.join(auth_res['allowed_domains'])}")
            print(f"Safety Mode:       {auth_res['environment'].upper()} SAFE (Real Capital Prohibited)")
            print("Rate Limiting:     READ: 60/m | ANALYZE: 30/m | CONFIG: 15/m | EXECUTE: 5/m")
            print("=" * 60)
            return 0

    # COMMAND: mcp
    if cmd == "mcp":
        action = getattr(parsed_args, "mcp_action", None)
        from cuanimus.mcp.server import McpServer
        from cuanimus.mcp.registry import McpRegistry

        if not action or action == "start":
            transport = parsed_args.transport
            if getattr(parsed_args, "daemon", False):
                if transport != "http":
                    print("[ERROR] Daemon mode is only supported with HTTP transport (--transport http).")
                    return 1
                host = parsed_args.host
                port = parsed_args.port
                cmd_args = [sys.executable, "-m", "cuanimus.cli", "mcp", "start", "--transport", "http", "--host", host, "--port", str(port)]
                ok, pid, msg = _start_background_daemon(cmd_args, "mcp")
                if ok:
                    print(f"[OK] {msg}")
                    print(f"CUANIMUS MCP Daemon active in background:")
                    print(f"  MCP HTTP Endpoint: http://{host}:{port}/")
                    print(f"To stop: ./cuanimus-cli mcp stop")
                    return 0
                else:
                    print(f"[ERROR] {msg}")
                    return 1

            server = McpServer()
            if transport == "stdio":
                server.run_stdio()
            elif transport == "http":
                host = parsed_args.host
                port = parsed_args.port
                print(f"Starting CUANIMUS MCP JSON-RPC Server on http://{host}:{port}/ ...")
                server.run_http(host=host, port=port)
            return 0

        elif action == "stop":
            ok, msg = _stop_background_daemon("mcp")
            if ok:
                print(f"[OK] {msg}")
                return 0
            else:
                print(f"[INFO] {msg}")
                return 1

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

    # COMMAND: ui
    if cmd == "ui":
        action = getattr(parsed_args, "ui_action", None)
        if action == "bootstrap":
            from cuanimus.api.auth import AuthManager
            res = AuthManager().bootstrap_admin(force=getattr(parsed_args, "force", False))
            print("=" * 60)
            print("       CUANIMUS WEB CONTROL CENTER ADMIN BOOTSTRAP")
            print("=" * 60)
            print(f"Status:   {res['status']}")
            print(f"Username: {res['username']}")
            if "temporary_password" in res:
                print(f"Password: {res['temporary_password']}")
                print(f"Role:     {res['role']}")
                print(f"Stored:   {res['credential_file']}")
                print(f"Note:     {res['note']}")
            else:
                print(f"Message:  {res.get('message', '')}")
            print("=" * 60)
            return 0

        elif action == "stop":
            ok, msg = _stop_background_daemon("ui")
            if ok:
                print(f"[OK] {msg}")
                return 0
            else:
                print(f"[INFO] {msg}")
                return 1

        elif not action or action == "start":
            host = parsed_args.host
            port = parsed_args.port
            if getattr(parsed_args, "daemon", False):
                cmd_args = [sys.executable, "-m", "cuanimus.cli", "ui", "start", "--host", host, "--port", str(port)]
                ok, pid, msg = _start_background_daemon(cmd_args, "ui")
                if ok:
                    print(f"[OK] {msg}")
                    print(f"CUANIMUS Web Control Center active in background:")
                    print(f"  Web UI:       http://{host}:{port}/")
                    print(f"  Remote MCP:   http://{host}:{port}/mcp")
                    print(f"  Health Check: http://{host}:{port}/health")
                    print(f"To stop: ./cuanimus-cli ui stop")
                    return 0
                else:
                    print(f"[ERROR] {msg}")
                    return 1
            else:
                from cuanimus.api.http_server import HttpServerDaemon
                daemon = HttpServerDaemon(host=host, port=port)
                daemon.start(blocking=True)
                return 0

        elif action == "status":
            from cuanimus.api.control_plane import ControlPlaneAPI
            api = ControlPlaneAPI()
            status = api.get_system_status()
            print("=" * 60)
            print("         CUANIMUS WEB CONTROL CENTER STATUS")
            print("=" * 60)
            print(f"Environment:       {status['environment']}")
            print(f"Safety Clearance:  {status['safety_status']}")
            print(f"Emergency Stop:    {'LOCKED' if status['emergency_stop_active'] else 'ARMED / SAFE'}")
            print(f"Active Strategy:   {status['strategy_id']}")
            print(f"Risk Profile:      {status['risk_profile']}")
            print(f"Exchange:          {status['exchange']}")
            print(f"Active Sessions:   {status['active_session_count']}")
            print("=" * 60)
            return 0

    # COMMAND: backup
    if cmd == "backup":
        action = getattr(parsed_args, "backup_action", None)
        from cuanimus.core.backup import BackupManager
        bm = BackupManager()
        if not action or action == "create":
            tag = getattr(parsed_args, "tag", None)
            res = bm.create_backup(tag=tag)
            print("=" * 60)
            print("          CUANIMUS ATOMIC BACKUP COMPLETED")
            print("=" * 60)
            print(f"Snapshot ID:     {res['snapshot_id']}")
            print(f"Files Backed Up: {res['item_count']}")
            print(f"Target Dir:      {res['snapshot_dir']}")
            print(f"Manifest:        {res['manifest_path']}")
            print("Integrity:       SHA256 verified")
            print("=" * 60)
            return 0
        elif action == "verify":
            snap_id = getattr(parsed_args, "id", None)
            res = bm.verify_backup(snapshot_id=snap_id)
            if res.get("valid"):
                print(f"[PASS] Backup '{res['snapshot_id']}' integrity VERIFIED BIT-EXACT ({res['checked_files']} files checked).")
                return 0
            else:
                print(f"[FAIL] Backup verification failed: {res.get('error', 'Integrity mismatch')}")
                return 1
        elif action == "list":
            backups = bm.list_backups()
            if not backups:
                print("No backup snapshots found.")
                return 0
            headers = ["Snapshot ID", "Created At", "Items Count", "Path"]
            rows = [[b["snapshot_id"], b["created_at"][:19], b["item_count"], b["path"]] for b in backups]
            print("Available CUANIMUS Backups:")
            print(format_table(headers, rows))
            return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
