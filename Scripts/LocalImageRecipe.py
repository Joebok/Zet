#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if __package__ in {None, ""} and str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from zet.app import ZetApp
from zet.services.checkpoint_lab_service import CheckpointLabService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compile a one-character local image API recipe.")
    parser.add_argument("--character", required=True)
    parser.add_argument("--phase", required=True)
    parser.add_argument("--view", required=True)
    parser.add_argument("--costume", required=True)
    parser.add_argument("--image-generation", required=True)
    parser.add_argument("--render-profile", required=True)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config.toml")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--seed", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        app = ZetApp.from_config(args.config.resolve())
        result = CheckpointLabService(app, PROJECT_ROOT).local_image_recipe(
            character=args.character,
            phase=args.phase,
            view=args.view,
            costume=args.costume,
            image_generation=args.image_generation,
            render_profile=args.render_profile,
            output_path=args.output,
            seed=args.seed,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
