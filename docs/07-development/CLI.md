# CUANIMUS Command-Line Interface (CLI) Guide

**Document Version:** 1.0.0  
**Phase:** 6C Operator Experience  
**Status:** IMPLEMENTED & VERIFIED  
**Date:** October 2026  

---

## 1. Overview

The CUANIMUS CLI provides an ergonomic interface for operators, quant researchers, and developers. It exposes diagnostics, configuration management, plugin exploration, backtesting, and paper trading without requiring source code edits.

Invoke via:
```bash
./cuanimus-cli <command> [options]
# Or via python module:
python3 -m cuanimus.cli <command> [options]
```

---

## 2. Command Reference

### 2.1 `cuanimus init`
Runs the guided setup wizard to create a valid, safe configuration file.
```bash
# Interactive mode (step-by-step terminal prompts):
./cuanimus-cli init

# Non-interactive / scripted mode:
./cuanimus-cli init --preset balanced --output cuanimus.user.yaml --non-interactive
```
- **Presets Available:** `beginner`, `conservative`, `balanced`, `aggressive`.
- **Safety Invariant:** Live trading is NEVER enabled by init (`live_trading_enabled: false`).

---

### 2.2 `cuanimus doctor`
Executes an automated 12-point health diagnostic across the entire stack.
```bash
./cuanimus-cli doctor
```
**Diagnostic Checks:**
- Python version ($\ge 3.10$)
- Docker subsystem & container health
- SQLite database write probe
- Filesystem directories (`config/`, `data/`, `experiments/`, etc.)
- Market data streams and SHA-256 manifests
- System clock & UTC monotonic drift
- Secret quarantine (scans for accidental credentials)
- Active configuration schema validity
- Strategy plugin registry
- Risk Engine mathematical integrity
- AI provider status (deterministic fallback verified)
- Live capital safety guard active

**Exit Code:** `0` if all checks pass; `1` if any critical failure is detected.

---

### 2.3 `cuanimus config validate`
Validates active or target configuration against typed schemas and safety invariants.
```bash
# Validate default balanced configuration:
./cuanimus-cli config validate

# Validate custom file with specific profile:
./cuanimus-cli config validate --config custom.yaml --profile conservative
```
**Output Format:**
```text
============================================================
          CUANIMUS CONFIGURATION VALIDATION
============================================================
  [PASS] Environment: PAPER (dry_run=True)
  [PASS] Exchange:    BINANCE (futures on testnet)
  [PASS] Strategy:    hybrid_v2c (v2.0.0)
  [PASS] Risk Engine: BALANCED (1.0%/trade, max 5.0x)
  [PASS] Execution:   BALANCED (entry=limit, slip=BASE)
  [PASS] AI Sidecar:  DISABLED (Pure Deterministic)
------------------------------------------------------------
Result:        VALID
Safety Status: PAPER_SAFE
============================================================
```

---

### 2.4 `cuanimus config show`
Displays active merged configuration after layered precedence resolution.
```bash
./cuanimus-cli config show --profile balanced --format yaml
./cuanimus-cli config show --format json
```

---

### 2.5 `cuanimus config explain`
Explains parameter value, provenance source, allowed ranges, risk level, and mutability policy.
```bash
# Explain specific parameter:
./cuanimus-cli config explain risk.risk_per_trade_pct

# Explain all parameters in a subsystem:
./cuanimus-cli config explain risk
```
**Output Example:**
```text
Parameter:   risk.risk_per_trade_pct
Value:       1.0 %
Source:      risk/balanced.yaml
Type:        float
Allowed:     [0.1 .. 5.0]
Risk Level:  CRITICAL
Mutability:  RESTART_REQUIRED
Description: Maximum risk equity percentage risked on a single trade
```

---

### 2.6 `cuanimus config schema`
Exports the complete JSON Schema Draft 2020-12 dictionary for API and Web UI integration.
```bash
./cuanimus-cli config schema > schema.json
```

---

### 2.7 `cuanimus strategy list` & `inspect`
Lists registered strategy plugins or inspects their hyperparameter schemas.
```bash
./cuanimus-cli strategy list
./cuanimus-cli strategy inspect hybrid_v2c
```

---

### 2.8 `cuanimus risk list` & `inspect`
Lists registered risk profiles and inspects sizing limits.
```bash
./cuanimus-cli risk list
./cuanimus-cli risk inspect balanced
```

---

### 2.9 `cuanimus backtest`
Configures and launches deterministic historical replay across target pairs and timeframe.
```bash
./cuanimus-cli backtest --profile balanced --strategy hybrid_v2c
```

---

### 2.10 `cuanimus paper start` / `stop`
Controls a safe in-memory forward paper trading session.
```bash
./cuanimus-cli paper start --profile balanced
./cuanimus-cli paper stop
```

---

### 2.11 `cuanimus status`
Prints platform health, active environment mode, and safety lock state.
```bash
./cuanimus-cli status
```
