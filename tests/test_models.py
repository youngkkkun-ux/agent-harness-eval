"""Tests for the core Pydantic data contracts."""
import pytest
from pydantic import ValidationError

from hermes_eval.models import (
    EvalDimension,
    ExpectedOutput,
    Task,
    RunConfig,
    ToolCallRecord,
    RunRecord,
    DimensionScore,
    EvalResult,
)


# ---------- Task ----------

def _minimal_task_kwargs(**over):
    base = dict(
        task_id="mem-001",
        name="cross-session memory",
        harness_layer="memory",
        prompt="write a crawler",
        acceptance_criteria=["uses httpx"],
        eval_dimensions=[EvalDimension(name="correctness", weight=3.0, threshold=7.0)],
    )
    base.update(over)
    return base


def test_task_minimal_valid():
    t = Task(**_minimal_task_kwargs())
    assert t.task_id == "mem-001"
    assert t.harness_layer == "memory"
    assert t.difficulty == "medium"  # default


def test_task_requires_at_least_one_acceptance_criteria():
    # PRD 6.5: a task with no acceptance criteria cannot be validated -> reject
    with pytest.raises(ValidationError):
        Task(**_minimal_task_kwargs(acceptance_criteria=[]))


def test_task_requires_at_least_one_eval_dimension():
    with pytest.raises(ValidationError):
        Task(**_minimal_task_kwargs(eval_dimensions=[]))


def test_task_rejects_unknown_harness_layer():
    with pytest.raises(ValidationError):
        Task(**_minimal_task_kwargs(harness_layer="quantum"))


def test_task_invalid_regex_expected_output_rejected():
    # PRD 6.2: invalid regex blocks task from being stored (rejected at definition time)
    with pytest.raises(ValidationError):
        ExpectedOutput(type="regex_match", value="(unclosed")


def test_task_valid_regex_accepted():
    ok = ExpectedOutput(type="regex_match", value="htt(p|ps)x")
    t = Task(**_minimal_task_kwargs(expected_outputs=[ok]))
    assert t.expected_outputs[0].value == "htt(p|ps)x"


def test_expected_output_rejects_unknown_type():
    with pytest.raises(ValidationError):
        ExpectedOutput(type="telepathy", value="x")


# ---------- RunConfig ----------

def test_run_config_defaults():
    c = RunConfig(model="claude-opus-4-6")
    assert c.skill_enabled is True
    assert c.memory_enabled is True
    assert c.orchestration_enabled is True
    assert c.prior_session_id is None


# ---------- RunRecord ----------

def test_run_record_roundtrip():
    rec = RunRecord(
        run_id="r1",
        task_id="mem-001",
        session_id="s1",
        config=RunConfig(model="m"),
        prompt="p",
        response="resp httpx",
        tool_calls=[ToolCallRecord(tool="memory_read", input="k", output="httpx")],
        input_tokens=10,
        output_tokens=5,
        duration_seconds=1.2,
    )
    dumped = rec.model_dump()
    again = RunRecord(**dumped)
    assert again.tool_calls[0].tool == "memory_read"
    assert again.error is None


# ---------- EvalResult ----------

def test_dimension_score_clamped_and_passed():
    ds = DimensionScore(name="correctness", score=8.0, threshold=7.0)
    assert ds.passed is True
    ds2 = DimensionScore(name="correctness", score=5.0, threshold=7.0)
    assert ds2.passed is False


def test_dimension_score_allows_none_for_skipped():
    ds = DimensionScore(name="state", score=None, threshold=6.0)
    assert ds.passed is None  # skipped dimensions are neither pass nor fail
