"""Tests for consistency metrics (PRD 3.2 — 多次运行方差)."""
import math

from hermes_eval.metrics import (
    consistency_score,
    error_recurrence_rate,
    improvement_rate,
    learning_loop_metrics,
    skill_creation_rate,
    skill_hit_rate,
    variance_stats,
)
from hermes_eval.models import EvalResult, RunConfig, RunRecord


def test_identical_scores_are_perfectly_consistent():
    assert consistency_score([8.0, 8.0, 8.0]) == 10.0


def test_extreme_spread_is_zero_consistency():
    assert consistency_score([10.0, 0.0]) == 0.0


def test_moderate_spread():
    # mean 8, pstdev = sqrt(2/3) ≈ 0.8165 -> 10*(1-0.8165/5) ≈ 8.367
    val = consistency_score([7.0, 8.0, 9.0])
    assert math.isclose(val, 8.367, abs_tol=0.01)


def test_single_or_empty_returns_none():
    assert consistency_score([5.0]) is None
    assert consistency_score([]) is None


def test_variance_stats():
    s = variance_stats([7.0, 8.0, 9.0])
    assert s["n"] == 3
    assert s["mean"] == 8.0
    assert math.isclose(s["std"], math.sqrt(2 / 3), abs_tol=1e-9)
    assert math.isclose(s["consistency"], 8.367, abs_tol=0.01)


def test_variance_stats_empty():
    s = variance_stats([])
    assert s["n"] == 0
    assert s["mean"] is None
    assert s["std"] is None
    assert s["consistency"] is None


# ---------- learning-loop metrics (PRD 3.3) ----------

def test_improvement_rate():
    assert improvement_rate([5.0, 6.0, 8.0]) == 60.0          # (8-5)/5
    assert improvement_rate([5.0, None, 8.0]) == 60.0          # skips breakpoints
    assert improvement_rate([5.0]) is None
    assert improvement_rate([0.0, 8.0]) is None                # base 0 -> undefined


def test_error_recurrence_rate():
    # cat "a" appears in 2 runs -> recurs; "b" only once -> not
    sets = [{"a", "b"}, {"a"}, {"c"}]
    # distinct cats: a,b,c ; recurring (>=2): a -> 1/3
    assert error_recurrence_rate(sets) == round(1 / 3, 4)
    assert error_recurrence_rate([set(), set()]) is None       # no errors


def test_skill_creation_rate():
    assert skill_creation_rate([True, False, True, True]) == 0.75
    assert skill_creation_rate([]) is None


def test_skill_hit_rate():
    # use_httpx created at run0, reused at run1 -> hit; lint created at last run -> not eligible
    sets = [{"use_httpx"}, {"use_httpx"}, {"lint"}]
    assert skill_hit_rate(sets) == 1.0
    # created once, never reused
    assert skill_hit_rate([{"a"}, set(), set()]) == 0.0
    assert skill_hit_rate([set(), set()]) is None              # nothing created early


def _rec(run_id, error=None, skills=None):
    return RunRecord(run_id=run_id, task_id="fb-002", session_id="s",
                     config=RunConfig(model="m"), prompt="p", response="x",
                     error=error,
                     hermes_state_snapshot={"skills_created": skills or []})


def _res(run_id, score, rule_fails=None):
    return EvalResult(run_id=run_id, task_id="fb-002", overall_score=score,
                      passed=score >= 7,
                      rule_results=[{"type": t, "passed": False} for t in (rule_fails or [])])


def test_learning_loop_metrics_from_objects():
    records = [_rec("r1", skills=[]), _rec("r2", skills=["fix_date"]),
              _rec("r3", skills=["fix_date"])]
    results = [_res("r1", 5.0, rule_fails=["contains"]),
               _res("r2", 7.0),
               _res("r3", 8.0)]
    m = learning_loop_metrics(records, results)
    assert m["improvement_rate"] == 60.0          # (8-5)/5
    assert m["skill_creation_rate"] == round(2 / 3, 4)   # 2 of 3 runs created
    assert m["skill_hit_rate"] == 1.0             # fix_date created r2, reused r3
    # only the "contains" rule failure in r1, never recurs -> 0/1
    assert m["error_recurrence_rate"] == 0.0
