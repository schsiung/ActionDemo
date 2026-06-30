"""AIP MVP 端到端演示."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from aip.agents.deep_research_agent import DeepResearchAgent
from aip.agents.query_agent import QueryAgent
from aip.assets.center import AssetCenter
from aip.data_prep.dataset_registry import DataAgentProfile, Dataset, DatasetRegistry
from aip.data_prep.script_workbench import ScriptWorkbench
from aip.data_prep.session_upload import SessionUploadService
from aip.report.composer import ReportComposer
from aip.semantic.model import load_semantic_model
from aip.trust.layer import TrustLayer
from aip.visualization.dashboard import DashboardGenerator

DEMO_DIR = Path(__file__).parent
DATA_DIR = DEMO_DIR / "data"
OUTPUT_DIR = Path("output")


def _header(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def _print_json(data: dict, indent: int = 2) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=indent, default=str))


def setup() -> tuple[DatasetRegistry, QueryAgent, DeepResearchAgent, AssetCenter]:
    """初始化数据集、语义模型与 Agent."""
    registry = DatasetRegistry()
    csv_path = DATA_DIR / "sample_customers.csv"
    semantic_path = DATA_DIR / "semantic_model.yaml"

    dataset = Dataset(
        id="ds_customer_credit",
        name="客户授信主题数据集",
        source_type="table",
        table_name="customer_credit",
        profile=DataAgentProfile(vectorized=True, update_mode="full"),
    )
    registry.register_csv(dataset, csv_path)
    semantic = load_semantic_model(semantic_path)

    query_agent = QueryAgent(registry, semantic, dataset.table_name)
    deep_agent = DeepResearchAgent(registry, semantic, dataset.table_name)
    assets = AssetCenter()

    return registry, query_agent, deep_agent, assets


def demo_data_prep(registry: DatasetRegistry) -> None:
    _header("0.1 数据集接入与配置")
    for ds in registry.list_datasets():
        print(f"  数据集: {ds.name} ({ds.id})")
        print(f"    行数: {ds.metadata.get('row_count')}, 列: {ds.metadata.get('columns')}")
        print(f"    DataAgent: 向量化={ds.profile.vectorized}, 更新模式={ds.profile.update_mode}")

    _header("0.1 会话文件上传 (模拟)")
    upload_service = SessionUploadService(registry, session_id="demo_session")
    result = upload_service.parse_file(DATA_DIR / "sample_customers.csv")
    _print_json(result)

    _header("0.3 分析脚本 Workbench")
    workbench = ScriptWorkbench(registry)
    sql_result = workbench.execute_sql(
        "SELECT industry, COUNT(*) AS cnt, AVG(risk_score) AS avg_risk "
        "FROM customer_credit GROUP BY industry ORDER BY cnt DESC"
    )
    print(f"  SQL 执行: {'成功' if sql_result['success'] else '失败'}")
    print(f"  返回 {sql_result['row_count']} 行")


def demo_query(query_agent: QueryAgent) -> None:
    _header("1.1 智能问数")
    questions = [
        "各机构授信余额排名",
        "授信余额口径是什么",
        "推荐相关指标",
    ]
    for q in questions:
        print(f"\n  Q: {q}")
        result = query_agent.ask(q)
        print(f"  类型: {result.get('type')}")
        if result.get("conclusion"):
            print(f"  结论: {result['conclusion']['text']}")
        if result.get("result"):
            print(f"  数据: {result['result']['row_count']} 行")

    _header("1.2 多轮追问")
    print("  Q1: 各机构授信余额")
    r1 = query_agent.ask("各机构授信余额")
    print(f"  → {r1.get('result', {}).get('row_count', 0)} 行")
    print("  Q2: 按行业分布")
    r2 = query_agent.ask("按行业分布")
    print(f"  → {r2.get('result', {}).get('row_count', 0)} 行")
    print(f"  推荐追问: {r2.get('follow_up_suggestions', [])}")


def demo_insights(deep_agent: DeepResearchAgent) -> dict:
    _header("5.1 分析任务规划 + 5.2 综合洞察")
    result = deep_agent.execute("对公客户风险全景分析")
    print("  洞察要点:")
    for insight in result.get("insights", []):
        print(f"    • {insight}")

    _header("5.3 指标波动归因")
    attr = deep_agent.attribute("risk_score", "industry")
    print(f"  解读: {attr['interpretation']}")
    for factor in attr["top_factors"][:3]:
        print(f"    - {factor.get('dimension')}: 贡献 {factor.get('contribution_pct')}%")

    return result


def demo_dashboard(deep_agent: DeepResearchAgent) -> str:
    _header("2.1 HTML 可交互看板生成")
    comparison = deep_agent.compare.by_dimension("region", "credit_balance")
    summary = deep_agent.registry.execute_sql(
        "SELECT COUNT(*) AS cnt, SUM(credit_balance) AS total, AVG(risk_score) AS avg_risk FROM customer_credit"
    ).to_dict(orient="records")[0]

    generator = DashboardGenerator(OUTPUT_DIR / "dashboards")
    path = generator.generate({
        "title": "对公客户风险监控看板",
        "subtitle": "AIP MVP 演示",
        "report_period": datetime.now().strftime("%Y-%m"),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "filters": [
            {"label": "区域", "options": ["全部", "华东", "华南", "华北", "华中", "西南"], "default": "全部"},
            {"label": "报告期", "options": ["2025-06", "2025-05", "2025-04"], "default": "2025-06"},
        ],
        "kpis": [
            {"label": "客户总数", "value": f"{summary['cnt']} 户"},
            {"label": "授信余额", "value": f"{summary['total']:,.0f} 万"},
            {"label": "平均风险分", "value": f"{summary['avg_risk']:.1f}", "delta": "较上月 +2.3", "delta_direction": "up"},
            {"label": "高风险客户", "value": "6 户", "delta": "需关注", "delta_direction": "up"},
        ],
        "charts": [
            {"title": "区域授信余额对比", "type": "bar", "data": comparison["rows"]},
            {"title": "行业风险分布", "type": "bar", "data": deep_agent.attribution.dimension_attribution("risk_score", "industry")["top_factors"]},
        ],
        "insight": comparison.get("interpretation", ""),
        "filename": "risk_dashboard.html",
    })
    print(f"  看板已生成: {path}")
    return path


def demo_report(deep_result: dict) -> str:
    _header("4. 报告生成 (周报模板)")
    composer = ReportComposer(OUTPUT_DIR / "reports")
    deep_result["question"] = "对公客户风险全景分析"
    deep_result["actions"] = [
        "对 6 户高风险客户启动贷后回访",
        "关注房地产、钢铁行业风险集中度",
        "核实西南区域授信增速异常原因",
    ]
    report = composer.compose(
        template_id="weekly_review",
        data=deep_result,
        variables={"report_period": "2025-W26", "org_name": "华东分行"},
    )
    print(f"  报告已生成: {report['output_path']}")
    print(f"  质检: {report['quality_check']['message']}")
    return report["output_path"]


def demo_trust(query_agent: QueryAgent, deep_agent: DeepResearchAgent) -> None:
    _header("7. 可信层 - 证据引用与过程回溯")
    trust = TrustLayer()
    trace_info = trust.trace_summary(deep_agent.trace)
    print(f"  Trace ID: {trace_info['trace_id']}")
    print(f"  步骤数: {trace_info['step_count']}")
    for step in trace_info["steps"]:
        print(f"    [{step['agent']}] {step['action']}: {step['output']}")


def demo_assets(assets: AssetCenter, query_agent: QueryAgent) -> None:
    _header("8. 资产沉淀")
    if query_agent.context.last_sql:
        fav = assets.save_favorite_query(
            "各机构授信余额排名",
            query_agent.context.last_sql,
            tags=["授信", "区域"],
        )
        print(f"  收藏问数: {fav['question']}")
    ref = assets.save_reference_case(
        "高风险客户筛查参考",
        {"pattern": "risk_score >= 70", "action": "贷后回访"},
        score=4.5,
    )
    print(f"  参考样例: {ref['title']} (评分 {ref['score']})")
    assets.publish_template_version("weekly_review", "v1.0.0", {"sections": 4})
    print(f"  运营指标: {assets.get_metrics()}")


def main() -> None:
    print("\n🚀 AIP 智能分析平台 MVP Demo")
    print(f"   时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    registry, query_agent, deep_agent, assets = setup()

    demo_data_prep(registry)
    demo_query(query_agent)
    deep_result = demo_insights(deep_agent)
    dashboard_path = demo_dashboard(deep_agent)
    report_path = demo_report(deep_result)
    demo_trust(query_agent, deep_agent)
    demo_assets(assets, query_agent)

    _header("Demo 完成")
    print(f"  📊 看板: {dashboard_path}")
    print(f"  📄 报告: {report_path}")
    print(f"  📁 输出目录: {OUTPUT_DIR.resolve()}")
    print("\n  运行 API 服务: python -m demo.api")
    print("  运行测试: pytest tests/\n")


if __name__ == "__main__":
    main()
