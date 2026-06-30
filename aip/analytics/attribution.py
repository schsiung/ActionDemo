"""指标波动归因引擎."""

from __future__ import annotations

from typing import Any

from aip.data_prep.dataset_registry import DatasetRegistry


class AttributionEngine:
    """维度归因：量化各维值对指标波动的贡献."""

    def __init__(self, registry: DatasetRegistry, table_name: str):
        self.registry = registry
        self.table_name = table_name

    def dimension_attribution(self, metric_field: str, dimension_field: str, top_n: int = 3) -> dict[str, Any]:
        sql = f"""
            WITH stats AS (
                SELECT {dimension_field} AS dimension,
                       AVG({metric_field}) AS avg_metric,
                       COUNT(*) AS sample_count
                FROM {self.table_name}
                GROUP BY {dimension_field}
            ),
            overall AS (
                SELECT AVG({metric_field}) AS global_mean FROM {self.table_name}
            )
            SELECT s.dimension,
                   s.avg_metric,
                   s.sample_count,
                   s.avg_metric - o.global_mean AS diff_from_mean
            FROM stats s, overall o
            ORDER BY ABS(s.avg_metric - o.global_mean) DESC
            LIMIT {top_n}
        """
        df = self.registry.execute_sql(sql)
        rows = df.to_dict(orient="records")

        total_abs_diff = sum(abs(r.get("diff_from_mean", 0) or 0) for r in rows) or 1
        for r in rows:
            r["contribution_pct"] = round(abs(r.get("diff_from_mean", 0) or 0) / total_abs_diff * 100, 1)

        drivers = []
        for r in rows:
            direction = "高于" if (r.get("diff_from_mean") or 0) > 0 else "低于"
            drivers.append(
                f"{r.get('dimension')} {direction}均值，贡献约 {r.get('contribution_pct')}%"
            )

        return {
            "type": "attribution",
            "metric_field": metric_field,
            "dimension_field": dimension_field,
            "top_factors": rows,
            "interpretation": "；".join(drivers) + "。",
        }
