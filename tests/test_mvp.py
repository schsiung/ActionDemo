"""MVP 单元测试."""

from pathlib import Path

import pytest

from aip.agents.deep_research_agent import DeepResearchAgent
from aip.agents.query_agent import QueryAgent
from aip.data_prep.dataset_registry import Dataset, DatasetRegistry
from aip.data_prep.script_workbench import ScriptWorkbench
from aip.report.composer import ReportComposer
from aip.semantic.model import load_semantic_model
from aip.trust.layer import TrustLayer
from aip.visualization.chart import ChartPlanner, ChartRenderer
from aip.visualization.dashboard import DashboardGenerator

DATA_DIR = Path(__file__).parent.parent / "demo" / "data"


@pytest.fixture
def registry():
    reg = DatasetRegistry()
    ds = Dataset(id="test_ds", name="测试", source_type="file", table_name="test_table")
    reg.register_csv(ds, DATA_DIR / "sample_customers.csv")
    return reg


@pytest.fixture
def semantic():
    return load_semantic_model(DATA_DIR / "semantic_model.yaml")


@pytest.fixture
def query_agent(registry, semantic):
    return QueryAgent(registry, semantic, "test_table")


@pytest.fixture
def deep_agent(registry, semantic):
    return DeepResearchAgent(registry, semantic, "test_table")


def test_dataset_register(registry):
    datasets = registry.list_datasets()
    assert len(datasets) == 1
    assert datasets[0].metadata["row_count"] == 20


def test_semantic_model(semantic):
    explanation = semantic.explain_metric("credit_balance")
    assert explanation["found"] is True
    assert "SUM" in explanation["formula"]


def test_query_agent(query_agent):
    result = query_agent.ask("各机构授信余额排名")
    assert result["type"] == "query"
    assert result["result"]["row_count"] > 0


def test_metric_explain(query_agent):
    result = query_agent.ask("授信余额口径是什么")
    assert result["type"] == "metric_explain"
    assert result["explanation"]["found"] is True


def test_deep_research(deep_agent):
    result = deep_agent.execute("风险分析")
    assert "insights" in result
    assert len(result["insights"]) >= 2
    assert "conclusion" in result


def test_attribution(deep_agent):
    result = deep_agent.attribute()
    assert result["type"] == "attribution"
    assert len(result["top_factors"]) > 0


def test_script_workbench(registry):
    wb = ScriptWorkbench(registry)
    result = wb.execute_sql("SELECT COUNT(*) AS cnt FROM test_table")
    assert result["success"] is True
    assert result["rows"][0]["cnt"] == 20


def test_chart_render():
    data = [{"region": "华东", "total": 100}, {"region": "华南", "total": 80}]
    spec = ChartPlanner.from_query_result(data, "bar", "测试图表")
    html = ChartRenderer.render(spec)
    assert "plotly" in html.lower() or "bar" in html.lower()


def test_dashboard_generate(deep_agent, tmp_path):
    comparison = deep_agent.compare.by_dimension("region", "credit_balance")
    gen = DashboardGenerator(tmp_path)
    path = gen.generate({
        "title": "测试看板",
        "kpis": [{"label": "测试", "value": "100"}],
        "charts": [{"title": "对比", "type": "bar", "data": comparison["rows"]}],
        "filename": "test.html",
    })
    assert Path(path).exists()


def test_report_compose(deep_agent, tmp_path):
    data = deep_agent.execute("测试报告")
    composer = ReportComposer(tmp_path)
    result = composer.compose("weekly_review", data, {"report_period": "2025-01"})
    assert Path(result["output_path"]).exists()
    assert result["quality_check"]["passed"] or result["quality_check"]["issues"]


def test_trust_layer():
    from aip.models import Conclusion, EvidenceRef, ConfidenceLevel
    trust = TrustLayer()
    conclusion = Conclusion(text="测试结论", confidence=ConfidenceLevel.HIGH)
    validated = trust.validate_conclusion(conclusion)
    assert validated.confidence == ConfidenceLevel.LOW

    conclusion.evidence.append(EvidenceRef(type="query", source="test", detail="sql"))
    validated = trust.validate_conclusion(conclusion)
    assert validated.confidence == ConfidenceLevel.MEDIUM
