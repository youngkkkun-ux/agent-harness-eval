"""Tests for the RuleEvaluator (PRD 5.3.1)."""
from hermes_eval.models import ExpectedOutput, RunConfig, RunRecord, ToolCallRecord
from hermes_eval.evaluators.rule import RuleEvaluator


def _run(response="hello httpx world", tool_calls=None, snapshot=None,
         input_tokens=10, output_tokens=5):
    return RunRecord(
        run_id="r1",
        task_id="t1",
        session_id="s1",
        config=RunConfig(model="m"),
        prompt="p",
        response=response,
        tool_calls=tool_calls or [],
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        hermes_state_snapshot=snapshot or {},
    )


def _check(rule_type, value, run):
    return RuleEvaluator().check_one(ExpectedOutput(type=rule_type, value=value), run)


def test_contains():
    assert _check("contains", "httpx", _run()).passed is True
    assert _check("contains", "requests", _run()).passed is False


def test_not_contains():
    assert _check("not_contains", "requests", _run()).passed is True
    assert _check("not_contains", "httpx", _run()).passed is False


def test_regex_match():
    assert _check("regex_match", r"htt(p|ps)x", _run()).passed is True
    assert _check("regex_match", r"^zzz", _run()).passed is False


def test_tool_called():
    run = _run(tool_calls=[ToolCallRecord(tool="memory_read")])
    assert _check("tool_called", "memory_read", run).passed is True
    assert _check("tool_called", "shell", run).passed is False


def test_tool_not_called():
    run = _run(tool_calls=[ToolCallRecord(tool="memory_read")])
    assert _check("tool_not_called", "shell", run).passed is True
    assert _check("tool_not_called", "memory_read", run).passed is False


def test_skill_created():
    run = _run(snapshot={"skills_created": ["use_httpx", "lint_python"]})
    assert _check("skill_created", "httpx", run).passed is True
    assert _check("skill_created", "nonexistent", run).passed is False


def test_memory_written():
    run = _run(snapshot={"memory_writes": ["prefers httpx over requests"]})
    assert _check("memory_written", "httpx", run).passed is True
    assert _check("memory_written", "golang", run).passed is False


def test_token_count_lt():
    run = _run(input_tokens=100, output_tokens=100)  # total 200
    assert _check("token_count_lt", "500", run).passed is True
    assert _check("token_count_lt", "100", run).passed is False


def test_evaluate_aggregates_to_dimension_score():
    expected = [
        ExpectedOutput(type="contains", value="httpx"),
        ExpectedOutput(type="not_contains", value="requests"),
    ]
    ds, results = RuleEvaluator().evaluate(expected, _run())
    assert ds.source == "rule"
    assert ds.score == 10.0  # both pass -> full marks
    assert len(results) == 2


def test_evaluate_partial_pass_scaled_score():
    expected = [
        ExpectedOutput(type="contains", value="httpx"),     # pass
        ExpectedOutput(type="contains", value="requests"),  # fail
    ]
    ds, _ = RuleEvaluator().evaluate(expected, _run())
    assert ds.score == 5.0  # 1 of 2


def test_evaluate_no_rules_returns_none_score():
    ds, results = RuleEvaluator().evaluate([], _run())
    assert ds.score is None
    assert results == []
