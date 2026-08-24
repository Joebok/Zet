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
    parser = argparse.ArgumentParser(description="Run a Prompt Evolution prompt through a local recipe matrix.")
    parser.add_argument("--prompt-json", type=Path, required=True)
    parser.add_argument("--reference-image", type=Path, required=True)
    parser.add_argument("--pose-image", type=Path)
    parser.add_argument("--checkpoint", action="append", required=True)
    parser.add_argument("--reference-weight", action="append", type=float, required=True)
    parser.add_argument("--seed", action="append", type=int, required=True)
    parser.add_argument(
        "--replace-positive",
        action="append",
        default=[],
        metavar="OLD=NEW",
        help="Apply a deterministic replacement to the positive prompt before rendering.",
    )
    parser.add_argument("--render-profile", default="image-recipe-lab-ipadapter-sdxl")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config.toml")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        prompt = json.loads(args.prompt_json.resolve().read_text(encoding="utf-8"))
        positive_prompt = str(prompt.get("positive_prompt") or "")
        for replacement in args.replace_positive:
            if "=" not in replacement:
                raise ValueError("--replace-positive must use OLD=NEW syntax.")
            old, new = replacement.split("=", 1)
            if old not in positive_prompt:
                raise ValueError(f"Positive prompt does not contain replacement text: {old}")
            positive_prompt = positive_prompt.replace(old, new)
        app = ZetApp.from_config(args.config.resolve())
        result = CheckpointLabService(app, PROJECT_ROOT).run_comfyui_prompt_matrix(
            positive_prompt=positive_prompt,
            negative_prompt=str(prompt.get("negative_prompt") or ""),
            reference_image=args.reference_image,
            pose_image=args.pose_image,
            render_profile=args.render_profile,
            checkpoints=args.checkpoint,
            reference_weights=args.reference_weight,
            seeds=args.seed,
            output_dir=args.output_dir,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
