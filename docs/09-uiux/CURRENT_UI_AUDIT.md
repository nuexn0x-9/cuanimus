# CUANIMUS PHASE 8 — CURRENT UI AUDIT & INVENTORY

**Document Version:** 1.0.0  
**Phase:** Phase 8 — Web UI/UX Audit & Agentic Control Center  
**Status:** COMPLETE  
**Auditor:** Senior Product Designer + UX Architect + Trading UI Specialist  

---

## 1. Executive Summary

CUANIMUS was established across Phases 1 through 7 as an enterprise-grade quantitative trading platform and AI agent control plane. While its core quantitative engines (Strategy, Risk, Order FSM, Paper Execution Guard, Validation Replay, and MCP Agent Protocol) are verified with 111 passing tests, **the user interface prior to Phase 8 was exclusively headless and CLI-driven** (`./cuanimus-cli`).

In Phase 6, a minimal headless API class `ControlPlaneAPI` (`cuanimus/api/control_plane.py`) was introduced to serve JSON Schema and read-only diagnostics. However:
- No dedicated web frontend (`frontend/`, `web/`, or `apps/`) existed in the repository.
- No HTML/CSS/JavaScript graphical user interface existed for operators or quants.
- Operators were required to manage paper trading sessions, backtests, and configuration updates exclusively through terminal commands (`./cuanimus-cli paper`, `./cuanimus-cli backtest`, `./cuanimus-cli config`).
- AI agents operated through stdio/HTTP MCP protocols without real-time visual synchrony for human operators.

This audit establishes the baseline inventory, identifies architectural and usability gaps, and defines the target information architecture for the Phase 8 Web Control Center.

---

## 2. Repository Discovery & Subsystem Audit

| Subsystem / Path | Inspected Assets | Findings & Prior State |
| :--- | :--- | :--- |
| **`frontend/`** | None | Directory did not exist in repository. |
| **`web/`** | None | Directory did not exist in repository. |
| **`apps/`** | None | Directory did not exist in repository. |
| **`cuanimus/api/`** | `control_plane.py`, `__init__.py` | Contained headless `ControlPlaneAPI` class. Served configuration schema, read-only system status, strategy metadata, risk profiles, and experiment summaries. **Lacked an HTTP daemon, routing engine, static file server, and mutation endpoints.** |
| **`cuanimus/config/`** | `loader.py`, `models.py`, `schema.py`, `validator.py` | Highly robust typed configuration system with Pydantic-style models and JSON Schema generation. Fully capable of powering dynamic web forms without hardcoding. |
| **`cuanimus/agent/`** | `session.py`, `policy.py`, `proposal.py`, `audit.py` | Possesses full trading session lifecycle FSM (`TradingSessionManager`), safety watchdog, and audit logging. State was only accessible via Python calls and CLI. |
| **`cuanimus/mcp/`** | `server.py`, `protocol.py`, `registry.py`, 46 tools | Possessed JSON-RPC 2.0 server supporting stdio and HTTP POST. Designed for external AI clients (Antigravity, Codex, Hermes, Claude), but lacked browser UI presentation. |
| **`cuanimus/execution/`**| `paper_safety.py`, `state_machine.py` | Deterministic Order FSM and Paper Execution Safety Guard tracking 20+ telemetry metrics. Telemetry was emitted to terminal logs rather than an interactive UI. |
| **`cuanimus/risk/`** | `engine.py`, `stop_loss.py`, `sizing.py` | Independent Risk Engine with hard invariants and manual emergency stop. Required terminal CLI to invoke or inspect. |
| **`experiments/`** | 6 validation experiments | Stored rich metrics (`metrics.json`, `equity_curve.csv`, `trades.csv`), but lacked interactive charting and visual comparison interfaces. |
| **`Telegram Integration`**| `config/defaults.yaml`, `.env.example` | Configuration keys `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, and `telegram_enabled` defined, but lacked runtime dispatch service and UI test controls. |

---

## 3. UI Inventory & Route Analysis

Prior to Phase 8, every web route was categorized as **MISSING**. Below is the comprehensive classification and dependency mapping for all target routes:

| Route Path | View Name | Prior State | Classification | API Dependency | Data Source / Domain | Priority |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `/` | **Dashboard / Overview** | Non-existent | `MISSING` | `GET /api/system/status`, `GET /api/trading/positions` | `ControlPlaneAPI`, `TradingSessionManager` | **P0** |
| `/trading` | **Trading Terminal** | Non-existent | `MISSING` | `GET /api/trading/positions`, `GET /api/trading/orders` | `OrderStateMachine`, `PaperExecutionSafetyGuard` | **P0** |
| `/markets` | **Market Watchlist & Regime** | Non-existent | `MISSING` | `GET /api/markets/watchlist`, `GET /api/markets/regimes` | `MarketRegimeClassifier`, Feature Engine | **P1** |
| `/strategies` | **Strategy Center & Inspector** | Non-existent | `MISSING` | `GET /api/strategies`, `GET /api/strategies/:id` | `StrategyRegistry`, Feature Pipeline | **P1** |
| `/research` | **Backtest Lab & Experiments** | Non-existent | `MISSING` | `POST /api/research/backtest`, `GET /api/research/experiments` | `CausalReplayEngine`, Experiments Registry | **P0** |
| `/risk` | **Risk Center & Exposure** | Non-existent | `MISSING` | `GET /api/risk/status`, `GET /api/risk/profiles` | `RiskEngine`, `RiskProfileRegistry` | **P0** |
| `/agents` | **Agent Center & Sessions** | Non-existent | `MISSING` | `GET /api/agents`, `GET /api/agents/sessions` | `TradingSessionManager`, `AgentIdentityRegistry` | **P0** |
| `/config` | **Configuration Center** | Non-existent | `MISSING` | `GET /api/config/schema`, `POST /api/config/validate` | `ConfigLoader`, `ConfigValidator`, `schema.py` | **P1** |
| `/data` | **Data Center & Health** | Non-existent | `MISSING` | `GET /api/data/datasets` | `data/manifest.json`, Fingerprint Engine | **P2** |
| `/logs` | **Events & Decision Trace** | Non-existent | `MISSING` | `GET /api/logs/events`, `GET /api/agents/audit` | `AgentAuditLogger`, System Event Log | **P1** |
| `/settings` | **Settings & Telegram** | Non-existent | `MISSING` | `GET /api/settings`, `POST /api/telegram/test` | Settings Store, Telegram Notifier | **P1** |

---

## 4. Frontend Architecture & Technology Decisions

### 4.1 Host Environment Constraints
- **Operating System:** Ubuntu Linux 22.04 LTS (x86_64).
- **Runtime:** System Python 3.10 standard library.
- **Node.js / npm:** Neither `node` nor `npm` are installed on the host machine.
- **Third-Party Python Web Frameworks:** Neither `fastapi` nor `flask` are installed in the global environment.

### 4.2 Architectural Decision: Zero-Build Modern Web Application (SPA)
To ensure **100% determinism, zero build fragility, and instant portability across any workstation or server without requiring Node/npm or external package installation**:
1. **Frontend Core:** Pure modern HTML5 + CSS3 (custom CSS design tokens, CSS Grid, Flexbox) + native ES Modules (vanilla JavaScript).
2. **Component Architecture:** Declarative, modular component architecture with reactive state stores, client-side routing, and event delegation.
3. **Data Visualization:** High-performance, zero-bloat vector SVG + HTML5 Canvas charting engine supporting multi-timeframe candlesticks, volume bars, EMA overlays, swing points, order blocks, and SL/TP price levels.
4. **Backend Server:** Built-in multi-threaded HTTP/1.1 daemon (`cuanimus.api.http_server.HttpServerDaemon`) built upon Python standard library `http.server.ThreadingHTTPServer`, with non-blocking request dispatch, mime-type streaming, and REST API routing.
5. **Real-Time Updates:** High-frequency non-blocking polling and EventSource-ready streaming for positions, orders, agent heartbeats, and audit logs.

---

## 5. Security & Safety Baseline

1. **No Accidental Live Trading:** In strict alignment with CUANIMUS safety invariants, the web interface hard-locks live real-capital trading. Mode indicators (`PAPER`, `TESTNET`, `RESEARCH`) are permanently visible across all viewports.
2. **Persistent Emergency Kill Switch:** A prominent, global Emergency Stop action is accessible in the UI header and mobile navigation drawer, directly tripping `RiskEngine.trigger_emergency_stop()` and halting all active agent sessions.
3. **Secret Quarantine:** API keys, Telegram bot tokens, and Gemini secrets are never reflected in client-side HTML or returned in cleartext JSON.
4. **Localhost Binding:** The Web UI daemon binds to `127.0.0.1` by default to prevent unauthorized network exposure.
