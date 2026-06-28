"""RuleEvaluator: deterministic checks against a run (PRD 5.3.1)."""
from __future__ import annotations

import re

from ..models import DimensionScore, ExpectedOutput, RunRecord


class RuleResult:
    """Result of one rule check (kept as a plain dict for storage)."""

    @staticmethod
    def make(rule: ExpectedOutput, passed: bool, detail: str = "") -> dict:
        return {
            "type": rule.type,
            "value": rule.value,
            "passed": passed,
            "detail": detail,
        }


class _SingleCheck:
    """A single rule outcome with a `.passed` attribute (for ergonomic tests)."""

    def __init__(self, rule: ExpectedOutput, passed: bool, detail: str = ""):
        self.rule = rule
        self.passed = passed
        self.detail = detail

    def as_dict(self) -> dict:
        return RuleResult.make(self.rule, self.passed, self.detail)


class RuleEvaluator:
    """Evaluates a list of ExpectedOutput rules; full marks if all pass."""

    DIMENSION = "rule_compliance"

    def check_one(self, rule: ExpectedOutput, run: RunRecord) -> _SingleCheck:
        passed = self._dispatch(rule, run)
        return _SingleCheck(rule, passed)

    def _dispatch(self, rule: ExpectedOutput, run: RunRecord) -> bool:
        t, v = rule.type, rule.value
        response = run.response or ""
        snap = run.hermes_state_snapshot or {}

        if t == "contains":
            return v in response
        if t == "not_contains":
            return v not in response
        if t == "regex_match":
            return re.search(v, response) is not None
        if t == "tool_called":
            return any(tc.tool == v for tc in run.tool_calls)
        if t == "tool_not_called":
            return not any(tc.tool == v for tc in run.tool_calls)
        if t == "skill_created":
            return any(v in s for s in snap.get("skills_created", []))
        if t == "memory_written":
            return any(v in m for m in snap.get("memory_writes", []))
        if t == "token_count_lt":
            total = run.input_tokens + run.output_tokens
            return total < int(v)
        raise ValueError(f"unknown rule type: {t}")  # pragma: no cover

    def evaluate(
        self, rules: list[ExpectedOutput], run: RunRecord
    ) -> tuple[DimensionScore, list[dict]]:
        """Return a DimensionScore (0-10) plus per-rule result dicts."""
        if not rules:
            return (
                DimensionScore(name=self.DIMENSION, score=None, source="rule"),
                [],
            )
        checks = [self.check_one(r, run) for r in rules]
        passed = sum(1 for c in checks if c.passed)
        score = 10.0 * passed / len(checks)
        ds = DimensionScore(
            name=self.DIMENSION,
            score=score,
            threshold=10.0,  # all rules must pass for this dimension to pass
            source="rule",
            critique=f"{passed}/{len(checks)} rules passed",
        )
        return ds, [c.as_dict() for c in checks]
