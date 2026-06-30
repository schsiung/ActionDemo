# AIP 智能分析平台 MVP

企业级智能分析中台最小可行产品（MVP），覆盖数据准备、智能问数、图表/看板、洞察分析、报告生成、可信约束与资产沉淀等核心能力。

## 项目结构

```
aip/
├── data_prep/          # 数据集注册、会话上传、脚本 Workbench
├── semantic/           # 语义模型（指标、维度、口径）
├── agents/             # QueryAgent、DeepResearchAgent
├── analytics/          # 归因分析、多维对比
├── visualization/      # 5类图表 + HTML 看板生成
├── report/             # 报告模板与编排
├── trust/              # 可信层（证据、质检、回溯）
├── assets/             # 资产沉淀中心
└── models.py           # 核心数据模型

demo/
├── run_mvp.py          # 端到端 CLI 演示
├── api.py              # FastAPI REST 服务
└── data/               # 示例数据与语义模型配置

tests/                  # 单元测试
```

## 快速开始

### 安装依赖

```bash
pip install -e ".[dev]"
```

### 运行 MVP 演示

```bash
python -m demo.run_mvp
```

演示将依次执行：
- 数据集接入与会话文件上传
- 智能问数与多轮追问
- 深度研究与归因分析
- HTML 可交互看板生成
- 周报模板报告生成
- 可信层证据引用与过程回溯
- 资产沉淀

输出文件位于 `output/dashboards/` 和 `output/reports/`。

### 启动 API 服务

```bash
python -m demo.api
# 或
uvicorn demo.api:app --host 0.0.0.0 --port 8000
```

访问 http://localhost:8000 查看 API 说明，http://localhost:8000/docs 查看 Swagger 文档。

### API 示例

```bash
# 智能问数
curl -X POST http://localhost:8000/api/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "各机构授信余额排名"}'

# 深度研究
curl -X POST http://localhost:8000/api/research \
  -H "Content-Type: application/json" \
  -d '{"question": "对公客户风险全景分析"}'

# 生成报告
curl -X POST http://localhost:8000/api/report \
  -H "Content-Type: application/json" \
  -d '{"template_id": "weekly_review", "variables": {"report_period": "2025-W26"}}'

# 生成看板
curl http://localhost:8000/api/dashboard
```

### 运行测试

```bash
pytest tests/ -v
pytest tests/test_scenarios.py -v   # 34 条场景全覆盖
```

## 全场景演示

覆盖 34 条业务能力场景（数据准备 → 沉淀类），每条场景配有独立数据与演示方案。

```bash
# 列出全部场景
python3 -m demo.run_scenarios --list

# 运行单条场景（如智能问数）
python3 -m demo.run_scenarios --id 1.1

# 按能力组运行
python3 -m demo.run_scenarios --group 问数类

# 运行全部 34 条
python3 -m demo.run_scenarios --all
```

详细场景说明见 [docs/SCENARIOS.md](docs/SCENARIOS.md)。

## 研发文档

- [研发计划（P0/P1/里程碑）](docs/RD_PLAN.md)
- [技术方案（模块实现与选型）](docs/TECHNICAL_DESIGN.md)
- [**本体论技术规格（T-Box/A-Box/V-Box）**](docs/ONTOLOGY_SPEC.md)
- [场景演示方案](docs/SCENARIOS.md)

### 本体化能力

```bash
# 导出 OWL Turtle
python3 -m aip.ontology.cli

# 查看语义 DDL Prompt
python3 -c "
from aip.ontology.factory import get_ontology_registry
from aip.ontology.prompt import SemanticDDLPromptBuilder
b = SemanticDDLPromptBuilder(get_ontology_registry())
print(b.build_semantic_ddl('aip:Dataset/customer_360'))
"
```

## MVP 能力覆盖

| 能力组 | MVP 实现 | 说明 |
|--------|----------|------|
| 数据准备 | ✅ | 数据集注册、CSV上传解析、SQL Workbench |
| 语义模型 | ✅ | YAML 配置指标/维度/口径 |
| 智能问数 | ✅ | 规则意图识别 + SQL 生成（可替换 LLM） |
| 多轮追问 | ✅ | 会话上下文 + 维度下钻 |
| 指标口径解释 | ✅ | 语义模型元数据召回 |
| 归因/对比 | ✅ | 维度归因 + 区域对比 |
| 图表生成 | ✅ | 折线/柱状/排行/漏斗/热力图 |
| HTML 看板 | ✅ | 可交互筛选器 + KPI + 图表 |
| 报告生成 | ✅ | 日报/周报/营销模板 |
| 可信约束 | ✅ | 证据引用、质检、Trace 回溯 |
| 资产沉淀 | ✅ | 收藏问数、参考样例、模板版本 |

## 技术栈

- **Python 3.10+**
- **DuckDB** — 内存分析引擎
- **Pandas** — 数据处理
- **Plotly** — 图表渲染
- **Jinja2** — HTML 模板
- **FastAPI** — REST API
- **Pydantic** — 数据校验

## 扩展方向

- 将 QueryAgent 规则匹配替换为企业 LLM Text2SQL
- 对接行内数仓与 BI 系统
- 增加权限控制与敏感数据脱敏
- 完善周期报告调度与多受众版本
- 接入 OpenTelemetry 全链路 Trace
