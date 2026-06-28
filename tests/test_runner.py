"""Tests for the Runner with an injected FakeDriver (PRD 5.2 / 6.1)."""
import pytest

from hermes_eval.models import EvalDimension, RunConfig, Task
from hermes_eval.runner import Runner, DriverResult, HermesUnavailable


def _task(requires_prior=False):
    return Task(
        task_id="mem-001", name="mem", harness_layer="memory", prompt="write a crawler",
        acceptance_criteria=["uses httpx"],
        eval_dimensions=[EvalDimension(name="correctness", weight=3.0, threshold=7.0)],
        requires_prior_session=requires_prior,
        prior_session_prompt="remember: I like httpx" if requires_prior else None,
    )


class FakeDriver:
    def __init__(self, result=None, healthy=True, snapshot=None, raise_on_run=None):
        self._result = result or DriverResult(response="ok httpx", input_tokens=10, output_tokens=5)
        self._healthy = healthy
        self._snapshot = snapshot or {"available": True}
        self._raise = raise_on_run
        self.runs = []          # list of (prompt, session_id)
        self.snapshots = 0

    def health_check(self):
        return self._healthy

    def run(self, prompt, config, session_id):
        self.runs.append((prompt, session_id))
        if self._raise:
            raise self._raise
        return self._result

    def snapshot_state(self, session_id):
        self.snapshots += 1
        return self._snapshot


def test_basic_run_produces_record():
    driver = FakeDriver()
    rec = Runner(driver).run_task(_task(), RunConfig(model="m"))
    assert rec.response == "ok httpx"
    assert rec.input_tokens == 10
    assert rec.error is None
    assert rec.task_id == "mem-001"
    assert rec.session_id  # auto-generated
    assert rec.hermes_state_snapshot == {"available": True}


def test_health_check_failure_skips_run():
    driver = FakeDriver(healthy=False)
    rec = Runner(driver).run_task(_task(), RunConfig(model="m"))
    assert rec.error == "HERMES_NOT_AVAILABLE"
    assert driver.runs == []  # never executed


def test_health_check_failure_can_raise_when_strict():
    with pytest.raises(HermesUnavailable):
        Runner(FakeDriver(healthy=False)).run_task(
            _task(), RunConfig(model="m"), strict=True
        )


def test_timeout_recorded():
    driver = FakeDriver(raise_on_run=TimeoutError("boom"))
    rec = Runner(driver).run_task(_task(), RunConfig(model="m"))
    assert rec.error == "TIMEOUT"


def test_empty_response_flagged():
    driver = FakeDriver(result=DriverResult(response="  "))
    rec = Runner(driver).run_task(_task(), RunConfig(model="m"))
    assert rec.error == "EMPTY_RESPONSE"


def test_prior_session_executed_first():
    driver = FakeDriver()
    Runner(driver).run_task(_task(requires_prior=True), RunConfig(model="m"))
    # two runs: prior session prompt, then the task prompt
    assert len(driver.runs) == 2
    assert driver.runs[0][0] == "remember: I like httpx"
    assert driver.runs[1][0] == "write a crawler"
    # prior session has its own id, distinct from the task session
    assert driver.runs[0][1] != driver.runs[1][1]


def test_run_id_and_session_id_unique_across_runs():
    driver = FakeDriver()
    r = Runner(driver)
    a = r.run_task(_task(), RunConfig(model="m"))
    b = r.run_task(_task(), RunConfig(model="m"))
    assert a.run_id != b.run_id
    assert a.session_id != b.session_id
