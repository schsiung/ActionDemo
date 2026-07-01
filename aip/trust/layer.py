"""可信层 - 受控生成、证据引用、SHACL 质检与回溯."""

from __future__ import annotations

from typing import Any

from aip.models import AnalysisTrace, Conclusion, ConfidenceLevel, EvidenceRef
from aip.ontology.factory import get_shacl_validator
from aip.ontology.shacl_validator import ShaclValidator


class TrustLayer:
    """横切可信约束：所有生成内容须经此层校验."""

    def __init__(self, shacl: ShaclValidator | None = None):
        self.shacl = shacl or get_shacl_validator()

    def validate_conclusion(self, conclusion: Conclusion) -> Conclusion:
        """受控生成：无证据则降低置信度."""
        if not conclusion.evidence:
            conclusion.confidence = ConfidenceLevel.LOW
            if "缺少数据证据引用" not in conclusion.limitations:
                conclusion.limitations.append("缺少数据证据引用")
        elif len(conclusion.evidence) < 2:
            conclusion.confidence = ConfidenceLevel.MEDIUM
        else:
            has_iri = any(e.iri or e.metric_id for e in conclusion.evidence)
            conclusion.confidence = ConfidenceLevel.HIGH if has_iri else ConfidenceLevel.MEDIUM

        shacl_result = self.shacl.validate_conclusion(conclusion)
        if not shacl_result.passed:
            conclusion.confidence = ConfidenceLevel.LOW
            for v in shacl_result.violations:
                if v["message"] not in conclusion.limitations:
                    conclusion.limitations.append(v["message"])
        return conclusion

    def quality_check(self, conclusion: Conclusion, source_data: dict[str, Any]) -> dict[str, Any]:
        """分析结果质检：SHACL + 数字一致性."""
        issues = []
        shacl = self.shacl.validate_conclusion(conclusion)
        issues.extend(v["message"] for v in shacl.violations)
        issues.extend(v["message"] for v in shacl.warnings)

        if not conclusion.evidence:
            issues.append("结论缺少证据引用")

        if conclusion.confidence == ConfidenceLevel.LOW:
            issues.append("置信度偏低，建议人工复核")

        shacl_passed = len([i for i in issues if "必须" in i or "禁止" in i]) == 0
        return {
            "passed": len(issues) == 0,
            "shacl_passed": shacl_passed,
            "issues": issues,
            "message": "；".join(issues) if issues else "质检通过",
        }

    def validate_screening(self, conclusion: Conclusion, customer: dict[str, Any]) -> dict[str, Any]:
        """贷前筛查专项 SHACL 校验."""
        result = self.shacl.validate_all(conclusion, customer=customer, conclusion_type="pre_loan_screening")
        validated = self.validate_conclusion(conclusion)
        return {**result.to_dict(), "conclusion": validated.model_dump()}

    def attach_evidence(
        self,
        conclusion: Conclusion,
        evidence_type: str,
        source: str,
        detail: str = "",
        **kwargs: Any,
    ) -> Conclusion:
        from uuid import uuid4

        conclusion.evidence.append(
            EvidenceRef(
                type=evidence_type,
                source=source,
                detail=detail,
                iri=kwargs.pop("iri", None) or f"data:aip/evidence/{uuid4().hex[:12]}",
                **kwargs,
            )
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
