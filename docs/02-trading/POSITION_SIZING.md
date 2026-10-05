# Position Sizing & Margin Management Specification
## Project: CUANIMUS — Quantitative Capital Allocation

- **Document Version:** 1.0.0
- **Date:** 2026-10-03
- **Status:** APPROVED

---

## 1. Mathematical Formulation: Fixed Fractional Risk Sizing

In quantitative derivatives trading, order sizing must be a function of **account equity, percentage risk per trade, stop-loss distance, and leverage**, rather than an arbitrary flat dollar amount (such as the fixed $10.0 USDT stake in V0).

### 1.1 The Sizing Equation

Let:
- $E$ = Current total wallet equity ($\text{USDT}$)
- $R$ = Risk percentage per trade (e.g., $1.0\% = 0.01$)
- $P_{\text{entry}}$ = Target entry fill price ($\text{USDT}$)
- $P_{\text{sl}}$ = Stop-loss price ($\text{USDT}$)
- $L$ = Allocated isolated leverage (e.g., $5\text{x}$)
- $d_{\text{sl}} = \frac{|P_{\text{entry}} - P_{\text{sl}}|}{P_{\text{entry}}}$ = Fractional stop-loss distance

The **Maximum Permissible Capital Loss** ($\text{MaxLoss}$) is:
\[
\text{MaxLoss} = E \times R
\]

The required **Notional Position Value** ($V_{\text{notional}}$) to ensure that hitting the stop loss loses exactly $\text{MaxLoss}$ is:
\[
V_{\text{notional}} = \frac{\text{MaxLoss}}{d_{\text{sl}}} = \frac{E \times R}{d_{\text{sl}}}
\]

The **Margin Required (Stake Amount)** ($M_{\text{stake}}$) allocated from the wallet is:
\[
M_{\text{stake}} = \frac{V_{\text{notional}}}{L} = \frac{E \times R}{d_{\text{sl}} \times L}
\]

The **Base Asset Contract Amount** ($Q_{\text{contracts}}$) to purchase is:
\[
Q_{\text{contracts}} = \frac{V_{\text{notional}}}{P_{\text{entry}}} = \frac{E \times R}{d_{\text{sl}} \times P_{\text{entry}}}
\]

---

## 2. Safety Bounds & Clamping Invariants

Before dispatching an order, the calculated $M_{\text{stake}}$ must pass four mandatory sanity bounds:

1. **Exchange Minimum Notional Check:**
   \[
   V_{\text{notional}} \ge V_{\text{min\_exchange}} \quad (\text{e.g., } 5.0\text{ USDT on Binance})
   \]
2. **Maximum Margin Allocation Cap:**
   \[
   M_{\text{stake}} \le E \times \text{MaxStakeRatio} \quad (\text{Default: } 25\% \text{ of available wallet})
   \]
3. **Liquidation Price Distance Buffer:**
   The calculated stop-loss price $P_{\text{sl}}$ must be strictly closer to $P_{\text{entry}}$ than the estimated liquidation price $P_{\text{liq}}$ by a minimum safety buffer:
   \[
   |P_{\text{entry}} - P_{\text{sl}}| \le 0.70 \times |P_{\text{entry}} - P_{\text{liq}}|
   \]
   *(Guarantees that a stop loss always triggers before catastrophic exchange liquidation).*
4. **Lot-Size and Step-Size Quantization:**
   $Q_{\text{contracts}}$ must be quantized strictly to the exchange's lot step-size using floor rounding to prevent over-allocation:
   \[
   Q_{\text{quantized}} = \text{floor}\left(\frac{Q_{\text{contracts}}}{\text{step\_size}}\right) \times \text{step\_size}
   \]

---

## 3. Comparison: Fixed Stake ($10 Baseline) vs Dynamic Sizing

| Scenario | V0 Fixed Stake ($10 @ 5x) | Target Dynamic Sizing ($100 Equity, Risk=1.5%) |
| :--- | :--- | :--- |
| **High Volatility (ATR SL = 4.0%)** | Margin = $10. Loss at SL = $10 \times 4\% \times 5 = **$2.00 (2% loss)** | Margin = $\frac{100 \times 0.015}{0.04 \times 5} =$ **$7.50**. Loss at SL = **$1.50 (exact 1.5%)** |
| **Low Volatility (ATR SL = 1.0%)** | Margin = $10. Loss at SL = $10 \times 1\% \times 5 = **$0.50 (0.5% loss)** | Margin = $\frac{100 \times 0.015}{0.01 \times 5} =$ **$30.00$** (clamped to 25%). Loss at SL = **$1.25** |
| **Account Drawdown ($65 -> $30)** | Still bets $10 (now 33% of wallet!). Risk compounds exponentially! | Margin scales down proportionally to $30 equity, protecting surviving capital. |

---

## 4. Production Reference Implementation

```python
import math
import logging

logger = logging.getLogger(__name__)

def calculate_dynamic_position_size(
    wallet_balance: float,
    risk_per_trade_pct: float,
    entry_price: float,
    stop_loss_price: float,
    leverage: float,
    min_notional: float = 5.0,
    max_margin_ratio: float = 0.25,
    step_size: float = 0.001
) -> dict:
    """
    Computes exact contract quantity and required margin based on fractional risk.
    """
    assert wallet_balance > 0, "Wallet balance must be positive"
    assert entry_price > 0 and stop_loss_price > 0, "Prices must be positive"
    assert leverage >= 1.0, "Leverage must be >= 1.0"

    sl_distance_fraction = abs(entry_price - stop_loss_price) / entry_price
    if sl_distance_fraction < 0.002: # Minimum 0.2% distance to prevent division by zero
        raise ValueError("Stop loss distance too tight (< 0.2%)")

    max_loss_usdt = wallet_balance * (risk_per_trade_pct / 100.0)
    desired_notional = max_loss_usdt / sl_distance_fraction
    required_margin = desired_notional / leverage

    # Clamp margin to maximum portfolio fraction
    max_allowed_margin = wallet_balance * max_margin_ratio
    if required_margin > max_allowed_margin:
        required_margin = max_allowed_margin
        desired_notional = required_margin * leverage
        max_loss_usdt = desired_notional * sl_distance_fraction

    # Verify exchange minimum notional
    if desired_notional < min_notional:
        logger.warning(f"Calculated notional {desired_notional:.2f} below exchange min {min_notional}")
        return {"approved": False, "reason": "BELOW_MIN_NOTIONAL"}

    raw_contracts = desired_notional / entry_price
    quantized_contracts = math.floor(raw_contracts / step_size) * step_size

    return {
        "approved": True,
        "stake_amount": round(required_margin, 2),
        "contracts": round(quantized_contracts, 6),
        "notional_value": round(quantized_contracts * entry_price, 2),
        "max_risk_usdt": round(max_loss_usdt, 2),
        "sl_distance_pct": round(sl_distance_fraction * 100, 2)
    }
```
