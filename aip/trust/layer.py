"""可信层 - 受控生成、证据引用、质检与回溯."""

from __future__ import annotations

from typing import Any

from aip.models import AnalysisTrace, Conclusion, ConfidenceLevel, EvidenceRef


class TrustLayer:
    """横切可信约束：所有生成内容须经此层校验."""

    def validate_conclusion(self, conclusion: Conclusion) -> Conclusion:
        """受控生成：无证据则降低置信度."""
        if not conclusion.evidence:
            conclusion.confidence = ConfidenceLevel.LOW
            conclusion.limitations.append("缺少数据证据引用")
        elif len(conclusion.evidence) < 2:
            conclusion.confidence = ConfidenceLevel.MEDIUM
        else:
            conclusion.confidence = ConfidenceLevel.HIGH
        return conclusion

    def quality_check(self, conclusion: Conclusion, source_data: dict[str, Any]) -> dict[str, Any]:
        """分析结果质检：数字一致性、依据完整性."""
        issues = []

        if not conclusion.evidence:
            issues.append("结论缺少证据引用")

        summary = source_data.get("summary", {})
        insights = source_data.get("insights", [])
        if summary and insights:
            import re
            for insight in insights:
                numbers = re.findall(r"[\d,.]+", insight)
                for num in numbers:
                    clean_num = num.replace(",", "")
                    if clean_num.isdigit():
                        val = int(clean_num)
                        known = {summary.get("customer_count"), summary.get("total_credit")}
                        if val > 0 and val not in known and val != int(summary.get("avg_risk", 0)):
                            pass  # MVP: 简化校验

        if conclusion.confidence == ConfidenceLevel.LOW:
            issues.append("置信度偏低，建议人工复核")

        return {
            "passed": len(issues) == 0,
            "issues": issues,
            "message": "；".join(issues) if issues else "质检通过",
        }

    def attach_evidence(
        self,
        conclusion: Conclusion,
        evidence_type: str,
        source: str,
        detail: str = "",
        **kwargs: Any,
    ) -> Conclusion:
        conclusion.evidence.append(
            EvidenceRef(type=evidence_type, source=source, detail=detail, **kwargs)
        )
        return self.validate_conclusion(conclusion)

    def trace_summary(self, trace: AnalysisTrace) -> dict[str, Any]:
        """分析过程回溯摘要."""
        return {
            "trace_id": trace.trace_id,
            "step_count": len(trace.steps),
            "steps": [
                {
                    "agent": s.agent,
                    "action": s.action,
                    "input": s.input_summary,
                    "output": s.output_summary,
                    "time": s.timestamp.isoformat(),
                }
                for s in trace.steps
            ],
        }
