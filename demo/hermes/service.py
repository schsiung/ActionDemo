"""Hermes 对话服务 - 编排场景执行与 Agent 问答."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from demo.hermes.formatter import (
    format_group_summary,
    format_query_result,
    format_research_result,
    format_run_all_summary,
    format_scenario_list,
    format_scenario_result,
)
from demo.hermes.router import HermesRouter, RouteResult
from demo.hermes.session import HermesSession, SessionStore
from demo.scenarios.executor import ScenarioExecutor


class HermesService:
    """Hermes 智能对话核心服务."""

    def __init__(self) -> None:
        self.router = HermesRouter()
        self.sessions = SessionStore()
        self._executor: ScenarioExecutor | None = None

    @property
    def executor(self) -> ScenarioExecutor:
        if self._executor is None:
            self._executor = ScenarioExecutor()
        return self._executor

    def list_scenarios(self, group: str | None = None) -> list[dict]:
        items = self.router.list_scenarios()
        if group:
            items = [s for s in items if s["group"] == group]
        return items

    def run_scenario(self, scenario_id: str) -> dict:
        record = self.executor.run_by_id(scenario_id)
        if not record:
            return {"status": "error", "error": f"场景不存在: {scenario_id}", "id": scenario_id}
        return record

    def run_group(self, group: str) -> list[dict]:
        self.executor.results.clear()
        return self.executor.run_by_group(group)

    def run_all(self) -> list[dict]:
        self.executor.results.clear()
        return self.executor.run_all()

    def chat(self, message: str, session_id: str | None = None) -> dict[str, Any]:
        session = self.sessions.get_or_create(session_id)
        session.add_user(message)

        if session.tour_active and message.strip() in ("下一个场景", "继续", "继续导览", "next"):
            route = RouteResult(intent="next_tour", reason="导览中前进")
        else:
            route = self.router.route(message)

        reply, artifacts, suggestions, meta = self._dispatch(route, session, message)
        msg = session.add_assistant(
            reply,
            intent=route.intent,
            scenario_id=meta.get("scenario_id"),
            artifacts=artifacts,
            suggestions=suggestions,
        )
        return {
            "session_id": session.session_id,
            "reply": reply,
            "intent": route.intent,
            "route_reason": route.reason,
            "message_id": len(session.messages),
            "artifacts": artifacts,
            "suggestions": suggestions,
            "metadata": meta,
            "history": session.history(10),
        }

    def _dispatch(
        self,
        route: RouteResult,
        session: HermesSession,
        message: str,
    ) -> tuple[str, list[dict], list[str], dict[str, Any]]:
        meta: dict[str, Any] = {"scenario_id": route.scenario_id}

        if route.intent == "list_scenarios":
            scenarios = self.list_scenarios(route.group)
            return format_scenario_list(scenarios, route.group), [], ["演示全部", "开始导览", "运行场景 1.1"], meta

        if route.intent == "run_scenario" and route.scenario_id:
            record = self.run_scenario(route.scenario_id)
            session.last_scenario_id = route.scenario_id
            reply, artifacts, suggestions = format_scenario_result(record)
            meta["scenario_result"] = {"status": record.get("status"), "id": route.scenario_id}
            return reply, artifacts, suggestions, meta

        if route.intent == "run_group" and route.group:
            results = self.run_group(route.group)
            session.last_group = route.group
            meta["group_results"] = len(results)
            return format_group_summary(results, route.group), [], ["演示全部", "帮助"], meta

        if route.intent == "run_all":
            results = self.run_all()
            meta["total"] = len(results)
            return format_run_all_summary(results), [], ["开始导览", "运行场景 0.1"], meta

        if route.intent == "start_tour":
            session.tour_active = True
            session.tour_index = 0
            return self._run_tour_step(session)

        if route.intent == "next_tour":
            if not session.tour_active:
                session.tour_active = True
                session.tour_index = 0
            else:
                session.tour_index += 1
            return self._run_tour_step(session)

        if route.intent == "stop_tour":
            session.tour_active = False
            return "已结束场景导览。可随时说「运行场景 X.X」或「演示全部」。", [], ["演示全部", "帮助"], meta

        if route.intent == "query":
            agent = self.executor.ctx.get_query_agent()
            result = agent.ask(route.question or message)
            return format_query_result(result), [], ["运行场景 1.2", "深度研究分析"], meta

        if route.intent == "knowledge":
            result = self.executor.ctx.knowledge.answer(route.question or message)
            return format_query_result(result), [], ["运行场景 1.1", "帮助"], meta

        if route.intent == "research":
            deep = self.executor.ctx.get_deep_agent()
            result = deep.execute(route.question or message)
            return format_research_result(result), [], ["运行场景 5.1", "运行场景 5.2"], meta

        # fallback
        agent = self.executor.ctx.get_query_agent()
        result = agent.ask(message)
        return format_query_result(result), [], ["帮助", "演示全部"], meta

    def _run_tour_step(self, session: HermesSession) -> tuple[str, list[dict], list[str], dict[str, Any]]:
        scenarios = self.router.scenarios
        if session.tour_index >= len(scenarios):
            session.tour_active = False
            return (
                f"🎉 场景导览已完成，共 **{len(scenarios)}** 个场景。可说「演示全部」查看汇总。",
                [],
                ["演示全部", "帮助"],
                {"tour_complete": True},
            )
        scenario = scenarios[session.tour_index]
        record = self.run_scenario(scenario["id"])
        session.last_scenario_id = scenario["id"]
        body, artifacts, _ = format_scenario_result(record)
        header = f"📍 **导览 {session.tour_index + 1}/{len(scenarios)}**\n\n"
        suggestions = ["下一个场景", "结束导览"] if session.tour_index < len(scenarios) - 1 else ["结束导览", "演示全部"]
        meta = {"scenario_id": scenario["id"], "tour_index": session.tour_index, "tour_total": len(scenarios)}
        return header + body, artifacts, suggestions, meta


@lru_cache(maxsize=1)
def get_hermes_service() -> HermesService:
    return HermesService()
