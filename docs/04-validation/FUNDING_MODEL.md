# CUANIMUS Perpetual Futures Funding Rate Model

**Document Version:** 1.0.0  
**Phase:** 5D Cost Modeling  
**Status:** VERIFIED & HARDENED  
**Date:** October 2026  

---

## 1. Executive Summary

In perpetual futures markets, funding payments represent a recurring capital transfer between long and short contract holders designed to tether the perpetual mark price to the spot index price. In strategies holding positions over multiple hours, ignoring funding payments creates severe positive bias in backtest returns.

CUANIMUS models historical 8-hour funding fees directly from Binance Futures historical API records.

---

## 2. Settlement Mechanism

Binance Futures settles funding payments thrice daily:
- **00:00:00 UTC**
- **08:00:00 UTC**
- **16:00:00 UTC**

Any open position held during the exact second of funding settlement incurs a funding fee or receives a funding rebate calculated as:

$$\text{Payment} = \text{Position Size} \times \text{Index/Close Price} \times \text{Funding Rate}$$

### Directional Cash Flow:
- **Long Positions:**
  - If $\text{Funding Rate} > 0$: Long pays Short (cash outflow / cost).
  - If $\text{Funding Rate} < 0$: Long receives rebate from Short (cash inflow).
- **Short Positions:**
  - If $\text{Funding Rate} > 0$: Short receives rebate from Long (cash inflow).
  - If $\text{Funding Rate} < 0$: Short pays Long (cash outflow / cost).

---

## 3. Data Acquisition & Integrity

Historical funding rates for the 100-day evaluation window (2026-06-25 through 2026-10-02) were downloaded directly from the Binance Futures public endpoint `/fapi/v1/fundingRate`:
- **ADA/USDT:USDT:** 300 settlement records.
- **ETH/USDT:USDT:** 300 settlement records.
- **XRP/USDT:USDT:** 300 settlement records.

Each dataset was validated against data corruption, negative anomalies, timestamp monotonicity, and registered in `data/manifest.json`.

---

## 4. Replay Engine Integration

In `cuanimus.validation.replay_engine.TrueBarReplayEngine`:
1. When bar clock ticks to an hour $\in \{0, 8, 16\}$ with minute $0$, the active position's accumulated funding is updated:
   ```python
   if bar_date.hour in (0, 8, 16) and bar_date.minute == 0:
       key = bar_date.isoformat()[:13]
       f_rate = funding_map.get(key, 0.0001)
       funding_fee = active_position.size * bar["close"] * f_rate
       if active_position.side == SignalDirection.LONG:
           active_position.accumulated_funding += funding_fee
       else:
           active_position.accumulated_funding -= funding_fee
   ```
2. On position exit, accumulated funding is subtracted from gross PnL alongside accumulated trading commissions.
