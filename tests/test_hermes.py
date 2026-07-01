"""Hermes 智能对话测试."""

import pytest
from fastapi.testclient import TestClient

from demo.api import app
from demo.hermes.router import HermesRouter
from demo.hermes.service import HermesService


@pytest.fixture
def hermes():
    return HermesService()


@pytest.fixture
def router():
    return HermesRouter()


@pytest.fixture
def client():
    return TestClient(app)


def test_router_list_intent(router):
    r = router.route("有哪些场景")
    assert r.intent == "list_scenarios"


def test_router_scenario_id(router):
    r = router.route("运行场景 5.1")
    assert r.intent == "run_scenario"
    assert r.scenario_id == "5.1"


def test_router_run_all(router):
    r = router.route("演示全部34个场景")
    assert r.intent == "run_all"


def test_router_group(router):
    r = router.route("运行问数类场景")
    assert r.intent == "run_group"
    assert r.group == "问数类"


def test_router_keyword_match(router):
    r = router.route("帮我生成贷后巡检看板")
    assert r.intent == "run_scenario"
    assert r.scenario_id in ("2.1", "2.2")


def test_router_query_fallback(router):
    r = router.route("查询各机构授信余额排名")
    assert r.intent == "query"


def test_service_list_scenarios(hermes):
    scenarios = hermes.list_scenarios()
    assert len(scenarios) == 34


def test_service_run_scenario(hermes):
    record = hermes.run_scenario("1.1")
    assert record["status"] == "ok"
    assert record["id"] == "1.1"


def test_service_chat_list(hermes):
    resp = hermes.chat("帮助")
    assert resp["intent"] == "list_scenarios"
    assert "34" in resp["reply"] or "场景" in resp["reply"]
    assert resp["session_id"]


def test_service_chat_run_scenario(hermes):
    resp = hermes.chat("运行场景 1.3")
    assert resp["intent"] == "run_scenario"
    assert "1.3" in resp["reply"]


def test_service_tour(hermes):
    start = hermes.chat("开始导览")
    assert start["intent"] == "start_tour"
    assert "导览" in start["reply"]
    nxt = hermes.chat("下一个场景", start["session_id"])
    assert "导览" in nxt["reply"]


def test_api_hermes_scenarios(client):
    r = client.get("/api/hermes/scenarios")
    assert r.status_code == 200
    assert r.json()["total"] == 34


def test_api_hermes_chat(client):
    r = client.post("/api/hermes/chat", json={"message": "运行场景 0.1"})
    assert r.status_code == 200
    data = r.json()
    assert data["intent"] == "run_scenario"
    assert "0.1" in data["reply"]


def test_api_hermes_ui(client):
    r = client.get("/hermes")
    assert r.status_code == 200
    assert "Hermes" in r.text


def test_api_run_scenario_endpoint(client):
    r = client.post("/api/hermes/scenarios/7.4/run")
    assert r.status_code == 200
    assert r.json()["record"]["status"] == "ok"
