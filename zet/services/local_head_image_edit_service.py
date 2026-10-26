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
        character = str(payload.get("character") or "").strip()
        target_phase = str(payload.get("phase") or "").strip()
        character_root = (Path(self.app.config.base_character_path) / character).resolve()
        source_dir = (character_root / source_phase).resolve()
        if (source_phase == target_phase or source_dir.parent != character_root
                or not (source_dir / "Character.md").is_file()):
            raise LocalHeadImageError("Choose a different available phase of this character as the source.")
        records = self.asset_store.locked_assets(character, source_phase, pipeline=self.asset_pipeline)
        return next((record for record in records if record.get("view") == "FRONT"
                     and not record.get("qualifier")), None)

    def _ranking_guidance(self, run, view):
        from Scripts.Compile_Character_Template import load_template_sections
        from zet.services.template_source_service import active_revision, template_sources
        from zet.services.view_conditioning_service import ViewContext, condition_section
        path = Path(self.app.config.base_character_path) / run["character"] / run["phase"] / "Character.md"
        with template_sources(active_revision(Path(run["root"])).get("sources", [])):
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
            result["blocking_reasons"].append("Author Head-Image Edit phase-change rules in the target phase first.")
        source_phase = str(payload.get("front_source_phase") or "").strip()
        source_path = str(payload.get("front_source_path") or "").strip()
        record = self._locked_phase_source(payload)
        if source_phase and record is None:
            result["can_create"] = False
            result["blocking_reasons"].append(
                f"Lock a FRONT Head-Image Edit image in {source_phase} before creating this batch.")
        elif payload.get("apply_phase_change") is True and not (source_phase or source_path):
            result["can_create"] = False
            result["blocking_reasons"].append("Choose a source phase or upload a FRONT image for phase change.")
        return result

    def _front_source_for_create(self, payload):
        source_phase = str(payload.get("front_source_phase") or "").strip()
        if not source_phase:
            return super()._front_source_for_create(payload)
        record = self._locked_phase_source(payload)
        if record is None:
            raise LocalHeadImageError(
                f"Lock a FRONT Head-Image Edit image in {source_phase} before creating this batch.")
        return record["image_path"], {"kind": "locked_phase", "phase": source_phase,
                                      "source_key": record["key"], "asset_id": record.get("entity_library_asset_id", "")}

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
        prompt_pilot = bool(candidate.get("prompt_generator"))
        refs = [] if prompt_pilot else ((candidate.get("render_input") or {}).get("references") or (candidate.get("refinement") or {}).get("reference_inputs", []))
        dependencies = []
        for ref in refs:
            source_view = ref.get("view")
            if ref.get("candidate_id") and source_view and source_view != view:
                selected = next((item for item in run["candidates"] if item["candidate_id"] == run.get("selected_views", {}).get(source_view)), {})
                source = Path(str(selected.get("image_path") or ""))
                if (selected.get("candidate_id") != ref["candidate_id"] or not source.is_file()
                        or (selected.get("human_review") or {}).get("decision") == "reject"
                        or (ref.get("sha256") and self._hash(source) != ref["sha256"])):
                    raise LocalHeadImageError("The selected source or guide changed; regenerate or refine before locking.")
                dependencies.append({"key": self.asset_store.key(self.asset_pipeline, source_view), "image_sha256": self._hash(source)})
        return self.asset_store.lock_batch_selection(run["character"], run["phase"], self.asset_pipeline, view,
            candidate_id=cid, image_path=image, batch_id=run_id, dependencies=dependencies,
            prompt_generator=candidate.get("prompt_generator"))
