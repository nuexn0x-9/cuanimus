# CUANIMUS Execution & Cost Simulation Model

**Document Version:** 1.0.0  
**Phase:** 5D Execution Modeling  
**Status:** VERIFIED & HARDENED  
**Date:** October 2026  

---

## 1. Executive Summary

A frequent flaw in algorithmic trading backtests is assuming idealized fills:
- Zero slippage on market orders.
- Immediate fills on limit orders regardless of price penetration.
- Uniform or omitted exchange transaction fees.
- Omission of overnight/8-hour funding rates.

CUANIMUS incorporates a realistic, pessimistic execution engine that models market microstructure constraints, taker adverse slippage, separate maker/taker tier fees, and liquidity limits.

---

## 2. Order Types & Execution Rules

### 2.1 Limit Orders (Entry & Take-Profit)
- **Maker Placement:** All primary entry orders are submitted as limit orders at the closing price of the signal candle.
- **Fill Condition:**
  - `BUY` Limit at price $P$: Fills during candle $t$ if and only if $\text{Low}_t \le P$.
  - `SELL` Limit at price $P$: Fills during candle $t$ if and only if $\text{High}_t \ge P$.
- **Time-In-Force / Order Expiry:** Unfilled limit orders remain open for up to 4 execution bars (60 minutes on 15m timeframe). If the price fails to trade through the limit within 4 bars, the order expires, returning locked margin to available balance.
- **Fee Tier:** Fills are charged the VIP 0 Maker fee of **0.02%** (2 basis points).

### 2.2 Market & Stop-Loss Orders (Exits)
- **Taker Execution:** Stop-loss exits are triggered immediately when candle bounds violate the stop threshold ($\text{Low}_t \le P_{\text{SL}}$ for long; $\text{High}_t \ge P_{\text{SL}}$ for short).
- **Fee Tier:** Fills are charged the VIP 0 Taker fee of **0.05%** (5 basis points).
- **Adverse Slippage Model:** Market orders cross the bid-ask spread and absorb order book depth, resulting in adverse slippage.

---

## 3. Slippage Modeling Framework

Slippage is modeled as an adverse percentage penalty deducted from execution price:

$$\text{Fill Price}_{\text{Long Exit}} = P_{\text{SL}} \times (1 - S)$$
$$\text{Fill Price}_{\text{Short Exit}} = P_{\text{SL}} \times (1 + S)$$

Where $S$ is the slippage fraction.

Three explicit stress tiers are evaluated across all strategy variants:

| Slippage Tier | Parameter Value | Market Condition Modeled |
| :--- | :--- | :--- |
| **BASE** | **0.05%** (5 bps) | Normal liquid conditions for high-volume pairs (ADA, ETH, XRP). |
| **CONSERVATIVE** | **0.10%** (10 bps) | Moderate volatility, wider bid-ask spread, minor book thinning. |
| **STRESS** | **0.25%** (25 bps) | Extreme volatility spikes, order-book cascades, liquidation events. |

---

## 4. Conservative Resolution of Intra-Bar Conflicts

When bar-level simulation is conducted on 15-minute candles, intra-bar sequence ambiguity can arise if both Stop Loss ($P_{\text{SL}}$) and Take Profit ($P_{\text{TP}}$) are touched within the same candle:
$$\text{Low}_t \le P_{\text{SL}} \quad \text{AND} \quad \text{High}_t \ge P_{\text{TP}}$$

To eliminate survivorship and optimistic fill biases, CUANIMUS enforces the **Pessimistic Stop-Loss Precedence Rule**:
> In any bar where both Stop Loss and Take Profit price levels are breached, the engine assumes the Stop Loss was hit first, executing a taker exit with adverse slippage and logging the trade as a loss.

---

## 5. Risk-Adjusted Position Sizing Integration

The execution engine receives order requests sized deterministically by the Risk Engine:
$$\text{Position Size} = \frac{\text{Equity} \times \text{Risk Fraction}}{\Delta_{\text{Stop}}}$$
$$\Delta_{\text{Stop}} = \frac{|P_{\text{entry}} - P_{\text{SL}}|}{P_{\text{entry}}}$$

- **Leverage Cap:** Leverage is capped at 5.0x under standard conditions and throttled to 2.0x during portfolio drawdown $> 10\%$.
- **Notional Cap:** Single position notional cannot exceed 25% of portfolio equity.
