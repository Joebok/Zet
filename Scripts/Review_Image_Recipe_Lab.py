#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if __package__ in {None, ""} and str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from zet.services.image_quality_review_service import ImageQualityReviewService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prefilter a Recipe Lab experiment with local vision QA.")
    parser.add_argument("experiment", type=Path)
    parser.add_argument("--model", default="vision-analysis:latest")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = ImageQualityReviewService(PROJECT_ROOT).review_experiment(
            args.experiment,
            model=args.model,
        )
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
