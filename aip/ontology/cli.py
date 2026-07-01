"""本体 CLI 工具."""

from __future__ import annotations

import argparse

from aip.ontology.factory import clear_ontology_caches, ensure_ttl_export, get_sync_service


def export_owl() -> None:
    path = ensure_ttl_export()
    print(f"OWL Turtle exported to: {path}")


def sync_ontology(direction: str = "yaml_to_ttl", dry_run: bool = False) -> None:
    service = get_sync_service()
    result = service.sync(direction, dry_run=dry_run)  # type: ignore[arg-type]
    if direction == "diff":
        print("Diff:", result.get("in_sync"), result.get("changes"))
    else:
        print(f"Sync {direction} (dry_run={dry_run}):", result)
    if not dry_run and direction in ("yaml_to_ttl", "ttl_to_yaml"):
        clear_ontology_caches()


def main() -> None:
    parser = argparse.ArgumentParser(description="AIP 本体工具")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("export", help="导出 YAML → TTL")
    sync_p = sub.add_parser("sync", help="双向同步")
    sync_p.add_argument(
        "--direction",
        choices=["yaml_to_ttl", "ttl_to_yaml", "diff"],
        default="yaml_to_ttl",
    )
    sync_p.add_argument("--dry-run", action="store_true")

    args = parser.parse_args()
    if args.command == "sync":
        sync_ontology(args.direction, args.dry_run)
    else:
        export_owl()


if __name__ == "__main__":
    main()
