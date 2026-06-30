"""AIP 核心数据模型."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class ChartType(str, Enum):
    LINE = "line"
    BAR = "bar"
    RANK = "rank"
    FUNNEL = "funnel"
    HEATMAP = "heatmap"


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class EvidenceRef(BaseModel):
    type: str
    source: str
    detail: str = ""
    period: str | None = None
    metric_id: str | None = None


class QueryResult(BaseModel):
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    dataset_id: str
    row_count: int


class ChartSpec(BaseModel):
    chart_type: ChartType
    title: str
    x_field: str | None = None
    y_field: str | None = None
    data: list[dict[str, Any]]


class Conclusion(BaseModel):
    text: str
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    evidence: list[EvidenceRef] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


class TraceStep(BaseModel):
    step_id: str = Field(default_factory=lambda: str(uuid4())[:8])
    agent: str
    action: str
    input_summary: str = ""
    output_summary: str = ""
    timestamp: datetime = Field(default_factory=datetime.now)


class AnalysisTrace(BaseModel):
    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    steps: list[TraceStep] = Field(default_factory=list)

    def add(self, agent: str, action: str, input_summary: str = "", output_summary: str = "") -> None:
        self.steps.append(
            TraceStep(
                agent=agent,
                action=action,
                input_summary=input_summary,
                output_summary=output_summary,
            )
        )
