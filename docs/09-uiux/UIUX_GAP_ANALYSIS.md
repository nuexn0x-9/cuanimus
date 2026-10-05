# CUANIMUS PHASE 8 — CURRENT → TARGET UX GAP ANALYSIS

**Document Version:** 1.0.0  
**Phase:** Phase 8 — Web UI/UX Audit & Agentic Control Center  
**Status:** COMPLETE  

---

## 1. Overview & Prioritization Scheme

This document identifies all operational, perceptual, and architectural UX gaps between the legacy headless/CLI state and the target CUANIMUS Web Control Center.

Each gap is prioritized according to operational safety and quantitative workflow requirements:
- **`P0 (Critical)`**: Essential for operational safety, portfolio protection, or core trading workflows.
- **`P1 (High)`**: Critical for quantitative analysis, AI agent oversight, or configuration reliability.
- **`P2 (Medium)`**: Enhances usability, data transparency, or workflow efficiency.
- **`P3 (Nice-to-Have)`**: Advanced workflow enhancements, productivity accelerators, or visual refinements.

---

## 2. Detailed Gap Registry

### GAP-01: Lack of Visual Operational Dashboard (P0)
- **Current State:** System state and safety locks only visible via `./cuanimus-cli status` or `./cuanimus-cli doctor` in a terminal.
- **Problem:** Operators cannot glance at their screen and understand portfolio health, active environment, or system safety within 5 seconds.
- **Impact:** High cognitive friction; delayed situational awareness in fast-moving market conditions.
- **Target Experience:** Professional Overview Dashboard where first viewport answers:
  1. *What mode am I in?* (`PAPER` / `TESTNET` / `RESEARCH`)
  2. *Is the system healthy?* (Subsystem status grid)
  3. *Am I safe?* (Daily loss %, drawdown %, exposure %)
  4. *What positions are open and what is my PnL?*
  5. *What strategy and AI agent are running?*
- **Implementation:** Implement unified Overview View (`/`) consuming `GET /api/system/status`, `GET /api/trading/positions`, and `GET /api/risk/status`.

---

### GAP-02: Absence of Interactive Trading Terminal & Order FSM Tracking (P0)
- **Current State:** Positions and orders logged to terminal; no interactive order book, chart, or position table.
- **Problem:** Impossible to monitor mark price movement against active ATR stop loss and take profit targets visually.
- **Impact:** Quants cannot inspect trade execution quality or verify order state machine transitions (`SUBMITTED` -> `FILLED` -> `CLOSED`) in real time.
- **Target Experience:** Unified Trading Terminal (`/trading`) featuring multi-timeframe candlestick chart, active positions table with ROE and risk status, live order center with FSM lifecycle states, and interactive session controls.
- **Implementation:** Build modular SVG/Canvas candlestick charting engine with dynamic indicator overlays and position panels consuming `GET /api/trading/positions` and `GET /api/trading/orders`.

---

### GAP-03: Zero Real-Time Risk Exposure Visibility (P0)
- **Current State:** RiskEngine evaluates intents purely in memory during trade validation; limits only inspectable via `./cuanimus-cli risk inspect`.
- **Problem:** Operators cannot see how close their portfolio is to tripping a circuit breaker or daily loss limit before a trade is vetoed.
- **Impact:** Risk parameters feel like a "black box" to human operators; sudden trading halts cause confusion.
- **Target Experience:** Dedicated Risk Center (`/risk`) featuring live visual progress meters for Daily Loss (e.g. `1.2% / 3.0%`), Portfolio Drawdown, Pair Concentration, Total Exposure, and Cooldown timers with color-coded warning thresholds.
- **Implementation:** Build Risk Center view consuming `GET /api/risk/status` and `GET /api/risk/profiles` with deterministic threshold indicators (Normal, Warning, Limit).

---

### GAP-04: Headless AI Agent Management & Lack of Session Controls (P0)
- **Current State:** External AI agents interact via MCP stdio/HTTP or CLI scripts; human operator cannot visually inspect active agent sessions, pause/resume them, or view real-time agent heartbeats.
- **Problem:** AI autonomy lacks human-in-the-loop visual supervision and immediate browser-based override controls.
- **Impact:** Operator cannot intervene quickly if an agent behaves erratically or consumes its error budget.
- **Target Experience:** Dedicated Agent Center (`/agents`) displaying connected agents, session durations, error budgets, heartbeat status, and one-click Pause, Resume, Stop, and Kill controls. Includes a real-time Agent Activity Feed timeline.
- **Implementation:** Connect UI to `TradingSessionManager` via `GET /api/agents/sessions` and `POST /api/agents/sessions/:id/action`.

---

### GAP-05: Absence of One-Click Human Emergency Kill Switch in Browser (P0)
- **Current State:** Emergency stop requires executing Python code or killing terminal processes via SIGKILL.
- **Problem:** In market flash crashes or operational anomalies, finding the correct terminal command takes critical seconds.
- **Impact:** Catastrophic risk of unwanted execution or cascading orders during anomalies.
- **Target Experience:** Permanent, prominent **EMERGENCY STOP** button located in the global header across all views. Clicking triggers a two-step confirmation modal that instantly trips `RiskEngine.trigger_emergency_stop()`, halts all active agent sessions, and records a tamper-evident audit log.
- **Implementation:** Global header component bound to `POST /api/system/emergency-stop`.

---

### GAP-06: Backtest & Quantitative Research Workflow Trapped in CLI (P1)
- **Current State:** Running backtests requires `./cuanimus-cli backtest` or running Python scripts in `experiments/`.
- **Problem:** Viewing equity curves and trade distributions requires plotting external CSV files in third-party software.
- **Impact:** Hinders iterative hypothesis testing and rapid quant strategy development.
- **Target Experience:** Web-based Research Lab (`/research`) with interactive parameter selectors (Strategy, Timeframe, Date Range, Capital, Fees, Slippage), one-click "Run Backtest", real-time expectancy metrics (PF, Expectancy, Win Rate, Max DD, MAE/MFE), and interactive Equity & Drawdown curves.
- **Implementation:** Build Research Lab view powered by `POST /api/research/backtest/run` and `GET /api/research/experiments`.

---

### GAP-07: Inability to Visually Compare Multi-Model Validation Experiments (P1)
- **Current State:** Experiments (V0 Baseline, V1 ATR Stop, V2A Pullback, V2B Structure, V2C Hybrid) stored in separate subdirectories in `experiments/`.
- **Problem:** No consolidated side-by-side comparison matrix showing in-sample vs out-of-sample performance across model iterations.
- **Impact:** Difficult to verify whether structural improvements (e.g. V2B) actually improved risk-adjusted expectancy over baseline.
- **Target Experience:** Experiment Registry comparison view with multi-column metrics table, clear data partitioning flags (`IN-SAMPLE`, `VALIDATION`, `OUT-OF-SAMPLE`), and walk-forward efficiency metrics.
- **Implementation:** Build comparison component consuming `GET /api/research/experiments`.

---

### GAP-08: Manual YAML Configuration Editing Prone to Human Syntax Errors (P1)
- **Current State:** Users must edit YAML files in text editors and run `./cuanimus-cli config validate`.
- **Problem:** Beginners struggle with indentation, type mismatches, and unfamiliar risk keys.
- **Impact:** Configuration errors prevent the bot from launching or cause runtime crashes.
- **Target Experience:** Dual-Mode Configuration Center (`/config`):
  1. *Simple Mode:* Intuitive dropdowns and sliders for common settings (Environment, Strategy, Pairs, Risk Profile).
  2. *Advanced Mode:* Full dynamic form generated directly from `cuanimus/config/schema.py` JSON Schema with real-time validation and diff preview before saving.
- **Implementation:** Build Configuration form generator consuming `GET /api/config/schema` and `POST /api/config/validate`.

---

### GAP-09: Lack of AI-Assisted Configuration Copilot in Web UI (P1)
- **Current State:** AI configuration assistance was introduced in Phase 7 via MCP tools, but only available to external AI agents.
- **Problem:** Human users cannot interactively prompt CUANIMUS in the browser to generate tailored configurations.
- **Impact:** Underutilization of Phase 7's intelligent configuration capabilities for end-users.
- **Target Experience:** Interactive AI Configuration Assistant widget in the browser: user types natural language intent (e.g., *"Setup conservative ETH paper trading with 0.5% risk"*), agent proposes typed configuration, UI displays clear diff, and user applies with one click.
- **Implementation:** Integrate `POST /api/agents/propose-config` with configuration preview and validation modal.

---

### GAP-10: Black-Box Trade Execution Without Decision Trace Visibility (P1)
- **Current State:** Fills are recorded, but the causal chain of decisions leading to a fill is only found in fragmented terminal log lines.
- **Problem:** User cannot quickly answer: *"Why did the bot enter this trade? Why did it reject that trade?"*
- **Impact:** Decreases trust in autonomous trading systems; makes debugging strategies difficult.
- **Target Experience:** Trade Decision Trace Inspector: clicking any trade or signal in the UI opens the full causal chain:
  *User/Agent Request -> Market Context -> Strategy Signal -> Agent Decision -> Policy Check -> Risk Evaluation -> Execution FSM -> Fill Result*.
- **Implementation:** Build Decision Trace modal consuming `GET /api/trading/decision-traces`.

---

### GAP-11: Telegram Notification & Alert Status Missing from Control Plane (P1)
- **Current State:** Telegram credentials existed in `.env.example` and `config/defaults.yaml`, but the system lacked runtime verification and in-browser status monitoring.
- **Problem:** User cannot verify if Telegram alerts are functioning without waiting for a real trade event.
- **Impact:** Missed emergency alerts or position notifications if Telegram bot is misconfigured.
- **Target Experience:** Telegram Integration Center in Settings (`/settings`): displays bot connection status, chat ID verification, granular notification switches, and a one-click "Send Test Alert" button.
- **Implementation:** Create `cuanimus/api/telegram.py` service and endpoints `GET /api/telegram/status` and `POST /api/telegram/test`.

---

### GAP-12: Keyboard Accessibility & Professional Financial Ergonomics (P2)
- **Current State:** Web interfaces for crypto bots often lack professional keyboard navigation, requiring repetitive mouse clicks.
- **Problem:** Inefficient navigation for quantitative traders used to Bloomberg Terminal or modern IDE command palettes.
- **Impact:** Slow operational response times.
- **Target Experience:** Global Command Palette accessible via `Ctrl+K` or `Cmd+K` allowing quick jump to any pair, running backtests, inspecting risk, or stopping sessions. Full keyboard accessibility with clear focus rings.
- **Implementation:** Build native JavaScript Command Palette component and WCAG AA keyboard handlers.

---

### GAP-13: Mobile Responsiveness & Form Factor Degeneracy (P2)
- **Current State:** No mobile interface existed.
- **Problem:** Trading interfaces squeezed onto mobile screens typically break tables and charts.
- **Impact:** Operators cannot monitor their bots safely while away from their desks.
- **Target Experience:** Purpose-built responsive layout: Mobile view prioritizes Portfolio Equity, Active Positions, Agent Watchdog Status, and the Emergency Stop button, tucking complex multi-panel charts into dedicated full-screen views.
- **Implementation:** Pure CSS media queries (`@media (max-width: 768px)`) and touch-friendly mobile action drawer.
