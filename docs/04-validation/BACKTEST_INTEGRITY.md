# BACKTEST INTEGRITY AUDIT REPORT (PHASE 3.5)

**Document Version:** 1.0.0  
**Audit Date:** 2026-10-03  
**Auditor Roles:** Principal Quant Engineer + Backtest Validation Specialist + Risk Engineer + Reliability Engineer  
**Audit Subject:** V0 Baseline Dataset, V1 ATR Stop Simulation, Engine Mechanics, and Execution Realism  
**Validation Gate Status:** **INCONCLUSIVE** (Fundamental Data Limitation)

---

## 1. EXECUTIVE SUMMARY & VALIDATION GATE

An exhaustive forensic audit was performed across the data pipeline, calculation models, simulation logic, and execution realism of the CUANIMUS quantitative framework.

### Validation Gate Evaluation:
| Validation Domain | Audit Assessment | Evidence & Finding |
| :--- | :---: | :--- |
| **Lookahead / Future Leakage in Indicators** | **PASS** | `compute_closed_candle_atr` strictly uses closed historical bars. No incomplete candle leakage. |
| **Intra-Trade Candle Path Reconstruction** | **FAIL** | Raw 15m/1m OHLCV bars for the period 2026-06-25 to 2026-10-02 were not archived in `user_data/data/binance`. |
| **V1 Dynamic Stop Simulation Validity** | **INCONCLUSIVE** | V1 relied on ex-post MAE/MFE proxy rather than forward bar-by-bar evaluation. |
| **Exit Order of Events Policy** | **PASS** | Pessimistic fill rule enforced: Stop-loss takes priority over take-profit in conflicting bars. |
| **Position Sizing Mathematics** | **PASS** | Fixed fractional sizing verified; leverage is not double-counted; boundary guards pass 7 edge-case tests. |
| **Fee & Slippage Realism** | **PASS** | Taker (0.05%) and Maker (0.02%) fees separated; 0.05% adverse taker slippage applied. |
| **Funding Rate Modeling** | **LIMITATION** | Historical dry-run SQLite did not record funding fees. Explicitly marked: `funding = NOT MODELED`. |
| **V0 Reproduction** | **PASS** | Bit-exact reproduction from SQLite hash `30a71e5d704c88b1a...` (733 trades, Net PnL -38.27 USDT). |

**FINAL PHASE 3.5 GATE VERDICT:** **INCONCLUSIVE**  
*Rationale:* Without intra-trade candlestick paths (Candle +1, +2, ...), it cannot be rigorously proven that a trade exiting at -1.5% in V0 would have survived to hit a 2.0x ATR trailing stop or profit target without touching the wider stop price first.

---

## 2. V0 DATA SOURCE & PIPELINE ARCHITECTURE

### Data Flow Diagram:
```text
RAW DATA (Freqtrade Dry-Run SQLite DB: user_data/tradesv3.dryrun.sqlite)
   ↓ [Module: experiments/run_experiments.py::load_baseline_trades]
NORMALIZATION (Standardized Python trade dictionary)
   ↓ [Module: user_data/strategies/ai_gemini_futures.py::populate_indicators]
FEATURES (Historical EMA20, EMA50, StochRSI, Volume Avg)
   ↓ [Module: user_data/strategies/ai_gemini_futures.py::populate_entry_trend]
SIGNAL (Historical Trend Cross + Stoch condition + Gemini API)
   ↓ [Module: user_data/strategies/utils/risk_management.py::calculate_position_size]
RISK (Historical Fixed 3% Risk, Fixed -1.5% Stop Loss, 5.0x Leverage)
   ↓ [Freqtrade Internal Dry-Run Matching Engine: 2026-06-25 to 2026-10-02]
ORDER SIMULATOR (Recorded into table 'trades' & table 'orders')
   ↓ [Module: cuanimus/validation/metrics.py::compute_performance_metrics]
PORTFOLIO & METRICS (65.0 USDT starting capital, 733 trades evaluated)
```

### Forensic Code-Level Findings:
1. **Source of the 733 Trades:** The trades originated directly from `user_data/tradesv3.dryrun.sqlite` table `trades` (`WHERE is_open = 0`).
2. **Absence of Raw OHLCV:** The directory `user_data/data/binance/` contains zero historical candle files (`.json.gz` or `.feather`).
3. **Information Stored in SQLite:** Only summary trade aggregates exist: `open_date`, `close_date`, `open_rate`, `close_rate`, `min_rate`, `max_rate`, `stake_amount`, `fee_open_cost`, `fee_close_cost`, and `exit_reason`.
4. **Intra-Trade Sequence Blindspot:** For closed trades, `min_rate` and `max_rate` record only the lowest and highest prices reached *while the trade was open*. When Freqtrade triggered `stop_loss` at -1.5%, the trade was closed immediately, terminating tracking. Price evolution *after* that stop-out is completely absent from the database.

---

## 3. ATR CALCULATION & LOOKAHEAD AUDIT

### Mathematical Definition:
$$\text{TR}_t = \max(H_t - L_t, |H_t - C_{t-1}|, |L_t - C_{t-1}|)$$
$$\text{ATR}_t = \frac{(N - 1) \cdot \text{ATR}_{t-1} + \text{TR}_t}{N}$$

### Integrity Findings:
1. **Core Library (`cuanimus/strategy/features.py`):** The function `compute_closed_candle_atr` was added and verified by unit test `test_anti_lookahead_atr_strictly_closed_candles`. It operates exclusively on closed historical candles ($t=1$ to $N$). If fewer than $N+1$ closed bars are supplied, it raises a `ValueError`.
2. **Phase 3 Experiment Script Audit (`experiments/run_experiments.py`):**
   - Line 55 contained: `estimated_atr_pct = max(1.0, (mae_pct + mfe_pct) * 0.4)`
   - **Audit Finding (Defect):** This calculation estimated ATR using the trade's *own future excursion* (`mae_pct` and `mfe_pct` over the trade's lifespan). This is an ex-post proxy that introduces future leakage.
   - **Remediation:** In subsequent research, ATR must be computed strictly from pre-entry OHLCV bars.

---

## 4. STOP-LOSS SIMULATION AUDIT

In quantitative validation, simulating an alternate stop loss requires evaluating the forward price path bar-by-bar:

$$\text{Entry} \xrightarrow{} \text{Bar } t+1 \xrightarrow{} \text{Bar } t+2 \xrightarrow{} \text{Bar } t+3 \dots$$
- For LONG: Check if $\text{Low}_{t+k} \le \text{StopPrice}$.
- For SHORT: Check if $\text{High}_{t+k} \ge \text{StopPrice}$.

### Audit Finding:
Because raw OHLCV bars were not stored in the repository, the Phase 3 simulation evaluated V1 via an algebraic model:
```python
if t["exit_reason"] == "stop_loss" and mae < sl_threshold:
    sim_profit_pct = min(t["mfe_pct"] * 0.5, 1.8)
    sim_exit = "trailing_stop"
```
While mathematically illustrative of noise-reduction potential, **this cannot be accepted as empirical validation**. It cannot prove whether the price touched the wider ATR stop before or after the favorable excursion occurred.
**Verdict:** V1 empirical validity is **INCONCLUSIVE** until re-run on bar-level OHLCV data.

---

## 5. CONSERVATIVE EXIT ORDER OF EVENTS POLICY

To prevent execution leakage and over-optimistic fill assumptions during bar backtesting, the following deterministic policy is formalized and enforced in `cuanimus/validation/backtest_engine.py`:

1. **Intra-Bar Conflict Rule (Pessimistic Order):**
   If within a single bar both Stop Loss ($\text{Low} \le \text{SL}$) and Take Profit ($\text{High} \ge \text{TP}$) are breached:
   - **Policy:** **Stop Loss executes first.** The simulation records a loss with taker slippage.
   - *Rationale:* Conservative risk modeling must assume the worst-case path through the bar's price range.
2. **Same-Bar Entry & Adverse Breach:**
   If a limit/market entry order is filled on bar $i$ and bar $i$'s range breaches the stop loss:
   - **Policy:** The position is stopped out on bar $i$.
3. **Trailing Stop Ratchet:**
   Trailing stops update only on bar close. Intra-bar stop evaluation uses the stop price established at the beginning of the bar.

*Verified via unit test:* [`test_conservative_exit_order_sl_precedence`](file:///home/zero/ai-gemini-futures-bot/tests/test_backtest_integrity.py#L42).

---

## 6. POSITION SIZING MATHEMATICAL AUDIT

The position sizing formula in `cuanimus/risk/sizing.py` was audited:
$$\text{MaxLoss} = \text{WalletBalance} \cdot \left(\frac{\text{RiskPct}}{100}\right)$$
$$\text{SLDistancePct} = \frac{|\text{EntryPrice} - \text{StopLossPrice}|}{\text{EntryPrice}}$$
$$\text{DesiredNotional} = \frac{\text{MaxLoss}}{\text{SLDistancePct}}$$
$$\text{RequiredMargin} = \frac{\text{DesiredNotional}}{\text{Leverage}}$$

### Findings:
- **No Leverage Double-Counting:** Leverage is applied solely to calculate margin requirement, not to multiply notional value.
- **Edge Cases Passing 7 Tests:**
  1. `wallet_balance <= 0` $\rightarrow$ Rejected (`NON_POSITIVE_WALLET_BALANCE`).
  2. `stop_loss_price == entry_price` $\rightarrow$ Rejected (`STOP_LOSS_TOO_TIGHT`).
  3. `sl_distance_pct < 0.2%` $\rightarrow$ Rejected (`STOP_LOSS_TOO_TIGHT`).
  4. `leverage < 1.0` $\rightarrow$ Rejected (`LEVERAGE_LESS_THAN_ONE`).
  5. `desired_notional < min_notional` $\rightarrow$ Rejected (`NOTIONAL_BELOW_MIN`).
  6. Quantization quantization check with `step_size` $\rightarrow$ Passed.
  7. Margin cap check: if margin exceeds 25% of wallet, notional is scaled down.

---

## 7. FEE, FUNDING, AND SLIPPAGE AUDIT

| Cost Element | Modeled in Engine | Value / Parameter | Accounting Status |
| :--- | :---: | :---: | :--- |
| **Maker Fee** | Yes | 0.02% (0.0002) | Applied on passive limit fills |
| **Taker Fee** | Yes | 0.05% (0.0005) | Applied on market entries and stop-loss exits |
| **Slippage** | Yes | 0.05% (0.0005) | Adverse price adjustment on taker fills |
| **Spread** | Yes | Included in slippage | Absorbed via adverse slippage model |
| **Funding Fee** | **No (Dry-Run)** | `NOT MODELED` | SQLite dry-run records 0.0 USDT funding fees |

*Limitation Notice:* In dry-run mode, Freqtrade does not debit or credit 8-hour futures funding rates. Funding impact is marked **NOT MODELED** for historical datasets and must be validated in forward paper trading.

---

## 8. RECONCILIATION OF V0 METRIC DISCREPANCIES

All numerical discrepancies between earlier narrative audits and current database truth are reconciled below:

| Metric | Old Reported Value | New Verified Value | Reason for Discrepancy | Data Source | Resolution |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Largest Win** | +10.47% (+1.03 USDT) | **+5.39%** (+0.54 USDT) | Old report applied theoretical 10x leverage to price move. | SQLite `trades.close_profit` | Adopt verified SQLite value (5.39%) |
| **Largest Loss** | -5.75% (-0.57 USDT) | **-11.28%** (-1.13 USDT) | Old report capped at -5.75%; missed trade #295 slippage gap. | SQLite `trades.close_profit` | Adopt verified SQLite value (-11.28%) |
| **Avg Duration** | 1.10 hours (65.9 min) | **39.3 minutes** (0.65 hr) | Old report used unweighted estimate; actual timestamps average 39.3 min. | SQLite `open_date`, `close_date` | Adopt verified timestamp delta (39.3 min) |
| **Turnover** | 2,917.47 USDT | **7,268.65 USDT** (Margin)<br>**36,343.25 USDT** (Notional) | Old report calculated turnover from an incomplete trade subset. | Sum of `trades.stake_amount` | Adopt verified SQLite sum (7,268.65 USDT) |
| **Total Fees** | 10.7671 USDT | **10.7671 USDT** | Exact match across reports. | Sum of `fee_open_cost + fee_close_cost` | Verified exact |
| **Net PnL** | -38.27 USDT | **-38.27 USDT** | Exact match across reports. | Sum of `trades.close_profit_abs` | Verified exact |
| **Funding** | 0.00 USDT | **-0.0368 USDT** (recorded)<br>**NOT MODELED** (actual) | Dry-run engine logged nominal near-zero artifacts. | SQLite `trades.funding_fees` | Labeled: `funding = NOT MODELED` |

---

## 9. REQUIRED DATA TO ADVANCE TO PASS

To convert Phase 3.5 Validation Gate from **INCONCLUSIVE** to **PASS**, the following data must be provided:
1. **Raw 15-minute and 1-minute OHLCV data** for `ADA/USDT`, `ETH/USDT`, and `XRP/USDT` spanning 2026-06-25 through 2026-10-02 downloaded via exchange API.
2. Re-simulation of all entries through `TrueBarReplayEngine.run()` bar-by-bar using closed-candle ATR stops.
3. Verification that simulated bar-level exits do not exceed theoretical excursion limits.

---

## 10. PHASE 5 RECONCILIATION & RESOLUTION

In Phase 5, all data and engine prerequisites were completed:
1. **Raw Historical OHLCV & Funding:** Acquired from Binance Futures API across 2026-06-25 to 2026-10-02 (ADA, ETH, XRP; 15m, 1h, 1m; 300 funding settlement records). Manifest verified at `data/manifest.json`.
2. **True Bar Replay Engine:** Replaced the legacy `estimated_atr_pct` proxy with causal Wilder ATR(14) on completed closed bars, $O(1)$ multi-timeframe alignment, causal fractal confirmation ($i + \text{window}$), maker/taker fees, adverse slippage, and 8h funding debits.
3. **Empirical Finding:**
   - On true causal bar-level replay, **V1 generated 11 trades, Win Rate 27.27%, Net PnL -3.15 USDT, Profit Factor 0.500, and WFE 0.0%**.
   - This formally resolves the Phase 3.5 inconclusive status: the previous hypothesis of high V1 profitability was a byproduct of the future-leakage proxy.
   - The **Information Boundary Gate** and **Data Integrity Gate** are now fully **PASS**.
   - The **Strategy Deployment Gate** is formally marked **STRICTLY NO-GO**.

