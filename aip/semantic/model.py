"""语义模型中心 - 与本体 T-Box 对齐."""

from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING

import yaml
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from aip.ontology.registry import OntologyRegistry


class DimensionDef(BaseModel):
    id: str
    name: str
    field: str
    description: str = ""
    iri: str | None = None


class MetricDef(BaseModel):
    id: str
    name: str
    formula: str
    description: str = ""
    unit: str = ""
    time_window: str = ""
    update_frequency: str = ""
    related_metrics: list[str] = Field(default_factory=list)
    iri: str | None = None
    derived_from: list[str] = Field(default_factory=list)


class SemanticModel(BaseModel):
    id: str
    name: str
    dataset_id: str
    dataset_iri: str | None = None
    dimensions: list[DimensionDef] = Field(default_factory=list)
    metrics: list[MetricDef] = Field(default_factory=list)

    def get_metric(self, metric_id: str) -> MetricDef | None:
        for m in self.metrics:
            if m.id == metric_id or m.iri == metric_id or (m.iri and metric_id in m.iri):
                return m
        return None

    def explain_metric(self, metric_id: str) -> dict[str, Any]:
        metric = self.get_metric(metric_id)
        if not metric:
            return {"found": False, "metric_id": metric_id}
        return {
            "found": True,
            "id": metric.id,
            "iri": metric.iri or f"aip:Metric/{metric.id}",
            "name": metric.name,
            "formula": metric.formula,
            "description": metric.description,
            "time_window": metric.time_window,
            "update_frequency": metric.update_frequency,
            "related_metrics": metric.related_metrics,
            "derived_from": metric.derived_from,
        }

    def recommend_related(self, metric_id: str) -> list[dict[str, str]]:
        metric = self.get_metric(metric_id)
        if not metric:
            return []
        results = []
        for rid in metric.related_metrics:
            related = self.get_metric(rid)
            if related:
                results.append({
                    "id": related.id,
                    "iri": related.iri or f"aip:Metric/{related.id}",
                    "name": related.name,
                    "reason": f"与 {metric.name} 关联",
                })
        return results

    @classmethod
    def from_ontology(cls, registry: OntologyRegistry, dataset_iri: str, model_id: str, model_name: str) -> SemanticModel:
        """从 OntologyRegistry 同步构建语义模型."""
        binding = registry.get_dataset_binding(dataset_iri)
        metrics = []
        if binding:
            for miri in binding.metrics:
                om = registry.get_metric(miri)
                if om:
                    short_id = om.iri.split("/")[-1]
                    metrics.append(MetricDef(
                        id=short_id,
                        name=om.label,
                        formula=om.formula,
                        unit=om.unit,
                        time_window=om.time_window,
                        iri=om.iri,
                        related_metrics=[r.split("/")[-1] for r in om.related_to],
                        derived_from=[d.split("/")[-1] for d in om.derived_from],
                    ))
        return cls(
            id=model_id,
            name=model_name,
            dataset_id=binding.table if binding else model_id,
            dataset_iri=dataset_iri,
            metrics=metrics,
        )


def load_semantic_model(path: str | Path) -> SemanticModel:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return SemanticModel(**data)
