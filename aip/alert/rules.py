"""数据预警规则引擎."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class AlertEngine:
  """根据规则检测数据预警."""

  def __init__(self, rules_path: str | Path):
    with open(rules_path, encoding="utf-8") as f:
      data = yaml.safe_load(f)
    self.rules = data.get("rules", [])

  def evaluate_row(self, row: dict[str, Any]) -> list[dict[str, Any]]:
    triggered = []
    for rule in self.rules:
      metric = rule["metric"]
      if metric not in row:
        continue
      value = row[metric]
      condition = rule["condition"]
      if self._match(value, condition):
        triggered.append({
          "rule_id": rule["id"],
          "name": rule["name"],
          "level": rule["level"],
          "action": rule["action"],
          "notify": rule["notify"],
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
    import ast
    condition = condition.strip()
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
