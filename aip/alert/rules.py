"""数据预警规则引擎 - 支持 YAML 规则与本体公理."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import yaml

from aip.ontology.registry import OntologyRegistry


class AlertEngine:
    """根据规则检测数据预警."""

    def __init__(self, rules_path: str | Path | None = None, ontology: OntologyRegistry | None = None):
        self.rules: list[dict[str, Any]] = []
        if rules_path:
            with open(rules_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
            self.rules = data.get("rules", [])
        if ontology:
            self._merge_ontology_alerts(ontology)

    def _merge_ontology_alerts(self, ontology: OntologyRegistry) -> None:
        for ax in ontology.get_alert_rules():
            if ax.metric:
                prop = ax.metric.split("/")[-1]
            elif ax.property:
                prop = ax.property
            else:
                continue
            rule_id = ax.id.replace("ax_", "ALERT_").upper()
            if any(r["id"] == rule_id for r in self.rules):
                continue
            cond = ax.expression or ""
            self.rules.append({
                "id": rule_id,
                "name": ax.label,
                "metric": prop,
                "condition": cond,
                "level": ax.level or "黄色",
                "action": ax.action or "",
                "notify": "客户经理",
                "iri": getattr(ax, "iri", None) or f"aip:AlertRule/{ax.id}",
            })

    def evaluate_row(self, row: dict[str, Any]) -> list[dict[str, Any]]:
        triggered = []
        for rule in self.rules:
            metric = rule.get("metric") or rule.get("property")
            if not metric or metric not in row:
                continue
            value = row[metric]
            condition = rule["condition"]
            if self._match(value, condition):
                triggered.append({
                    "rule_id": rule["id"],
                    "rule_iri": rule.get("iri", f"aip:AlertRule/{rule['id']}"),
                    "name": rule["name"],
                    "level": rule["level"],
                    "action": rule["action"],
                    "notify": rule.get("notify", ""),
                    "metric": metric,
                    "value": value,
                })
        return triggered

    def evaluate_dataset(self, rows: list[dict[str, Any]]) -> dict[str, Any]:
        all_alerts = []
        for row in rows:
            alerts = self.evaluate_row(row)
            for a in alerts:
                a["customer_id"] = row.get("customer_id", "")
                a["customer_name"] = row.get("customer_name", "")
                all_alerts.append(a)
        by_level: dict[str, int] = {}
        for a in all_alerts:
            by_level[a["level"]] = by_level.get(a["level"], 0) + 1
        return {"total": len(all_alerts), "by_level": by_level, "alerts": all_alerts}

    @staticmethod
    def _match(value: Any, condition: str) -> bool:
        condition = condition.strip()
        if not condition:
            return False
        if condition.startswith("<= "):
            return float(value) <= float(condition[3:])
        if condition.startswith(">= "):
            return float(value) >= float(condition[3:])
        if condition.startswith("> "):
            return float(value) > float(condition[2:])
        if condition.startswith("< "):
            return float(value) < float(condition[2:])
        if condition.startswith("in "):
            allowed = ast.literal_eval(condition[3:])
            return value in allowed
        return False
