"""Tests for the ScoreAggregator (PRD 5.3.2)."""
from datetime import datetime

from hermes_eval.models import DimensionScore, EvalDimension, RunConfig, RunRecord, Task
from hermes_eval.evaluators.aggregator import ScoreAggregator


def _task():
    return Task(
        task_id="t1", name="agg", harness_layer="memory", prompt="p",
        acceptance_criteria=["c"],
        eval_dimensions=[
            EvalDimension(name="correctness", weight=3.0, threshold=7.0),
            EvalDimension(name="harness_utilization", weight=2.0, threshold=6.0),
        ],
    )


def _run(error=None, response="x"):
    return RunRecord(
        run_id="r1", task_id="t1", session_id="s1", config=RunConfig(model="m"),
        prompt="p", response=response, error=error,
    )


def test_weighted_average():
    scores = [
        DimensionScore(name="correctness", score=8.0, threshold=7.0),
        DimensionScore(name="harness_utilization", score=6.0, threshold=6.0),
    ]
    res = ScoreAggregator().aggregate(_task(), _run(), scores)
    # (8*3 + 6*2) / (3+2) = 36/5 = 7.2
    assert round(res.overall_score, 2) == 7.2
    assert res.passed is True


def test_fails_if_any_dimension_below_threshold():
    scores = [
        DimensionScore(name="correctness", score=5.0, threshold=7.0),
        DimensionScore(name="harness_utilization", score=9.0, threshold=6.0),
    ]
    res = ScoreAggregator().aggregate(_task(), _run(), scores)
    assert res.passed is False


def test_none_dimensions_excluded_from_average():
    scores = [
        DimensionScore(name="correctness", score=8.0, threshold=7.0),
        DimensionScore(name="state", score=None, threshold=6.0),  # skipped
    ]
    res = ScoreAggregator().aggregate(_task(), _run(), scores)
    assert res.overall_score == 8.0  # only correctness counts
    assert res.passed is True  # skipped dimension does not fail the run


def test_empty_response_scores_zero():
    # PRD 6.1: empty response -> all dimensions 0, run not counted in averages elsewhere
    res = ScoreAggregator().aggregate(_task(), _run(response=""), [])
    assert res.overall_score == 0.0
    assert res.passed is False
    assert res.flags.get("empty_response") is True


def test_error_run_scores_zero_and_flagged():
    res = ScoreAggregator().aggregate(_task(), _run(error="TIMEOUT"), [])
    assert res.overall_score == 0.0
    assert res.passed is False
    assert res.flags.get("error") == "TIMEOUT"


def test_unknown_dimension_threshold_defaults_to_zero():
    # a score whose name isn't in the task still aggregates, threshold from score itself
    scores = [DimensionScore(name="rule_compliance", score=10.0, threshold=10.0)]
    res = ScoreAggregator().aggregate(_task(), _run(), scores)
    assert res.overall_score == 10.0
    assert res.passed is True


def test_merges_meta_into_result():
    scores = [DimensionScore(name="correctness", score=8.0, threshold=7.0)]
    res = ScoreAggregator().aggregate(
        _task(), _run(), scores,
        rule_results=[{"type": "contains", "passed": True}],
        meta={"actionable_feedback": "tighten it up", "suspicious_score": True},
    )
    assert res.actionable_feedback == "tighten it up"
    assert res.flags.get("suspicious_score") is True
    assert res.rule_results == [{"type": "contains", "passed": True}]
    assert isinstance(res.evaluated_at, datetime)
