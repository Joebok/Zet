import json
from pathlib import Path
import tempfile
import unittest

from zet.models.asset import Asset
from zet.services.config_service import Config
from zet.models.identity_key import IdentityKey
from zet.models.turnaround import TurnaroundSheet
from zet.models import story as story_models
from zet.services.path_service import PathService
from zet.services.scene_document_service import SceneDocumentService
from zet.services import story_service as story_service_module
from zet.services.story_service import StoryGitResult, StoryService, StoryServiceError
from zet.services.story_reference_service import StoryReferenceService
from zet.services.story_render_service import StoryRenderService


class FakeAuxiliaryResource:
    def __init__(self, resource_id: str, category: str, label: str, tag: str, image_path: str, template_path: str = "", images=None):
        self.resource_id = resource_id
        self.category = category
        self.label = label
        self.tag = tag
        self.image_path = image_path
        self.template_path = template_path
        self.images = images or []


class FakeAuxiliaryResourceRepository:
    def __init__(self, resources=None):
        self.resources = resources or []

    def list_resources(self):
        return list(self.resources)

    def get_resource(self, resource_id: str):
        for resource in self.resources:
            if resource.resource_id == resource_id:
                return resource
        raise KeyError(resource_id)


class FakeIdentityKeyRepository:
    def __init__(self, identity_keys=None):
        self.identity_keys = identity_keys or []

    def list_identity_keys(self, character: str, phase: str):
        return [
            identity_key for identity_key in self.identity_keys
            if identity_key.character == character and identity_key.phase == phase
        ]

    def get_identity_key(self, character: str, phase: str, identity_key_id: str):
        for identity_key in self.list_identity_keys(character, phase):
            if identity_key.identity_key_id == identity_key_id:
                return identity_key
        raise KeyError(identity_key_id)


class FakeAssetRepository:
    def __init__(self, assets=None):
        self.assets = assets or []

    def list_assets(self, character: str, phase: str):
        return [
            asset for asset in self.assets
            if asset.character == character and asset.phase == phase
        ]

    def get_asset(self, character: str, phase: str, asset_id: int):
        for asset in self.list_assets(character, phase):
            if asset.asset_id == asset_id:
                return asset
        raise KeyError(asset_id)


class FakeTurnaroundRepository:
    def __init__(self, sheets=None):
        self.sheets = sheets or []

    def list_sheets(self, character: str, phase: str):
        return [
            sheet for sheet in self.sheets
            if sheet.character == character and sheet.phase == phase
        ]


class StoryServiceTests(unittest.TestCase):

    def _service(
        self,
        root: Path,
        auxiliary_resource_repository=None,
        identity_key_repository=None,
        asset_repository=None,
        turnaround_repository=None,
    ) -> StoryService:
        config = Config(
            base_library_path=str(root),
            base_character_path=str(root / "Characters"),
            base_asset_path=str(root / "Assets"),
            base_pipeline_path=str(root / "Pipelines"),
            base_ai_queue_path=str(root / "Queue"),
        )
        return StoryService(
            PathService(config, root),
            asset_repository or FakeAssetRepository(),
            auxiliary_resource_repository or FakeAuxiliaryResourceRepository(),
            identity_key_repository,
            turnaround_repository,
        )


    def _write_scene_builder(
        self,
        service: StoryService,
        story_slug: str,
        scene_slug: str,
        reference_tags: list[str] | None = None,
    ) -> None:
        story_path = service.path_service.story_folder_path(story_slug) / f"{story_slug}.md"
        settings_path = service.path_service.story_folder_path(story_slug) / f"{story_slug}.story.json"
        if not settings_path.exists():
            service.save_story_settings(settings_path, service.create_default_story_settings(story_path))
        data = {
            "schema_version": 3,
            "setup": {
                "canvas": {"orientation": "landscape", "aspect_ratio": "16:9"},
                "environment": {"location": "academy archway", "lighting": "morning light"},
            },
            "scene_elements": [],
            "placements": [],
        }
        for index, tag in enumerate(reference_tags or [], start=1):
            element_id = f"reference_{index}"
            data["scene_elements"].append(
                {
                    "id": element_id,
                    "display_name": f"Reference {index}",
                    "element_type": "Object",
                    "reference_images": [{"tag": tag}],
                }
            )
            data["placements"].append({"scene_element_id": element_id, "position_within_cell": "center"})
        service.scene_builder_json_path(story_slug, scene_slug).write_text(json.dumps(data), encoding="utf-8")





    def test_scene_builder_save_and_reload_generates_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            story_dir = root / "Stories" / "FirstDay"
            story_dir.mkdir(parents=True)
            service = self._service(root)
            (story_dir / "FirstDay.md").write_text(
                """Title: `[First Day]`
Canonical Art Style: `[Painterly fantasy]`

<!-- ZET:BEGIN STORY_TITLE -->
First Day
<!-- ZET:END STORY_TITLE -->

<!-- ZET:BEGIN CANONICAL_ART_STYLE -->
Painterly fantasy
<!-- ZET:END CANONICAL_ART_STYLE -->
""",
                encoding="utf-8",
            )
            (story_dir / "At-the-Arch.md").write_text(
                """Scene: `[At the Arch]`

<!-- ZET:BEGIN SCENE_NAME -->
At the Arch
<!-- ZET:END SCENE_NAME -->
""",
                encoding="utf-8",
            )

            data = service.create_default_scene_builder_data("FirstDay", "At-the-Arch")
            data["scene_elements"] = [{"id": "Tsaeytte", "display_name": "Tsaeytte", "element_type": "Character"}]
            data["placements"] = [{
                "id": "placement_001",
                "scene_element_id": "Tsaeytte",
                "position_within_cell": "left",
                "depth": "foreground",
                "pose": "crouched",
            }]
            data["setup"]["environment"]["location"] = "magic academy hall"
            data["setup"]["environment"]["lighting"] = "cool blue light"

            document = service.save_scene_builder_data("FirstDay", "At-the-Arch", data)

            self.assertTrue((story_dir / "At-the-Arch.scene.json").exists())
            self.assertEqual(3, document.data["schema_version"])
            self.assertNotIn("screen_cell", document.data["placements"][0])
            self.assertIn("composition", document.data["setup"])
            self.assertNotIn("camera", document.data["setup"])
            self.assertNotIn("style", document.data["setup"])
            self.assertTrue(document.data["metadata"]["created_at"])
            self.assertTrue(document.data["metadata"]["updated_at"])

            reloaded = service.load_scene_builder_data("FirstDay", "At-the-Arch")
            self.assertEqual("Tsaeytte", reloaded.data["placements"][0]["scene_element_id"])







    def test_scene_builder_validation_and_markdown_export(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            story_dir = root / "Stories" / "FirstDay"
            story_dir.mkdir(parents=True)
            service = self._service(root)
            (story_dir / "FirstDay.md").write_text(
                """Title: `[First Day]`
Canonical Art Style: `[Painterly fantasy]`

<!-- ZET:BEGIN STORY_TITLE -->
First Day
<!-- ZET:END STORY_TITLE -->

<!-- ZET:BEGIN CANONICAL_ART_STYLE -->
Painterly fantasy
<!-- ZET:END CANONICAL_ART_STYLE -->
""",
                encoding="utf-8",
            )
            scene_path = story_dir / "At-the-Arch.md"
            scene_path.write_text(
                """Scene: `[At the Arch]`

<!-- ZET:BEGIN SCENE_NAME -->
At the Arch
<!-- ZET:END SCENE_NAME -->

Keep this manual note.
""",
                encoding="utf-8",
            )

            data = service.create_default_scene_builder_data("FirstDay", "At-the-Arch")
            data["scene_elements"] = [{"id": "Tsaeytte", "display_name": "Tsaeytte Display", "element_type": "Character"}]
            data["placements"] = [{
                "id": "placement_001",
                "scene_element_id": "Tsaeytte",
                "depth": "distant background",
                "expression": "alert",
            }]
            data["interactions"] = [{"subject_element_id": "Tsaeytte", "relationship": "looking at", "target_element_id": "Teacher", "note": ""}]

            warnings = service.validate_scene_builder_data(service._normalize_scene_builder_data("FirstDay", "At-the-Arch", data))

            self.assertTrue(any("missing target Teacher" in warning for warning in warnings))
            self.assertTrue(any("no image reference tag or fallback visual description" in warning for warning in warnings))
            self.assertFalse(any("Placement placement_001" in warning for warning in warnings))
            self.assertTrue(any("No lighting specified" in warning for warning in warnings))
            service.export_scene_markdown("FirstDay", "At-the-Arch", data)
            text = scene_path.read_text(encoding="utf-8")
            self.assertIn("Keep this manual note.", text)
            self.assertIn("<!-- ZET:BEGIN SCENE_BUILDER -->", text)
            self.assertIn("## Positive Image Prompt", text)

    def test_delete_story_commits_then_removes_story_folder(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            story_dir = root / "Stories" / "FirstDay"
            story_dir.mkdir(parents=True)
            (story_dir / "FirstDay.md").write_text("story", encoding="utf-8")
            service = self._service(root)
            commits = []
            service.story_git_commit = lambda: commits.append(True) or StoryGitResult("", False)

            service.delete_story("FirstDay")

            self.assertEqual([True], commits)
            self.assertFalse(story_dir.exists())


    def test_create_story_handles_story_heading_before_compiler_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            stories = root / "Stories"
            stories.mkdir(parents=True)
            shared_stories = root / "Shared_Library" / "Stories"
            shared_stories.mkdir(parents=True)
            (shared_stories / "_Story_Template.md").write_text(
                """Title: `[story title]`
Canonical Art Style: `[Painterly semi-realistic, anime-influenced facial proportions, etc.]`

# Story

Draft prose starts here.

# Compiler Sections

<!-- ZET:BEGIN STORY_TITLE -->
[story title]
<!-- ZET:END STORY_TITLE -->

<!-- ZET:BEGIN CANONICAL_ART_STYLE -->
[Painterly semi-realistic, anime-influenced facial proportions, etc.]
<!-- ZET:END CANONICAL_ART_STYLE -->
""",
                encoding="utf-8",
            )
            service = self._service(root)

            document = service.create_story("First Day")

            self.assertIn("# Story", document.text)
            self.assertIn("Title: `[First Day]`", document.text)
            self.assertIn("<!-- ZET:BEGIN STORY_TITLE -->\nFirst Day\n<!-- ZET:END STORY_TITLE -->", document.text)


    def test_stage_scene_render_resolves_identity_key_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            story_dir = root / "Stories" / "FirstDay"
            story_dir.mkdir(parents=True)
            image_path = root / "Characters" / "Tsaeytte" / "YoungAdult" / "Assets" / "IdentityKeys" / "IK_front.png"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"image")
            (story_dir / "FirstDay.md").write_text(
                """Title: `[FirstDay]`
Canonical Art Style: `[ink wash]`

<!-- ZET:BEGIN STORY_TITLE -->
FirstDay
<!-- ZET:END STORY_TITLE -->

<!-- ZET:BEGIN CANONICAL_ART_STYLE -->
ink wash
<!-- ZET:END CANONICAL_ART_STYLE -->

<!-- ZET:BEGIN STORY_PREMISE -->
Premise.
<!-- ZET:END STORY_PREMISE -->

<!-- ZET:BEGIN STORY_VISUAL_CONTINUITY -->
Continuity.
<!-- ZET:END STORY_VISUAL_CONTINUITY -->
""",
                encoding="utf-8",
            )
            (story_dir / "At-the-Arch.md").write_text(
                """<!-- ZET:BEGIN SCENE_NAME -->
At the Arch
<!-- ZET:END SCENE_NAME -->

<!-- ZET:BEGIN SCENE_DESCRIPTION -->
Two students meet.
<!-- ZET:END SCENE_DESCRIPTION -->

<!-- ZET:BEGIN SCENE_IMAGE_REFERENCES -->
{{IDENTITY:Tsaeytte:YoungAdult:IK_front}}
<!-- ZET:END SCENE_IMAGE_REFERENCES -->

<!-- ZET:BEGIN SCENE_RENDERING_NOTES -->
Morning light.
<!-- ZET:END SCENE_RENDERING_NOTES -->
""",
                encoding="utf-8",
            )
            identity_repository = FakeIdentityKeyRepository(
                [
                    IdentityKey(
                        identity_key_id="IK_front",
                        character="Tsaeytte",
                        phase="YoungAdult",
                        label="Front identity",
                        crop_percent=100,
                        source_asset_id=7,
                        source_pipeline="Expression",
                        source_body_view="FRONT",
                        image_path=str(image_path),
                    )
                ]
            )
            service = self._service(root, identity_key_repository=identity_repository)
            self._write_scene_builder(service, "FirstDay", "At-the-Arch", ["{{IDENTITY:Tsaeytte:YoungAdult:IK_front}}"])

            task = service.stage_scene_render("FirstDay", "At-the-Arch")
            rows = service.image_reference_rows(text_filter="Front identity")

            self.assertEqual(1, len(task.reference_files))
            self.assertEqual("{{IDENTITY:Tsaeytte:YoungAdult:IK_front}}", task.reference_files[0]["tag"])
            self.assertEqual("identity-key", task.reference_files[0]["kind"])
            self.assertEqual(str(image_path), task.reference_files[0]["path"])
            self.assertEqual(1, len(rows))
            self.assertEqual("{{IDENTITY:Tsaeytte:YoungAdult:IK_front}}", rows[0].tag)







    def test_stage_scene_render_with_builder_writes_v3_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            story_dir = root / "Stories" / "FirstDay"
            story_dir.mkdir(parents=True)
            (story_dir / "FirstDay.md").write_text(
                """Title: `[FirstDay]`
Canonical Art Style: `[ink wash]`

<!-- ZET:BEGIN STORY_TITLE -->
FirstDay
<!-- ZET:END STORY_TITLE -->

<!-- ZET:BEGIN CANONICAL_ART_STYLE -->
ink wash
<!-- ZET:END CANONICAL_ART_STYLE -->
""",
                encoding="utf-8",
            )
            (story_dir / "At-the-Arch.md").write_text(
                """<!-- ZET:BEGIN SCENE_NAME -->
At the Arch
<!-- ZET:END SCENE_NAME -->

<!-- ZET:BEGIN SCENE_DESCRIPTION -->
Two students meet at the arch.
<!-- ZET:END SCENE_DESCRIPTION -->
""",
                encoding="utf-8",
            )
            service = self._service(root)
            service.save_story_settings(story_dir / "FirstDay.story.json", service.create_default_story_settings(story_dir / "FirstDay.md"))
            service.scene_builder_json_path("FirstDay", "At-the-Arch").write_text(
                json.dumps(
                    {
                        "schema_version": 3,
                        "setup": {
                            "canvas": {"orientation": "landscape", "aspect_ratio": "16:9"},
                            "environment": {"location": "academy archway", "lighting": "morning light", "mood": "tense"},
                        },
                        "scene_elements": [
                            {"id": "tsa", "display_name": "Tsaeytte", "element_type": "Character", "default_visual_description": "petite elf student"},
                            {"id": "val", "display_name": "Valindia", "element_type": "Character", "default_visual_description": "elegant elf student"},
                        ],
                        "placements": [
                            {"scene_element_id": "val", "position_within_cell": "left", "depth": "foreground", "pose": {"summary": "standing", "gaze_target_element_id": "tsa"}},
                            {"scene_element_id": "tsa", "position_within_cell": "right", "depth": "foreground", "pose": {"summary": "kneeling", "gaze_target_element_id": "val"}},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            task = service.stage_scene_render("FirstDay", "At-the-Arch")

            pipeline = Path(task.pipeline_path)
            self.assertTrue((pipeline / "Scene_Render_IR.json").exists())
            self.assertTrue((pipeline / "Scene_Render_Validation.json").exists())
            self.assertTrue((pipeline / "Local_Render_Brief.json").exists())
            self.assertTrue((pipeline / "Local_Render_Prompt.md").exists())
            prompt = Path(task.final_prompt_path).read_text(encoding="utf-8")
            self.assertIn("# Render Task", prompt)
            self.assertIn("**Valindia:** Stands in the left foreground.", prompt)
            self.assertNotIn("cell ", prompt)
            local_prompt = (pipeline / "Local_Render_Prompt.md").read_text(encoding="utf-8")
            self.assertIn("prompt:", local_prompt)
            self.assertIn("negative:", local_prompt)
            source_map = json.loads((pipeline / "Prompt_Source_Map.json").read_text(encoding="utf-8"))
            self.assertEqual("scene_render_v3", source_map["compiler"])
            art_style_source = next(
                fragment for fragment in source_map["fragments"] if fragment.get("source_label") == "Canonical art style"
            )
            self.assertEqual("/style_defaults/canonical_art_style/full_prompt_text", art_style_source["json_pointer"])



    def test_scene_prompt_source_map_links_auxiliary_identity_and_story_style(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = self._service(root)
            story_path = root / "Stories" / "Test" / "Test.story.json"
            scene_path = root / "Stories" / "Test" / "Scene.scene.json"
            prompt_path = root / "Pipelines" / "Stories" / "Test" / "Scene" / "Final_Image_Prompt.md"
            ir = {
                "style": {"visual_continuity": {"rules": []}},
                "elements": [
                    {
                        "id": "val",
                        "display_name": "Valindia",
                        "resource_type": "Person",
                        "resolved_source_sections": {
                            "identity_source": "AuxiliaryResources/Images/valindia/valindia_Template.md",
                        },
                    }
                ],
            }
            prompt = "- Art style: painterly fantasy.\n\n## Valindia\n\n**Identity:** elegant half-elf.\n"

            source_map = service._scene_prompt_source_map(ir, prompt, prompt_path, scene_path, story_path, [])

            story_source, identity_source = source_map["fragments"]
            self.assertEqual("story_settings", story_source["source_kind"])
            self.assertEqual("/style_defaults/canonical_art_style/full_prompt_text", story_source["json_pointer"])
            self.assertEqual("auxiliary_template_section", identity_source["source_kind"])
            self.assertEqual("IDENTITY_PRESERVATION_SCENE", identity_source["section_name"])

    def test_stage_scene_render_blocks_invalid_builder_gaze(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            story_dir = root / "Stories" / "FirstDay"
            story_dir.mkdir(parents=True)
            (story_dir / "FirstDay.md").write_text(
                """Title: `[FirstDay]`
Canonical Art Style: `[ink wash]`

<!-- ZET:BEGIN STORY_TITLE -->
FirstDay
<!-- ZET:END STORY_TITLE -->

<!-- ZET:BEGIN CANONICAL_ART_STYLE -->
ink wash
<!-- ZET:END CANONICAL_ART_STYLE -->
""",
                encoding="utf-8",
            )
            (story_dir / "At-the-Arch.md").write_text("<!-- ZET:BEGIN SCENE_NAME -->\nAt the Arch\n<!-- ZET:END SCENE_NAME -->\n", encoding="utf-8")
            service = self._service(root)
            service.save_story_settings(story_dir / "FirstDay.story.json", service.create_default_story_settings(story_dir / "FirstDay.md"))
            service.scene_builder_json_path("FirstDay", "At-the-Arch").write_text(
                json.dumps(
                    {
                        "schema_version": 3,
                        "setup": {"canvas": {"orientation": "landscape", "aspect_ratio": "16:9"}},
                        "scene_elements": [{"id": "tsa", "display_name": "Tsaeytte", "element_type": "Character"}],
                        "placements": [{"scene_element_id": "tsa", "pose": {"gaze_target_element_id": "missing"}}],
                    }
                ),
                encoding="utf-8",
            )

            service.stage_scene_render("FirstDay", "At-the-Arch")

            validation = json.loads((root / "Pipelines" / "Stories" / "FirstDay" / "At-the-Arch" / "Scene_Render_Validation.json").read_text(encoding="utf-8"))
            self.assertTrue(any("gaze target references missing element missing" in warning for warning in validation["warnings"]))
            self.assertIn("No Story Beat specified.", validation["warnings"])

    def test_story_and_scene_orders_are_persisted_independently_of_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = self._service(root)
            for story_slug in ("Alpha", "Beta"):
                folder = root / "Stories" / story_slug
                folder.mkdir(parents=True)
                story_path = folder / f"{story_slug}.md"
                story_path.write_text(f"Title: `[{story_slug}]`\n", encoding="utf-8")
                settings = service.create_default_story_settings(story_path)
                settings["scene_index"] = []
                service.save_story_settings(folder / f"{story_slug}.story.json", settings)
            alpha = root / "Stories" / "Alpha"
            for slug in ("First", "Second"):
                (alpha / f"{slug}.md").write_text(f"Scene: `[{slug}]`\n", encoding="utf-8")

            service.reorder_stories(["Beta", "Alpha"])
            service.reorder_scenes("Alpha", ["Second", "First"])

            self.assertEqual(["Beta", "Alpha"], [record.slug for record in service.list_stories()])
            self.assertEqual(["Second", "First"], [record.slug for record in service.list_scenes("Alpha")])


    def test_move_scene_moves_artifacts_orders_and_structured_references(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = self._service(root)
            for story_slug in ("Source", "Target"):
                folder = root / "Stories" / story_slug
                folder.mkdir(parents=True)
                story_path = folder / f"{story_slug}.md"
                story_path.write_text(f"Title: `[{story_slug}]`\n", encoding="utf-8")
                settings = service.create_default_story_settings(story_path)
                settings["scene_index"] = ["Opening"] if story_slug == "Source" else []
                service.save_story_settings(folder / f"{story_slug}.story.json", settings)
            source = root / "Stories" / "Source"
            (source / "Opening.md").write_text("Scene: `[Opening]`\n", encoding="utf-8")
            (source / "Opening.png").write_bytes(b"image")
            (source / "Opening.scene.json").write_text(
                json.dumps({
                    "schema_version": 3,
                    "file_kind": "scene",
                    "scene": {
                        "slug": "Opening",
                        "name": "Opening",
                        "story_settings_path": "Stories/Source/Source.story.json",
                        "associated_png_path": "Stories/Source/Opening.png",
                    },
                }),
                encoding="utf-8",
            )
            pipeline = root / "Pipelines" / "Stories" / "Source" / "Opening"
            pipeline.mkdir(parents=True)
            (pipeline / "dependency_manifest.json").write_text(
                json.dumps({"story_slug": "Source", "scene_slug": "Opening"}), encoding="utf-8"
            )
            candidate_dir = pipeline / "Candidate"
            candidate_dir.mkdir()
            (candidate_dir / "Opening.png").write_bytes(b"candidate")
            zine = root / "Assets" / "Zines" / "Sample"
            zine.mkdir(parents=True)
            (zine / "Sample.json").write_text('{"front":"{{SCENE:Source:Opening}}"}', encoding="utf-8")

            document = service.move_scene("Source", "Opening", "Target")

            target = root / "Stories" / "Target"
            self.assertEqual("Target", document.story.slug)
            for suffix in (".md", ".png", ".scene.json"):
                self.assertTrue((target / f"Opening{suffix}").exists())
            self.assertFalse((source / "Opening.md").exists())
            self.assertTrue((root / "Pipelines" / "Stories" / "Target" / "Opening").exists())
            self.assertEqual(
                b"candidate",
                (root / "Pipelines" / "Stories" / "Target" / "Opening" / "Candidate" / "Opening.png").read_bytes(),
            )
            self.assertEqual([], [record.slug for record in service.list_scenes("Source")])
            self.assertEqual(["Opening"], [record.slug for record in service.list_scenes("Target")])
            scene_data = json.loads((target / "Opening.scene.json").read_text(encoding="utf-8"))
            self.assertEqual("Stories/Target/Target.story.json", scene_data["scene"]["story_settings_path"])
            self.assertIn("{{SCENE:Target:Opening}}", (zine / "Sample.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
