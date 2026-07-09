from pathlib import Path
import tempfile
import unittest

from zet.services.config_service import Config
from zet.services.path_service import PathService
from zet.services.story_service import StoryService


class FakeAuxiliaryResource:
    def __init__(self, resource_id: str, category: str, label: str, tag: str, image_path: str):
        self.resource_id = resource_id
        self.category = category
        self.label = label
        self.tag = tag
        self.image_path = image_path


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


class StoryServiceTests(unittest.TestCase):
    def _service(self, root: Path, auxiliary_resource_repository=None) -> StoryService:
        config = Config(
            base_library_path=str(root),
            base_character_path=str(root / "Characters"),
            base_asset_path=str(root / "Assets"),
            base_pipeline_path=str(root / "Pipelines"),
            base_ai_queue_path=str(root / "Queue"),
        )
        return StoryService(PathService(config), None, auxiliary_resource_repository or FakeAuxiliaryResourceRepository())

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

    def test_save_scene_renames_file_from_scene_name(self) -> None:
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

            document = service.save_scene("FirstDay", "Old-Name", text)

            self.assertEqual("02-Campfire", document.record.slug)
            self.assertFalse((story_dir / "Old-Name.md").exists())
            self.assertFalse((story_dir / "Old-Name.png").exists())
            self.assertTrue((story_dir / "02-Campfire.md").exists())
            self.assertEqual(b"image", (story_dir / "02-Campfire.png").read_bytes())

    def test_create_story_handles_story_heading_before_compiler_sections(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            stories = root / "Stories"
            stories.mkdir(parents=True)
            (stories / "_Story_Template.md").write_text(
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
{{AUX:place:arch}}
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
                        "{{AUX:place:arch}}",
                        "AuxiliaryResources/Images/place/arch.png",
                    )
                ]
            )
            service = self._service(root, repository)

            task = service.stage_scene_render("FirstDay", "At-the-Arch")

            prompt = Path(task.final_prompt_path).read_text(encoding="utf-8")
            self.assertIn("FirstDay", prompt)
            self.assertIn("ink wash", prompt)
            self.assertIn("The Scene:\nTwo students meet at the arch.", prompt)
            self.assertNotIn("[story title]", prompt)
            self.assertNotIn("Short premise", prompt)
            self.assertEqual(1, len(task.reference_files))
            self.assertTrue((Path(task.ask_path) / "ask_manifest.json").exists())
            self.assertEqual(prompt, (Path(task.ask_path) / "Final_Image_Prompt.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
