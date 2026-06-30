"""数据集注册与 DataAgent 配置."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd


@dataclass
class DataAgentProfile:
    vectorized: bool = True
    update_mode: str = "full"  # full | incremental
    realtime_sync: bool = False
    sensitive_fields: list[str] = field(default_factory=list)


@dataclass
class Dataset:
    id: str
    name: str
    source_type: str  # table | bi | file
    table_name: str
    profile: DataAgentProfile = field(default_factory=DataAgentProfile)
    metadata: dict[str, Any] = field(default_factory=dict)


class DatasetRegistry:
    """管理持久化数据集与会话级临时数据."""

    def __init__(self, db_path: str = ":memory:"):
        self._conn = duckdb.connect(db_path)
        self._datasets: dict[str, Dataset] = {}

    @property
    def conn(self) -> duckdb.DuckDBPyConnection:
        return self._conn

    def register_csv(self, dataset: Dataset, csv_path: str | Path) -> None:
        path = Path(csv_path)
        self._conn.execute(
            f"CREATE OR REPLACE TABLE {dataset.table_name} AS SELECT * FROM read_csv_auto(?)",
            [str(path)],
        )
        schema = self._conn.execute(f"DESCRIBE {dataset.table_name}").fetchdf()
        dataset.metadata["columns"] = schema["column_name"].tolist()
        dataset.metadata["row_count"] = self._conn.execute(
            f"SELECT COUNT(*) FROM {dataset.table_name}"
        ).fetchone()[0]
        self._datasets[dataset.id] = dataset

    def register_dataframe(self, dataset: Dataset, df: pd.DataFrame) -> None:
        self._conn.register("tmp_df", df)
        self._conn.execute(f"CREATE OR REPLACE TABLE {dataset.table_name} AS SELECT * FROM tmp_df")
        self._conn.unregister("tmp_df")
        dataset.metadata["columns"] = list(df.columns)
        dataset.metadata["row_count"] = len(df)
        self._datasets[dataset.id] = dataset

    def get(self, dataset_id: str) -> Dataset | None:
        return self._datasets.get(dataset_id)

    def list_datasets(self) -> list[Dataset]:
        return list(self._datasets.values())

    def execute_sql(self, sql: str) -> pd.DataFrame:
        return self._conn.execute(sql).fetchdf()

    def preview(self, dataset_id: str, limit: int = 5) -> pd.DataFrame:
        dataset = self._datasets[dataset_id]
        return self._conn.execute(f"SELECT * FROM {dataset.table_name} LIMIT {limit}").fetchdf()
