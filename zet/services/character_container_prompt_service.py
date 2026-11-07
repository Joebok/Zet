"""Compile one character Asset view without creating or reading a legacy run."""
from pathlib import Path
from uuid import uuid4


class CharacterContainerPromptService:
    COMPILERS = {
        "body-reference": ("Scripts.Run_Body_Reference_Jobs", "compile_body_reference_job"),
        "head-image": ("Scripts.Run_Head_Image_Jobs", "compile_head_image_job"),
        "head-image-edit": ("Scripts.Run_Head_Image_Edit_Jobs", "compile_head_image_edit_job"),
        "character-assembly": ("Scripts.Run_Character_Assembly_Jobs", "compile_character_assembly_job"),
        "costume-dressing": ("Scripts.Run_Costume_Dressing_Jobs", "compile_costume_dressing_job"),
    }

    def __init__(self, app, project_root: str | Path):
        self.app = app
        self.project_root = Path(project_root).resolve()

    def compile(self, scope: dict, view: str, output_dir: str | Path,
                references: list[dict], *, apply_phase_change: bool = False,
                assembly_style_mode: str = "", render_mode: str = "draft") -> dict:
        pipeline = scope["pipeline"]
        if view not in scope["views"]:
            raise ValueError("Choose a view in this Asset Container.")
        try:
            module_name, compiler_name = self.COMPILERS[pipeline]
        except KeyError as exc:
            raise ValueError("Unsupported character Asset pipeline.") from exc
        from importlib import import_module
        compiler = getattr(import_module(module_name), compiler_name)
        library_root = Path(self.app.config.base_library_path).resolve()
        normalized_references = []
        for index, reference in enumerate(references):
            source = Path(str(reference.get("path") or "")).resolve()
            if not source.is_relative_to(library_root) or not source.is_file():
                raise ValueError("A selected prompt reference is unavailable in this universe.")
            normalized_references.append({**reference, "path": str(source),
                                          "image_index": index + 1})
        character_template = (Path(self.app.config.base_character_path) /
                              scope["character"] / scope["phase"] / "Character.md")
        if not character_template.is_file():
            raise ValueError("The current character master is unavailable for a new prompt.")
        directory = Path(output_dir).resolve()
        if not directory.is_relative_to(library_root):
            raise ValueError("Prompt compilation must stay inside the selected universe library.")
        directory.mkdir(parents=True, exist_ok=True)
        job = {
            "Job": f"Container_{uuid4().hex}", "Task": pipeline,
            "Character": scope["character"], "Phase": scope["phase"],
            "Body View": view, "Head View": view,
            "Template Path": str(character_template), "Output Directory": str(directory),
            "Reference Files": normalized_references,
            "Allow Unanchored View": pipeline == "head-image" and not normalized_references,
            "Apply Phase Change": apply_phase_change,
            "Assembly Style Mode": assembly_style_mode,
        }
        if pipeline == "costume-dressing":
            costume = next(item for item in self.app.costume_service.list_costumes(
                scope["character"], scope["phase"]) if item.slug == scope["costume"])
            job.update(Costume=costume.name, **{"Costume Path": costume.path})
        if pipeline == "body-reference":
            from Scripts.Run_Body_Reference_Jobs import compile_body_reference_job
            compiled = compile_body_reference_job(job, self.project_root, pipeline_mode="local",
                universe_root=self.app.config.base_library_path)
            from zet.services.local_body_reference_service import LocalBodyReferenceService
            prompt = Path(compiled["final_prompt"]).read_text(encoding="utf-8")
            adapter = LocalBodyReferenceService(self.app, self.project_root)
            prompt = adapter._qwen_prompt(prompt, view, anchor=bool(normalized_references), 
                anchor_view=normalized_references[0]["view"] if normalized_references else "FRONT")
        else:
            compiled = compiler(job, self.project_root, pipeline_mode="local",
                universe_root=self.app.config.base_library_path)
            prompt = Path(compiled["final_prompt"]).read_text(encoding="utf-8")
        compiled_references = [dict(item) for item in compiled.get("reference_files", normalized_references)]
        return {"view": view, "prompt": prompt,
                "reference_inputs": compiled_references,
                "template_revision_id": compiled.get("template_revision_id", ""),
                "source_map_path": str(Path(compiled["final_prompt"]).with_name("Prompt_Source_Map.json"))}
