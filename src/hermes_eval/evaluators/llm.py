"""LLMEvaluator: LLM-as-Judge scoring with an injectable client (PRD 5.3.1).

The Judge LLM call is hidden behind the JudgeClient protocol so the evaluator
is fully testable offline. A production HTTP-backed client lives in
`hermes_eval.judge_clients` (not required for the core test suite).
"""
from __future__ import annotations

import json
import re
from typing import Protocol

from ..models import DimensionScore, RunRecord, Task

PROMPT_TEMPLATE = """\
你是一个严格的 AI Agent 评测专家，正在评估 Hermes Agent 对以下任务的回应质量。

## 任务定义
{task_description}

## 验收标准
{acceptance_criteria}

## Hermes 的回应
{hermes_response}

## 已知工具调用
{tool_calls}

## 评分维度（每项 0-10，严格评分，不给高分）
{dimensions}

请输出 JSON：
{{
  "dimensions": [
    {{"name": "维度名", "score": 7.5, "critique": "原因", "passed": true}}
  ],
  "overall_summary": "总体评价",
  "actionable_feedback": "具体可操作的改进建议"
}}

仅输出 JSON，不加任何其他内容。
"""


class JudgeClient(Protocol):
    def complete(self, prompt: str) -> str: ...


def _extract_json(raw: str) -> dict:
    """Parse a JSON object, tolerating leading/trailing prose or code fences."""
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?|\n?```$", "", raw).strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Last resort: grab the outermost {...} block.
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


class LLMEvaluator:
    def __init__(self, judge: JudgeClient, max_retries: int = 1):
        self.judge = judge
        self.max_retries = max_retries

    def build_prompt(self, task: Task, run: RunRecord) -> str:
        dims = "\n".join(
            f"- {d.name}（阈值 {d.threshold}）" for d in task.eval_dimensions
        )
        tool_calls = (
            "\n".join(f"- {tc.tool}: {tc.input}" for tc in run.tool_calls)
            or "（无工具调用）"
        )
        return PROMPT_TEMPLATE.format(
            task_description=f"{task.name}\n{task.prompt}",
            acceptance_criteria="\n".join(f"- {c}" for c in task.acceptance_criteria),
            hermes_response=run.response or "（空回应）",
            tool_calls=tool_calls,
            dimensions=dims,
        )

    def evaluate(
        self, task: Task, run: RunRecord
    ) -> tuple[list[DimensionScore], dict]:
        prompt = self.build_prompt(task, run)
        thresholds = {d.name: d.threshold for d in task.eval_dimensions}

        payload = None
        for _ in range(self.max_retries + 1):
            raw = self.judge.complete(prompt)
            try:
                payload = _extract_json(raw)
                break
            except json.JSONDecodeError:
                payload = None
                continue

        if payload is None:  # PRD 6.2: degrade to rule-only scoring
            return [], {"llm_eval_failed": True}

        scores: list[DimensionScore] = []
        for d in payload.get("dimensions", []):
            name = d.get("name", "")
            raw_score = d.get("score")
            scores.append(
                DimensionScore(
                    name=name,
                    score=raw_score,  # clamped in the model validator
                    threshold=thresholds.get(name, 0.0),
                    critique=d.get("critique", ""),
                    source="llm",
                )
            )

        meta = {
            "overall_summary": payload.get("overall_summary", ""),
            "actionable_feedback": payload.get("actionable_feedback", ""),
        }
        # PRD 6.2: all-10 or all-0 is suspicious.
        numeric = [s.score for s in scores if s.score is not None]
        if numeric and (all(s == 10.0 for s in numeric) or all(s == 0.0 for s in numeric)):
            meta["suspicious_score"] = True
        return scores, meta
