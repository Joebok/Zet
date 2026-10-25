"""Compile an independent Costume Dressing view for Image Generator staging."""
from __future__ import annotations

from pathlib import Path

from zet.services.render_slot_service import frozen_input


class CostumeNoReferenceService:
    """Prepare a Dressing view using its Assembly snapshot, without prior costume views."""

    @staticmethod
    def availability_reason(workflow, run: dict, view: str) -> str:
        if workflow.pipeline != "costume-dressing":
            return "Available only for Costume Dressing."
        if view not in run.get("views", []):
            return "Unknown Costume Dressing view."
        try:
            sources = workflow.adapter._verify_snapshot_view(run, view)
            assembly = sources.get("character_assembly") or {}
            image = Path(str(assembly.get("image_path") or ""))
            if not image.is_file():
                return f"Original Character-Assembly snapshot for {view} is missing or changed."
            expected_hash = str(assembly.get("sha256") or "")
            if expected_hash and workflow.adapter._hash(image) != expected_hash:
                return f"Original Character-Assembly snapshot for {view} is missing or changed."
        except (ValueError, KeyError, OSError) as exc:
            return str(exc)
        return ""

    def prepare(self, workflow, run: dict, view: str, directory: Path) -> dict:
        reason = self.availability_reason(workflow, run, view)
        if reason:
            raise ValueError(reason)

        assembly = workflow.adapter._verify_snapshot_view(run, view)["character_assembly"]
        references = [{
            "role": "character_assembly",
            "prompt_role": "edit_base",
            "path": assembly["image_path"],
            "view": view,
            "body_view": view,
            "head_view": view,
            "character": run["character"],
            "phase": run["phase"],
            "label": f"Matching Character-Assembly image ({view})",
        }]
        from zet.services.template_source_service import active_revision, template_sources
        revision = active_revision(Path(run["root"]))
        with template_sources(revision.get("sources", [])):
            compiled = workflow.adapter._compile(run, view, references, output_dir=directory / "prompt")
        saved = frozen_input(directory / "inputs", Path(compiled["final_prompt"]).read_text(encoding="utf-8"),
                             compiled["reference_files"], workflow.adapter.definition["preset"])
        saved["template_revision_id"] = revision.get("revision_id", "")
        saved["reference_recipe"] = {"mode": "none"}
        return saved
