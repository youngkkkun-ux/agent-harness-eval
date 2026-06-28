"""Consistency / variance metrics (PRD 3.2).

`consistency` measures how stable a task's score is across repeated runs:
10 when every run scores identically, 0 when scores span the full 0–10 range.
Mapping: consistency = 10 * (1 - std / 5), clamped to [0, 10] (population std;
5 is the maximum std for scores bounded in [0, 10]).
"""
from __future__ import annotations

import statistics
from collections import Counter
from typing import Optional, Sequence

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


# ---------- learning-loop metrics (PRD 3.3) ----------

def improvement_rate(scores: Sequence[Optional[float]]) -> Optional[float]:
    """(last - first) / first × 100, over non-null scores. None if base is 0/undefined."""
    valid = [s for s in scores if s is not None]
    if len(valid) < 2 or valid[0] == 0:
        return None
    return round(100.0 * (valid[-1] - valid[0]) / valid[0], 4)


def error_recurrence_rate(error_sets: Sequence[set]) -> Optional[float]:
    """Fraction of distinct error categories that appear in ≥2 runs. None if no errors."""
    counts: Counter = Counter()
    for s in error_sets:
        counts.update(set(s))
    if not counts:
        return None
    recurring = sum(1 for n in counts.values() if n >= 2)
    return round(recurring / len(counts), 4)


def skill_creation_rate(created_flags: Sequence[bool]) -> Optional[float]:
    """Fraction of runs that created at least one Skill. None if no runs."""
    if not created_flags:
        return None
    return round(sum(1 for f in created_flags if f) / len(created_flags), 4)


def skill_hit_rate(skill_sets: Sequence[set]) -> Optional[float]:
    """Of skills first created before the last run, fraction reused in a later run.

    None if no skill was created early enough to have a chance to recur.
    """
    first_seen: dict = {}
    for i, s in enumerate(skill_sets):
        for sk in s:
            first_seen.setdefault(sk, i)
    last = len(skill_sets) - 1
    eligible = [sk for sk, i in first_seen.items() if i < last]
    if not eligible:
        return None
    hit = sum(
        1 for sk in eligible
        if any(sk in skill_sets[j] for j in range(first_seen[sk] + 1, len(skill_sets)))
    )
    return round(hit / len(eligible), 4)


def learning_loop_metrics(records, results) -> dict:
    """Derive PRD 3.3 learning-loop metrics from a run/result sequence.

    - error categories per run: `run:<error>` and `rule:<type>` for failed rules
    - skill creation/reuse: from each run's `hermes_state_snapshot["skills_created"]`
    """
    scores: list[Optional[float]] = []
    error_sets: list[set] = []
    created_flags: list[bool] = []
    skill_sets: list[set] = []
    for rec, res in zip(records, results):
        scores.append(None if rec.error else res.overall_score)
        cats = set()
        if rec.error:
            cats.add(f"run:{rec.error}")
        for r in (res.rule_results or []):
            if not r.get("passed"):
                cats.add(f"rule:{r.get('type')}")
        error_sets.append(cats)
        skills = set((rec.hermes_state_snapshot or {}).get("skills_created", []))
        skill_sets.append(skills)
        created_flags.append(bool(skills))
    return {
        "improvement_rate": improvement_rate(scores),
        "error_recurrence_rate": error_recurrence_rate(error_sets),
        "skill_creation_rate": skill_creation_rate(created_flags),
        "skill_hit_rate": skill_hit_rate(skill_sets),
    }
