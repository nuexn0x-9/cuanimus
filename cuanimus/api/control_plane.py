"""
CUANIMUS Web Control Plane & REST/UI API Layer.
Provides headless programmatic API endpoints serving JSON Schema, configuration inspection,
validation services, strategy/risk registries, and experiment summaries.
Designed to be consumed directly by FastAPI, Flask, or future React/Vue Web UIs.
"""
import os
import json
from typing import Dict, Any, List, Optional

from cuanimus.config.loader import ConfigLoader
from cuanimus.config.validator import ConfigValidator
from cuanimus.config.schema import generate_json_schema
from cuanimus.strategy.registry import StrategyRegistry
from cuanimus.risk.registry import RiskProfileRegistry
from cuanimus.cli.doctor import CuanimusDoctor


class ControlPlaneAPI:
    """Headless API service for CUANIMUS Web Control Plane."""

    def __init__(self, base_dir: str = "."):
        self.base_dir = base_dir
        self.loader = ConfigLoader(base_config_dir=os.path.join(base_dir, "config"))
        self.validator = ConfigValidator()

    def get_config_schema(self) -> Dict[str, Any]:
        """Returns JSON Schema for dynamic UI form rendering."""
        return generate_json_schema()

    def get_system_status(self) -> Dict[str, Any]:
        """Returns current operational status and environment safety locks."""
        cfg, _ = self.loader.load()
        report = self.validator.validate(cfg)
        return {
            "environment": cfg.environment.env_name,
            "dry_run": cfg.environment.dry_run,
            "live_trading_enabled": cfg.environment.live_trading_enabled,
            "safety_status": report.safety_status,
            "is_valid": report.is_valid,
            "strategy_id": cfg.strategy.strategy_id,
            "risk_profile": cfg.risk.profile_name,
            "exchange": f"{cfg.exchange.provider} ({cfg.exchange.environment})",
            "ai_enabled": cfg.ai.enabled,
        }

    def list_strategies(self) -> List[Dict[str, Any]]:
        """Lists registered strategy plugins with metadata and parameters."""
        return StrategyRegistry.list_strategies()

    def inspect_strategy(self, strategy_id: str) -> Dict[str, Any]:
        """Returns detailed parameter specifications for a strategy plugin."""
        return StrategyRegistry.get_metadata(strategy_id).to_dict()

    def list_risk_profiles(self) -> List[Dict[str, Any]]:
        """Lists pre-packaged risk profiles."""
        return RiskProfileRegistry.list_profiles()

    def inspect_risk_profile(self, profile_name: str) -> Dict[str, Any]:
        """Returns parameters for a specific risk profile."""
        cfg = RiskProfileRegistry.get_config(profile_name)
        return cfg.__dict__

    def validate_configuration(self, raw_config: Dict[str, Any]) -> Dict[str, Any]:
        """Validates an incoming configuration payload submitted from Web UI."""
        cfg_obj = self.loader._build_config_instance(raw_config)
        report = self.validator.validate(cfg_obj)
        return report.to_dict()

    def run_doctor_diagnostics(self) -> List[Dict[str, str]]:
        """Runs full doctor health checks and returns structured results."""
        doctor = CuanimusDoctor(base_dir=self.base_dir)
        return doctor.run_all_checks()

    def list_experiments(self) -> List[Dict[str, Any]]:
        """Scans experiments directory and returns metadata and summary metrics."""
        exp_dir = os.path.join(self.base_dir, "experiments")
        experiments = []
        if os.path.exists(exp_dir):
            for entry in sorted(os.listdir(exp_dir)):
                ep = os.path.join(exp_dir, entry)
                if os.path.isdir(ep):
                    meta_path = os.path.join(ep, "metadata.json")
                    metrics_path = os.path.join(ep, "metrics.json")
                    item: Dict[str, Any] = {"experiment_id": entry, "path": ep}
                    if os.path.exists(meta_path):
                        with open(meta_path, "r") as f:
                            item["metadata"] = json.load(f)
                    if os.path.exists(metrics_path):
                        with open(metrics_path, "r") as f:
                            item["metrics"] = json.load(f)
                    experiments.append(item)
        return experiments
