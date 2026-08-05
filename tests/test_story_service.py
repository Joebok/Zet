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
    def test_story_service_reexports_story_models(self):
        for name in (
            "StoryRecord", "SceneRecord", "StoryDocument", "SceneDocument",
            "SceneBuilderDocument", "ImageReferenceRow", "StoryRenderTask", "StoryGitResult",
        ):
            self.assertIs(getattr(story_service_module, name), getattr(story_models, name))

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

    def test_composes_scene_document_reference_and_render_services(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = self._service(Path(temp_dir))

            self.assertIsInstance(service.scene_document_service, SceneDocumentService)
            self.assertIsInstance(service.story_reference_service, StoryReferenceService)
            self.assertIsInstance(service.story_render_service, StoryRenderService)

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

    def test_firstday_style_value_is_not_placeholder(self) -> None:
        service = self._service(Path("unused"))
        text = """Title: `[FirstDay]`
Canonical Art Style: `[Painterly semi-realistic, anime-influenced facial proportions]`

<!-- ZET:BEGIN STORY_TITLE -->
FirstDay
<!-- ZET:END STORY_TITLE -->

<!-- ZET:BEGIN CANONICAL_ART_STYLE -->
Painterly semi-realistic, anime-influenced facial proportions
<!-- ZET:END CANONICAL_ART_STYLE -->
"""
        self.assertNotIn("Canonical Art Style must be filled in.", service.validate_story_text(text))

    def test_save_story_writes_file_even_with_validation_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = self._service(root)
            text = """Title: `[Story Title]`
Canonical Art Style: `[]`

<!-- ZET:BEGIN STORY_TITLE -->

<!-- ZET:END STORY_TITLE -->

<!-- ZET:BEGIN CANONICAL_ART_STYLE -->

<!-- ZET:END CANONICAL_ART_STYLE -->
"""
            document = service.save_story("FirstDay", text)
            saved_text = (root / "Stories" / "FirstDay" / "FirstDay.md").read_text(encoding="utf-8")
            self.assertEqual(text.rstrip() + "\n", saved_text)
            self.assertTrue(document.validation_errors)

    def test_save_scene_does_not_rename_from_scene_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            story_dir = root / "Stories" / "FirstDay"
            story_dir.mkdir(parents=True)
            service = self._service(root)
            text = """Scene: `[02 Campfire]`

<!-- ZET:BEGIN SCENE_NAME -->
02 Campfire
            <!-- ZET:END SCENE_NAME -->
"""
            (story_dir / "Old-Name.md").write_text(text, encoding="utf-8")
            (story_dir / "Old-Name.png").write_bytes(b"image")
            (story_dir / "Old-Name.scene.json").write_text('{"schema_version": 3}', encoding="utf-8")

            document = service.save_scene("FirstDay", "Old-Name", text)

            self.assertEqual("Old-Name", document.record.slug)
            self.assertTrue((story_dir / "Old-Name.md").exists())
            self.assertEqual(b"image", (story_dir / "Old-Name.png").read_bytes())
            self.assertTrue((story_dir / "Old-Name.scene.json").exists())

    def test_scene_builder_path_mapping_uses_scene_basename(self) -> None:
        service = self._service(Path("unused"))

        self.assertEqual(Path("Scenes/Test_Scene.scene.json"), service.get_scene_builder_json_path(Path("Scenes/Test_Scene.md")))
        self.assertEqual(Path("Scenes/Test_Scene.scene.json"), service.get_scene_builder_json_path(Path("Scenes/Test_Scene.png")))

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

    def test_deprecated_prompt_fields_are_removed_on_save(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            story_dir = root / "Stories" / "FirstDay"
            story_dir.mkdir(parents=True)
            service = self._service(root)
            (story_dir / "FirstDay.md").write_text("Title: `[First Day]`\n", encoding="utf-8")
            (story_dir / "At-the-Arch.md").write_text("Scene: `[At the Arch]`\n", encoding="utf-8")
            settings = service.create_default_story_settings(story_dir / "FirstDay.md")
            self.assertNotIn("default_avoid", settings["style_defaults"])
            self.assertNotIn("include_final_verification", settings["compiler_profiles"]["final_image_prompt"])
            settings["style_defaults"]["default_avoid"] = ["legacy"]
            settings["compiler_profiles"]["final_image_prompt"]["include_final_verification"] = False
            settings["unrelated"] = "preserved"
            settings_path = story_dir / "FirstDay.story.json"

            service.save_story_settings(settings_path, settings)
            saved_settings = json.loads(settings_path.read_text(encoding="utf-8"))
            self.assertNotIn("default_avoid", saved_settings["style_defaults"])
            self.assertNotIn("include_final_verification", saved_settings["compiler_profiles"]["final_image_prompt"])
            self.assertEqual("preserved", saved_settings["unrelated"])

            scene = service.create_default_scene_builder_data("FirstDay", "At-the-Arch")
            scene["setup"]["environment"]["important_exclusions"] = ["legacy"]
            scene["avoid"] = {"scene_specific": ["legacy"]}
            scene["unrelated"] = "preserved"
            document = service.save_scene_builder_data("FirstDay", "At-the-Arch", scene)

            self.assertNotIn("important_exclusions", document.data["setup"]["environment"])
            self.assertNotIn("avoid", document.data)
            self.assertEqual("preserved", document.data["unrelated"])
            self.assertEqual(
                {"anatomical_requirements", "avoid", "high_risk_elements", "final_verification"},
                set(document.data["final_image_prompt_overrides"]),
            )

    def test_scene_builder_world_position_is_trimmed_and_blank_is_omitted(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            story_dir = root / "Stories" / "FirstDay"
            story_dir.mkdir(parents=True)
            service = self._service(root)
            (story_dir / "FirstDay.md").write_text("Title: `[First Day]`\n", encoding="utf-8")
            (story_dir / "At-the-Arch.md").write_text("Scene: `[At the Arch]`\n", encoding="utf-8")
            data = service.create_default_scene_builder_data("FirstDay", "At-the-Arch")
            data["scene_elements"] = [
                {"id": "Tsaeytte", "display_name": "Tsaeytte", "element_type": "Character"},
                {"id": "Rin", "display_name": "Rin", "element_type": "Character"},
            ]
            data["placements"] = [
                {"scene_element_id": "Tsaeytte", "world_position": "  at the edge of the pit  "},
                {"scene_element_id": "Rin", "world_position": "   "},
            ]

            document = service.save_scene_builder_data("FirstDay", "At-the-Arch", data)

            self.assertEqual("at the edge of the pit", document.data["placements"][0]["world_position"])
            self.assertNotIn("world_position", document.data["placements"][1])
            reloaded = service.load_scene_builder_data("FirstDay", "At-the-Arch")
            self.assertEqual("at the edge of the pit", reloaded.data["placements"][0]["world_position"])

    def test_continue_scene_builder_copies_visual_setup_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            story_dir = root / "Stories" / "FirstDay"
            story_dir.mkdir(parents=True)
            service = self._service(root)
            (story_dir / "FirstDay.md").write_text("Title: `[First Day]`\n", encoding="utf-8")
            for scene_slug in ("Arrival", "Departure"):
                (story_dir / f"{scene_slug}.md").write_text(f"Scene: `[{scene_slug}]`\n", encoding="utf-8")

            source = service.create_default_scene_builder_data("FirstDay", "Arrival")
            source["setup"]["canvas"] = {"orientation": "landscape", "aspect_ratio": "16:9"}
            source["setup"]["composition"] = {"focal_point": "Mira", "left_to_right": ["Mira"], "composition_notes": "wide"}
            source["setup"]["environment"] = {"location": "Courtyard", "lighting": "Sunset"}
            source["scene_elements"] = [
                {"id": "Mira", "display_name": "Mira", "element_type": "Character"},
                {"id": "Courtyard", "display_name": "Courtyard", "element_type": "Backdrop"},
            ]
            source["placements"] = [
                {"id": "placement_001", "scene_element_id": "Mira", "position_within_cell": "left", "depth": "foreground"},
                {"id": "placement_002", "scene_element_id": "Courtyard", "position_within_cell": "", "depth": "background"},
            ]
            service.save_scene_builder_data("FirstDay", "Arrival", source)

            target = service.create_default_scene_builder_data("FirstDay", "Departure")
            target["interactions"] = [{"subject_element_id": "Old", "relationship": "looks at", "target_element_id": "Other"}]
            target["dialogue"] = [{"speaker_element_id": "Old", "text": "Keep this."}]
            service.save_scene_builder_data("FirstDay", "Departure", target)

            document = service.continue_scene_builder_from("FirstDay", "Departure", "Arrival")

            self.assertEqual("landscape", document.data["setup"]["canvas"]["orientation"])
            self.assertEqual("16:9", document.data["setup"]["canvas"]["aspect_ratio"])
            self.assertEqual(source["setup"]["composition"], document.data["setup"]["composition"])
            self.assertEqual("Courtyard", document.data["setup"]["environment"]["location"])
            self.assertEqual("Mira", document.data["scene_elements"][0]["id"])
            self.assertEqual("Courtyard", document.data["scene_elements"][1]["id"])
            self.assertEqual("Mira", document.data["placements"][0]["scene_element_id"])
            self.assertEqual(target["interactions"], document.data["interactions"])
            self.assertEqual(target["dialogue"], document.data["dialogue"])

    def test_scene_builder_load_rejects_v1_character(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            story_dir = root / "Stories" / "FirstDay"
            story_dir.mkdir(parents=True)
            service = self._service(root)
            (story_dir / "FirstDay.md").write_text("Title: `[First Day]`\n", encoding="utf-8")
            (story_dir / "At-the-Arch.md").write_text("Scene: `[At the Arch]`\n", encoding="utf-8")
            (story_dir / "At-the-Arch.scene.json").write_text(
                json.dumps({
                    "schema_version": 1,
                    "characters": [{
                        "id": "Tsaeytte",
                        "display_name": "Tsaeytte",
                        "asset_tag": "{{ASSET:Tsaeytte:Adult:31}}",
                        "identity_prompt": "",
                        "default_costume": "adult adventuring outfit",
                        "notes": "",
                    }],
                    "placements": [{
                        "id": "placement_001",
                        "character_id": "Tsaeytte",
                        "screen_cell": {"row": 2, "column": 1, "name": "lower-left"},
                        "depth": "foreground",
                        "pose": "crouched",
                        "gaze_target": "Teacher",
                        "notes": "test note",
                    }],
                }),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(StoryServiceError, "Unsupported Scene Builder schema_version: 1"):
                service.load_scene_builder_data("FirstDay", "At-the-Arch")

    def test_scene_builder_normalize_creates_paired_placement(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            story_dir = root / "Stories" / "FirstDay"
            story_dir.mkdir(parents=True)
            service = self._service(root)
            (story_dir / "FirstDay.md").write_text("Title: `[First Day]`\n", encoding="utf-8")
            (story_dir / "At-the-Arch.md").write_text("Scene: `[At the Arch]`\n", encoding="utf-8")
            data = service.create_default_scene_builder_data("FirstDay", "At-the-Arch")
            data["scene_elements"] = [{"id": "Door", "display_name": "Door", "element_type": "Backdrop"}]
            data["placements"] = []

            normalized = service._normalize_scene_builder_data("FirstDay", "At-the-Arch", data)

            self.assertEqual(1, len(normalized["placements"]))
            self.assertEqual("Door", normalized["placements"][0]["scene_element_id"])
            self.assertEqual("background", normalized["placements"][0]["depth"])

    def test_scene_builder_prop_defaults_to_suppressed_placement(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            story_dir = root / "Stories" / "FirstDay"
            story_dir.mkdir(parents=True)
            service = self._service(root)
            (story_dir / "FirstDay.md").write_text("Title: `[First Day]`\n", encoding="utf-8")
            (story_dir / "At-the-Arch.md").write_text("Scene: `[At the Arch]`\n", encoding="utf-8")
            data = service.create_default_scene_builder_data("FirstDay", "At-the-Arch")
            data["scene_elements"] = [{"id": "Book", "display_name": "Book", "element_type": "Prop"}]
            data["placements"] = []
            data["setup"]["composition"]["left_to_right"] = ["Book"]

            normalized = service._normalize_scene_builder_data("FirstDay", "At-the-Arch", data)

            self.assertEqual("None", normalized["placements"][0]["position_within_cell"])
            self.assertEqual([], normalized["setup"]["composition"]["left_to_right"])
            self.assertFalse(any("Book" in values for values in normalized["depth_lanes"].values()))

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

    def test_delete_scene_commits_then_removes_markdown_and_png(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            story_dir = root / "Stories" / "FirstDay"
            story_dir.mkdir(parents=True)
            (story_dir / "At-the-Arch.md").write_text("scene", encoding="utf-8")
            (story_dir / "At-the-Arch.png").write_bytes(b"image")
            (story_dir / "At-the-Arch.json").write_text('{"schema_version": 1}', encoding="utf-8")
            candidate_dir = root / "Pipelines" / "Stories" / "FirstDay" / "At-the-Arch" / "Candidate"
            candidate_dir.mkdir(parents=True)
            (candidate_dir / "At-the-Arch.png").write_bytes(b"candidate")
            (candidate_dir / "Render_Review_Comment.md").write_text("pending\n", encoding="utf-8")
            service = self._service(root)
            commits = []
            service.story_git_commit = lambda: commits.append(True) or StoryGitResult("", False)

            service.delete_scene("FirstDay", "At-the-Arch")

            self.assertEqual([True], commits)
            self.assertFalse((story_dir / "At-the-Arch.md").exists())
            self.assertFalse((story_dir / "At-the-Arch.png").exists())
            self.assertFalse((story_dir / "At-the-Arch.json").exists())
            self.assertFalse(candidate_dir.exists())

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

    def test_stage_scene_render_writes_prompt_and_manual_render_ask(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            story_dir = root / "Stories" / "FirstDay"
            story_dir.mkdir(parents=True)
            image_path = root / "AuxiliaryResources" / "Images" / "place" / "arch.png"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"image")
            (story_dir / "FirstDay.md").write_text(
                """Title: `[FirstDay]`
Canonical Art Style: `[ink wash]`

<!-- ZET:BEGIN STORY_TITLE -->
[story title]
<!-- ZET:END STORY_TITLE -->

<!-- ZET:BEGIN CANONICAL_ART_STYLE -->
[Painterly semi-realistic, anime-influenced facial proportions, etc.]
<!-- ZET:END CANONICAL_ART_STYLE -->

<!-- ZET:BEGIN STORY_PREMISE -->
[Short premise, central conflict, emotional arc, or visual theme.]
<!-- ZET:END STORY_PREMISE -->

<!-- ZET:BEGIN STORY_VISUAL_CONTINUITY -->
Keep the arch consistent.
<!-- ZET:END STORY_VISUAL_CONTINUITY -->
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

<!-- ZET:BEGIN SCENE_IMAGE_REFERENCES -->
{{AUX:place:arch:main}}
<!-- ZET:END SCENE_IMAGE_REFERENCES -->

<!-- ZET:BEGIN SCENE_RENDERING_NOTES -->
Morning light.
<!-- ZET:END SCENE_RENDERING_NOTES -->
""",
                encoding="utf-8",
            )
            repository = FakeAuxiliaryResourceRepository(
                [
                    FakeAuxiliaryResource(
                        "arch",
                        "place",
                        "Arch",
                        "{{AUX:place:arch:main}}",
                        "AuxiliaryResources/Images/place/arch.png",
                        images=[{"image_id": "main", "label": "Main", "image_path": "AuxiliaryResources/Images/place/arch.png"}],
                    )
                ]
            )
            service = self._service(root, repository)
            self._write_scene_builder(service, "FirstDay", "At-the-Arch", ["{{AUX:place:arch:main}}"])

            task = service.stage_scene_render("FirstDay", "At-the-Arch")

            prompt = Path(task.final_prompt_path).read_text(encoding="utf-8")
            self.assertIn("academy archway", prompt)
            self.assertIn("morning light", prompt)
            self.assertNotIn("[story title]", prompt)
            self.assertNotIn("Short premise", prompt)
            self.assertEqual(1, len(task.reference_files))
            self.assertTrue((Path(task.ask_path) / "ask_manifest.json").exists())
            self.assertEqual(prompt, (Path(task.ask_path) / "Final_Image_Prompt.md").read_text(encoding="utf-8"))
            manifest = json.loads((Path(task.ask_path) / "ask_manifest.json").read_text(encoding="utf-8"))
            self.assertTrue(manifest["scene_image_review"])
            self.assertEqual(
                str(root / "Pipelines" / "Stories" / "FirstDay" / "At-the-Arch" / "Candidate" / "At-the-Arch.png"),
                manifest["target_output_file"],
            )

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

    def test_image_reference_rows_uses_descriptive_asset_tag(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            image_path = root / "Assets" / "Tsaeytte" / "Youth" / "woodland.png"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"image")
            (root / "Characters" / "Tsaeytte" / "Youth").mkdir(parents=True)
            asset = Asset(
                29,
                "Tsaeytte",
                "Youth",
                "Costume-Dressing",
                "Back",
                costume="Woodland outfit",
                asset_state="LOCKED",
                pipeline_stage="LOCKED",
                final_image_output="woodland.png",
            )
            service = self._service(root, asset_repository=FakeAssetRepository([asset]))

            rows = service.image_reference_rows(text_filter="Woodland outfit")

            self.assertEqual(1, len(rows))
            self.assertEqual("{{ASSET:Tsaeytte:Youth:29:Costume | Back | Woodland outfit}}", rows[0].tag)

    def test_image_reference_rows_matches_all_space_separated_terms(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "Characters" / "Tsaeytte" / "Adult").mkdir(parents=True)
            assets = [
                Asset(
                    asset_id,
                    "Tsaeytte",
                    "Adult",
                    "Costume-Dressing",
                    view,
                    costume="Canonical Adventure Gear",
                    asset_state="LOCKED",
                    pipeline_stage="LOCKED",
                    final_image_output=f"asset-{asset_id}.png",
                )
                for asset_id, view in [(25, "Front"), (26, "Front-Left-3-4"), (27, "Front-Right-3-4")]
            ]
            service = self._service(root, asset_repository=FakeAssetRepository(assets))

            rows = service.image_reference_rows(text_filter="tsaeytte adult adventure gear front")

            self.assertEqual([25, 26, 27], [int(row.tag.split(":")[3]) for row in rows])

    def test_image_reference_rows_exposes_only_full_locked_turnarounds(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            phase_path = root / "Characters" / "Tsaeytte" / "Youth"
            phase_path.mkdir(parents=True)
            locked_path = root / "Assets" / "Tsaeytte" / "Youth" / "Turnarounds" / "Costume-Woodland-outfit.png"
            locked_path.parent.mkdir(parents=True)
            locked_path.write_bytes(b"image")
            sheets = [
                TurnaroundSheet(
                    "Costume-Woodland-outfit",
                    "Tsaeytte",
                    "Youth",
                    "Costume-Dressing",
                    costume="Woodland outfit",
                    sheet_type="full",
                    status="RENDER_REVIEW",
                    source_asset_ids=[26, 27],
                    locked_image_path=str(locked_path),
                ),
                TurnaroundSheet(
                    "Costume-Woodland-outfit__partial__head",
                    "Tsaeytte",
                    "Youth",
                    "Costume-Dressing",
                    costume="Woodland outfit",
                    sheet_type="partial",
                    parent_turnaround_id="Costume-Woodland-outfit",
                    status="LOCKED",
                    source_asset_ids=[26, 27],
                    locked_image_path=str(locked_path),
                ),
            ]
            service = self._service(root, turnaround_repository=FakeTurnaroundRepository(sheets))

            rows = service.image_reference_rows(text_filter="Tsaeytte Youth Woodland outfit")

            self.assertEqual(1, len(rows))
            self.assertEqual(
                "{{ASSET:Tsaeytte:Youth:26:Costume | Turnaround | Woodland outfit}}",
                rows[0].tag,
            )

    def test_descriptive_turnaround_tag_resolves_locked_sheet(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            locked_path = root / "Assets" / "Tsaeytte" / "Youth" / "Turnarounds" / "Costume-Woodland-outfit.png"
            locked_path.parent.mkdir(parents=True)
            locked_path.write_bytes(b"image")
            sheet = TurnaroundSheet(
                "Costume-Woodland-outfit",
                "Tsaeytte",
                "Youth",
                "Costume-Dressing",
                costume="Woodland outfit",
                label="Costume-Dressing | Woodland outfit",
                status="RENDER_REVIEW",
                source_asset_ids=[26, 27],
                locked_image_path=str(locked_path),
            )
            service = self._service(root, turnaround_repository=FakeTurnaroundRepository([sheet]))
            tag = "{{ASSET:Tsaeytte:Youth:26:Costume | Turnaround | Woodland outfit}}"

            reference = service.story_reference_service.resolve_image_tag(tag)

            self.assertEqual(str(locked_path), reference["path"])
            self.assertEqual("turnaround", reference["kind"])
            self.assertEqual("Costume-Woodland-outfit", reference["turnaround_id"])

    def test_context_reference_filter_includes_disabled_matching_turnaround(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "Characters" / "Tsaeytte" / "Youth").mkdir(parents=True)
            sheets = [
                TurnaroundSheet(
                    "Costume-Woodland-outfit",
                    "Tsaeytte",
                    "Youth",
                    "Costume-Dressing",
                    costume="Woodland outfit",
                    source_asset_ids=[26],
                    locked_image_path=None,
                ),
                TurnaroundSheet(
                    "Costume-Formal",
                    "Tsaeytte",
                    "Youth",
                    "Costume-Dressing",
                    costume="Formal",
                    source_asset_ids=[27],
                    locked_image_path=None,
                ),
            ]
            service = self._service(
                root,
                turnaround_repository=FakeTurnaroundRepository(sheets),
            )

            rows = service.image_reference_rows(
                character_filter="Tsaeytte",
                phase_filter="Youth",
                costume_filter="Woodland outfit",
                scope="context",
                include_unavailable=True,
            )

            self.assertEqual(1, len(rows))
            self.assertFalse(rows[0].available)
            self.assertEqual("Turnaround has no locked image.", rows[0].disabled_reason)

    def test_stage_scene_render_resolves_old_and_descriptive_asset_tags(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            story_dir = root / "Stories" / "FirstDay"
            story_dir.mkdir(parents=True)
            image_path = root / "Assets" / "Tsaeytte" / "Youth" / "woodland.png"
            image_path.parent.mkdir(parents=True)
            image_path.write_bytes(b"image")
            asset = Asset(
                29,
                "Tsaeytte",
                "Youth",
                "Costume-Dressing",
                "Back",
                costume="Woodland outfit",
                asset_state="LOCKED",
                pipeline_stage="LOCKED",
                final_image_output="woodland.png",
            )
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
            service = self._service(root, asset_repository=FakeAssetRepository([asset]))
            for tag in [
                "{{ASSET:Tsaeytte:Youth:29}}",
                "{{ASSET:Tsaeytte:Youth:29:Costume | Back | Woodland outfit}}",
            ]:
                (story_dir / "At-the-Arch.md").write_text(
                    f"""<!-- ZET:BEGIN SCENE_NAME -->
At the Arch
<!-- ZET:END SCENE_NAME -->

<!-- ZET:BEGIN SCENE_DESCRIPTION -->
Two students meet.
<!-- ZET:END SCENE_DESCRIPTION -->

<!-- ZET:BEGIN SCENE_IMAGE_REFERENCES -->
{tag}
<!-- ZET:END SCENE_IMAGE_REFERENCES -->

<!-- ZET:BEGIN SCENE_RENDERING_NOTES -->
Morning light.
<!-- ZET:END SCENE_RENDERING_NOTES -->
""",
                    encoding="utf-8",
                )
                self._write_scene_builder(service, "FirstDay", "At-the-Arch", [tag])

                task = service.stage_scene_render("FirstDay", "At-the-Arch")

                self.assertEqual(1, len(task.reference_files))
                self.assertEqual(str(image_path), task.reference_files[0]["path"])
                self.assertEqual(tag, task.reference_files[0]["tag"])

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

    def test_stage_scene_render_reads_scene_character_and_costume_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            story_dir = root / "Stories" / "FirstDay"
            story_dir.mkdir(parents=True)
            character_dir = root / "Characters" / "Tsaeytte" / "Adult"
            character_dir.mkdir(parents=True)
            service = self._service(root)
            (story_dir / "FirstDay.md").write_text("Title: `[FirstDay]`\n", encoding="utf-8")
            service.save_story_settings(story_dir / "FirstDay.story.json", service.create_default_story_settings(story_dir / "FirstDay.md"))
            (story_dir / "At-the-Arch.md").write_text("<!-- ZET:BEGIN SCENE_NAME -->\nAt the Arch\n<!-- ZET:END SCENE_NAME -->\n", encoding="utf-8")
            (character_dir / "Character_Image_Template.md").write_text(
                "<!-- ZET:BEGIN IDENTITY_PRESERVATION_SCENE -->\ncore identity from character\n<!-- ZET:END IDENTITY_PRESERVATION_SCENE -->\n",
                encoding="utf-8",
            )
            (character_dir / "Costume_Canonical_Adventure_Gear.md").write_text(
                "<!-- ZET:BEGIN IDENTITY_PRESERVATION_COSTUME_SCENE -->\ncostume identity from costume\n<!-- ZET:END IDENTITY_PRESERVATION_COSTUME_SCENE -->\n",
                encoding="utf-8",
            )
            data = service.create_default_scene_builder_data("FirstDay", "At-the-Arch")
            data["scene_elements"] = [{
                "id": "tsa",
                "display_name": "Tsaeytte",
                "resource_type": "Character",
                "element_type": "Character",
                "character": "Tsaeytte",
                "phase": "Adult",
                "costume": "Canonical Adventure Gear",
            }]
            service.scene_builder_json_path("FirstDay", "At-the-Arch").write_text(json.dumps(data), encoding="utf-8")

            task = service.stage_scene_render("FirstDay", "At-the-Arch")

            prompt = Path(task.final_prompt_path).read_text(encoding="utf-8")
            self.assertIn("core identity from character", prompt)
            self.assertIn("costume identity from costume", prompt)
            source_map = json.loads((Path(task.pipeline_path) / "Prompt_Source_Map.json").read_text(encoding="utf-8"))
            identity_source = next(
                fragment for fragment in source_map["fragments"] if fragment.get("source_label") == "Tsaeytte identity"
            )
            costume_source = next(
                fragment for fragment in source_map["fragments"] if fragment.get("source_label") == "Tsaeytte costume"
            )
            self.assertEqual("IDENTITY_PRESERVATION_SCENE", identity_source["section_name"])
            self.assertEqual("IDENTITY_PRESERVATION_COSTUME_SCENE", costume_source["section_name"])

    def test_stage_scene_render_omits_costume_information_when_costume_is_blank(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            story_dir = root / "Stories" / "FirstDay"
            story_dir.mkdir(parents=True)
            character_dir = root / "Characters" / "Tsaeytte" / "Adult"
            character_dir.mkdir(parents=True)
            service = self._service(root)
            (story_dir / "FirstDay.md").write_text("Title: `[FirstDay]`\n", encoding="utf-8")
            service.save_story_settings(story_dir / "FirstDay.story.json", service.create_default_story_settings(story_dir / "FirstDay.md"))
            (story_dir / "At-the-Arch.md").write_text("<!-- ZET:BEGIN SCENE_NAME -->\nAt the Arch\n<!-- ZET:END SCENE_NAME -->\n", encoding="utf-8")
            (character_dir / "Character_Image_Template.md").write_text(
                "<!-- ZET:BEGIN IDENTITY_PRESERVATION_SCENE -->\ncore identity from character\n<!-- ZET:END IDENTITY_PRESERVATION_SCENE -->\n",
                encoding="utf-8",
            )
            (character_dir / "Costume_Canonical_Adventure_Gear.md").write_text(
                "<!-- ZET:BEGIN IDENTITY_PRESERVATION_COSTUME_SCENE -->\ncostume identity from costume\n<!-- ZET:END IDENTITY_PRESERVATION_COSTUME_SCENE -->\n",
                encoding="utf-8",
            )
            data = service.create_default_scene_builder_data("FirstDay", "At-the-Arch")
            data["scene_elements"] = [{
                "id": "tsa",
                "display_name": "Tsaeytte",
                "resource_type": "Character",
                "element_type": "Character",
                "character": "Tsaeytte",
                "phase": "Adult",
                "costume": "",
            }]
            service.scene_builder_json_path("FirstDay", "At-the-Arch").write_text(json.dumps(data), encoding="utf-8")

            task = service.stage_scene_render("FirstDay", "At-the-Arch")

            prompt = Path(task.final_prompt_path).read_text(encoding="utf-8")
            self.assertIn("core identity from character", prompt)
            self.assertNotIn("costume identity from costume", prompt)
            source_map = json.loads((Path(task.pipeline_path) / "Prompt_Source_Map.json").read_text(encoding="utf-8"))
            self.assertFalse(any(
                fragment.get("source_label") == "Tsaeytte costume"
                for fragment in source_map["fragments"]
            ))

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

    def test_rename_updates_titles_without_changing_slugs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = self._service(root)
            folder = root / "Stories" / "FirstDay"
            folder.mkdir(parents=True)
            story_path = folder / "FirstDay.md"
            story_path.write_text(
                "Title: `[First Day]`\n<!-- ZET:BEGIN STORY_TITLE -->\nFirst Day\n<!-- ZET:END STORY_TITLE -->\n",
                encoding="utf-8",
            )
            service.save_story_settings(folder / "FirstDay.story.json", service.create_default_story_settings(story_path))
            scene_path = folder / "Opening.md"
            scene_path.write_text(
                "Scene: `[Opening]`\n<!-- ZET:BEGIN SCENE_NAME -->\nOpening\n<!-- ZET:END SCENE_NAME -->\n",
                encoding="utf-8",
            )
            (folder / "Opening.scene.json").write_text(
                json.dumps({"schema_version": 3, "file_kind": "scene", "scene": {"slug": "Opening", "name": "Opening"}}),
                encoding="utf-8",
            )

            story = service.rename_story("FirstDay", "A Better Day")
            scene = service.rename_scene("FirstDay", "Opening", "At the Gate")

            self.assertEqual("FirstDay", story.record.slug)
            self.assertEqual("Opening", scene.record.slug)
            self.assertIn("A Better Day", story_path.read_text(encoding="utf-8"))
            story_settings = json.loads((folder / "FirstDay.story.json").read_text(encoding="utf-8"))
            self.assertEqual("A Better Day", story_settings["story"]["title"])
            self.assertEqual("FirstDay", story_settings["story"]["slug"])
            self.assertEqual("firstday", story_settings["story"]["id"])
            self.assertIn("At the Gate", scene_path.read_text(encoding="utf-8"))
            self.assertEqual("At the Gate", json.loads((folder / "Opening.scene.json").read_text(encoding="utf-8"))["scene"]["name"])

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
