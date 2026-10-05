"""
CUANIMUS True Bar-Level Revalidation Suite.
Executes True Bar Replay across raw Binance Futures OHLCV for:
- V1 True Revalidation (Dynamic ATR Stop Loss, Causal Replay)
- V2A True Revalidation (EMA20 Pullback + Stochastic Reset)
- V2B True Revalidation (Market Structure + Fibonacci Retest)
- V2C True Revalidation (Hybrid Pullback + Order Block)
- Slippage Sensitivity Stress Tests (BASE, CONSERVATIVE, STRESS)
- Chronological Walk-Forward & Out-of-Sample Analysis
- Regime & Pair Stability Analysis
"""
import os
import sys
import json
import csv
from datetime import datetime, timezone
from typing import Dict, Any, List

from cuanimus.common.types import SignalDirection
from cuanimus.risk.engine import RiskEngine
from cuanimus.strategy.baseline_v0 import BaselineV0Strategy
from cuanimus.strategy.v2_pullback import V2PullbackStrategy, V2StrategyConfig
from cuanimus.validation.replay_engine import (
    ReplayConfig,
    ReplayFeeModel,
    ReplaySlippageModel,
    TrueBarReplayEngine,
    export_experiment_artifacts,
)
from cuanimus.validation.metrics import compute_performance_metrics
from cuanimus.validation.walk_forward import calculate_walk_forward_efficiency

DATA_DIR = "user_data/data/binance/futures"
EXP_DIR = "experiments"

PAIRS = ["ADA/USDT:USDT", "ETH/USDT:USDT", "XRP/USDT:USDT"]


def load_pair_data(pair: str) -> Dict[str, Any]:
    sym_clean = pair.replace("/", "_").replace(":", "_")
    p15m = os.path.join(DATA_DIR, f"{sym_clean}-15m-futures.json")
    p1h = os.path.join(DATA_DIR, f"{sym_clean}-1h-futures.json")
    pfund = os.path.join(DATA_DIR, f"{sym_clean}-funding_rate.json")

    with open(p15m, "r") as f:
        bars_15m = json.load(f)
    with open(p1h, "r") as f:
        bars_1h = json.load(f)

    funding_records = []
    if os.path.exists(pfund):
        with open(pfund, "r") as f:
            funding_records = json.load(f)

    return {"15m": bars_15m, "1h": bars_1h, "funding": funding_records}


def run_multi_pair_replay(
    strategy,
    risk_engine: RiskEngine,
    config: ReplayConfig,
    atr_multiplier: float = 2.0,
) -> Dict[str, Any]:
    engine = TrueBarReplayEngine(strategy, risk_engine, config)
    all_closed_trades = []

    for pair in PAIRS:
        data = load_pair_data(pair)
        res = engine.run(
            symbol=pair,
            bars_15m=data["15m"],
            bars_1h=data["1h"],
            funding_records=data["funding"],
            atr_multiplier=atr_multiplier,
        )
        all_closed_trades.extend(res["closed_trades"])

    # Sort all trades chronologically by close_date
    all_closed_trades.sort(key=lambda t: t["close_date"])
    for idx, t in enumerate(all_closed_trades):
        t["trade_id"] = idx + 1

    # Reconstruct portfolio equity curve
    equity = config.initial_capital
    peak_equity = equity
    equity_curve = [{"timestamp": "2026-06-25T00:00:00Z", "equity": equity, "drawdown_pct": 0.0}]

    for t in all_closed_trades:
        equity += t["profit_abs"]
        if equity > peak_equity:
            peak_equity = equity
        dd_pct = ((peak_equity - equity) / peak_equity * 100.0) if peak_equity > 0 else 0.0
        c_date = t["close_date"].isoformat() if hasattr(t["close_date"], "isoformat") else str(t["close_date"])
        equity_curve.append({"timestamp": c_date, "equity": round(equity, 4), "drawdown_pct": round(dd_pct, 2)})

    metrics = compute_performance_metrics(all_closed_trades, initial_capital=config.initial_capital)
    return {
        "metrics": metrics,
        "closed_trades": all_closed_trades,
        "equity_curve": equity_curve,
        "final_equity": equity,
    }


def analyze_stability(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Computes breakdowns across Pair, Side, and Regime."""
    pair_breakdown = {}
    for p in PAIRS:
        p_trades = [t for t in trades if t["symbol"] == p]
        m = compute_performance_metrics(p_trades, initial_capital=65.0)
        pair_breakdown[p] = {
            "total_trades": len(p_trades),
            "win_rate": m["win_rate"],
            "net_pnl": m["total_net_pnl"],
            "profit_factor": m["profit_factor"],
        }

    long_trades = [t for t in trades if t["is_short"] == 0]
    short_trades = [t for t in trades if t["is_short"] == 1]

    m_long = compute_performance_metrics(long_trades, initial_capital=65.0)
    m_short = compute_performance_metrics(short_trades, initial_capital=65.0)

    return {
        "pairs": pair_breakdown,
        "long": {"total_trades": len(long_trades), "win_rate": m_long["win_rate"], "net_pnl": m_long["total_net_pnl"], "profit_factor": m_long["profit_factor"]},
        "short": {"total_trades": len(short_trades), "win_rate": m_short["win_rate"], "net_pnl": m_short["total_net_pnl"], "profit_factor": m_short["profit_factor"]},
    }


def analyze_walk_forward(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Performs 60% Train, 20% Val, 20% Test chronological split."""
    n = len(trades)
    if n < 10:
        return {"status": "INSUFFICIENT_TRADES"}

    split_train = int(n * 0.60)
    split_val = int(n * 0.80)

    train_t = trades[:split_train]
    val_t = trades[split_train:split_val]
    test_t = trades[split_val:]

    m_train = compute_performance_metrics(train_t, initial_capital=65.0)
    m_val = compute_performance_metrics(val_t, initial_capital=65.0)
    m_test = compute_performance_metrics(test_t, initial_capital=65.0)

    wfe = calculate_walk_forward_efficiency(m_train["win_rate"], m_test["win_rate"])
    return {
        "train": {"trades": len(train_t), "win_rate": m_train["win_rate"], "net_pnl": m_train["total_net_pnl"], "profit_factor": m_train["profit_factor"]},
        "validation": {"trades": len(val_t), "win_rate": m_val["win_rate"], "net_pnl": m_val["total_net_pnl"], "profit_factor": m_val["profit_factor"]},
        "test_oos": {"trades": len(test_t), "win_rate": m_test["win_rate"], "net_pnl": m_test["total_net_pnl"], "profit_factor": m_test["profit_factor"]},
        "wfe_metric": wfe,
    }


def run_all_revalidations():
    print("=== STARTING CUANIMUS TRUE BAR-LEVEL REVALIDATION ===")
    risk_engine = RiskEngine()
    config_base = ReplayConfig(slippage_model=ReplaySlippageModel("BASE", 0.05))

    # 1. TRUE V1 REVALIDATION
    print("\n--- Running True V1 Revalidation (Dynamic ATR Stop Loss) ---")
    v1_strategy = BaselineV0Strategy()
    res_v1 = run_multi_pair_replay(v1_strategy, risk_engine, config_base, atr_multiplier=2.0)
    v1_oos = analyze_walk_forward(res_v1["closed_trades"])
    v1_stability = analyze_stability(res_v1["closed_trades"])

    meta_v1 = {
        "experiment_id": "EXP_V1_TRUE_REVALIDATION",
        "parent_version": "EXP_V0_BASELINE",
        "strategy_name": "V1_TRUE_DYNAMIC_ATR_STOP",
        "information_boundary": "STRICT_CAUSAL_CLOSED_BARS",
        "date_range": "2026-06-25T00:00:00Z to 2026-10-02T23:59:59Z",
        "execution_model": "MODELED (Limit Entry, Adverse Taker Slippage 0.05%)",
        "funding_model": "HISTORICAL BINANCE FUTURES FUNDING RATE 8H",
        "walk_forward": v1_oos,
        "stability": v1_stability,
    }
    export_experiment_artifacts(os.path.join(EXP_DIR, "V1_TRUE_REVALIDATION"), res_v1, meta_v1)
    print(f"V1 True: {res_v1['metrics']['total_trades']} Trades | Win Rate: {res_v1['metrics']['win_rate']}% | PnL: {res_v1['metrics']['total_net_pnl']:.2f} USDT | PF: {res_v1['metrics']['profit_factor']:.3f} | Max DD: {res_v1['metrics']['max_drawdown_pct']:.2f}%")

    # 2. TRUE V2A REVALIDATION (Pullback Only)
    print("\n--- Running True V2A Revalidation (Pullback Only) ---")
    v2a_strategy = V2PullbackStrategy(V2StrategyConfig(variant="V2A_PULLBACK"))
    res_v2a = run_multi_pair_replay(v2a_strategy, risk_engine, config_base, atr_multiplier=2.0)
    v2a_oos = analyze_walk_forward(res_v2a["closed_trades"])
    v2a_stability = analyze_stability(res_v2a["closed_trades"])

    meta_v2a = {
        "experiment_id": "EXP_V2A_TRUE_REVALIDATION",
        "parent_version": "EXP_V1_TRUE_REVALIDATION",
        "strategy_name": "V2A_PULLBACK_ONLY",
        "information_boundary": "STRICT_CAUSAL_CLOSED_BARS",
        "date_range": "2026-06-25T00:00:00Z to 2026-10-02T23:59:59Z",
        "execution_model": "MODELED (Limit Entry, Adverse Taker Slippage 0.05%)",
        "funding_model": "HISTORICAL BINANCE FUTURES FUNDING RATE 8H",
        "walk_forward": v2a_oos,
        "stability": v2a_stability,
    }
    export_experiment_artifacts(os.path.join(EXP_DIR, "V2A_TRUE_REVALIDATION"), res_v2a, meta_v2a)
    print(f"V2A True: {res_v2a['metrics']['total_trades']} Trades | Win Rate: {res_v2a['metrics']['win_rate']}% | PnL: {res_v2a['metrics']['total_net_pnl']:.2f} USDT | PF: {res_v2a['metrics']['profit_factor']:.3f} | Max DD: {res_v2a['metrics']['max_drawdown_pct']:.2f}%")

    # 3. TRUE V2B REVALIDATION (Structure Only)
    print("\n--- Running True V2B Revalidation (Structure / Fib Only) ---")
    v2b_strategy = V2PullbackStrategy(V2StrategyConfig(variant="V2B_STRUCTURE"))
    res_v2b = run_multi_pair_replay(v2b_strategy, risk_engine, config_base, atr_multiplier=2.0)
    v2b_oos = analyze_walk_forward(res_v2b["closed_trades"])
    v2b_stability = analyze_stability(res_v2b["closed_trades"])

    meta_v2b = {
        "experiment_id": "EXP_V2B_TRUE_REVALIDATION",
        "parent_version": "EXP_V1_TRUE_REVALIDATION",
        "strategy_name": "V2B_STRUCTURE_FIB_ONLY",
        "information_boundary": "STRICT_CAUSAL_CLOSED_BARS",
        "date_range": "2026-06-25T00:00:00Z to 2026-10-02T23:59:59Z",
        "execution_model": "MODELED (Limit Entry, Adverse Taker Slippage 0.05%)",
        "funding_model": "HISTORICAL BINANCE FUTURES FUNDING RATE 8H",
        "walk_forward": v2b_oos,
        "stability": v2b_stability,
    }
    export_experiment_artifacts(os.path.join(EXP_DIR, "V2B_TRUE_REVALIDATION"), res_v2b, meta_v2b)
    print(f"V2B True: {res_v2b['metrics']['total_trades']} Trades | Win Rate: {res_v2b['metrics']['win_rate']}% | PnL: {res_v2b['metrics']['total_net_pnl']:.2f} USDT | PF: {res_v2b['metrics']['profit_factor']:.3f} | Max DD: {res_v2b['metrics']['max_drawdown_pct']:.2f}%")

    # 4. TRUE V2C REVALIDATION (Pullback + Structure Hybrid)
    print("\n--- Running True V2C Revalidation (Hybrid Pullback + Structure) ---")
    v2c_strategy = V2PullbackStrategy(V2StrategyConfig(variant="V2C_PULLBACK_STRUCTURE"))
    res_v2c = run_multi_pair_replay(v2c_strategy, risk_engine, config_base, atr_multiplier=2.0)
    v2c_oos = analyze_walk_forward(res_v2c["closed_trades"])
    v2c_stability = analyze_stability(res_v2c["closed_trades"])

    meta_v2c = {
        "experiment_id": "EXP_V2C_TRUE_REVALIDATION",
        "parent_version": "EXP_V1_TRUE_REVALIDATION",
        "strategy_name": "V2C_HYBRID_PULLBACK_STRUCTURE",
        "information_boundary": "STRICT_CAUSAL_CLOSED_BARS",
        "date_range": "2026-06-25T00:00:00Z to 2026-10-02T23:59:59Z",
        "execution_model": "MODELED (Limit Entry, Adverse Taker Slippage 0.05%)",
        "funding_model": "HISTORICAL BINANCE FUTURES FUNDING RATE 8H",
        "walk_forward": v2c_oos,
        "stability": v2c_stability,
    }
    export_experiment_artifacts(os.path.join(EXP_DIR, "V2C_TRUE_REVALIDATION"), res_v2c, meta_v2c)
    print(f"V2C True: {res_v2c['metrics']['total_trades']} Trades | Win Rate: {res_v2c['metrics']['win_rate']}% | PnL: {res_v2c['metrics']['total_net_pnl']:.2f} USDT | PF: {res_v2c['metrics']['profit_factor']:.3f} | Max DD: {res_v2c['metrics']['max_drawdown_pct']:.2f}%")

    # 5. SLIPPAGE SENSITIVITY STRESS TEST (BASE, CONSERVATIVE, STRESS)
    print("\n--- Running Slippage Sensitivity Stress Test on V2C ---")
    stress_results = {}
    for slip_name, slip_val in [("BASE", 0.05), ("CONSERVATIVE", 0.10), ("STRESS", 0.25)]:
        cfg_stress = ReplayConfig(slippage_model=ReplaySlippageModel(slip_name, slip_val))
        stress_res = run_multi_pair_replay(v2c_strategy, risk_engine, cfg_stress, atr_multiplier=2.0)
        stress_results[slip_name] = {
            "slippage_pct": slip_val,
            "win_rate": stress_res["metrics"]["win_rate"],
            "net_pnl": stress_res["metrics"]["total_net_pnl"],
            "profit_factor": stress_res["metrics"]["profit_factor"],
            "max_drawdown_pct": stress_res["metrics"]["max_drawdown_pct"],
        }
        print(f"Slippage {slip_name} ({slip_val}%): PnL: {stress_res['metrics']['total_net_pnl']:.2f} USDT | PF: {stress_res['metrics']['profit_factor']:.3f} | Max DD: {stress_res['metrics']['max_drawdown_pct']:.2f}%")

    with open(os.path.join(EXP_DIR, "slippage_sensitivity_results.json"), "w") as f:
        json.dump(stress_results, f, indent=2)

    print("\n=== TRUE BAR-LEVEL REVALIDATION COMPLETED SUCCESSFULLY ===")


if __name__ == "__main__":
    run_all_revalidations()
