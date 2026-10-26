"""One input contract for Costume-Dressing rendering, staging and previews."""
from __future__ import annotations

from pathlib import Path
import hashlib

from zet.services.local_image_pipeline_policy import mutate_local_run_state
from zet.services.local_view_reference_service import selected_reference
from zet.services.costume_mode_conditioning_service import MODES


def render_settings(run: dict, view: str) -> dict:
    from zet.services.local_prompt_preview_service import PREDECESSORS
    if view not in run.get("views", []):
        raise ValueError("Unknown Costume-Dressing view.")
    recipe = (run.get("view_reference_recipes") or {}).get(view) or {}
    saved = (run.get("render_settings") or {}).get(view) or {}
    default_source = recipe.get("source_view") or ((run.get("character_progression") or {}).get("back_reference", "BACK_LEFT_3_4")
                                                  if view == "BACK" else PREDECESSORS.get(view, "FRONT"))
    return {"mode": saved.get("mode", "doll-dressing-no-ref" if recipe.get("mode") == "none" and view != "FRONT" else MODES[0]),
            "costume_reference_view": "" if view == "FRONT" else saved.get("costume_reference_view", default_source),
            "revision": int(saved.get("revision", 0))}


def input_reason(run, view, settings=None, *, include_review=True):
    try:
        settings = settings or render_settings(run, view)
        CostumeRenderModeService.validate(run, view, settings)
        if include_review:
            from zet.services.local_character_progression_service import prompt_review_required
            if run.get("character_progression") and prompt_review_required(run):
                return "Analyze and accept the governing prompts first."
        assembly = ((run.get("sources") or {}).get(view) or {}).get("character_assembly") or {}
        image = Path(str(assembly.get("image_path") or ""))
        if not image.is_file() or assembly.get("sha256") and hashlib.sha256(image.read_bytes()).hexdigest() != assembly["sha256"]:
            return f"Original Character-Assembly snapshot for {view} is missing or changed."
        if view != "FRONT" and settings["mode"] != "doll-dressing-no-ref":
            selected_reference(run, view, {"mode": "selected_view", "source_view": settings["costume_reference_view"]})
    except (ValueError, KeyError, OSError) as exc:
        return str(exc)
    return ""


class CostumeRenderModeService:
    def __init__(self, workflow):
        if workflow.pipeline != "costume-dressing":
            raise ValueError("Rendering modes are available only for Costume Dressing.")
        self.workflow = workflow

    @staticmethod
    def validate(run, view, settings):
        mode = settings.get("mode")
        if mode not in MODES or view == "FRONT" and mode != MODES[0]:
            raise ValueError("FRONT supports only Doll-dressing (w/ Ref)." if view == "FRONT" else "Unknown Costume-Dressing rendering mode.")
        source = settings.get("costume_reference_view", "")
        if view != "FRONT" and mode != "doll-dressing-no-ref" and (source == view or source not in run.get("views", [])):
            raise ValueError("Choose a different view in this batch as the costume reference.")

    def reason(self, run, view, settings=None, *, include_review=True):
        return input_reason(run, view, settings, include_review=include_review)

    def save(self, run, view, payload):
        current = render_settings(run, view)
        settings = {"mode": payload.get("mode"), "costume_reference_view": "" if view == "FRONT" else str(payload.get("costume_reference_view") or "").upper(),
                    "revision": current["revision"] + 1}
        self.validate(run, view, settings)
        def update(state):
            revision = int(((state.get("render_settings") or {}).get(view) or {}).get("revision", 0))
            if payload.get("expected_revision") != revision:
                raise ValueError("Rendering settings changed; refresh before saving.")
            state.setdefault("render_settings", {})[view] = settings
        mutate_local_run_state(Path(run["root"]), update)
        return settings

    def references(self, run, view, settings=None, *, text_preview=False):
        settings = settings or render_settings(run, view)
        self.validate(run, view, settings)
        assembly = ({"image_path": "declared:character_assembly"} if text_preview
                    else self.workflow.adapter._verify_snapshot_view(run, view)["character_assembly"])
        reference = {"role": "character_assembly", "prompt_role": "edit_base", "path": assembly["image_path"],
                     "view": view, "body_view": view, "head_view": view, "character": run["character"], "phase": run["phase"],
                     "label": f"Matching Character-Assembly image ({view})"}
        if view == "FRONT" or settings["mode"] == "doll-dressing-no-ref":
            return [reference]
        source_view = settings["costume_reference_view"]
        if text_preview:
            from zet.services.local_view_reference_service import batch_view_reference
            source = batch_view_reference(source_view, view, "declared:batch_view_reference", "declared")
        else:
            source = selected_reference(run, view, {"mode": "selected_view", "source_view": source_view})
        if settings["mode"] != "rotate":
            return [reference, source]
        from zet.services.costume_rotation_service import rotation_instruction
        source.update(role="costume_rotation_source", prompt_role="edit_base", source_view=source_view,
                      label=f"Dressed character to rotate ({source_view})", notes=rotation_instruction(source_view, view))
        reference.update(prompt_role="layout_reference", label=f"Target orientation only ({view})",
                         ignore=["fitment clothing", "bare feet", "rendering details"])
        return [source, reference]

    def prepare(self, run, view, directory, *, settings=None, output_dir=None):
        from zet.services.render_slot_service import frozen_input
        from zet.services.template_source_service import active_revision
        settings = settings or render_settings(run, view)
        reason = self.reason(run, view, settings, include_review=False)
        if reason:
            raise ValueError(reason)
        references = self.references(run, view, settings)
        compiled = self.workflow.adapter._compile(run, view, references, output_dir=output_dir or Path(directory) / "prompt", render_mode=settings["mode"])
        prompt = Path(compiled["final_prompt"])
        saved = frozen_input(Path(directory) / "inputs", prompt.read_text(encoding="utf-8"), compiled["reference_files"], self.workflow.adapter.definition["preset"])
        from zet.services.local_render_backend_service import LocalRenderBackendService
        saved["render_profile"] = LocalRenderBackendService(self.workflow.app.config.state_file(self.workflow.project_root, "Local_Render_Presets.json"),
            config=self.workflow.app.config).preset(saved["preset"])
        saved.update(render_settings=settings, rendering_mode=settings["mode"],
                     template_revision_id=active_revision(Path(run["root"])).get("revision_id", ""), compiler_facts=compiled.get("packet_facts", {}))
        return saved
