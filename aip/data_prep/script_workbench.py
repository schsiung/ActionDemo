"""分析脚本 Workbench - SQL/Python 执行与预览."""

from __future__ import annotations

from typing import Any

import pandas as pd

from aip.data_prep.dataset_registry import DatasetRegistry


class ScriptWorkbench:
    """对数据集或上传文件编写/执行 SQL 或 Python 脚本."""

    def __init__(self, registry: DatasetRegistry):
        self.registry = registry
        self._history: list[dict[str, Any]] = []

    def execute_sql(self, sql: str) -> dict[str, Any]:
        try:
            df = self.registry.execute_sql(sql)
            result = {
                "success": True,
                "sql": sql,
                "columns": list(df.columns),
                "rows": df.to_dict(orient="records"),
                "row_count": len(df),
                "error": None,
            }
        except Exception as e:
            result = {
                "success": False,
                "sql": sql,
                "columns": [],
                "rows": [],
                "row_count": 0,
                "error": str(e),
            }
        self._history.append(result)
        return result

    def execute_python(self, code: str, input_df: pd.DataFrame | None = None) -> dict[str, Any]:
        """受限 Python 执行环境，仅暴露 pandas/numpy 与输入 DataFrame."""
        import numpy as np

        local_vars: dict[str, Any] = {"pd": pd, "np": np, "df": input_df}
        try:
            exec(code, {"__builtins__": {}}, local_vars)
            result_df = local_vars.get("result")
            if result_df is None:
                result_df = local_vars.get("df")
            if not isinstance(result_df, pd.DataFrame):
                raise ValueError("脚本须将结果赋值给 result 变量 (DataFrame)")
            return {
                "success": True,
                "columns": list(result_df.columns),
                "rows": result_df.to_dict(orient="records"),
                "row_count": len(result_df),
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "columns": [],
                "rows": [],
                "row_count": 0,
                "error": str(e),
            }
