"""SHACL 形状校验器 - 贷前筛查等场景."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from aip.models import Conclusion, EvidenceRef
from aip.ontology.registry import OntologyRegistry


class ShaclValidationResult:
    def __init__(self):
        self.violations: list[dict[str, str]] = []
        self.warnings: list[dict[str, str]] = []

    @property
    def passed(self) -> bool:
        return len(self.violations) == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "violations": self.violations,
            "warnings": self.warnings,
            "message": "SHACL 校验通过" if self.passed else "；".join(v["message"] for v in self.violations),
        }


class ShaclValidator:
    """基于 YAML 形状定义的轻量 SHACL 校验（与 .shacl.ttl 对齐）."""

    def __init__(self, shapes_path: str | Path | None = None, ontology: OntologyRegistry | None = None):
        self.ontology = ontology
        self.shapes: list[dict] = []
        if shapes_path:
            self.load(shapes_path)

    def load(self, path: str | Path) -> None:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self.shapes = data.get("shapes", [])

    def validate_conclusion(
        self,
        conclusion: Conclusion | dict,
        conclusion_type: str = "query",
        metric_iri: str | None = None,
    ) -> ShaclValidationResult:
        result = ShaclValidationResult()
        if isinstance(conclusion, Conclusion):
            c = conclusion
        else:
            c = Conclusion(**{k: v for k, v in conclusion.items() if k in Conclusion.model_fields})

        # sh:ConclusionShape
        if not c.evidence:
            result.violations.append({
                "shape": "sh:ConclusionShape",
                "message": "结论必须至少有一条证据支撑",
            })

        # sh:ConclusionConfidenceShape
        if c.confidence.value in ("low", "unknown") and not c.limitations:
            result.warnings.append({
                "shape": "sh:ConclusionConfidenceShape",
                "message": "低置信结论须标注局限性",
            })

        # sh:EvidenceShape + sh:EvidenceQueryShape
        for ev in c.evidence:
            if not ev.type or not ev.source:
                result.violations.append({
                    "shape": "sh:EvidenceShape",
                    "message": "证据必须包含类型与来源",
                })
            if ev.type == "query" and len(ev.detail or "") < 5:
                result.violations.append({
                    "shape": "sh:EvidenceQueryShape",
                    "message": "查询类证据必须包含 derivation（SQL 或查询摘要）",
                })

        # sh:MetricExplainShape
        if conclusion_type == "metric_explain":
            has_metric_iri = any(
                (ev.metric_id and ev.metric_id.startswith("aip:Metric/")) or metric_iri
                for ev in c.evidence
            )
            if not has_metric_iri and not metric_iri:
                result.violations.append({
                    "shape": "sh:MetricExplainShape",
                    "message": "指标口径解释必须引用指标 IRI",
                })

        return result

    def validate_customer_screening(self, customer: dict[str, Any]) -> ShaclValidationResult:
        """贷前筛查客户数据形状校验."""
        result = ShaclValidationResult()

        if customer.get("risk_score") is None:
            result.warnings.append({
                "shape": "sh:PreLoanScreeningCustomerShape",
                "message": "贷前筛查客户应包含风险评分",
            })
        if not customer.get("crr_level"):
            result.warnings.append({
                "shape": "sh:PreLoanScreeningCustomerShape",
                "message": "贷前筛查客户应包含 CRR 等级",
            })

        risk = customer.get("risk_score", 0)
        if risk >= 70 and not customer.get("legal_cases") and customer.get("legal_cases") != 0:
            result.warnings.append({
                "shape": "sh:PreLoanHighRiskShape",
                "message": "高风险客户须有司法信号记录",
            })

        return result

    def validate_conclusion_text_axioms(self, text: str, customer: dict[str, Any] | None = None) -> ShaclValidationResult:
        """公理约束：CRR-D/E 禁止纯信用放贷表述."""
        result = ShaclValidationResult()
        if not customer:
            return result

        crr = customer.get("crr_level", "")
        forbidden_phrases = ["纯信用放贷", "可纯信用", "建议纯信用贷款"]
        if crr in ("D", "E"):
            for phrase in forbidden_phrases:
                if phrase in text:
                    result.violations.append({
                        "shape": "sh:CRRRestrictionShape",
                        "message": f"CRR-{crr} 级客户禁止输出「{phrase}」类结论（公理 ax_crr_d/e）",
                    })
        return result

    def validate_query_result(self, result_data: dict[str, Any]) -> ShaclValidationResult:
        result = ShaclValidationResult()
        if not result_data.get("dataset_id") and not result_data.get("dataset"):
            result.violations.append({
                "shape": "sh:QueryResultShape",
                "message": "查询结果必须关联数据集",
            })
        if result_data.get("row_count", -1) < 0:
            result.violations.append({
                "shape": "sh:QueryResultShape",
                "message": "rowCount 无效",
            })
        return result

    def validate_all(
        self,
        conclusion: Conclusion | dict,
        query_result: dict | None = None,
        customer: dict | None = None,
        conclusion_type: str = "query",
        metric_iri: str | None = None,
    ) -> ShaclValidationResult:
        merged = ShaclValidationResult()
        for partial in [
            self.validate_conclusion(conclusion, conclusion_type, metric_iri),
            self.validate_query_result(query_result or {}),
            self.validate_customer_screening(customer or {}) if customer else ShaclValidationResult(),
            self.validate_conclusion_text_axioms(
                conclusion.text if isinstance(conclusion, Conclusion) else conclusion.get("text", ""),
                customer,
            ),
        ]:
            merged.violations.extend(partial.violations)
            merged.warnings.extend(partial.warnings)
        return merged
