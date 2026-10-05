"""
CUANIMUS Runtime Immutability & Hot-Reload Policy Manager.
Prevents uncoordinated in-flight parameter shifts from corrupting active positions or risk limits.

Policies:
- HOT_SAFE: Telemetry, alert flags, and non-structural thresholds that can update in-memory.
- RESTART_REQUIRED: Capital limits, timeframes, and sizing fractions that require graceful position drain / restart.
- NEVER_RUNTIME_MODIFIABLE: Core safety invariants, environment modes, and exchange providers.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Tuple

from cuanimus.config.models import CuanimusConfig
from cuanimus.config.fields import RuntimePolicy, ConfigField


class ReloadDecision(str, Enum):
    HOT_APPLY_PERMITTED = "HOT_APPLY_PERMITTED"
    RESTART_REQUIRED = "RESTART_REQUIRED"
    RELOAD_BLOCKED_CRITICAL = "RELOAD_BLOCKED_CRITICAL"


@dataclass
class ConfigChangeItem:
    parameter_path: str
    old_value: Any
    new_value: Any
    policy: RuntimePolicy
    description: str


@dataclass
class ReloadAssessment:
    decision: ReloadDecision
    changes: List[ConfigChangeItem]
    reasons: List[str]

    @property
    def can_hot_apply(self) -> bool:
        return self.decision == ReloadDecision.HOT_APPLY_PERMITTED


class RuntimeImmutabilityManager:
    """Audits runtime configuration updates to ensure state safety."""

    def __init__(self, active_config: CuanimusConfig):
        self.active_config = active_config
        self.field_specs = CuanimusConfig.get_all_field_specs()

    def assess_update(self, proposed_config: CuanimusConfig) -> ReloadAssessment:
        old_dict = self.active_config.to_dict()
        new_dict = proposed_config.to_dict()
        changes: List[ConfigChangeItem] = []
        reasons: List[str] = []

        has_restart_required = False
        has_never_modifiable = False

        for full_path, spec in self.field_specs.items():
            sec, param = full_path.split(".", 1)
            old_val = old_dict.get(sec, {}).get(param)
            new_val = new_dict.get(sec, {}).get(param)

            if old_val != new_val:
                item = ConfigChangeItem(
                    parameter_path=full_path,
                    old_value=old_val,
                    new_value=new_val,
                    policy=spec.runtime_policy,
                    description=spec.description,
                )
                changes.append(item)

                if spec.runtime_policy == RuntimePolicy.NEVER_RUNTIME_MODIFIABLE:
                    has_never_modifiable = True
                    reasons.append(
                        f"CRITICAL INVARIANT ALTERED: '{full_path}' changed from '{old_val}' to '{new_val}'. "
                        "This parameter is NEVER runtime-modifiable. Full process termination and re-init required."
                    )
                elif spec.runtime_policy == RuntimePolicy.RESTART_REQUIRED:
                    has_restart_required = True
                    reasons.append(
                        f"RESTART REQUIRED: '{full_path}' changed from '{old_val}' to '{new_val}'. "
                        "Requires controlled engine restart to re-initialize state."
                    )

        if has_never_modifiable:
            decision = ReloadDecision.RELOAD_BLOCKED_CRITICAL
        elif has_restart_required:
            decision = ReloadDecision.RESTART_REQUIRED
        elif changes:
            decision = ReloadDecision.HOT_APPLY_PERMITTED
            reasons.append("All altered parameters are categorized as HOT_SAFE. In-memory update approved.")
        else:
            decision = ReloadDecision.HOT_APPLY_PERMITTED
            reasons.append("No configuration changes detected.")

        return ReloadAssessment(
            decision=decision,
            changes=changes,
            reasons=reasons,
        )
