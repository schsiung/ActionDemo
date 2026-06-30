"""场景演示测试."""

import pytest

from demo.scenarios.context import ScenarioContext
from demo.scenarios.executor import ScenarioExecutor, ACTION_HANDLERS


@pytest.fixture
def executor():
    return ScenarioExecutor()


def test_registry_loads(executor):
    scenarios = executor.ctx.load_registry()
    assert len(scenarios) == 34


def test_all_handlers_registered(executor):
    scenarios = executor.ctx.load_registry()
    actions = {s["demo_action"] for s in scenarios}
    missing = actions - set(ACTION_HANDLERS.keys())
    assert not missing, f"缺少处理器: {missing}"


@pytest.mark.parametrize("scenario_id", [
    "0.1", "0.2", "0.3",
    "1.1", "1.2", "1.3", "1.4",
    "2.1", "2.2", "2.3",
    "3.1", "3.2", "3.3",
    "4.1", "4.2", "4.3", "4.4", "4.5", "4.6",
    "5.1", "5.2", "5.3", "5.4",
    "6.1", "6.2",
    "7.1", "7.2", "7.3", "7.4", "7.5",
    "8.1", "8.2", "8.3", "8.4",
])
def test_scenario_runs(executor, scenario_id):
    result = executor.run_by_id(scenario_id)
    assert result is not None
    assert result["status"] == "ok", f"{scenario_id} failed: {result.get('error')}"


def test_knowledge_engine():
    ctx = ScenarioContext()
    answer = ctx.knowledge.answer("科创e贷产品政策")
    assert answer["found"] is True


def test_alert_engine():
    ctx = ScenarioContext()
    rows = ctx.query_table("customer_360", "SELECT * FROM customer_360")
    result = ctx.alert_engine.evaluate_dataset(rows)
    assert result["total"] > 0
