"""本体 CLI 工具."""

from aip.ontology.factory import ensure_ttl_export


def export_owl() -> None:
    path = ensure_ttl_export()
    print(f"OWL Turtle exported to: {path}")


if __name__ == "__main__":
    export_owl()
