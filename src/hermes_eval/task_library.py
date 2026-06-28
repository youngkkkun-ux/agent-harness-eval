"""Task Library: load and validate evaluation tasks from YAML (PRD 5.1)."""
from __future__ import annotations

from pathlib import Path
from typing import Iterator

import yaml
from pydantic import ValidationError

from .models import HarnessLayer, Task


class TaskValidationError(Exception):
    """A task file failed YAML parsing or schema validation."""


class DuplicateTaskError(Exception):
    """Two task files declare the same task_id (PRD 6.3)."""


class EmptyLibraryError(Exception):
    """No tasks were found (PRD 6.5)."""


def _parse_file(path: Path) -> Task:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise TaskValidationError(f"{path}: invalid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise TaskValidationError(f"{path}: expected a mapping at top level")
    try:
        return Task(**raw)
    except ValidationError as exc:
        raise TaskValidationError(f"{path}: schema error: {exc}") from exc


class TaskLibrary:
    """An in-memory collection of validated tasks, keyed by task_id."""

    def __init__(self, tasks: list[Task]):
        self._tasks: dict[str, Task] = {}
        for t in tasks:
            if t.task_id in self._tasks:
                raise DuplicateTaskError(f"duplicate task_id: {t.task_id}")
            self._tasks[t.task_id] = t

    # ----- construction -----

    @staticmethod
    def _iter_yaml(directory: Path) -> Iterator[Path]:
        for ext in ("*.yaml", "*.yml"):
            yield from sorted(Path(directory).rglob(ext))

    @classmethod
    def from_directory(cls, directory: Path) -> "TaskLibrary":
        """Load all tasks; raise on the first invalid file or duplicate id."""
        tasks = [_parse_file(p) for p in cls._iter_yaml(directory)]
        if not tasks:
            raise EmptyLibraryError(f"no task files found under {directory}")
        return cls(tasks)

    @classmethod
    def validate_directory(cls, directory: Path) -> tuple[list[Task], list[str]]:
        """Load everything, collecting per-file errors instead of raising.

        Returns (valid_tasks, error_messages). Useful for `hermes-eval list`.
        """
        valid: list[Task] = []
        errors: list[str] = []
        seen: set[str] = set()
        for p in cls._iter_yaml(directory):
            try:
                t = _parse_file(p)
            except TaskValidationError as exc:
                errors.append(str(exc))
                continue
            if t.task_id in seen:
                errors.append(f"{p}: duplicate task_id: {t.task_id}")
                continue
            seen.add(t.task_id)
            valid.append(t)
        return valid, errors

    # ----- access -----

    def __len__(self) -> int:
        return len(self._tasks)

    def __iter__(self) -> Iterator[Task]:
        return iter(self._tasks.values())

    def get(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def by_layer(self, layer: HarnessLayer) -> list[Task]:
        return [t for t in self._tasks.values() if t.harness_layer == layer]
