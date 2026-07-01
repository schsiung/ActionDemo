"""Hermes 意图路由 - 自然语言 → 场景/Agent."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

BASE_DIR = Path(__file__).parent.parent
REGISTRY_PATH = BASE_DIR / "data" / "scenarios" / "scenario_registry.yaml"

GROUP_ALIASES = {
    "数据准备": "数据准备类",
    "问数": "问数类",
    "看板": "看板类",
    "图表": "图表类",
    "报告": "报告类",
    "洞察": "洞察类",
    "预警": "预警建议类",
    "预警建议": "预警建议类",
    "可信": "可信类",
    "沉淀": "沉淀类",
}

# 能力关键词 → 场景 ID（补充匹配）
CAPABILITY_HINTS: list[tuple[str, str]] = [
    ("名单导入", "0.1"),
    ("数据集接入", "0.1"),
    ("语义模型", "0.2"),
    ("指标配置", "0.2"),
    ("脚本", "0.3"),
    ("workbench", "0.3"),
    ("智能问数", "1.1"),
    ("知识问答", "1.1"),
    ("多轮追问", "1.2"),
    ("口径", "1.3"),
    ("关联指标", "1.4"),
    ("看板", "2.1"),
    ("dashboard", "2.1"),
    ("看板解读", "2.2"),
    ("下钻", "2.3"),
    ("图表设计", "3.1"),
    ("图表生成", "3.2"),
    ("图表解读", "3.3"),
    ("报告模板", "4.1"),
    ("报告大纲", "4.2"),
    ("周期报告", "4.3"),
    ("周报", "4.3"),
    ("日报", "4.3"),
    ("变量化报告", "4.4"),
    ("多受众", "4.5"),
    ("报告生成", "4.6"),
    ("任务规划", "5.1"),
    ("taskgraph", "5.1"),
    ("综合洞察", "5.2"),
    ("归因", "5.3"),
    ("对比分析", "5.4"),
    ("预警规则", "6.1"),
    ("业务建议", "6.2"),
    ("质检", "7.1"),
    ("受控生成", "7.2"),
    ("证据引用", "7.3"),
    ("过程回溯", "7.4"),
    ("trace", "7.4"),
    ("低置信", "7.5"),
    ("模板沉淀", "8.1"),
    ("模板运营", "8.2"),
    ("参考样例", "8.3"),
    ("运营监测", "8.4"),
    ("贷前筛查", "5.1"),
    ("贷后看板", "2.1"),
    ("本体", "0.2"),
    ("shacl", "7.1"),
]


@dataclass
class RouteResult:
    intent: str
    scenario_id: str | None = None
    group: str | None = None
    question: str | None = None
    confidence: float = 1.0
    reason: str = ""


class HermesRouter:
    """规则意图路由：优先命令，再场景匹配，最后 Agent 兜底."""

    SCENARIO_ID_RE = re.compile(r"(?:场景|scenario)?\s*(\d+\.\d+)", re.I)
    GROUP_RUN_RE = re.compile(r"(?:运行|演示|执行).{0,6}(数据准备|问数|看板|图表|报告|洞察|预警|可信|沉淀)")

    def __init__(self, scenarios: list[dict[str, Any]] | None = None):
        self.scenarios = scenarios or self._load_scenarios()
        self._by_id = {s["id"]: s for s in self.scenarios}
        self._index = self._build_index()

    @staticmethod
    def _load_scenarios() -> list[dict]:
        with open(REGISTRY_PATH, encoding="utf-8") as f:
            return yaml.safe_load(f)["scenarios"]

    def _build_index(self) -> list[tuple[str, str, float]]:
        """(keyword, scenario_id, weight)."""
        entries: list[tuple[str, str, float]] = []
        for s in self.scenarios:
            sid = s["id"]
            for text in (s.get("capability", ""), s.get("business_scene", ""), s.get("group", "")):
                for token in re.split(r"[\s\-—、/]+", text):
                    if len(token) >= 2:
                        entries.append((token.lower(), sid, 1.0))
        for hint, sid in CAPABILITY_HINTS:
            entries.append((hint.lower(), sid, 1.5))
        return entries

    def route(self, message: str) -> RouteResult:
        text = message.strip()
        lower = text.lower()

        # 系统命令
        if any(k in text for k in ("帮助", "help", "能做什么", "有哪些场景", "场景列表", "全部场景")):
            return RouteResult(intent="list_scenarios", reason="用户请求场景清单")

        if any(k in text for k in ("演示全部", "运行全部", "完整演示", "全场景", "34个场景", "全部演示")):
            return RouteResult(intent="run_all", reason="用户请求全场景演示")

        if any(k in text for k in ("导览", "引导演示", "场景导览", "开始导览")):
            return RouteResult(intent="start_tour", reason="用户启动场景导览")

        if "下一个场景" in text or "继续导览" in text:
            return RouteResult(intent="next_tour", reason="导览下一步")

        if "结束导览" in text:
            return RouteResult(intent="stop_tour", reason="结束导览")

        if "深度研究" in text or "风险全景" in text or "全景分析" in text:
            return RouteResult(intent="research", question=text, reason="深度研究关键词")

        # 显式场景 ID
        m = self.SCENARIO_ID_RE.search(text)
        if m:
            sid = m.group(1)
            if sid in self._by_id:
                return RouteResult(intent="run_scenario", scenario_id=sid, reason=f"显式场景编号 {sid}")

        # 能力组
        gm = self.GROUP_RUN_RE.search(text)
        if gm:
            group = GROUP_ALIASES.get(gm.group(1), gm.group(1) + "类")
            return RouteResult(intent="run_group", group=group, reason=f"能力组 {group}")

        for alias, group in GROUP_ALIASES.items():
            if alias in text and any(v in text for v in ("运行", "演示", "执行", "场景")):
                return RouteResult(intent="run_group", group=group, reason=f"能力组关键词 {group}")

        # 关键词打分匹配场景
        best_id, best_score = self._match_scenario(lower)
        if best_score >= 2.0:
            return RouteResult(
                intent="run_scenario",
                scenario_id=best_id,
                confidence=min(best_score / 5, 1.0),
                reason=f"关键词匹配场景 {best_id}",
            )

        # 知识 vs 问数
        if any(k in text for k in ("政策", "规则", "CRR", "操作指南", "知识", "什么意思", "限制")):
            return RouteResult(intent="knowledge", question=text, reason="知识库关键词")

        if any(k in text for k in ("查询", "排名", "多少", "哪些", "授信", "风险", "客户", "流水", "按")):
            return RouteResult(intent="query", question=text, reason="问数关键词")

        # 弱场景匹配
        if best_score >= 1.0:
            return RouteResult(
                intent="run_scenario",
                scenario_id=best_id,
                confidence=0.5,
                reason=f"弱匹配场景 {best_id}",
            )

        return RouteResult(intent="query", question=text, reason="默认问数兜底")

    def _match_scenario(self, lower: str) -> tuple[str, float]:
        scores: dict[str, float] = {}
        for keyword, sid, weight in self._index:
            if keyword in lower:
                scores[sid] = scores.get(sid, 0) + weight
        if not scores:
            return "1.1", 0.0
        best = max(scores.items(), key=lambda x: x[1])
        return best[0], best[1]

    def get_scenario(self, scenario_id: str) -> dict | None:
        return self._by_id.get(scenario_id)

    def list_scenarios(self) -> list[dict[str, Any]]:
        return [
            {
                "id": s["id"],
                "capability": s["capability"],
                "group": s["group"],
                "priority": s.get("priority", ""),
                "business_scene": s["business_scene"],
                "expected_output": s.get("expected_output", ""),
            }
            for s in self.scenarios
        ]

    def list_groups(self) -> list[str]:
        return list(dict.fromkeys(s["group"] for s in self.scenarios))
