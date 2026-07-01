"""OWL 双向同步服务 - YAML ↔ Turtle."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

import yaml

from aip.ontology.owl import TurtleSerializer
from aip.ontology.rdf_loader import RdfOntologyLoader
from aip.ontology.registry import OntologyRegistry


SyncDirection = Literal["yaml_to_ttl", "ttl_to_yaml", "diff"]


class OntologySyncService:
    """本体配置台核心：YAML 与 OWL Turtle 双向同步与差异检测."""

    def __init__(
        self,
        yaml_path: str | Path,
        ttl_path: str | Path,
        registry: OntologyRegistry | None = None,
    ):
        self.yaml_path = Path(yaml_path)
        self.ttl_path = Path(ttl_path)
        self.registry = registry or OntologyRegistry()
        if self.yaml_path.exists():
            self.registry.load(self.yaml_path)

    def status(self) -> dict[str, Any]:
        yaml_hash = _file_hash(self.yaml_path) if self.yaml_path.exists() else None
        ttl_hash = _file_hash(self.ttl_path) if self.ttl_path.exists() else None
        preview = TurtleSerializer(self.registry).serialize()
        preview_hash = hashlib.sha256(preview.encode()).hexdigest()[:16]
        in_sync = ttl_hash == preview_hash if ttl_hash and self.ttl_path.exists() else False
        ttl_summary = {}
        if self.ttl_path.exists():
            ttl_summary = RdfOntologyLoader(self.ttl_path).summary()
        return {
            "ontology_version": self.registry.version,
            "yaml_path": str(self.yaml_path),
            "ttl_path": str(self.ttl_path),
            "yaml_hash": yaml_hash,
            "ttl_hash": ttl_hash,
            "preview_hash": preview_hash,
            "in_sync": in_sync,
            "yaml_exists": self.yaml_path.exists(),
            "ttl_exists": self.ttl_path.exists(),
            "ttl_summary": ttl_summary,
            "metric_count": len({m.iri for m in self.registry._metrics.values() if getattr(m, "iri", "").startswith("aip:")}),
            "axiom_count": len(self.registry._axioms),
            "binding_count": len(self.registry._bindings),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    def preview_ttl(self) -> str:
        return TurtleSerializer(self.registry).serialize()

    def diff(self) -> dict[str, Any]:
        """比较 YAML 导出预览与磁盘 TTL 差异."""
        preview = self.preview_ttl()
        preview_hash = hashlib.sha256(preview.encode()).hexdigest()[:16]
        if not self.ttl_path.exists():
            return {
                "in_sync": False,
                "preview_hash": preview_hash,
                "ttl_hash": None,
                "changes": ["TTL 文件不存在，需执行 yaml_to_ttl 同步"],
                "preview_lines": len(preview.splitlines()),
            }

        on_disk = self.ttl_path.read_text(encoding="utf-8")
        ttl_hash = hashlib.sha256(on_disk.encode()).hexdigest()[:16]
        changes: list[str] = []
        if preview_hash != ttl_hash:
            preview_metrics = set(_extract_metric_ids(preview))
            disk_metrics = set(_extract_metric_ids(on_disk))
            added = preview_metrics - disk_metrics
            removed = disk_metrics - preview_metrics
            if added:
                changes.append(f"YAML 新增指标: {', '.join(sorted(added))}")
            if removed:
                changes.append(f"TTL 独有指标: {', '.join(sorted(removed))}")
            if not added and not removed:
                changes.append("指标集合一致，但序列化内容有差异（公式/公理/格式）")
        loader = RdfOntologyLoader(self.ttl_path)
        yaml_metrics = {m.iri for m in self.registry._metrics.values() if m.iri.startswith("aip:")}
        ttl_metrics = {m["iri"] for m in loader.extract_metrics()}
        only_ttl = ttl_metrics - yaml_metrics
        only_yaml = yaml_metrics - ttl_metrics
        if only_ttl:
            changes.append(f"TTL 可回写指标: {', '.join(sorted(only_ttl))}")
        if only_yaml:
            changes.append(f"仅 YAML 存在: {', '.join(sorted(only_yaml))}")

        return {
            "in_sync": preview_hash == ttl_hash and not only_ttl,
            "preview_hash": preview_hash,
            "ttl_hash": ttl_hash,
            "changes": changes or ["YAML 与 TTL 已同步"],
            "only_in_ttl": sorted(only_ttl),
            "only_in_yaml": sorted(only_yaml),
        }

    def sync(self, direction: SyncDirection, dry_run: bool = False) -> dict[str, Any]:
        if direction == "diff":
            return self.diff()

        if direction == "yaml_to_ttl":
            preview = self.preview_ttl()
            result: dict[str, Any] = {
                "direction": direction,
                "dry_run": dry_run,
                "bytes": len(preview.encode()),
                "lines": len(preview.splitlines()),
            }
            if not dry_run:
                self.ttl_path.parent.mkdir(parents=True, exist_ok=True)
                self.ttl_path.write_text(preview, encoding="utf-8")
                result["written_to"] = str(self.ttl_path)
            result["preview_hash"] = hashlib.sha256(preview.encode()).hexdigest()[:16]
            return result

        if direction == "ttl_to_yaml":
            if not self.ttl_path.exists():
                raise FileNotFoundError(f"TTL 不存在: {self.ttl_path}")
            loader = RdfOntologyLoader(self.ttl_path)
            with open(self.yaml_path, encoding="utf-8") as f:
                data = yaml.safe_load(f)

            merged = {
                "metrics_added": [],
                "axioms_added": [],
                "bindings_added": [],
                "conflicts": [],
            }
            existing_metrics = {m["iri"] for m in data.get("metrics", [])}
            for m in loader.extract_metrics():
                if m["iri"] not in existing_metrics:
                    merged["metrics_added"].append(m["iri"])
                    if not dry_run:
                        data.setdefault("metrics", []).append(m)

            existing_axioms = {a["id"] for a in data.get("axioms", [])}
            for a in loader.extract_axioms():
                if a["id"] not in existing_axioms:
                    merged["axioms_added"].append(a["id"])
                    if not dry_run:
                        data.setdefault("axioms", []).append(a)

            existing_bindings = {b["iri"] for b in data.get("dataset_bindings", [])}
            for b in loader.extract_dataset_bindings():
                if b["iri"] not in existing_bindings:
                    merged["bindings_added"].append(b["iri"])
                    if not dry_run:
                        data.setdefault("dataset_bindings", []).append(b)

            result = {
                "direction": direction,
                "dry_run": dry_run,
                **merged,
            }
            if not dry_run and any(merged[k] for k in ("metrics_added", "axioms_added", "bindings_added")):
                backup = self.yaml_path.with_suffix(".yaml.bak")
                backup.write_text(self.yaml_path.read_text(encoding="utf-8"), encoding="utf-8")
                with open(self.yaml_path, "w", encoding="utf-8") as f:
                    yaml.dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
                result["backup"] = str(backup)
                result["written_to"] = str(self.yaml_path)
                self.registry.load(self.yaml_path)
            return result

        raise ValueError(f"未知同步方向: {direction}")


def _file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode()).hexdigest()[:16]


def _extract_metric_ids(ttl: str) -> set[str]:
    ids: set[str] = set()
    for line in ttl.splitlines():
        if "aip:Metric_" in line and " a aip:Metric" in line:
            part = line.split("aip:Metric_")[1].split()[0]
            ids.add(part)
    return ids
