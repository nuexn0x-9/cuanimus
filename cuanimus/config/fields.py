"""
CUANIMUS Config Field & Parameter Metadata Definition.
Defines metadata, valid ranges, descriptions, units, risk levels, and runtime mutability policies
for all configuration parameters across the platform.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, List, Dict


class RuntimePolicy(str, Enum):
    """Defines how a parameter can be modified while the engine is running."""
    HOT_SAFE = "HOT_SAFE"                          # Can be modified live without interrupting trading
    RESTART_REQUIRED = "RESTART_REQUIRED"          # Requires controlled engine restart / state drain
    NEVER_RUNTIME_MODIFIABLE = "NEVER_RUNTIME_MODIFIABLE"  # Hardcoded immutable once initialized


class RiskLevel(str, Enum):
    """Categorizes the financial/safety risk associated with altering this parameter."""
    LOW = "LOW"            # Cosmetic or telemetry (e.g., log level, alert channels)
    MEDIUM = "MEDIUM"      # Strategy hyperparameters (e.g., EMA period, stochastic levels)
    HIGH = "HIGH"          # Trading boundaries (e.g., risk per trade, stop distance, leverage)
    CRITICAL = "CRITICAL"  # System invariants (e.g., live trading lock, emergency kill switch)


@dataclass
class ConfigField:
    """Metadata describing a single configuration parameter."""
    name: str
    field_type: str  # "float", "int", "str", "bool", "list", "dict"
    default: Any
    description: str = ""
    unit: str = ""
    category: str = "general"
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    choices: Optional[List[Any]] = None
    risk_level: RiskLevel = RiskLevel.LOW
    runtime_policy: RuntimePolicy = RuntimePolicy.RESTART_REQUIRED
    is_safety_invariant: bool = False
    is_secret: bool = False

    def validate_value(self, value: Any, param_path: str = "") -> List[str]:
        """Validates a proposed value against constraints and type expectations."""
        errors = []
        path_str = param_path or self.name

        # Type checking and coercion check
        if self.field_type == "bool":
            if not isinstance(value, bool):
                errors.append(f"Parameter '{path_str}' must be boolean, got {type(value).__name__} ({value})")
        elif self.field_type in ("int", "float"):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append(f"Parameter '{path_str}' must be numeric ({self.field_type}), got {type(value).__name__} ({value})")
            else:
                if self.field_type == "int" and not isinstance(value, int) and not (isinstance(value, float) and value.is_integer()):
                    errors.append(f"Parameter '{path_str}' must be an integer, got float {value}")
                if self.minimum is not None and value < self.minimum:
                    errors.append(f"Parameter '{path_str}' value {value} is below minimum allowed {self.minimum} {self.unit}".strip())
                if self.maximum is not None and value > self.maximum:
                    errors.append(f"Parameter '{path_str}' value {value} exceeds maximum allowed {self.maximum} {self.unit}".strip())
        elif self.field_type == "str":
            if not isinstance(value, str):
                errors.append(f"Parameter '{path_str}' must be string, got {type(value).__name__}")
            elif self.choices is not None and value not in self.choices:
                errors.append(f"Parameter '{path_str}' value '{value}' is invalid. Allowed choices: {self.choices}")
        elif self.field_type == "list":
            if not isinstance(value, list):
                errors.append(f"Parameter '{path_str}' must be a list, got {type(value).__name__}")
        elif self.field_type == "dict":
            if not isinstance(value, dict):
                errors.append(f"Parameter '{path_str}' must be a dictionary, got {type(value).__name__}")

        return errors

    def to_schema_dict(self) -> Dict[str, Any]:
        """Exports metadata formatted for schema inspectors and UI form generation."""
        schema = {
            "name": self.name,
            "type": self.field_type,
            "default": self.default,
            "description": self.description,
            "unit": self.unit,
            "category": self.category,
            "risk_level": self.risk_level.value,
            "runtime_policy": self.runtime_policy.value,
            "is_safety_invariant": self.is_safety_invariant,
            "is_secret": self.is_secret,
        }
        if self.minimum is not None:
            schema["minimum"] = self.minimum
        if self.maximum is not None:
            schema["maximum"] = self.maximum
        if self.choices is not None:
            schema["choices"] = self.choices
        return schema
