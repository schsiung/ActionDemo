"""TaskGraph 本体化节点测试."""

from pathlib import Path

import pytest

from aip.agents.deep_research_agent import DeepResearchAgent
from aip.data_prep.dataset_registry import Dataset, DatasetRegistry
from aip.ontology.factory import get_task_graph_registry
from aip.ontology.task_graph import TaskGraphExecutor, TaskGraphRegistry, TaskStatus
from aip.semantic.model import load_semantic_model

DATA_DIR = Path(__file__).parent.parent / "demo" / "data"
ONTOLOGY_DIR = DATA_DIR / "ontology"


@pytest.fixture
def registry():
    reg = DatasetRegistry()
    ds = Dataset(id="test_ds", name="测试", source_type="file", table_name="test_table")
    reg.register_csv(ds, DATA_DIR / "scenarios" / "customer_360.csv")
    return reg


@pytest.fixture
def semantic():
    return load_semantic_model(DATA_DIR / "scenarios" / "semantic_pre_loan.yaml")


@pytest.fixture
def task_graph_registry():
    return TaskGraphRegistry(ONTOLOGY_DIR / "task_graphs.yaml")


@pytest.fixture
def deep_agent(registry, semantic, task_graph_registry):
    return DeepResearchAgent(
        registry,
        semantic,
        "test_table",
        task_graph_registry=task_graph_registry,
        dataset_iri="aip:Dataset/customer_360",
    )


def test_task_graph_registry_load(task_graph_registry):
    graphs = task_graph_registry.list_graphs()
    assert len(graphs) == 2
    ids = {g["id"] for g in graphs}
    assert "general_risk_analysis" in ids
    assert "pre_loan_screening" in ids


def test_resolve_for_question(task_graph_registry):
    assert task_graph_registry.resolve_for_question("贷前风险筛查名单") == "pre_loan_screening"
    assert task_graph_registry.resolve_for_question("对公客户风险全景") == "general_risk_analysis"


def test_topological_order_general(task_graph_registry):
    graph = task_graph_registry.instantiate("general_risk_analysis", "风险分析")
    order = [n.id for n in graph.topological_order()]
    assert order == ["T1", "T2", "T3", "T4"]
    assert order.index("T1") < order.index("T2")
    assert order.index("T1") < order.index("T3")
    assert order.index("T4") > order.index("T2")
    assert order.index("T4") > order.index("T3")


def test_topological_order_pre_loan(task_graph_registry):
    graph = task_graph_registry.instantiate("pre_loan_screening", "贷前筛查")
    order = [n.id for n in graph.topological_order()]
    assert len(order) == 6
    assert order[-1] == "T6"
    assert order.index("T5") < order.index("T6")


def test_task_graph_jsonld(task_graph_registry):
    graph = task_graph_registry.instantiate("general_risk_analysis", "测试")
    doc = graph.to_jsonld()
    assert doc["@type"] == "aip:TaskGraph"
    assert doc["@id"].startswith("data:aip/task-graph/")
    assert len(doc["aip:hasTask"]) == 4
    first_task = doc["aip:hasTask"][0]
    assert first_task["aip:taskId"] == "T1"
    assert first_task["aip:metrics"]


def test_executor_general_workflow(registry, semantic, task_graph_registry):
    executor = TaskGraphExecutor(
        registry, "test_table", "aip:Dataset/customer_360", "test_ds"
    )
    for action, handler in executor.default_handlers().items():
        executor.register_handler(action, handler)

    graph = task_graph_registry.instantiate("general_risk_analysis", "风险分析")
    result = executor.execute(graph)
    completed = [n for n in result.nodes if n.status == TaskStatus.COMPLETED]
    assert len(completed) == 4
    synth = result.get_node("T4")
    assert synth and synth.output
    assert synth.output.get("text") or synth.output.get("insights")


def test_executor_pre_loan_path_recommendation(registry, semantic, task_graph_registry):
    executor = TaskGraphExecutor(
        registry, "test_table", "aip:Dataset/customer_360", "test_ds"
    )
    for action, handler in executor.default_handlers().items():
        executor.register_handler(action, handler)

    graph = task_graph_registry.instantiate("pre_loan_screening", "贷前筛查")
    result = executor.execute(graph)
    path_node = result.get_node("T6")
    assert path_node.status == TaskStatus.COMPLETED
    assert path_node.governed_by
    assert "ax_crr_e_no_pure_credit" in path_node.governed_by
    assert path_node.output.get("recommendations")


def test_deep_agent_plan_ontology(deep_agent):
    plan = deep_agent.plan("贷前风险筛查：名单导入→多源扫描")
    assert plan["workflow_id"] == "pre_loan_screening"
    assert len(plan["tasks"]) == 6
    assert plan["task_graph"]["@type"] == "aip:TaskGraph"
    assert plan["execution_order"][-1] == "T6"


def test_deep_agent_execute_backward_compat(deep_agent):
    result = deep_agent.execute("风险分析")
    assert "insights" in result
    assert len(result["insights"]) >= 2
    assert "conclusion" in result
    assert result["task_graph"]["@type"] == "aip:TaskGraph"
    assert result["workflow_id"] == "general_risk_analysis"
    assert "T4" in result["task_results"]


def test_factory_get_task_graph_registry():
    from aip.ontology.factory import get_task_graph_registry as factory_get

    reg = factory_get()
    assert len(reg.list_graphs()) >= 2
