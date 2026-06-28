"""Consistency / variance metrics (PRD 3.2).

`consistency` measures how stable a task's score is across repeated runs:
10 when every run scores identically, 0 when scores span the full 0–10 range.
Mapping: consistency = 10 * (1 - std / 5), clamped to [0, 10] (population std;
5 is the maximum std for scores bounded in [0, 10]).
"""
from __future__ import annotations

import statistics
from typing import Optional

_MAX_STD = 5.0  # max population std for values in [0, 10]


def consistency_score(scores: list[float]) -> Optional[float]:
    """Return a 0–10 consistency score, or None if fewer than 2 scores."""
    if len(scores) < 2:
        return None
    std = statistics.pstdev(scores)
    return round(max(0.0, min(10.0, 10.0 * (1.0 - std / _MAX_STD))), 4)


def variance_stats(scores: list[float]) -> dict:
    """Summary stats over a run's score sequence."""
    if not scores:
        return {"n": 0, "mean": None, "std": None, "consistency": None}
    return {
        "n": len(scores),
        "mean": round(statistics.fmean(scores), 4),
        "std": statistics.pstdev(scores) if len(scores) > 1 else 0.0,
        "consistency": consistency_score(scores),
    }
