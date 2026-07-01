"""TaskGraph 本体化任务图 - 节点、规划与执行."""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import yaml
from pydantic import BaseModel, Field

from aip.models import Conclusion, ConfidenceLevel, EvidenceRef


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskNode(BaseModel):
    """本体化分析任务节点 - 对齐 aip:AnalysisTask."""

    id: str
    name: str
    action: str
    ontology_class: str = "aip:AnalysisTask"
    output_type: str = "aip:QueryResult"
    iri: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    governed_by: list[str] = Field(default_factory=list)
    expected_output: str = ""
    status: TaskStatus = TaskStatus.PENDING
    output: dict[str, Any] | None = None
    output_iri: str | None = None
    error: str | None = None

    def model_post_init(self, __context: Any) -> None:
        if not self.iri:
            object.__setattr__(self, "iri", f"data:aip/task/{self.id}")

    def to_jsonld(self, graph_iri: str) -> dict[str, Any]:
        return {
            "@type": self.ontology_class,
            "@id": self.iri,
            "aip:taskId": self.id,
            "aip:name": self.name,
            "aip:action": self.action,
            "aip:outputType": self.output_type,
            "aip:dependsOn": [f"data:aip/task/{d}" for d in self.depends_on],
            "aip:metrics": self.metrics,
            "aip:dimensions": self.dimensions,
            "aip:status": self.status.value,
            "aip:partOf": graph_iri,
            "aip:expectedOutput": self.expected_output,
            "aip:governedBy": [f"aip:{g}" if not g.startswith("aip:") else g for g in self.governed_by],
        }


class TaskGraph(BaseModel):
    """任务图 - 对齐 aip:TaskGraph."""

    id: str
    iri: str
    label: str
    pattern: str = ""
    dataset_iri: str = "aip:Dataset/customer_360"
    question: str = ""
    graph_iri: str | None = None
    nodes: list[TaskNode] = Field(default_factory=list)

    def model_post_init(self, __context: Any) -> None:
        if not self.graph_iri:
            suffix = uuid4().hex[:8]
            object.__setattr__(self, "graph_iri", f"data:aip/task-graph/{self.id}/{suffix}")

    def to_jsonld(self) -> dict[str, Any]:
        return {
            "@context": "https://bank.example.com/ontology/aip/context.jsonld",
            "@type": "aip:TaskGraph",
            "@id": self.graph_iri,
            "aip:label": self.label,
            "aip:pattern": self.pattern,
            "aip:dataset": self.dataset_iri,
            "aip:question": self.question,
            "aip:hasTask": [n.to_jsonld(self.graph_iri) for n in self.nodes],
        }

    def get_node(self, node_id: str) -> TaskNode | None:
        return next((n for n in self.nodes if n.id == node_id), None)

    def topological_order(self) -> list[TaskNode]:
        """按依赖拓扑排序."""
        order: list[TaskNode] = []
        done: set[str] = set()
        while len(order) < len(self.nodes):
            progressed = False
            for node in self.nodes:
                if node.id in done:
                    continue
                if all(dep in done for dep in node.depends_on):
                    order.append(node)
                    done.add(node.id)
                    progressed = True
            if not progressed:
                raise ValueError(f"TaskGraph 存在循环依赖: {self.id}")
        return order


class TaskGraphRegistry:
    """加载本体化 TaskGraph 模板."""

    def __init__(self, path: str | Path | None = None):
        self._graphs: dict[str, dict] = {}
        self._action_types: dict[str, dict] = {}
        if path:
            self.load(path)

    def load(self, path: str | Path) -> None:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        for g in data.get("task_graphs", []):
            self._graphs[g["id"]] = g
        self._action_types = data.get("action_types", {})

    def list_graphs(self) -> list[dict[str, str]]:
        return [{"id": g["id"], "iri": g["iri"], "label": g["label"]} for g in self._graphs.values()]

    def get_action_type(self, action: str) -> dict[str, str]:
        return self._action_types.get(action, {"ontology_class": "aip:AnalysisTask", "output_class": "aip:QueryResult"})

    def instantiate(self, graph_id: str, question: str, dataset_iri: str | None = None) -> TaskGraph:
        template = self._graphs.get(graph_id)
        if not template:
            raise ValueError(f"TaskGraph 不存在: {graph_id}")
        nodes = []
        for n in template["nodes"]:
            action_meta = self.get_action_type(n["action"])
            nodes.append(TaskNode(
                id=n["id"],
                name=n["name"],
                action=n["action"],
                ontology_class=n.get("ontology_class", action_meta.get("ontology_class", "aip:AnalysisTask")),
                output_type=n.get("output_type", action_meta.get("output_class", "aip:QueryResult")),
                depends_on=n.get("depends_on", []),
                metrics=n.get("metrics", []),
                dimensions=n.get("dimensions", []),
                governed_by=n.get("governed_by", []),
                expected_output=n.get("expected_output", ""),
            ))
        return TaskGraph(
            id=template["id"],
            iri=template["iri"],
            label=template["label"],
            pattern=template.get("pattern", ""),
            dataset_iri=dataset_iri or template.get("dataset_iri", "aip:Dataset/customer_360"),
            question=question,
            nodes=nodes,
        )

    def resolve_for_question(self, question: str) -> str:
        """根据问题关键词选择 TaskGraph 模板."""
        q = question.lower()
        if any(k in question for k in ("贷前", "筛查", "名单", "screening")):
            return "pre_loan_screening"
        return "general_risk_analysis"


class TaskGraphExecutor:
    """按拓扑序执行 TaskGraph 节点."""

    def __init__(
        self,
        registry: Any,  # DatasetRegistry
        table_name: str,
        dataset_iri: str,
        semantic_dataset_id: str,
        handlers: dict[str, Callable] | None = None,
    ):
        self.registry = registry
        self.table_name = table_name
        self.dataset_iri = dataset_iri
        self.semantic_dataset_id = semantic_dataset_id
        self._handlers = handlers or {}
        self._context: dict[str, Any] = {}

    def register_handler(self, action: str, handler: Callable) -> None:
        self._handlers[action] = handler

    def execute(self, graph: TaskGraph) -> TaskGraph:
        for node in graph.topological_order():
            node.status = TaskStatus.RUNNING
            handler = self._handlers.get(node.action)
            if not handler:
                node.status = TaskStatus.FAILED
                node.error = f"未注册动作处理器: {node.action}"
                continue
            try:
                output = handler(node, self._context, self)
                node.output = output
                node.output_iri = output.get("@id") or output.get("iri") or f"data:aip/output/{node.id}/{uuid4().hex[:8]}"
                node.status = TaskStatus.COMPLETED
                self._context[node.id] = output
            except Exception as e:
                node.status = TaskStatus.FAILED
                node.error = str(e)
        return graph

    # ---- 内置动作处理器 ----

    def handle_aggregate_summary(self, node: TaskNode, ctx: dict, _exec: TaskGraphExecutor) -> dict:
        sql = f"""
            SELECT COUNT(*) AS customer_count,
                   AVG(risk_score) AS avg_risk,
                   SUM(credit_balance) AS total_credit
            FROM {self.table_name}
        """
        df = self.registry.execute_sql(sql)
        row = df.to_dict(orient="records")[0]
        return {
            "@type": node.output_type,
            "@id": f"data:aip/query-result/{node.id}",
            "iri": f"data:aip/query-result/{node.id}",
            "dataset": self.dataset_iri,
            "metrics": node.metrics,
            "derivation": sql.strip(),
            "rowCount": 1,
            "data": row,
        }

    def handle_risk_scan(self, node: TaskNode, ctx: dict, _exec: TaskGraphExecutor) -> dict:
        sql = f"""
            SELECT customer_id, customer_name, risk_score, risk_level, crr_level,
                   region, legal_cases
            FROM {self.table_name}
            WHERE risk_score >= 70 OR risk_level IN ('高', '极高') OR crr_level IN ('D', 'E') OR legal_cases >= 2
            ORDER BY risk_score DESC
            LIMIT 10
        """
        df = self.registry.execute_sql(sql)
        alerts = []
        for r in df.to_dict(orient="records"):
            alerts.append({
                "@type": "aip:AlertEvent",
                "@id": f"data:aip/alert-event/{r.get('customer_id', uuid4().hex[:6])}",
                "customer": f"data:aip/customer/{r.get('customer_id', '')}",
                "riskScore": r.get("risk_score"),
                "crrLevel": r.get("crr_level"),
                "legalCases": r.get("legal_cases"),
            })
        return {
            "@type": node.output_type,
            "@id": f"data:aip/alert-batch/{node.id}",
            "iri": f"data:aip/alert-batch/{node.id}",
            "alerts": alerts,
            "count": len(alerts),
            "derivation": sql.strip(),
            "data": df.to_dict(orient="records"),
        }

    def handle_compare(self, node: TaskNode, ctx: dict, exec_: TaskGraphExecutor) -> dict:
        from aip.analytics.compare import CompareEngine
        dim = "region"
        if node.dimensions:
            dim = node.dimensions[0].split("/")[-1]
        metric = "credit_balance"
        if node.metrics:
            metric = node.metrics[0].split("/")[-1]
        result = CompareEngine(self.registry, self.table_name).by_dimension(dim, metric)
        return {
            "@type": node.output_type,
            "@id": f"data:aip/comparison/{node.id}",
            "iri": f"data:aip/comparison/{node.id}",
            "dimension": node.dimensions[0] if node.dimensions else f"aip:Dimension/{dim}",
            "metric": node.metrics[0] if node.metrics else f"aip:Metric/{metric}",
            **result,
        }

    def handle_attribution(self, node: TaskNode, ctx: dict, exec_: TaskGraphExecutor) -> dict:
        from aip.analytics.attribution import AttributionEngine
        metric = "risk_score"
        dim = "industry"
        if node.metrics:
            metric = node.metrics[0].split("/")[-1]
        if node.dimensions:
            dim = node.dimensions[0].split("/")[-1]
        result = AttributionEngine(self.registry, self.table_name).dimension_attribution(metric, dim)
        return {
            "@type": node.output_type,
            "@id": f"data:aip/attribution/{node.id}",
            "iri": f"data:aip/attribution/{node.id}",
            "metric": node.metrics[0] if node.metrics else f"aip:Metric/{metric}",
            "dimension": node.dimensions[0] if node.dimensions else f"aip:Dimension/{dim}",
            **result,
        }

    def handle_synthesize(self, node: TaskNode, ctx: dict, _exec: TaskGraphExecutor) -> dict:
        insights = []
        summary = ctx.get("T1", {}).get("data", {})
        if summary:
            insights.append(
                f"共 {summary.get('customer_count', 0)} 户客户，"
                f"平均风险分 {summary.get('avg_risk', 0):.1f}"
            )
        risk = ctx.get("T2", {})
        risk_data = risk.get("data", risk.get("alerts", []))
        if risk_data:
            insights.append(f"识别 {len(risk_data)} 户高风险/预警客户需重点关注")
        compare = ctx.get("T3", {}) or ctx.get("T4", {})
        if compare.get("interpretation"):
            insights.append(compare["interpretation"])
        attr = ctx.get("T3", {})
        if attr.get("type") == "attribution" and attr.get("interpretation"):
            insights.append(attr["interpretation"])

        text = "；".join(insights) + "。" if insights else "暂无足够数据形成洞察。"
        conclusion = Conclusion(
            text=text,
            confidence=ConfidenceLevel.HIGH if len(insights) >= 2 else ConfidenceLevel.MEDIUM,
            evidence=[
                EvidenceRef(
                    type="query",
                    source=self.dataset_iri,
                    detail=f"TaskGraph nodes: {list(ctx.keys())}",
                    iri=f"data:aip/evidence/{node.id}",
                )
            ],
            limitations=["基于 TaskGraph 结构化分析"],
            iri=f"data:aip/conclusion/{node.id}",
        )
        return {
            "@type": node.output_type,
            "@id": conclusion.iri,
            "iri": conclusion.iri,
            "text": conclusion.text,
            "confidence": conclusion.confidence.value,
            "insights": insights,
            "conclusion": conclusion.model_dump(),
            "conclusion_jsonld": conclusion.to_jsonld(),
        }

    def handle_path_recommendation(self, node: TaskNode, ctx: dict, _exec: TaskGraphExecutor) -> dict:
        """贷前路径建议 - 受公理约束."""
        synth = ctx.get("T5", ctx.get("T4", {}))
        risk_data = ctx.get("T2", {}).get("data", [])
        recommendations = []
        for r in risk_data:
            crr = r.get("crr_level", "C")
            name = r.get("customer_name", "")
            if crr == "E":
                recommendations.append(f"{name}：暂缓合作（公理 ax_crr_e_no_pure_credit）")
            elif crr == "D":
                recommendations.append(f"{name}：需补充核查，限制纯信用产品（公理 ax_crr_d_limit_credit）")
            elif r.get("legal_cases", 0) >= 2:
                recommendations.append(f"{name}：限制新增授信，核实司法案件（公理 ax_legal_cases_alert）")
            elif r.get("risk_score", 0) >= 70:
                recommendations.append(f"{name}：加强尽调后可继续营销")
            else:
                recommendations.append(f"{name}：可继续营销")

        text = synth.get("text", "") + " 路径建议：" + "；".join(recommendations[:3])
        conclusion = Conclusion(
            text=text,
            confidence=ConfidenceLevel.HIGH,
            evidence=[
                EvidenceRef(type="rule", source="aip:BusinessRule/pre_loan_path", detail=";".join(node.governed_by), iri=f"data:aip/evidence/{node.id}-rule"),
                EvidenceRef(type="query", source=self.dataset_iri, detail="risk_scan", iri=f"data:aip/evidence/{node.id}-query"),
            ],
            limitations=["路径建议来自规则库公理，非审批结论"],
            iri=f"data:aip/conclusion/{node.id}-path",
        )
        return {
            "@type": node.output_type,
            "@id": conclusion.iri,
            "iri": conclusion.iri,
            "recommendations": recommendations,
            "governed_by": node.governed_by,
            "conclusion": conclusion.model_dump(),
            "conclusion_jsonld": conclusion.to_jsonld(),
        }

    def default_handlers(self) -> dict[str, Callable]:
        return {
            "aggregate_summary": self.handle_aggregate_summary,
            "risk_scan": self.handle_risk_scan,
            "compare": self.handle_compare,
            "attribution": self.handle_attribution,
            "synthesize": self.handle_synthesize,
            "path_recommendation": self.handle_path_recommendation,
        }
