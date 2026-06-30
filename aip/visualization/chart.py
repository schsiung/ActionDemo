"""图表生成与解读 - 支持5种图表类型."""

from __future__ import annotations

from typing import Any

import plotly.express as px
import plotly.graph_objects as go

from aip.models import ChartSpec, ChartType


class ChartRenderer:
    """根据查询结果生成可视化图表 HTML."""

    @staticmethod
    def render(spec: ChartSpec) -> str:
        chart_type = spec.chart_type
        data = spec.data
        if not data:
            return "<p>无数据</p>"

        if chart_type == ChartType.LINE:
            fig = px.line(data, x=spec.x_field, y=spec.y_field, title=spec.title)
        elif chart_type == ChartType.BAR:
            fig = px.bar(data, x=spec.x_field or list(data[0].keys())[0], y=spec.y_field or list(data[0].keys())[1], title=spec.title)
        elif chart_type == ChartType.RANK:
            x = spec.x_field or list(data[0].keys())[0]
            y = spec.y_field or list(data[0].keys())[1]
            fig = px.bar(data, x=y, y=x, orientation="h", title=spec.title)
        elif chart_type == ChartType.FUNNEL:
            fig = go.Figure(go.Funnel(y=[r.get(spec.x_field or "stage", "") for r in data],
                                      x=[r.get(spec.y_field or "value", 0) for r in data]))
            fig.update_layout(title=spec.title)
        elif chart_type == ChartType.HEATMAP:
            import pandas as pd
            df = pd.DataFrame(data)
            fig = px.density_heatmap(df, x=spec.x_field, y=spec.y_field, title=spec.title)
        else:
            fig = px.bar(data, title=spec.title)

        return fig.to_html(full_html=False, include_plotlyjs="cdn")

    @staticmethod
    def interpret(spec: ChartSpec) -> str:
        """图表解读 - MVP 规则化描述."""
        if not spec.data:
            return "图表无数据，无法解读。"

        chart_type = spec.chart_type
        if chart_type == ChartType.LINE:
            return f"折线图「{spec.title}」展示时序变化趋势，关注拐点与波动幅度。"
        if chart_type == ChartType.RANK:
            top = spec.data[0]
            key = spec.x_field or list(top.keys())[0]
            val_key = spec.y_field or list(top.keys())[1]
            return f"排行榜显示 {top.get(key)} 位居第一（{top.get(val_key)}），头部集中度需关注。"
        if chart_type == ChartType.BAR:
            return f"柱状图「{spec.title}」展示分组对比，可识别结构差异与极值。"
        if chart_type == ChartType.FUNNEL:
            return f"漏斗图「{spec.title}」展示阶段转化，关注转化率骤降环节。"
        if chart_type == ChartType.HEATMAP:
            return f"热力图「{spec.title}」展示二维分布密度，识别高密区域。"
        return f"图表「{spec.title}」已生成，请结合业务口径解读。"


class ChartPlanner:
    """根据分析目的选择图表类型."""

    @staticmethod
    def from_query_result(rows: list[dict[str, Any]], chart_type: str, title: str = "分析图表") -> ChartSpec:
        ct = ChartType(chart_type)
        keys = list(rows[0].keys()) if rows else []
        x_field = keys[0] if keys else None
        y_field = keys[1] if len(keys) > 1 else None
        return ChartSpec(chart_type=ct, title=title, x_field=x_field, y_field=y_field, data=rows)
