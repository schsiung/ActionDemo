"""全场景演示执行器 - 按 scenario_registry 逐条执行."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from aip.models import Conclusion, ConfidenceLevel, EvidenceRef
from aip.report.composer import ReportComposer
from aip.report.templates import TEMPLATES, get_template
from aip.trust.layer import TrustLayer
from aip.visualization.chart import ChartPlanner, ChartRenderer
from aip.visualization.dashboard import DashboardGenerator
from demo.scenarios.context import OUTPUT_DIR, SCENARIO_DIR, ScenarioContext

# 演示动作 → 处理方法映射
ACTION_HANDLERS = {}


def _register(name: str):
    def decorator(fn):
        ACTION_HANDLERS[name] = fn
        return fn
    return decorator


class ScenarioExecutor:
    def __init__(self):
        self.ctx = ScenarioContext()
        self.trust = TrustLayer()
        self.results: list[dict[str, Any]] = []

    def run(self, scenario: dict) -> dict[str, Any]:
        action = scenario["demo_action"]
        handler = ACTION_HANDLERS.get(action)
        if not handler:
            result = {"status": "skipped", "reason": f"未实现动作: {action}"}
        else:
            try:
                output = handler(self, scenario)
                result = {"status": "ok", "output": output}
            except Exception as e:
                result = {"status": "error", "error": str(e)}

        record = {
            "id": scenario["id"],
            "capability": scenario["capability"],
            "group": scenario["group"],
            "business_scene": scenario["business_scene"],
            "priority": scenario.get("priority", ""),
            "expected_output": scenario.get("expected_output", ""),
            **result,
        }
        self.results.append(record)
        return record

    def run_all(self, scenarios: list[dict] | None = None) -> list[dict]:
        if scenarios is None:
            scenarios = self.ctx.load_registry()
        for s in scenarios:
            self.run(s)
        return self.results

    def run_by_id(self, scenario_id: str) -> dict | None:
        for s in self.ctx.load_registry():
            if s["id"] == scenario_id:
                return self.run(s)
        return None

    def run_by_group(self, group: str) -> list[dict]:
        scenarios = [s for s in self.ctx.load_registry() if s["group"] == group]
        return [self.run(s) for s in scenarios]


# ===================== 数据准备类 =====================

@_register("data_connect")
def _data_connect(ex: ScenarioExecutor, scenario: dict) -> dict:
    params = scenario["demo_params"]
    datasets = [{"id": d.id, "name": d.name, "rows": d.metadata.get("row_count")} for d in ex.ctx.registry.list_datasets()]
    upload = ex.ctx.upload_service("demo_01").parse_file(SCENARIO_DIR / params["upload_file"])
    return {"persistent_datasets": datasets[:3], "upload_result": upload}


@_register("semantic_config")
def _semantic_config(ex: ScenarioExecutor, scenario: dict) -> dict:
    params = scenario["demo_params"]
    semantic = ex.ctx.get_semantic(params["semantic_model"].replace(".yaml", ""))
    explanations = [semantic.explain_metric(m) for m in params["explain_metrics"] if semantic.get_metric(m)]
    benchmark = ex.ctx.query_table("industry_benchmark", "SELECT * FROM industry_benchmark LIMIT 5")
    return {"metrics": explanations, "benchmark_sample": benchmark}


@_register("script_workbench")
def _script_workbench(ex: ScenarioExecutor, scenario: dict) -> dict:
    wb = ex.ctx.workbench()
    result = wb.execute_sql(scenario["demo_params"]["sql"])
    return {"sql": result["sql"], "row_count": result["row_count"], "rows": result["rows"][:5]}


# ===================== 问数类 =====================

@_register("query_and_knowledge")
def _query_and_knowledge(ex: ScenarioExecutor, scenario: dict) -> dict:
    params = scenario["demo_params"]
    agent = ex.ctx.get_query_agent()
    data_results = []
    for q in params["data_questions"]:
        r = agent.ask(q)
        data_results.append({"question": q, "type": r.get("type"), "rows": r.get("result", {}).get("row_count", 0)})
    knowledge_results = [ex.ctx.knowledge.answer(q) for q in params["knowledge_questions"]]
    return {"data_query": data_results, "knowledge": knowledge_results}


@_register("multi_turn_query")
def _multi_turn_query(ex: ScenarioExecutor, scenario: dict) -> dict:
    agent = ex.ctx.get_query_agent()
    turns = []
    for q in scenario["demo_params"]["turns"]:
        r = agent.ask(q)
        turns.append({"question": q, "type": r.get("type"), "rows": r.get("result", {}).get("row_count", 0)})
    judicial = ex.ctx.query_table("judicial_signals", "SELECT * FROM judicial_signals LIMIT 5")
    return {"turns": turns, "judicial_detail": judicial, "follow_up": turns[-1].get("follow_up") if turns else []}


@_register("metric_explain")
def _metric_explain(ex: ScenarioExecutor, scenario: dict) -> dict:
    agent = ex.ctx.get_query_agent()
    return {"explanations": [agent.ask(q) for q in scenario["demo_params"]["questions"]]}


@_register("metric_recommend")
def _metric_recommend(ex: ScenarioExecutor, scenario: dict) -> dict:
    semantic = ex.ctx.get_semantic("semantic_marketing")
    return {
        "base_metric": scenario["demo_params"]["base_metric"],
        "recommendations": semantic.recommend_related("marketing_priority"),
        "customer_data": ex.ctx.query_table("marketing_whitelist", "SELECT * FROM marketing_whitelist WHERE customer_name LIKE '%华信%'"),
    }


# ===================== 看板类 =====================

@_register("dashboard_generate")
def _dashboard_generate(ex: ScenarioExecutor, scenario: dict) -> dict:
    params = scenario["demo_params"]
    warnings = ex.ctx.query_table("post_loan_monitoring", "SELECT * FROM post_loan_monitoring")
    by_level = {}
    for w in warnings:
        by_level[w["warning_level"]] = by_level.get(w["warning_level"], 0) + 1

    gen = DashboardGenerator(OUTPUT_DIR / "dashboards")
    path = gen.generate({
        "title": params["title"],
        "subtitle": "贷后巡检智能化提升",
        "report_period": "2025-06",
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "filters": [
            {"label": "预警等级", "options": ["全部", "红色", "橙色", "黄色", "绿色"], "default": "全部"},
            {"label": "区域", "options": ["全部", "华东", "华南", "西南", "华北"], "default": "全部"},
        ],
        "kpis": [
            {"label": "预警客户", "value": f"{len(warnings)} 户"},
            {"label": "红色预警", "value": f"{by_level.get('红色', 0)} 户", "delta": "需立即处置", "delta_direction": "up"},
            {"label": "橙色预警", "value": f"{by_level.get('橙色', 0)} 户"},
            {"label": "正常客户", "value": f"{by_level.get('绿色', 0)} 户"},
        ],
        "charts": [
            {"title": "预警等级分布", "type": "bar", "data": [{"level": k, "count": v} for k, v in by_level.items()]},
            {"title": "流水变动趋势", "type": "line", "data": ex.ctx.query_table("transaction_flow", "SELECT month, flow_yoy_pct FROM transaction_flow WHERE customer_name='天宇建筑工程'")},
        ],
        "insight": "红色预警客户需优先处置：天宇建筑流水骤降32.5%，鼎盛房地产存在大额交易与负面舆情。",
        "filename": "post_loan_dashboard.html",
    })
    return {"dashboard_path": path}


@_register("dashboard_interpret")
def _dashboard_interpret(ex: ScenarioExecutor, scenario: dict) -> dict:
    signals = ex.ctx.query_table("post_loan_monitoring", "SELECT * FROM post_loan_monitoring WHERE warning_level IN ('红色','橙色')")
    interpretations = []
    for s in signals:
        text = f"{s['customer_name']}：{s['warning_type']}，{s['warning_level']}预警。"
        if float(s.get("flow_change_pct", 0)) < -20:
            text += f" 流水下降{abs(float(s['flow_change_pct']))}%，偏离正常区间。"
        interpretations.append(text)
    return {"signals": signals, "interpretations": interpretations}


@_register("drill_down")
def _drill_down(ex: ScenarioExecutor, scenario: dict) -> dict:
    levels = {}
    levels["L1_汇总"] = ex.ctx.query_table("post_loan_monitoring", "SELECT warning_level, COUNT(*) AS cnt FROM post_loan_monitoring GROUP BY warning_level")
    levels["L2_客户"] = ex.ctx.query_table("post_loan_monitoring", "SELECT * FROM post_loan_monitoring WHERE warning_level='红色'")
    levels["L3_月度流水"] = ex.ctx.query_table("transaction_flow", "SELECT * FROM transaction_flow WHERE customer_name='天宇建筑工程'")
    levels["L4_行业对标"] = ex.ctx.query_table("industry_benchmark", "SELECT * FROM industry_benchmark WHERE industry='建筑'")
    attr = ex.ctx.query_table("transaction_flow",
        "SELECT month AS dimension, flow_yoy_pct AS avg_metric FROM transaction_flow WHERE customer_name='天宇建筑工程'")
    return {"drill_levels": levels, "attribution": {"top_factors": attr, "interpretation": "流水逐月恶化"}}


# ===================== 图表类 =====================

@_register("chart_design")
def _chart_design(ex: ScenarioExecutor, scenario: dict) -> dict:
    return {"designs": scenario["demo_params"]["purposes"]}


@_register("chart_generate")
def _chart_generate(ex: ScenarioExecutor, scenario: dict) -> dict:
    data = ex.ctx.query_table("customer_360", "SELECT region, SUM(credit_balance) AS total FROM customer_360 GROUP BY region")
    charts = {}
    for ct in scenario["demo_params"]["charts"]:
        spec = ChartPlanner.from_query_result(data, ct, f"授信余额-{ct}")
        charts[ct] = {"html_length": len(ChartRenderer.render(spec)), "preview": ChartRenderer.interpret(spec)}
    return {"charts": charts, "data_rows": len(data)}


@_register("chart_interpret")
def _chart_interpret(ex: ScenarioExecutor, scenario: dict) -> dict:
    customer = scenario["demo_params"]["customer"]
    flow = ex.ctx.query_table("transaction_flow", f"SELECT month, flow_yoy_pct FROM transaction_flow WHERE customer_name='{customer}'")
    spec = ChartPlanner.from_query_result(flow, "line", f"{customer}流水趋势")
    interpretation = ChartRenderer.interpret(spec)
    financial = ex.ctx.query_table("financial_reports", f"SELECT * FROM financial_reports WHERE customer_name='{customer}' AND report_year=2024")
    if financial:
        f = financial[0]
        interpretation += f" 财报：收入同比{f['revenue_yoy_pct']}%，{'触及' if f['revenue_yoy_pct'] <= -20 else '未触及'}关注阈值。"
    return {"customer": customer, "flow_data": flow, "interpretation": interpretation}


# ===================== 报告类 =====================

@_register("report_templates")
def _report_templates(ex: ScenarioExecutor, scenario: dict) -> dict:
    templates = []
    for tid in scenario["demo_params"]["templates"]:
        t = get_template(tid)
        if t:
            templates.append({
                "id": t.id, "name": t.name, "audience": t.audience,
                "sections": [{"id": s.id, "title": s.title, "type": s.type.value, "variables": s.variables} for s in t.sections],
            })
    return {"templates": templates}


@_register("report_outline")
def _report_outline(ex: ScenarioExecutor, scenario: dict) -> dict:
    deep = ex.ctx.get_deep_agent()
    plan = deep.plan(scenario["demo_params"]["question"])
    composer = ReportComposer(OUTPUT_DIR / "reports")
    outline = composer.plan_outline(scenario["demo_params"]["question"], get_template("post_loan_report"))
    return {"plan": plan, "outline": outline}


@_register("periodic_report")
def _periodic_report(ex: ScenarioExecutor, scenario: dict) -> dict:
    deep = ex.ctx.get_deep_agent()
    data = deep.execute("本周业务回顾")
    data["actions"] = ["跟进逾期客户催收", "完成贷后巡检", "推进授信方案"]
    composer = ReportComposer(OUTPUT_DIR / "reports")
    outputs = []
    for tid in scenario["demo_params"]["templates"]:
        r = composer.compose(tid, data, {"report_period": datetime.now().strftime("%Y-%m-%d")})
        outputs.append({"template": tid, "path": r["output_path"]})
    return {"reports": outputs}


@_register("variable_report")
def _variable_report(ex: ScenarioExecutor, scenario: dict) -> dict:
    composer = ReportComposer(OUTPUT_DIR / "reports")
    outputs = []
    for vars_set in scenario["demo_params"]["variables"]:
        signals = ex.ctx.query_table("post_loan_monitoring", f"SELECT * FROM post_loan_monitoring WHERE customer_name='{vars_set['customer_name']}'")
        data = {
            "insights": [f"{vars_set['customer_name']} 贷后{vars_set['check_type']}"],
            "risk_signals": signals,
            "comparison": {
                "rows": ex.ctx.query_table("post_loan_monitoring", "SELECT warning_level AS dimension, flow_change_pct AS total_value FROM post_loan_monitoring"),
                "interpretation": f"{vars_set['customer_name']} 专项检查完成",
            },
            "actions": [f"由{vars_set['org_name']}安排核查"],
            "conclusion": {"text": "检查完成", "confidence": "high", "evidence": [{"type": "query", "source": "post_loan_monitoring", "detail": vars_set['customer_name']}], "limitations": []},
        }
        r = composer.compose(scenario["demo_params"]["template"], data, vars_set)
        outputs.append({"variables": vars_set, "path": r["output_path"]})
    return {"reports": outputs}


@_register("multi_audience_report")
def _multi_audience_report(ex: ScenarioExecutor, scenario: dict) -> dict:
    customer = scenario["demo_params"]["customer"]
    base = ex.ctx.query_table("marketing_whitelist", f"SELECT * FROM marketing_whitelist WHERE customer_name LIKE '%{customer[:2]}%'")
    versions = {}
    for ver in scenario["demo_params"]["versions"]:
        if ver == "管理版":
            versions[ver] = {"style": "结论先行", "content": f"{customer}：园区核心企业，建议优先营销科创e贷，预计额度3000万。"}
        elif ver == "执行版":
            versions[ver] = {"style": "动作清单", "content": ["预约下周拜访", "准备科创e贷方案", "收集高新技术企业证书"]}
        else:
            versions[ver] = {"style": "数据附录", "content": base}
    return {"customer": customer, "versions": versions}


@_register("full_report")
def _full_report(ex: ScenarioExecutor, scenario: dict) -> dict:
    deep = ex.ctx.get_deep_agent("customer_360")
    data = deep.execute("营销方案生成")
    whitelist = ex.ctx.query_table("marketing_whitelist", "SELECT * FROM marketing_whitelist ORDER BY marketing_priority LIMIT 3")
    data["insights"] = [f"推荐优先营销：{r['customer_name']}（优先级{r['marketing_priority']}）" for r in whitelist]
    data["actions"] = ["推荐科创e贷", "安排园区对接", "准备预授信方案"]
    composer = ReportComposer(OUTPUT_DIR / "reports")
    outputs = []
    for tid in scenario["demo_params"]["templates"]:
        r = composer.compose(tid, data, {"customer_name": "华信科技有限公司", "product_line": "科技贷款"})
        outputs.append({"template": tid, "path": r["output_path"]})
    return {"reports": outputs}


# ===================== 洞察类 =====================

@_register("task_planning")
def _task_planning(ex: ScenarioExecutor, scenario: dict) -> dict:
    deep = ex.ctx.get_deep_agent()
    question = "贷前风险筛查：名单导入→多源扫描→规则命中→画像→路径判断"
    plan = deep.plan(question)
    return {
        "workflow": scenario["demo_params"]["workflow"],
        "workflow_id": plan["workflow_id"],
        "node_count": len(plan["tasks"]),
        "execution_order": plan["execution_order"],
        "task_graph_id": plan["task_graph"]["@id"],
        "plan": plan,
    }


@_register("insight_synthesis")
def _insight_synthesis(ex: ScenarioExecutor, scenario: dict) -> dict:
    results = {}
    if "贷前风险画像" in scenario["demo_params"]["scenes"]:
        high_risk = ex.ctx.query_table("customer_360", "SELECT customer_name, risk_score, crr_level, legal_cases FROM customer_360 WHERE risk_score >= 70")
        results["风险画像"] = {
            "要点": [f"{r['customer_name']}：风险分{r['risk_score']}，CRR={r['crr_level']}，司法{r['legal_cases']}件" for r in high_risk],
            "建议路径": "需补充核查" if high_risk else "可继续营销",
        }
    if "营销商机排序" in scenario["demo_params"]["scenes"]:
        ranking = ex.ctx.query_table("marketing_whitelist", "SELECT customer_name, marketing_priority, supply_chain_score FROM marketing_whitelist ORDER BY marketing_priority")
        results["商机排序"] = [{"客户": r["customer_name"], "优先级": r["marketing_priority"], "产业链分": r["supply_chain_score"]} for r in ranking]
    return results


@_register("attribution")
def _attribution(ex: ScenarioExecutor, scenario: dict) -> dict:
    results = []
    for item in scenario["demo_params"]["metrics"]:
        if "customer" in item:
            data = ex.ctx.query_table("transaction_flow", f"SELECT month AS dimension, flow_yoy_pct AS avg_metric FROM transaction_flow WHERE customer_name='{item['customer']}'")
            results.append({"metric": item["metric"], "factors": data, "interpretation": f"{item['customer']}流水波动分析"})
        else:
            deep = ex.ctx.get_deep_agent()
            attr = deep.attribute(item.get("metric", "risk_score"), item.get("dimension", "industry"))
            results.append(attr)
    return {"attributions": results}


@_register("comparison")
def _comparison(ex: ScenarioExecutor, scenario: dict) -> dict:
    results = []
    for comp in scenario["demo_params"]["comparisons"]:
        if comp["type"] == "同业对标":
            bid = ex.ctx.query_table("bid_scoring", f"SELECT * FROM bid_scoring WHERE customer_name LIKE '%{comp['customer'][:2]}%'")
            results.append({"type": "同业对标", "data": bid, "interpretation": f"我方得分{bid[0]['our_score'] if bid else 'N/A'}，竞对{bid[0]['competitor_score'] if bid else 'N/A'}"})
        else:
            deep = ex.ctx.get_deep_agent()
            cmp = deep.compare.by_dimension(comp.get("dimension", "region"), "credit_balance")
            results.append(cmp)
    return {"comparisons": results}


# ===================== 预警建议类 =====================

@_register("alert_design")
def _alert_design(ex: ScenarioExecutor, scenario: dict) -> dict:
    all_alerts = []
    for ds_name in scenario["demo_params"]["evaluate_datasets"]:
        table = DATASET_MAP.get(ds_name, ("", ds_name, ""))[1]
        rows = ex.ctx.query_table(ds_name, f"SELECT * FROM {table}")
        result = ex.ctx.alert_engine.evaluate_dataset(rows)
        all_alerts.append({"dataset": ds_name, **result})
    return {"rules": [r["name"] for r in ex.ctx.alert_engine.rules], "evaluations": all_alerts}


@_register("suggestion_generate")
def _suggestion_generate(ex: ScenarioExecutor, scenario: dict) -> dict:
    suggestions = {}
    if "贷前筛查建议" in scenario["demo_params"]["scenes"]:
        high = ex.ctx.query_table("customer_360", "SELECT * FROM customer_360 WHERE risk_score >= 70 LIMIT 1")
        if high:
            c = high[0]
            suggestions["贷前筛查"] = [
                f"客户{c['customer_name']}：补充财务报表与流水",
                "核实司法案件进展",
                "限制纯信用类产品" if c["crr_level"] in ("D", "E") else "可继续营销但加强尽调",
            ]
    if "贷后处置建议" in scenario["demo_params"]["scenes"]:
        suggestions["贷后处置"] = ["安排现场核查", "压降授信额度", "加强监测频率"]
    if "营销触达建议" in scenario["demo_params"]["scenes"]:
        suggestions["营销触达"] = ["推荐科创e贷", "话题：园区政策补贴", "触达路径：园区管委会引荐"]
    return suggestions


# ===================== 可信类 =====================

@_register("quality_check")
def _quality_check(ex: ScenarioExecutor, scenario: dict) -> dict:
    deep = ex.ctx.get_deep_agent()
    data = deep.execute("质检测试")
    conclusion = Conclusion(**data["conclusion"])
    return ex.trust.quality_check(conclusion, data)


@_register("controlled_generation")
def _controlled_generation(ex: ScenarioExecutor, scenario: dict) -> dict:
    agent = ex.ctx.get_query_agent()
    cases = []
    for tc in scenario["demo_params"]["test_cases"]:
        r = agent.ask(tc["question"])
        conf = r.get("conclusion", {}).get("confidence", "unknown")
        cases.append({"question": tc["question"], "expect": tc["expect"], "actual_confidence": conf, "type": r.get("type")})
    return {"test_cases": cases}


@_register("evidence_citation")
def _evidence_citation(ex: ScenarioExecutor, scenario: dict) -> dict:
    agent = ex.ctx.get_query_agent()
    r = agent.ask("查询授信余额排名")
    return {"conclusion": r.get("conclusion"), "evidence_count": len(r.get("conclusion", {}).get("evidence", []))}


@_register("trace_back")
def _trace_back(ex: ScenarioExecutor, scenario: dict) -> dict:
    agent = ex.ctx.get_query_agent()
    agent.ask("各机构授信余额")
    agent.ask("按行业分布")
    deep = ex.ctx.get_deep_agent()
    deep.execute("追溯测试")
    return {
        "query_trace": ex.trust.trace_summary(agent.trace),
        "deep_trace": ex.trust.trace_summary(deep.trace),
    }


@_register("low_confidence_tag")
def _low_confidence_tag(ex: ScenarioExecutor, scenario: dict) -> dict:
    conclusion = Conclusion(
        text="部分客户征信数据过期，结论仅供参考",
        confidence=ConfidenceLevel.LOW,
        evidence=[EvidenceRef(type="query", source="customer_360", detail="部分字段缺失")],
        limitations=["征信数据过期3个月", "司法数据仅覆盖公开案件", "样本量不足10户"],
    )
    return ex.trust.validate_conclusion(conclusion).model_dump()


# ===================== 沉淀类 =====================

@_register("template_precipitate")
def _template_precipitate(ex: ScenarioExecutor, scenario: dict) -> dict:
    ex.ctx.assets.save_favorite_query("高风险客户筛查", "SELECT * FROM customer_360 WHERE risk_score >= 70", ["贷前", "风险"])
    ex.ctx.assets.save_reference_case("贷后流水骤降处置", {"action": "现场核查", "result": "风险化解"}, 4.5)
    return {"saved": ex.ctx.assets.get_metrics(), "items": scenario["demo_params"]["save_items"]}


@_register("template_ops")
def _template_ops(ex: ScenarioExecutor, scenario: dict) -> dict:
    params = scenario["demo_params"]
    version = ex.ctx.assets.publish_template_version(params["template_id"], params["version"], {"sections": 4})
    return {"published": version, "template_id": params["template_id"]}


@_register("reference_case")
def _reference_case(ex: ScenarioExecutor, scenario: dict) -> dict:
    cases = ex.ctx.query_table("risk_cases", "SELECT * FROM risk_cases")
    for c in cases:
        ex.ctx.assets.save_reference_case(f"{c['case_type']}-{c['signal_type']}", c, 4.5)
    return {"reference_cases": ex.ctx.assets.list_reference_cases(scenario["demo_params"]["min_score"])}


@_register("ops_metrics")
def _ops_metrics(ex: ScenarioExecutor, scenario: dict) -> dict:
    return {
        "query_success_rate": 0.92,
        "report_success_rate": 0.88,
        "template_usage_count": 156,
        "manual_edit_rate": 0.23,
        "conclusion_adoption_rate": 0.76,
        "asset_metrics": ex.ctx.assets.get_metrics(),
    }


# 补充 DATASET_MAP 引用
from demo.scenarios.context import DATASET_MAP  # noqa: E402
