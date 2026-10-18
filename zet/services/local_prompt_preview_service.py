"""Text-only character prompt composition, independent of generated image files."""
from pathlib import Path
import json

from zet.services.template_source_service import template_sources
from zet.services.view_conditioning_service import VIEW_ORDER


PREDECESSORS = {
    "FRONT_LEFT_3_4": "FRONT", "FRONT_RIGHT_3_4": "FRONT",
    "LEFT_PROFILE": "FRONT_LEFT_3_4", "RIGHT_PROFILE": "FRONT_RIGHT_3_4",
    "BACK_LEFT_3_4": "LEFT_PROFILE", "BACK_RIGHT_3_4": "RIGHT_PROFILE",
    "BACK": "BACK_LEFT_3_4",
}


class LocalPromptPreviewService:
    def __init__(self, workflow):
        self.workflow = workflow

    def compile(self, run, sources, directory):
        from Scripts.Run_Body_Reference_Jobs import compile_body_reference_job
        from Scripts.Run_Head_Image_Jobs import compile_head_image_job
        from Scripts.Run_Character_Assembly_Jobs import compile_character_assembly_job
        from Scripts.Run_Costume_Dressing_Jobs import compile_costume_dressing_job
        workflow = self.workflow
        pipeline = workflow.pipeline
        compiler = {"body-reference": compile_body_reference_job, "head-image": compile_head_image_job,
                    "character-assembly": compile_character_assembly_job,
                    "costume-dressing": compile_costume_dressing_job}[pipeline]
        character = Path(workflow.app.config.base_character_path) / run["character"] / run["phase"] / "Character.md"
        result = []
        with template_sources(sources):
            for view in VIEW_ORDER:
                references = []
                def declare(role, source_view=view):
                    references.append({"role": role, "path": "declared:" + role, "label": role.replace("_", " "),
                        "character": run["character"], "phase": run["phase"], "view": source_view,
                        "body_view": source_view, "head_view": source_view})
                if pipeline == "head-image" and (view != "FRONT" or run.get("front_source")):
                    declare("head_image_source", PREDECESSORS.get(view, "FRONT"))
                    references[-1].update(candidate_id="declared")
                if pipeline == "character-assembly":
                    declare("body_reference")
                    declare("head_image")
                if pipeline == "costume-dressing":
                    declare("character_assembly")
                if pipeline in {"character-assembly", "costume-dressing"} and view != "FRONT":
                    declare("batch_view_reference", PREDECESSORS[view])
                    references[-1].update(candidate_id="declared", prompt_role="subject_reference")
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
                        anchor_view=PREDECESSORS.get(view, "FRONT"))
                source_map = json.loads((output / "Prompt_Source_Map.json").read_text(encoding="utf-8"))
                compact = []
                for fragment in source_map.get("fragments", []):
                    item = {key: fragment[key] for key in ("source_kind", "source_path", "section_name", "placeholder", "editable") if key in fragment}
                    if item not in compact:
                        compact.append(item)
                result.append({"view": view, "prompt": prompt, "source_map": compact,
                    "reference_inputs": references, "renderable": False})
        return result
