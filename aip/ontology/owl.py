"""OWL/Turtle 序列化与反序列化."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from aip.ontology.registry import OntologyRegistry

AIP = "https://bank.example.com/ontology/aip#"
RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
OWL = "http://www.w3.org/2002/07/owl#"
XSD = "http://www.w3.org/2001/XMLSchema#"


def _q(local: str) -> str:
    return f"aip:{local}"


def _iri(local: str) -> str:
    return f"<{AIP}{local}>"


class TurtleSerializer:
    """将 OntologyRegistry / YAML 本体导出为 OWL Turtle."""

    def __init__(self, registry: OntologyRegistry):
        self.reg = registry
        self.ns = registry._core.namespace if registry._core else AIP

    def serialize(self) -> str:
        lines = [
            f"@prefix aip: <{self.ns}> .",
            f"@prefix rdf: <{RDF}> .",
            f"@prefix rdfs: <{RDFS}> .",
            f"@prefix owl: <{OWL}> .",
            f"@prefix xsd: <{XSD}> .",
            "",
            f"aip: aip:Ontology ;",
            f"    owl:versionInfo \"{self.reg.version}\" ;",
            f"    rdfs:label \"AIP-Core 领域本体\"@zh .",
            "",
        ]
        lines.extend(self._serialize_classes())
        lines.extend(self._serialize_metrics())
        lines.extend(self._serialize_axioms())
        lines.extend(self._serialize_bindings())
        return "\n".join(lines) + "\n"

    def _serialize_classes(self) -> list[str]:
        classes = [
            ("Customer", "客户", "BusinessEntity"),
            ("Metric", "指标", None),
            ("Dimension", "维度", None),
            ("Dataset", "数据集", None),
            ("Conclusion", "结论", None),
            ("Evidence", "证据", None),
            ("AlertRule", "预警规则", None),
            ("AlertEvent", "预警事件", None),
            ("BusinessRule", "业务规则", None),
            ("QueryResult", "查询结果", None),
            ("AnalysisTask", "分析任务", None),
            ("Report", "报告", None),
            ("ReportTemplate", "报告模板", None),
        ]
        out = []
        for name, label, parent in classes:
            if parent:
                out.append(f"aip:{name} a owl:Class ; rdfs:subClassOf aip:{parent} ; rdfs:label \"{label}\"@zh .")
            else:
                out.append(f"aip:{name} a owl:Class ; rdfs:label \"{label}\"@zh .")
        out.append("")
        # CRR levels
        for level in ["A", "B", "C", "D", "E"]:
            out.append(f"aip:CRRLevel_{level} a aip:CRRLevel ; rdfs:label \"CRR-{level}\"@zh .")
        out.append("")
        return out

    def _serialize_metrics(self) -> list[str]:
        out = []
        seen = set()
        for key, metric in self.reg._metrics.items():
            if not key.startswith("aip:") and "/" not in key:
                local = f"Metric/{key}"
                if local in seen:
                    continue
                seen.add(local)
                out.append(f"aip:{local.replace('/', '_')} a aip:Metric ;")
                out.append(f"    rdfs:label \"{metric.label}\"@zh ;")
                out.append(f"    aip:formula \"{metric.formula}\" ;")
                if metric.unit:
                    out.append(f"    aip:unit \"{metric.unit}\" ;")
                if metric.time_window:
                    out.append(f"    aip:timeWindow \"{metric.time_window}\" ;")
                for rel in metric.related_to:
                    rel_local = rel.split("/")[-1].replace("/", "_")
                    out.append(f"    aip:relatedTo aip:Metric_{rel_local} ;")
                out[-1] = out[-1].rstrip(" ;") + " ."
                out.append("")
        return out

    def _serialize_axioms(self) -> list[str]:
        out = []
        for axiom in self.reg._axioms.values():
            local = axiom.id
            out.append(f"aip:{local} a owl:Class ;")
            out.append(f"    rdfs:label \"{axiom.label}\"@zh ;")
            out.append(f"    aip:axiomType \"{axiom.type}\" ;")
            if axiom.type == "restriction" and axiom.condition:
                prop = axiom.condition.get("property", "")
                val = axiom.condition.get("value", "")
                out.append(f"    aip:onProperty aip:{prop} ;")
                out.append(f"    aip:hasValue \"{val}\" ;")
            if axiom.type == "alert":
                if axiom.metric:
                    out.append(f"    aip:metric aip:Metric_{axiom.metric.split('/')[-1]} ;")
                if axiom.expression:
                    out.append(f"    aip:expression \"{axiom.expression}\" ;")
                if axiom.level:
                    out.append(f"    aip:alertLevel \"{axiom.level}\" ;")
                if axiom.action:
                    out.append(f"    aip:action \"{axiom.action}\" ;")
            out[-1] = out[-1].rstrip(" ;") + " ."
            out.append("")
        return out

    def _serialize_bindings(self) -> list[str]:
        out = []
        for binding in self.reg._bindings.values():
            local = binding.iri.split("/")[-1]
            out.append(f"aip:Dataset_{local} a aip:Dataset ;")
            out.append(f"    rdfs:label \"{binding.label}\"@zh ;")
            out.append(f"    aip:physicalTable \"{binding.table}\" ;")
            for miri in binding.metrics:
                out.append(f"    aip:hasMetric aip:Metric_{miri.split('/')[-1]} ;")
            out[-1] = out[-1].rstrip(" ;") + " ."
            out.append("")
        return out

    def write(self, path: str | Path) -> Path:
        p = Path(path)
        p.write_text(self.serialize(), encoding="utf-8")
        return p


class TurtleLoader:
    """从 Turtle 加载指标、公理、数据集绑定（轻量解析）."""

    METRIC_PATTERN = re.compile(
        r"aip:Metric_(\w+)\s+a\s+aip:Metric\s*;(.*?)(?=\naip:|\Z)", re.DOTALL
    )
    FORMULA_PATTERN = re.compile(r'aip:formula\s+"([^"]+)"')
    LABEL_PATTERN = re.compile(r'rdfs:label\s+"([^"]+)"@zh')

    def __init__(self, ttl_path: str | Path):
        self.ttl_path = Path(ttl_path)
        self.content = self.ttl_path.read_text(encoding="utf-8")

    def parse_metrics(self) -> list[dict]:
        metrics = []
        for m in self.METRIC_PATTERN.finditer(self.content):
            block = m.group(2)
            mid = m.group(1)
            formula_m = self.FORMULA_PATTERN.search(block)
            label_m = self.LABEL_PATTERN.search(block)
            metrics.append({
                "iri": f"aip:Metric/{mid}",
                "label": label_m.group(1) if label_m else mid,
                "formula": formula_m.group(1) if formula_m else "",
            })
        return metrics

    def validate_syntax(self) -> dict:
        """基础语法校验."""
        issues = []
        if "@prefix aip:" not in self.content:
            issues.append("缺少 aip 命名空间前缀")
        if "aip:Metric_" not in self.content and "aip:Customer" not in self.content:
            issues.append("未找到核心类定义")
        open_paren = self.content.count("(")
        close_paren = self.content.count(")")
        if open_paren != close_paren:
            issues.append("括号不匹配")
        return {"valid": len(issues) == 0, "issues": issues, "metric_count": len(self.parse_metrics())}
