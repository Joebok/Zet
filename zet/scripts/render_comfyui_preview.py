from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
from pathlib import Path
import sys

from zet.services.comfyui_render_service import compile_ir_to_comfyui_workflow, run_comfyui_workflow
from zet.services.config_service import ConfigService


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Compile and run a local ComfyUI preview from Scene_Render_IR.json.")
    parser.add_argument("scene_render_ir", type=Path)
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    parser.add_argument("--profile", default="")
    parser.add_argument("--checkpoint", default="")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--compile-only", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config_path = args.config.resolve()
        config = ConfigService.load(config_path)
        ir_path = args.scene_render_ir.resolve()
        ir_bytes = ir_path.read_bytes()
        ir = json.loads(ir_bytes.decode("utf-8-sig"))
        profile_name = args.profile or config.comfyui_profile
        profiles_path = config_path.parent / "Config" / "Local_Render_Presets.json"
        profiles = json.loads(profiles_path.read_text(encoding="utf-8"))
        profile = profiles.get(profile_name) if isinstance(profiles, dict) else None
        if not isinstance(profile, dict) or profile.get("backend") != "comfyui":
            raise ValueError(f"Unknown ComfyUI render profile: {profile_name}")
        checkpoint = args.checkpoint or config.comfyui_checkpoint
        scene_slug = str(ir.get("scene", {}).get("slug") or "Scene")
        compilation = compile_ir_to_comfyui_workflow(
            ir,
            profile,
            checkpoint=checkpoint,
            positive_prompt_globals=config.comfyui_positive_prompt_globals,
            negative_prompt_globals=config.comfyui_negative_prompt_globals,
            seed=args.seed,
            output_prefix=f"Zet/{scene_slug}",
        )
        output_dir = (args.output_dir or ir_path.parent).resolve()
        workflow_path = output_dir / "ComfyUI_Workflow_API.json"
        _write_json(workflow_path, compilation.workflow)
        print(f"Wrote {workflow_path}")
        if args.compile_only:
            return 0

        started_at = datetime.now()
        render_dir = output_dir / str(profile.get("output_subdir") or "Local_Test_Renders")
        result = run_comfyui_workflow(
            compilation.workflow,
            server_url=config.comfyui_server_url,
            output_dir=render_dir,
            poll_seconds=config.comfyui_poll_seconds,
            timeout_seconds=config.comfyui_timeout_seconds,
        )
        completed_at = datetime.now()
        metadata_path = render_dir / "ComfyUI_Render_Metadata.json"
        _write_json(metadata_path, {
            "created_at": completed_at.isoformat(timespec="seconds"),
            "started_at": started_at.isoformat(timespec="seconds"),
            "elapsed_seconds": round((completed_at - started_at).total_seconds(), 3),
            "backend": "comfyui",
            "profile": profile_name,
            "profile_settings": profile,
            "server_url": config.comfyui_server_url,
            "checkpoint": checkpoint,
            "scene_render_ir": str(ir_path),
            "scene_render_ir_sha256": hashlib.sha256(ir_bytes).hexdigest(),
            "prompts": compilation.prompts,
            "seed": compilation.seed,
            "width": compilation.width,
            "height": compilation.height,
            "prompt_id": result.prompt_id,
            "status": "SUCCESS",
            "outputs": result.outputs,
            "images": [str(path) for path in result.image_paths],
        })
        print(f"Wrote {metadata_path}")
        for image_path in result.image_paths:
            print(f"Downloaded {image_path}")
        return 0
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
