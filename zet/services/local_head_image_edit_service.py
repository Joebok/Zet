"""Independent FRONT-anchored edit pipeline using the shared head lifecycle."""
from pathlib import Path

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
            validate_authoring(path)
        except TemplateCompileError as exc:
            raise LocalHeadImageError(str(exc)) from exc
        return super().preview(payload)

    def create_run(self, payload):
        run = super().create_run(payload)
        path = Path(run["root"]) / "spec.json"
        spec = self._read_json(path)
        spec.update(recipe_version=1, source_policy="independent_front")
        self._write(path, spec)
        return self.detail(run["run_id"])

    def lock_selected_view(self, run_id, view):
        run = self.detail(run_id)
        cid = run.get("selected_views", {}).get(view)
        candidate = next((item for item in run["candidates"] if item["candidate_id"] == cid and item["view"] == view), {})
        image = Path(str(candidate.get("image_path") or ""))
        if not image.is_file():
            raise LocalHeadImageError("Select an available image before locking.")
        refs = (candidate.get("render_input") or {}).get("references") or (candidate.get("refinement") or {}).get("reference_inputs", [])
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
            candidate_id=cid, image_path=image, batch_id=run_id, dependencies=dependencies)
