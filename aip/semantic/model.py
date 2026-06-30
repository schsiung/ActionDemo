"""语义模型中心 - 字段业务名、指标公式、维度与口径."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class DimensionDef(BaseModel):
    id: str
    name: str
    field: str
    description: str = ""


class MetricDef(BaseModel):
    id: str
    name: str
    formula: str
    description: str = ""
    unit: str = ""
    time_window: str = ""
    update_frequency: str = ""
    related_metrics: list[str] = Field(default_factory=list)


class SemanticModel(BaseModel):
    id: str
    name: str
    dataset_id: str
    dimensions: list[DimensionDef] = Field(default_factory=list)
    metrics: list[MetricDef] = Field(default_factory=list)

    def get_metric(self, metric_id: str) -> MetricDef | None:
        return next((m for m in self.metrics if m.id == metric_id), None)

    def explain_metric(self, metric_id: str) -> dict[str, Any]:
        metric = self.get_metric(metric_id)
        if not metric:
            return {"found": False, "metric_id": metric_id}
        return {
            "found": True,
            "id": metric.id,
            "name": metric.name,
            "formula": metric.formula,
            "description": metric.description,
            "time_window": metric.time_window,
            "update_frequency": metric.update_frequency,
            "related_metrics": metric.related_metrics,
        }

    def recommend_related(self, metric_id: str) -> list[dict[str, str]]:
        metric = self.get_metric(metric_id)
        if not metric:
            return []
        results = []
        for rid in metric.related_metrics:
            related = self.get_metric(rid)
            if related:
                results.append({"id": related.id, "name": related.name, "reason": f"与 {metric.name} 关联"})
        return results


def load_semantic_model(path: str | Path) -> SemanticModel:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return SemanticModel(**data)
