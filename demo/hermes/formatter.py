"""Hermes 场景产出格式化 - 对话友好展示."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def format_scenario_result(record: dict[str, Any]) -> tuple[str, list[dict], list[str]]:
    """返回 (markdown回复, artifacts, suggestions)."""
    sid = record.get("id", "")
    cap = record.get("capability", "")
    status = record.get("status", "")
    expected = record.get("expected_output", "")

    if status == "error":
        return (
            f"❌ 场景 **{sid} {cap}** 执行失败：{record.get('error', '未知错误')}",
            [],
            _suggest_next(sid),
        )

    output = record.get("output", {})
    lines = [
        f"✅ **场景 {sid} · {cap}**",
        f"**业务场景**：{record.get('business_scene', '')}",
        f"**预期产出**：{expected}",
        "",
        _summarize_output(output),
    ]
    artifacts = _extract_artifacts(output)
    if artifacts:
        lines.append("\n**可查看产物：**")
        for a in artifacts:
            lines.append(f"- [{a['label']}]({a['url']})")

    return "\n".join(lines), artifacts, _suggest_next(sid)


def format_scenario_list(scenarios: list[dict], group: str | None = None) -> str:
    lines = ["## Hermes 场景能力清单\n"]
    if group:
        lines.append(f"当前能力组：**{group}**\n")
    lines.append(f"共 **{len(scenarios)}** 个演示场景。可说「运行场景 1.1」或「演示贷前看板」。\n")
    current = ""
    for s in scenarios:
        if s.get("group") != current:
            current = s["group"]
            lines.append(f"\n### {current}")
        lines.append(f"- **{s['id']}** {s['capability']} — {s['business_scene']} `{s.get('priority', '')}`")
    lines.append("\n**快捷指令**：`演示全部` · `开始导览` · `运行问数类` · `帮助`")
    return "\n".join(lines)


def format_run_all_summary(results: list[dict]) -> str:
    ok = sum(1 for r in results if r.get("status") == "ok")
    err = sum(1 for r in results if r.get("status") == "error")
    lines = [
        f"## 全场景演示完成\n",
        f"- ✅ 成功：**{ok}**",
        f"- ❌ 失败：**{err}**",
        f"- 📊 总计：**{len(results)}**",
        "",
        "### 分组摘要",
    ]
    by_group: dict[str, list[dict]] = {}
    for r in results:
        by_group.setdefault(r.get("group", ""), []).append(r)
    for group, items in by_group.items():
        g_ok = sum(1 for i in items if i.get("status") == "ok")
        lines.append(f"- **{group}**：{g_ok}/{len(items)} 成功")
    lines.append("\n可说「开始导览」逐步查看每个场景详情。")
    return "\n".join(lines)


def format_group_summary(results: list[dict], group: str) -> str:
    ok = [r for r in results if r.get("status") == "ok"]
    lines = [f"## {group} 演示完成（{len(ok)}/{len(results)} 成功）\n"]
    for r in results:
        icon = "✅" if r.get("status") == "ok" else "❌"
        lines.append(f"{icon} **{r['id']}** {r['capability']}")
    return "\n".join(lines)


def format_query_result(result: dict) -> str:
    qtype = result.get("type", "query")
    if qtype == "knowledge" or result.get("found") is not None:
        return result.get("answer", str(result))
    if result.get("conclusion"):
        text = result["conclusion"].get("text", "") if isinstance(result["conclusion"], dict) else ""
        rows = result.get("result", {}).get("row_count", 0)
        return f"**结论**：{text}\n\n返回 **{rows}** 行数据。"
    if result.get("explanation"):
        exp = result["explanation"]
        return f"**{exp.get('label', '指标')}**：{exp.get('formula', '')}\n{exp.get('description', '')}"
    rows = result.get("result", {}).get("row_count", 0)
    shacl = result.get("shacl", {})
    msg = f"查询完成，返回 **{rows}** 行。"
    if shacl:
        msg += f" SHACL：{'通过' if shacl.get('passed') else '未通过'}"
    return msg


def format_research_result(result: dict) -> str:
    insights = result.get("insights", [])
    lines = ["## 深度研究分析\n"]
    if result.get("workflow_id"):
        lines.append(f"工作流：`{result['workflow_id']}`")
    for i in insights:
        lines.append(f"- {i}")
    if result.get("task_graph"):
        lines.append(f"\nTaskGraph：`{result['task_graph'].get('@id', '')}`")
    return "\n".join(lines)


def _summarize_output(output: Any, max_len: int = 1200) -> str:
    if not output:
        return "_（无结构化产出）_"
    if isinstance(output, dict):
        parts = []
        for key, val in output.items():
            if key.endswith("_path") or key == "dashboard_path":
                parts.append(f"- **{key}**：`{val}`")
            elif isinstance(val, list) and val and isinstance(val[0], dict):
                parts.append(f"- **{key}**：{len(val)} 条记录")
                if len(val) <= 3:
                    parts.append(f"  ```json\n{json.dumps(val, ensure_ascii=False, indent=2)[:400]}\n  ```")
            elif isinstance(val, dict):
                brief = json.dumps(val, ensure_ascii=False, default=str)
                if len(brief) > 200:
                    brief = brief[:200] + "..."
                parts.append(f"- **{key}**：{brief}")
            else:
                parts.append(f"- **{key}**：{val}")
        text = "\n".join(parts)
        return text[:max_len] + ("…" if len(text) > max_len else "")
    text = json.dumps(output, ensure_ascii=False, indent=2, default=str)
    return text[:max_len] + ("…" if len(text) > max_len else "")


def _extract_artifacts(output: dict) -> list[dict]:
    artifacts = []
    if not isinstance(output, dict):
        return artifacts

    def _add(path_val: str, label: str) -> None:
        if not path_val:
            return
        p = Path(path_val)
        if p.suffix == ".html":
            rel = f"/output/scenarios/{p.parent.name}/{p.name}" if "scenarios" in str(p) else f"/output/{p.parent.name}/{p.name}"
            artifacts.append({"type": "html", "label": label, "url": rel, "path": str(p)})

    _add(output.get("dashboard_path", ""), "查看看板")
    for key in ("reports", "report"):
        val = output.get(key)
        if isinstance(val, list):
            for i, r in enumerate(val):
                if isinstance(r, dict) and r.get("output_path"):
                    _add(r["output_path"], f"报告 {i + 1}")
        elif isinstance(val, dict) and val.get("output_path"):
            _add(val["output_path"], "查看报告")
    if isinstance(output.get("reports"), list):
        for r in output["reports"]:
            if isinstance(r, str):
                _add(r, "报告")
            elif isinstance(r, dict):
                _add(r.get("path", r.get("output_path", "")), "报告")
    return artifacts


def _suggest_next(current_id: str) -> list[str]:
    try:
        major, minor = current_id.split(".")
        nxt = f"{major}.{int(minor) + 1}"
        return [f"运行场景 {nxt}", "下一个场景", "演示全部", "帮助"]
    except (ValueError, IndexError):
        return ["开始导览", "演示全部", "帮助"]
