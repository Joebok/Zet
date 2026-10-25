"""Prepare a dressed-view rotation without changing the originating pipeline."""
from __future__ import annotations

from pathlib import Path
import json

from zet.services.local_view_reference_service import selected_reference


_TURN_ORDER = ("FRONT", "FRONT_LEFT_3_4", "LEFT_PROFILE", "BACK_LEFT_3_4",
               "BACK", "BACK_RIGHT_3_4", "RIGHT_PROFILE", "FRONT_RIGHT_3_4")


def rotation_degrees(source: str, target: str) -> int:
    distance = abs(_TURN_ORDER.index(source) - _TURN_ORDER.index(target))
    return min(distance, 8 - distance) * 45


def rotation_source(run: dict, view: str) -> dict:
    """Honor the view recipe, otherwise use the closest usable selected view."""
    recipe = (run.get("view_reference_recipes") or {}).get(view) or {"mode": "default"}
    if recipe["mode"] == "selected_view":
        return selected_reference(run, view, recipe)
    if recipe["mode"] == "none":
        raise ValueError("Choose a selected dressed view as this view's reference before staging rotation.")
    choices = sorted((source for source in _TURN_ORDER if source != view),
                     key=lambda source: rotation_degrees(source, view))
    for source in choices:
        if source not in run.get("views", []):
            continue
        try:
            return selected_reference(run, view, {"mode": "selected_view", "source_view": source})
        except ValueError:
            continue
    raise ValueError("Select an available, non-rejected dressed image in a different view before staging rotation.")


class CostumeRotationService:
    def __init__(self, workflow):
        self.workflow = workflow

    def prepare(self, run: dict, view: str, directory: Path) -> dict:
        if self.workflow.pipeline != "costume-dressing":
            raise ValueError("Stage Rotation is available only for Costume Dressing.")
        source = rotation_source(run, view)
        # Require the original matching snapshot; staging must never create new
        # source snapshots or rewrite prompts in the source batch.
        assembly = self.workflow.adapter._verify_snapshot_view(run, view)["character_assembly"]
        references = [
            {"role": "costume_rotation_source", "prompt_role": "edit_base", "path": source["path"],
             "view": source["view"], "source_view": source["view"], "candidate_id": source["candidate_id"],
             "label": f"Dressed character to rotate ({source['view']})",
             "notes": f"Turn approximately {rotation_degrees(source['view'], view)} degrees around the body's vertical axis toward {view}; stop at the orientation shown in Image 2"},
            {"role": "character_assembly", "prompt_role": "layout_reference", "path": assembly["image_path"],
             "view": view, "label": f"Target orientation only ({view})",
             "ignore": ["fitment clothing", "bare feet", "rendering details"],
             "notes": "Use only the body/head viewing direction, stance and framing; edit Image 1"},
        ]
        from Scripts.Run_Costume_Dressing_Jobs import compile_costume_dressing_job
        from zet.services.render_slot_service import frozen_input
        from zet.services.template_source_service import active_revision, template_sources
        adapter = self.workflow.adapter
        job = {"Job": f"Rotation_{run['run_id']}_{view}", "Task": "costume-dressing",
               "Character": run["character"], "Phase": run["phase"], "Body View": view, "Head View": view,
               "Costume": run["costume"], "Costume Path": run["costume_path"],
               "Template Path": str(adapter.character_root / run["character"] / run["phase"] / "Character.md"),
               "Output Directory": str(directory / "prompt"), "Reference Files": references}
        # The normal compilation wrapper records provenance inside a pipeline
        # tree. Staging artifacts live in a temporary directory instead.
        with template_sources(active_revision(Path(run["root"])).get("sources", [])):
            result = compile_costume_dressing_job(job, self.workflow.project_root,
                pipeline_mode="local", rotation=True, universe_root=adapter.app.config.base_library_path)
        saved = frozen_input(directory / "inputs", Path(result["final_prompt"]).read_text(encoding="utf-8"),
                             result["reference_files"], adapter.definition["preset"])
        saved["compiler_facts"] = {**result.get("packet_facts", {}),
            "rotation": {"source_view": source["view"], "target_view": view,
                         "source_candidate_id": source["candidate_id"]}}
        saved["required_constraints"] = ["Edit Image 1.",
            "Image 2 controls target orientation, stance and framing only."]
        source_map = Path(result["final_prompt"]).parent / "Prompt_Source_Map.json"
        if source_map.is_file():
            saved["prompt_packet_declarations"] = json.loads(source_map.read_text(encoding="utf-8")).get("prompt_packet_declarations", [])
        return saved
