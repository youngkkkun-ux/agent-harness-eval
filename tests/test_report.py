"""Tests for the Report Generator (PRD 5.5)."""
from hermes_eval.models import DimensionScore, EvalResult, RunConfig, RunRecord
from hermes_eval.report import ReportGenerator


def _run():
    return RunRecord(
        run_id="r1", task_id="mem-001", session_id="s1",
        config=RunConfig(model="claude-opus-4-6"), prompt="p",
        response="uses httpx", input_tokens=100, output_tokens=50,
    )


def _result(score=7.8, passed=True, task_id="mem-001"):
    return EvalResult(
        run_id="r1", task_id=task_id, overall_score=score, passed=passed,
        dimension_scores=[
            DimensionScore(name="correctness", score=8.5, threshold=7.0),
            DimensionScore(name="harness_utilization", score=7.0, threshold=6.0),
        ],
        rule_results=[{"type": "contains", "value": "httpx", "passed": True}],
        critique="good code",
        actionable_feedback="add error handling",
    )


def test_run_report_contains_key_fields():
    md = ReportGenerator().run_report(_run(), _result())
    assert "mem-001" in md
    assert "7.8" in md
    assert "PASSED" in md
    assert "correctness" in md
    assert "8.5" in md
    assert "good code" in md
    assert "httpx" in md  # rule result


def test_run_report_marks_failed():
    md = ReportGenerator().run_report(_run(), _result(score=3.0, passed=False))
    assert "FAILED" in md


def test_harness_summary_groups_by_layer():
    layer_map = {"mem-001": "memory", "mem-002": "memory", "con-001": "constraints"}
    results = [
        _result(score=8.0, passed=True, task_id="mem-001"),
        _result(score=6.0, passed=False, task_id="mem-002"),
        _result(score=9.0, passed=True, task_id="con-001"),
    ]
    md = ReportGenerator().harness_summary(results, layer_map, model="claude-opus-4-6")
    assert "memory" in md
    assert "constraints" in md
    # memory: avg of 8 and 6 = 7.0, pass rate 50%
    assert "7.0" in md
    assert "50" in md  # pass rate percent


def test_learning_curve_report_computes_improvement():
    curve = [
        {"run_number": 1, "score": 5.0},
        {"run_number": 2, "score": 6.0},
        {"run_number": 5, "score": 8.0},
    ]
    md = ReportGenerator().learning_curve_report("fb-002", curve)
    assert "fb-002" in md
    assert "60" in md  # (8-5)/5 = 60% improvement


def test_learning_curve_handles_gap():
    # PRD 6.3: broken curve point is null
    curve = [
        {"run_number": 1, "score": 5.0},
        {"run_number": 2, "score": None},
        {"run_number": 3, "score": 7.0},
    ]
    md = ReportGenerator().learning_curve_report("fb-002", curve)
    assert "fb-002" in md  # does not crash on None


def test_comparison_report():
    md = ReportGenerator().comparison_report(
        "with Skill", [_result(score=8.1, passed=True)],
        "without Skill", [_result(score=6.3, passed=False)],
    )
    assert "with Skill" in md
    assert "without Skill" in md
    assert "8.1" in md
    assert "6.3" in md


def test_json_export_roundtrip():
    payload = ReportGenerator().json_export([_result()])
    assert payload[0]["task_id"] == "mem-001"
    assert payload[0]["overall_score"] == 7.8
