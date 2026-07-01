"""OWL 双向同步与 pyshacl 集成测试."""

from pathlib import Path

import pytest
from rdflib import Graph

from aip.models import Conclusion, ConfidenceLevel, EvidenceRef
from aip.ontology.factory import (
    DEFAULT_SHACL_TTL,
    DEFAULT_TTL,
    DEFAULT_YAML,
    get_shacl_validator,
    get_sync_service,
)
from aip.ontology.pyshacl_engine import PyShaclEngine
from aip.ontology.rdf_loader import RdfOntologyLoader
from aip.ontology.rdf_utils import conclusion_to_graph, customer_to_graph, parse_shacl_report
from aip.ontology.sync import OntologySyncService

ONTOLOGY_DIR = Path(__file__).parent.parent / "demo" / "data" / "ontology"


def test_sync_service_status():
    sync = get_sync_service()
    status = sync.status()
    assert status["yaml_exists"] is True
    assert status["metric_count"] >= 5
    assert "preview_hash" in status


def test_sync_yaml_to_ttl_dry_run():
    sync = get_sync_service()
    result = sync.sync("yaml_to_ttl", dry_run=True)
    assert result["direction"] == "yaml_to_ttl"
    assert result["lines"] > 20
    assert "preview_hash" in result


def test_sync_diff():
    sync = get_sync_service()
    diff = sync.diff()
    assert "changes" in diff
    assert "only_in_ttl" in diff


def test_rdf_loader_extract_metrics():
    loader = RdfOntologyLoader(DEFAULT_TTL)
    metrics = loader.extract_metrics()
    assert len(metrics) >= 5
    assert any(m["iri"] == "aip:Metric/credit_balance" for m in metrics)


def test_pyshacl_engine_load_shapes():
    engine = PyShaclEngine(DEFAULT_SHACL_TTL, DEFAULT_TTL)
    shapes = engine.list_shapes()
    assert len(shapes) >= 4
    names = {s["local_name"] for s in shapes}
    assert "ConclusionShape" in names


def test_pyshacl_valid_conclusion():
    engine = PyShaclEngine(DEFAULT_SHACL_TTL, DEFAULT_TTL)
    conclusion = Conclusion(
        text="测试结论",
        confidence=ConfidenceLevel.HIGH,
        evidence=[
            EvidenceRef(
                type="query",
                source="aip:Dataset/customer_360",
                detail="SELECT COUNT(*) FROM customer_360",
                iri="data:aip/evidence/test1",
            )
        ],
        iri="data:aip/conclusion/test",
    )
    result = engine.validate_conclusion(conclusion)
    assert result["engine"] == "pyshacl"
    assert result["passed"] is True


def test_pyshacl_invalid_conclusion_no_evidence():
    engine = PyShaclEngine(DEFAULT_SHACL_TTL, DEFAULT_TTL)
    conclusion = Conclusion(text="无证据结论", confidence=ConfidenceLevel.HIGH, evidence=[])
    result = engine.validate_conclusion(conclusion)
    assert result["passed"] is False
    assert len(result["violations"]) >= 1


def test_pyshacl_customer_shape():
    engine = PyShaclEngine(DEFAULT_SHACL_TTL, DEFAULT_TTL)
    customer = {"customer_id": "C001", "risk_score": 85, "crr_level": "D"}
    result = engine.validate_customer(customer)
    assert result["engine"] == "pyshacl"
    assert "violations" in result or "warnings" in result


def test_shacl_validator_uses_pyshacl():
    validator = get_shacl_validator()
    assert validator.engine_name == "pyshacl"
    conclusion = Conclusion(
        text="测试",
        confidence=ConfidenceLevel.HIGH,
        evidence=[EvidenceRef(type="query", source="aip:Dataset/customer_360", detail="SELECT 1")],
    )
    result = validator.validate_conclusion(conclusion)
    assert result.engine == "pyshacl"
    assert result.passed is True


def test_shacl_validator_axiom_still_works():
    validator = get_shacl_validator()
    result = validator.validate_conclusion_text_axioms(
        "建议纯信用放贷",
        {"crr_level": "E"},
    )
    assert result.passed is False


def test_conclusion_to_graph():
    g = conclusion_to_graph({
        "text": "测试",
        "confidence": "high",
        "evidence": [{"type": "query", "source": "aip:Dataset/customer_360", "detail": "SELECT 1"}],
        "iri": "data:aip/conclusion/t1",
    })
    assert len(g) >= 3


def test_customer_to_graph():
    g = customer_to_graph({"customer_id": "X1", "risk_score": 80, "crr_level": "C"})
    assert len(g) >= 3


def test_sync_service_from_paths(tmp_path):
    yaml_copy = tmp_path / "test.yaml"
    yaml_copy.write_text(DEFAULT_YAML.read_text(encoding="utf-8"), encoding="utf-8")
    ttl_copy = tmp_path / "test.ttl"
    service = OntologySyncService(yaml_copy, ttl_copy)
    service.sync("yaml_to_ttl", dry_run=False)
    assert ttl_copy.exists()
    assert RdfOntologyLoader(ttl_copy).summary()["metrics"] >= 5
