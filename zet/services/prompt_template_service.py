from __future__ import annotations

import json
from pathlib import Path

from Scripts.Build_Static_Final_Prompt import prompt_template_path, render_static_prompt_with_source_map, write_compiled_sections
from Scripts.Compile_Character_Template import (
    TemplateCompileError,
    load_template_sections_with_sources,
    select_sections_for_prompt,
)


def filter_prompt_variant_blocks(template_text: str, prompt_variant: str) -> str:
    """Keep shared text and blocks marked for the requested prompt variant."""
    if prompt_variant not in {"generation", "analysis"}:
        raise ValueError(f"Unsupported prompt variant: {prompt_variant}")
    selected_marker = "IMAGE_PROMPT_ONLY" if prompt_variant == "generation" else "ANALYSIS_PROMPT_ONLY"
    active_marker = None
    output = []
    for line in template_text.splitlines(keepends=True):
        marker = line.strip()
        if marker in {"<!-- ZET:BEGIN IMAGE_PROMPT_ONLY -->", "<!-- ZET:BEGIN ANALYSIS_PROMPT_ONLY -->"}:
            if active_marker is not None:
                raise TemplateCompileError("INVALID_PROMPT_VARIANT_BLOCK", "Prompt variant blocks cannot be nested.")
            active_marker = marker.removeprefix("<!-- ZET:BEGIN ").removesuffix(" -->")
            continue
        if marker in {"<!-- ZET:END IMAGE_PROMPT_ONLY -->", "<!-- ZET:END ANALYSIS_PROMPT_ONLY -->"}:
            closing_marker = marker.removeprefix("<!-- ZET:END ").removesuffix(" -->")
            if active_marker != closing_marker:
                raise TemplateCompileError("INVALID_PROMPT_VARIANT_BLOCK", "Prompt variant block has a mismatched end tag.")
            active_marker = None
            continue
        if active_marker is None or active_marker == selected_marker:
            output.append(line)
    if active_marker is not None:
        raise TemplateCompileError("INVALID_PROMPT_VARIANT_BLOCK", "Prompt variant block has no end tag.")
    return "".join(output)


def filter_pipeline_mode_blocks(template_text: str, pipeline_mode: str) -> str:
    """Keep shared text and blocks marked for the selected pipeline mode."""
    if pipeline_mode not in {"traditional", "local"}:
        raise ValueError(f"Unsupported pipeline mode: {pipeline_mode}")
    selected = "LOCAL_PIPELINE_ONLY" if pipeline_mode == "local" else "TRADITIONAL_PIPELINE_ONLY"
    active: str | None = None
    output: list[str] = []
    for line in template_text.splitlines(keepends=True):
        marker = line.strip()
        if marker in {"<!-- ZET:BEGIN LOCAL_PIPELINE_ONLY -->", "<!-- ZET:BEGIN TRADITIONAL_PIPELINE_ONLY -->"}:
            if active is not None:
                raise TemplateCompileError("INVALID_PIPELINE_MODE_BLOCK", "Pipeline mode blocks cannot be nested.")
            active = marker.removeprefix("<!-- ZET:BEGIN ").removesuffix(" -->")
            continue
        if marker in {"<!-- ZET:END LOCAL_PIPELINE_ONLY -->", "<!-- ZET:END TRADITIONAL_PIPELINE_ONLY -->"}:
            closing = marker.removeprefix("<!-- ZET:END ").removesuffix(" -->")
            if active != closing:
                raise TemplateCompileError("INVALID_PIPELINE_MODE_BLOCK", "Pipeline mode block has a mismatched end tag.")
            active = None
            continue
        if active is None or active == selected:
            output.append(line)
    if active is not None:
        raise TemplateCompileError("INVALID_PIPELINE_MODE_BLOCK", "Pipeline mode block has no end tag.")
    return "".join(output)


class PromptTemplateService:
    """Resolve direct prompt placeholders and write traceable prompt artifacts."""

    def __init__(self, project_root: Path):
        self.project_root = Path(project_root)

    def load_marked_sections(self, paths: list[tuple[Path, str, str]]) -> tuple[dict[str, str], dict[str, dict]]:
        sections: dict[str, str] = {}
        sources: dict[str, dict] = {}
        for path, source_kind, source_label in paths:
            values, value_sources = load_template_sections_with_sources(
                path,
                source_kind=source_kind,
                source_label=source_label,
            )
            collisions = sorted(set(sections).intersection(values))
            if collisions:
                raise TemplateCompileError("SECTION_NAMESPACE_COLLISION", f"Marked section collision: {', '.join(collisions)}")
            sections.update(values)
            sources.update(value_sources)
        return sections, sources

    def _known_section_names(self, view_token: str) -> set[str]:
        path = self.project_root / "Config" / "Prompt_Section_Metadata.json"
        if not path.exists():
            return set()
        payload = json.loads(path.read_text(encoding="utf-8"))
        return {
            name.replace("{VIEW}", view_token) if "{VIEW}" in name else name
            for name in payload.get("sections", {})
        }

    def select_sections(self, bundle: dict, all_sections: dict[str, str], section_sources: dict[str, dict], view_token: str, *, prompt_variant: str = "generation", pipeline_mode: str = "traditional"):
        template_file = prompt_template_path(self.project_root, str(bundle.get("static_prompt_template", "")))
        return select_sections_for_prompt(
            all_sections,
            filter_prompt_variant_blocks(
                filter_pipeline_mode_blocks(template_file.read_text(encoding="utf-8"), pipeline_mode),
                prompt_variant,
            ),
            view_token,
            section_sources,
            self._known_section_names(view_token),
        )

    def render_artifacts(
        self,
        *,
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
    ) -> str:
        template_file = prompt_template_path(self.project_root, str(bundle.get("static_prompt_template", "")))
        prompt_text, source_map = render_static_prompt_with_source_map(
            filter_prompt_variant_blocks(
                filter_pipeline_mode_blocks(template_file.read_text(encoding="utf-8"), pipeline_mode),
                prompt_variant,
            ),
            template_path=template_file,
            metadata=metadata_values,
            metadata_sources=metadata_sources,
            selection=selection,
            required_section_names=required_section_names,
            view_token=view_token,
            final_prompt_name=final_prompt_path.name,
        )
        final_prompt_path.write_text(prompt_text, encoding="utf-8")
        source_map_path.write_text(
            json.dumps({**source_map, **metadata}, indent=2, ensure_ascii=ensure_ascii_source_map) + "\n",
            encoding="utf-8",
        )
        write_compiled_sections(compiled_sections_path, job_metadata=metadata, view_token=view_token, selection=selection)
        return prompt_text
