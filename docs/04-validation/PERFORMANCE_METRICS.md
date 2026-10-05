# Performance Metrics & Mathematical Scorecard Specification
## Project: CUANIMUS — Quantitative Evaluation Standards

- **Document Version:** 1.0.0
- **Date:** 2026-10-03
- **Status:** APPROVED & TESTED

---

## 1. Primary Portfolio & Return Metrics

In quantitative systems, gross percentage gain is an insufficient measure of edge. Performance must be audited using risk-adjusted, fee-inclusive metrics:

### 1.1 Mathematical Expectancy ($E$)
The expected average return per dollar risked on every trade execution:
\[
E_{\%} = \left(W \times \overline{R}_{\text{win}}\right) + \left((1 - W) \times \overline{R}_{\text{loss}}\right)
\]
\[
E_{\text{USDT}} = \left(W \times \overline{P}_{\text{win}}\right) + \left((1 - W) \times \overline{P}_{\text{loss}}\right)
\]
Where:
- $W$ = Win Rate ($\text{Wins} / \text{Total Trades}$)
- $\overline{R}_{\text{win}}$ = Average win return percentage
- $\overline{R}_{\text{loss}}$ = Average loss return percentage (negative value)

*V0 Empirical Value:* $E = -0.527\%$ (-0.0522 USDT per trade). Confirms systematic negative expectancy.

### 1.2 Profit Factor ($PF$)
The ratio of gross profits to gross losses:
\[
PF = \frac{\sum \text{Gross Realized Profits}}{\sum |\text{Gross Realized Losses}|}
\]
- $PF < 1.0$: Deeply unprofitable (V0 Baseline: $0.564$).
- $1.0 \le PF < 1.3$: Marginal (vulnerable to fee and slippage drift).
- $PF \ge 1.6$: Viable institutional target.

### 1.3 Maximum Drawdown ($MDD$) & Recovery Factor ($RF$)
\[
MDD_{\text{abs}} = \max_{t \in [0, T]} \left( \max_{s \in [0, t]} \text{Equity}_s - \text{Equity}_t \right)
\]
\[
MDD_{\%} = \frac{MDD_{\text{abs}}}{\text{Peak Equity}} \times 100\%
\]
\[
RF = \frac{|\text{Net Realized PnL}|}{MDD_{\text{abs}}}
\]
*V0 Empirical Value:* $MDD = 58.87\%$, $RF = 1.00$.

---

## 2. Advanced Trade Distribution & Execution Quality Metrics

### 2.1 Maximum Adverse Excursion (MAE)
- The maximum unrealized intraday loss experienced by a trade before it was closed:
\[
\text{MAE}_{\text{long}} = \frac{\text{Min Rate During Trade} - \text{Entry Price}}{\text{Entry Price}} \times 100\%
\]
*Diagnostic Value:* Highlights whether stop loss is placed too close to the entry price relative to normal volatility. (V0 Average MAE was $-1.80\%$, explaining why static $-1.5\%$ SL failed $61.39\%$ of the time).

### 2.2 Maximum Favorable Excursion (MFE)
- The peak unrealized gain achieved during the trade duration:
\[
\text{MFE}_{\text{long}} = \frac{\text{Max Rate During Trade} - \text{Entry Price}}{\text{Entry Price}} \times 100\%
\]
*Diagnostic Value:* Determines whether take-profit targets are set realistically relative to available price expansion.

### 2.3 R-Multiple Distribution
- Normalizes every trade profit/loss by the initial risk dollar amount ($1R = \text{Initial Stop-Loss Distance} \times \text{Position Size}$):
\[
R = \frac{\text{Net Realized PnL}}{\text{Max Dollar Risk at Entry}}
\]
- A robust trading system must demonstrate a right-skewed R-distribution with a positive mean ($> +0.3R$).

---

## 3. Cost & Friction Drag Breakdown

Every performance report must explicitly isolate three friction components:
1. **Exchange Trading Fees:**
   \[
   \text{Fee Drag} = \frac{\text{Total Maker/Taker Fees Paid}}{\text{Initial Account Capital}} \times 100\%
   \]
   *(On V0, trading fees consumed $16.56\%$ of the initial account balance).*
2. **Derivatives Funding Rates:**
   Cumulative 8-hour funding cash flows paid/received for holding perpetual futures positions.
3. **Execution Slippage Drag:**
   Difference between requested limit/trigger price and actual average fill price.
