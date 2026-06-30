"""报告模板资产定义."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class SectionType(str, Enum):
    AI_SUMMARY = "ai_summary"
    AI_ANALYSIS = "ai_analysis"
    DATA_TABLE = "data_table"
    CHART = "chart"
    ACTION_ITEMS = "action_items"
    METRIC_DEF = "metric_def"


class ReportSection(BaseModel):
    id: str
    title: str
    type: SectionType
    chart_slots: list[str] = Field(default_factory=list)
    variables: list[str] = Field(default_factory=list)


class ReportTemplate(BaseModel):
    id: str
    name: str
    type: str  # daily | weekly | marketing | risk
    audience: str
    sections: list[ReportSection] = Field(default_factory=list)
    output_formats: list[str] = Field(default_factory=lambda: ["html"])


# MVP 预置模板
DAILY_REPORT_TEMPLATE = ReportTemplate(
    id="daily_ops",
    name="经营日报",
    type="daily",
    audience="客户经理",
    sections=[
        ReportSection(id="overview", title="数据概览", type=SectionType.AI_SUMMARY),
        ReportSection(id="kpi", title="核心指标分析", type=SectionType.AI_ANALYSIS, chart_slots=["trend_line", "rank_bar"]),
        ReportSection(id="chart_insight", title="图表解读", type=SectionType.CHART, chart_slots=["trend_line"]),
        ReportSection(id="actions", title="关注事项与建议", type=SectionType.ACTION_ITEMS),
    ],
)

WEEKLY_REPORT_TEMPLATE = ReportTemplate(
    id="weekly_review",
    name="业务周报",
    type="weekly",
    audience="分支行领导",
    sections=[
        ReportSection(id="summary", title="本周摘要", type=SectionType.AI_SUMMARY),
        ReportSection(id="comparison", title="区域对比分析", type=SectionType.AI_ANALYSIS, chart_slots=["compare_bar"]),
        ReportSection(id="risk", title="风险信号", type=SectionType.DATA_TABLE),
        ReportSection(id="recommendations", title="下周建议", type=SectionType.ACTION_ITEMS),
    ],
)

MARKETING_TEMPLATE = ReportTemplate(
    id="marketing_onepager",
    name="行内营销一页纸",
    type="marketing",
    audience="客户经理",
    sections=[
        ReportSection(id="profile", title="客户画像摘要", type=SectionType.AI_SUMMARY, variables=["customer_name"]),
        ReportSection(id="talking_points", title="聊天谈资", type=SectionType.AI_ANALYSIS),
        ReportSection(id="products", title="产品推荐", type=SectionType.ACTION_ITEMS, variables=["product_line"]),
        ReportSection(id="contact", title="触达策略", type=SectionType.ACTION_ITEMS),
    ],
)

CUSTOMER_ONEPAGER_TEMPLATE = ReportTemplate(
    id="customer_onepager",
    name="对客营销一页纸",
    type="marketing",
    audience="客户",
    sections=[
        ReportSection(id="intro", title="产品推荐", type=SectionType.AI_SUMMARY, variables=["customer_name"]),
        ReportSection(id="products", title="产品介绍", type=SectionType.AI_ANALYSIS, chart_slots=["product_card"]),
        ReportSection(id="credit", title="预授信额度", type=SectionType.DATA_TABLE, variables=["pre_credit_amount"]),
        ReportSection(id="contact", title="客户经理联系方式", type=SectionType.ACTION_ITEMS),
    ],
)

LEADER_BRIEF_TEMPLATE = ReportTemplate(
    id="leader_brief",
    name="领导参阅",
    type="marketing",
    audience="分支行领导",
    sections=[
        ReportSection(id="cooperation", title="客户及集团合作情况", type=SectionType.AI_SUMMARY),
        ReportSection(id="intro", title="客户介绍", type=SectionType.AI_ANALYSIS),
        ReportSection(id="breakthrough", title="建议议题/突破点", type=SectionType.ACTION_ITEMS),
        ReportSection(id="executive", title="高管信息", type=SectionType.DATA_TABLE, variables=["avatar_slot"]),
    ],
)

PRODUCT_BROCHURE_TEMPLATE = ReportTemplate(
    id="product_brochure",
    name="产品推荐材料",
    type="marketing",
    audience="对客/触达",
    sections=[
        ReportSection(id="highlights", title="产品亮点", type=SectionType.AI_SUMMARY),
        ReportSection(id="charts", title="推荐产品图文", type=SectionType.CHART, chart_slots=["product_chart"]),
        ReportSection(id="cases", title="合作案例", type=SectionType.AI_ANALYSIS),
    ],
)

POST_LOAN_REPORT_TEMPLATE = ReportTemplate(
    id="post_loan_report",
    name="贷后检查报告",
    type="risk",
    audience="客户经理",
    sections=[
        ReportSection(id="overview", title="客户基本情况", type=SectionType.AI_SUMMARY, variables=["customer_name", "check_type"]),
        ReportSection(id="signals", title="预警信号", type=SectionType.DATA_TABLE),
        ReportSection(id="analysis", title="指标分析", type=SectionType.AI_ANALYSIS, chart_slots=["flow_trend"]),
        ReportSection(id="actions", title="处置建议", type=SectionType.ACTION_ITEMS),
        ReportSection(id="metric_def", title="口径说明", type=SectionType.METRIC_DEF),
    ],
)

TEMPLATES: dict[str, ReportTemplate] = {
    "daily_ops": DAILY_REPORT_TEMPLATE,
    "weekly_review": WEEKLY_REPORT_TEMPLATE,
    "marketing_onepager": MARKETING_TEMPLATE,
    "customer_onepager": CUSTOMER_ONEPAGER_TEMPLATE,
    "leader_brief": LEADER_BRIEF_TEMPLATE,
    "product_brochure": PRODUCT_BROCHURE_TEMPLATE,
    "post_loan_report": POST_LOAN_REPORT_TEMPLATE,
}


def get_template(template_id: str) -> ReportTemplate | None:
    return TEMPLATES.get(template_id)
