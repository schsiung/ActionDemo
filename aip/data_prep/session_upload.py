"""会话内文件上传、解析、质量初检与字段映射."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from aip.data_prep.dataset_registry import DataAgentProfile, Dataset, DatasetRegistry


class SessionUploadService:
    """处理 Excel/CSV 上传，作为当次会话临时分析数据."""

    def __init__(self, registry: DatasetRegistry, session_id: str):
        self.registry = registry
        self.session_id = session_id
        self._uploads: list[dict[str, Any]] = []

    def parse_file(self, file_path: str | Path, sheet: str | int = 0) -> dict[str, Any]:
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix == ".csv":
            df = pd.read_csv(path)
            sheets = {"default": df}
        elif suffix in {".xlsx", ".xls"}:
            sheets = pd.read_excel(path, sheet_name=None)
            if isinstance(sheet, int):
                sheet_name = list(sheets.keys())[sheet]
            else:
                sheet_name = sheet
            sheets = {sheet_name: sheets[sheet_name]}
        else:
            raise ValueError(f"不支持的文件格式: {suffix}")

        results = []
        for sheet_name, df in sheets.items():
            quality = self._quality_check(df)
            mapping = {col: col for col in df.columns}
            preview = df.head(5).to_dict(orient="records")

            upload_id = f"upload_{self.session_id}_{len(self._uploads)}"
            dataset = Dataset(
                id=upload_id,
                name=f"会话上传-{path.name}-{sheet_name}",
                source_type="file",
                table_name=f"tmp_{upload_id}",
                profile=DataAgentProfile(vectorized=False),
                metadata={"session": self.session_id, "original_file": path.name},
            )
            self.registry.register_dataframe(dataset, df)

            item = {
                "upload_id": upload_id,
                "sheet": sheet_name,
                "columns": list(df.columns),
                "preview": preview,
                "quality": quality,
                "field_mapping": mapping,
                "row_count": len(df),
            }
            self._uploads.append(item)
            results.append(item)

        return {"session_id": self.session_id, "uploads": results}

    def confirm_mapping(self, upload_id: str, mapping: dict[str, str]) -> dict[str, Any]:
        upload = next((u for u in self._uploads if u["upload_id"] == upload_id), None)
        if not upload:
            raise ValueError(f"上传记录不存在: {upload_id}")
        upload["field_mapping"] = mapping
        upload["confirmed"] = True
        return upload

    @staticmethod
    def _quality_check(df: pd.DataFrame) -> dict[str, Any]:
        null_counts = df.isnull().sum().to_dict()
        duplicate_rows = int(df.duplicated().sum())
        issues = []
        for col, cnt in null_counts.items():
            if cnt > 0:
                issues.append(f"列 '{col}' 存在 {cnt} 个空值")
        if duplicate_rows > 0:
            issues.append(f"存在 {duplicate_rows} 行重复记录")
        return {
            "null_counts": null_counts,
            "duplicate_rows": duplicate_rows,
            "issues": issues,
            "passed": len(issues) == 0,
        }
