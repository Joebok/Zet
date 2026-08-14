from __future__ import annotations

import json
from pathlib import Path

from zet.services.prompt_template_service import PromptTemplateService


def safe_filename_fragment(value: str, fallback: str) -> str:
    text = str(value or "").strip()
    return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in text).strip("-") or fallback


def write_json_file(path: Path, payload: object, *, ensure_ascii: bool = False) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=ensure_ascii) + "\n", encoding="utf-8")


def bundle_output_paths(output_dir: Path, files: dict, defaults: dict[str, str]) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    return {key: output_dir / files.get(key, default) for key, default in defaults.items()}


def select_prompt_sections(
    project_root: Path,
    bundle: dict,
    all_sections: dict[str, str],
    section_sources: dict[str, dict],
    view_token: str,
):
    return PromptTemplateService(project_root).select_sections(bundle, all_sections, section_sources, view_token)


def render_static_prompt_artifacts(
    *,
    project_root: Path,
    bundle: dict,
    final_prompt_path: Path,
    source_map_path: Path,
    compiled_sections_path: Path,
    metadata: dict,
    metadata_values: dict,
    metadata_sources: dict,
    selection: object,
    required_section_names: list[str],
    view_token: str,
    ensure_ascii_source_map: bool = False,
) -> str:
    return PromptTemplateService(project_root).render_artifacts(
        bundle=bundle,
        final_prompt_path=final_prompt_path,
        source_map_path=source_map_path,
        compiled_sections_path=compiled_sections_path,
        metadata=metadata,
        metadata_values=metadata_values,
        metadata_sources=metadata_sources,
        selection=selection,
        required_section_names=required_section_names,
        view_token=view_token,
        ensure_ascii_source_map=ensure_ascii_source_map,
    )
