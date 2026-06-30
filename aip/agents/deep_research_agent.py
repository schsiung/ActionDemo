"""DeepResearchAgent - 分析任务规划与综合洞察."""

from __future__ import annotations

from typing import Any

from aip.agents.query_agent import QueryAgent
from aip.analytics.attribution import AttributionEngine
from aip.analytics.compare import CompareEngine
from aip.data_prep.dataset_registry import DatasetRegistry
from aip.models import AnalysisTrace, Conclusion, ConfidenceLevel, EvidenceRef
from aip.semantic.model import SemanticModel


class DeepResearchAgent:
    """将业务问题拆解为子任务并逐步执行."""

    def __init__(
        self,
        registry: DatasetRegistry,
        semantic_model: SemanticModel,
        table_name: str,
    ):
        self.registry = registry
        self.semantic = semantic_model
        self.table_name = table_name
        self.query_agent = QueryAgent(registry, semantic_model, table_name)
        self.attribution = AttributionEngine(registry, table_name)
        self.compare = CompareEngine(registry, table_name)
        self.trace = AnalysisTrace()

    def plan(self, question: str) -> dict[str, Any]:
        """分析任务规划 - 拆解子任务."""
        tasks = [
            {"id": "T1", "name": "数据概览", "action": "summary", "depends_on": []},
            {"id": "T2", "name": "风险信号扫描", "action": "risk_scan", "depends_on": ["T1"]},
            {"id": "T3", "name": "多维对比", "action": "compare", "depends_on": ["T1"]},
            {"id": "T4", "name": "综合洞察归纳", "action": "synthesize", "depends_on": ["T2", "T3"]},
        ]
        self.trace.add("DeepResearchAgent", "plan", input_summary=question, output_summary=f"{len(tasks)} tasks")
        return {"question": question, "tasks": tasks}

    def execute(self, question: str) -> dict[str, Any]:
        plan = self.plan(question)
        outputs: dict[str, Any] = {}

        # T1: 数据概览
        summary_sql = f"""
            SELECT COUNT(*) AS customer_count,
                   AVG(risk_score) AS avg_risk,
                   SUM(credit_balance) AS total_credit
            FROM {self.table_name}
        """
        summary_df = self.registry.execute_sql(summary_sql)
        outputs["summary"] = summary_df.to_dict(orient="records")[0]
        self.trace.add("DeepResearchAgent", "summary", output_summary=str(outputs["summary"]))

        # T2: 风险信号
        risk_sql = f"""
            SELECT customer_name, risk_score, risk_level, region
            FROM {self.table_name}
            WHERE risk_score >= 70 OR risk_level IN ('高', '极高')
            ORDER BY risk_score DESC
            LIMIT 10
        """
        risk_df = self.registry.execute_sql(risk_sql)
        outputs["risk_signals"] = risk_df.to_dict(orient="records")
        self.trace.add("DeepResearchAgent", "risk_scan", output_summary=f"{len(risk_df)} signals")

        # T3: 区域对比
        outputs["comparison"] = self.compare.by_dimension("region", "credit_balance")

        # T4: 综合洞察
        high_risk_count = len(outputs["risk_signals"])
        insights = [
            f"共 {outputs['summary']['customer_count']} 户客户，平均风险分 {outputs['summary']['avg_risk']:.1f}",
            f"识别 {high_risk_count} 户高风险客户需重点关注",
        ]
        if outputs["comparison"]["rows"]:
            top_region = outputs["comparison"]["rows"][0]
            region_name = top_region.get("dimension", top_region.get("region", "未知区域"))
            insights.append(
                f"{region_name} 授信余额最高，"
                f"达 {top_region.get('total_value', 0):,.0f} 万元"
            )

        conclusion = Conclusion(
            text="；".join(insights) + "。",
            confidence=ConfidenceLevel.HIGH,
            evidence=[
                EvidenceRef(type="query", source=self.semantic.dataset_id, detail="summary+risk+compare"),
            ],
            limitations=["MVP 演示仅覆盖结构化数据洞察"],
        )

        outputs["insights"] = insights
        outputs["conclusion"] = conclusion.model_dump()
        outputs["plan"] = plan
        outputs["trace_id"] = self.trace.trace_id

        return outputs

    def attribute(self, metric_field: str = "risk_score", dimension_field: str = "industry") -> dict[str, Any]:
        result = self.attribution.dimension_attribution(metric_field, dimension_field)
        self.trace.add("DeepResearchAgent", "attribution", output_summary=metric_field)
        return result
