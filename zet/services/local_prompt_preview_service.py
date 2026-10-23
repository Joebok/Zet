"""Text-only character prompt composition, independent of generated image files."""
from pathlib import Path
import json

from zet.services.template_source_service import template_sources


PREDECESSORS = {
    "FRONT_LEFT_3_4": "FRONT", "FRONT_RIGHT_3_4": "FRONT",
    "LEFT_PROFILE": "FRONT_LEFT_3_4", "RIGHT_PROFILE": "FRONT_RIGHT_3_4",
    "BACK_LEFT_3_4": "LEFT_PROFILE", "BACK_RIGHT_3_4": "RIGHT_PROFILE",
    "BACK": "BACK_LEFT_3_4",
}


class LocalPromptPreviewService:
    def __init__(self, workflow):
        self.workflow = workflow

    def compile(self, run, sources, directory, *, all_orientations=False):
        from Scripts.Run_Body_Reference_Jobs import compile_body_reference_job
        from Scripts.Run_Head_Image_Jobs import compile_head_image_job
        from Scripts.Run_Head_Image_Edit_Jobs import compile_head_image_edit_job
        from Scripts.Run_Character_Assembly_Jobs import compile_character_assembly_job
        from Scripts.Run_Costume_Dressing_Jobs import compile_costume_dressing_job
        from zet.services.local_character_progression_service import stages_for
        from zet.services.view_conditioning_service import VIEW_ORDER
        workflow = self.workflow
        pipeline = workflow.pipeline
        compiler = {"body-reference": compile_body_reference_job, "head-image": compile_head_image_job, "head-image-edit": compile_head_image_edit_job,
                    "character-assembly": compile_character_assembly_job,
                    "costume-dressing": compile_costume_dressing_job}[pipeline]
        character = Path(workflow.app.config.base_character_path) / run["character"] / run["phase"] / "Character.md"
        from zet.services.local_view_reference_service import batch_view_reference, reference_recipes
        recipes = reference_recipes(Path(run["root"]), pipeline)
        result = []
        with template_sources(sources):
            views = VIEW_ORDER if all_orientations else [view for stage in stages_for(run) for view in stage]
            for view in views:
                references = []
                def declare(role, source_view=view):
                    references.append({"role": role, "path": "declared:" + role,
                        "character": run["character"], "phase": run["phase"], "view": source_view,
                        "body_view": source_view, "head_view": source_view})
                source_view = "FRONT" if pipeline == "head-image-edit" else PREDECESSORS.get(view, "FRONT")
                if view == "BACK":
                    source_view = (run.get("character_progression") or {}).get("back_reference", source_view)
                    if pipeline in {"body-reference", "head-image-edit"}:
                        source_view = "FRONT"
                recipe = recipes.get(view) or {}
                if recipe.get("mode") == "selected_view":
                    source_view = recipe["source_view"]
                if pipeline in {"head-image", "head-image-edit"} and view == "FRONT" and run.get("front_source"):
                    declare("head_image_source")
                if pipeline == "character-assembly":
                    declare("body_reference")
                    declare("head_image")
                if pipeline == "costume-dressing":
                    declare("character_assembly")
                if view != "FRONT" and pipeline != "character-assembly":
                    reference = batch_view_reference(source_view, view, "declared:batch_view_reference", "declared")
                    if pipeline in {"head-image", "head-image-edit"}:
                        reference.update(role="head_image_source", prompt_role="edit_base")
                    references.append(reference)
                output = Path(directory) / view
                job = {"Job": "PromptPreview_" + view, "Task": pipeline, "Character": run["character"],
                    "Phase": run["phase"], "Body View": view, "Head View": view, "Template Path": str(character),
                    "Output Directory": str(output), "Reference Files": references, "use_front_anchor": False,
                    "Apply Phase Change": bool(run.get("apply_phase_change"))}
                if pipeline == "costume-dressing":
                    job.update(Costume=run["costume"], **{"Costume Path": str(workflow.adapter._costume_path(
                        run["character"], run["phase"], run["costume"]))})
                compiled = compiler(job, workflow.project_root, pipeline_mode="local",
                    universe_root=workflow.app.config.base_library_path, text_preview=True)
                prompt = Path(compiled["final_prompt"]).read_text(encoding="utf-8")
                if pipeline == "body-reference":
                    prompt = workflow.adapter._qwen_prompt(prompt, view, anchor=view != "FRONT",
                        anchor_view=source_view)
                source_map = json.loads((output / "Prompt_Source_Map.json").read_text(encoding="utf-8"))
                compact = []
                for fragment in source_map.get("fragments", []):
                    item = {key: fragment[key] for key in ("source_kind", "source_path", "section_name", "placeholder", "editable") if key in fragment}
                    if item not in compact:
                        compact.append(item)
                result.append({"view": view, "prompt": prompt, "source_map": compact,
                    "reference_inputs": compiled["reference_files"], "renderable": False})
        return result
