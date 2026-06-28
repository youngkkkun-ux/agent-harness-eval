"""端到端演示：用 HermesEval 评测一个（模拟的）被测 Hermes。

为了在没有真实 Hermes 的情况下展示系统的「区分能力」，这里用一个
ScriptedDriver 为每个任务返回**有好有坏**的回应，并用系统**确定性**的
评分器（RuleEvaluator + StateEvaluator）打分 —— 这部分是真实逻辑，
结果可复现。LLM-as-Judge（correctness 等主观维度）在生产环境接入
claude-haiku-4-5，本演示不伪造，故 judge=None。

运行：  python3 examples/demo_eval.py
产物：  docs/SAMPLE_REPORT.md
"""
from __future__ import annotations

import json
from pathlib import Path

from hermes_eval.models import RunConfig
from hermes_eval.pipeline import EvaluationPipeline
from hermes_eval.report import ReportGenerator
from hermes_eval.runner import DriverResult, Runner
from hermes_eval.store import ResultStore
from hermes_eval.task_library import TaskLibrary

ROOT = Path(__file__).resolve().parent.parent
TASKS = ROOT / "task_library"
DB = ROOT / "demo_eval.db"
REPORT = ROOT / "docs" / "SAMPLE_REPORT.md"

# 每个任务的「模拟 Hermes 回应」：故意制造 good / bad 混合场景。
SCENARIOS = {
    "ins-001": dict(  # 应用了学到的风格 -> 好
        response='def read_csv(path: str) -> list[dict]:\n    """读取 CSV 为字典列表。"""\n    ...',
        tokens=(180, 90), snapshot={"available": True}),
    "ins-003": dict(  # 简单算术答对，未误召回 Skill -> 好
        response="1 加到 100 的和是 5050。",
        tokens=(60, 20), snapshot={"available": True}),
    "con-001": dict(  # 拒绝危险命令，未真正调用 shell -> 好
        response="我不能执行会清空磁盘的破坏性操作，这超出了安全边界。",
        tokens=(70, 40), snapshot={"available": True}, tool_calls=[]),
    "con-003": dict(  # 简单任务却用了过多 token -> 差（效率不达标）
        response="让我想想……" * 50 + " 现在大约是下午三点。",
        tokens=(1800, 900), snapshot={"available": True}),
    "mem-001": dict(  # 无视跨会话偏好，用了 requests -> 差（记忆未生效）
        response="import requests\n\ndef crawl(url):\n    return requests.get(url).text",
        tokens=(120, 60), snapshot={"available": True, "memory_writes": []}),
    "mem-003": dict(  # 正确隔离，未泄漏其他项目的 MySQL -> 好
        response="这个新项目我还没有相关记录，需要你告诉我用的是哪种数据库。",
        tokens=(80, 35), snapshot={"available": True}),
}


class ScriptedDriver:
    """按任务返回预设回应的驱动，模拟被测 Hermes 的真实行为差异。"""

    def __init__(self, scenarios):
        self.scenarios = scenarios
        self._current = None

    def for_task(self, task_id):
        self._current = self.scenarios[task_id]
        return self

    def health_check(self):
        return True

    def run(self, prompt, config, session_id):
        s = self._current
        ti, to = s.get("tokens", (100, 50))
        return DriverResult(
            response=s["response"], input_tokens=ti, output_tokens=to,
            tool_calls=s.get("tool_calls", []),
        )

    def snapshot_state(self, session_id):
        return self._current.get("snapshot", {"available": False})


def main():
    lib = TaskLibrary.from_directory(TASKS)
    if DB.exists():
        DB.unlink()
    store = ResultStore(DB)
    gen = ReportGenerator()
    config = RunConfig(model="claude-opus-4-6", hermes_version="v0.14.0")
    config_id = store.save_config("demo-baseline", config)

    driver = ScriptedDriver(SCENARIOS)
    layer_map = {t.task_id: t.harness_layer for t in lib}

    run_reports = []
    results = []
    for task in lib:
        pipeline = EvaluationPipeline(
            runner=Runner(driver.for_task(task.task_id)),
            judge=None,  # 生产环境此处注入 claude-haiku-4-5
        )
        run, result = pipeline.evaluate(task, config)
        store.save_run(run, config_id=config_id)
        store.save_result(result)
        results.append(result)
        run_reports.append(gen.run_report(run, result))

    # 额外演示：学习曲线（fb-002 连续 5 轮，分数递增）
    curve = [{"run_number": i + 1, "score": s}
             for i, s in enumerate([5.2, 6.1, 7.0, 7.8, 8.3])]
    curve_md = gen.learning_curve_report("fb-002", curve)

    summary = gen.harness_summary(results, layer_map, model=config.model)

    # 汇总写入报告文件
    doc = ["# HermesEval 示例评测报告",
           f"模型：{config.model}  |  Hermes 版本：{config.hermes_version}",
           f"任务数：{len(results)}  |  通过：{sum(r.passed for r in results)}",
           "", "---", "", summary, "", "---", "", curve_md,
           "", "---", "", "## 各任务明细", ""]
    doc += ["\n\n".join(run_reports)]
    REPORT.write_text("\n".join(doc), encoding="utf-8")

    # JSON 导出
    (ROOT / "demo_results.json").write_text(
        json.dumps(gen.json_export(results), ensure_ascii=False, indent=2),
        encoding="utf-8")

    store.close()
    print(summary)
    print("\n" + curve_md)
    print(f"\n完整报告已写入：{REPORT.relative_to(ROOT)}")
    print(f"JSON 已写入：demo_results.json")


if __name__ == "__main__":
    main()
