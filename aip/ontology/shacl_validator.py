"""SHACL 形状校验器 - 轻量规则 + pyshacl 生产引擎."""

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
        self.engine: str = "legacy"
        self.report_text: str = ""

    @property
    def passed(self) -> bool:
        return len(self.violations) == 0

    def merge(self, other: ShaclValidationResult) -> None:
        self.violations.extend(other.violations)
        self.warnings.extend(other.warnings)
        if other.engine != "legacy":
            self.engine = other.engine
        if other.report_text:
            self.report_text = other.report_text

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "engine": self.engine,
            "violations": self.violations,
            "warnings": self.warnings,
            "message": "SHACL 校验通过" if self.passed else "；".join(v["message"] for v in self.violations),
            "report_text": self.report_text[:2000] if self.report_text else "",
        }


class ShaclValidator:
    """YAML 形状目录 + pyshacl 图校验 + 公理文本规则."""

    def __init__(
        self,
        shapes_path: str | Path | None = None,
        ontology: OntologyRegistry | None = None,
        shapes_ttl_path: str | Path | None = None,
        ontology_ttl_path: str | Path | None = None,
        use_pyshacl: bool = True,
    ):
        self.ontology = ontology
        self.shapes: list[dict] = []
        self.use_pyshacl = use_pyshacl
        self._pyshacl = None
        if shapes_path:
            self.load(shapes_path)
        if shapes_ttl_path and use_pyshacl:
            self._init_pyshacl(shapes_ttl_path, ontology_ttl_path)

    @property
    def engine_name(self) -> str:
        return "pyshacl" if self._pyshacl else "legacy"

    def _init_pyshacl(self, shapes_ttl: str | Path, ontology_ttl: str | Path | None) -> None:
        try:
            from aip.ontology.pyshacl_engine import PyShaclEngine

            self._pyshacl = PyShaclEngine(shapes_ttl, ontology_ttl)
        except Exception:
            self._pyshacl = None
            self.use_pyshacl = False

    def load(self, path: str | Path) -> None:
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        self.shapes = data.get("shapes", [])

    def list_shapes(self) -> list[dict[str, str]]:
        return [
            {"id": s.get("id", ""), "target_class": s.get("target_class", ""), "label": s.get("label", "")}
            for s in self.shapes
        ]

    def validate_conclusion(
        self,
        conclusion: Conclusion | dict,
        conclusion_type: str = "query",
        metric_iri: str | None = None,
        use_pyshacl: bool | None = None,
    ) -> ShaclValidationResult:
        result = ShaclValidationResult()
        if isinstance(conclusion, Conclusion):
            c = conclusion
        else:
            c = Conclusion(**{k: v for k, v in conclusion.items() if k in Conclusion.model_fields})

        if self._should_use_pyshacl(use_pyshacl):
            py_result = self._pyshacl.validate_conclusion(c)
            result.engine = py_result.get("engine", "pyshacl")
            result.violations = py_result.get("violations", [])
            result.warnings = py_result.get("warnings", [])
            result.report_text = py_result.get("report_text", "")
            if conclusion_type == "metric_explain":
                legacy = self._legacy_metric_explain(c, metric_iri)
                result.merge(legacy)
            return result

        return self._legacy_validate_conclusion(c, conclusion_type, metric_iri)

    def _legacy_validate_conclusion(
        self,
        c: Conclusion,
        conclusion_type: str,
        metric_iri: str | None,
    ) -> ShaclValidationResult:
        result = ShaclValidationResult()
        if not c.evidence:
            result.violations.append({
                "shape": "sh:ConclusionShape",
                "message": "结论必须至少有一条证据支撑",
            })
        if c.confidence.value in ("low", "unknown") and not c.limitations:
            result.warnings.append({
                "shape": "sh:ConclusionConfidenceShape",
                "message": "低置信结论须标注局限性",
            })
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
        if conclusion_type == "metric_explain":
            result.merge(self._legacy_metric_explain(c, metric_iri))
        return result

    def _legacy_metric_explain(self, c: Conclusion, metric_iri: str | None) -> ShaclValidationResult:
        result = ShaclValidationResult()
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

    def validate_customer_screening(
        self,
        customer: dict[str, Any],
        use_pyshacl: bool | None = None,
    ) -> ShaclValidationResult:
        if self._should_use_pyshacl(use_pyshacl) and customer:
            py_result = self._pyshacl.validate_customer(customer)
            result = ShaclValidationResult()
            result.engine = py_result.get("engine", "pyshacl")
            result.violations = py_result.get("violations", [])
            result.warnings = py_result.get("warnings", [])
            result.report_text = py_result.get("report_text", "")
            return result

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
        if risk >= 70 and customer.get("legal_cases") is None:
            result.warnings.append({
                "shape": "sh:PreLoanHighRiskShape",
                "message": "高风险客户须有司法信号记录",
            })
        return result

    def validate_conclusion_text_axioms(self, text: str, customer: dict[str, Any] | None = None) -> ShaclValidationResult:
        """公理约束：CRR-D/E 禁止纯信用放贷表述（业务规则，非 SHACL 图）."""
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

    def validate_query_result(
        self,
        result_data: dict[str, Any],
        use_pyshacl: bool | None = None,
    ) -> ShaclValidationResult:
        if self._should_use_pyshacl(use_pyshacl) and result_data:
            py_result = self._pyshacl.validate_query_result(result_data)
            result = ShaclValidationResult()
            result.engine = py_result.get("engine", "pyshacl")
            result.violations = py_result.get("violations", [])
            result.warnings = py_result.get("warnings", [])
            return result

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
        use_pyshacl: bool | None = None,
    ) -> ShaclValidationResult:
        merged = ShaclValidationResult()

        if self._should_use_pyshacl(use_pyshacl):
            c = conclusion if isinstance(conclusion, Conclusion) else Conclusion(
                **{k: v for k, v in conclusion.items() if k in Conclusion.model_fields}
            )
            py_bundle = self._pyshacl.validate_bundle(c, query_result, customer)
            merged.engine = py_bundle.get("engine", "pyshacl")
            merged.violations = list(py_bundle.get("violations", []))
            merged.warnings = list(py_bundle.get("warnings", []))
            merged.report_text = py_bundle.get("report_text", "")
            axiom = self.validate_conclusion_text_axioms(c.text, customer)
            merged.merge(axiom)
            if conclusion_type == "metric_explain":
                merged.merge(self._legacy_metric_explain(c, metric_iri))
            return merged

        for partial in [
            self.validate_conclusion(conclusion, conclusion_type, metric_iri, use_pyshacl=False),
            self.validate_query_result(query_result or {}, use_pyshacl=False),
            self.validate_customer_screening(customer or {}, use_pyshacl=False) if customer else ShaclValidationResult(),
            self.validate_conclusion_text_axioms(
                conclusion.text if isinstance(conclusion, Conclusion) else conclusion.get("text", ""),
                customer,
            ),
        ]:
            merged.merge(partial)
        return merged

    def _should_use_pyshacl(self, override: bool | None) -> bool:
        if override is False:
            return False
        return bool(self.use_pyshacl and self._pyshacl)
