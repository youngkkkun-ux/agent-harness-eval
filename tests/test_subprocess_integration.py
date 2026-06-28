"""End-to-end integration test for SubprocessDriver against a stub `hermes`.

This exercises the *real* integration path — actual subprocess execution, real
stdout/stderr parsing, and real ~/.hermes/ file reads — without needing the real
Hermes binary. The stub follows the CLI contract documented in
`SubprocessDriver` (README → 接入真实 Hermes). Swap the stub for a real Hermes
that honors the same contract and this path works unchanged.
"""
import os
import stat
import textwrap

import pytest

from hermes_eval.models import RunConfig
from hermes_eval.runner import Runner, SubprocessDriver

# Stub honoring the contract: --version; --prompt <text>; writes $HERMES_HOME
# state; emits `tool:` and `usage:` log lines on stderr; response on stdout.
STUB = """\
#!/bin/sh
if [ "$1" = "--version" ]; then echo "hermes 0.14.0"; exit 0; fi
prompt=""
while [ $# -gt 0 ]; do
  case "$1" in
    --prompt) prompt="$2"; shift 2 ;;
    *) shift ;;
  esac
done
mkdir -p "$HERMES_HOME/skills/use_httpx"
printf 'prefers httpx over requests\\n' > "$HERMES_HOME/memory.md"
echo "tool: memory_read input: httpx" >&2
echo "usage: input_tokens=42 output_tokens=17" >&2
printf 'Here is code using httpx for: %s\\n' "$prompt"
"""


@pytest.fixture
def stub_hermes(tmp_path):
    path = tmp_path / "hermes"
    path.write_text(textwrap.dedent(STUB), encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC | stat.S_IRWXU)
    return path


def _driver(stub, home):
    return SubprocessDriver(binary=str(stub), hermes_home=str(home))


def test_health_check_real_subprocess(stub_hermes, tmp_path):
    assert _driver(stub_hermes, tmp_path / "h").health_check() is True


def test_run_parses_response_tools_and_tokens(stub_hermes, tmp_path):
    home = tmp_path / "h"
    res = _driver(stub_hermes, home).run("write a crawler", RunConfig(model="m"), "s1")
    assert "httpx" in res.response
    assert res.input_tokens == 42
    assert res.output_tokens == 17
    assert any(tc.tool == "memory_read" for tc in res.tool_calls)
    assert "write a crawler" in res.response  # prompt was passed through


def test_snapshot_reads_state_written_by_subprocess(stub_hermes, tmp_path):
    home = tmp_path / "h"
    drv = _driver(stub_hermes, home)
    drv.run("p", RunConfig(model="m"), "s1")  # stub writes ~/.hermes state
    snap = drv.snapshot_state("s1")
    assert snap["available"] is True
    assert "httpx" in snap["memory_md"]
    assert "use_httpx" in snap["skills_created"]


def test_full_runner_end_to_end(stub_hermes, tmp_path):
    home = tmp_path / "h"
    from hermes_eval.models import Task, EvalDimension, ExpectedOutput

    task = Task(
        task_id="mem-001", name="mem", harness_layer="memory",
        prompt="write a crawler",
        expected_outputs=[ExpectedOutput(type="contains", value="httpx")],
        acceptance_criteria=["uses httpx"],
        eval_dimensions=[EvalDimension(name="correctness", weight=3.0, threshold=7.0)],
    )
    rec = Runner(_driver(stub_hermes, home)).run_task(task, RunConfig(model="m"))
    assert rec.error is None
    assert "httpx" in rec.response
    assert rec.input_tokens == 42
    assert rec.hermes_state_snapshot["available"] is True


def test_missing_binary_health_check_false(tmp_path):
    drv = SubprocessDriver(binary=str(tmp_path / "nonexistent-hermes"))
    assert drv.health_check() is False
