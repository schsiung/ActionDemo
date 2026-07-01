# Hermes 智能对话演示指南

Hermes 是 AIP 平台的**智能对话入口**，可在对话中完整演示全部 **34 个业务场景**，覆盖数据准备、问数、看板、图表、报告、洞察、预警、可信与沉淀九大能力组。

## 快速启动

```bash
pip install -e ".[dev]"
python3 -m demo.api
```

浏览器打开：

- **Hermes 对话界面**：http://localhost:8000/hermes
- **API 文档**：http://localhost:8000/docs
- **本体配置台**：http://localhost:8000/ontology/console

## 对话指令示例

| 用户说法 | Hermes 行为 |
|----------|-------------|
| `帮助` / `场景列表` | 列出 34 个场景 |
| `开始导览` | 从 0.1 起逐步演示 |
| `下一个场景` | 导览前进 |
| `运行场景 5.1` | 执行指定场景 |
| `演示全部` | 批量运行 34 场景并汇总 |
| `运行问数类` | 执行问数类 4 个场景 |
| `查询华东高风险客户` | QueryAgent 智能问数 |
| `贷前筛查任务规划` | 路由至场景 5.1 |
| `生成贷后巡检看板` | 路由至场景 2.1 |

## API

```bash
curl -X POST http://localhost:8000/api/hermes/chat \
  -H 'Content-Type: application/json' \
  -d '{"message":"开始导览"}'
```

## 架构

```
用户对话 → HermesRouter → HermesService → ScenarioExecutor / QueryAgent / DeepResearchAgent
```

与 `aip-scenarios` CLI 共用 `scenario_registry.yaml`，演示结果一致。
