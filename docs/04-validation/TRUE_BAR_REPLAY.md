# CUANIMUS True Bar-Level Replay Architecture & Verification

**Document Version:** 1.0.0  
**Phase:** 5B Validation Engine Specification  
**Status:** VERIFIED & HARDENED  
**Date:** October 2026  

---

## 1. Executive Overview

Prior validation phases (Phase 3 and early 3.5 audits) identified a critical architectural limitation in legacy backtesting:
1. Strategy metrics were computed as proxy simulations over closed trade records in `tradesv3.dryrun.sqlite`.
2. Stop-loss extensions used an empirical proxy (`estimated_atr_pct = max(1.0, (mae_pct + mfe_pct) * 0.4)`), which introduced **future leakage** by deriving candle volatility from post-trade excursions.
3. Higher timeframe (HTF) context leaked unclosed bar data into execution decisions.

To achieve institutional-grade quant validity, CUANIMUS implemented the **True Bar-Level Replay Engine** (`cuanimus.validation.replay_engine.TrueBarReplayEngine`). This engine executes strategy signals, risk decisions, and order states bar-by-bar across verified, raw historical OHLCV data from Binance Futures.

---

## 2. Core Architecture & Strict Information Boundary

```
+-------------------------------------------------------------------------+
|                        Strict Event Clock (t)                           |
+-------------------------------------------------------------------------+
       |                                                 |
       v                                                 v
[Closed Bars t-N ... t-1]                     [Forming Execution Bar t]
       |                                                 |
       +---> Feature Engine (Causal Wilder RMA)          +---> Intra-Bar Limit Fill Evaluation
       +---> HTF Alignment (Closed 1h <= t)              +---> Intra-Bar Exit Evaluation
       +---> Swing / Structure (Confirmed <= t-2)        +---> Conservative SL Precedence Check
       |                                                 +---> 8h Funding Rate Assessment
       v                                                 |
 [TradeIntent (t)] ---> [RiskEngine (t)] ---> [OrderRequest (t)]
```

### 2.1 Strict Event Clock (`StrictEventClock`)
The event clock governs time progression during replay:
- Maintains monotonic progression ($t_{k} \ge t_{k-1}$). Moving backwards raises `LookaheadViolationError`.
- For any data point queried with timestamp $\tau$, asserts $\tau \le t$. If $\tau > t$, raises `LookaheadViolationError("STRICT INFORMATION BOUNDARY BREACH")`.
- 100% verified via unit test `test_strict_event_clock_detects_future_access`.

### 2.2 Multi-Timeframe Alignment (`MultiTimeframeAlignmentManager`)
In multi-timeframe trading (15m execution with 1h higher-timeframe trend filter):
- A 1h candle labeled with open time `10:00:00` only closes at `11:00:00`.
- Execution at `10:15:00`, `10:30:00`, or `10:45:00` **cannot** access the `10:00:00` 1h bar, because it is still actively forming.
- The alignment manager strictly matches 15m execution timestamp $T$ against 1h bars where $\text{close\_time} \le T$. At `10:15:00`, the latest available 1h bar is the `09:00:00` candle (which closed at `10:00:00`).
- Implemented with an $O(1)$ advancing causal pointer for optimal replay throughput.
- 100% verified via unit test `test_multi_timeframe_alignment_no_incomplete_htf_bar`.

### 2.3 Causal Feature & Structure Extraction
- **Causal ATR(14):** Computed using Wilder's RMA over strictly closed candle True Ranges ($TR_t = \max(H_t - L_t, |H_t - C_{t-1}|, |L_t - C_{t-1}|)$). Closed bar history requirement is strictly enforced ($N \ge 15$).
- **Causal Swing Points & Fractals:** A swing high at bar $k$ with window $W=2$ requires two lower highs to the right ($k+1, k+2$). It is mathematically impossible to confirm the swing at bar $k$; it can only be confirmed at bar $k+2$. The structure engine marks `confirmed_index = k + window` and filters out unconfirmed swings.
- **Order Block Causal Tracking:** An order block identified at bar $k$ enters the registry only after swing confirmation ($k + W$). It remains valid until subsequent bar price action penetrates the mitigation boundary.
- 100% verified via unit tests `test_causal_fractal_confirmation_prevents_lookahead` and `test_anti_lookahead_atr_strictly_closed_candles`.

---

## 3. Order Execution & Matching Simulation

### 3.1 Limit Order Fill Mechanics
CUANIMUS strategies submit limit orders to capture maker fee rebates:
- **Buy Limit Order:** Fills during bar $t$ if and only if $\text{Low}_t \le P_{\text{limit}}$.
- **Sell Limit Order:** Fills during bar $t$ if and only if $\text{High}_t \ge P_{\text{limit}}$.
- **Order Expiration:** Pending limit orders expire after 4 bars (60 minutes) if unfilled, releasing reserved margin.

### 3.2 Intra-Bar Exit Resolution & Conservative SL Precedence
During active position holding, every bar is inspected for exit triggers:
1. **Pessimistic / Conservative Policy:** If a candle's range encompasses both Stop Loss and Take Profit (e.g., in a high-volatility spike where $\text{Low}_t \le P_{\text{SL}}$ and $\text{High}_t \ge P_{\text{TP}}$), the engine **strictly executes Stop Loss first**. This prevents survivorship and optimistic fill biases.
2. **Adverse Slippage on Market/Stop Exits:** Stop losses execute as taker market orders with modeled adverse slippage:
   $$\text{Fill Price}_{\text{Long SL}} = P_{\text{SL}} \times (1 - \text{Slippage})$$
   $$\text{Fill Price}_{\text{Short SL}} = P_{\text{SL}} \times (1 + \text{Slippage})$$
3. **Fee Accounting:** Maker fills incur 0.02% (2 bps) commission; taker/stop fills incur 0.05% (5 bps) commission.
4. **Funding Rate Realization:** At funding intervals (00:00, 08:00, 16:00 UTC), funding payments are settled based on historical Binance funding records:
   $$\text{Funding Cost} = \text{Position Size} \times \text{Close Price} \times \text{Funding Rate}$$

---

## 4. Verification Status

| Component | Status | Empirical Validation Method |
| :--- | :--- | :--- |
| Strict Event Clock | **VERIFIED** | Unit test exception assertion on forward timestamp access |
| HTF Candle Alignment | **VERIFIED** | Unit test verifying unclosed 1h candle exclusion |
| Causal Fractals / Swings | **VERIFIED** | Unit test asserting $i + 2$ confirmation delay |
| Conservative SL Precedence | **VERIFIED** | Test fixture forcing simultaneous SL & TP breach |
| Cost & Funding Engine | **VERIFIED** | Unit test verifying maker/taker and funding separation |
