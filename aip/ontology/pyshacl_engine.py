"""pyshacl 生产级 SHACL 校验引擎."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pyshacl import validate as pyshacl_validate
from rdflib import Graph

from aip.ontology.rdf_utils import (
    conclusion_to_graph,
    customer_to_graph,
    load_graph,
    merge_graphs,
    parse_shacl_report,
    query_result_to_graph,
)


class PyShaclEngine:
    """使用 pyshacl + rdflib 对 JSON-LD/RDF 数据图执行 SHACL 校验."""

    def __init__(
        self,
        shapes_path: str | Path,
        ontology_path: str | Path | None = None,
        inference: str = "none",
    ):
        self.shapes_path = Path(shapes_path)
        self.ontology_path = Path(ontology_path) if ontology_path else None
        self.inference = inference
        self._shapes_graph: Graph | None = None
        self._ontology_graph: Graph | None = None

    @property
    def shapes_graph(self) -> Graph:
        if self._shapes_graph is None:
            self._shapes_graph = load_graph(str(self.shapes_path))
        return self._shapes_graph

    @property
    def ontology_graph(self) -> Graph | None:
        if self._ontology_graph is None and self.ontology_path and self.ontology_path.exists():
            self._ontology_graph = load_graph(str(self.ontology_path))
        return self._ontology_graph

    def list_shapes(self) -> list[dict[str, str]]:
        from rdflib.namespace import RDF, SH

        shapes = []
        for subj in self.shapes_graph.subjects(RDF.type, SH.NodeShape):
            shapes.append({
                "iri": str(subj),
                "local_name": str(subj).split("#")[-1],
            })
        return shapes

    def validate_graph(self, data_graph: Graph) -> dict[str, Any]:
        conforms, report_graph, report_text = pyshacl_validate(
            data_graph,
            shacl_graph=self.shapes_graph,
            ont_graph=self.ontology_graph,
            inference=self.inference,
            abort_on_first=False,
            allow_infos=True,
            allow_warnings=True,
            advanced=True,
        )
        violations, warnings = parse_shacl_report(report_graph)
        return {
            "passed": bool(conforms),
            "engine": "pyshacl",
            "violations": violations,
            "warnings": warnings,
            "report_text": report_text or "",
            "message": "SHACL 校验通过" if conforms else "；".join(v["message"] for v in violations[:3]),
        }

    def validate_conclusion(self, conclusion: Any) -> dict[str, Any]:
        return self.validate_graph(conclusion_to_graph(conclusion))

    def validate_query_result(self, result: Any) -> dict[str, Any]:
        return self.validate_graph(query_result_to_graph(result))

    def validate_customer(self, customer: dict[str, Any]) -> dict[str, Any]:
        return self.validate_graph(customer_to_graph(customer))

    def validate_bundle(
        self,
        conclusion: Any | None = None,
        query_result: Any | None = None,
        customer: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        graphs = []
        if conclusion:
            graphs.append(conclusion_to_graph(conclusion))
        if query_result:
            graphs.append(query_result_to_graph(query_result))
        if customer:
            graphs.append(customer_to_graph(customer))
        if not graphs:
            return {"passed": True, "engine": "pyshacl", "violations": [], "warnings": [], "message": "无数据"}
        return self.validate_graph(merge_graphs(*graphs))
