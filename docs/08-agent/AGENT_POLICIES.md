# CUANIMUS Agent Trading Policies

## 1. Overview & Institutional Invariants

`AgentTradingPolicy` establishes hard constraints on autonomous agent behavior. Even if an agent generates an intent, it cannot be forwarded to the Risk Engine unless it satisfies the agent's active policy.

### Platform Invariant Ceilings (Non-Negotiable)
- **Institutional Leverage Ceiling**: 10.0x. Any policy attempting $> 10.0\text{x}$ leverage is rejected at initialization.
- **Maximum Risk Per Trade Ceiling**: 5.0%.
- **Live Trading Invariant**: Live real-capital trading is strictly forbidden for autonomous agents.
- **Mandatory Stop-Loss**: Stop loss levels must be positive numbers. Unhedged trades without stop-loss are rejected.

---

## 2. Policy Schema

```yaml
policy_name: "standard_paper_policy"
allowed_environments:
  - "paper"
  - "testnet"
allowed_symbols:
  - "BTC/USDT:USDT"
  - "ETH/USDT:USDT"
  - "SOL/USDT:USDT"
  - "BNB/USDT:USDT"
  - "XRP/USDT:USDT"
allowed_strategies:
  - "v2_pullback"
  - "baseline_v0"
  - "conservative_ema"
max_risk_per_trade_pct: 2.0
max_leverage: 5.0
max_daily_loss_pct: 3.0
max_orders_per_minute: 10
require_two_step_intent: true
require_mandatory_stop_loss: true
```

---

## 3. Policy Rate Limiting

To prevent runaway loops from spamming the exchange simulator or network, `AgentTradingPolicy` enforces a sliding 60-second rate limiter (`max_orders_per_minute`, default 10). Excess orders receive an immediate rejection without execution.
