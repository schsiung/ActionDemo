"""多维对比分析引擎."""

from __future__ import annotations

from typing import Any

from aip.data_prep.dataset_registry import DatasetRegistry


class CompareEngine:
    """横向/纵向对比：差异幅度与相对排位."""

    def __init__(self, registry: DatasetRegistry, table_name: str):
        self.registry = registry
        self.table_name = table_name

    def by_dimension(self, dimension_field: str, metric_field: str) -> dict[str, Any]:
        sql = f"""
            SELECT {dimension_field} AS dimension,
                   SUM({metric_field}) AS total_value,
                   AVG({metric_field}) AS avg_value,
                   COUNT(*) AS count
            FROM {self.table_name}
            GROUP BY {dimension_field}
            ORDER BY total_value DESC
        """
        df = self.registry.execute_sql(sql)
        rows = df.to_dict(orient="records")

        if not rows:
            return {"type": "compare", "rows": [], "benchmark": None, "interpretation": "无数据"}

        benchmark = sum(r["total_value"] for r in rows) / len(rows)
        for i, r in enumerate(rows):
            r["rank"] = i + 1
            r["vs_benchmark"] = "高于" if r["total_value"] > benchmark else "低于"
            r["diff_pct"] = round((r["total_value"] - benchmark) / benchmark * 100, 1) if benchmark else 0

        top = rows[0]
        interpretation = (
            f"{top['dimension']} 排名第 1，"
            f"指标值 {top['total_value']:,.0f}，"
            f"{top['vs_benchmark']}均值 {abs(top['diff_pct'])}%"
        )

        return {
            "type": "compare",
            "dimension_field": dimension_field,
            "metric_field": metric_field,
            "rows": rows,
            "benchmark": benchmark,
            "interpretation": interpretation,
        }
