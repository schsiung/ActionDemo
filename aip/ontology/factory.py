"""本体工厂 - 全局默认 OntologyRegistry 与路径."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from aip.ontology.registry import OntologyRegistry
from aip.ontology.shacl_validator import ShaclValidator
from aip.ontology.task_graph import TaskGraphRegistry

ONTOLOGY_DIR = Path(__file__).parent.parent.parent / "demo" / "data" / "ontology"
DEFAULT_YAML = ONTOLOGY_DIR / "aip_core.yaml"
DEFAULT_TTL = ONTOLOGY_DIR / "aip_core.ttl"
DEFAULT_SHACL = ONTOLOGY_DIR / "shapes" / "pre_loan_screening.yaml"
DEFAULT_TASK_GRAPHS = ONTOLOGY_DIR / "task_graphs.yaml"
DEFAULT_DATASET_IRI = "aip:Dataset/customer_360"


@lru_cache(maxsize=1)
def get_ontology_registry() -> OntologyRegistry:
    reg = OntologyRegistry()
    if DEFAULT_YAML.exists():
        reg.load(DEFAULT_YAML)
    return reg


@lru_cache(maxsize=1)
def get_shacl_validator() -> ShaclValidator:
    return ShaclValidator(DEFAULT_SHACL, get_ontology_registry())


@lru_cache(maxsize=1)
def get_task_graph_registry() -> TaskGraphRegistry:
    reg = TaskGraphRegistry()
    if DEFAULT_TASK_GRAPHS.exists():
        reg.load(DEFAULT_TASK_GRAPHS)
    return reg


def ensure_ttl_export() -> Path:
    """确保 aip_core.ttl 与 YAML 同步."""
    from aip.ontology.owl import TurtleSerializer

    reg = get_ontology_registry()
    serializer = TurtleSerializer(reg)
    return serializer.write(DEFAULT_TTL)
