# CUANIMUS Configuration Architecture & Specification

**Document Version:** 1.0.0  
**Phase:** 6A Configuration Platform  
**Status:** IMPLEMENTED & VERIFIED  
**Date:** October 2026  

---

## 1. Executive Vision: Configuration Over Hardcoding

In previous phases of CUANIMUS, parameters were distributed across Python source code files (e.g., `EMA_FAST = 20`, `MAX_LEVERAGE = 5.0`). This developer-centric design required source code edits to modify trading pairs, risk fractions, indicator thresholds, or exchange environments.

Phase 6 implements a **centralized, typed, layered, and safety-enforced configuration platform**:

```text
CONFIGURE ───► VALIDATE ───► BACKTEST ───► PAPER TRADE ───► MONITOR ───► ITERATE
```

Operators and contributors can configure all platform subsystems without modifying core engine source code.

---

## 2. Parameter Classification

Every parameter in CUANIMUS is classified into one of three distinct categories:

| Category | Definition | User Modifiable | Examples |
| :--- | :--- | :---: | :--- |
| **`CORE CONSTANT`** | Fundamental mathematical or protocol constants that never change across implementations. | **No** | Decimal precision definitions, KaTeX formulas, ISO-8601 formatting. |
| **`CONFIGURABLE PARAMETER`** | Operational and strategy settings that can be customized across presets and profiles. | **Yes** (Within bounds) | `risk_per_trade_pct`, `ema_fast`, `pairs`, `timeframe`, `slippage_pct`. |
| **`SAFETY INVARIANT`** | Capital preservation safeguards and risk boundaries enforced by the system. | **Restricted / Immutable** | `dry_run` safety guard, `live_trading_enabled` lock, `pessimistic_sl_precedence`, maximum leverage ceiling ($10.0\times$). |

> [!CAUTION]
> **Safety Invariants cannot be relaxed or bypassed by strategy configurations.** Any configuration attempting to disable stop-loss precedence or elevate leverage above the platform ceiling is rejected with an immediate fatal validation error.

---

## 3. Configuration Directory Hierarchy

Configurations are organized modularly within the [`config/`](file:///home/zero/ai-gemini-futures-bot/config/) directory:

```text
config/
├── defaults.yaml               # Base platform fallbacks
├── strategies/                 # Strategy algorithm configurations
│   ├── baseline_v0.yaml
│   ├── atr_v1.yaml
│   ├── pullback_v2a.yaml
│   ├── structure_v2b.yaml
│   └── hybrid_v2c.yaml
├── risk/                       # Risk management profiles
│   ├── conservative.yaml
│   ├── balanced.yaml
│   └── aggressive.yaml
├── execution/                  # Order execution policies
│   ├── conservative.yaml
│   ├── balanced.yaml
│   └── aggressive.yaml
├── exchanges/                  # Exchange connection profiles
│   ├── binance_futures.yaml
│   └── mock_exchange.yaml
├── environments/               # Operational environments
│   ├── research.yaml
│   ├── backtest.yaml
│   ├── paper.yaml
│   ├── testnet.yaml
│   └── live.yaml
└── profiles/                   # Complete pre-packaged presets
    ├── beginner.yaml
    ├── conservative.yaml
    ├── balanced.yaml
    └── aggressive.yaml
```

---

## 4. Multi-Layer Precedence Hierarchy

CUANIMUS loads and resolves configuration settings using strict layered precedence. Higher levels override lower levels without wiping unrelated sibling keys (deep dictionary merging):

```
Level 1: Code Defaults (cuanimus.config.models)
   │
   ▼
Level 2: config/defaults.yaml
   │
   ▼
Level 3: config/profiles/{profile}.yaml (e.g. balanced.yaml)
   │
   ▼
Level 4: Subsystem YAMLs (strategies/, risk/, execution/, exchanges/, environments/)
   │
   ▼
Level 5: Custom YAML File (--config custom.yaml)
   │
   ▼
Level 6: Environment Variables (CUANIMUS_{SECTION}__{PARAM})
   │
   ▼
Level 7: Programmatic CLI / Runtime Overrides
```

### Precedence Tracking (Provenance)
Every loaded parameter tracks its origin (e.g., `risk/balanced.yaml`, `DEFAULT`, `ENV_VAR:CUANIMUS_...`). Operators can inspect the origin of any parameter via:
```bash
./cuanimus-cli config explain risk.risk_per_trade_pct
```

---

## 5. Runtime Mutability & Hot-Reload Policies

To prevent in-flight parameter shifts from desynchronizing active exchange positions, every parameter is assigned a mutability policy:

| Policy | Description | Examples | Handling on Change |
| :--- | :--- | :--- | :--- |
| **`HOT_SAFE`** | Non-structural parameter that can safely update in-memory during trading. | `log_level`, `alert_on_entry`, `retry_attempts`. | In-memory hot application permitted. |
| **`RESTART_REQUIRED`** | Sizing or risk parameter that requires graceful drain of open orders before applying. | `risk_per_trade_pct`, `pairs`, `ema_fast`. | Requires controlled engine restart / state drain. |
| **`NEVER_RUNTIME_MODIFIABLE`** | Fundamental architecture or safety invariant that cannot change during process lifespan. | `env_name`, `provider`, `live_trading_enabled`, `pessimistic_sl_precedence`. | In-flight update blocked; requires full shutdown and re-initialization. |

---

## 6. Secret Quarantine & Security Invariant

API keys and passwords are **strictly excluded** from version-controlled YAML configuration files.
- Credentials must be provided via environment variables (`BINANCE_API_KEY`, `BINANCE_API_SECRET`, `GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`).
- The configuration validator scans all YAML configurations for high-entropy tokens or secret keywords. If detected, validation immediately fails with a `SECURITY LEAKAGE VIOLATION`.
