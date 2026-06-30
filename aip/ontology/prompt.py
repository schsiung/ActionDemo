"""语义 DDL Prompt 构建器 - 注入 QueryAgent / Text2SQL."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from aip.ontology.registry import OntologyRegistry

PROMPTS_DIR = Path(__file__).parent.parent / "agents" / "prompts"


class SemanticDDLPromptBuilder:
    """从本体注册中心构建 Text2SQL / 问数 Prompt."""

    def __init__(self, ontology: OntologyRegistry, prompts_path: str | Path | None = None):
        self.ontology = ontology
        self.prompts_path = Path(prompts_path) if prompts_path else PROMPTS_DIR / "query_text2sql.yaml"
        self._templates: dict[str, Any] = {}
        if self.prompts_path.exists():
            with open(self.prompts_path, encoding="utf-8") as f:
                self._templates = yaml.safe_load(f) or {}

    def build_semantic_ddl(self, dataset_iri: str) -> str:
        """完整语义 DDL：数据集 + 指标 + 维度 + 公理约束."""
        base = self.ontology.semantic_ddl(dataset_iri)
        axioms = self._format_axioms()
        restrictions = self._format_restrictions()
        return f"{base}\n\nBusiness Axioms:\n{axioms}\n\nQuery Restrictions:\n{restrictions}"

    def _format_axioms(self) -> str:
        lines = []
        for ax in self.ontology.get_axioms():
            if ax.type == "alert":
                lines.append(f"  - [{ax.id}] {ax.label}: {ax.expression or ''} → {ax.level} → {ax.action}")
            elif ax.type == "restriction":
                cond = ax.condition or {}
                lines.append(f"  - [{ax.id}] {ax.label}: {cond}")
        return "\n".join(lines) if lines else "  (none)"

    def _format_restrictions(self) -> str:
        return self._templates.get("restrictions", "  - 仅 SELECT，禁止 DDL/DML\n  - 必须有 WHERE 权限过滤")

    def build_system_prompt(self, dataset_iri: str) -> str:
        tpl = self._templates.get("system_template", "")
        return tpl.format(
            ontology_version=self.ontology.version,
            semantic_ddl=self.build_semantic_ddl(dataset_iri),
            namespace=self.ontology._core.namespace if self.ontology._core else "",
        )

    def build_user_prompt(self, question: str, conversation_summary: str = "") -> str:
        tpl = self._templates.get("user_template", "用户问题：{question}")
        return tpl.format(question=question, conversation_summary=conversation_summary or "（首轮对话）")

    def build_full_prompt(self, dataset_iri: str, question: str, conversation_summary: str = "") -> dict[str, str]:
        return {
            "system": self.build_system_prompt(dataset_iri),
            "user": self.build_user_prompt(question, conversation_summary),
            "semantic_ddl": self.build_semantic_ddl(dataset_iri),
            "ontology_version": self.ontology.version,
        }
