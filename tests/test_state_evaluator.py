"""Tests for the StateEvaluator (PRD 5.3.1 / 6.2 / 6.4)."""
from hermes_eval.models import EvalDimension, RunConfig, RunRecord, Task
from hermes_eval.evaluators.state import StateEvaluator


def _task(**over):
    base = dict(
        task_id="t1", name="state", harness_layer="memory", prompt="p",
        acceptance_criteria=["c"],
        eval_dimensions=[EvalDimension(name="state_consistency", weight=2.0, threshold=6.0)],
    )
    base.update(over)
    return Task(**base)


def _run(snapshot):
    return RunRecord(
        run_id="r1", task_id="t1", session_id="s1", config=RunConfig(model="m"),
        prompt="p", response="x", hermes_state_snapshot=snapshot,
    )


def test_state_available_and_passes():
    snap = {
        "available": True,
        "memory_md": "user prefers httpx over requests",
        "skills_created": ["use_httpx"],
        "memory_md_chars": 100,
    }
    ds, results = StateEvaluator(checks=["memory_contains:httpx", "skill_exists:httpx"]).evaluate(_task(), _run(snap))
    assert ds.score == 10.0
    assert all(r["passed"] for r in results)


def test_state_partial():
    snap = {"available": True, "memory_md": "nothing relevant", "skills_created": []}
    ds, _ = StateEvaluator(checks=["memory_contains:httpx", "skill_exists:httpx"]).evaluate(_task(), _run(snap))
    assert ds.score == 0.0


def test_state_unavailable_is_skipped():
    # PRD 6.2: cannot read SQLite -> dimension score None, excluded from average
    snap = {"available": False}
    ds, results = StateEvaluator(checks=["memory_contains:httpx"]).evaluate(_task(), _run(snap))
    assert ds.score is None
    assert results == []


def test_memory_budget_violation_detected():
    # PRD 6.4: memory.md > 2200 chars
    snap = {"available": True, "memory_md": "x" * 3000, "memory_md_chars": 3000}
    ds, results = StateEvaluator(checks=["memory_budget_ok"]).evaluate(_task(), _run(snap))
    assert ds.score == 0.0
    assert any("budget" in r["check"] for r in results)


def test_no_checks_returns_none():
    ds, results = StateEvaluator(checks=[]).evaluate(_task(), _run({"available": True}))
    assert ds.score is None
    assert results == []
