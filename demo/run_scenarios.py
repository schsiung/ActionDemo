"""全场景演示入口 - 按场景编号/能力组运行."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from demo.scenarios.context import OUTPUT_DIR
from demo.scenarios.executor import ScenarioExecutor

GROUPS = [
    "数据准备类", "问数类", "看板类", "图表类", "报告类",
    "洞察类", "预警建议类", "可信类", "沉淀类",
]


def _header(text: str) -> None:
    print(f"\n{'=' * 70}")
    print(f"  {text}")
    print(f"{'=' * 70}")


def _print_result(r: dict) -> None:
    status_icon = {"ok": "✅", "error": "❌", "skipped": "⏭️"}.get(r["status"], "❓")
    print(f"\n{status_icon} [{r['id']}] {r['capability']} ({r['priority']})")
    print(f"   场景: {r['business_scene']}")
    print(f"   预期: {r.get('expected_output', '')}")
    if r["status"] == "ok":
        output_str = json.dumps(r["output"], ensure_ascii=False, indent=2, default=str)
        if len(output_str) > 800:
            output_str = output_str[:800] + "\n   ... (截断)"
        print(f"   产出:\n{output_str}")
    elif r["status"] == "error":
        print(f"   错误: {r['error']}")


def list_scenarios(executor: ScenarioExecutor) -> None:
    scenarios = executor.ctx.load_registry()
    _header(f"全部场景清单 ({len(scenarios)} 条)")
    current_group = ""
    for s in scenarios:
        if s["group"] != current_group:
            current_group = s["group"]
            print(f"\n## {current_group}")
        print(f"  [{s['id']}] {s['capability']} - {s['business_scene']} ({s['priority']})")


def main() -> None:
    parser = argparse.ArgumentParser(description="AIP 全场景演示")
    parser.add_argument("--list", action="store_true", help="列出全部场景")
    parser.add_argument("--id", type=str, help="运行指定场景编号，如 1.1")
    parser.add_argument("--group", type=str, choices=GROUPS, help="运行指定能力组")
    parser.add_argument("--all", action="store_true", help="运行全部场景")
    parser.add_argument("--export", type=str, help="导出结果到 JSON 文件")
    args = parser.parse_args()

    executor = ScenarioExecutor()

    if args.list:
        list_scenarios(executor)
        return

    print("\n🎬 AIP 全场景演示")
    print(f"   输出目录: {OUTPUT_DIR.resolve()}")

    if args.id:
        _header(f"运行场景 {args.id}")
        r = executor.run_by_id(args.id)
        if r:
            _print_result(r)
        else:
            print(f"未找到场景: {args.id}")
    elif args.group:
        _header(f"运行能力组: {args.group}")
        for r in executor.run_by_group(args.group):
            _print_result(r)
    else:
        _header("运行全部场景")
        for r in executor.run_all():
            _print_result(r)

    ok = sum(1 for r in executor.results if r["status"] == "ok")
    err = sum(1 for r in executor.results if r["status"] == "error")
    print(f"\n{'=' * 70}")
    print(f"  完成: {ok} 成功 / {err} 失败 / {len(executor.results)} 总计")
    print(f"  输出: {OUTPUT_DIR.resolve()}")
    print(f"{'=' * 70}\n")

    if args.export and executor.results:
        Path(args.export).write_text(json.dumps(executor.results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print(f"结果已导出: {args.export}")


if __name__ == "__main__":
    main()
