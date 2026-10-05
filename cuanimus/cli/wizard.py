"""
CUANIMUS Setup Wizard (cuanimus init).
Guides users through initializing a safe, validated trading configuration
without editing core source code.
Supports interactive CLI prompts and non-interactive scripted modes.
"""
import os
import yaml
from typing import Dict, Any, Optional

from cuanimus.config.loader import ConfigLoader
from cuanimus.config.validator import ConfigValidator


class InitWizard:
    def __init__(self, output_path: str = "cuanimus.user.yaml"):
        self.output_path = output_path

    def run_non_interactive(self, preset: str = "balanced") -> Dict[str, Any]:
        """Generates configuration from a named preset."""
        preset_clean = preset.lower()
        if preset_clean not in ("beginner", "conservative", "balanced", "aggressive"):
            preset_clean = "balanced"

        loader = ConfigLoader()
        cfg, _ = loader.load(profile=preset_clean)
        raw_dict = cfg.to_dict()

        # Enforce initial safe invariants
        raw_dict["environment"]["env_name"] = "paper"
        raw_dict["environment"]["dry_run"] = True
        raw_dict["environment"]["live_trading_enabled"] = False

        self._save_yaml(raw_dict, self.output_path)
        return raw_dict

    def run_interactive(self) -> Dict[str, Any]:
        """Prompts user through step-by-step setup in terminal."""
        print("=" * 60)
        print("          CUANIMUS PLATFORM INITIALIZATION WIZARD")
        print("=" * 60)
        print("Configure trading parameters without modifying core code.")
        print("Live real-capital trading is STRICTLY DISABLED by default.\n")

        # 1. Trading Profile
        print("Select Trading Profile Preset:")
        print("  [1] Beginner     (ETH only, 0.5% risk, 2x leverage, ultra-safe)")
        print("  [2] Conservative (ETH & XRP, 0.5% risk, 3x leverage, tight limits)")
        print("  [3] Balanced     (ADA, ETH, XRP, 1.0% risk, 5x leverage) [Recommended]")
        print("  [4] Aggressive   (ADA, ETH, XRP, 1.5% risk, 7x leverage, long & short)")
        choice = input("Enter choice [1-4, default 3]: ").strip() or "3"

        preset_map = {"1": "beginner", "2": "conservative", "3": "balanced", "4": "aggressive"}
        profile = preset_map.get(choice, "balanced")

        # 2. Environment
        print("\nSelect Operational Environment:")
        print("  [1] Paper Trading (In-memory real-time simulation) [Default]")
        print("  [2] Backtest Mode (Historical replay lab)")
        print("  [3] Binance Testnet (Exchange testnet sandbox)")
        print("  [4] Research Mode (Offline indicator analysis)")
        env_choice = input("Enter choice [1-4, default 1]: ").strip() or "1"
        env_map = {"1": "paper", "2": "backtest", "3": "testnet", "4": "research"}
        env_name = env_map.get(env_choice, "paper")

        # 3. Strategy Selection
        print("\nSelect Strategy Algorithm:")
        print("  [1] V2C Hybrid Pullback & Structure [Recommended]")
        print("  [2] V2B Market Structure & Fibonacci")
        print("  [3] V2A Pullback & Stochastic Reset")
        print("  [4] Baseline V0 / V1 Dynamic ATR Stop")
        strat_choice = input("Enter choice [1-4, default 1]: ").strip() or "1"
        strat_map = {"1": "hybrid_v2c", "2": "structure_v2b", "3": "pullback_v2a", "4": "baseline_v0"}
        strategy_id = strat_map.get(strat_choice, "hybrid_v2c")

        # Load preset base
        loader = ConfigLoader()
        cfg, _ = loader.load(profile=profile, strategy_override=strategy_id)
        raw_dict = cfg.to_dict()

        raw_dict["environment"]["env_name"] = env_name
        raw_dict["environment"]["dry_run"] = True
        raw_dict["environment"]["live_trading_enabled"] = False
        raw_dict["strategy"]["strategy_id"] = strategy_id

        # Validate
        cfg_obj = loader._build_config_instance(raw_dict)
        report = ConfigValidator().validate(cfg_obj)

        print("\n" + "-" * 60)
        print("Configuration Pre-flight Summary:")
        print(f"  Profile:     {profile.upper()}")
        print(f"  Environment: {env_name.upper()} (Safety: {report.safety_status})")
        print(f"  Strategy:    {strategy_id}")
        print(f"  Pairs:       {', '.join(raw_dict['market']['pairs'])}")
        print(f"  Risk/Trade:  {raw_dict['risk']['risk_per_trade_pct']}%")
        print(f"  Max Leverage:{raw_dict['risk']['max_leverage']}x")
        print(f"  Status:      {'VALID' if report.is_valid else 'INVALID'}")
        print("-" * 60)

        self._save_yaml(raw_dict, self.output_path)
        print(f"\n[OK] Configuration written successfully to '{self.output_path}'.")
        print("Next commands:")
        print(f"  cuanimus config validate --config {self.output_path}")
        print(f"  cuanimus backtest --config {self.output_path}")
        print(f"  cuanimus paper start --config {self.output_path}\n")

        return raw_dict

    def _save_yaml(self, data: Dict[str, Any], path: str):
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)
