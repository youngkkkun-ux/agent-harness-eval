"""Tests for the EvaluationPipeline that wires evaluators together."""
import json

from hermes_eval.models import EvalDimension, ExpectedOutput, RunConfig, Task
from hermes_eval.pipeline import EvaluationPipeline
from hermes_eval.runner import DriverResult, Runner


class FakeDriver:
    def __init__(self, response, snapshot=None):
        self._response = response
        self._snapshot = snapshot or {"available": True, "memory_md": "prefers httpx"}

    def health_check(self):
        return True

    def run(self, prompt, config, session_id):
        return DriverResult(response=self._response, input_tokens=50, output_tokens=20)

    def snapshot_state(self, session_id):
        return self._snapshot


class FakeJudge:
    def complete(self, prompt):
        return json.dumps({
            "dimensions": [
                {"name": "correctness", "score": 8.0, "critique": "ok", "passed": True}
            ],
            "overall_summary": "good",
            "actionable_feedback": "none",
        })


def _task():
    return Task(
        task_id="mem-001", name="mem", harness_layer="memory",
        prompt="write a crawler",
        expected_outputs=[
            ExpectedOutput(type="contains", value="httpx"),
            ExpectedOutput(type="not_contains", value="requests"),
        ],
        acceptance_criteria=["uses httpx"],
        eval_dimensions=[EvalDimension(name="correctness", weight=3.0, threshold=7.0)],
        requires_prior_session=True,
        prior_session_prompt="remember: httpx",
    )


def test_pipeline_end_to_end_pass():
    runner = Runner(FakeDriver(response="here is code using httpx"))
    pipeline = EvaluationPipeline(
        runner=runner, judge=FakeJudge(),
        state_checks=["memory_contains:httpx"],
    )
    run, result = pipeline.evaluate(_task(), RunConfig(model="m"))
    assert run.error is None
    assert result.passed is True
    names = {d.name for d in result.dimension_scores}
    assert {"rule_compliance", "correctness", "state_consistency"} <= names
    assert result.actionable_feedback == "none"


def test_pipeline_rule_failure_fails_run():
    runner = Runner(FakeDriver(response="here is code using requests"))
    pipeline = EvaluationPipeline(runner=runner, judge=FakeJudge())
    _, result = pipeline.evaluate(_task(), RunConfig(model="m"))
    # not_contains:requests fails -> rule_compliance below threshold -> fail
    assert result.passed is False


def test_pipeline_without_judge_uses_rules_only():
    runner = Runner(FakeDriver(response="httpx code here"))
    pipeline = EvaluationPipeline(runner=runner, judge=None)
    _, result = pipeline.evaluate(_task(), RunConfig(model="m"))
    sources = {d.source for d in result.dimension_scores}
    assert "llm" not in sources
    assert result.passed is True


def test_pipeline_error_run_scores_zero():
    class DeadDriver(FakeDriver):
        def health_check(self):
            return False

    runner = Runner(DeadDriver(response=""))
    pipeline = EvaluationPipeline(runner=runner, judge=None)
    run, result = pipeline.evaluate(_task(), RunConfig(model="m"))
    assert run.error == "HERMES_NOT_AVAILABLE"
    assert result.overall_score == 0.0
    assert result.passed is False
