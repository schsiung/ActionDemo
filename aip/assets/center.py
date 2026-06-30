"""资产沉淀中心 - 模板、分析路径与参考样例."""

from __future__ import annotations

from datetime import datetime
from typing import Any


class AssetCenter:
    """沉淀常用问数路径、报告框架与参考样例."""

    def __init__(self):
        self._favorites: list[dict[str, Any]] = []
        self._reference_cases: list[dict[str, Any]] = []
        self._templates_versions: dict[str, list[dict[str, Any]]] = {}

    def save_favorite_query(self, question: str, sql: str, tags: list[str] | None = None) -> dict[str, Any]:
        item = {
            "id": f"fav_{len(self._favorites)}",
            "question": question,
            "sql": sql,
            "tags": tags or [],
            "created_at": datetime.now().isoformat(),
        }
        self._favorites.append(item)
        return item

    def save_reference_case(self, title: str, content: dict[str, Any], score: float = 0.0) -> dict[str, Any]:
        item = {
            "id": f"ref_{len(self._reference_cases)}",
            "title": title,
            "content": content,
            "score": score,
            "created_at": datetime.now().isoformat(),
        }
        self._reference_cases.append(item)
        return item

    def publish_template_version(self, template_id: str, version: str, config: dict[str, Any]) -> dict[str, Any]:
        entry = {
            "version": version,
            "config": config,
            "published_at": datetime.now().isoformat(),
            "status": "published",
        }
        self._templates_versions.setdefault(template_id, []).append(entry)
        return entry

    def list_favorites(self) -> list[dict[str, Any]]:
        return self._favorites

    def list_reference_cases(self, min_score: float = 0.0) -> list[dict[str, Any]]:
        return [c for c in self._reference_cases if c["score"] >= min_score]

    def get_metrics(self) -> dict[str, Any]:
        return {
            "favorite_count": len(self._favorites),
            "reference_case_count": len(self._reference_cases),
            "template_count": len(self._templates_versions),
        }
