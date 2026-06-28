"""Tests for the Anthropic-backed LLM Judge client (offline, via a fake SDK client)."""
import json

import pytest

from hermes_eval.judge_clients import AnthropicJudgeClient


class _Block:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Resp:
    def __init__(self, *texts):
        self.content = [_Block(t) for t in texts]


class FakeMessages:
    def __init__(self, resp):
        self._resp = resp
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._resp


class FakeAnthropic:
    """Stands in for anthropic.Anthropic()."""

    def __init__(self, resp):
        self.messages = FakeMessages(resp)


def test_complete_returns_text():
    payload = json.dumps({"dimensions": [], "overall_summary": "ok",
                          "actionable_feedback": "none"})
    fake = FakeAnthropic(_Resp(payload))
    judge = AnthropicJudgeClient(client=fake)
    out = judge.complete("score this")
    assert out == payload


def test_uses_haiku_and_low_temperature_by_default():
    fake = FakeAnthropic(_Resp("{}"))
    AnthropicJudgeClient(client=fake).complete("p")
    call = fake.messages.calls[0]
    assert call["model"] == "claude-haiku-4-5"        # PRD-specified judge model
    assert call["temperature"] == 0.2                  # scoring stability
    assert call["messages"] == [{"role": "user", "content": "p"}]
    # Haiku 4.5 rejects effort/adaptive thinking — must not be sent.
    assert "thinking" not in call
    assert "output_config" not in call


def test_model_and_temperature_overridable():
    fake = FakeAnthropic(_Resp("{}"))
    AnthropicJudgeClient(client=fake, model="claude-sonnet-4-6",
                         temperature=0.0, max_tokens=512).complete("p")
    call = fake.messages.calls[0]
    assert call["model"] == "claude-sonnet-4-6"
    assert call["temperature"] == 0.0
    assert call["max_tokens"] == 512


def test_concatenates_multiple_text_blocks():
    fake = FakeAnthropic(_Resp('{"a":', ' 1}'))
    out = AnthropicJudgeClient(client=fake).complete("p")
    assert out == '{"a": 1}'


def test_integrates_with_llm_evaluator():
    from hermes_eval.evaluators.llm import LLMEvaluator
    from hermes_eval.models import EvalDimension, RunConfig, RunRecord, Task

    payload = json.dumps({
        "dimensions": [{"name": "correctness", "score": 8.0,
                        "critique": "good", "passed": True}],
        "overall_summary": "solid", "actionable_feedback": "ship it",
    })
    judge = AnthropicJudgeClient(client=FakeAnthropic(_Resp(payload)))
    task = Task(task_id="t1", name="n", harness_layer="memory", prompt="p",
                acceptance_criteria=["c"],
                eval_dimensions=[EvalDimension(name="correctness", weight=3.0, threshold=7.0)])
    run = RunRecord(run_id="r1", task_id="t1", session_id="s1",
                    config=RunConfig(model="m"), prompt="p", response="resp")
    scores, meta = LLMEvaluator(judge=judge).evaluate(task, run)
    assert scores[0].score == 8.0
    assert meta["actionable_feedback"] == "ship it"
