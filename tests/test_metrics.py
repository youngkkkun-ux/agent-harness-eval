"""Tests for consistency metrics (PRD 3.2 — 多次运行方差)."""
import math

from hermes_eval.metrics import consistency_score, variance_stats


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
