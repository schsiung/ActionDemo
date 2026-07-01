"""本体化改造集成测试."""

from pathlib import Path

import pytest

from aip.agents.query_agent import QueryAgent
from aip.alert.rules import AlertEngine
from aip.data_prep.dataset_registry import Dataset, DatasetRegistry
from aip.models import Conclusion, ConfidenceLevel, EvidenceRef
from aip.ontology.factory import ensure_ttl_export, get_ontology_registry, get_shacl_validator
from aip.ontology.owl import TurtleLoader, TurtleSerializer
from aip.ontology.prompt import SemanticDDLPromptBuilder
from aip.ontology.shacl_validator import ShaclValidator
from aip.semantic.model import SemanticModel, load_semantic_model
from aip.trust.layer import TrustLayer

DATA_DIR = Path(__file__).parent.parent / "demo" / "data"
ONTOLOGY_DIR = DATA_DIR / "ontology"


@pytest.fixture
def ontology():
    return get_ontology_registry()


@pytest.fixture
def registry():
    reg = DatasetRegistry()
    ds = Dataset(id="ds", name="test", source_type="file", table_name="customer_360")
    reg.register_csv(ds, DATA_DIR / "scenarios" / "customer_360.csv")
    return reg


@pytest.fixture
def query_agent(registry, ontology):
    semantic = load_semantic_model(DATA_DIR / "scenarios" / "semantic_pre_loan.yaml")
    semantic.dataset_iri = "aip:Dataset/customer_360"
    return QueryAgent(
        registry, semantic, "customer_360",
        ontology_registry=ontology,
        dataset_iri="aip:Dataset/customer_360",
        shacl_validator=get_shacl_validator(),
    )


def test_owl_ttl_export(ontology):
    path = ensure_ttl_export()
    assert path.exists()
    loader = TurtleLoader(path)
    v = loader.validate_syntax()
    assert v["valid"] is True
    assert v["metric_count"] >= 5


def test_owl_roundtrip(ontology):
    ttl = TurtleSerializer(ontology).serialize()
    assert "aip:Metric_credit_balance" in ttl
    assert "owl:Class" in ttl


def test_semantic_ddl_prompt(ontology):
    builder = SemanticDDLPromptBuilder(ontology)
    ddl = builder.build_semantic_ddl("aip:Dataset/customer_360")
    assert "aip:Metric/credit_balance" in ddl

    prompt = builder.build_full_prompt("aip:Dataset/customer_360", "高风险客户")
    assert prompt["ontology_version"] == "1.0.0"
    assert len(prompt["semantic_ddl"]) > 50


def test_shacl_conclusion_valid(query_agent):
    result = query_agent.ask("各机构授信余额")
    assert result["shacl"]["passed"] is True
    assert result.get("conclusion_jsonld", {}).get("@type") == "aip:Conclusion"
    assert result.get("result_jsonld", {}).get("@type") == "aip:QueryResult"


def test_shacl_pre_loan_screening(query_agent):
    result = query_agent.ask("高风险客户筛查")
    assert result["type"] == "pre_loan_screening"
    assert result["metric_iri"] == "aip:Metric/risk_score"
    assert result["shacl"]["passed"] is True


def test_shacl_crr_violation():
    shacl = ShaclValidator(ONTOLOGY_DIR / "shapes" / "pre_loan_screening.yaml")
    conclusion = Conclusion(
        text="建议对该客户开展纯信用放贷",
        confidence=ConfidenceLevel.HIGH,
        evidence=[EvidenceRef(type="query", source="aip:Dataset/customer_360", detail="SELECT 1")],
    )
    result = shacl.validate_conclusion_text_axioms(conclusion.text, {"crr_level": "E"})
    assert result.passed is False
    assert any("CRR" in v["message"] for v in result.violations)


def test_alert_engine_from_ontology(ontology, registry):
    engine = AlertEngine(DATA_DIR / "scenarios" / "alert_rules.yaml", ontology)
    rows = registry.execute_sql("SELECT * FROM customer_360").to_dict(orient="records")
    result = engine.evaluate_dataset(rows)
    assert result["total"] >= 0
    ontology_rules = [r for r in engine.rules if "AlertRule" in r.get("iri", "")]
    assert len(ontology_rules) >= 1


def test_semantic_model_from_ontology(ontology):
    model = SemanticModel.from_ontology(ontology, "aip:Dataset/customer_360", "test", "测试")
    assert len(model.metrics) >= 3
    assert model.metrics[0].iri.startswith("aip:Metric/")


def test_trust_layer_shacl():
    trust = TrustLayer(get_shacl_validator())
    c = Conclusion(text="测试", confidence=ConfidenceLevel.HIGH, evidence=[])
    validated = trust.validate_conclusion(c)
    assert validated.confidence == ConfidenceLevel.LOW
