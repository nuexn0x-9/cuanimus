# CUANIMUS MCP Tool Catalogue

CUANIMUS provides 46 specialized MCP tools across 8 functional domains. Access to every tool is strictly controlled by **Role-Based Access Control (RBAC)** under a **Default-Deny** security posture.

---

## 1. System Domain (`system.*`)

| Tool Name | Description | Required Permission |
| :--- | :--- | :--- |
| `system.get_status` | Returns system operational status, active environment, and safety locks. | `READ_SYSTEM` |
| `system.get_version` | Returns CUANIMUS platform, MCP protocol, and build target version. | `READ_SYSTEM` |
| `system.get_safety_status` | Evaluates safety invariants (live disabled, SL mandatory, leverage ceiling). | `READ_SYSTEM` |
| `system.get_capabilities` | Discovers registered strategies, risk profiles, and execution modes. | `READ_SYSTEM` |
| `system.doctor` | Executes full environment, data integrity, and system health checks. | `READ_SYSTEM` |

---

## 2. Configuration Domain (`config.*`)

| Tool Name | Description | Required Permission |
| :--- | :--- | :--- |
| `config.get_schema` | Returns JSON Schema definition for CUANIMUS configuration. | `READ_SYSTEM` |
| `config.get_current` | Returns active merged configuration with secrets sanitized. | `READ_SYSTEM` |
| `config.validate` | Validates candidate configuration against schema and safety invariants. | `CONFIGURE` |
| `config.explain` | Explains the purpose, range, and risk impact of a specific parameter. | `READ_SYSTEM` |
| `config.get_profiles` | Lists pre-packaged environment, strategy, and risk configuration profiles. | `READ_SYSTEM` |
| `config.preview` | Creates a Configuration Proposal, generating deep diffs without applying. | `CONFIGURE` |
| `config.apply` | Writes an approved Configuration Proposal to `cuanimus.user.yaml`. | `CONFIGURE` |

---

## 3. Market Intelligence Domain (`market.*`)

| Tool Name | Description | Required Permission |
| :--- | :--- | :--- |
| `market.get_snapshot` | Returns latest ticker, 24h high/low, and volume for a symbol. | `READ_MARKET` |
| `market.get_ohlcv` | Retrieves historical OHLCV candlestick series for a symbol and timeframe. | `READ_MARKET` |
| `market.get_ticker` | Retrieves order book top bid and ask quotes and spread in basis points. | `READ_MARKET` |
| `market.get_funding` | Returns latest 8h funding rate and predicted next settlement rate. | `READ_MARKET` |
| `market.get_regime` | Classifies market regime (TRENDING_BULL, TRENDING_BEAR, RANGING, etc.). | `READ_MARKET` |

---

## 4. Portfolio & Account Telemetry Domain (`portfolio.*`)

| Tool Name | Description | Required Permission |
| :--- | :--- | :--- |
| `portfolio.get_balance` | Retrieves account equity, wallet balance, and available margin. | `READ_PORTFOLIO` |
| `portfolio.get_positions` | Retrieves list of active futures positions, mark prices, and unrealized PnL. | `READ_PORTFOLIO` |
| `portfolio.get_orders` | Retrieves active open limit/stop orders and their state machine statuses. | `READ_PORTFOLIO` |
| `portfolio.get_exposure` | Retrieves gross and net exposure per trading pair and total portfolio exposure. | `READ_PORTFOLIO` |
| `portfolio.get_pnl` | Returns realized and unrealized profit & loss and win-rate statistics. | `READ_PORTFOLIO` |
| `portfolio.get_drawdown` | Returns current and peak portfolio drawdown metrics against thresholds. | `READ_PORTFOLIO` |

---

## 5. Strategy Intelligence Domain (`strategy.*`)

| Tool Name | Description | Required Permission |
| :--- | :--- | :--- |
| `strategy.list` | Lists all registered quantitative strategies in the registry. | `READ_STRATEGY` |
| `strategy.inspect` | Inspects metadata, timeframe, and configurable parameters of a strategy. | `READ_STRATEGY` |
| `strategy.evaluate` | Evaluates strategy logic against given market data to generate TradeIntent. | `ANALYZE` |
| `strategy.explain_signal` | Explains technical factors and indicators driving a signal (LONG/SHORT/HOLD). | `ANALYZE` |

---

## 6. Risk Guardrails Domain (`risk.*`)

| Tool Name | Description | Required Permission |
| :--- | :--- | :--- |
| `risk.get_status` | Retrieves current Risk Engine status, cooldown states, and kill switches. | `READ_RISK` |
| `risk.get_limits` | Retrieves configured risk limits (max risk %, leverage, daily loss, drawdown). | `READ_RISK` |
| `risk.assess_trade` | Evaluates candidate trade against Risk Engine guardrails and sizing rules. | `ANALYZE` |
| `risk.calculate_position_size`| Calculates mathematical contract count and stake USDT for an entry and SL. | `READ_RISK` |

---

## 7. Trading Execution Domain (`trading.*`)

| Tool Name | Description | Required Permission |
| :--- | :--- | :--- |
| `trading.find_setup` | Scans configured pairs for algorithmic strategy setups. | `ANALYZE` |
| `trading.simulate_trade` | Simulates prospective trade execution costs, fees, and slippage. | `SIMULATE` |
| `trading.create_intent` | Step 1 of pipeline: creates a new TradeIntent with idempotency key. | `PAPER_TRADE` |
| `trading.validate_intent` | Step 2 of pipeline: validates intent against Policy and RiskEngine. | `PAPER_TRADE` |
| `trading.execute_intent` | Step 3 of pipeline: executes validated intent under safety guards (Live blocked). | `PAPER_TRADE` |
| `trading.cancel_order` | Cancels an active simulated or testnet order safely. | `CANCEL_ORDER` |
| `trading.close_position` | Closes an active futures position at market price. | `CLOSE_POSITION` |
| `trading.get_decision_trace` | Inspects complete rationale and lifecycle log for a trade intent. | `ANALYZE` |

---

## 8. Session Automation Domain (`session.*`)

| Tool Name | Description | Required Permission |
| :--- | :--- | :--- |
| `session.create` | Creates an automated `PAPER_AUTO` or `TESTNET_AUTO` trading session. | `MANAGE_SESSION` |
| `session.start` | Starts an initialized trading session. | `MANAGE_SESSION` |
| `session.pause` | Pauses an active trading session temporarily. | `MANAGE_SESSION` |
| `session.resume` | Resumes a paused trading session. | `MANAGE_SESSION` |
| `session.stop` | Cleanly terminates an active trading session. | `MANAGE_SESSION` |
| `session.get_status` | Returns live status, error budget, and health for trading sessions. | `MANAGE_SESSION` |
| `session.emergency_stop` | CRITICAL KILL-SWITCH: Instantly halts sessions and locks RiskEngine. | `EMERGENCY_STOP` |
