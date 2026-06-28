"""Tests for the SQLite Result Store (PRD 5.4 / 6.3)."""
import pytest

from hermes_eval.models import (
    DimensionScore, EvalResult, RunConfig, RunRecord, ToolCallRecord,
)
from hermes_eval.store import ResultStore


def _run(run_id="r1", task_id="mem-001", response="uses httpx not requests"):
    return RunRecord(
        run_id=run_id, task_id=task_id, session_id="s1",
        config=RunConfig(model="claude-opus-4-6"), prompt="p", response=response,
        tool_calls=[ToolCallRecord(tool="memory_read", input="k")],
        input_tokens=10, output_tokens=5, duration_seconds=1.5,
    )


def _result(run_id="r1", task_id="mem-001", score=7.8, passed=True):
    return EvalResult(
        run_id=run_id, task_id=task_id, overall_score=score, passed=passed,
        dimension_scores=[DimensionScore(name="correctness", score=score, threshold=7.0)],
        critique="good",
    )


@pytest.fixture
def store(tmp_path):
    s = ResultStore(tmp_path / "eval.db")
    yield s
    s.close()


def test_save_and_get_run(store):
    cfg_id = store.save_config("baseline", RunConfig(model="m"))
    store.save_run(_run(), config_id=cfg_id)
    got = store.get_run("r1")
    assert got.response == "uses httpx not requests"
    assert got.tool_calls[0].tool == "memory_read"


def test_save_and_get_result(store):
    store.save_config("c", RunConfig(model="m"), config_id="c1")
    store.save_run(_run(), config_id="c1")
    store.save_result(_result())
    got = store.get_result("r1")
    assert got.overall_score == 7.8
    assert got.passed is True
    assert got.dimension_scores[0].name == "correctness"


def test_fts_search_runs(store):
    store.save_config("c", RunConfig(model="m"), config_id="c1")
    store.save_run(_run(run_id="r1", response="this mentions httpx"), config_id="c1")
    store.save_run(_run(run_id="r2", response="this mentions golang"), config_id="c1")
    hits = store.search_runs("httpx")
    assert "r1" in hits
    assert "r2" not in hits


def test_learning_curve_records_in_order(store):
    store.save_config("c", RunConfig(model="m"), config_id="c1")
    for n, sc in enumerate([5.2, 6.1, 7.0], start=1):
        store.save_run(_run(run_id=f"r{n}", task_id="fb-002"), config_id="c1")
        store.save_result(_result(run_id=f"r{n}", task_id="fb-002", score=sc))
        store.record_learning_point("fb-002", "c1", run_number=n, run_id=f"r{n}", score=sc)
    curve = store.get_learning_curve("fb-002", "c1")
    assert [p["score"] for p in curve] == [5.2, 6.1, 7.0]
    assert [p["run_number"] for p in curve] == [1, 2, 3]


def test_results_for_layer_summary(store):
    store.save_config("c", RunConfig(model="m"), config_id="c1")
    store.save_run(_run(run_id="r1", task_id="mem-001"), config_id="c1")
    store.save_result(_result(run_id="r1", task_id="mem-001", score=8.0, passed=True))
    store.save_run(_run(run_id="r2", task_id="mem-002"), config_id="c1")
    store.save_result(_result(run_id="r2", task_id="mem-002", score=6.0, passed=False))
    results = store.all_results()
    assert len(results) == 2


def test_get_missing_returns_none(store):
    assert store.get_run("nope") is None
    assert store.get_result("nope") is None


def test_reopen_persists_data(tmp_path):
    path = tmp_path / "eval.db"
    s1 = ResultStore(path)
    s1.save_config("c", RunConfig(model="m"), config_id="c1")
    s1.save_run(_run(), config_id="c1")
    s1.close()
    s2 = ResultStore(path)
    assert s2.get_run("r1") is not None
    s2.close()


def test_integrity_check_ok(store):
    assert store.integrity_ok() is True
