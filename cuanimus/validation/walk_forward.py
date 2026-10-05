"""
CUANIMUS Walk-Forward Analysis (WFA) Engine.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Dict, Any

@dataclass
class WindowSlice:
    fold_index: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime

def generate_walk_forward_windows(
    start_date: datetime,
    end_date: datetime,
    train_duration_days: int = 90,
    test_duration_days: int = 30,
    step_days: int = 30,
) -> List[WindowSlice]:
    windows = []
    current_train_start = start_date
    fold = 1

    while True:
        train_end = current_train_start + timedelta(days=train_duration_days)
        test_start = train_end
        test_end = test_start + timedelta(days=test_duration_days)

        if test_end > end_date:
            break

        windows.append(
            WindowSlice(
                fold_index=fold,
                train_start=current_train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
            )
        )

        current_train_start += timedelta(days=step_days)
        fold += 1

    return windows

def calculate_walk_forward_efficiency(
    annualized_return_in_sample: float,
    annualized_return_out_of_sample: float,
) -> Dict[str, Any]:
    if annualized_return_in_sample <= 0:
        return {
            "wfe_pct": 0.0,
            "status": "REJECTED_NEGATIVE_IN_SAMPLE",
            "is_robust": False,
        }

    wfe = (annualized_return_out_of_sample / annualized_return_in_sample) * 100.0
    is_robust = wfe >= 60.0
    status = "ROBUST" if is_robust else ("MARGINAL" if wfe >= 40.0 else "OVERFITTED")

    return {
        "wfe_pct": round(wfe, 2),
        "status": status,
        "is_robust": is_robust,
    }

