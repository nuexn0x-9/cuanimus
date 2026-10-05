# Developer Guide: Building a Custom Risk Profile

**Document Version:** 1.0.0  
**Target Audience:** Risk Engineers & Quant Developers  
**Status:** COMPLETE  
**Date:** October 2026  

---

## 1. Overview

The CUANIMUS Risk Engine is the supreme financial authority in the trading lifecycle. While a strategy evaluates market signals and emits `TradeIntent`, the Risk Engine evaluates portfolio drawdown, daily loss limits, consecutive losses, and calculates mathematical position sizing.

Contributors can configure existing risk parameters or register new risk profiles without modifying core strategy engines.

---

## 2. Key Risk Parameters

All risk profiles define boundaries for the following dimensions:

| Parameter | Type | Valid Range | Description |
| :--- | :---: | :---: | :--- |
| `risk_per_trade_pct` | `float` | `0.1% - 5.0%` | Capital percentage risked on a single trade. |
| `max_leverage` | `float` | `1.0x - 10.0x` | Maximum permissible leverage (platform ceiling: 10.0x). |
| `max_daily_loss_pct` | `float` | `0.5% - 10.0%` | Rolling 24-hour realized loss limit before trading pause. |
| `max_drawdown_pct` | `float` | `3.0% - 30.0%` | Peak-to-trough portfolio drawdown threshold. |
| `max_pair_exposure_pct` | `float` | `5.0% - 50.0%` | Maximum capital allocated to a single asset. |
| `max_total_exposure_pct`| `float` | `10% - 100%` | Maximum total exposure across all open positions. |
| `consecutive_loss_pair_threshold` | `int` | `1 - 10` | Consecutive losses on a pair before triggering cooldown. |
| `consecutive_loss_portfolio_threshold` | `int` | `2 - 15` | Consecutive portfolio losses before global cooldown. |

---

## 3. Creating a Custom Risk Profile YAML

Create `config/risk/scalping_risk.yaml`:

```yaml
risk:
  profile_name: scalping_risk
  risk_per_trade_pct: 0.75
  max_leverage: 4.0
  max_daily_loss_pct: 2.0
  max_drawdown_pct: 12.0
  max_pair_exposure_pct: 25.0
  max_total_exposure_pct: 60.0
  consecutive_loss_pair_threshold: 2
  consecutive_loss_pair_cooldown_hours: 3.0
  consecutive_loss_portfolio_threshold: 4
  consecutive_loss_portfolio_cooldown_hours: 12.0
  emergency_stop_enabled: true
  capital_preservation_lock: true
  drawdown_leverage_throttle_threshold_pct: 8.0
  drawdown_throttled_leverage: 2.0
```

---

## 4. Programmatic Registration in Python

If embedding custom risk logic into code:

```python
from cuanimus.risk.registry import RiskProfileRegistry
from cuanimus.config.models import RiskConfig

RiskProfileRegistry.register(
    name="scalping_risk",
    config=RiskConfig(
        profile_name="scalping_risk",
        risk_per_trade_pct=0.75,
        max_leverage=4.0,
        max_daily_loss_pct=2.0,
        max_drawdown_pct=12.0,
    )
)
```

---

## 5. Verification via CLI

```bash
# Verify profile is recognized:
./cuanimus-cli risk list

# Inspect exact parameters:
./cuanimus-cli risk inspect scalping_risk

# Validate active configuration with custom profile:
./cuanimus-cli config validate --profile scalping_risk
```
