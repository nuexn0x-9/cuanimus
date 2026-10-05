"""
CUANIMUS Configuration JSON Schema Generator.
Generates an institutional-grade, JSON Schema Draft 7/2020-12 compliant schema dictionary
from the typed CuanimusConfig models.
This serves as the single source of truth for CLI validation, REST APIs, and future Web UIs.
"""
from typing import Dict, Any
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


def generate_json_schema() -> Dict[str, Any]:
    """Builds a complete JSON Schema representation of the CUANIMUS configuration domain."""
    section_models = {
        "environment": ("Environment Settings", EnvironmentConfig),
        "exchange": ("Exchange Connection Settings", ExchangeConfig),
        "market": ("Market Universe & Timeframes", MarketConfig),
        "strategy": ("Strategy Parameters", StrategyConfig),
        "risk": ("Risk Engine & Safeguards", RiskConfig),
        "execution": ("Order Execution Policy", ExecutionConfig),
        "ai": ("AI Intelligence Layer (Optional)", AIConfig),
        "backtest": ("Historical Replay Settings", BacktestConfig),
        "notification": ("Alert Dispatch Settings", NotificationConfig),
        "observability": ("Telemetry & Logging Settings", ObservabilityConfig),
    }

    schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "CUANIMUS Quantitative Trading Platform Configuration",
        "type": "object",
        "description": "Unified, typed configuration domain for research, backtesting, paper trading, and execution.",
        "properties": {},
        "required": list(section_models.keys()),
    }

    type_mapping = {
        "str": "string",
        "int": "integer",
        "float": "number",
        "bool": "boolean",
        "list": "array",
        "dict": "object",
    }

    for sec_id, (sec_title, sec_cls) in section_models.items():
        field_specs = sec_cls.get_field_specs()
        sec_properties = {}

        for param_id, spec in field_specs.items():
            prop: Dict[str, Any] = {
                "type": type_mapping.get(spec.field_type, "string"),
                "title": spec.name.replace("_", " ").title(),
                "description": spec.description,
                "default": spec.default,
                "x-cuanimus-unit": spec.unit,
                "x-cuanimus-category": spec.category,
                "x-cuanimus-risk-level": spec.risk_level.value,
                "x-cuanimus-runtime-policy": spec.runtime_policy.value,
                "x-cuanimus-safety-invariant": spec.is_safety_invariant,
            }
            if spec.minimum is not None:
                prop["minimum"] = spec.minimum
            if spec.maximum is not None:
                prop["maximum"] = spec.maximum
            if spec.choices is not None:
                prop["enum"] = spec.choices

            sec_properties[param_id] = prop

        schema["properties"][sec_id] = {
            "type": "object",
            "title": sec_title,
            "properties": sec_properties,
            "required": list(field_specs.keys()),
        }

    return schema
