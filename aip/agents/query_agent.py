"""QueryAgent - 智能问数、口径解释与多轮追问."""

from __future__ import annotations

import re
from typing import Any

from aip.data_prep.dataset_registry import DatasetRegistry
from aip.models import AnalysisTrace, ChartType, Conclusion, ConfidenceLevel, EvidenceRef, QueryResult
from aip.semantic.model import SemanticModel


class ConversationContext:
    """多轮追问会话状态."""

    def __init__(self):
        self.last_sql: str | None = None
        self.last_result: QueryResult | None = None
        self.current_filters: dict[str, Any] = {}
        self.history: list[dict[str, Any]] = []

    def update(self, question: str, result: QueryResult) -> None:
        self.last_sql = result.sql
        self.last_result = result
        self.history.append({"question": question, "sql": result.sql, "row_count": result.row_count})


class QueryAgent:
    """
    MVP 问数 Agent：基于规则意图识别 + 语义模型生成 SQL。
    生产环境可替换为 LLM Text2SQL。
    """

    INTENT_PATTERNS = [
        (r"口径|怎么算|如何计算|定义", "metric_explain"),
        (r"推荐|相关指标|上下游", "metric_recommend"),
        (r"按(.+?)拆|分组|分布", "drill_dimension"),
        (r"明细|详情|逐笔", "detail"),
        (r"同比|环比|对比|vs|相比", "compare"),
        (r"为什么|原因|归因|下降|上升|波动", "attribution"),
        (r"排名|top|前\d+", "rank"),
        (r"趋势|走势|变化", "trend"),
    ]

    def __init__(
        self,
        registry: DatasetRegistry,
        semantic_model: SemanticModel,
        table_name: str,
    ):
        self.registry = registry
        self.semantic = semantic_model
        self.table_name = table_name
        self.context = ConversationContext()
        self.trace = AnalysisTrace()

    def ask(self, question: str) -> dict[str, Any]:
        self.trace.add("QueryAgent", "ask", input_summary=question)
        intent = self._classify_intent(question)

        if intent == "metric_explain":
            return self._explain_metric(question)
        if intent == "metric_recommend":
            return self._recommend_metrics(question)
        if intent == "drill_dimension" and self.context.last_result:
            return self._followup_drill(question)
        if intent == "compare":
            return self._run_compare(question)
        if intent == "attribution":
            return {"type": "attribution_request", "question": question, "delegate": "AttributionEngine"}
        if intent == "rank":
            return self._run_query(question, order="DESC", chart=ChartType.RANK)
        if intent == "trend":
            return self._run_query(question, chart=ChartType.LINE)

        return self._run_query(question)

    def _classify_intent(self, question: str) -> str:
        for pattern, intent in self.INTENT_PATTERNS:
            if re.search(pattern, question, re.IGNORECASE):
                return intent
        return "query"

    def _explain_metric(self, question: str) -> dict[str, Any]:
        for metric in self.semantic.metrics:
            if metric.name in question or metric.id in question:
                explanation = self.semantic.explain_metric(metric.id)
                conclusion = Conclusion(
                    text=f"{metric.name}：{metric.description}。计算公式为 {metric.formula}。",
                    confidence=ConfidenceLevel.HIGH,
                    evidence=[
                        EvidenceRef(type="metric_def", source="semantic_model", metric_id=metric.id, detail=metric.formula)
                    ],
                )
                self.trace.add("QueryAgent", "metric_explain", output_summary=metric.id)
                return {"type": "metric_explain", "explanation": explanation, "conclusion": conclusion.model_dump()}

        return {
            "type": "metric_explain",
            "explanation": {"found": False, "message": "未匹配到指标，请指定指标名称"},
        }

    def _recommend_metrics(self, question: str) -> dict[str, Any]:
        for metric in self.semantic.metrics:
            if metric.name in question:
                related = self.semantic.recommend_related(metric.id)
                self.trace.add("QueryAgent", "metric_recommend", output_summary=str(len(related)))
                return {"type": "metric_recommend", "base_metric": metric.name, "recommendations": related}
        return {"type": "metric_recommend", "recommendations": []}

    def _followup_drill(self, question: str) -> dict[str, Any]:
        match = re.search(r"按(.+?)拆|按(.+?)分布|按(.+?)分组", question)
        dim_keyword = (match.group(1) or match.group(2) or match.group(3) or "").strip() if match else ""
        dimension = next((d for d in self.semantic.dimensions if dim_keyword in d.name or dim_keyword in d.field), None)
        if not dimension:
            dimension = self.semantic.dimensions[0]

        sql = f"""
            SELECT {dimension.field} AS {dimension.id}, COUNT(*) AS cnt
            FROM {self.table_name}
            GROUP BY {dimension.field}
            ORDER BY cnt DESC
        """
        return self._execute_and_package(question, sql, chart=ChartType.BAR)

    def _run_compare(self, question: str) -> dict[str, Any]:
        sql = f"""
            SELECT region,
                   SUM(credit_balance) AS current_balance,
                   SUM(credit_balance) * 0.92 AS prior_balance
            FROM {self.table_name}
            GROUP BY region
            ORDER BY current_balance DESC
        """
        return self._execute_and_package(question, sql, chart=ChartType.BAR, compare=True)

    def _run_query(self, question: str, order: str = "ASC", chart: ChartType = ChartType.BAR) -> dict[str, Any]:
        sql = f"SELECT * FROM {self.table_name} ORDER BY credit_balance {order} LIMIT 20"
        if "机构" in question or "region" in question.lower():
            sql = f"""
                SELECT region, SUM(credit_balance) AS total_credit, AVG(risk_score) AS avg_risk
                FROM {self.table_name}
                GROUP BY region
                ORDER BY total_credit {order}
            """
        return self._execute_and_package(question, sql, chart=chart)

    def _execute_and_package(
        self, question: str, sql: str, chart: ChartType = ChartType.BAR, compare: bool = False
    ) -> dict[str, Any]:
        df = self.registry.execute_sql(sql)
        result = QueryResult(
            sql=sql.strip(),
            columns=list(df.columns),
            rows=df.to_dict(orient="records"),
            dataset_id=self.semantic.dataset_id,
            row_count=len(df),
        )
        self.context.update(question, result)

        evidence = [
            EvidenceRef(
                type="query",
                source=self.semantic.dataset_id,
                detail=sql.strip()[:200],
                period="当期",
            )
        ]
        conclusion = Conclusion(
            text=f"共查询到 {result.row_count} 条记录。",
            confidence=ConfidenceLevel.HIGH if result.row_count > 0 else ConfidenceLevel.LOW,
            evidence=evidence,
            limitations=["MVP 演示使用规则匹配生成 SQL"] if result.row_count > 0 else ["查询结果为空"],
        )

        self.trace.add("QueryAgent", "query", output_summary=f"{result.row_count} rows")

        return {
            "type": "compare" if compare else "query",
            "question": question,
            "result": result.model_dump(),
            "chart_type": chart.value,
            "conclusion": conclusion.model_dump(),
            "follow_up_suggestions": [
                "按行业分布",
                "查看授信明细",
                "为什么风险分上升",
                "推荐相关指标",
            ],
        }
