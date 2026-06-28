"""Tests for the LLMEvaluator with an injected fake Judge client (PRD 5.3.1)."""
import json

from hermes_eval.models import EvalDimension, RunConfig, RunRecord, Task, ExpectedOutput
from hermes_eval.evaluators.llm import LLMEvaluator


def _task():
    return Task(
        task_id="t1",
        name="quality",
        harness_layer="memory",
        prompt="write a crawler",
        acceptance_criteria=["uses httpx"],
        eval_dimensions=[
            EvalDimension(name="correctness", weight=3.0, threshold=7.0),
            EvalDimension(name="harness_utilization", weight=2.0, threshold=6.0),
        ],
    )


def _run():
    return RunRecord(
        run_id="r1", task_id="t1", session_id="s1",
        config=RunConfig(model="m"), prompt="p", response="here is httpx code",
    )


class FakeJudge:
    """A scripted JudgeClient: returns whatever raw string it is given."""

    def __init__(self, raw, fail_times=0):
        self._raw = raw
        self._fail_times = fail_times
        self.calls = 0

    def complete(self, prompt: str) -> str:
        self.calls += 1
        if self.calls <= self._fail_times:
            return "not json at all"
        return self._raw


def _good_payload(c=8.5, h=7.0):
    return json.dumps({
        "dimensions": [
            {"name": "correctness", "score": c, "critique": "good", "passed": True},
            {"name": "harness_utilization", "score": h, "critique": "ok", "passed": True},
        ],
        "overall_summary": "solid",
        "actionable_feedback": "add tests",
    })


def test_parses_dimension_scores():
    ev = LLMEvaluator(judge=FakeJudge(_good_payload()))
    scores, meta = ev.evaluate(_task(), _run())
    by = {s.name: s for s in scores}
    assert by["correctness"].score == 8.5
    assert by["correctness"].source == "llm"
    assert by["correctness"].threshold == 7.0  # threshold pulled from task dimension
    assert meta["actionable_feedback"] == "add tests"


def test_bad_json_retries_once_then_succeeds():
    judge = FakeJudge(_good_payload(), fail_times=1)
    ev = LLMEvaluator(judge=judge)
    scores, meta = ev.evaluate(_task(), _run())
    assert judge.calls == 2  # one failure + one success
    assert meta.get("llm_eval_failed") is not True
    assert len(scores) == 2


def test_bad_json_twice_degrades_gracefully():
    judge = FakeJudge("still not json", fail_times=99)
    ev = LLMEvaluator(judge=judge)
    scores, meta = ev.evaluate(_task(), _run())
    assert meta["llm_eval_failed"] is True
    assert scores == []  # degraded: no LLM dimensions produced


def test_out_of_range_score_is_clamped():
    ev = LLMEvaluator(judge=FakeJudge(_good_payload(c=99.0, h=-4.0)))
    scores, _ = ev.evaluate(_task(), _run())
    by = {s.name: s for s in scores}
    assert by["correctness"].score == 10.0
    assert by["harness_utilization"].score == 0.0


def test_extreme_scores_flagged_suspicious():
    ev = LLMEvaluator(judge=FakeJudge(_good_payload(c=10.0, h=10.0)))
    _, meta = ev.evaluate(_task(), _run())
    assert meta.get("suspicious_score") is True


def test_prompt_includes_task_and_response():
    captured = {}

    class CapJudge:
        def complete(self, prompt):
            captured["prompt"] = prompt
            return _good_payload()

    LLMEvaluator(judge=CapJudge()).evaluate(_task(), _run())
    assert "write a crawler" in captured["prompt"]
    assert "here is httpx code" in captured["prompt"]
    assert "uses httpx" in captured["prompt"]  # acceptance criteria
