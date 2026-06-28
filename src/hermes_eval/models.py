"""Core Pydantic data contracts for HermesEval.

These models are the system's contract: Task definitions (Task Library),
run records (Runner) and evaluation results (Evaluator / Result Store).
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# Hermes five-layer harness.
HarnessLayer = Literal[
    "instructions",   # L1 Skill system
    "constraints",    # L2 permissions + sandbox
    "feedback",       # L3 learning loop
    "memory",         # L4 three-tier memory
    "orchestration",  # L5 sub-agent orchestration
    "all",            # end-to-end tasks
]

Difficulty = Literal["easy", "medium", "hard"]

# Rule types understood by the RuleEvaluator (PRD 5.3.1).
ExpectedOutputType = Literal[
    "contains",
    "not_contains",
    "regex_match",
    "tool_called",
    "tool_not_called",
    "skill_created",
    "memory_written",
    "token_count_lt",
    "subagent_count_lte",  # orchestration: sub-agent fan-out limit (PRD 6.4)
]


class ExpectedOutput(BaseModel):
    """A single rule-based check against a run."""

    type: ExpectedOutputType
    value: str

    @field_validator("value")
    @classmethod
    def _validate_regex(cls, v: str, info):
        if info.data.get("type") == "regex_match":
            try:
                re.compile(v)
            except re.error as exc:  # PRD 6.2: invalid regex blocks task
                raise ValueError(f"invalid regex: {exc}") from exc
        return v


class EvalDimension(BaseModel):
    """A scoring dimension with weight and pass threshold."""

    name: str
    weight: float = Field(gt=0)
    threshold: float = Field(ge=0, le=10)


class Task(BaseModel):
    """An evaluation task (PRD 5.1.1)."""

    task_id: str
    name: str
    harness_layer: HarnessLayer
    category: Optional[str] = None
    difficulty: Difficulty = "medium"
    prompt: str
    expected_outputs: list[ExpectedOutput] = Field(default_factory=list)
    acceptance_criteria: list[str]
    eval_dimensions: list[EvalDimension]
    requires_prior_session: bool = False
    prior_session_prompt: Optional[str] = None
    tags: list[str] = Field(default_factory=list)

    @field_validator("acceptance_criteria")
    @classmethod
    def _at_least_one_criteria(cls, v):
        # PRD 6.5: a task with no acceptance criteria cannot be verified.
        if not v:
            raise ValueError("at least one acceptance_criteria is required")
        return v

    @field_validator("eval_dimensions")
    @classmethod
    def _at_least_one_dimension(cls, v):
        if not v:
            raise ValueError("at least one eval_dimension is required")
        return v

    @model_validator(mode="after")
    def _prior_session_consistency(self):
        if self.requires_prior_session and not self.prior_session_prompt:
            raise ValueError(
                "requires_prior_session=True needs a prior_session_prompt"
            )
        return self


class RunConfig(BaseModel):
    """Configuration for a single run (PRD 5.2.2)."""

    model: str
    skill_enabled: bool = True
    memory_enabled: bool = True
    orchestration_enabled: bool = True
    hermes_version: str = "unknown"
    prior_session_id: Optional[str] = None


class ToolCallRecord(BaseModel):
    tool: str
    input: str = ""
    output: str = ""


class RunRecord(BaseModel):
    """Full data captured for one run (PRD 5.2.2)."""

    run_id: str
    task_id: str
    session_id: str
    config: RunConfig
    prompt: str
    response: str = ""
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    duration_seconds: float = 0.0
    hermes_state_snapshot: dict = Field(default_factory=dict)
    raw_log: str = ""
    error: Optional[str] = None
    truncated: bool = False
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


class DimensionScore(BaseModel):
    """Score for one dimension. score=None means the dimension was skipped."""

    name: str
    score: Optional[float] = None
    threshold: float = 0.0
    critique: str = ""
    source: str = "rule"  # rule | llm | state

    @field_validator("score")
    @classmethod
    def _clamp(cls, v):
        # PRD 6.2: clamp out-of-range scores to [0, 10].
        if v is None:
            return v
        return max(0.0, min(10.0, v))

    @property
    def passed(self) -> Optional[bool]:
        if self.score is None:
            return None
        return self.score >= self.threshold


class EvalResult(BaseModel):
    """Aggregated evaluation result for a run (PRD 5.3.2)."""

    run_id: str
    task_id: str
    overall_score: float
    passed: bool
    dimension_scores: list[DimensionScore] = Field(default_factory=list)
    rule_results: list[dict] = Field(default_factory=list)
    state_results: list[dict] = Field(default_factory=list)
    critique: str = ""
    actionable_feedback: str = ""
    flags: dict = Field(default_factory=dict)  # e.g. llm_eval_failed, suspicious_score
    evaluated_at: Optional[datetime] = None
