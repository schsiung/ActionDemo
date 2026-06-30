# AIP 全场景演示方案

本文档为每一条能力场景提供：**业务场景说明**、**示例数据**、**演示命令**与**预期产出**。

## 快速使用

```bash
# 列出全部 34 条场景
python3 -m demo.run_scenarios --list

# 运行单条场景
python3 -m demo.run_scenarios --id 1.1

# 按能力组运行
python3 -m demo.run_scenarios --group 问数类

# 运行全部并导出结果
python3 -m demo.run_scenarios --all --export output/scenarios/results.json
```

## 数据资产目录

| 文件 | 用途 | 关联场景 |
|------|------|----------|
| `scenarios/customer_360.csv` | 客户全景（授信/风险/司法） | 问数、洞察、预警 |
| `scenarios/pre_loan_screening_list.csv` | 贷前筛查名单上传 | 0.1, 5.1 |
| `scenarios/judicial_signals.csv` | 司法案件信号 | 1.2, 5.2 |
| `scenarios/financial_reports.csv` | 财报与变动阈值 | 0.2, 3.3, 5.3 |
| `scenarios/post_loan_monitoring.csv` | 贷后巡检预警 | 2.x, 4.4, 6.1 |
| `scenarios/transaction_flow.csv` | 结算流水 | 2.3, 3.3, 5.3 |
| `scenarios/industry_benchmark.csv` | 行业/辖内对标 | 0.2, 2.3, 5.4 |
| `scenarios/marketing_whitelist.csv` | 营销白名单 | 1.4, 4.5, 4.6 |
| `scenarios/product_catalog.csv` | 产品目录 | 3.1 |
| `scenarios/bid_scoring.csv` | 投标评分对标 | 5.4 |
| `scenarios/risk_cases.csv` | 脱敏风险案例 | 6.2, 8.1, 8.3 |
| `scenarios/daily_activities.csv` | 日报活动记录 | 4.3 |
| `scenarios/related_party.csv` | 关联企业 | 1.2 |
| `scenarios/external_credit.csv` | 他行授信 | 5.4 |
| `scenarios/semantic_pre_loan.yaml` | 贷前语义模型 | 0.2, 1.x |
| `scenarios/semantic_post_loan.yaml` | 贷后语义模型 | 2.x |
| `scenarios/semantic_marketing.yaml` | 营销语义模型 | 1.4, 4.x |
| `scenarios/alert_rules.yaml` | 预警规则 | 6.1 |
| `knowledge/product_policy.md` | 产品政策知识库 | 1.1 |
| `knowledge/crr_rules.md` | CRR 规则知识库 | 1.1, 1.3 |
| `knowledge/operation_guide.md` | 操作规范 | 1.1 |

---

## 零、数据准备类

### 0.1 数据集接入与配置 (P0)

| 项 | 内容 |
|----|------|
| **中行场景** | 数字化人员预置主题数据集；客户经理上传筛查名单 Excel |
| **数据** | `customer_360.csv` + `pre_loan_screening_list.csv` |
| **演示** | `python3 -m demo.run_scenarios --id 0.1` |
| **动作** | 注册持久化数据集 → 模拟上传解析 → 质量初检 → 字段映射 |
| **产出** | 数据集元信息 + 上传预览 JSON |

### 0.2 语义模型与指标配置 (P0)

| 项 | 内容 |
|----|------|
| **中行场景** | CRR 等级、销贷比、财报变动阈值、行业对标口径 |
| **数据** | `semantic_pre_loan.yaml` + `financial_reports.csv` + `industry_benchmark.csv` |
| **演示** | `python3 -m demo.run_scenarios --id 0.2` |
| **动作** | 加载语义模型 → 解释销贷比/收入同比/CRR 口径 |
| **产出** | 指标公式 + 统计范围 + 对标样例 |

### 0.3 分析脚本编写与编辑 (P0)

| 项 | 内容 |
|----|------|
| **中行场景** | 上传数据后 SQL 微调，筛选触阈客户 |
| **数据** | `financial_reports.csv` |
| **演示** | `python3 -m demo.run_scenarios --id 0.3` |
| **动作** | Workbench 执行 SQL：`revenue_yoy_pct < -20` |
| **产出** | 盛达贸易、天宇建筑等财报恶化客户清单 |

---

## 一、问数类

### 1.1 智能问数与知识问答 (P0)

| 项 | 内容 |
|----|------|
| **中行场景** | 客户经理查授信贷后；年轻经理查产品政策 |
| **数据** | `customer_360.csv` + `knowledge/*.md` |
| **演示** | `python3 -m demo.run_scenarios --id 1.1` |
| **问数示例** | 「查询盛达贸易集团的授信贷后情况」「华东区域高风险客户」 |
| **知识示例** | 「CRR等级高于C级有什么限制」「科创e贷的产品政策」 |
| **产出** | 表格结果 + 知识库回答 + 来源引用 |

### 1.2 多轮追问分析 (P0)

| 项 | 内容 |
|----|------|
| **中行场景** | 贷前筛查：授信贷后 → 司法 → 按行业分布 |
| **演示** | `python3 -m demo.run_scenarios --id 1.2` |
| **追问链** | Q1 高风险客户摘要 → Q2 按行业分布 → 司法明细表 |
| **产出** | 3 轮递进结果 + 司法案件明细 |

### 1.3 指标口径解释 (P0)

| 项 | 内容 |
|----|------|
| **中行场景** | 财报变动 20%/41% 阈值、销贷比统计范围 |
| **演示** | `python3 -m demo.run_scenarios --id 1.3` |
| **产出** | 公式 + 时间窗口 + 业务描述 |

### 1.4 关联指标推荐 (P1)

| 项 | 内容 |
|----|------|
| **中行场景** | 白名单画像：园区/产业链/资金环 |
| **数据** | `marketing_whitelist.csv` |
| **演示** | `python3 -m demo.run_scenarios --id 1.4` |
| **产出** | 营销优先级 → 产业链评分、中标数等关联指标 |

---

## 二、看板类

### 2.1 Dashboard 设计与接入 (P0)

| 项 | 内容 |
|----|------|
| **中行场景** | 贷后巡检预警看板 |
| **数据** | `post_loan_monitoring.csv` + `transaction_flow.csv` |
| **演示** | `python3 -m demo.run_scenarios --id 2.1` |
| **产出** | `output/scenarios/dashboards/post_loan_dashboard.html` |

### 2.2 Dashboard 解读 (P0)

| 项 | 内容 |
|----|------|
| **中行场景** | 大额交易、流水降幅、负面舆情信号解读 |
| **演示** | `python3 -m demo.run_scenarios --id 2.2` |
| **产出** | 红/橙预警客户业务化文字解读 |

### 2.3 数据下钻分析 (P0)

| 项 | 内容 |
|----|------|
| **中行场景** | 预警 → 客户事实 → 月度流水 → 行业对照 |
| **演示** | `python3 -m demo.run_scenarios --id 2.3` |
| **产出** | 4 层下钻数据 + 流水归因 |

---

## 三、图表类

### 3.1 图表设计 (P0) | 3.2 图表生成 (P0) | 3.3 图表解读 (P0)

| 场景 | 演示命令 | 要点 |
|------|----------|------|
| 3.1 按目的选图 | `--id 3.1` | 趋势→折线、排名→排行、转化→漏斗 |
| 3.2 五类图生成 | `--id 3.2` | line/bar/rank/funnel/heatmap |
| 3.3 天宇建筑流水解读 | `--id 3.3` | 降幅32.5% + 财报阈值判断 |

---

## 四、报告类

### 4.1 报告模板 (P0)

| 模板 ID | 名称 | 受众 |
|---------|------|------|
| `marketing_onepager` | 行内营销一页纸 | 客户经理 |
| `customer_onepager` | 对客营销一页纸 | 客户 |
| `leader_brief` | 领导参阅 | 分支行领导 |
| `product_brochure` | 产品推荐材料 | 对客/触达 |
| `post_loan_report` | 贷后检查报告 | 客户经理 |
| `daily_ops` | 经营日报 | 客户经理 |
| `weekly_review` | 业务周报 | 分支行领导 |

演示：`python3 -m demo.run_scenarios --id 4.1`

### 4.2 单次大纲规划 (P0)

演示：`--id 4.2` → 输出「天宇建筑风险专项」章节规划

### 4.3 周期报告编排 (P0)

演示：`--id 4.3` → 生成日报 + 周报 HTML

### 4.4 报告变量化 (P1)

演示：`--id 4.4` → 按客户/机构/检查类型生成 2 份贷后报告

### 4.5 多受众版本 (P1)

演示：`--id 4.5` → 管理版/执行版/明细版

### 4.6 全套报告生成 (P0)

演示：`--id 4.6` → 行内+对客+领导参阅三份报告

---

## 五、洞察类

| ID | 场景 | 演示要点 | 产出 |
|----|------|----------|------|
| 5.1 | 贷前筛查任务规划 | `--id 5.1` | T1-T4 子任务图 |
| 5.2 | 风险画像+商机排序 | `--id 5.2` | 高风险要点 + 营销优先级 |
| 5.3 | 流水/风险归因 | `--id 5.3` | Top因子贡献率 |
| 5.4 | 同业对标+区域排位 | `--id 5.4` | 评分差距 + 区域排名 |

---

## 六、预警建议类

### 6.1 数据预警设计

| 规则 | 条件 | 等级 |
|------|------|------|
| 流水骤降 | flow_change ≤ -20% | 橙色 |
| 还款逾期 | overdue_days > 0 | 黄色 |
| 司法信号 | legal_cases ≥ 2 | 红色 |
| CRR-D级 | crr_level in D/E | 红色 |
| 收入骤降 | revenue_yoy ≤ -20% | 橙色 |

演示：`python3 -m demo.run_scenarios --id 6.1`

### 6.2 业务建议生成

演示：`--id 6.2` → 贷前材料清单 + 贷后处置 + 营销话术

---

## 七、可信类

| ID | 能力 | 演示要点 |
|----|------|----------|
| 7.1 | 质检 | 数字/口径一致性检查 |
| 7.2 | 受控生成 | 无数据→低置信；有口径→有证据 |
| 7.3 | 证据引用 | 结论绑定 SQL/数据集 |
| 7.4 | 过程回溯 | Query + DeepResearch 全 Trace |
| 7.5 | 低置信标注 | 缺失/过期/样本不足 limitations |

演示：`python3 -m demo.run_scenarios --group 可信类`

---

## 八、沉淀类

| ID | 能力 | 演示要点 |
|----|------|----------|
| 8.1 | 分析模板沉淀 | 收藏问数 + 参考路径 |
| 8.2 | 模板运营 | 版本发布 v1.1.0 |
| 8.3 | 参考样例 | 4 条脱敏风险案例 |
| 8.4 | 运营监测 | 成功率/采纳率指标 |

演示：`python3 -m demo.run_scenarios --group 沉淀类`

---

## 场景与能力组对照总表

| 编号 | 能力 | 组 | 优先级 | 核心数据 |
|------|------|-----|--------|----------|
| 0.1 | 数据集接入 | 数据准备 | P0 | customer_360, screening_list |
| 0.2 | 语义模型 | 数据准备 | P0 | semantic_pre_loan |
| 0.3 | 脚本编辑 | 数据准备 | P0 | financial_reports |
| 1.1 | 问数+知识 | 问数 | P0 | customer_360, knowledge |
| 1.2 | 多轮追问 | 问数 | P0 | customer_360, judicial |
| 1.3 | 口径解释 | 问数 | P0 | semantic_pre_loan |
| 1.4 | 指标推荐 | 问数 | P1 | marketing_whitelist |
| 2.1 | 看板生成 | 看板 | P0 | post_loan, flow |
| 2.2 | 看板解读 | 看板 | P0 | post_loan |
| 2.3 | 下钻分析 | 看板 | P0 | post_loan, flow, benchmark |
| 3.1 | 图表设计 | 图表 | P0 | marketing, products |
| 3.2 | 图表生成 | 图表 | P0 | customer_360 |
| 3.3 | 图表解读 | 图表 | P0 | flow, financial |
| 4.1 | 报告模板 | 报告 | P0 | 7套模板 |
| 4.2 | 大纲规划 | 报告 | P0 | customer_360 |
| 4.3 | 周期编排 | 报告 | P0 | daily_activities |
| 4.4 | 变量化 | 报告 | P1 | post_loan |
| 4.5 | 多受众 | 报告 | P1 | marketing |
| 4.6 | 报告生成 | 报告 | P0 | marketing, customer_360 |
| 5.1 | 任务规划 | 洞察 | P0 | screening, customer_360 |
| 5.2 | 洞察归纳 | 洞察 | P0 | customer_360, marketing |
| 5.3 | 波动归因 | 洞察 | P0 | flow, financial |
| 5.4 | 多维对比 | 洞察 | P0 | benchmark, bid_scoring |
| 6.1 | 预警设计 | 预警 | P0 | alert_rules |
| 6.2 | 业务建议 | 预警 | P0 | risk_cases |
| 7.1-7.5 | 可信类 | 可信 | P0 | 横切全链路 |
| 8.1-8.4 | 沉淀类 | 沉淀 | P1 | assets center |
