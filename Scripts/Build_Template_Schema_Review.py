#!/usr/bin/env python3
from __future__ import annotations

import difflib
import json
import shutil
from pathlib import Path

from Scripts.Compile_Character_Template import load_template_sections
from Scripts.Run_Body_Reference_Jobs import compile_body_reference_job
from Scripts.Run_Character_Assembly_Jobs import compile_character_assembly_job
from Scripts.Run_Costume_Dressing_Jobs import compile_costume_dressing_job
from Scripts.Run_Head_Image_Jobs import compile_head_image_job


PROJECT_ROOT = Path(__file__).resolve().parents[1]
LIBRARY_ROOT = PROJECT_ROOT.parent / "Zet_Library"
REVIEW_ROOT = PROJECT_ROOT / "Docs" / "Template_Schema_Review"
VIEWS = ("FRONT", "FRONT_LEFT_3_4", "LEFT_PROFILE", "BACK_RIGHT_3_4")
DISPLAY = {token: token.title().replace("_", "-").replace("3-4", "3-4") for token in VIEWS}


def copy_after_structure() -> None:
    before_root = REVIEW_ROOT / "before" / "structure"
    after_root = REVIEW_ROOT / "after" / "structure"
    for before in before_root.rglob("*"):
        if not before.is_file():
            continue
        relative = before.relative_to(before_root)
        if relative.parts[0] == "repo":
            source = PROJECT_ROOT.joinpath(*relative.parts[1:])
        else:
            source = LIBRARY_ROOT / "Characters" / "Tsaeytte" / Path(*relative.parts[1:])
        target = after_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    extras = (
        PROJECT_ROOT / "Config" / "Prompt_Global_Sections.md",
        PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Character_Template_Instructions.md",
        PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Costume_Template_Instructions.md",
        PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Character_Retired_Sections.md",
        PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Costume_Template_Retired_Sections.md",
    )
    for source in extras:
        target = after_root / "repo" / source.relative_to(PROJECT_ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for source in (LIBRARY_ROOT / "Characters" / "Tsaeytte").rglob("*_Retired_Sections.md"):
        target = after_root / "library" / source.relative_to(LIBRARY_ROOT / "Characters" / "Tsaeytte")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def manifest(task: str, view_token: str) -> dict:
    root = LIBRARY_ROOT / "Pipelines" / "Tsaeytte" / "Elder" / task
    for path in root.rglob("dependency_manifest.json"):
        payload = json.loads(path.read_text(encoding="utf-8"))
        token = payload.get("view_token") or payload.get("body_view_token")
        if token == view_token and (task != "Costume-Dressing" or payload.get("costume_name") == "Everyday"):
            return payload
    raise FileNotFoundError(f"No {task} manifest for {view_token}")


def build_prompts() -> None:
    character = LIBRARY_ROOT / "Characters" / "Tsaeytte" / "Elder" / "Character.md"
    after_prompts = REVIEW_ROOT / "after" / "prompts"
    artifact_root = REVIEW_ROOT / "after" / "artifacts"
    compilers = {
        "Body-Reference": compile_body_reference_job,
        "Head-Image": compile_head_image_job,
        "Character-Assembly": compile_character_assembly_job,
        "Costume-Dressing": compile_costume_dressing_job,
    }
    for task, compiler in compilers.items():
        for view_token in VIEWS:
            output = artifact_root / task / DISPLAY[view_token]
            job = {
                "Job": f"Template_Review_{task}_{view_token}",
                "Task": task.lower(),
                "Character": "Tsaeytte",
                "Phase": "Elder",
                "Template Path": str(character),
                "Output Directory": str(output),
            }
            if task == "Body-Reference":
                job.update({"Body View": view_token, "Reference Files": []})
            else:
                saved = manifest(task, view_token)
                job["Reference Files"] = saved["resources"]
                if task == "Head-Image":
                    job["Head View"] = view_token
                elif task == "Character-Assembly":
                    job.update({"Body View": view_token, "Head View": view_token, "Assembly Style Mode": saved.get("assembly_style_mode", "MATCHED_STYLE")})
                else:
                    job.update({
                        "Body View": view_token,
                        "Head View": view_token,
                        "Costume": "Everyday",
                        "Costume Path": saved["costume_path"],
                    })
            result = compiler(job, PROJECT_ROOT)
            target = after_prompts / task / f"{DISPLAY[view_token]}.md"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(result["final_prompt"], target)


def write_diffs() -> None:
    diff_root = REVIEW_ROOT / "diffs"
    for before in (REVIEW_ROOT / "before" / "prompts").rglob("*.md"):
        relative = before.relative_to(REVIEW_ROOT / "before" / "prompts")
        after = REVIEW_ROOT / "after" / "prompts" / relative
        diff = difflib.unified_diff(
            before.read_text(encoding="utf-8").splitlines(keepends=True),
            after.read_text(encoding="utf-8").splitlines(keepends=True),
            fromfile=f"before/{relative.as_posix()}",
            tofile=f"after/{relative.as_posix()}",
        )
        target = diff_root / relative.with_suffix(".diff")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("".join(diff), encoding="utf-8")


def write_trees() -> None:
    for side in ("before", "after"):
        lines = [f"# {side.title()} Template Markers", ""]
        for path in sorted((REVIEW_ROOT / side / "structure").rglob("*.md")):
            try:
                names = list(load_template_sections(path))
            except Exception:
                continue
            lines.extend((f"## {path.relative_to(REVIEW_ROOT / side / 'structure').as_posix()}", "", *[f"- `{name}`" for name in names], ""))
        (REVIEW_ROOT / f"Trees_{side.title()}.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    copy_after_structure()
    build_prompts()
    write_diffs()
    write_trees()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
