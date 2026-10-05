# CUANIMUS PHASE 8 — FREQUI FUNCTIONAL BENCHMARK & FEATURE PARITY MATRIX

**Document Version:** 1.0.0  
**Phase:** Phase 8 — Web UI/UX Audit & Agentic Control Center  
**Benchmark Reference:** FreqUI / Freqtrade Web UI (Functional Patterns Only — Zero Code Copy)  
**Status:** IMPLEMENTED  

---

## 1. Benchmark Principle & Scope

FreqUI provides a well-tested set of interaction patterns for algorithmic trading:
- Real-time bot status and wallet summary
- Tabular views of open positions, trade history, and orders
- Interactive candlestick charts with indicator overlays
- Web-based backtesting execution and visualization
- Application settings and notifications

**CUANIMUS does not copy branding, visual design, or code from FreqUI.** Rather, CUANIMUS adopts the validated usability patterns of quantitative trading dashboards while extending them with its unique architectural differentiators:
1. **Decoupled Quantitative Risk Engine:** Clear visual exposure of daily loss limits, drawdown brakes, and exposure limits.
2. **AI Agent Control & MCP Gateway:** Autonomous agent monitoring, policy enforcement, session lifecycles, and audit trails.
3. **Deterministic Decision Traces:** Visual causal chain for every trade decision (*Market -> Regime -> Strategy -> Agent -> Policy -> Risk -> Execution*).
4. **Multi-Model Research Lab:** Out-of-sample revalidation matrices and experiment comparison across V0, V1, and V2 model families.
5. **Architectural Safety Invariants:** Permanent environment indicators, paper safety guards, and one-click human emergency kill switch.

---

## 2. Comprehensive Feature Parity Matrix

Status vocabulary:
- **`IMPLEMENTED`**: Functional parity achieved with standard trading capabilities.
- **`SUPERIOR`**: CUANIMUS exceeds standard functionality with unique quant, risk, or AI capabilities.
- **`PARTIAL`**: Core workflow operational; advanced sub-features planned for future phase.
- **`NOT APPLICABLE`**: Freqtrade-specific legacy feature obsolete in CUANIMUS's decoupled architecture.

| Feature Domain | FreqUI Benchmark Capability | CUANIMUS Web Control Center Implementation | Status | CUANIMUS Enhancement / Superiority |
| :--- | :--- | :--- | :--- | :--- |
| **System Dashboard** | Shows bot state (running/stopped), dry-run status, wallet balance, active pairs, and daily PnL. | Header & Dashboard Hero displays environment mode (`PAPER`, `TESTNET`, `RESEARCH`), health indicator, equity, 24h PnL, max drawdown, open positions, active strategy, and active AI agent session. | `SUPERIOR` | Real-time global subsystem health (API, Risk Engine, Strategy Registry, MCP, Agent Watchdog) + permanent safety mode banner. |
| **Position Management** | Lists open trades with current rate, profit %, duration, stoploss rate. Action buttons: force exit. | Comprehensive Position Panel displaying Symbol, Side, Size, Entry, Current Mark Price, uPnL (USD & %), ROE, Leverage, Dynamic ATR Stop Loss, Take Profit, and Safety State. | `SUPERIOR` | Status tag (`PROTECTED`, `AT RISK`, `LIMIT NEAR`), risk exposure contribution %, and direct link to full causal Decision Trace. |
| **Order Center** | View open and closed orders with basic fill status. | Order Center displaying full lifecycle states (`SUBMITTED`, `FILLED`, `PARTIALLY_FILLED`, `CANCELLED`, `EXPIRED`, `REJECTED`) with timestamps, client order IDs, and fee breakdown. | `SUPERIOR` | Directly maps to CUANIMUS Order Lifecycle FSM with reason codes for cancellations and timeout manager events. |
| **Trade History** | Tabular historical trade log with entry/exit times, prices, and net profit. | Searchable and filterable Trade Log displaying execution timestamps, side, amount, net PnL, duration, and execution slippage. | `SUPERIOR` | Integrated "Inspect Decision Trace" modal mapping each trade back to the generating agent, risk evaluation, and regime context. |
| **Charting & Candlesticks** | Candlestick chart with EMA/SMA lines, volume bars, entry and exit triangles. | Modular Canvas/SVG Candlestick & Volume Chart with dynamic crosshairs, multi-timeframe toggles (5m, 15m, 1h, 4h), EMA-20/50, ATR bands, Swing Points, and Order Blocks. | `SUPERIOR` | Visual markers for ATR Stop Loss, Take Profit targets, regime status badges, and Chart Profiles (`Basic`, `Advanced`, `Custom`). |
| **Start / Stop Controls** | Bot start, stop, reload config buttons. | Comprehensive Session Controls: Start Paper Session, Pause Session, Resume Session, Stop Session, and Emergency Kill Switch. | `SUPERIOR` | Strict server-side validation; forbids starting unauthorized or live-capital sessions; trips independent RiskEngine on emergency halt. |
| **Emergency Controls** | Force exit all positions button. | Header-level persistent **EMERGENCY STOP** button with two-step confirmation modal. | `SUPERIOR` | Halts all agent sessions, activates Risk Engine circuit breaker, drops pending orders, and records tamper-evident audit event. |
| **Backtesting Lab** | Run backtests via web UI; view profit, win rate, and basic trade list. | Research Backtest Lab: Interactive execution with strategy, version, pair, timeframe, date range, capital, fees, slippage, and funding models. | `SUPERIOR` | Full quant expectancy metrics (Profit Factor, Expectancy, Win Rate, Max DD, MAE/MFE, Fee impact) + interactive Equity & Drawdown curves. |
| **Strategy Comparison** | Limited / single run viewer. | Multi-Model Experiment Registry: Side-by-side comparison matrix (V0 Baseline vs V1 ATR vs V2A Pullback vs V2B Structure vs V2C Hybrid). | `SUPERIOR` | Clear partitioning into IN-SAMPLE, VALIDATION, and OUT-OF-SAMPLE data slices to prevent overfitting illusions. |
| **Walk-Forward Analysis** | Not available in standard FreqUI. | Walk-Forward Revalidation Viewer with train/test splits, WFE (Walk Forward Efficiency), and sample size warning badges. | `SUPERIOR` | Native CUANIMUS quant validation framework accessible in the web browser. |
| **Market Watchlist** | Basic list of whitelisted pairs with prices. | Market Center: Real-time watchlist (BTC, ETH, SOL, XRP, etc.) with 24h change, volume, volatility index, and current strategy signal. | `SUPERIOR` | Includes Regime Matrix across all tracked assets (Bullish Trend, Bearish Trend, Ranging, High Volatility, Uncertain). |
| **Risk Center** | Basic max open trades limit display. | Dedicated Risk Control Center with live visual progress gauges: Risk per Trade, Daily Realized Loss vs Limit, Drawdown vs Cap, Pair Concentration, Total Exposure, Cooldowns. | `SUPERIOR` | Real-time visual limit gauges with Warning and Cap thresholds; visualizes consecutive loss counters and circuit breakers. |
| **AI Agent Control** | None (Freqtrade has no native agent architecture). | Agent Control Center: Real-time monitoring of connected AI agents (Antigravity, Codex, Hermes, Claude), active sessions, policies, and permissions. | `SUPERIOR` | Autonomous session watchdog status, error budget tracking, heartbeat health, and live Agent Activity Timeline feed. |
| **AI-Assisted Config** | None. | AI Copilot Configuration Assistant: Natural language prompt input ("Setup conservative ETH paper trading") -> generated typed proposal -> visual diff -> apply. | `SUPERIOR` | Powered by CUANIMUS MCP Agent domain; previews JSON diffs before mutating configuration files. |
| **Configuration Center** | Raw JSON file editor or limited form. | Dual-Mode Configuration Center: Simple Mode (guided toggles) & Advanced Mode (full dynamic form generated from typed JSON Schema). | `SUPERIOR` | Zero hardcoded frontend forms; validates in real-time against `cuanimus/config/schema.py`; highlights schema constraint errors. |
| **Telegram Integration** | Basic Telegram bot token input in config. | Telegram Integration Center in Settings: Real-time connection status check, test message dispatch, and granular event notification toggles. | `SUPERIOR` | Native zero-dependency HTTP notification service dispatching alerts for fills, risk vetoes, emergency stops, and agent events. |
| **Logs & Event Center** | Plaintext log streaming. | Structured Event & Audit Center: Filterable by severity (`INFO`, `WARNING`, `ERROR`, `CRITICAL`), domain (Agent, Order, Risk, System), and correlation ID. | `SUPERIOR` | Sanitizes secrets automatically; links agent tool calls directly to affected trade intents. |
| **Command Palette** | Not available in standard FreqUI. | Global Command Palette (`Ctrl/Cmd + K`): Rapid keyboard search, direct navigation to pairs/sessions, quick actions, and risk inspect. | `SUPERIOR` | Instant desktop accessibility matching modern professional financial workstations. |
| **Responsive UX** | Desktop-centric layout. | Fully responsive design: Desktop (dense multi-panel workspace), Tablet (collapsible panels), Mobile (prioritized portfolio, agent status, and emergency kill switch). | `SUPERIOR` | Custom CSS Grid layouts optimized for each device form factor without decorative bloat. |

---

## 3. Summary of Usability Enhancements

1. **Information Density without Chaos:** Designed for quantitative professionals with high visual density, high contrast dark theme, and legible tabular layouts.
2. **Deterministic Clarity:** Every signal and trade explains **why** it was taken or why it was vetoed.
3. **Safety by Design:** Live real-capital trading remains locked out architecturally, and the user is always informed of the operating sandbox mode.
