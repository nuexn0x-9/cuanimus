# Product Requirement Document (PRD)

## Project: CUANIMUS — Modular Algorithmic Crypto Trading Platform

- **Project Name:** CUANIMUS
- **Document Version:** 1.0.0
- **Document Date:** 2026-10-03
- **Status:** APPROVED / IN-DESIGN
- **Owners:**
  - Principal Product Manager & Open-Source Lead
  - Senior Software Architect
  - Quant Trading Systems Architect
- **Target Repository:** `cuanimus` (evolving from `ai-gemini-futures-bot` to `CUANIMUS Core`)

---

## 1. Product Vision

### 1.1 Vision Statement

> "A modular algorithmic crypto trading platform for research, backtesting, paper trading, and controlled live execution, with deterministic risk and execution controls and optional AI-assisted market intelligence."

### 1.2 Problem Statement

Current open-source trading bots (including standard wrapper setups around monolithic engines like Freqtrade) present critical failure modes when scaled to production:

1. **Coupled Risk & Strategy:** Stop loss, position sizing, and leverage are entangled inside strategy signal scripts, leading to unverified risk parameters and blown accounts.
2. **Fragile and Blocking External Integrations:** Synchronous HTTP calls to LLMs (e.g., Gemini) directly inside real-time tick/candle loops block event loops, delay trade fills, and introduce stochastic non-determinism into execution.
3. **Operational Security Hazards:** Hardcoded plaintext exchange credentials, Telegram tokens, and API keys committed into version control.
4. **Disjointed Research-to-Live Lifecycle:** Strategies that appear profitable in simplistic backtests fail in dry-run/live environments due to lack of slippage modeling, order book simulation, and unhandled order states (e.g., zombie unfilled orders).
5. **High Barrier to Community Contribution:** Monolithic designs require contributors to understand the entire framework just to add an indicator, test an alternate risk sizing formula, or plug in a new exchange adapter.

### 1.3 Target Audience & Personas

- **Developer Contributor:** Wants clear interfaces, typed contracts, modular plugins, comprehensive mock tests, and clean separation of concerns.
- **Quant / Trader / Researcher:** Wants reproducible backtesting, frictionless strategy authoring, separated risk guardrails, and data-driven market regime analytics.
- **DevOps / System Operator:** Wants containerized deployment, zero plaintext credentials, continuous health checks, Prometheus/Grafana metrics, and deterministic kill-switches.

### 1.4 Short-Term Goals (0 - 3 Months)

- Eliminate all security vulnerabilities (secrets in code, unmounted persistence).
- Decouple Risk Engine and Execution Engine from Strategy logic.
- Implement an Asynchronous Intelligence Sidecar architecture for Gemini AI with strict TTL and fallback.
- Resolve state locking (unfilled order timeouts, lifecycle state machines).
- Establish automated test coverage (unit, integration, deterministic backtest fixtures).

### 1.5 Long-Term Goals (3 - 12 Months)

- Provide an exchange-agnostic abstraction layer (CCXT-based with normalized order state machines).
- Enable multi-strategy, multi-pair, multi-timeframe portfolio management with global drawdown limits.
- Deliver an open-source research workbench supporting walk-forward validation and parameter optimization without lookahead bias.
- Foster an active open-source contributor ecosystem with strict governance, plugin SDKs, and sandboxed execution.

### 1.6 Non-Goals (Out of Scope)

- **NO Guaranteed Profitability / "Money-Printing" Engine:** The platform is a deterministic execution and risk-enforcement framework; it does not claim to make unprofitable strategies profitable.
- **NO Autonomous AI-Led Trade Execution:** LLMs will never have direct order-placement authority; AI output is strictly treated as an advisory, optional signal feature with validation boundaries.
- **NO High-Frequency Trading (HFT) / Microsecond Colocation:** The platform targets timeframe resolutions from 1-minute to multi-hour/daily swings; it is not designed for sub-millisecond FPGA arbitrage.
- **NO Closed Proprietary Ecosystem:** No vendor lock-in; core components must run self-hosted via standard containers on standard Linux hardware.

---

## 2. Product Principles

1. **Safety Before Performance:** Capital preservation supersedes alpha generation. If any health check, risk limit, or data feed fails, the system defaults to safe mode (halt entries, manage open positions).
2. **Deterministic Execution:** Given identical inputs (market data, state, configuration), the engine must produce identical decisions. Stochastic components (LLMs, random seeds) must be isolated.
3. **Risk is Independent from Strategy:** A strategy author cannot override maximum risk per trade, portfolio leverage ceilings, or daily loss limits. Risk engine holds absolute veto power.
4. **Strategy is Replaceable:** Strategies are pure functions or stateless plugins consuming standardized market frames and emitting normalized trade intents.
5. **AI is Optional Intelligence, Not Decision Authority:** The platform must execute flawlessly with zero AI dependencies. When enabled, AI provides asynchronous context (regime, sentiment, macro bias) subject to strict schema validation and expiration TTL.
6. **Every Decision is Observable:** Every state change, signal generation, risk veto, and order transition must emit structured logs and metrics explaining _why_ it occurred.
7. **Every Trade is Auditable:** Trade lifecycle records must capture input indicators, risk sizing calculations, target entry/exit prices, fill slippage, and net fees in immutable storage.
8. **Backtest Results Must Be Reproducible:** Backtests must eliminate lookahead bias, account for trading fees, realistic funding rates, and order book fill modeling.
9. **Live Trading Requires Explicit Multi-Stage Confirmation:** Transitioning from paper/dry-run to live capital requires strict environment separation and validated risk configurations.
10. **Open-Source Ergonomics:** Clean interfaces, dependency injection, high unit-test coverage, and modular directory structures allow developers to contribute isolated modules safely.

---

## 3. Personas & Use Cases

```
┌────────────────────────────────────────────────────────────────────────┐
│                          PLATFORM PERSONAS                             │
├─────────────────┬──────────────────────────────────────────────────────┤
│ 1. Trader       │ Focus: Execution fidelity, capital safety, PnL,      │
│                 │ alerting, emergency stop controls.                   │
├─────────────────┼──────────────────────────────────────────────────────┤
│ 2. Quant /      │ Focus: Clean strategy API, historical data caching,  │
│    Researcher   │ backtesting accuracy, parameter optimization.        │
├─────────────────┼──────────────────────────────────────────────────────┤
│ 3. System       │ Focus: Docker container orchestration, secrets mgmt, │
│    Operator     │ uptime, monitoring, alerting, backups, DB integrity. │
├─────────────────┼──────────────────────────────────────────────────────┤
│ 4. Contributor  │ Focus: Clear module boundaries, typed contracts,     │
│                 │ fast CI tests, clean documentation, easy onboarding. │
└─────────────────┴──────────────────────────────────────────────────────┘
```

### 3.1 Persona Detail Matrix

- **Persona A: Quant Researcher (Alice)**
  - _Needs:_ Load historical OHLCV + funding rates, run vectorized or event-driven backtests, measure Sharpe/Sortino/Max Drawdown without slippage distortion.
  - _Frustration:_ Having to run a full live bot container just to test a hypothesis on 15m candles.
- **Persona B: Strategy Developer (Bob)**
  - _Needs:_ Implement `IStrategy` with standard `on_candle()` or `populate_indicators()`, without touching exchange connection logic or raw database queries.
  - _Frustration:_ Hardcoded risk variables in strategy templates overriding account preferences.
- **Persona C: System Operator / DevOps (Charlie)**
  - _Needs:_ Single `.env` file for credentials, structured JSON logs streamed to standard log routers, health check endpoints, automated DB backups.
  - _Frustration:_ Plaintext API keys checked into git, SQLite files stored in ephemeral container paths.
- **Persona D: Semi-Automated Discretionary Trader (Diana)**
  - _Needs:_ Reliable Telegram / Webhook notifications with actionable exit buttons, clean dashboard, instant emergency kill switch.
  - _Frustration:_ Bot stuck for 45 days on a hanging unfilled limit order, blocking capital allocation.

---

## 4. Functional Requirements

### 4.1 Market Data Engine

- **FR-MD-01 (OHLCV Ingestion):** Ingest historical and real-time candles across arbitrary timeframes (`1m`, `5m`, `15m`, `1h`, `4h`, `1d`).
- **FR-MD-02 (Multi-Timeframe Synchronization):** Automatically align higher-timeframe (HTF) data without lookahead bias (e.g., a 1h candle is only accessible at the close of that 1h period).
- **FR-MD-03 (Derivatives Metadata):** Ingest funding rates, open interest, mark price, index price, and liquidation volumes for futures pairs.
- **FR-MD-04 (Order Book Depth):** Optional Level-2 order book snapshots for entry/exit slippage estimation and depth checks.
- **FR-MD-05 (Data Caching & Storage):** Efficient parquet/feather/sqlite local storage for historical market data with automated gap-fill reconciliation.

### 4.2 Strategy Engine

- **FR-SE-01 (Stateless Signal Generation):** Strategies receive immutable market data snapshots and emit typed `TradeIntent` objects (`LONG`, `SHORT`, `HOLD`, `EXIT_LONG`, `EXIT_SHORT`).
- **FR-SE-02 (Multi-Pair & Multi-Strategy):** Support running multiple strategies concurrently against designated pair whitelists with partitioned capital budgets.
- **FR-SE-03 (Market Regime Filtering):** Built-in regime detection modules (e.g., ADX trend strength, ATR volatility bands, Volume profile, Bull/Bear classification).
- **FR-SE-04 (Strategy Independence):** Strategies MUST NOT declare absolute order sizes, absolute wallet allocations, or bypass risk limits.

### 4.3 Risk Engine (Autonomous & Independent Layer)

- **FR-RE-01 (Capital & Position Sizing):** Compute stake amount dynamically based on account equity, maximum percentage risk per trade (e.g., 1.0% - 2.0%), and stop loss distance.
- **FR-RE-02 (Dynamic Volatility Stop Loss):** Support volatility-adjusted stop losses (e.g., `k * ATR(14)`) as opposed to arbitrary fixed percentages.
- **FR-RE-03 (Take Profit & Trailing Stop Engine):** Multi-tier take profit scaling (partial exits) and dynamic trailing stops activated once risk thresholds (e.g., +1.5R) are achieved.
- **FR-RE-04 (Account-Level Circuit Breakers):**
  - Maximum daily loss limit (e.g., halt trading for 24h if account drops > 5% in a day).
  - Maximum overall drawdown guard (enter Safe Mode if drawdown exceeds 15%).
- **FR-RE-05 (Exposure & Correlation Guard):** Limit total simultaneous exposure across correlated assets (e.g., combined exposure of BTC, ETH, and high-beta altcoins capped at defined notional value).
- **FR-RE-06 (Leverage Ceilings):** Enforce strict platform-wide maximum leverage overrides regardless of user-strategy configurations.

### 4.4 Execution Engine (Deterministic Order Manager)

- **FR-EE-01 (Order Type Support):** Support Limit, Market, Stop-Market, and Take-Profit-Market order primitives.
- **FR-EE-02 (Unfilled Order Lifecycles & Timeouts):** Active monitoring of pending orders with configurable expiration (`unfilledtimeout`). Unfilled orders must be automatically cancelled or adjusted.
- **FR-EE-03 (Partial Fill Handling):** Deterministic state machine handling partial fills, amending position records, and recalculating remaining stop loss protections.
- **FR-EE-04 (Order Idempotency):** Unique client order IDs (`clientOrderId`) preventing duplicate order dispatch during network retries or process restarts.
- **FR-EE-05 (State Reconciliation):** On startup and periodically (heartbeat), query exchange API to reconcile local position/order state against exchange ground truth. Detect and alert on phantom trades or out-of-band manual interventions.

### 4.5 Portfolio & Accounting Engine

- **FR-PA-01 (Balance & Margin Tracking):** Real-time tracking of total balance, available margin, maintenance margin, and unrealized/realized PnL.
- **FR-PA-02 (Fee & Funding Reconciliation):** Account for maker/taker fees, slippage, and cumulative futures funding payments in net performance metrics.
- **FR-PA-03 (Equity Curve Persistence):** Snapshot account equity at regular intervals into persistent storage for drawdown and Sharpe/Sortino analysis.

### 4.6 Research & Validation Engine

- **FR-RS-01 (Reproducible Event-Driven Backtest):** Simulate candle-by-candle execution with exact timestamps, tick-level order book simulation, realistic fees, and slippage.
- **FR-RS-02 (Walk-Forward Optimization):** Automated in-sample parameter optimization followed by out-of-sample validation to prevent overfitting.
- **FR-RS-03 (Performance Benchmarking):** Automated generation of metrics: Total Return, CAGR, Max Drawdown, Win Rate, Profit Factor, Expectancy, Calmar Ratio, and Trade Duration distributions.

### 4.7 AI & Intelligence Layer (Optional Advisory Subsystem)

- **FR-AI-01 (Asynchronous Sidecar Architecture):** AI processes run outside the main trade execution loop, communicating via cached IPC/state files or Redis/message queues.
- **FR-AI-02 (Structured Output Enforcement):** All LLM calls (e.g., Gemini 2.0 Flash) must use strict JSON Schema mode (no markdown text parsing, no fragile regex extracting).
- **FR-AI-03 (Time-To-Live / Cache Invalidation):** Every AI insight contains an explicit timestamp and TTL (e.g., 60 minutes). If data is older than TTL, the strategy engine automatically treats AI status as `NEUTRAL / DISABLED`.
- **FR-AI-04 (Graceful Fallback):** If Gemini API returns 429 (rate limit), 5xx (server error), network timeout, or invalid schema, the system logs a warning and proceeds strictly on quantitative technical rules.
- **FR-AI-05 (Scope of AI Analysis):** Focus on macro sentiment, multi-timeframe regime synthesis, and news/event risk scoring, NOT low-level numeric indicator arithmetic.

### 4.8 Operations, Alerting & Control

- **FR-OP-01 (Emergency Kill Switch):** Immediate CLI command, API endpoint, or Telegram command (`/stop`, `/forcesell_all`) to cancel all open orders and optionally market-close all positions.
- **FR-OP-02 (Multi-Channel Notifications):** Configurable notifications via Telegram, Discord, and Webhooks for order fills, risk triggers, system errors, and daily summaries.
- **FR-OP-03 (Health Check & Liveness Probes):** HTTP health endpoints (`/health/live`, `/health/ready`) validating exchange websocket connectivity, database writeability, and memory limits.

---

## 5. Non-Functional Requirements

### 5.1 Reliability & Fault Tolerance

- **NFR-REL-01:** System must recover gracefully from network disconnection, exchange 5xx errors, and rate-limit backoffs without crashing or losing open trade state.
- **NFR-REL-02:** Database transactions must be ACID-compliant (WAL mode in SQLite or PostgreSQL) with zero data loss on unexpected power/process termination.

### 5.2 Performance & Latency

- **NFR-PERF-01:** Internal candle processing and signal evaluation latency must be < 50ms per pair on timeframe candle close.
- **NFR-PERF-02:** Zero blocking I/O calls in the main event loop. All external network requests (exchange private REST, AI APIs) must be asynchronous or scheduled.

### 5.3 Observability & Telemetry

- **NFR-OBS-01:** Structured JSON logging (`timestamp`, `level`, `component`, `pair`, `trade_id`, `event`, `details`).
- **NFR-OBS-02:** Metrics instrumentation compatible with Prometheus (order count, execution latency, error counts, active exposure, memory usage).

### 5.4 Security & Secrets Governance

- **NFR-SEC-01:** ZERO credentials, tokens, or private secrets in source code or default configuration files.
- **NFR-SEC-02:** Strict `.env` parsing with validation on startup; abort launch immediately if dummy/insecure keys are detected in non-dry-run mode.
- **NFR-SEC-03:** Least-privilege API key permissions: Documentation must clearly specify that Binance API keys require ONLY "Enable Reading" and "Enable Futures", NEVER "Enable Withdrawals".

### 5.5 Scalability & Portability

- **NFR-SCA-01:** Packaged as standard OCI-compliant Docker containers runnable across x86_64 and ARM64 (Linux, macOS, cloud instances).
- **NFR-SCA-02:** Memory footprint for core execution engine must remain < 512MB RAM for standard multi-pair operation.

### 5.6 Testability & Quality Assurance

- **NFR-TST-01:** Minimum 80% automated test coverage across Risk Engine, Execution State Machine, and Data Ingestion layers.
- **NFR-TST-02:** Mock exchange adapters and recorded market fixtures enabling full CI/CD test runs without live network connectivity.

---

## 6. Trading Modes & State Machine Boundaries

The platform strictly differentiates 5 operational modes to ensure capital safety:

```
┌────────────────────────────────────────────────────────────────────────┐
│                        TRADING MODE BOUNDARIES                         │
├───────────┬──────────────┬──────────────┬──────────────┬───────────────┤
│ Mode      │ Market Data  │ Order Fill   │ Balance      │ Capital Risk  │
├───────────┼──────────────┼──────────────┼──────────────┼───────────────┤
│ RESEARCH  │ Historical   │ None         │ N/A          │ Zero (0)      │
│ BACKTEST  │ Historical   │ Simulated    │ Virtual      │ Zero (0)      │
│ PAPER     │ Real-time WS │ Simulated    │ Virtual      │ Zero (0)      │
│ DRY-RUN   │ Real-time WS │ Sim w/ Book  │ Virtual Res. │ Zero (0)      │
│ LIVE      │ Real-time WS │ Real Exch.   │ Real Exch.   │ Real Capital  │
└───────────┴──────────────┴──────────────┴──────────────┴───────────────┘
```

### 6.1 State Isolation Rules

1. **RESEARCH Mode:** Interactive exploration (Jupyter notebooks, scripts). Read-only data access. No order generation.
2. **BACKTEST Mode:** Event-driven simulation over static historical data datasets. Evaluates fills using historic high/low/close and volume constraints.
3. **PAPER Mode:** Live streaming ticker/orderbook from exchange, but all order books, wallet balances, and trade executions are strictly simulated in local memory.
4. **DRY-RUN Mode:** Runs against real-time live market feeds with active order book top evaluation, tracking persistent paper database records, exactly matching live order lifecycle states without dispatching signed REST orders to exchange.
5. **LIVE Mode:** Requires explicit flag (`"dry_run": false` AND environment confirmation `PLATFORM_MODE=LIVE`). Dispatches real cryptographically signed orders to exchange. Any unhandled exception triggers safety fallback.

---

## 7. Safety Requirements (Live Trading Guardrails)

Before a single real dollar can be committed to the exchange, the platform must satisfy the following invariant checks:

1. **Explicit Multi-Stage Enablement:**
   - Setting `"dry_run": false` in JSON is insufficient. The environment variable `CONFIRM_LIVE_TRADING_CAPITAL_RISK=YES` must be explicitly exported.
2. **Secret & Key Validation:**
   - Verify that API keys are not placeholders or demo strings.
   - Verify that IP whitelisting is enabled on the exchange API key if supported.
3. **Pre-Flight Connectivity & Time Synchronization Check:**
   - Query exchange server time. If system clock drift exceeds **500 milliseconds**, abort immediately to prevent timestamp rejection (`recvWindow` errors).
4. **Startup Reconciliation & Stale Order Cleanup:**
   - On boot, inspect all open orders on the exchange.
   - If an open order exists in the exchange but not in the local database, trigger an alert and suspend automated entries until operator reconciliation.
   - Automatically cancel open limit orders older than `unfilledtimeout`.
5. **Balance & Margin Sanity Verification:**
   - Verify actual exchange wallet balance against local accounting. If discrepancy exceeds 1%, halt startup.
   - Ensure available balance exceeds maintenance margin buffer (`liquidation_buffer >= 0.05`).
6. **Order Sanity Bounds:**
   - Reject any order with price deviation > 2% from current mark price (prevents fat-finger market sweeps).
   - Enforce hard stop loss on EVERY entry order; entry orders without a designated stop loss trigger an immediate invariant exception.
7. **Circuit Breakers & Emergency Kill-Switch:**
   - Process-level unhandled exception or loss of exchange websocket connection for > 30 seconds triggers automated order cancellation and operator notification.

---

## 8. Open-Source Architecture & Contributor Requirements

To transform this repository into an inviting, robust open-source project:

### 8.1 Plugin / Extension Philosophy

- Clean interface abstractions via Python Abstract Base Classes (`abc.ABC`) and Pydantic schemas:
  - `BaseStrategy`: Strategy developers implement `populate_indicators()`, `evaluate_entry()`, `evaluate_exit()`.
  - `BaseRiskModel`: Risk modelers can test custom position sizing (Kelly Criterion, Volatility Parity, Fixed Fractional).
  - `BaseExchangeAdapter`: Exchange developers wrap CCXT or custom websocket APIs behind standard order/balance methods.
  - `BaseIntelligenceProvider`: AI researchers can implement alternative LLMs (Gemini, Claude, local Ollama) or on-chain data providers.

### 8.2 Repository & Module Directory Target Architecture

```text
cuanimus/
├── cmd/                          # Application entry points (CLI, Worker, API)
├── config/                       # Configuration schemas, default settings
│   ├── config.example.json
│   └── .env.example
├── docs/                         # Architecture, PRD, tutorials, API docs
│   ├── 00-product/
│   │   └── PRD.md
│   └── 01-architecture/
├── cuanimus/                     # Core Python package
│   ├── common/                   # Types, interfaces, exceptions, logger
│   ├── data/                     # Ingestion, storage, data feeds, CCXT wrapper
│   ├── strategy/                 # Strategy base class, indicator libraries
│   │   └── builtins/             # Example strategies (EMA, Breakout, MeanRevert)
│   ├── risk/                     # Dynamic sizing, ATR stops, portfolio guards
│   ├── execution/                # Order state machine, reconciliation, timeouts
│   ├── intelligence/             # Asynchronous AI sidecar, Gemini adapter
│   └── telemetry/                # Prometheus metrics, structured logging, alerts
├── tests/                        # Comprehensive test suite
│   ├── unit/                     # Fast isolated component tests
│   ├── integration/              # Database, CCXT mock, exchange tests
│   └── fixtures/                 # Recorded candle and order book datasets
├── docker/                       # Production & development Dockerfiles
│   ├── Dockerfile
│   └── docker-compose.yml
├── .gitignore
├── pyproject.toml                # Poetry/UV dependency specification
└── README.md                     # Contributor onboarding, quickstart
```

### 8.3 Contributor Standards

- **Typing & Linting:** 100% type annotations checked via `mypy` or `pyright`. Strict linting via `ruff`.
- **Test Requirement:** Every PR adding a feature must include corresponding unit/integration tests with fixture mocks.
- **Security Vulnerability Disclosure:** Clear `SECURITY.md` detailing responsible disclosure protocols and vulnerability reporting.

---

## 9. Observability & Auditability Requirements

Every trading decision must be completely reconstructible from telemetry data. The system must answer the **"10 Audit Questions"** deterministically:

| Audit Question                        | Telemetry Field / Event                                             | Storage Location                         |
| :------------------------------------ | :------------------------------------------------------------------ | :--------------------------------------- |
| 1. Why was entry triggered?           | `signal_intent`, `indicators_snapshot`, `entry_rule_id`             | `trades.trade_custom_data` & JSON Logs   |
| 2. Why was exit triggered?            | `exit_reason` (`roi`, `stop_loss`, `trailing_stop`, `signal_exit`)  | `trades.exit_reason` & Audit Log         |
| 3. What strategy produced the signal? | `strategy_name`, `strategy_version`                                 | `trades.strategy`                        |
| 4. What risk assessment was applied?  | `risk_per_trade_pct`, `sl_distance_pct`, `atr_value`                | Structured log event: `RISK_EVALUATION`  |
| 5. How was position size calculated?  | `calculated_stake`, `wallet_balance`, `leverage_applied`            | `trades.stake_amount`, `trades.leverage` |
| 6. When was the order sent?           | `order_date_utc`, `latency_ms`                                      | `orders.order_date`                      |
| 7. How was the order filled?          | `order_type`, `open_rate_requested`, `open_rate_actual`, `slippage` | `orders.average`, `trades.open_rate`     |
| 8. What fees were incurred?           | `fee_open_cost`, `fee_close_cost`, `funding_fee_running`            | `trades.fee_*`, `trades.funding_fees`    |
| 9. What context did AI provide?       | `market_bias`, `confidence`, `regime_tag`, `model_timestamp`        | `trade_custom_data` & AI sidecar log     |
| 10. What was the market regime?       | `regime_adx`, `trend_htf_ema`, `volatility_band`                    | Indicators snapshot at entry             |

---

## 10. Measurable Acceptance Criteria

To ensure quality, milestones must meet objective, measurable thresholds:

- **AC-01 (Security Sanitization):** `git log` and codebase scans using automated tools (e.g., `trufflehog`, `gitleaks`) report zero secrets or private keys in tracked files.
- **AC-02 (Database Persistence):** Recreating the Docker container (`docker compose down && docker compose up`) preserves 100% of historical trade and order records across restarts.
- **AC-03 (Zero Blocking in Event Loop):** Under load testing, main loop candle-evaluation latency remains $< 50\text{ ms}$ for 10 simultaneous pairs; AI service latency does not delay trade decision loop by $> 0\text{ ms}$ (strictly asynchronous decoupling).
- **AC-04 (Hanging Order Auto-Resolution):** Any unfilled limit order older than `unfilledtimeout` (default: 10 minutes) is cancelled automatically by the execution state machine, releasing the reserved slot.
- **AC-05 (Dynamic Sizing Verification):** Under simulated dry-run tests with fluctuating account balance, position sizing scales strictly according to the formula:
  $$\text{Stake} = \frac{\text{Wallet Balance} \times \text{Risk \%}}{\text{Stop Loss \%} \times \text{Leverage}}$$
  bounded by minimum exchange lot size and maximum portfolio exposure caps.
- **AC-06 (Structured AI Outputs):** 100% of responses from the AI intelligence provider conform to validated Pydantic schemas; zero regex text extraction failures occur over 1,000 consecutive simulated market evaluations.
- **AC-07 (Test Suite Pass Rate):** Test suite achieves $> 80\%$ statement coverage on `risk/`, `execution/`, and `data/` modules with 100% green status on continuous integration.

---

## 11. Milestone Scoping (MVP vs V1 vs V2)

```
┌────────────────────────────────────────────────────────────────────────┐
│                        RELEASE SCOPING ROADMAP                         │
├─────────────────────┬──────────────────────────────────────────────────┤
│ MVP: Stabilization  │ • Extract all secrets to .env & .gitignore       │
│ & Hygiene           │ • Persist database inside mounted volume path    │
│                     │ • Cancel zombie orders & add unfilledtimeout     │
│                     │ • Decouple risk management into reusable module  │
│                     │ • Fix AI execution bug & disable blocking HTTP   │
├─────────────────────┼──────────────────────────────────────────────────┤
│ V1: Modular Core    │ • Separate Architecture (Core, Strategy, Risk)   │
│ & Research Platform │ • Asynchronous AI sidecar with JSON Schema       │
│                     │ • ATR-based volatility stop losses & dynamic TP  │
│                     │ • Reproducible backtesting engine with CLI       │
│                     │ • Unit & integration test suite (>80% coverage)  │
│                     │ • Structured logging & Prometheus metrics        │
├─────────────────────┼──────────────────────────────────────────────────┤
│ V2: Advanced Scale  │ • Multi-exchange adapter interface (CCXT base)   │
│ & Intelligence      │ • Portfolio-level exposure & correlation guard   │
│                     │ • Walk-forward optimization engine               │
│                     │ • Order book depth & liquidation heatmap feed    │
│                     │ • Modern Web UI for monitoring and backtest plots│
└─────────────────────┴──────────────────────────────────────────────────┘
```

---

## 12. Product Risk Register

| Risk ID    | Risk Description                                | Probability | Impact   | Mitigation Strategy                                                                                                     |
| :--------- | :---------------------------------------------- | :---------- | :------- | :---------------------------------------------------------------------------------------------------------------------- |
| **RSK-01** | **Trading Loss / Capital Depletion**            | High        | Critical | Enforce independent risk engine; hardcoded max risk per trade (1-2%); automated daily drawdown circuit breaker.         |
| **RSK-02** | **Credential / Secret Leak**                    | Medium      | Critical | Remove secrets from git history; utilize `.env` with `.env.example`; enforce secret scanning in CI/CD pipeline.         |
| **RSK-03** | **Unfilled Limit Order Hang (Capital Lock)**    | High        | High     | Implement deterministic order lifecycle state machine with configurable `unfilledtimeout` and automated cancellation.   |
| **RSK-04** | **Exchange API Disconnection / Outage**         | Medium      | High     | Websocket reconnection backoff; REST fallback; local emergency stop if disconnected for > 30s during active positions.  |
| **RSK-05** | **AI Hallucination / Non-Deterministic Signal** | High        | Medium   | AI never executes orders directly; output is strictly bounded to advisory categorical tags with confidence score & TTL. |
| **RSK-06** | **Clock Drift / Timestamp Rejection**           | Medium      | High     | Automated pre-flight NTP synchronization check against exchange API; abort if offset $> 500\text{ ms}$.                 |
| **RSK-07** | **Database Corruption / Data Loss**             | Low         | High     | Enable SQLite WAL mode; configure explicit persistent mount in Docker; automated daily sqlite vacuum/backup.            |
| **RSK-08** | **Negative Slippage on Market Stop Loss**       | High        | Medium   | Model slippage in backtests; calculate position sizing with conservative slippage buffer; use limit-chasing stop exits. |
| **RSK-09** | **Funding Rate Bleed on Long Futures Hold**     | Medium      | Medium   | Track cumulative funding fees in position records; time-decay exit rule if funding costs exceed expected alpha.         |
| **RSK-10** | **Overfitting in Strategy Optimization**        | High        | High     | Enforce out-of-sample and walk-forward validation; reject strategies with parameter sensitivity spikes.                 |

---

## 13. Assumptions & Open Questions

### 13.1 Assumptions

1. Binance Futures will remain the primary reference exchange for MVP/V1, while keeping abstractions compatible with Bybit and OKX via CCXT.
2. The user has an environment capable of running standard Linux Docker containers with stable internet connectivity.
3. The platform operates primarily in `DRY-RUN` and `PAPER` modes until all acceptance criteria of MVP and V1 are formally signed off.

### 13.2 Open Questions

1. **Engine Foundation:** Should V1 continue using Freqtrade as an underlying library while rewriting strategies and risk layers, or should it gradually transition to a lightweight standalone event-driven core (`CUANIMUS Core`)?
2. **AI Provider Scope:** Beyond Google Gemini, should the AI sidecar interface support local models via Ollama (e.g., Llama 3 / DeepSeek) to allow 100% offline, zero-API-cost research?
3. **User Interface:** Is the Telegram bot and FreqUI sufficient for operational management, or does the open-source community require a dedicated lightweight React/Tailwind analytics frontend?
