"""Hermes 智能对话 API 与 Web UI."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from demo.hermes.service import get_hermes_service
from demo.scenarios.context import OUTPUT_DIR

router = APIRouter(tags=["hermes"])


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class RunScenarioRequest(BaseModel):
    session_id: str | None = None


@router.get("/hermes", response_class=HTMLResponse, include_in_schema=False)
def hermes_ui() -> str:
    return HERMES_HTML


@router.post("/api/hermes/chat")
def hermes_chat(req: ChatRequest) -> dict[str, Any]:
    service = get_hermes_service()
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="消息不能为空")
    return service.chat(req.message.strip(), req.session_id)


@router.get("/api/hermes/scenarios")
def list_scenarios(group: str | None = None) -> dict[str, Any]:
    service = get_hermes_service()
    scenarios = service.list_scenarios(group)
    return {
        "total": len(scenarios),
        "groups": service.router.list_groups(),
        "scenarios": scenarios,
    }


@router.post("/api/hermes/scenarios/{scenario_id}/run")
def run_scenario(scenario_id: str, req: RunScenarioRequest | None = None) -> dict[str, Any]:
    service = get_hermes_service()
    record = service.run_scenario(scenario_id)
    if record.get("status") == "error" and "不存在" in record.get("error", ""):
        raise HTTPException(status_code=404, detail=record["error"])
    from demo.hermes.formatter import format_scenario_result

    reply, artifacts, suggestions = format_scenario_result(record)
    result: dict[str, Any] = {
        "record": record,
        "reply": reply,
        "artifacts": artifacts,
        "suggestions": suggestions,
    }
    if req and req.session_id:
        session = service.sessions.get_or_create(req.session_id)
        session.add_assistant(reply, intent="run_scenario", scenario_id=scenario_id, artifacts=artifacts, suggestions=suggestions)
        result["session_id"] = session.session_id
    return result


@router.post("/api/hermes/scenarios/run-all")
def run_all_scenarios() -> dict[str, Any]:
    service = get_hermes_service()
    results = service.run_all()
    from demo.hermes.formatter import format_run_all_summary

    return {"results": results, "summary": format_run_all_summary(results)}


@router.get("/api/hermes/sessions/{session_id}")
def get_session(session_id: str) -> dict[str, Any]:
    service = get_hermes_service()
    session = service.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {
        "session_id": session.session_id,
        "tour_active": session.tour_active,
        "tour_index": session.tour_index,
        "last_scenario_id": session.last_scenario_id,
        "history": session.history(50),
    }


@router.get("/output/scenarios/{category}/{filename}")
def serve_scenario_output(category: str, filename: str):
    path = OUTPUT_DIR / category / filename
    if path.exists():
        return FileResponse(path, media_type="text/html")
    path2 = OUTPUT_DIR / filename
    if path2.exists():
        return FileResponse(path2, media_type="text/html")
    raise HTTPException(status_code=404, detail="文件不存在")


HERMES_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hermes 智能对话 - AIP 全场景演示</title>
<style>
:root{--bg:#0b1020;--panel:#151d33;--accent:#5eead4;--accent2:#38bdf8;--text:#e8eef8;--muted:#8b9cb8;--user:#1e3a5f;--bot:#1a2332}
*{box-sizing:border-box}body{margin:0;font-family:"Segoe UI",system-ui,sans-serif;background:var(--bg);color:var(--text);height:100vh;display:flex;flex-direction:column}
header{padding:14px 20px;border-bottom:1px solid #243049;display:flex;align-items:center;justify-content:space-between;background:#0f1628}
header h1{font-size:1.1rem;margin:0}header span{color:var(--muted);font-size:.85rem}
.layout{flex:1;display:grid;grid-template-columns:260px 1fr;min-height:0}
.sidebar{border-right:1px solid #243049;background:var(--panel);overflow:auto;padding:12px}
.sidebar h3{font-size:.8rem;color:var(--accent);margin:12px 0 8px;text-transform:uppercase;letter-spacing:.05em}
.chip{display:block;width:100%;text-align:left;background:#1c2640;border:1px solid #2a3654;color:var(--text);padding:8px 10px;border-radius:8px;margin:4px 0;cursor:pointer;font-size:.82rem}
.chip:hover{border-color:var(--accent2)}
.main{display:flex;flex-direction:column;min-height:0}
.messages{flex:1;overflow:auto;padding:20px;display:flex;flex-direction:column;gap:12px}
.msg{max-width:85%;padding:12px 14px;border-radius:12px;line-height:1.55;font-size:.92rem;white-space:pre-wrap}
.msg.user{align-self:flex-end;background:var(--user)}
.msg.bot{align-self:flex-start;background:var(--bot);border:1px solid #2a3654}
.msg.bot a{color:var(--accent2)}
.suggestions{display:flex;flex-wrap:wrap;gap:6px;padding:0 20px 8px}
.sug{background:#1c2a44;border:1px solid #334155;color:var(--accent);padding:6px 10px;border-radius:16px;font-size:.78rem;cursor:pointer}
.input-bar{display:flex;gap:8px;padding:14px 20px;border-top:1px solid #243049;background:#0f1628}
.input-bar input{flex:1;background:#1a2332;border:1px solid #334155;color:var(--text);padding:12px 14px;border-radius:10px;font-size:.95rem}
.input-bar button{background:linear-gradient(135deg,var(--accent2),var(--accent));color:#041018;border:none;padding:0 18px;border-radius:10px;font-weight:700;cursor:pointer}
.status{font-size:.75rem;color:var(--muted);padding:0 20px 8px}
@media(max-width:800px){.layout{grid-template-columns:1fr}.sidebar{display:none}}
</style>
</head>
<body>
<header>
  <div><h1>Hermes 智能对话</h1><span>AIP 全场景演示 · 34 场景 · 本体 + SHACL + TaskGraph</span></div>
  <div><a href="/docs" style="color:var(--accent2);font-size:.85rem;text-decoration:none">API</a> · <a href="/ontology/console" style="color:var(--accent2);font-size:.85rem;text-decoration:none">本体台</a></div>
</header>
<div class="layout">
  <aside class="sidebar" id="sidebar"></aside>
  <section class="main">
    <div class="messages" id="messages"></div>
    <div class="suggestions" id="suggestions"></div>
    <div class="status" id="status"></div>
    <div class="input-bar">
      <input id="input" placeholder="例如：演示贷前筛查任务规划 / 运行场景 2.1 / 查询华东高风险客户" />
      <button id="send">发送</button>
    </div>
  </section>
</div>
<script>
let sessionId = localStorage.getItem('hermes_session') || null;
const $ = (id)=>document.getElementById(id);
function md(text){
  return text
    .replace(/\\*\\*(.+?)\\*\\*/g,'<strong>$1</strong>')
    .replace(/\\[(.+?)\\]\\((.+?)\\)/g,'<a href="$2" target="_blank">$1</a>')
    .replace(/^### (.+)$/gm,'<h4>$1</h4>').replace(/^## (.+)$/gm,'<h3>$1</h3>')
    .replace(/^- (.+)$/gm,'<li>$1</li>').replace(/(<li>.*<\\/li>)/gs,'<ul>$1</ul>');
}
function addMsg(role, content){
  const el=document.createElement('div');
  el.className='msg '+role;
  el.innerHTML=role==='bot'?md(content):content;
  $('messages').appendChild(el);
  $('messages').scrollTop=$('messages').scrollHeight;
}
function setSuggestions(list){
  $('suggestions').innerHTML='';
  (list||[]).forEach(s=>{
    const b=document.createElement('button');
    b.className='sug'; b.textContent=s;
    b.onclick=()=>{ $('input').value=s; send(); };
    $('suggestions').appendChild(b);
  });
}
async function send(){
  const text=$('input').value.trim(); if(!text) return;
  $('input').value=''; addMsg('user', text);
  $('status').textContent='Hermes 思考中…';
  const r=await fetch('/api/hermes/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:text,session_id:sessionId})});
  const d=await r.json();
  sessionId=d.session_id; localStorage.setItem('hermes_session', sessionId);
  addMsg('bot', d.reply||JSON.stringify(d));
  setSuggestions(d.suggestions);
  $('status').textContent=`意图: ${d.intent} · ${d.route_reason||''}`;
}
async function loadSidebar(){
  const r=await fetch('/api/hermes/scenarios'); const d=await r.json();
  let html='<h3>快捷演示</h3>';
  ['演示全部','开始导览','帮助','运行场景 5.1','运行场景 2.1','运行问数类'].forEach(c=>{
    html+=`<button class="chip" onclick="document.getElementById('input').value='${c}';send()">${c}</button>`;
  });
  let g='';
  d.scenarios.forEach(s=>{
    if(s.group!==g){g=s.group;html+=`<h3>${g}</h3>`;}
    html+=`<button class="chip" onclick="document.getElementById('input').value='运行场景 ${s.id}';send()">${s.id} ${s.capability}</button>`;
  });
  $('sidebar').innerHTML=html;
}
$('send').onclick=send;
$('input').addEventListener('keydown',e=>{if(e.key==='Enter')send();});
loadSidebar();
addMsg('bot','你好，我是 **Hermes** 智能分析助手。\\n\\n我可以帮你完成 **34 个 AIP 场景** 的完整演示，包括问数、看板、报告、洞察、预警、可信与沉淀。\\n\\n试试：\\n- `开始导览` 逐步演示全部场景\\n- `运行场景 1.1` 智能问数\\n- `演示贷前筛查任务规划`');
setSuggestions(['开始导览','演示全部','运行场景 1.1','查询华东高风险客户']);
</script>
</body></html>"""


def get_hermes_router() -> APIRouter:
    return router
