# CUANIMUS — Open-Source Algorithmic Crypto Trading Platform

[![CI Tests](https://img.shields.io/badge/tests-138%20passed-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()
[![MCP](https://img.shields.io/badge/MCP-2024--11--05-purple.svg)]()
[![Live Capital](https://img.shields.io/badge/live%20capital-STRICTLY%20NO--GO-red.svg)]()

**CUANIMUS** is a modular, research-driven, open-source algorithmic crypto trading platform designed for systematic quant research, rigorous causal backtesting, paper trading, and agent-assisted execution.

---

## Key Architectural Principles

1. **Configuration Over Hardcoding:** Configure trading pairs, risk profiles, execution parameters, and indicator thresholds without editing core Python code.
2. **Strict Information Boundaries:** True bar-by-bar causal replay ($t \le T$) with zero lookahead bias, confirmed fractal swings, and causal multi-timeframe alignment.
3. **Independent Risk Authority:** Sizing and portfolio safeguards operate independently of strategy signal generators.
4. **Decoupled Architecture:** Strategy plugins emit pure intentions (`TradeIntent`), never touching exchange APIs directly.
5. **Safety-First Invariants:** Mandatory air-gapped paper trading guards; live capital trading is **strictly disabled** by default.
6. **AI Agent Accessible (MCP Gateway):** Full Model Context Protocol (MCP) integration over `stdio` and `http` allowing AI agents (Antigravity, Codex, Claude Desktop, Cursor) to analyze markets, propose configurations, and automate paper trading safely.

---

## Quick Start (5 Steps)

```bash
# 1. Clone repository
git clone https://github.com/nuexn0x-9/cuanimus.git
cd cuanimus

# 2. Run system doctor diagnostics
./cuanimus-cli doctor

# 3. Initialize your configuration using the balanced preset
./cuanimus-cli init --preset balanced

# 4. Validate configuration integrity and safety invariants
./cuanimus-cli config validate

# 5. Run deterministic historical backtest or start paper trading
./cuanimus-cli backtest --profile balanced
./cuanimus-cli paper start --profile balanced
```

---

## AI Agent Integration & Autonomous Paper Trading (Phase 7)

CUANIMUS provides native support for AI agents through the **Model Context Protocol (MCP)**:

```bash
# Initialize agent policy and generate client MCP config snippets
./cuanimus-cli agent init --preset paper_auto

# Validate agent policy against platform safety invariants
./cuanimus-cli agent validate --config config/agents/paper_auto.yaml

# Start MCP Server via stdio for Antigravity or Claude Desktop
./cuanimus-cli mcp start --transport stdio

# Or start MCP Server via HTTP JSON-RPC POST on port 8000
./cuanimus-cli mcp start --transport http --port 8000
```

Add CUANIMUS to your `claude_desktop_config.json` or `.cursor/mcp.json`:
```json
{
  "mcpServers": {
    "cuanimus": {
      "command": "python3",
      "args": ["-m", "cuanimus.cli", "mcp", "start", "--transport", "stdio"],
      "env": {}
    }
  }
}
```

---

## Configuration Hierarchy

CUANIMUS organizes configuration hierarchically in [`config/`](config/):

```text
config/
├── defaults.yaml               # Global platform fallbacks
├── strategies/                 # Strategy algorithms (baseline_v0, pullback_v2a, structure_v2b, hybrid_v2c)
├── risk/                       # Risk management profiles (conservative, balanced, aggressive)
├── execution/                  # Execution models (conservative, balanced, aggressive)
├── exchanges/                  # Exchange connection profiles (binance_futures, mock_exchange)
├── environments/               # Operational environments (research, backtest, paper, testnet, live)
├── agents/                     # Agent trading policies (advisory, paper_auto, testnet_auto)
└── profiles/                   # Complete pre-packaged presets (beginner, conservative, balanced, aggressive)
```

Settings resolve using strict layered precedence:
$$\text{Defaults} \longrightarrow \text{Profile} \longrightarrow \text{Subsystem YAMLs} \longrightarrow \text{Environment Variables} \longrightarrow \text{Overrides}$$

---

## CLI Command Reference

| Command | Description |
| :--- | :--- |
| `./cuanimus-cli init` | Interactive terminal wizard to configure trading profiles and environments. |
| `./cuanimus-cli doctor` | Comprehensive 12-point system, environment, clock, and secret health check. |
| `./cuanimus-cli config validate` | Validates configuration against typed schemas and platform safety invariants. |
| `./cuanimus-cli config show` | Outputs active merged configuration in YAML or JSON format. |
| `./cuanimus-cli config explain <param>`| Explains parameter source, allowed range, risk level, and mutability policy. |
| `./cuanimus-cli config schema` | Exports complete JSON Schema Draft 2020-12 for Web UI form generation. |
| `./cuanimus-cli strategy list` | Lists all registered strategy plugins with version and trade direction support. |
| `./cuanimus-cli strategy inspect <id>` | Displays parameter specifications and metadata for a specific strategy plugin. |
| `./cuanimus-cli risk list` | Lists all registered risk profiles with risk/trade and leverage limits. |
| `./cuanimus-cli risk inspect <name>` | Displays detailed risk boundaries, drawdown limits, and cooldown timers. |
| `./cuanimus-cli backtest` | Launches deterministic bar-level replay across historical OHLCV data. |
| `./cuanimus-cli paper start` | Starts a safe, in-memory forward paper trading session. |
| `./cuanimus-cli status` | Displays platform runtime status, active environment, and safety locks. |
| `./cuanimus-cli agent init` | Generates agent trading policy and client connection configurations. |
| `./cuanimus-cli agent validate` | Validates agent policy against platform institutional ceilings. |
| `./cuanimus-cli agent list` | Lists registered AI agents and preset policy files. |
| `./cuanimus-cli mcp start` | Starts the CUANIMUS Model Context Protocol JSON-RPC 2.0 Server. |
| `./cuanimus-cli mcp status` | Displays MCP server status, tool count, and active safety modes. |
| `./cuanimus-cli mcp tools` | Lists all 46 registered MCP tools across 8 functional domains. |
| `./cuanimus-cli ui start` | Starts the CUANIMUS Web Control Center & Trading Interface HTTP daemon. |
| `./cuanimus-cli ui status` | Displays Web Control Center status, active sessions, and endpoints. |

---

## Web Control Center & Trading Interface (Phase 8)

CUANIMUS includes a professional, zero-build web-based trading control center:

```bash
# 1. Inspect Web Control Center status
./cuanimus-cli ui status

# 2. Start the Web Control Center HTTP Daemon (default: http://127.0.0.1:8080)
./cuanimus-cli ui start --port 8080

# 3. Open browser:
# http://127.0.0.1:8080/
```

Key features:
- **Zero-Dependency Architecture:** Pure modern HTML5/CSS3/ES Modules. No Node.js or npm required.
- **Hardware-Accelerated Canvas Charting:** Candlesticks, EMA overlays, ATR bands, Order Blocks, and SL/TP targets.
- **Dedicated Risk Center:** Live visual progress meters for Daily Loss limit, Drawdown cap, and Capital Exposure.
- **Deterministic Decision Traces:** Visual causal chain (*Market -> Regime -> Strategy -> Agent -> Risk -> Execution FSM -> Fill*).
- **AI Configuration Copilot:** Natural language prompt input with typed JSON Schema diff preview before applying.
- **Telegram Alert Integration:** Zero-dependency alert dispatching with connection status and test ping button.
- **Global Emergency Kill Switch:** Persistent header-level emergency stop halting active sessions and locking RiskEngine.

---

---

## Production Server Deployment & Access

CUANIMUS provides hardened deployment features for Linux servers:
- **Zero Port Conflict:** Web UI defaults to `127.0.0.1:8888` (leaving Apache on port 80 and Freqtrade on port 8080 unaffected).
- **Salted PBKDF2 Web Authentication:** 100k rounds HMAC-SHA256, session tokens, anti-brute force lockout, and RBAC (`ADMIN`, `OPERATOR`, `VIEWER`).
- **Scoped MCP Bearer Tokens:** Per-agent tokens with sliding-window domain rate limiting (READ: 60/m, ANALYZE: 30/m, CONFIG: 15/m, EXECUTE: 5/m).
- **Disaster Recovery:** Automated atomic backups with SHA256 integrity verification (`./cuanimus-cli backup create`).

```bash
# 1. Bootstrap admin credentials
./cuanimus-cli ui bootstrap

# 2. Start Web Control Center in daemon mode
./cuanimus-cli ui start --daemon --port 8888

# 3. Access securely via SSH Tunnel from workstation:
# ssh -N -L 8888:127.0.0.1:8888 user@server-ip
# Open http://localhost:8888/
```

---

## Extension Guides & Documentation

- **[Buku Panduan Lengkap Penggunaan (Tutorial Bahasa Indonesia)](TUTORIAL.md)**
- **[Production Deployment Quickstart](docs/10-deployment/GETTING_STARTED.md)**
- **[Web Access & Security Architecture](docs/10-deployment/WEB_ACCESS.md)**
- **[MCP Server Setup & Scoped Tokens](docs/10-deployment/MCP_SETUP.md)**
- **[Google Antigravity Integration Guide](docs/10-deployment/ANTIGRAVITY_SETUP.md)**
- **[OpenAI Codex Integration Guide](docs/10-deployment/CODEX_SETUP.md)**
- **[Nous Hermes Integration Guide](docs/10-deployment/HERMES_SETUP.md)**
- **[Autonomous Agent Trading Lifecycle](docs/10-deployment/AGENT_TRADING.md)**
- **[Production Operations & Disaster Recovery](docs/10-deployment/OPERATIONS.md)**
- **[Troubleshooting Guide](docs/10-deployment/TROUBLESHOOTING.md)**
- **[Quality Gates Deployment Report (G1–G15)](docs/10-deployment/DEPLOYMENT_REPORT.md)**
- [Phase 8 UI/UX Audit & Readiness Report](docs/09-uiux/PHASE_8_REPORT.md)
- [Current UI Audit & Route Inventory](docs/09-uiux/CURRENT_UI_AUDIT.md)
- [FreqUI Functional Benchmark & Parity Matrix](docs/09-uiux/FREQUI_PARITY.md)
- [Current to Target UI/UX Gap Analysis](docs/09-uiux/UIUX_GAP_ANALYSIS.md)
- [Agent Architecture & Gateway Decoupling](docs/08-agent/AGENT_ARCHITECTURE.md)
- [Model Context Protocol (MCP) Architecture](docs/08-agent/MCP_ARCHITECTURE.md)
- [MCP Tool Catalogue (46 Tools)](docs/08-agent/MCP_TOOLS.md)
- [Agent Identity & RBAC](docs/08-agent/AGENT_IDENTITY.md)
- [Agent Trading Policies](docs/08-agent/AGENT_POLICIES.md)
- [Assisted Configuration & Proposal Engine](docs/08-agent/AGENT_CONFIGURATION.md)
- [Trading Sessions & Automation Watchdogs](docs/08-agent/TRADING_SESSIONS.md)
- [Automated Paper Trading Guide](docs/08-agent/AUTOMATED_TRADING.md)
- [Security Architecture & Threat Defense](docs/08-agent/SECURITY.md)
- [Google Antigravity Integration Guide](docs/08-agent/ANTIGRAVITY.md)
- [Codex & OpenAI Tool Calling Guide](docs/08-agent/CODEX.md)
- [Hermes Autonomous Bot Guide](docs/08-agent/HERMES.md)
- [Phase 7 Readiness Report](docs/08-agent/PHASE_7_REPORT.md)
- [Configuration Guide](docs/07-development/CONFIGURATION.md)
- [Plugin System Architecture](docs/07-development/PLUGIN_SYSTEM.md)
- [CLI Reference Manual](docs/07-development/CLI.md)
- [Developing a Strategy Plugin](docs/07-development/DEVELOPING_A_STRATEGY.md)
- [Developing a Custom Risk Profile](docs/07-development/DEVELOPING_A_RISK_PROFILE.md)
- [Developing an Exchange Adapter](docs/07-development/DEVELOPING_AN_EXCHANGE_ADAPTER.md)

---

## Safety & Disclaimer

> [!CAUTION]
> **Real-Capital Live Trading is STRICTLY DISABLED (NO-GO).**  
> CUANIMUS is strictly for quantitative research, backtesting, and forward paper trading on testnets. Past empirical performance or simulation results do not guarantee future live returns.
