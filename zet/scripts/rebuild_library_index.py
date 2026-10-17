import argparse
import json
from pathlib import Path

from zet.services.config_service import ConfigService
from zet.services.library_index_service import LibraryIndexService
from zet.services.universe_service import UniverseService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild the machine-local Zet library index.")
    parser.add_argument("--config", default="config.toml", help="Path to the Zet config.toml file.")
    parser.add_argument("--index-root", help="Override the machine-local index directory (primarily for tests).")
    parser.add_argument("--universe", help="Rebuild one explicitly named universe; defaults to the saved selection.")
    parser.add_argument("--all-universes", action="store_true", help="Rebuild every discovered universe.")
    return parser


def rebuild_indexes(config, config_path: str, *, index_root: str | None = None,
                    universe_id: str | None = None, all_universes: bool = False) -> list[dict]:
    project_root = Path(config_path).resolve().parent
    selection_path = config.state_file(project_root, "universe-selection.json")
    universes = UniverseService(config.base_library_path, selection_path)
    if universe_id:
        targets = [universes.get_universe(universe_id)]
    elif all_universes:
        targets = universes.list_universes()
        if not targets:
            raise ValueError(f"No universes found under {config.base_library_path}")
    else:
        selected = universes.selection()
        targets = [universes.get_universe(selected)]
    reports = []
    for item in targets:
        bound = universes.bind_config(config, item["universe_id"])
        report = LibraryIndexService(bound, index_root=index_root, project_root=project_root).rebuild()
        report["universe_id"] = item["universe_id"]
        reports.append(report)
    return reports


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = ConfigService.load(args.config)
    reports = rebuild_indexes(config, args.config, index_root=args.index_root,
                              universe_id=args.universe, all_universes=args.all_universes)
    print(json.dumps({"universes": reports}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
