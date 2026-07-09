from __future__ import annotations

import argparse
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from zet.services.character_grid_service import CharacterGridOptions, CharacterGridService


def _image_for_order_name(input_dir: Path, name: str) -> Path:
    """Find an image in the input directory by stem."""
    matches = []
    for suffix in (".png", ".jpg", ".jpeg", ".webp"):
        candidate = input_dir / f"{name}{suffix}"
        if candidate.exists():
            matches.append(candidate)
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one image for ordered name '{name}', found {len(matches)}.")
    return matches[0]


def _resolve_input_paths(args: argparse.Namespace) -> list[Path]:
    """Resolve CLI image inputs from explicit paths or an ordered input directory."""
    if args.inputs:
        paths = [Path(value) for value in args.inputs]
        if args.order:
            by_stem = {path.stem: path for path in paths}
            missing = [name for name in args.order if name not in by_stem]
            if missing:
                raise ValueError(f"Ordered input names were not found: {', '.join(missing)}")
            return [by_stem[name] for name in args.order]
        return paths
    if not args.input_dir:
        raise ValueError("--input-dir or --inputs is required.")
    input_dir = Path(args.input_dir)
    if not input_dir.exists() or not input_dir.is_dir():
        raise ValueError(f"Input directory does not exist: {input_dir}")
    if len(args.order) != 8:
        raise ValueError("--order must contain exactly 8 image stems when using --input-dir.")
    return [_image_for_order_name(input_dir, name) for name in args.order]


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser for grid assembly."""
    parser = argparse.ArgumentParser(description="Assemble 8 character images into a normalized 4x2 turnaround grid.")
    parser.add_argument("--input-dir", default="")
    parser.add_argument("--inputs", nargs="*", default=[])
    parser.add_argument(
        "--order",
        nargs="*",
        default=[
            "front",
            "front_left_3_4",
            "left_profile",
            "back_left_3_4",
            "back",
            "back_right_3_4",
            "right_profile",
            "front_right_3_4",
        ],
    )
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--background-mode", choices=["auto", "fixed"], default="auto")
    parser.add_argument("--fixed-background-rgb", nargs=3, type=int, default=(128, 128, 128))
    parser.add_argument("--tolerance", type=float, default=20.0)
    parser.add_argument("--target-height-mode", choices=["median", "min", "max", "explicit"], default="median")
    parser.add_argument("--target-height", type=int)
    parser.add_argument("--outer-margin", type=int, default=60)
    parser.add_argument("--col-gap", type=int, default=30)
    parser.add_argument("--row-gap", type=int, default=40)
    parser.add_argument("--cell-padding-x", type=int, default=40)
    parser.add_argument("--cell-padding-y", type=int, default=40)
    parser.add_argument("--crop-height-percent", type=float)
    parser.add_argument("--crop-width-to-character", action="store_true")
    parser.add_argument("--diagnostics", dest="diagnostics", action="store_true", default=True)
    parser.add_argument("--no-diagnostics", dest="diagnostics", action="store_false")
    return parser


def options_from_args(args: argparse.Namespace) -> CharacterGridOptions:
    """Convert parsed CLI arguments into grid service options."""
    return CharacterGridOptions(
        background_mode=args.background_mode,
        fixed_background_rgb=tuple(args.fixed_background_rgb),
        tolerance=args.tolerance,
        target_height_mode=args.target_height_mode,
        target_height=args.target_height,
        outer_margin=args.outer_margin,
        col_gap=args.col_gap,
        row_gap=args.row_gap,
        cell_padding_x=args.cell_padding_x,
        cell_padding_y=args.cell_padding_y,
        crop_height_percent=args.crop_height_percent,
        crop_width_to_character=args.crop_width_to_character,
        diagnostics=args.diagnostics,
    )


def main() -> int:
    """Run character grid assembly from the command line."""
    args = build_parser().parse_args()
    paths = _resolve_input_paths(args)
    result = CharacterGridService().assemble_grid(paths, Path(args.output_dir), options_from_args(args))
    print(f"grid: {result.grid_path}")
    print(f"analysis: {result.analysis_path}")
    print(f"diagnostics: {result.diagnostics_path}")
    for item in result.results:
        print(
            f"{item.name}: source={item.source_width}x{item.source_height} "
            f"bbox={item.bbox} height={item.character_height} scale={item.scale_factor:.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
