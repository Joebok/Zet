"""Independent FRONT-anchored edit pipeline using the shared head lifecycle."""
from pathlib import Path
import re

from Scripts.Compile_Character_Template import TemplateCompileError
from Scripts.Run_Head_Image_Edit_Jobs import compile_head_image_edit_job
from zet.services.local_head_image_service import LocalHeadImageError, LocalHeadImageService


class LocalHeadImageEditService(LocalHeadImageService):
    pipeline_id = "head-image-edit"
    asset_pipeline = "Head-Image-Edit"
    run_kind = "local_head_image_edit"
    queue_pipeline = "Local-Head-Image-Edit"
    ask_prefix = "LocalHeadImageEdit"
    compiler = staticmethod(compile_head_image_edit_job)
    edit_preset = "comfyui-qwen-head-image-edit-v1"
    text_preset = "comfyui-qwen-head-image-edit-front-v1"

    def _locked_phase_source(self, payload):
        source_phase = str(payload.get("front_source_phase") or "").strip()
        source_path = str(payload.get("front_source_path") or "").strip()
        apply_phase = payload.get("apply_phase_change") is True
        if source_phase and (not apply_phase or source_path):
            raise LocalHeadImageError("Choose either a locked source phase or an uploaded FRONT image with Apply Phase Change.")
        if not source_phase:
            return None
        try:
            path, origin = self._locked_phase_source_for_mode(payload, "draft")
            return {"image_path": path, "key": origin["source_key"], "entity_library_asset_id": origin["asset_id"]}
        except LocalHeadImageError as exc:
            if str(exc).startswith("Lock a "):
                return None
            raise

    def _ranking_guidance(self, run, view):
        from Scripts.Compile_Character_Template import load_template_sections
        from zet.services.view_conditioning_service import ViewContext, condition_section
        path = Path(self.app.config.base_character_path) / run["character"] / run["phase"] / "Character.md"
        sections = load_template_sections(path)
        return "\n\n" + "\n\n".join(condition_section(sections.get(name, ""), name, {}, ViewContext(head_view=view))[0]
                           for name in ("HEAD_EDIT_VIEW_OVERRIDES", "HEAD_EDIT_REVIEW_CRITERIA"))

    def preview(self, payload):
        from Scripts.Run_Head_Image_Edit_Jobs import validate_authoring
        path = Path(self.app.config.base_character_path) / str(payload.get("character") or "") / str(payload.get("phase") or "") / "Character.md"
        if not path.resolve().is_relative_to(Path(self.app.config.base_character_path).resolve()):
            raise ValueError("Character template must belong to this universe.")
        try:
            sections = validate_authoring(path)
        except TemplateCompileError as exc:
            raise LocalHeadImageError(str(exc)) from exc
        result = super().preview(payload)
        if payload.get("apply_phase_change") is True and not re.sub(
                r"<!--.*?-->", "", sections.get("HEAD_EDIT_PHASE_CHANGES", ""), flags=re.S).strip():
            result["can_create"] = False
            result["blocking_reasons"].append("Author Head-Image (Edit) phase-change rules in the target phase first.")
        source_phase = str(payload.get("front_source_phase") or "").strip()
        source_path = str(payload.get("front_source_path") or "").strip()
        record = self._locked_phase_source(payload)
        if source_phase and record is None:
            result["can_create"] = False
            result["blocking_reasons"].append(
                f"Lock a FRONT Head-Image (Edit) image in {source_phase} before creating this batch.")
        elif payload.get("apply_phase_change") is True and not (source_phase or source_path):
            result["can_create"] = False
            result["blocking_reasons"].append("Choose a source phase or upload a FRONT image for phase change.")
        return result

    def _front_source_for_create(self, payload):
        source_phase = str(payload.get("front_source_phase") or "").strip()
        if not source_phase:
            return super()._front_source_for_create(payload)
        return super()._front_source_for_create(payload)

    def create_run(self, payload):
        preview = self.preview(payload)
        if not preview["can_create"]:
            raise LocalHeadImageError("; ".join(preview["blocking_reasons"]))
        run = super().create_run(payload)
        path = Path(run["root"]) / "spec.json"
        spec = self._read_json(path)
        spec.update(recipe_version=1, source_policy="independent_front")
        self._write(path, spec)
        return self.detail(run["run_id"])

    def update_front_source(self, run_id, source_path):
        super().update_front_source(run_id, source_path)
        path = self._run_root(run_id) / "spec.json"
        spec = self._read_json(path)
        if "front_source_origin" in spec:
            spec.pop("front_source_origin")
            self._write(path, spec)
        return self.detail(run_id)

    def lock_selected_view(self, run_id, view):
        run = self.detail(run_id)
        cid = run.get("selected_views", {}).get(view)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == cid and item["view"] == view), {})
        image = Path(str(candidate.get("image_path") or ""))
        if not image.is_file():
            raise LocalHeadImageError("Select an available image before locking.")
        return self.asset_store.lock_batch_selection(run["character"], run["phase"], self.asset_pipeline, view,
            candidate_id=cid, image_path=image, batch_id=run_id, dependencies=[],
            prompt_generator=candidate.get("prompt_generator"),
            prompt=str((candidate.get("render_input") or {}).get("prompt") or candidate.get("prompt") or ""))
