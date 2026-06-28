"""Report Generator: Markdown + JSON reports (PRD 5.5)."""
from __future__ import annotations

from statistics import mean

from .models import EvalResult, RunRecord


def _pct(x: float) -> str:
    return f"{x:.0f}%"


def _check(passed) -> str:
    return "✓" if passed else "✗"


class ReportGenerator:
    # ---------- single run report ----------

    def run_report(self, run: RunRecord, result: EvalResult) -> str:
        status = "✓ PASSED" if result.passed else "✗ FAILED"
        lines = [
            f"# Task: {result.task_id}",
            f"Run ID: {run.run_id}  |  Model: {run.config.model}",
            "",
            f"## 总分：{result.overall_score:.1f} / 10  {status}",
            "",
            "| 维度 | 得分 | 阈值 | 状态 |",
            "|------|------|------|------|",
        ]
        for d in result.dimension_scores:
            score = "—" if d.score is None else f"{d.score:.1f}"
            mark = "skip" if d.passed is None else _check(d.passed)
            lines.append(f"| {d.name} | {score} | {d.threshold:.1f} | {mark} |")

        if result.rule_results:
            lines += ["", "## 规则检查"]
            for r in result.rule_results:
                desc = f"{r.get('type')} {r.get('value', '')}".strip()
                lines.append(f"- {_check(r.get('passed'))} {desc}")

        if result.state_results:
            lines += ["", "## 状态验证"]
            for r in result.state_results:
                lines.append(f"- {_check(r.get('passed'))} {r.get('check')}")

        if result.critique:
            lines += ["", "## LLM Critique", result.critique]
        if result.actionable_feedback:
            lines += ["", "## 改进建议", result.actionable_feedback]
        if result.flags:
            flagstr = ", ".join(f"{k}={v}" for k, v in result.flags.items())
            lines += ["", f"> ⚠️ flags: {flagstr}"]
        return "\n".join(lines)

    # ---------- harness layer summary ----------

    def harness_summary(
        self, results: list[EvalResult], layer_map: dict[str, str], model: str
    ) -> str:
        by_layer: dict[str, list[EvalResult]] = {}
        for r in results:
            layer = layer_map.get(r.task_id, "unknown")
            by_layer.setdefault(layer, []).append(r)

        lines = [
            "# Hermes Harness 评测报告",
            f"模型：{model}",
            "",
            "## 五层 Harness 得分总览",
            "",
            "| Harness 层 | 任务数 | 平均分 | 通过率 |",
            "|-----------|--------|--------|--------|",
        ]
        for layer in sorted(by_layer):
            rs = by_layer[layer]
            avg = mean(r.overall_score for r in rs)
            pass_rate = 100.0 * sum(1 for r in rs if r.passed) / len(rs)
            lines.append(
                f"| {layer} | {len(rs)} | {avg:.1f} | {_pct(pass_rate)} |"
            )

        # weakest layer analysis
        if by_layer:
            weakest = min(
                by_layer, key=lambda l: mean(r.overall_score for r in by_layer[l])
            )
            wavg = mean(r.overall_score for r in by_layer[weakest])
            lines += ["", "## 最弱项分析", f"{weakest}（{wavg:.1f}/10）为最弱 Harness 层。"]
        return "\n".join(lines)

    # ---------- learning curve ----------

    def learning_curve_report(self, task_id: str, curve: list[dict]) -> str:
        rendered = []
        valid = [p for p in curve if p.get("score") is not None]
        for p in curve:
            s = "断点" if p.get("score") is None else f"{p['score']:.1f}"
            rendered.append(f"Run{p['run_number']}: {s}")
        line = " → ".join(rendered)

        improvement = ""
        if len(valid) >= 2 and valid[0]["score"]:
            rate = 100.0 * (valid[-1]["score"] - valid[0]["score"]) / valid[0]["score"]
            verdict = "✓ 学习循环有效" if rate > 0 else "✗ 无明显提升"
            improvement = f"\n改善率：{rate:+.1f}%  {verdict}"
        note = "" if len(valid) == len(curve) else "\n（曲线不完整，存在断点）"
        return f"## 学习曲线：{task_id}\n{line}{improvement}{note}"

    # ---------- comparison ----------

    def comparison_report(
        self, name_a: str, results_a: list[EvalResult],
        name_b: str, results_b: list[EvalResult],
    ) -> str:
        def stats(rs):
            avg = mean(r.overall_score for r in rs) if rs else 0.0
            pr = 100.0 * sum(1 for r in rs if r.passed) / len(rs) if rs else 0.0
            return avg, pr

        a_avg, a_pr = stats(results_a)
        b_avg, b_pr = stats(results_b)
        diff_pct = (100.0 * (a_avg - b_avg) / b_avg) if b_avg else 0.0
        return "\n".join([
            f"# 对比：{name_a} vs {name_b}",
            "",
            "| 指标 | " + name_a + " | " + name_b + " | 差值 |",
            "|------|------|------|------|",
            f"| 平均分 | {a_avg:.1f} | {b_avg:.1f} | {diff_pct:+.1f}% |",
            f"| 通过率 | {_pct(a_pr)} | {_pct(b_pr)} | {a_pr - b_pr:+.0f}pp |",
        ])

    # ---------- json ----------

    def json_export(self, results: list[EvalResult]) -> list[dict]:
        return [r.model_dump(mode="json") for r in results]
