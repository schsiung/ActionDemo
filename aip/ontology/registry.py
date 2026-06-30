"""本体注册中心 - 加载 T-Box、提供指标/公理查询."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from aip.ontology.schema import Axiom, DatasetBinding, MetricIndividual, OntologyCore, OntologyRef


class OntologyRegistry:
    """M1 基于 YAML；M2 扩展 OWL/Turtle 加载。"""

    def __init__(self, ontology_path: str | Path | None = None):
        self._core: OntologyCore | None = None
        self._metrics: dict[str, MetricIndividual] = {}
        self._axioms: dict[str, Axiom] = {}
        self._bindings: dict[str, DatasetBinding] = {}
        if ontology_path:
            self.load(ontology_path)

    def load(self, path: str | Path) -> None:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        onto = data.get("ontology", {})
        self._core = OntologyCore(
            id=onto.get("id", "aip-core"),
            version=onto.get("version", "1.0.0"),
            namespace=onto.get("namespace", ""),
            data_namespace=onto.get("data_namespace", ""),
        )
        for m in data.get("metrics", []):
            metric = MetricIndividual(**m)
            self._metrics[metric.iri] = metric
            short_id = metric.iri.split("/")[-1]
            self._metrics[short_id] = metric
        for a in data.get("axioms", []):
            raw = dict(a)
            if isinstance(raw.get("condition"), str):
                raw["expression"] = raw.pop("condition")
            axiom = Axiom(**raw)
            self._axioms[axiom.id] = axiom
        for b in data.get("dataset_bindings", []):
            binding = DatasetBinding(**b)
            self._bindings[binding.iri] = binding

    def get_metric(self, iri_or_id: str) -> MetricIndividual | None:
        return self._metrics.get(iri_or_id)

    def explain_metric(self, iri_or_id: str) -> dict[str, Any]:
        metric = self.get_metric(iri_or_id)
        if not metric:
            return {"found": False, "iri": iri_or_id}
        return {
            "found": True,
            "iri": metric.iri,
            "label": metric.label,
            "formula": metric.formula,
            "unit": metric.unit,
            "time_window": metric.time_window,
            "derived_from": metric.derived_from,
            "related_to": metric.related_to,
        }

    def related_metrics(self, iri_or_id: str) -> list[OntologyRef]:
        metric = self.get_metric(iri_or_id)
        if not metric:
            return []
        return [OntologyRef(iri=r, type="aip:Metric") for r in metric.related_to]

    def get_axioms(self, axiom_type: str | None = None) -> list[Axiom]:
        axioms = list(self._axioms.values())
        if axiom_type:
            axioms = [a for a in axioms if a.type == axiom_type]
        return axioms

    def get_alert_rules(self) -> list[Axiom]:
        return self.get_axioms("alert")

    def get_dataset_binding(self, iri: str) -> DatasetBinding | None:
        return self._bindings.get(iri)

    def semantic_ddl(self, dataset_iri: str) -> str:
        """生成注入 LLM 的语义 DDL 摘要."""
        binding = self.get_dataset_binding(dataset_iri)
        if not binding:
            return ""
        lines = [f"Dataset: {binding.iri} ({binding.label})", f"Table: {binding.table}", "Metrics:"]
        for miri in binding.metrics:
            m = self.get_metric(miri)
            if m:
                lines.append(f"  - {m.iri}: {m.label} = {m.formula} ({m.unit})")
        lines.append("Related metrics:")
        for miri in binding.metrics:
            m = self.get_metric(miri)
            if m and m.related_to:
                lines.append(f"  - {m.label} → {', '.join(m.related_to)}")
        return "\n".join(lines)

    @property
    def version(self) -> str:
        return self._core.version if self._core else "0.0.0"
