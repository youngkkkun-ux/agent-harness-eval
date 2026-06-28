"""Multi-run experiment orchestration: learning curves and A/B comparisons.

Both helpers drive the EvaluationPipeline repeatedly and persist everything to
the ResultStore, returning data ready for ReportGenerator.
"""
from __future__ import annotations

from .metrics import variance_stats
from .models import EvalResult, RunConfig, Task
from .pipeline import EvaluationPipeline
from .store import ResultStore


def run_learning_curve(
    pipeline: EvaluationPipeline,
    store: ResultStore,
    task: Task,
    config: RunConfig,
    *,
    rounds: int,
    config_id: str,
) -> list[dict]:
    """Run `task` `rounds` times, recording the score trajectory (PRD 3.3).

    A round whose run errored is recorded as a null breakpoint (PRD 6.3).
    """
    curve: list[dict] = []
    for n in range(1, rounds + 1):
        run, result = pipeline.evaluate(task, config)
        store.save_run(run, config_id=config_id)
        store.save_result(result)
        score = None if run.error else result.overall_score
        store.record_learning_point(
            task.task_id, config_id, run_number=n, run_id=run.run_id, score=score
        )
        curve.append({"run_number": n, "run_id": run.run_id, "score": score})
    return curve


def run_consistency(
    pipeline: EvaluationPipeline,
    store: ResultStore,
    task: Task,
    config: RunConfig,
    *,
    repeats: int,
    config_id: str,
) -> dict:
    """Run `task` `repeats` times and measure score stability (PRD 3.2).

    Errored runs are excluded from the variance computation but counted.
    Returns: {n, errored, scores, mean, std, consistency}.
    """
    scores: list[float] = []
    errored = 0
    for _ in range(repeats):
        run, result = pipeline.evaluate(task, config)
        store.save_run(run, config_id=config_id)
        store.save_result(result)
        if run.error:
            errored += 1
        else:
            scores.append(result.overall_score)
    summary = variance_stats(scores)
    summary["scores"] = scores
    summary["errored"] = errored
    summary["task_id"] = task.task_id
    return summary


def run_comparison(
    pipeline: EvaluationPipeline,
    store: ResultStore,
    tasks: list[Task],
    config_a: RunConfig,
    name_a: str,
    config_b: RunConfig,
    name_b: str,
) -> tuple[list[EvalResult], list[EvalResult]]:
    """Evaluate a task set under two configs (e.g. with/without Skill)."""

    def _run(config: RunConfig, name: str) -> list[EvalResult]:
        config_id = store.save_config(name, config)
        results = []
        for task in tasks:
            run, result = pipeline.evaluate(task, config)
            store.save_run(run, config_id=config_id)
            store.save_result(result)
            results.append(result)
        return results

    return _run(config_a, name_a), _run(config_b, name_b)
