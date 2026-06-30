"""AIP 核心数据模型（本体化）."""

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
    """证据引用 - 对齐 aip:Evidence."""

    type: str
    source: str  # Dataset / Knowledge IRI 或 legacy id
    detail: str = ""
    period: str | None = None
    metric_id: str | None = None  # aip:Metric/xxx
    iri: str | None = None

    def to_jsonld(self) -> dict[str, Any]:
        return {
            "@type": "aip:Evidence",
            "@id": self.iri or f"data:aip/evidence/{uuid4().hex[:12]}",
            "evidenceType": self.type,
            "source": self.source,
            "metric": self.metric_id,
            "timePeriod": self.period,
            "derivation": self.detail,
        }


class QueryResult(BaseModel):
    sql: str
    columns: list[str]
    rows: list[dict[str, Any]]
    dataset_id: str
    row_count: int
    dataset_iri: str | None = None
    metric_iri: str | None = None
    result_iri: str | None = None

    def to_jsonld(self) -> dict[str, Any]:
        return {
            "@context": "https://bank.example.com/ontology/aip/context.jsonld",
            "@type": "aip:QueryResult",
            "@id": self.result_iri or f"data:aip/query-result/{uuid4().hex[:12]}",
            "dataset": self.dataset_iri or self.dataset_id,
            "rowCount": self.row_count,
            "aip:sql": self.sql,
        }


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
    iri: str | None = None
    metric_iri: str | None = None

    def to_jsonld(self) -> dict[str, Any]:
        return {
            "@context": "https://bank.example.com/ontology/aip/context.jsonld",
            "@type": "aip:Conclusion",
            "@id": self.iri or f"data:aip/conclusion/{uuid4().hex[:12]}",
            "text": self.text,
            "confidenceLevel": f"aip:Confidence/{self.confidence.value}",
            "supportedBy": [e.to_jsonld() for e in self.evidence],
            "limitations": self.limitations,
            "metric": self.metric_iri,
        }


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
