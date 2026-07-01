"""本体配置台 - FastAPI 路由与简易 Web UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from aip.models import Conclusion, EvidenceRef
from aip.ontology.factory import (
    DEFAULT_SHACL_TTL,
    DEFAULT_TTL,
    DEFAULT_YAML,
    get_ontology_registry,
    get_shacl_validator,
    get_sync_service,
)
from aip.ontology.pyshacl_engine import PyShaclEngine

router = APIRouter(prefix="/api/ontology", tags=["ontology"])


class SyncRequest(BaseModel):
    direction: Literal["yaml_to_ttl", "ttl_to_yaml", "diff"] = "yaml_to_ttl"
    dry_run: bool = False


class ShaclValidateRequest(BaseModel):
    conclusion: dict[str, Any] | None = None
    query_result: dict[str, Any] | None = None
    customer: dict[str, Any] | None = None
    use_pyshacl: bool = True


@router.get("/status")
def ontology_status() -> dict[str, Any]:
    sync = get_sync_service()
    validator = get_shacl_validator()
    return {
        **sync.status(),
        "shacl_engine": validator.engine_name,
        "shacl_shapes": str(DEFAULT_SHACL_TTL),
        "shapes_loaded": len(validator.list_shapes()),
    }


@router.get("/metrics")
def list_metrics() -> list[dict[str, Any]]:
    reg = get_ontology_registry()
    seen: set[str] = set()
    out = []
    for key, metric in reg._metrics.items():
        if not key.startswith("aip:") or metric.iri in seen:
            continue
        seen.add(metric.iri)
        out.append({
            "iri": metric.iri,
            "label": metric.label,
            "formula": metric.formula,
            "unit": metric.unit,
        })
    return out


@router.get("/metrics/{metric_id:path}")
def explain_metric(metric_id: str) -> dict[str, Any]:
    reg = get_ontology_registry()
    iri = metric_id if metric_id.startswith("aip:") else f"aip:Metric/{metric_id}"
    result = reg.explain_metric(iri)
    if not result.get("found"):
        raise HTTPException(status_code=404, detail=f"指标不存在: {iri}")
    return result


@router.get("/preview/ttl")
def preview_ttl() -> dict[str, str]:
    sync = get_sync_service()
    content = sync.preview_ttl()
    return {"path": str(DEFAULT_TTL), "content": content, "lines": str(len(content.splitlines()))}


@router.post("/sync")
def sync_ontology(req: SyncRequest) -> dict[str, Any]:
    sync = get_sync_service()
    try:
        return sync.sync(req.direction, dry_run=req.dry_run)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/shapes")
def list_shacl_shapes() -> dict[str, Any]:
    validator = get_shacl_validator()
    engine = PyShaclEngine(DEFAULT_SHACL_TTL, DEFAULT_TTL)
    return {
        "engine": validator.engine_name,
        "shapes_ttl": str(DEFAULT_SHACL_TTL),
        "shapes": engine.list_shapes(),
        "yaml_shapes": validator.list_shapes(),
    }


@router.post("/shacl/validate")
def validate_shacl(req: ShaclValidateRequest) -> dict[str, Any]:
    validator = get_shacl_validator()
    conclusion = None
    if req.conclusion:
        conclusion = Conclusion(**{
            k: v for k, v in req.conclusion.items() if k in Conclusion.model_fields
        })
        if req.conclusion.get("evidence"):
            conclusion.evidence = [
                EvidenceRef(**{k: v for k, v in e.items() if k in EvidenceRef.model_fields})
                for e in req.conclusion["evidence"]
            ]
    result = validator.validate_all(
        conclusion or Conclusion(text="", evidence=[]),
        query_result=req.query_result,
        customer=req.customer,
        use_pyshacl=req.use_pyshacl,
    )
    return result.to_dict()


CONSOLE_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AIP 本体配置台</title>
<style>
:root{--bg:#0f172a;--card:#1e293b;--accent:#38bdf8;--ok:#4ade80;--warn:#fbbf24;--text:#e2e8f0;--muted:#94a3b8}
*{box-sizing:border-box}body{font-family:system-ui,sans-serif;background:var(--bg);color:var(--text);margin:0;padding:24px;line-height:1.5}
h1{font-size:1.5rem;margin:0 0 8px}h2{font-size:1rem;color:var(--accent);margin:24px 0 12px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}
.card{background:var(--card);border-radius:12px;padding:16px;border:1px solid #334155}
.badge{display:inline-block;padding:2px 8px;border-radius:6px;font-size:.8rem}
.badge.ok{background:#14532d;color:var(--ok)}.badge.warn{background:#422006;color:var(--warn)}
button{background:var(--accent);color:#0f172a;border:none;padding:8px 14px;border-radius:8px;cursor:pointer;font-weight:600;margin:4px 4px 4px 0}
button.secondary{background:#475569;color:#fff}
pre{background:#0b1220;padding:12px;border-radius:8px;overflow:auto;font-size:.8rem;max-height:240px}
#log{min-height:80px;font-size:.85rem;color:var(--muted)}
.metric{font-size:.9rem;margin:4px 0}
a{color:var(--accent)}
</style>
</head>
<body>
<h1>AIP 本体配置台</h1>
<p style="color:var(--muted)">OWL 双向同步 · pyshacl 生产校验 · <a href="/docs">API 文档</a></p>
<div class="grid">
  <div class="card"><h2>同步状态</h2><div id="status">加载中…</div></div>
  <div class="card"><h2>操作</h2>
    <button onclick="sync('diff')">检测差异</button>
    <button onclick="sync('yaml_to_ttl',true)">预览 YAML→TTL</button>
    <button onclick="sync('yaml_to_ttl',false)">执行 YAML→TTL</button>
    <button onclick="sync('ttl_to_yaml',true)">预览 TTL→YAML</button>
    <button onclick="sync('ttl_to_yaml',false)">执行 TTL→YAML</button>
    <button class="secondary" onclick="loadPreview()">预览 TTL</button>
    <button class="secondary" onclick="testShacl()">SHACL 冒烟测试</button>
  </div>
</div>
<div class="card" style="margin-top:16px"><h2>指标词表</h2><div id="metrics"></div></div>
<div class="card" style="margin-top:16px"><h2>TTL 预览</h2><pre id="ttl"></pre></div>
<div class="card" style="margin-top:16px"><h2>操作日志</h2><pre id="log"></pre></div>
<script>
const log=(m)=>{const el=document.getElementById('log');el.textContent=new Date().toLocaleTimeString()+' '+m+'\\n'+el.textContent};
async function loadStatus(){
  const r=await fetch('/api/ontology/status');const d=await r.json();
  document.getElementById('status').innerHTML=`
    <div>版本 <b>${d.ontology_version}</b></div>
    <div>同步 <span class="badge ${d.in_sync?'ok':'warn'}">${d.in_sync?'已同步':'待同步'}</span></div>
    <div>SHACL 引擎 <b>${d.shacl_engine}</b>（${d.shapes_loaded} 形状）</div>
    <div>指标 ${d.metric_count} · 公理 ${d.axiom_count} · 绑定 ${d.binding_count}</div>
    <div style="font-size:.8rem;color:#94a3b8;margin-top:8px">YAML ${d.yaml_hash||'-'} · TTL ${d.ttl_hash||'-'}</div>`;
}
async function loadMetrics(){
  const r=await fetch('/api/ontology/metrics');const list=await r.json();
  document.getElementById('metrics').innerHTML=list.map(m=>`<div class="metric"><b>${m.label}</b> <code>${m.iri}</code></div>`).join('');
}
async function sync(dir,dry=true){
  const r=await fetch('/api/ontology/sync',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({direction:dir,dry_run:dry})});
  const d=await r.json();log(JSON.stringify(d,null,2));loadStatus();
}
async function loadPreview(){
  const r=await fetch('/api/ontology/preview/ttl');const d=await r.json();
  document.getElementById('ttl').textContent=d.content.slice(0,4000)+(d.content.length>4000?'\\n…':'');
}
async function testShacl(){
  const r=await fetch('/api/ontology/shacl/validate',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({conclusion:{text:'测试结论',confidence:'high',evidence:[{type:'query',source:'aip:Dataset/customer_360',detail:'SELECT COUNT(*) FROM customer_360'}]},query_result:{dataset:'aip:Dataset/customer_360',row_count:10}})});
  log('SHACL: '+JSON.stringify(await r.json()));
}
loadStatus();loadMetrics();
</script>
</body></html>"""


def get_console_router() -> APIRouter:
    main = APIRouter()

    @main.get("/ontology/console", response_class=HTMLResponse, include_in_schema=False)
    def ontology_console() -> str:
        return CONSOLE_HTML

    main.include_router(router)
    return main
