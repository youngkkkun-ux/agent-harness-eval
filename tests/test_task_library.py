"""Tests for the Task Library (YAML loading + validation)."""
import textwrap

import pytest

from hermes_eval.task_library import (
    TaskLibrary,
    TaskValidationError,
    DuplicateTaskError,
    EmptyLibraryError,
)


def _write(path, content):
    path.write_text(textwrap.dedent(content), encoding="utf-8")
    return path


VALID_TASK = """\
task_id: mem-001
name: cross session memory
harness_layer: memory
category: episodic
difficulty: medium
prompt: |
  please write a crawler
expected_outputs:
  - type: contains
    value: httpx
  - type: not_contains
    value: requests
acceptance_criteria:
  - uses httpx
eval_dimensions:
  - name: correctness
    weight: 3.0
    threshold: 7.0
tags: [memory, episodic]
"""


def test_load_valid_task(tmp_path):
    _write(tmp_path / "mem-001.yaml", VALID_TASK)
    lib = TaskLibrary.from_directory(tmp_path)
    assert len(lib) == 1
    t = lib.get("mem-001")
    assert t.harness_layer == "memory"


def test_load_nested_directories(tmp_path):
    d = tmp_path / "layer4_memory" / "episodic"
    d.mkdir(parents=True)
    _write(d / "mem-001.yaml", VALID_TASK)
    lib = TaskLibrary.from_directory(tmp_path)
    assert lib.get("mem-001") is not None


def test_duplicate_task_id_rejected(tmp_path):
    _write(tmp_path / "a.yaml", VALID_TASK)
    _write(tmp_path / "b.yaml", VALID_TASK)  # same task_id
    with pytest.raises(DuplicateTaskError):
        TaskLibrary.from_directory(tmp_path)


def test_invalid_yaml_rejected(tmp_path):
    _write(tmp_path / "bad.yaml", "task_id: x\n  : : nope\n")
    with pytest.raises(TaskValidationError):
        TaskLibrary.from_directory(tmp_path)


def test_invalid_task_schema_rejected(tmp_path):
    # missing acceptance_criteria
    _write(
        tmp_path / "bad.yaml",
        """\
        task_id: x
        name: x
        harness_layer: memory
        prompt: hi
        acceptance_criteria: []
        eval_dimensions:
          - name: correctness
            weight: 1.0
            threshold: 5.0
        """,
    )
    with pytest.raises(TaskValidationError):
        TaskLibrary.from_directory(tmp_path)


def test_empty_library_raises(tmp_path):
    # PRD 6.5: empty task set errors out
    with pytest.raises(EmptyLibraryError):
        TaskLibrary.from_directory(tmp_path)


def test_filter_by_layer(tmp_path):
    _write(tmp_path / "mem.yaml", VALID_TASK)
    con = VALID_TASK.replace("task_id: mem-001", "task_id: con-001").replace(
        "harness_layer: memory", "harness_layer: constraints"
    )
    _write(tmp_path / "con.yaml", con)
    lib = TaskLibrary.from_directory(tmp_path)
    mem = lib.by_layer("memory")
    assert [t.task_id for t in mem] == ["mem-001"]


def test_validate_collects_errors_without_raising(tmp_path):
    # bad task should not prevent reporting; one valid + one invalid
    _write(tmp_path / "ok.yaml", VALID_TASK)
    _write(tmp_path / "bad.yaml", "task_id: y\nname: y\nharness_layer: nope\n")
    valid, errors = TaskLibrary.validate_directory(tmp_path)
    assert "mem-001" in {t.task_id for t in valid}
    assert len(errors) == 1
