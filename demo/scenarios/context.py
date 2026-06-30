"""场景演示上下文 - 加载全部数据集与 Agent."""

from __future__ import annotations

from pathlib import Path

import yaml

from aip.agents.deep_research_agent import DeepResearchAgent
from aip.agents.query_agent import QueryAgent
from aip.alert.rules import AlertEngine
from aip.assets.center import AssetCenter
from aip.data_prep.dataset_registry import DataAgentProfile, Dataset, DatasetRegistry
from aip.data_prep.script_workbench import ScriptWorkbench
from aip.data_prep.session_upload import SessionUploadService
from aip.knowledge.rag import KnowledgeEngine
from aip.semantic.model import SemanticModel, load_semantic_model

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
SCENARIO_DIR = DATA_DIR / "scenarios"
KNOWLEDGE_DIR = DATA_DIR / "knowledge"
OUTPUT_DIR = Path("output/scenarios")


# 数据集注册映射
DATASET_MAP = {
    "customer_360": ("ds_customer_360", "customer_360", "客户全景数据集"),
    "pre_loan_screening_list": ("ds_screening", "screening_list", "筛查名单"),
    "judicial_signals": ("ds_judicial", "judicial_signals", "司法信号"),
    "financial_reports": ("ds_financial", "financial_reports", "财报数据"),
    "post_loan_monitoring": ("ds_post_loan", "post_loan_monitoring", "贷后巡检"),
    "transaction_flow": ("ds_flow", "transaction_flow", "流水数据"),
    "industry_benchmark": ("ds_benchmark", "industry_benchmark", "行业对标"),
    "marketing_whitelist": ("ds_marketing", "marketing_whitelist", "营销白名单"),
    "product_catalog": ("ds_products", "product_catalog", "产品目录"),
    "bid_scoring": ("ds_bid", "bid_scoring", "投标评分"),
    "risk_cases": ("ds_cases", "risk_cases", "风险案例"),
    "daily_activities": ("ds_daily", "daily_activities", "日报活动"),
    "related_party": ("ds_related", "related_party", "关联企业"),
    "external_credit": ("ds_ext_credit", "external_credit", "他行授信"),
}


class ScenarioContext:
    """全局场景演示上下文，一次性加载所有数据集."""

    def __init__(self):
        self.registry = DatasetRegistry()
        self.assets = AssetCenter()
        self.knowledge = KnowledgeEngine(KNOWLEDGE_DIR)
        self.alert_engine = AlertEngine(SCENARIO_DIR / "alert_rules.yaml")
        self._agents: dict[str, QueryAgent] = {}
        self._deep_agents: dict[str, DeepResearchAgent] = {}
        self._semantics: dict[str, SemanticModel] = {}
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        self._load_all_datasets()
        self._load_semantic_models()

    def _load_all_datasets(self) -> None:
        for file_key, (ds_id, table_name, name) in DATASET_MAP.items():
            csv_path = SCENARIO_DIR / f"{file_key}.csv"
            if csv_path.exists():
                ds = Dataset(
                    id=ds_id,
                    name=name,
                    source_type="table",
                    table_name=table_name,
                    profile=DataAgentProfile(vectorized=True, update_mode="full"),
                )
                self.registry.register_csv(ds, csv_path)

    def _load_semantic_models(self) -> None:
        for yaml_file in SCENARIO_DIR.glob("semantic_*.yaml"):
            model = load_semantic_model(yaml_file)
            self._semantics[model.id] = model

    def get_semantic(self, key: str = "semantic_pre_loan") -> SemanticModel:
        path = SCENARIO_DIR / f"{key}.yaml"
        if path.exists():
            return load_semantic_model(path)
        return load_semantic_model(SCENARIO_DIR / "semantic_pre_loan.yaml")

    def get_query_agent(self, table: str = "customer_360", semantic_key: str = "semantic_pre_loan") -> QueryAgent:
        cache_key = f"{table}_{semantic_key}"
        if cache_key not in self._agents:
            semantic = self.get_semantic(semantic_key)
            table_name = DATASET_MAP.get(table, ("", table, ""))[1]
            self._agents[cache_key] = QueryAgent(self.registry, semantic, table_name)
        return self._agents[cache_key]

    def get_deep_agent(self, table: str = "customer_360", semantic_key: str = "semantic_pre_loan") -> DeepResearchAgent:
        cache_key = f"{table}_{semantic_key}"
        if cache_key not in self._deep_agents:
            semantic = self.get_semantic(semantic_key)
            table_name = DATASET_MAP.get(table, ("", table, ""))[1]
            self._deep_agents[cache_key] = DeepResearchAgent(self.registry, semantic, table_name)
        return self._deep_agents[cache_key]

    def workbench(self) -> ScriptWorkbench:
        return ScriptWorkbench(self.registry)

    def upload_service(self, session_id: str = "scenario") -> SessionUploadService:
        return SessionUploadService(self.registry, session_id)

    def query_table(self, table: str, sql: str) -> list[dict]:
        return self.registry.execute_sql(sql).to_dict(orient="records")

    def load_registry(self) -> list[dict]:
        with open(SCENARIO_DIR / "scenario_registry.yaml", encoding="utf-8") as f:
            return yaml.safe_load(f)["scenarios"]
