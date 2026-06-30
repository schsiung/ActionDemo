"""本体论核心模型 - 与 JSON-LD / aip_core.yaml 对齐."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


class OntologyRef(BaseModel):
    """本体 IRI 引用."""

    iri: str
    label: str | None = None
    type: str | None = None  # CURIE 类名，如 aip:Metric

    @classmethod
    def metric(cls, metric_id: str, label: str = "") -> OntologyRef:
        return cls(iri=f"aip:Metric/{metric_id}", label=label, type="aip:Metric")

    @classmethod
    def customer(cls, customer_id: str, label: str = "") -> OntologyRef:
        return cls(iri=f"data:aip/customer/{customer_id}", label=label, type="aip:Customer")


class MetricIndividual(BaseModel):
    """T-Box 指标个体."""

    iri: str
    label: str
    formula: str
    unit: str = ""
    time_window: str = ""
    derived_from: list[str] = Field(default_factory=list)
    related_to: list[str] = Field(default_factory=list)


class Axiom(BaseModel):
    """公理 / 业务规则."""

    id: str
    label: str
    type: str  # restriction | threshold | alert
    condition: dict[str, Any] = Field(default_factory=dict)
    consequence: dict[str, Any] = Field(default_factory=dict)
    # alert/threshold 扩展字段
    expression: str | None = None
    metric: str | None = None
    property: str | None = None
    threshold: float | None = None
    level: str | None = None
    action: str | None = None

    model_config = {"extra": "allow"}


class DatasetBinding(BaseModel):
    """V-Box 数据集映射."""

    iri: str
    label: str
    table: str
    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)


class EvidenceIndividual(BaseModel):
    """A-Box 证据个体（JSON-LD 对齐）."""

    iri: str
    type: str = "aip:Evidence"
    evidence_type: str  # query | metric_def | knowledge | chart
    source: str  # Dataset or Document IRI
    metric: str | None = None
    time_period: str | None = None
    derivation: str = ""

    def to_jsonld(self) -> dict[str, Any]:
        return {
            "@type": self.type,
            "@id": self.iri,
            "aip:evidenceType": self.evidence_type,
            "aip:source": self.source,
            "aip:metric": self.metric,
            "aip:timePeriod": self.time_period,
            "aip:derivation": self.derivation,
        }


class ConclusionIndividual(BaseModel):
    """A-Box 结论个体."""

    iri: str
    type: str = "aip:Conclusion"
    text: str
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    supported_by: list[EvidenceIndividual] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)

    def to_jsonld(self) -> dict[str, Any]:
        return {
            "@context": "https://bank.example.com/ontology/aip/context.jsonld",
            "@type": self.type,
            "@id": self.iri,
            "aip:text": self.text,
            "aip:confidenceLevel": f"aip:Confidence/{self.confidence.value}",
            "aip:supportedBy": [e.to_jsonld() for e in self.supported_by],
            "aip:limitations": self.limitations,
        }


class OntologyCore(BaseModel):
    """aip_core.yaml 顶层结构."""

    id: str
    version: str
    namespace: str
    data_namespace: str
    metrics: list[MetricIndividual] = Field(default_factory=list)
    axioms: list[Axiom] = Field(default_factory=list)
    dataset_bindings: list[DatasetBinding] = Field(default_factory=list)
