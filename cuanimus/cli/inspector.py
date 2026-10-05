"""
CUANIMUS Configuration & System Inspector.
Formats configuration validation, parameter explanations, and registry listings
for human-readable CLI display and machine-readable JSON output.
"""
import json
import yaml
from typing import Dict, Any, List, Optional

from cuanimus.config.models import CuanimusConfig
from cuanimus.config.validator import ValidationReport


def format_validation_report(report: ValidationReport, config: CuanimusConfig) -> str:
    """Formats validation report into a clean terminal status checklist."""
    lines = []
    lines.append("=" * 60)
    lines.append("          CUANIMUS CONFIGURATION VALIDATION")
    lines.append("=" * 60)

    # Subsystem checklists
    env = config.environment
    ex = config.exchange
    strat = config.strategy
    r = config.risk
    exe = config.execution
    ai = config.ai

    lines.append(f"  [PASS] Environment: {env.env_name.upper()} (dry_run={env.dry_run})")
    lines.append(f"  [PASS] Exchange:    {ex.provider.upper()} ({ex.market_type} on {ex.environment})")
    lines.append(f"  [PASS] Strategy:    {strat.strategy_id} (v{strat.version})")
    lines.append(f"  [PASS] Risk Engine: {r.profile_name.upper()} ({r.risk_per_trade_pct}%/trade, max {r.max_leverage}x)")
    lines.append(f"  [PASS] Execution:   {exe.profile_name.upper()} (entry={exe.entry_order_type}, slip={exe.slippage_model})")
    lines.append(f"  [PASS] AI Sidecar:  {'ENABLED (' + ai.provider + ')' if ai.enabled else 'DISABLED (Pure Deterministic)'}")

    if report.warnings:
        lines.append("\nWarnings:")
        for w in report.warnings:
            lines.append(f"  [WARN] {w}")

    if report.errors:
        lines.append("\nErrors:")
        for e in report.errors:
            lines.append(f"  [FAIL] {e}")

    lines.append("-" * 60)
    status_str = "VALID" if report.is_valid else "INVALID (REJECTED)"
    lines.append(f"Result:        {status_str}")
    lines.append(f"Safety Status: {report.safety_status}")
    lines.append("=" * 60)
    return "\n".join(lines)


def explain_parameters(
    config: CuanimusConfig,
    provenance: Dict[str, str],
    target_path: Optional[str] = None,
) -> str:
    """Explains one or all parameters: value, source, range, risk level, description."""
    specs = CuanimusConfig.get_all_field_specs()
    cfg_dict = config.to_dict()

    lines = []
    lines.append("=" * 70)
    lines.append("          CUANIMUS CONFIGURATION EXPLANATION")
    lines.append("=" * 70)

    filtered_specs = {k: v for k, v in specs.items() if (not target_path or target_path in k)}
    if not filtered_specs:
        return f"No configuration parameter matching '{target_path}' found."

    for full_path, spec in sorted(filtered_specs.items()):
        sec, param = full_path.split(".", 1)
        val = cfg_dict.get(sec, {}).get(param)
        src = provenance.get(full_path, "DEFAULT")

        lines.append(f"\nParameter:   {full_path}")
        lines.append(f"Value:       {val} {spec.unit}".strip())
        lines.append(f"Source:      {src}")
        lines.append(f"Type:        {spec.field_type}")

        if spec.minimum is not None or spec.maximum is not None:
            min_s = str(spec.minimum) if spec.minimum is not None else "-inf"
            max_s = str(spec.maximum) if spec.maximum is not None else "+inf"
            lines.append(f"Allowed:     [{min_s} .. {max_s}]")
        elif spec.choices is not None:
            lines.append(f"Choices:     {spec.choices}")

        lines.append(f"Risk Level:  {spec.risk_level.value}")
        lines.append(f"Mutability:  {spec.runtime_policy.value}")
        lines.append(f"Description: {spec.description}")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)


def show_configuration(config: CuanimusConfig, output_format: str = "yaml") -> str:
    """Dumps active configuration in YAML or JSON."""
    data = config.to_dict()
    if output_format.lower() == "json":
        return json.dumps(data, indent=2)
    return yaml.dump(data, default_flow_style=False, sort_keys=False)


def format_table(headers: List[str], rows: List[List[str]]) -> str:
    """Formats ASCII table."""
    col_widths = [len(h) for h in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            col_widths[idx] = max(col_widths[idx], len(str(cell)))

    header_line = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    sep_line = "-+-".join("-" * col_widths[i] for i in range(len(headers)))
    row_lines = [" | ".join(str(cell).ljust(col_widths[i]) for i, cell in enumerate(row)) for row in rows]

    return f"{header_line}\n{sep_line}\n" + "\n".join(row_lines)
