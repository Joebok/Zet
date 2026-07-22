from __future__ import annotations

import json
from pathlib import Path


def safe_filename_fragment(value: str, fallback: str) -> str:
    text = str(value or "").strip()
    return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in text).strip("-") or fallback


def write_json_file(path: Path, payload: object, *, ensure_ascii: bool = False) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=ensure_ascii) + "\n", encoding="utf-8")


def bundle_output_paths(output_dir: Path, files: dict, defaults: dict[str, str]) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    return {key: output_dir / files.get(key, default) for key, default in defaults.items()}


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
    from Scripts.Build_Static_Final_Prompt import prompt_template_path, render_static_prompt_with_source_map, write_compiled_sections

    template_file = prompt_template_path(project_root, str(bundle.get("static_prompt_template", "")))
    prompt_text, source_map = render_static_prompt_with_source_map(
        template_file.read_text(encoding="utf-8"),
        template_path=template_file,
        metadata=metadata_values,
        metadata_sources=metadata_sources,
        selection=selection,
        required_section_names=required_section_names,
        view_token=view_token,
        final_prompt_name=final_prompt_path.name,
    )
    final_prompt_path.write_text(prompt_text, encoding="utf-8")
    write_json_file(source_map_path, {**source_map, **metadata}, ensure_ascii=ensure_ascii_source_map)
    write_compiled_sections(compiled_sections_path, job_metadata=metadata, view_token=view_token, selection=selection)
    return prompt_text
