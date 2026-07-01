"""DeepResearchAgent - 基于本体 TaskGraph 的分析任务规划与综合洞察."""

from __future__ import annotations

from typing import Any

from aip.agents.query_agent import QueryAgent
from aip.analytics.attribution import AttributionEngine
from aip.analytics.compare import CompareEngine
from aip.data_prep.dataset_registry import DatasetRegistry
from aip.models import AnalysisTrace, Conclusion, ConfidenceLevel, EvidenceRef
from aip.ontology.factory import DEFAULT_DATASET_IRI, get_ontology_registry, get_shacl_validator, get_task_graph_registry
from aip.ontology.task_graph import TaskGraph, TaskGraphExecutor, TaskGraphRegistry
from aip.semantic.model import SemanticModel


class DeepResearchAgent:
    """将业务问题拆解为本体化 TaskGraph 子任务并逐步执行."""

    def __init__(
        self,
        registry: DatasetRegistry,
        semantic_model: SemanticModel,
        table_name: str,
        ontology_registry=None,
        task_graph_registry: TaskGraphRegistry | None = None,
        dataset_iri: str | None = None,
    ):
        self.registry = registry
        self.semantic = semantic_model
        self.table_name = table_name
        self.ontology_registry = ontology_registry or get_ontology_registry()
        self.task_graph_registry = task_graph_registry or get_task_graph_registry()
        self.dataset_iri = dataset_iri or semantic_model.dataset_iri or DEFAULT_DATASET_IRI
        self.query_agent = QueryAgent(
            registry,
            semantic_model,
            table_name,
            ontology_registry=self.ontology_registry,
            dataset_iri=self.dataset_iri,
            shacl_validator=get_shacl_validator(),
        )
        self.attribution = AttributionEngine(registry, table_name)
        self.compare = CompareEngine(registry, table_name)
        self.trace = AnalysisTrace()
        self._executor = TaskGraphExecutor(
            registry,
            table_name,
            self.dataset_iri,
            semantic_model.dataset_id or table_name,
        )
        for action, handler in self._executor.default_handlers().items():
            self._executor.register_handler(action, handler)

    def plan(self, question: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """分析任务规划 - 实例化本体化 TaskGraph."""
        ctx = context or {}
        workflow_id = ctx.get("workflow_id") or self.task_graph_registry.resolve_for_question(question)
        graph = self.task_graph_registry.instantiate(
            workflow_id,
            question=question,
            dataset_iri=ctx.get("dataset_iri", self.dataset_iri),
        )
        self.trace.add(
            "DeepResearchAgent",
            "plan",
            input_summary=question,
            output_summary=f"{workflow_id}, {len(graph.nodes)} nodes",
        )
        return {
            "question": question,
            "workflow_id": workflow_id,
            "tasks": [n.model_dump() for n in graph.nodes],
            "task_graph": graph.to_jsonld(),
            "execution_order": [n.id for n in graph.topological_order()],
        }

    def execute(self, question: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """规划并执行 TaskGraph，返回兼容旧版与 JSON-LD 的结果."""
        plan_result = self.plan(question, context)
        graph = self.task_graph_registry.instantiate(
            plan_result["workflow_id"],
            question=question,
            dataset_iri=(context or {}).get("dataset_iri", self.dataset_iri),
        )
        executed = self._executor.execute(graph)
        outputs = self._build_outputs(executed, plan_result)
        self.trace.add(
            "DeepResearchAgent",
            "execute",
            input_summary=question,
            output_summary=f"{len(outputs.get('insights', []))} insights",
        )
        return outputs

    def attribute(self, metric_field: str = "risk_score", dimension_field: str = "industry") -> dict[str, Any]:
        result = self.attribution.dimension_attribution(metric_field, dimension_field)
        self.trace.add("DeepResearchAgent", "attribution", output_summary=metric_field)
        return result

    def _build_outputs(self, graph: TaskGraph, plan_result: dict[str, Any]) -> dict[str, Any]:
        """将 TaskGraph 节点产出映射为演示/报告兼容结构."""
        node_outputs = {n.id: (n.output or {}) for n in graph.nodes}

        summary = node_outputs.get("T1", {}).get("data", {})
        risk_signals = node_outputs.get("T2", {}).get("data", node_outputs.get("T2", {}).get("alerts", []))

        comparison: dict[str, Any] = {}
        for out in node_outputs.values():
            if out.get("rows") or out.get("@type") == "aip:ComparisonResult":
                comparison = out
                break

        synth_node = next(
            (n for n in reversed(graph.topological_order()) if n.action in ("synthesize", "path_recommendation")),
            None,
        )
        insights: list[str] = []
        conclusion_data: dict[str, Any] = {}
        if synth_node and synth_node.output:
            insights = synth_node.output.get("insights", [])
            conclusion_data = synth_node.output.get("conclusion", {})
            if not insights and synth_node.output.get("text"):
                insights = [synth_node.output["text"]]

        if not insights:
            insights = self._fallback_insights(summary, risk_signals, comparison)

        if not conclusion_data:
            conclusion_data = Conclusion(
                text="；".join(insights) + ("。" if insights else ""),
                confidence=ConfidenceLevel.HIGH if len(insights) >= 2 else ConfidenceLevel.MEDIUM,
                evidence=[
                    EvidenceRef(
                        type="task_graph",
                        source=self.dataset_iri,
                        detail=f"workflow={plan_result['workflow_id']}",
                        iri=graph.graph_iri,
                    )
                ],
                limitations=["基于 TaskGraph 结构化分析"],
                iri=f"data:aip/conclusion/{graph.id}",
            ).model_dump()

        task_results = {
            n.id: {
                "status": n.status.value,
                "action": n.action,
                "ontology_class": n.ontology_class,
                "output_type": n.output_type,
                "output_iri": n.output_iri,
                "governed_by": n.governed_by,
                "error": n.error,
            }
            for n in graph.nodes
        }

        return {
            "question": plan_result["question"],
            "workflow_id": plan_result["workflow_id"],
            "summary": summary,
            "risk_signals": risk_signals,
            "comparison": comparison,
            "insights": insights,
            "conclusion": conclusion_data,
            "plan": plan_result,
            "task_graph": plan_result["task_graph"],
            "task_results": task_results,
            "trace_id": self.trace.trace_id,
        }

    @staticmethod
    def _fallback_insights(
        summary: dict[str, Any],
        risk_signals: list[Any],
        comparison: dict[str, Any],
    ) -> list[str]:
        insights: list[str] = []
        if summary:
            insights.append(
                f"共 {summary.get('customer_count', 0)} 户客户，"
                f"平均风险分 {summary.get('avg_risk', 0):.1f}"
            )
        if risk_signals:
            insights.append(f"识别 {len(risk_signals)} 户高风险客户需重点关注")
        rows = comparison.get("rows", [])
        if rows:
            top = rows[0]
            region_name = top.get("dimension", top.get("region", "未知区域"))
            insights.append(
                f"{region_name} 授信余额最高，达 {top.get('total_value', 0):,.0f} 万元"
            )
        return insights
