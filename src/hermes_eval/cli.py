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

from .experiments import run_comparison, run_learning_curve
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
    driver = (DemoDriver() if args.demo
              else SubprocessDriver(binary=args.binary,
                                    hermes_home=getattr(args, "hermes_home", None)))
    judge = None
    if getattr(args, "judge_model", None):
        # LLM-as-Judge via Anthropic (needs ANTHROPIC_API_KEY in the environment).
        from .judge_clients import AnthropicJudgeClient

        judge = AnthropicJudgeClient(model=args.judge_model)
    return EvaluationPipeline(runner=Runner(driver), judge=judge)


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


def cmd_learn(args) -> int:
    try:
        lib = _load_library(args.tasks)
    except EmptyLibraryError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    task = lib.get(args.task)
    if task is None:
        print(f"未找到任务：{args.task}", file=sys.stderr)
        return 2

    store = ResultStore(args.db)
    config = RunConfig(model=args.model)
    config_id = store.save_config(args.config_name, config)
    curve = run_learning_curve(_make_pipeline(args), store, task, config,
                               rounds=args.rounds, config_id=config_id)
    store.close()
    print(ReportGenerator().learning_curve_report(task.task_id, curve))
    return 0


def cmd_compare(args) -> int:
    try:
        lib = _load_library(args.tasks)
    except EmptyLibraryError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    tasks = lib.by_layer(args.layer) if args.layer else list(lib)
    if not tasks:
        print("没有匹配的任务。", file=sys.stderr)
        return 2

    store = ResultStore(args.db)
    field = args.field
    cfg_a = RunConfig(model=args.model, **{field: True})
    cfg_b = RunConfig(model=args.model, **{field: False})
    res_a, res_b = run_comparison(_make_pipeline(args), store, tasks,
                                  cfg_a, f"{field}=on", cfg_b, f"{field}=off")
    store.close()
    print(ReportGenerator().comparison_report(f"{field}=on", res_a,
                                              f"{field}=off", res_b))
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
    pr.add_argument("--hermes-home", default=None, help="被测 Hermes 的 HOME（灰盒状态读取）")
    pr.add_argument("--demo", action="store_true", help="使用内置 DemoDriver")
    pr.add_argument("--judge-model", default=None,
                    help="启用 LLM-as-Judge 的模型（如 claude-haiku-4-5，需 ANTHROPIC_API_KEY）")
    pr.set_defaults(func=cmd_run)

    prep = sub.add_parser("report", help="生成 Harness 汇总报告")
    prep.add_argument("--db", default="hermes_eval.db")
    prep.add_argument("--tasks", default="task_library")
    prep.add_argument("--model", default="claude-opus-4-6")
    prep.set_defaults(func=cmd_report)

    pln = sub.add_parser("learn", help="学习曲线：同一任务连续运行 N 轮")
    pln.add_argument("--task", required=True, help="task_id（建议 fb 类）")
    pln.add_argument("--rounds", type=int, default=5)
    pln.add_argument("--tasks", default="task_library")
    pln.add_argument("--db", default="hermes_eval.db")
    pln.add_argument("--model", default="claude-opus-4-6")
    pln.add_argument("--config-name", default="learning")
    pln.add_argument("--binary", default="hermes")
    pln.add_argument("--hermes-home", default=None)
    pln.add_argument("--demo", action="store_true")
    pln.add_argument("--judge-model", default=None)
    pln.set_defaults(func=cmd_learn)

    pc = sub.add_parser("compare", help="A/B 对比（如有/无某 Harness 层）")
    pc.add_argument("--field", default="skill_enabled",
                    choices=["skill_enabled", "memory_enabled", "orchestration_enabled"],
                    help="对比的 RunConfig 开关")
    pc.add_argument("--layer", default=None, help="只比较某 harness_layer 的任务")
    pc.add_argument("--tasks", default="task_library")
    pc.add_argument("--db", default="hermes_eval.db")
    pc.add_argument("--model", default="claude-opus-4-6")
    pc.add_argument("--binary", default="hermes")
    pc.add_argument("--hermes-home", default=None)
    pc.add_argument("--demo", action="store_true")
    pc.add_argument("--judge-model", default=None)
    pc.set_defaults(func=cmd_compare)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
