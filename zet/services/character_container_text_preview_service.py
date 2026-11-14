"""Non-renderable prompt previews for container template analysis."""
from pathlib import Path

from zet.services.local_prompt_preview_service import PREDECESSORS
from zet.services.view_conditioning_service import VIEW_ORDER


class CharacterContainerTextPreviewService:
    def __init__(self, app, project_root):
        self.app = app
        self.project_root = Path(project_root)

    def compile(self, scope: dict, directory: Path, sources: list[dict] | None = None) -> list[dict]:
        from importlib import import_module
        from zet.services.character_container_prompt_service import CharacterContainerPromptService
        from zet.services.template_source_service import template_sources
        pipeline = scope["pipeline"]
        module, name = CharacterContainerPromptService.COMPILERS[pipeline]
        compiler = getattr(import_module(module), name)
        character = Path(self.app.config.base_character_path) / scope["character"] / scope["phase"] / "Character.md"
        result = []
        with template_sources(sources or []):
            for view in VIEW_ORDER:
                references = []
                def declare(role, source_view=view):
                    references.append({"role": role, "path": "declared:" + role,
                        "character": scope["character"], "phase": scope["phase"],
                        "view": source_view, "body_view": source_view, "head_view": source_view})
                if pipeline == "character-assembly":
                    declare("body_reference")
                    declare("head_image")
                elif pipeline == "costume-dressing":
                    declare("character_assembly")
                elif view != "FRONT":
                    from zet.services.local_view_reference_service import batch_view_reference
                    source_view = "FRONT" if pipeline == "head-image-edit" else PREDECESSORS.get(view, "FRONT")
                    reference = batch_view_reference(source_view, view, "declared:batch_view_reference", "declared")
                    if pipeline == "head-image-edit":
                        reference.update(role="head_image_source", prompt_role="edit_base")
                    references.append(reference)
                output = directory / view
                job = {"Job": "ContainerTextPreview_" + view, "Task": pipeline,
                    "Character": scope["character"], "Phase": scope["phase"],
                    "Body View": view, "Head View": view, "Template Path": str(character),
                    "Output Directory": str(output), "Reference Files": references}
                if pipeline == "costume-dressing":
                    costume = next(item for item in self.app.costume_service.list_costumes(
                        scope["character"], scope["phase"]) if item.slug == scope["costume"])
                    job.update(Costume=costume.name, **{"Costume Path": costume.path})
                compiled = compiler(job, self.project_root, pipeline_mode="local",
                    universe_root=self.app.config.base_library_path, text_preview=True)
                prompt = Path(compiled["final_prompt"]).read_text(encoding="utf-8")
                review_path = compiled.get("image_review")
                review = Path(review_path).read_text(encoding="utf-8") if review_path else ""
                if pipeline == "body-reference":
                    from zet.services.local_body_reference_service import LocalBodyReferenceService
                    prompt = LocalBodyReferenceService._qwen_prompt(
                        prompt, view, anchor=view != "FRONT", anchor_view=PREDECESSORS.get(view, "FRONT"))
                result.append({"view": view, "prompt": prompt,
                               "review_criteria": review,
                               "reference_inputs": compiled.get("reference_files", references),
                               "renderable": False})
        return result
