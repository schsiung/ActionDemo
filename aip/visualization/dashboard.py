"""可交互 HTML 看板生成."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jinja2 import Template

from aip.visualization.chart import ChartPlanner, ChartRenderer

DASHBOARD_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{ title }}</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: #f5f7fa; color: #1a1a2e; }
    .header { background: linear-gradient(135deg, #1e3a5f, #2d5a87); color: white; padding: 24px 32px; }
    .header h1 { font-size: 24px; margin-bottom: 8px; }
    .header p { opacity: 0.85; font-size: 14px; }
    .filters { background: white; padding: 16px 32px; display: flex; gap: 16px; border-bottom: 1px solid #e8ecf0; flex-wrap: wrap; }
    .filter-group label { font-size: 12px; color: #666; display: block; margin-bottom: 4px; }
    .filter-group select { padding: 6px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; }
    .kpi-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; padding: 24px 32px; }
    .kpi-card { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
    .kpi-card .label { font-size: 13px; color: #666; margin-bottom: 8px; }
    .kpi-card .value { font-size: 28px; font-weight: 700; color: #1e3a5f; }
    .kpi-card .delta { font-size: 13px; margin-top: 4px; }
    .delta.up { color: #e74c3c; }
    .delta.down { color: #27ae60; }
    .charts { display: grid; grid-template-columns: repeat(auto-fit, minmax(450px, 1fr)); gap: 20px; padding: 0 32px 32px; }
    .chart-card { background: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.06); }
    .chart-card h3 { font-size: 16px; margin-bottom: 12px; color: #333; }
    .insight { background: #fff8e1; border-left: 4px solid #f39c12; padding: 16px 32px; margin: 0 32px 24px; border-radius: 0 8px 8px 0; }
    .insight h3 { font-size: 14px; color: #e67e22; margin-bottom: 8px; }
    .footer { text-align: center; padding: 16px; color: #999; font-size: 12px; }
  </style>
</head>
<body>
  <div class="header">
    <h1>{{ title }}</h1>
    <p>{{ subtitle }} | 报告期: {{ report_period }} | 生成时间: {{ generated_at }}</p>
  </div>

  <div class="filters">
    {% for f in filters %}
    <div class="filter-group">
      <label>{{ f.label }}</label>
      <select onchange="filterChanged(this)">
        {% for opt in f.options %}
        <option value="{{ opt }}" {% if opt == f.default %}selected{% endif %}>{{ opt }}</option>
        {% endfor %}
      </select>
    </div>
    {% endfor %}
  </div>

  <div class="kpi-row">
    {% for kpi in kpis %}
    <div class="kpi-card">
      <div class="label">{{ kpi.label }}</div>
      <div class="value">{{ kpi.value }}</div>
      {% if kpi.delta %}
      <div class="delta {{ kpi.delta_direction }}">{{ kpi.delta }}</div>
      {% endif %}
    </div>
    {% endfor %}
  </div>

  {% if insight %}
  <div class="insight">
    <h3>AI 解读</h3>
    <p>{{ insight }}</p>
  </div>
  {% endif %}

  <div class="charts">
    {% for chart in charts %}
    <div class="chart-card">
      <h3>{{ chart.title }}</h3>
      {{ chart.html | safe }}
    </div>
    {% endfor %}
  </div>

  <div class="footer">AIP 智能分析平台 MVP | 数据仅供参考</div>

  <script>
    function filterChanged(el) {
      console.log('筛选变更:', el.previousElementSibling.textContent, el.value);
      // MVP: 前端筛选联动占位，生产环境对接 API 刷新数据
    }
  </script>
</body>
</html>
"""


class DashboardGenerator:
    """自动生成可交互 HTML 看板."""

    def __init__(self, output_dir: str | Path = "output/dashboards"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, config: dict[str, Any]) -> str:
        charts_html = []
        for chart_cfg in config.get("charts", []):
            spec = ChartPlanner.from_query_result(
                chart_cfg["data"],
                chart_cfg.get("type", "bar"),
                chart_cfg.get("title", "图表"),
            )
            charts_html.append({
                "title": chart_cfg.get("title", "图表"),
                "html": ChartRenderer.render(spec),
            })

        template = Template(DASHBOARD_TEMPLATE)
        html = template.render(
            title=config.get("title", "分析看板"),
            subtitle=config.get("subtitle", ""),
            report_period=config.get("report_period", "当期"),
            generated_at=config.get("generated_at", ""),
            filters=config.get("filters", []),
            kpis=config.get("kpis", []),
            charts=charts_html,
            insight=config.get("insight", ""),
        )

        filename = config.get("filename", "dashboard.html")
        output_path = self.output_dir / filename
        output_path.write_text(html, encoding="utf-8")
        return str(output_path)
