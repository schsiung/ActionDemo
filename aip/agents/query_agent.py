"""QueryAgent - 本体驱动的智能问数、口径解释与多轮追问."""

from __future__ import annotations

import re
from typing import Any
from uuid import uuid4

from aip.data_prep.dataset_registry import DatasetRegistry
from aip.models import AnalysisTrace, ChartType, Conclusion, ConfidenceLevel, EvidenceRef, QueryResult
from aip.ontology.factory import DEFAULT_DATASET_IRI, get_ontology_registry, get_shacl_validator
from aip.ontology.prompt import SemanticDDLPromptBuilder
from aip.ontology.shacl_validator import ShaclValidator
from aip.semantic.model import SemanticModel


class ConversationContext:
    """多轮追问会话状态."""

    def __init__(self):
        self.last_sql: str | None = None
        self.last_result: QueryResult | None = None
        self.current_filters: dict[str, Any] = {}
        self.history: list[dict[str, Any]] = []

    def summary(self) -> str:
        if not self.history:
            return ""
        lines = [f"Q: {h['question']} → {h['row_count']}行" for h in self.history[-3:]]
        return "\n".join(lines)

    def update(self, question: str, result: QueryResult) -> None:
        self.last_sql = result.sql
        self.last_result = result
        self.history.append({"question": question, "sql": result.sql, "row_count": result.row_count})


class QueryAgent:
    """
    问数 Agent：规则意图 + 语义模型 SQL + 本体语义 DDL Prompt。
    生产环境将 `_plan_with_llm` 对接企业 LLM Text2SQL。
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
        (r"高风险|风险客户|筛查", "pre_loan_screening"),
    ]

    def __init__(
        self,
        registry: DatasetRegistry,
        semantic_model: SemanticModel,
        table_name: str,
        ontology_registry=None,
        dataset_iri: str | None = None,
        shacl_validator: ShaclValidator | None = None,
    ):
        self.registry = registry
        self.semantic = semantic_model
        self.table_name = table_name
        self.ontology = ontology_registry or get_ontology_registry()
        self.dataset_iri = dataset_iri or semantic_model.dataset_iri or DEFAULT_DATASET_IRI
        self.prompt_builder = SemanticDDLPromptBuilder(self.ontology)
        self.shacl = shacl_validator or get_shacl_validator()
        self.context = ConversationContext()
        self.trace = AnalysisTrace()

    def ask(self, question: str) -> dict[str, Any]:
        self.trace.add("QueryAgent", "ask", input_summary=question)
        prompt_bundle = self.prompt_builder.build_full_prompt(
            self.dataset_iri, question, self.context.summary()
        )
        intent = self._classify_intent(question)

        if intent == "metric_explain":
            return self._package_response(self._explain_metric(question), prompt_bundle)
        if intent == "metric_recommend":
            return self._package_response(self._recommend_metrics(question), prompt_bundle)
        if intent == "drill_dimension" and self.context.last_result:
            return self._package_response(self._followup_drill(question), prompt_bundle)
        if intent == "compare":
            return self._package_response(self._run_compare(question), prompt_bundle)
        if intent == "attribution":
            return self._package_response(
                {"type": "attribution_request", "question": question, "delegate": "AttributionEngine"},
                prompt_bundle,
            )
        if intent == "pre_loan_screening":
            return self._package_response(self._run_pre_loan_screening(question), prompt_bundle)
        if intent == "rank":
            return self._package_response(self._run_query(question, order="DESC", chart=ChartType.RANK), prompt_bundle)
        if intent == "trend":
            return self._package_response(self._run_query(question, chart=ChartType.LINE), prompt_bundle)

        return self._package_response(self._run_query(question), prompt_bundle)

    def _classify_intent(self, question: str) -> str:
        for pattern, intent in self.INTENT_PATTERNS:
            if re.search(pattern, question, re.IGNORECASE):
                return intent
        return "query"

    def _explain_metric(self, question: str) -> dict[str, Any]:
        for metric in self.semantic.metrics:
            if metric.name in question or metric.id in question:
                iri = metric.iri or f"aip:Metric/{metric.id}"
                explanation = self.semantic.explain_metric(metric.id)
                if self.ontology.get_metric(metric.id):
                    explanation = self.ontology.explain_metric(metric.id)
                    explanation["iri"] = iri
                conclusion = Conclusion(
                    text=f"{metric.name}：{metric.description or explanation.get('label', '')}。计算公式为 {metric.formula}。",
                    confidence=ConfidenceLevel.HIGH,
                    metric_iri=iri,
                    evidence=[
                        EvidenceRef(
                            type="metric_def",
                            source=iri,
                            metric_id=iri,
                            detail=metric.formula,
                            iri=f"data:aip/evidence/{uuid4().hex[:12]}",
                        )
                    ],
                )
                shacl_result = self.shacl.validate_conclusion(conclusion, "metric_explain", iri)
                self.trace.add("QueryAgent", "metric_explain", output_summary=metric.id)
                return {
                    "type": "metric_explain",
                    "explanation": explanation,
                    "conclusion": conclusion.model_dump(),
                    "conclusion_jsonld": conclusion.to_jsonld(),
                    "shacl": shacl_result.to_dict(),
                }

        return {
            "type": "metric_explain",
            "explanation": {"found": False, "message": "未匹配到指标，请指定指标名称"},
        }

    def _recommend_metrics(self, question: str) -> dict[str, Any]:
        for metric in self.semantic.metrics:
            if metric.name in question or metric.id in question:
                related = self.semantic.recommend_related(metric.id)
                onto_related = self.ontology.related_metrics(metric.id)
                if onto_related:
                    related = [{"iri": r.iri, "name": r.label or r.iri, "reason": "本体关联"} for r in onto_related]
                self.trace.add("QueryAgent", "metric_recommend", output_summary=str(len(related)))
                return {
                    "type": "metric_recommend",
                    "base_metric": metric.name,
                    "base_metric_iri": metric.iri or f"aip:Metric/{metric.id}",
                    "recommendations": related,
                }
        return {"type": "metric_recommend", "recommendations": []}

    def _run_pre_loan_screening(self, question: str) -> dict[str, Any]:
        sql = f"""
            SELECT customer_id, customer_name, region, industry, credit_balance,
                   risk_score, crr_level, legal_cases, risk_level
            FROM {self.table_name}
            WHERE risk_score >= 70 OR crr_level IN ('D', 'E') OR legal_cases >= 2
            ORDER BY risk_score DESC
        """
        return self._execute_and_package(
            question, sql, chart=ChartType.RANK, metric_iri="aip:Metric/risk_score", conclusion_type="pre_loan_screening"
        )

    def _followup_drill(self, question: str) -> dict[str, Any]:
        match = re.search(r"按(.+?)拆|按(.+?)分布|按(.+?)分组", question)
        dim_keyword = (match.group(1) or match.group(2) or match.group(3) or "").strip() if match else ""
        dimension = next((d for d in self.semantic.dimensions if dim_keyword in d.name or dim_keyword in d.field), None)
        if not dimension:
            dimension = self.semantic.dimensions[0] if self.semantic.dimensions else None
        if not dimension:
            field = "industry"
            dim_id = "industry"
        else:
            field, dim_id = dimension.field, dimension.id

        sql = f"""
            SELECT {field} AS {dim_id}, COUNT(*) AS cnt
            FROM {self.table_name}
            GROUP BY {field}
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
        return self._execute_and_package(
            question, sql, chart=ChartType.BAR, compare=True, metric_iri="aip:Metric/credit_balance"
        )

    def _run_query(self, question: str, order: str = "ASC", chart: ChartType = ChartType.BAR) -> dict[str, Any]:
        sql = f"SELECT * FROM {self.table_name} ORDER BY credit_balance {order} LIMIT 20"
        metric_iri = "aip:Metric/credit_balance"
        if "机构" in question or "region" in question.lower():
            sql = f"""
                SELECT region, SUM(credit_balance) AS total_credit, AVG(risk_score) AS avg_risk
                FROM {self.table_name}
                GROUP BY region
                ORDER BY total_credit {order}
            """
        if "高风险" in question:
            return self._run_pre_loan_screening(question)
        return self._execute_and_package(question, sql, chart=chart, metric_iri=metric_iri)

    def _execute_and_package(
        self,
        question: str,
        sql: str,
        chart: ChartType = ChartType.BAR,
        compare: bool = False,
        metric_iri: str | None = None,
        conclusion_type: str = "query",
    ) -> dict[str, Any]:
        df = self.registry.execute_sql(sql)
        dataset_iri = self.dataset_iri
        result = QueryResult(
            sql=sql.strip(),
            columns=list(df.columns),
            rows=df.to_dict(orient="records"),
            dataset_id=self.semantic.dataset_id,
            dataset_iri=dataset_iri,
            metric_iri=metric_iri,
            row_count=len(df),
            result_iri=f"data:aip/query-result/{uuid4().hex[:12]}",
        )
        self.context.update(question, result)

        evidence = [
            EvidenceRef(
                type="query",
                source=dataset_iri,
                detail=sql.strip()[:500],
                period="当期",
                metric_id=metric_iri,
                iri=f"data:aip/evidence/{uuid4().hex[:12]}",
            )
        ]
        limitations = []
        if result.row_count > 0:
            limitations.append("SQL 由规则引擎基于语义 DDL 生成，生产环境对接 LLM Text2SQL")
        else:
            limitations.append("查询结果为空，无法支撑强结论")

        conclusion = Conclusion(
            text=f"共查询到 {result.row_count} 条记录。",
            confidence=ConfidenceLevel.HIGH if result.row_count > 0 else ConfidenceLevel.LOW,
            evidence=evidence,
            limitations=limitations,
            metric_iri=metric_iri,
        )

        shacl_result = self.shacl.validate_all(
            conclusion,
            query_result=result.model_dump(),
            conclusion_type=conclusion_type,
            metric_iri=metric_iri,
        )
        if not shacl_result.passed:
            conclusion.confidence = ConfidenceLevel.LOW
            conclusion.limitations.extend([v["message"] for v in shacl_result.violations])

        self.trace.add("QueryAgent", "query", output_summary=f"{result.row_count} rows")

        return {
            "type": "compare" if compare else conclusion_type if conclusion_type != "query" else "query",
            "question": question,
            "result": result.model_dump(),
            "result_jsonld": result.to_jsonld(),
            "chart_type": chart.value,
            "metric_iri": metric_iri,
            "conclusion": conclusion.model_dump(),
            "conclusion_jsonld": conclusion.to_jsonld(),
            "shacl": shacl_result.to_dict(),
            "follow_up_suggestions": [
                "按行业分布",
                "查看司法案件明细",
                "为什么风险分上升",
                "推荐相关指标",
            ],
        }

    def _package_response(self, payload: dict[str, Any], prompt_bundle: dict[str, str]) -> dict[str, Any]:
        payload["prompt"] = {
            "ontology_version": prompt_bundle.get("ontology_version"),
            "semantic_ddl": prompt_bundle.get("semantic_ddl"),
        }
        payload["@context"] = "https://bank.example.com/ontology/aip/context.jsonld"
        return payload

    def get_prompt_for_question(self, question: str) -> dict[str, str]:
        """暴露完整 Prompt 供调试 / LLM 对接."""
        return self.prompt_builder.build_full_prompt(self.dataset_iri, question, self.context.summary())
