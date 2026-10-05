"""
CUANIMUS Layered Configuration Loader.
Implements multi-tiered configuration loading with strict precedence, deep merging,
provenance tracking, environment variable injection, and secret quarantine.

Precedence Hierarchy (Lowest to Highest):
1. Code Defaults
2. defaults.yaml (config/defaults.yaml)
3. Profile (config/profiles/{profile}.yaml)
4. Subsystem Configs (strategies/, risk/, execution/, exchanges/, environments/)
5. User Config File (explicit custom path)
6. Environment Variables (CUANIMUS_{SECTION}__{PARAM})
7. Runtime Programmatic Overrides
"""
import os
import yaml
import copy
from typing import Dict, Any, Optional, Tuple
from dataclasses import fields, is_dataclass

from cuanimus.config.models import (
    CuanimusConfig,
    EnvironmentConfig,
    ExchangeConfig,
    MarketConfig,
    StrategyConfig,
    RiskConfig,
    ExecutionConfig,
    AIConfig,
    BacktestConfig,
    NotificationConfig,
    ObservabilityConfig,
)


class ConfigLoader:
    def __init__(self, base_config_dir: str = "config"):
        self.base_config_dir = base_config_dir
        self.provenance_map: Dict[str, str] = {}

    def load(
        self,
        profile: Optional[str] = None,
        custom_config_path: Optional[str] = None,
        overrides: Optional[Dict[str, Any]] = None,
        strategy_override: Optional[str] = None,
        risk_override: Optional[str] = None,
        execution_override: Optional[str] = None,
        exchange_override: Optional[str] = None,
        env_override: Optional[str] = None,
    ) -> Tuple[CuanimusConfig, Dict[str, str]]:
        """
        Loads, merges, and instantiates CuanimusConfig following the strict precedence hierarchy.
        Returns (CuanimusConfig, provenance_map).
        """
        merged_raw: Dict[str, Any] = {}
        provenance: Dict[str, str] = {}

        # 1. Base Model Defaults
        default_instance = CuanimusConfig()
        merged_raw = default_instance.to_dict()
        self._record_provenance(merged_raw, "DEFAULT", provenance)

        # 2. File: config/defaults.yaml
        defaults_path = os.path.join(self.base_config_dir, "defaults.yaml")
        if os.path.exists(defaults_path):
            file_data = self._read_yaml_file(defaults_path)
            self._deep_merge(merged_raw, file_data, "defaults.yaml", provenance)

        # 3. File: Profile (e.g. config/profiles/balanced.yaml)
        active_profile = profile or merged_raw.get("risk", {}).get("profile_name", "balanced")
        profile_path = os.path.join(self.base_config_dir, "profiles", f"{active_profile}.yaml")
        if os.path.exists(profile_path):
            prof_data = self._read_yaml_file(profile_path)
            self._deep_merge(merged_raw, prof_data, f"profile/{active_profile}.yaml", provenance)

        # 4. Strategy File (e.g. config/strategies/{strategy}.yaml)
        strat_id = strategy_override or merged_raw.get("strategy", {}).get("strategy_id")
        if strat_id:
            strat_path = os.path.join(self.base_config_dir, "strategies", f"{strat_id}.yaml")
            if os.path.exists(strat_path):
                strat_data = self._read_yaml_file(strat_path)
                # Nest under 'strategy' if root keys don't specify it
                if "strategy" not in strat_data:
                    strat_data = {"strategy": strat_data}
                self._deep_merge(merged_raw, strat_data, f"strategies/{strat_id}.yaml", provenance)

        # 5. Risk File (e.g. config/risk/{risk}.yaml)
        risk_id = risk_override or merged_raw.get("risk", {}).get("profile_name")
        if risk_id:
            risk_path = os.path.join(self.base_config_dir, "risk", f"{risk_id}.yaml")
            if os.path.exists(risk_path):
                risk_data = self._read_yaml_file(risk_path)
                if "risk" not in risk_data:
                    risk_data = {"risk": risk_data}
                self._deep_merge(merged_raw, risk_data, f"risk/{risk_id}.yaml", provenance)

        # 6. Execution File (e.g. config/execution/{execution}.yaml)
        exec_id = execution_override or merged_raw.get("execution", {}).get("profile_name")
        if exec_id:
            exec_path = os.path.join(self.base_config_dir, "execution", f"{exec_id}.yaml")
            if os.path.exists(exec_path):
                exec_data = self._read_yaml_file(exec_path)
                if "execution" not in exec_data:
                    exec_data = {"execution": exec_data}
                self._deep_merge(merged_raw, exec_data, f"execution/{exec_id}.yaml", provenance)

        # 7. Exchange File (e.g. config/exchanges/{exchange}.yaml)
        exch_id = exchange_override or merged_raw.get("exchange", {}).get("provider")
        if exch_id:
            exch_path = os.path.join(self.base_config_dir, "exchanges", f"{exch_id}.yaml")
            if os.path.exists(exch_path):
                exch_data = self._read_yaml_file(exch_path)
                if "exchange" not in exch_data:
                    exch_data = {"exchange": exch_data}
                self._deep_merge(merged_raw, exch_data, f"exchanges/{exch_id}.yaml", provenance)

        # 8. Environment File (e.g. config/environments/{env}.yaml)
        env_id = env_override or merged_raw.get("environment", {}).get("env_name")
        if env_id:
            env_path = os.path.join(self.base_config_dir, "environments", f"{env_id}.yaml")
            if os.path.exists(env_path):
                env_data = self._read_yaml_file(env_path)
                if "environment" not in env_data:
                    env_data = {"environment": env_data}
                self._deep_merge(merged_raw, env_data, f"environments/{env_id}.yaml", provenance)

        # 9. Custom Config File (if passed explicitly via CLI --config)
        if custom_config_path and os.path.exists(custom_config_path):
            custom_data = self._read_yaml_file(custom_config_path)
            self._deep_merge(merged_raw, custom_data, f"custom_file:{custom_config_path}", provenance)

        # 10. Environment Variables (CUANIMUS_{SECTION}__{PARAM})
        self._apply_env_vars(merged_raw, provenance)

        # 11. Programmatic Overrides
        if overrides:
            self._deep_merge(merged_raw, overrides, "OVERRIDE", provenance)

        # Instantiate typed objects
        config_obj = self._build_config_instance(merged_raw)
        self.provenance_map = provenance
        return config_obj, provenance

    def _read_yaml_file(self, filepath: str) -> Dict[str, Any]:
        """Safely parses YAML configuration file."""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)
                return content if isinstance(content, dict) else {}
        except Exception as e:
            return {}

    def _deep_merge(self, base: Dict[str, Any], update: Dict[str, Any], source: str, provenance: Dict[str, str], prefix: str = ""):
        """Recursively merges dictionary `update` into `base` while logging provenance."""
        for k, v in update.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict) and k in base and isinstance(base[k], dict):
                self._deep_merge(base[k], v, source, provenance, prefix=full_key)
            else:
                base[k] = copy.deepcopy(v)
                provenance[full_key] = source

    def _record_provenance(self, data: Dict[str, Any], source: str, provenance: Dict[str, str], prefix: str = ""):
        """Records initial provenance for nested defaults."""
        for k, v in data.items():
            full_key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict) and not k.startswith("parameters"):
                self._record_provenance(v, source, provenance, prefix=full_key)
            else:
                provenance[full_key] = source

    def _apply_env_vars(self, merged_raw: Dict[str, Any], provenance: Dict[str, str]):
        """
        Parses environment variables formatted like:
        CUANIMUS_RISK__RISK_PER_TRADE_PCT=1.5
        CUANIMUS_ENVIRONMENT__ENV_NAME=testnet
        """
        prefix = "CUANIMUS_"
        for env_key, env_val in os.environ.items():
            if env_key.startswith(prefix):
                remainder = env_key[len(prefix):].lower()
                parts = remainder.split("__")
                if len(parts) == 2:
                    sec, param = parts[0], parts[1]
                    if sec in merged_raw and isinstance(merged_raw[sec], dict):
                        coerced = self._coerce_env_val(env_val)
                        merged_raw[sec][param] = coerced
                        provenance[f"{sec}.{param}"] = f"ENV_VAR:{env_key}"

    def _coerce_env_val(self, val_str: str) -> Any:
        """Coerces string environment values to bool, int, float, or str."""
        if val_str.lower() in ("true", "1", "yes"):
            return True
        if val_str.lower() in ("false", "0", "no"):
            return False
        try:
            if "." in val_str:
                return float(val_str)
            return int(val_str)
        except ValueError:
            return val_str

    def _build_config_instance(self, raw: Dict[str, Any]) -> CuanimusConfig:
        """Instantiates CuanimusConfig dataclass from merged dictionary."""
        def safe_subclass(cls, data_dict):
            valid_fields = {f.name for f in fields(cls)}
            filtered = {k: v for k, v in data_dict.items() if k in valid_fields}
            return cls(**filtered)

        return CuanimusConfig(
            environment=safe_subclass(EnvironmentConfig, raw.get("environment", {})),
            exchange=safe_subclass(ExchangeConfig, raw.get("exchange", {})),
            market=safe_subclass(MarketConfig, raw.get("market", {})),
            strategy=safe_subclass(StrategyConfig, raw.get("strategy", {})),
            risk=safe_subclass(RiskConfig, raw.get("risk", {})),
            execution=safe_subclass(ExecutionConfig, raw.get("execution", {})),
            ai=safe_subclass(AIConfig, raw.get("ai", {})),
            backtest=safe_subclass(BacktestConfig, raw.get("backtest", {})),
            notification=safe_subclass(NotificationConfig, raw.get("notification", {})),
            observability=safe_subclass(ObservabilityConfig, raw.get("observability", {})),
        )
