"""ScoreAggregator: combine dimension scores into an EvalResult (PRD 5.3.2)."""
from __future__ import annotations

from datetime import datetime, timezone

from ..models import DimensionScore, EvalResult, RunRecord, Task


class ScoreAggregator:
    def aggregate(
        self,
        task: Task,
        run: RunRecord,
        dimension_scores: list[DimensionScore],
        rule_results: list[dict] | None = None,
        state_results: list[dict] | None = None,
        meta: dict | None = None,
    ) -> EvalResult:
        meta = dict(meta or {})
        now = datetime.now(timezone.utc)

        # PRD 6.1: error or empty response -> zero score, run flagged.
        if run.error:
            return self._zero(task, run, dimension_scores, rule_results,
                              state_results, meta, flag={"error": run.error}, ts=now)
        if not (run.response or "").strip():
            return self._zero(task, run, dimension_scores, rule_results,
                              state_results, meta, flag={"empty_response": True}, ts=now)

        scored = [d for d in dimension_scores if d.score is not None]
        if scored:
            total_w = sum(self._weight(task, d) for d in scored)
            overall = sum(d.score * self._weight(task, d) for d in scored) / total_w
        else:
            overall = 0.0

        # passed only if every scored dimension meets its threshold.
        passed = bool(scored) and all(d.passed for d in scored)

        flags = {k: v for k, v in meta.items()
                 if k in ("llm_eval_failed", "suspicious_score", "truncated")}
        if run.truncated:
            flags["truncated"] = True

        return EvalResult(
            run_id=run.run_id,
            task_id=task.task_id,
            overall_score=round(overall, 4),
            passed=passed,
            dimension_scores=dimension_scores,
            rule_results=rule_results or [],
            state_results=state_results or [],
            critique=meta.get("overall_summary", ""),
            actionable_feedback=meta.get("actionable_feedback", ""),
            flags=flags,
            evaluated_at=now,
        )

    @staticmethod
    def _weight(task: Task, ds: DimensionScore) -> float:
        for d in task.eval_dimensions:
            if d.name == ds.name:
                return d.weight
        return 1.0  # dimensions not declared on the task (e.g. rule_compliance)

    def _zero(self, task, run, dimension_scores, rule_results, state_results,
              meta, flag, ts) -> EvalResult:
        flags = dict(flag)
        return EvalResult(
            run_id=run.run_id,
            task_id=task.task_id,
            overall_score=0.0,
            passed=False,
            dimension_scores=dimension_scores,
            rule_results=rule_results or [],
            state_results=state_results or [],
            critique=meta.get("overall_summary", ""),
            actionable_feedback=meta.get("actionable_feedback", ""),
            flags=flags,
            evaluated_at=ts,
        )
