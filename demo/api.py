"""AIP MVP FastAPI 服务 - 提供 REST API 演示."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

from aip.agents.deep_research_agent import DeepResearchAgent
from aip.agents.query_agent import QueryAgent
from aip.assets.center import AssetCenter
from aip.data_prep.dataset_registry import DataAgentProfile, Dataset, DatasetRegistry
from aip.data_prep.session_upload import SessionUploadService
from demo.hermes.routes import get_hermes_router
from aip.ontology.console import get_console_router
from aip.ontology.factory import (
    DEFAULT_DATASET_IRI,
    ensure_ttl_export,
    get_ontology_registry,
    get_shacl_validator,
)
from aip.report.composer import ReportComposer
from aip.semantic.model import load_semantic_model
from aip.trust.layer import TrustLayer
from aip.visualization.dashboard import DashboardGenerator

DEMO_DIR = Path(__file__).parent
DATA_DIR = DEMO_DIR / "data"
OUTPUT_DIR = Path("output")

app = FastAPI(title="AIP 智能分析平台 MVP", version="0.1.0")
app.include_router(get_console_router())
app.include_router(get_hermes_router())

_registry: DatasetRegistry | None = None
_query_agent: QueryAgent | None = None
_deep_agent: DeepResearchAgent | None = None
_assets: AssetCenter | None = None


def _init():
    global _registry, _query_agent, _deep_agent, _assets
    if _registry is not None:
        return
    _registry = DatasetRegistry()
    ontology = get_ontology_registry()
    ensure_ttl_export()

    csv_path = DATA_DIR / "scenarios" / "customer_360.csv"
    if not csv_path.exists():
        csv_path = DATA_DIR / "sample_customers.csv"
    table_name = "customer_360" if "customer_360" in csv_path.name else "customer_credit"

    dataset = Dataset(
        id="ds_customer_360",
        name="客户全景数据集",
        source_type="table",
        table_name=table_name,
        profile=DataAgentProfile(vectorized=True),
    )
    _registry.register_csv(dataset, csv_path)

    semantic_path = DATA_DIR / "scenarios" / "semantic_pre_loan.yaml"
    if semantic_path.exists():
        semantic = load_semantic_model(semantic_path)
        semantic.dataset_iri = DEFAULT_DATASET_IRI
    else:
        semantic = load_semantic_model(DATA_DIR / "semantic_model.yaml")

    shacl = get_shacl_validator()
    _query_agent = QueryAgent(
        _registry,
        semantic,
        table_name,
        ontology_registry=ontology,
        dataset_iri=DEFAULT_DATASET_IRI,
        shacl_validator=shacl,
    )
    _deep_agent = DeepResearchAgent(_registry, semantic, table_name, ontology_registry=ontology, dataset_iri=DEFAULT_DATASET_IRI)
    _assets = AssetCenter()


@app.on_event("startup")
def startup():
    _init()
    OUTPUT_DIR.mkdir(exist_ok=True)


class AskRequest(BaseModel):
    question: str


class ReportRequest(BaseModel):
    template_id: str = "weekly_review"
    variables: dict[str, str] = {}


@app.get("/", response_class=HTMLResponse)
def index():
    return """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><title>AIP MVP</title>
<style>body{font-family:sans-serif;max-width:800px;margin:40px auto;padding:0 20px}
h1{color:#1e3a5f}code{background:#f0f4f8;padding:2px 6px;border-radius:4px}
.endpoint{margin:12px 0;padding:12px;background:#f9fafb;border-radius:8px}</style></head>
<body><h1>AIP 智能分析平台 MVP</h1>
<p>REST API 演示服务，核心端点:</p>
<div class="endpoint"><b><a href="/hermes">/hermes</a></b> - Hermes 智能对话（34 场景完整演示）⭐</div>
<div class="endpoint"><b>POST /api/hermes/chat</b> - 对话入口<br><code>{"message": "开始导览"}</code></div>
<div class="endpoint"><b>GET /api/hermes/scenarios</b> - 场景清单</div>
<div class="endpoint"><b>POST /api/ask</b> - 智能问数<br><code>{"question": "各机构授信余额排名"}</code></div>
<div class="endpoint"><b>POST /api/research</b> - 深度研究分析<br><code>{"question": "对公客户风险全景分析"}</code></div>
<div class="endpoint"><b>POST /api/report</b> - 生成报告<br><code>{"template_id": "weekly_review"}</code></div>
<div class="endpoint"><b>POST /api/upload</b> - 上传 CSV/Excel 文件</div>
<div class="endpoint"><b>GET /api/dashboard</b> - 生成 HTML 看板</div>
<div class="endpoint"><b>GET /ontology/console</b> - 本体配置台（OWL 同步 + SHACL）</div>
<div class="endpoint"><b>GET /api/ontology/status</b> - 本体同步状态</div>
<div class="endpoint"><b>POST /api/ontology/sync</b> - YAML ↔ TTL 双向同步</div>
<div class="endpoint"><b>POST /api/ontology/shacl/validate</b> - pyshacl 校验</div>
<div class="endpoint"><b>GET /docs</b> - Swagger API 文档</div>
</body></html>"""


@app.get("/api/datasets")
def list_datasets():
    _init()
    return [
        {"id": ds.id, "name": ds.name, "row_count": ds.metadata.get("row_count"), "columns": ds.metadata.get("columns")}
        for ds in _registry.list_datasets()
    ]


@app.post("/api/ask")
def ask(req: AskRequest):
    _init()
    result = _query_agent.ask(req.question)
    result["shacl_engine"] = _query_agent.shacl.engine_name
    return result


@app.post("/api/research")
def research(req: AskRequest):
    _init()
    return _deep_agent.execute(req.question)


@app.post("/api/report")
def generate_report(req: ReportRequest):
    _init()
    data = _deep_agent.execute("对公客户风险全景分析")
    data["actions"] = ["关注高风险客户", "开展区域对比分析", "更新风险评级"]
    composer = ReportComposer(OUTPUT_DIR / "reports")
    return composer.compose(req.template_id, data, req.variables)


@app.get("/api/dashboard")
def generate_dashboard():
    _init()
    comparison = _deep_agent.compare.by_dimension("region", "credit_balance")
    table = _deep_agent.table_name
    summary = _registry.execute_sql(
        f"SELECT COUNT(*) AS cnt, SUM(credit_balance) AS total, AVG(risk_score) AS avg_risk FROM {table}"
    ).to_dict(orient="records")[0]

    generator = DashboardGenerator(OUTPUT_DIR / "dashboards")
    path = generator.generate({
        "title": "对公客户风险监控看板",
        "subtitle": "API 生成",
        "report_period": datetime.now().strftime("%Y-%m"),
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "filters": [{"label": "区域", "options": ["全部", "华东", "华南", "华北"], "default": "全部"}],
        "kpis": [
            {"label": "客户总数", "value": f"{summary['cnt']} 户"},
            {"label": "授信余额", "value": f"{summary['total']:,.0f} 万"},
            {"label": "平均风险分", "value": f"{summary['avg_risk']:.1f}"},
        ],
        "charts": [{"title": "区域授信对比", "type": "bar", "data": comparison["rows"]}],
        "insight": comparison.get("interpretation", ""),
        "filename": "api_dashboard.html",
    })
    return {"path": path, "url": f"/output/dashboards/{Path(path).name}"}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    _init()
    upload_dir = OUTPUT_DIR / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    file_path = upload_dir / file.filename
    content = await file.read()
    file_path.write_bytes(content)

    service = SessionUploadService(_registry, session_id="api_session")
    return service.parse_file(file_path)


@app.get("/output/dashboards/{filename}")
def serve_dashboard(filename: str):
    path = OUTPUT_DIR / "dashboards" / filename
    if path.exists():
        return FileResponse(path, media_type="text/html")
    return {"error": "not found"}


@app.get("/output/reports/{filename}")
def serve_report(filename: str):
    path = OUTPUT_DIR / "reports" / filename
    if path.exists():
        return FileResponse(path, media_type="text/html")
    return {"error": "not found"}


@app.get("/api/metrics/explain/{metric_id}")
def explain_metric(metric_id: str):
    _init()
    ontology = get_ontology_registry()
    iri = metric_id if metric_id.startswith("aip:") else f"aip:Metric/{metric_id}"
    result = ontology.explain_metric(iri)
    if not result.get("found"):
        semantic = load_semantic_model(DATA_DIR / "semantic_model.yaml")
        return semantic.explain_metric(metric_id)
    return result


@app.get("/api/trace/{agent_type}")
def get_trace(agent_type: str):
    _init()
    trust = TrustLayer()
    agent = _deep_agent if agent_type == "deep" else _query_agent
    return trust.trace_summary(agent.trace)


def main():
    import uvicorn
    uvicorn.run("demo.api:app", host="0.0.0.0", port=8000, reload=False)


if __name__ == "__main__":
    main()
