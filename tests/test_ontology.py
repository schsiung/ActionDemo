"""本体论模块测试."""

from pathlib import Path

import pytest

from aip.ontology.registry import OntologyRegistry

ONTOLOGY_PATH = Path(__file__).parent.parent / "demo" / "data" / "ontology" / "aip_core.yaml"


@pytest.fixture
def registry():
    return OntologyRegistry(ONTOLOGY_PATH)


def test_load_ontology(registry):
    assert registry.version == "1.0.0"
    assert registry.get_metric("credit_balance") is not None


def test_explain_metric(registry):
    exp = registry.explain_metric("aip:Metric/credit_balance")
    assert exp["found"] is True
    assert "SUM" in exp["formula"]


def test_related_metrics(registry):
    related = registry.related_metrics("credit_balance")
    assert len(related) >= 1


def test_alert_axioms(registry):
    alerts = registry.get_alert_rules()
    assert len(alerts) >= 2


def test_semantic_ddl(registry):
    ddl = registry.semantic_ddl("aip:Dataset/customer_360")
    assert "customer_360" in ddl
    assert "credit_balance" in ddl
