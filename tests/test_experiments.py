"""Tests for learning-curve and A/B comparison orchestration (PRD 5.5, 3.3)."""
import pytest

from hermes_eval.experiments import run_comparison, run_learning_curve
from hermes_eval.models import EvalDimension, ExpectedOutput, RunConfig, Task
from hermes_eval.pipeline import EvaluationPipeline
from hermes_eval.runner import DriverResult, Runner
from hermes_eval.store import ResultStore


def _task():
    return Task(
        task_id="fb-002", name="learn", harness_layer="feedback", prompt="p",
        expected_outputs=[ExpectedOutput(type="contains", value="httpx")],
        acceptance_criteria=["uses httpx"],
        eval_dimensions=[EvalDimension(name="correctness", weight=1.0, threshold=7.0)],
    )


class ImprovingDriver:
    """Fails the first round, succeeds afterwards (simulates a learning loop)."""

    def __init__(self):
        self.n = 0

    def health_check(self):
        return True

    def run(self, prompt, config, session_id):
        self.n += 1
        resp = "no lib" if self.n == 1 else "uses httpx"
        return DriverResult(response=resp, input_tokens=10, output_tokens=5)

    def snapshot_state(self, session_id):
        return {"available": True}


class SkillSensitiveDriver:
    """Good output only when skills are enabled (simulates Skill effect)."""

    def health_check(self):
        return True

    def run(self, prompt, config, session_id):
        resp = "uses httpx" if config.skill_enabled else "no lib"
        return DriverResult(response=resp, input_tokens=10, output_tokens=5)

    def snapshot_state(self, session_id):
        return {"available": True}


@pytest.fixture
def store(tmp_path):
    s = ResultStore(tmp_path / "eval.db")
    yield s
    s.close()


def test_learning_curve_runs_n_rounds_and_records(store):
    pipeline = EvaluationPipeline(runner=Runner(ImprovingDriver()), judge=None)
    cfg = RunConfig(model="m")
    cid = store.save_config("c", cfg)
    curve = run_learning_curve(pipeline, store, _task(), cfg, rounds=3, config_id=cid)

    assert [p["run_number"] for p in curve] == [1, 2, 3]
    assert curve[0]["score"] == 0.0      # first round fails the rule
    assert curve[1]["score"] == 10.0     # improves
    # persisted to the learning_curves table
    stored = store.get_learning_curve("fb-002", cid)
    assert [p["score"] for p in stored] == [0.0, 10.0, 10.0]


def test_learning_curve_records_breakpoint_on_error(store):
    class FlakyDriver(ImprovingDriver):
        def run(self, prompt, config, session_id):
            self.n += 1
            if self.n == 2:
                raise TimeoutError("boom")
            return DriverResult(response="uses httpx", input_tokens=10, output_tokens=5)

    pipeline = EvaluationPipeline(runner=Runner(FlakyDriver()), judge=None)
    cfg = RunConfig(model="m")
    cid = store.save_config("c", cfg)
    curve = run_learning_curve(pipeline, store, _task(), cfg, rounds=3, config_id=cid)
    assert curve[1]["score"] is None  # PRD 6.3: failed round -> null breakpoint
    assert curve[0]["score"] == 10.0


def test_comparison_runs_both_configs(store):
    pipeline = EvaluationPipeline(runner=Runner(SkillSensitiveDriver()), judge=None)
    res_a, res_b = run_comparison(
        pipeline, store, [_task()],
        RunConfig(model="m", skill_enabled=True), "with Skill",
        RunConfig(model="m", skill_enabled=False), "without Skill",
    )
    assert res_a[0].passed is True
    assert res_b[0].passed is False
