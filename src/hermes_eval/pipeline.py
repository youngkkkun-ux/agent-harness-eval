"""EvaluationPipeline: orchestrate Runner + evaluators into an EvalResult.

Ties together the layers described in PRD 5.3.2:
    RunRecord -> (Rule | LLM | State) -> ScoreAggregator -> EvalResult
"""
from __future__ import annotations

from typing import Optional

from .evaluators.aggregator import ScoreAggregator
from .evaluators.llm import JudgeClient, LLMEvaluator
from .evaluators.rule import RuleEvaluator
from .evaluators.state import StateEvaluator
from .models import DimensionScore, EvalResult, RunConfig, RunRecord, Task
from .runner import Runner


class EvaluationPipeline:
    def __init__(
        self,
        runner: Runner,
        judge: Optional[JudgeClient] = None,
        state_checks: Optional[list[str]] = None,
    ):
        self.runner = runner
        self.rule_eval = RuleEvaluator()
        self.llm_eval = LLMEvaluator(judge) if judge is not None else None
        self.state_eval = StateEvaluator(state_checks or [])
        self.aggregator = ScoreAggregator()

    def evaluate(
        self, task: Task, config: RunConfig, strict: bool = False
    ) -> tuple[RunRecord, EvalResult]:
        run = self.runner.run_task(task, config, strict=strict)
        result = self.score(task, run)
        return run, result

    def score(self, task: Task, run: RunRecord) -> EvalResult:
        dimension_scores: list[DimensionScore] = []
        meta: dict = {}

        # Rule evaluator
        rule_ds, rule_results = self.rule_eval.evaluate(task.expected_outputs, run)
        if rule_ds.score is not None:
            dimension_scores.append(rule_ds)

        # State evaluator
        state_ds, state_results = self.state_eval.evaluate(task, run)
        if state_ds.score is not None:
            dimension_scores.append(state_ds)

        # LLM evaluator (optional)
        if self.llm_eval is not None and (run.response or "").strip() and not run.error:
            llm_scores, llm_meta = self.llm_eval.evaluate(task, run)
            dimension_scores.extend(llm_scores)
            meta.update(llm_meta)

        return self.aggregator.aggregate(
            task, run, dimension_scores,
            rule_results=rule_results, state_results=state_results, meta=meta,
        )
