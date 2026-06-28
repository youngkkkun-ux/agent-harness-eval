"""Command-line interface for HermesEval.

Commands:
  list    list/validate tasks in a task library directory
  run     run one task (or all) against Hermes, score it, store the result
  report  generate the harness-layer summary from stored results

The `--demo` flag swaps in a deterministic FakeDriver so the full pipeline can
be exercised without a real Hermes installation.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .models import RunConfig
from .pipeline import EvaluationPipeline
from .report import ReportGenerator
from .runner import DriverResult, Runner, SubprocessDriver
from .store import ResultStore
from .task_library import TaskLibrary, EmptyLibraryError


class DemoDriver:
    """Deterministic driver for demos/tests: echoes task-aware canned output."""

    def health_check(self) -> bool:
        return True

    def run(self, prompt: str, config: RunConfig, session_id: str) -> DriverResult:
        # Produce plausible content keyed off the prompt so rules can match.
        resp = "def solution():\n    return 5050  # uses httpx\n"
        return DriverResult(response=resp, input_tokens=120, output_tokens=40)

    def snapshot_state(self, session_id: str) -> dict:
        return {"available": True, "memory_md": "prefers httpx over requests",
                "memory_md_chars": 30, "skills_created": [], "memory_writes": ["httpx"]}


def _load_library(path: str) -> TaskLibrary:
    return TaskLibrary.from_directory(Path(path))


def cmd_list(args) -> int:
    valid, errors = TaskLibrary.validate_directory(Path(args.tasks))
    for t in valid:
        print(f"{t.task_id:10s} [{t.harness_layer:13s}] {t.name}")
    if errors:
        print("\n校验错误：", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
    if not valid and not errors:
        print("（任务库为空）", file=sys.stderr)
        return 1
    return 0


def _make_pipeline(args) -> EvaluationPipeline:
    driver = DemoDriver() if args.demo else SubprocessDriver(binary=args.binary)
    return EvaluationPipeline(runner=Runner(driver), judge=None)


def cmd_run(args) -> int:
    try:
        lib = _load_library(args.tasks)
    except EmptyLibraryError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    tasks = [lib.get(args.task)] if args.task else list(lib)
    if args.task and tasks[0] is None:
        print(f"未找到任务：{args.task}", file=sys.stderr)
        return 2

    store = ResultStore(args.db)
    config = RunConfig(model=args.model)
    config_id = store.save_config(args.config_name, config)
    pipeline = _make_pipeline(args)
    gen = ReportGenerator()

    for task in tasks:
        run, result = pipeline.evaluate(task, config)
        store.save_run(run, config_id=config_id)
        store.save_result(result)
        print(gen.run_report(run, result))
        print("\n" + "=" * 60 + "\n")
    store.close()
    return 0


def cmd_report(args) -> int:
    store = ResultStore(args.db)
    results = store.all_results()
    store.close()
    if not results:
        print("无有效数据。", file=sys.stderr)  # PRD 6.5
        return 1
    layer_map = {}
    try:
        lib = _load_library(args.tasks)
        layer_map = {t.task_id: t.harness_layer for t in lib}
    except EmptyLibraryError:
        pass
    print(ReportGenerator().harness_summary(results, layer_map, model=args.model))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="hermes-eval", description="HermesEval CLI")
    sub = p.add_subparsers(dest="command", required=True)

    pl = sub.add_parser("list", help="列出/校验任务库")
    pl.add_argument("--tasks", default="task_library")
    pl.set_defaults(func=cmd_list)

    pr = sub.add_parser("run", help="运行评测")
    pr.add_argument("--tasks", default="task_library")
    pr.add_argument("--task", default=None, help="只运行指定 task_id")
    pr.add_argument("--db", default="hermes_eval.db")
    pr.add_argument("--model", default="claude-opus-4-6")
    pr.add_argument("--config-name", default="default")
    pr.add_argument("--binary", default="hermes")
    pr.add_argument("--demo", action="store_true", help="使用内置 DemoDriver")
    pr.set_defaults(func=cmd_run)

    prep = sub.add_parser("report", help="生成 Harness 汇总报告")
    prep.add_argument("--db", default="hermes_eval.db")
    prep.add_argument("--tasks", default="task_library")
    prep.add_argument("--model", default="claude-opus-4-6")
    prep.set_defaults(func=cmd_report)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
