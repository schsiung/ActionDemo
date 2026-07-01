"""基于 rdflib 的 OWL/Turtle 双向加载器."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from rdflib import Graph, Literal
from rdflib.namespace import OWL, RDF, RDFS

from aip.ontology.rdf_utils import AIP, AIP_NS, load_graph


class RdfOntologyLoader:
    """从 Turtle/OWL 提取指标、公理、数据集绑定，用于 TTL → YAML 同步."""

    def __init__(self, ttl_path: str | Path):
        self.ttl_path = Path(ttl_path)
        self.graph = load_graph(str(self.ttl_path))

    def extract_metrics(self) -> list[dict[str, Any]]:
        metrics: list[dict[str, Any]] = []
        for subj in self.graph.subjects(RDF.type, AIP.Metric):
            local = _metric_iri(subj)
            if not local:
                continue
            label = _literal(self.graph.value(subj, RDFS.label))
            formula = _literal(self.graph.value(subj, AIP.formula))
            unit = _literal(self.graph.value(subj, AIP.unit))
            time_window = _literal(self.graph.value(subj, AIP.timeWindow))
            related = [
                _metric_iri(o) for o in self.graph.objects(subj, AIP.relatedTo) if _metric_iri(o)
            ]
            metric: dict[str, Any] = {
                "iri": local,
                "label": label or local.split("/")[-1],
                "formula": formula or "",
            }
            if unit:
                metric["unit"] = unit
            if time_window:
                metric["time_window"] = time_window
            if related:
                metric["related_to"] = related
            metrics.append(metric)
        return metrics

    def extract_axioms(self) -> list[dict[str, Any]]:
        axioms: list[dict[str, Any]] = []
        for subj in self.graph.subjects(RDF.type, OWL.Class):
            local = str(subj).replace(AIP_NS, "")
            if not local.startswith("ax_"):
                continue
            label = _literal(self.graph.value(subj, RDFS.label))
            axiom_type = _literal(self.graph.value(subj, AIP.axiomType)) or "restriction"
            entry: dict[str, Any] = {"id": local, "label": label or local, "type": axiom_type}
            prop = self.graph.value(subj, AIP.onProperty)
            val = self.graph.value(subj, AIP.hasValue)
            if prop and val:
                entry["condition"] = {
                    "property": str(prop).replace(AIP_NS, ""),
                    "value": str(val).strip('"'),
                }
            metric = self.graph.value(subj, AIP.metric)
            if metric:
                entry["metric"] = _metric_iri(metric) or str(metric)
            expression = _literal(self.graph.value(subj, AIP.expression))
            if expression:
                entry["expression"] = expression
            level = _literal(self.graph.value(subj, AIP.alertLevel))
            if level:
                entry["level"] = level
            action = _literal(self.graph.value(subj, AIP.action))
            if action:
                entry["action"] = action
            axioms.append(entry)
        return axioms

    def extract_dataset_bindings(self) -> list[dict[str, Any]]:
        bindings: list[dict[str, Any]] = []
        for subj in self.graph.subjects(RDF.type, AIP.Dataset):
            local = str(subj).replace(AIP_NS, "")
            if not local.startswith("Dataset_"):
                continue
            iri = f"aip:{local.replace('Dataset_', 'Dataset/')}"
            label = _literal(self.graph.value(subj, RDFS.label))
            table = _literal(self.graph.value(subj, AIP.physicalTable))
            metrics = [
                m for m in (_metric_iri(o) for o in self.graph.objects(subj, AIP.hasMetric)) if m
            ]
            bindings.append({
                "iri": iri,
                "label": label or iri.split("/")[-1],
                "table": table or "",
                "metrics": metrics,
            })
        return bindings

    def summary(self) -> dict[str, int]:
        return {
            "metrics": len(self.extract_metrics()),
            "axioms": len(self.extract_axioms()),
            "dataset_bindings": len(self.extract_dataset_bindings()),
            "triples": len(self.graph),
        }


def _literal(term: Any) -> str | None:
    if term is None:
        return None
    if isinstance(term, Literal):
        return str(term)
    return str(term).strip('"')


def _metric_iri(term: Any) -> str | None:
    if term is None:
        return None
    s = str(term)
    if "Metric_" in s:
        name = s.split("Metric_")[-1]
        return f"aip:Metric/{name}"
    if "Metric/" in s:
        return s.replace(AIP_NS, "aip:")
    return None
