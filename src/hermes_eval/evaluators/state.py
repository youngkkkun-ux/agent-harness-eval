"""StateEvaluator: verifies Hermes internal state from a snapshot (PRD 5.3.1).

Operates on the `hermes_state_snapshot` captured by the Runner's driver, so it
stays offline-testable. Each check is a "name[:arg]" string.
"""
from __future__ import annotations

from ..models import DimensionScore, RunRecord, Task

MEMORY_BUDGET_CHARS = 2200  # PRD 6.4


class StateEvaluator:
    DIMENSION = "state_consistency"

    def __init__(self, checks: list[str] | None = None):
        self.checks = checks or []

    def _run_check(self, spec: str, snap: dict) -> tuple[bool, str]:
        name, _, arg = spec.partition(":")
        if name == "memory_contains":
            return arg in snap.get("memory_md", ""), spec
        if name == "skill_exists":
            return any(arg in s for s in snap.get("skills_created", [])), spec
        if name == "memory_written":
            return any(arg in m for m in snap.get("memory_writes", [])), spec
        if name == "memory_budget_ok":
            chars = snap.get("memory_md_chars", len(snap.get("memory_md", "")))
            return chars <= MEMORY_BUDGET_CHARS, "memory_budget"
        if name == "session_linked":
            return bool(snap.get("prior_session_linked")), spec
        raise ValueError(f"unknown state check: {name}")  # pragma: no cover

    def evaluate(
        self, task: Task, run: RunRecord
    ) -> tuple[DimensionScore, list[dict]]:
        snap = run.hermes_state_snapshot or {}
        # PRD 6.2: state unreadable -> skip dimension (score None).
        if not self.checks or not snap.get("available", False):
            return (
                DimensionScore(name=self.DIMENSION, score=None, source="state"),
                [],
            )
        results = []
        passed = 0
        for spec in self.checks:
            ok, label = self._run_check(spec, snap)
            passed += int(ok)
            results.append({"check": label, "passed": ok})
        score = 10.0 * passed / len(self.checks)
        threshold = next(
            (d.threshold for d in task.eval_dimensions if d.name == self.DIMENSION),
            6.0,
        )
        ds = DimensionScore(
            name=self.DIMENSION,
            score=score,
            threshold=threshold,
            source="state",
            critique=f"{passed}/{len(self.checks)} state checks passed",
        )
        return ds, results
