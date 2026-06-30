"""JSON-LD 上下文与序列化辅助."""

from __future__ import annotations

from typing import Any

AIP_CONTEXT = {
    "@vocab": "https://bank.example.com/ontology/aip#",
    "aip": "https://bank.example.com/ontology/aip#",
    "data": "https://bank.example.com/data/aip/",
    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "text": "aip:text",
    "confidenceLevel": "aip:confidenceLevel",
    "supportedBy": {"@id": "aip:supportedBy", "@type": "@id"},
    "metric": {"@id": "aip:metric", "@type": "@id"},
    "source": {"@id": "aip:source", "@type": "@id"},
    "evidenceType": "aip:evidenceType",
    "derivation": "aip:derivation",
    "timePeriod": "aip:timePeriod",
    "limitations": {"@id": "aip:limitations", "@container": "@list"},
}


def wrap_jsonld(obj_type: str, obj_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    """包装为 JSON-LD 响应."""
    return {
        "@context": AIP_CONTEXT,
        "@type": obj_type,
        "@id": obj_id,
        **payload,
    }


def evidence_jsonld(
    iri: str,
    evidence_type: str,
    source: str,
    metric_iri: str | None = None,
    period: str | None = None,
    derivation: str = "",
) -> dict[str, Any]:
    return {
        "@type": "aip:Evidence",
        "@id": iri,
        "evidenceType": evidence_type,
        "source": source,
        "metric": metric_iri,
        "timePeriod": period,
        "derivation": derivation,
    }


def conclusion_jsonld(
    iri: str,
    text: str,
    confidence: str,
    evidence: list[dict[str, Any]],
    limitations: list[str] | None = None,
) -> dict[str, Any]:
    return wrap_jsonld("aip:Conclusion", iri, {
        "text": text,
        "confidenceLevel": f"aip:Confidence/{confidence}",
        "supportedBy": evidence,
        "limitations": limitations or [],
    })
