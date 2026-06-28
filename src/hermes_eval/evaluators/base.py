"""Shared types for evaluators."""
from __future__ import annotations

from typing import Protocol

from ..models import DimensionScore, RunRecord, Task


class Evaluator(Protocol):
    """An evaluator turns a RunRecord into one or more DimensionScores."""

    def evaluate(self, task: Task, run: RunRecord) -> list[DimensionScore]: ...


__all__ = ["Evaluator", "DimensionScore", "RunRecord", "Task"]
