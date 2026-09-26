from __future__ import annotations

import json
from pathlib import Path

from zet.services.prompt_template_service import PromptTemplateService
from zet.services.chatgpt_prompt_contract import (
    build_image_inputs,
    enrich_reference_files,
    manifest_contract,
    prompt_contract_values,
    write_prompt_diagnostics,
)


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
    *,
    prompt_variant: str = "generation",
    pipeline_mode: str = "traditional",
):
    return PromptTemplateService(project_root).select_sections(
        bundle, all_sections, section_sources, view_token, prompt_variant=prompt_variant,
        pipeline_mode=pipeline_mode,
    )


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
    prompt_variant: str = "generation",
    pipeline_mode: str = "traditional",
    image_inputs: list[dict] | None = None,
) -> str:
    service = PromptTemplateService(project_root)
    prompt_text = service.render_artifacts(
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
        prompt_variant=prompt_variant,
        pipeline_mode=pipeline_mode,
        image_inputs=image_inputs,
    )
    legacy_template = str(bundle.get("legacy_static_prompt_template") or "").strip()
    if legacy_template:
        legacy_bundle = {**bundle, "static_prompt_template": legacy_template}
        service.render_artifacts(
            bundle=legacy_bundle,
            final_prompt_path=final_prompt_path.with_name(f"{final_prompt_path.stem}_V1{final_prompt_path.suffix}"),
            source_map_path=source_map_path.with_name(f"{source_map_path.stem}_V1{source_map_path.suffix}"),
            compiled_sections_path=compiled_sections_path.with_name(
                f"{compiled_sections_path.stem}_V1{compiled_sections_path.suffix}"
            ),
            metadata={**metadata, "prompt_schema_version": 1},
            metadata_values=metadata_values,
            metadata_sources=metadata_sources,
            selection=selection,
            required_section_names=required_section_names,
            view_token=view_token,
            ensure_ascii_source_map=ensure_ascii_source_map,
            prompt_variant=prompt_variant,
            pipeline_mode=pipeline_mode,
            image_inputs=image_inputs,
        )
    return prompt_text


def prepare_chatgpt_prompt_contract(
    references: list[dict], *, render_mode: str, default_role: str = "subject_reference"
) -> tuple[list[dict], list[dict], dict[str, str], dict]:
    """Return ordered legacy references, image inputs, template values, and manifest fields."""
    image_inputs = build_image_inputs(
        references,
        render_mode=render_mode,
        default_role=default_role,
    )
    return (
        enrich_reference_files(references, image_inputs),
        image_inputs,
        prompt_contract_values(render_mode, image_inputs),
        manifest_contract(render_mode, image_inputs),
    )


def finalize_chatgpt_prompt(
    diagnostics_path: Path,
    prompt_text: str,
    image_inputs: list[dict],
    render_mode: str,
) -> dict:
    return write_prompt_diagnostics(diagnostics_path, prompt_text, image_inputs, render_mode)
