"""Runner: drives Hermes to execute a Task and captures a RunRecord (PRD 5.2).

The actual Hermes interaction is abstracted behind the HermesDriver protocol so
the orchestration logic (health checks, prior sessions, error mapping) is fully
testable with a FakeDriver. `SubprocessDriver` is the production implementation
(PRD method A: CLI subprocess + method C: gray-box state snapshot).
"""
from __future__ import annotations

import shlex
import subprocess
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol

from .models import RunConfig, RunRecord, Task, ToolCallRecord


@dataclass
class DriverResult:
    response: str = ""
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    raw_log: str = ""
    truncated: bool = False


class HermesDriver(Protocol):
    def health_check(self) -> bool: ...
    def run(self, prompt: str, config: RunConfig, session_id: str) -> DriverResult: ...
    def snapshot_state(self, session_id: str) -> dict: ...


class HermesUnavailable(Exception):
    """Raised in strict mode when the Hermes health check fails."""


class Runner:
    def __init__(self, driver: HermesDriver):
        self.driver = driver

    def run_task(
        self, task: Task, config: RunConfig, strict: bool = False
    ) -> RunRecord:
        run_id = uuid.uuid4().hex
        session_id = uuid.uuid4().hex
        started = datetime.now(timezone.utc)

        def _record(**over) -> RunRecord:
            base = dict(
                run_id=run_id, task_id=task.task_id, session_id=session_id,
                config=config, prompt=task.prompt,
                started_at=started, ended_at=datetime.now(timezone.utc),
            )
            base.update(over)
            return RunRecord(**base)

        # PRD 6.1: health check before running.
        if not self.driver.health_check():
            if strict:
                raise HermesUnavailable(task.task_id)
            return _record(error="HERMES_NOT_AVAILABLE")

        # PRD 6.1 / 6.5: establish prior session for memory tasks.
        if task.requires_prior_session and task.prior_session_prompt:
            prior_session = uuid.uuid4().hex
            try:
                self.driver.run(task.prior_session_prompt, config, prior_session)
                config = config.model_copy(update={"prior_session_id": prior_session})
            except Exception:
                return _record(error="PRIOR_SESSION_FAILED")

        try:
            result = self.driver.run(task.prompt, config, session_id)
        except TimeoutError:
            return _record(error="TIMEOUT")
        except ConnectionError:
            return _record(error="NETWORK_ERROR")
        except Exception as exc:  # noqa: BLE001 - record any driver failure
            return _record(error=f"RUNNER_ERROR: {exc}")

        try:
            snapshot = self.driver.snapshot_state(session_id)
        except Exception:
            snapshot = {"available": False}

        if not (result.response or "").strip():
            return _record(error="EMPTY_RESPONSE", hermes_state_snapshot=snapshot,
                           raw_log=result.raw_log)

        return _record(
            config=config,
            response=result.response,
            tool_calls=result.tool_calls,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            truncated=result.truncated,
            raw_log=result.raw_log,
            hermes_state_snapshot=snapshot,
        )


class SubprocessDriver:
    """Production driver: drives the `hermes` CLI as a subprocess (PRD 5.2.1 A+C).

    Not exercised by the offline test suite (requires a real Hermes install);
    kept minimal and dependency-free.
    """

    def __init__(self, binary: str = "hermes", hermes_home: str | None = None,
                 timeout: float = 300.0):
        self.binary = binary
        self.hermes_home = hermes_home
        self.timeout = timeout

    def health_check(self) -> bool:
        try:
            proc = subprocess.run(
                [self.binary, "--version"],
                capture_output=True, text=True, timeout=15,
            )
            return proc.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def run(self, prompt: str, config: RunConfig, session_id: str) -> DriverResult:
        cmd = [self.binary, "--session", session_id, "--model", config.model,
               "--prompt", prompt]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise TimeoutError(str(exc)) from exc
        log = (proc.stdout or "") + (proc.stderr or "")
        return DriverResult(
            response=proc.stdout or "",
            tool_calls=self._parse_tool_calls(log),
            raw_log=log,
        )

    @staticmethod
    def _parse_tool_calls(log: str) -> list[ToolCallRecord]:
        calls: list[ToolCallRecord] = []
        for line in log.splitlines():
            line = line.strip()
            if line.startswith("tool:"):
                # format: "tool: <name> input: <...>"
                rest = line[len("tool:"):].strip()
                name, _, inp = rest.partition("input:")
                calls.append(ToolCallRecord(tool=name.strip(), input=inp.strip()))
        return calls

    def snapshot_state(self, session_id: str) -> dict:
        # Phase 2 wires this to ~/.hermes/ SQLite + skills/ + memory.md.
        return {"available": False}
