"""报告编排与生成."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from jinja2 import Template

from aip.models import Conclusion
from aip.report.templates import ReportTemplate, SectionType, get_template
from aip.trust.layer import TrustLayer
from aip.visualization.chart import ChartPlanner, ChartRenderer

REPORT_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <title>{{ title }}</title>
  <style>
    body { font-family: "Noto Sans SC", sans-serif; max-width: 900px; margin: 0 auto; padding: 40px 24px; color: #333; line-height: 1.8; }
    h1 { color: #1e3a5f; border-bottom: 3px solid #2d5a87; padding-bottom: 12px; }
    h2 { color: #2d5a87; margin-top: 32px; border-left: 4px solid #f39c12; padding-left: 12px; }
    .meta { color: #888; font-size: 14px; margin-bottom: 24px; }
    .section { margin-bottom: 24px; }
    .evidence { background: #f0f4f8; padding: 12px 16px; border-radius: 8px; font-size: 13px; margin-top: 12px; }
    .evidence li { margin: 4px 0; }
    .action-item { background: #e8f5e9; padding: 8px 16px; border-radius: 6px; margin: 8px 0; }
    .limitation { color: #e67e22; font-size: 13px; }
    .chart-container { margin: 16px 0; }
    table { width: 100%; border-collapse: collapse; margin: 12px 0; }
    th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
    th { background: #f5f7fa; }
  </style>
</head>
<body>
  <h1>{{ title }}</h1>
  <div class="meta">
    模板: {{ template_name }} | 受众: {{ audience }} |
    报告期: {{ report_period }} | 生成时间: {{ generated_at }}
  </div>

  {% for section in sections %}
  <div class="section">
    <h2>{{ section.title }}</h2>
    <div>{{ section.content }}</div>
    {% if section.chart_html %}
    <div class="chart-container">{{ section.chart_html | safe }}</div>
    {% endif %}
    {% if section.table %}
    <table>
      <tr>{% for col in section.table.columns %}<th>{{ col }}</th>{% endfor %}</tr>
      {% for row in section.table.rows %}
      <tr>{% for col in section.table.columns %}<td>{{ row[col] }}</td>{% endfor %}</tr>
      {% endfor %}
    </table>
    {% endif %}
    {% if section.actions %}
    {% for action in section.actions %}
    <div class="action-item">{{ action }}</div>
    {% endfor %}
    {% endif %}
  </div>
  {% endfor %}

  {% if evidence %}
  <div class="evidence">
    <strong>证据引用</strong>
    <ul>
    {% for e in evidence %}
      <li>[{{ e.type }}] {{ e.source }} - {{ e.detail }}</li>
    {% endfor %}
    </ul>
  </div>
  {% endif %}

  {% if limitations %}
  <p class="limitation">局限性: {{ limitations | join('；') }}</p>
  {% endif %}
</body>
</html>
"""


class ReportComposer:
    """基于模板编排并生成完整报告."""

    def __init__(self, output_dir: str | Path = "output/reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.trust = TrustLayer()

    def plan_outline(self, question: str, template: ReportTemplate) -> dict[str, Any]:
        """单次报告大纲规划."""
        outline = []
        for section in template.sections:
            outline.append({
                "section_id": section.id,
                "title": section.title,
                "type": section.type.value,
                "planned_content": f"围绕「{question}」生成 {section.title}",
                "chart_slots": section.chart_slots,
            })
        return {"question": question, "template_id": template.id, "outline": outline}

    def compose(
        self,
        template_id: str,
        data: dict[str, Any],
        variables: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        template = get_template(template_id)
        if not template:
            raise ValueError(f"模板不存在: {template_id}")

        variables = variables or {}
        report_period = variables.get("report_period", datetime.now().strftime("%Y-%m-%d"))
        sections_output = []

        for section in template.sections:
            sec_data: dict[str, Any] = {"title": section.title, "content": ""}

            if section.type == SectionType.AI_SUMMARY:
                sec_data["content"] = data.get("insights", ["暂无摘要"])[0] if data.get("insights") else "暂无数据"
            elif section.type == SectionType.AI_ANALYSIS:
                sec_data["content"] = data.get("comparison", {}).get("interpretation", "暂无分析")
                chart_data = data.get("comparison", {}).get("rows", [])
                if chart_data:
                    spec = ChartPlanner.from_query_result(chart_data, "bar", section.title)
                    sec_data["chart_html"] = ChartRenderer.render(spec)
            elif section.type == SectionType.DATA_TABLE:
                risk_data = data.get("risk_signals", [])
                if risk_data:
                    sec_data["table"] = {
                        "columns": list(risk_data[0].keys()),
                        "rows": risk_data,
                    }
                    sec_data["content"] = f"共 {len(risk_data)} 条风险信号"
            elif section.type == SectionType.ACTION_ITEMS:
                actions = data.get("actions", [
                    "关注高风险客户，安排贷后回访",
                    "对授信余额下降客户进行原因排查",
                    "更新客户风险评级",
                ])
                sec_data["actions"] = actions
            elif section.type == SectionType.CHART:
                sec_data["content"] = data.get("chart_interpretation", "图表解读待生成")

            sections_output.append(sec_data)

        conclusion = data.get("conclusion", {})
        if isinstance(conclusion, dict):
            conclusion_obj = Conclusion(**conclusion)
        else:
            conclusion_obj = Conclusion(text=str(conclusion))

        qc = self.trust.quality_check(conclusion_obj, data)
        validated = self.trust.validate_conclusion(conclusion_obj)

        title = f"{template.name} - {variables.get('org_name', '全辖')}"
        template_obj = Template(REPORT_HTML_TEMPLATE)
        html = template_obj.render(
            title=title,
            template_name=template.name,
            audience=template.audience,
            report_period=report_period,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            sections=sections_output,
            evidence=[e.model_dump() for e in validated.evidence],
            limitations=validated.limitations + ([qc["message"]] if not qc["passed"] else []),
        )

        filename = f"{template_id}_{report_period}.html"
        output_path = self.output_dir / filename
        output_path.write_text(html, encoding="utf-8")

        return {
            "template_id": template_id,
            "output_path": str(output_path),
            "outline": self.plan_outline(data.get("question", ""), template),
            "quality_check": qc,
            "conclusion": validated.model_dump(),
        }
