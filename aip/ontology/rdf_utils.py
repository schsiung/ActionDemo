"""RDF 图构建与 SHACL 报告解析工具."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, SH, XSD

AIP_NS = "https://bank.example.com/ontology/aip#"
DATA_NS = "https://bank.example.com/data/aip/"
AIP = Namespace(AIP_NS)
DATA = Namespace(DATA_NS)


def load_graph(path: str | None = None, content: str | None = None, fmt: str = "turtle") -> Graph:
    g = Graph()
    g.bind("aip", AIP)
    g.bind("sh", SH)
    g.bind("rdfs", RDFS)
    if path:
        g.parse(path, format=fmt)
    elif content:
        g.parse(data=content, format=fmt)
    return g


def _as_uri(value: str, default_prefix: str = DATA_NS) -> URIRef:
    if value.startswith("http"):
        return URIRef(value)
    if value.startswith("aip:"):
        return URIRef(AIP_NS + value.split(":", 1)[1])
    if value.startswith("data:"):
        return URIRef(default_prefix + value.split(":", 1)[1])
    return URIRef(default_prefix + value.lstrip("/"))


def conclusion_to_graph(conclusion: dict[str, Any] | Any) -> Graph:
    """将结论模型手工序列化为 RDF 图（避免 JSON-LD 远程 context 拉取）."""
    g = Graph()
    g.bind("aip", AIP)

    if hasattr(conclusion, "model_dump"):
        data = conclusion.model_dump()
        evidence_items = conclusion.evidence
        text = conclusion.text
        cid = conclusion.iri or f"data:aip/conclusion/{uuid4().hex[:12]}"
    else:
        data = conclusion
        text = data.get("text", "")
        cid = data.get("iri") or data.get("@id") or f"data:aip/conclusion/{uuid4().hex[:12]}"
        evidence_items = data.get("evidence", [])

    node = _as_uri(cid)
    g.add((node, RDF.type, AIP.Conclusion))
    g.add((node, AIP.text, Literal(text)))

    for ev in evidence_items:
        if hasattr(ev, "model_dump"):
            ev_data = ev.model_dump()
            eid = ev.iri or f"data:aip/evidence/{uuid4().hex[:12]}"
            ev_type = ev.type
            source = ev.source
            detail = ev.detail
            metric = ev.metric_id
        else:
            ev_data = ev
            eid = ev.get("iri") or ev.get("@id") or f"data:aip/evidence/{uuid4().hex[:12]}"
            ev_type = ev.get("type") or ev.get("evidenceType")
            source = ev.get("source")
            detail = ev.get("detail") or ev.get("derivation", "")
            metric = ev.get("metric_id") or ev.get("metric")

        ev_node = _as_uri(eid)
        g.add((ev_node, RDF.type, AIP.Evidence))
        if ev_type:
            g.add((ev_node, AIP.evidenceType, Literal(ev_type)))
        if source:
            g.add((ev_node, AIP.source, _as_uri(source, AIP_NS)))
        if detail:
            g.add((ev_node, AIP.derivation, Literal(detail)))
        if metric:
            g.add((ev_node, AIP.metric, _as_uri(metric, AIP_NS)))
        g.add((node, AIP.supportedBy, ev_node))

    metric_iri = data.get("metric_iri") or data.get("metric")
    if metric_iri:
        g.add((node, AIP.metric, _as_uri(metric_iri, AIP_NS)))

    return g


def query_result_to_graph(result: dict[str, Any] | Any) -> Graph:
    g = Graph()
    g.bind("aip", AIP)

    if hasattr(result, "model_dump"):
        rid = result.result_iri or f"data:aip/query-result/{uuid4().hex[:12]}"
        dataset = result.dataset_iri or result.dataset_id
        row_count = result.row_count
    else:
        rid = result.get("result_iri") or result.get("@id") or "data:aip/query-result/test"
        dataset = result.get("dataset_iri") or result.get("dataset") or result.get("dataset_id")
        row_count = result.get("row_count", result.get("rowCount", 0))

    node = _as_uri(rid)
    g.add((node, RDF.type, AIP.QueryResult))
    if dataset:
        g.add((node, AIP.dataset, _as_uri(dataset, AIP_NS)))
    g.add((node, AIP.rowCount, Literal(int(row_count), datatype=XSD.integer)))
    return g


def customer_to_graph(customer: dict[str, Any], customer_iri: str | None = None) -> Graph:
    g = Graph()
    g.bind("aip", AIP)
    cid = customer_iri or f"data:aip/customer/{customer.get('customer_id', 'test')}"
    node = _as_uri(cid)
    g.add((node, RDF.type, AIP.Customer))
    if customer.get("customer_name"):
        g.add((node, RDFS.label, Literal(customer["customer_name"], lang="zh")))
    if customer.get("risk_score") is not None:
        g.add((node, AIP.riskScore, Literal(int(customer["risk_score"]), datatype=XSD.integer)))
    if customer.get("crr_level"):
        g.add((node, AIP.hasCRRLevel, URIRef(f"{AIP_NS}CRRLevel_{customer['crr_level']}")))
    return g


def merge_graphs(*graphs: Graph) -> Graph:
    merged = Graph()
    for graph in graphs:
        for triple in graph:
            merged.add(triple)
    return merged


def parse_shacl_report(report_graph: Graph) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    violations: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    for result in report_graph.subjects(predicate=SH.result):
        msg = report_graph.value(result, SH.resultMessage)
        severity = report_graph.value(result, SH.resultSeverity)
        source = report_graph.value(result, SH.sourceShape)
        focus = report_graph.value(result, SH.focusNode)
        entry = {
            "shape": _local_name(source),
            "message": str(msg) if msg else "",
            "focus": _local_name(focus),
            "severity": _local_name(severity) or "Violation",
        }
        sev = entry["severity"].lower()
        if sev in ("warning", "info"):
            warnings.append(entry)
        else:
            violations.append(entry)
    return violations, warnings


def _local_name(term: Any) -> str:
    if term is None:
        return ""
    s = str(term)
    if "#" in s:
        return s.split("#")[-1]
    if "/" in s:
        return s.rsplit("/", 1)[-1]
    return s
