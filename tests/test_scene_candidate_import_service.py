import json
from pathlib import Path
import tempfile
import unittest

from zet.services.config_service import Config, SceneCandidateSourceConfig
from zet.services.path_service import PathService
from zet.services.scene_candidate_import_service import SceneCandidateImportError, SceneCandidateImportService
from zet.services.story_service import StoryService


class EmptyAssetRepository:
    def list_assets(self, character, phase):
        return []


class AuxiliaryResource:
    def __init__(self, resource_id, category, label, tag=""):
        self.resource_id = resource_id
        self.category = category
        self.label = label
        self.template_path = ""
        self.images = [{"tag": tag}] if tag else []


class AuxiliaryRepository:
    def __init__(self, resources=None):
        self.resources = resources or []

    def list_resources(self):
        return list(self.resources)

    def get_resource(self, resource_id):
        return next(item for item in self.resources if item.resource_id == resource_id)


class SceneCandidateImportServiceTests(unittest.TestCase):
    def _setup(self, root: Path, markdown: str, resources=None):
        source = root / "Scene_Candidate_Index.md"
        source.write_text(markdown, encoding="utf-8")
        config = Config(
            base_library_path=str(root),
            base_character_path=str(root / "Characters"),
            base_asset_path=str(root / "Assets"),
            base_pipeline_path=str(root / "Pipelines"),
            base_ai_queue_path=str(root / "Queue"),
            scene_candidate_sources=(SceneCandidateSourceConfig(
                key="moonsea",
                label="Moonsea",
                path=str(source),
                default_story_slug="Moonsea",
            ),),
        )
        shared = root / "Shared_Library" / "Stories"
        shared.mkdir(parents=True)
        (shared / "_Scene_Template.md").write_text("Scene: `[scene title]`\n", encoding="utf-8")
        story_dir = root / "Stories" / "Moonsea"
        story_dir.mkdir(parents=True)
        (story_dir / "Moonsea.md").write_text("Title: `[Moonsea]`\n", encoding="utf-8")
        aux = AuxiliaryRepository(resources)
        story = StoryService(PathService(config, root), EmptyAssetRepository(), aux)
        story.save_story_settings(story_dir / "Moonsea.story.json", story.create_default_story_settings(story_dir / "Moonsea.md"))
        return source, story, SceneCandidateImportService(config, story)

    def _candidate(self, candidate_id="moonsea-test-a", title="A Test"):
        return f"""# Candidates

### Scene TEST-A — {title}

**Candidate ID:** {candidate_id}
**Source Session:** Session 001 — Test
**Status:** Candidate
**Story Beat:** Tsaeytte studies a strange visitor.
**Depicted Moment:** Tsaeytte points toward the visitor while Rin watches.
**Characters Present:**
- Tsaeytte
- Rin
- Jero
**Visible Elements:**
- Tsaeytte: pointing toward Jero
- Rin: watching from the side
- Jero: receiving the question
**Known Visual Facts:**
- Tsaeytte: established adult appearance
- Rin: established appearance
- Jero: Unknown
**Location:** Fountain plaza
**Lighting:** Blue twilight
**Mood:** Curious
**Atmosphere:** Fine mist
**Acting and Placement:**
- Tsaeytte: foreground, pointing toward Jero
- Rin: background, watching Jero
- Jero: midground, facing Tsaeytte
**Focal Point:** Tsaeytte
**Reading Order:**
- Tsaeytte
- Jero
- Rin
**Suggested Composition:** Medium-wide triangular grouping.
**Visible Dialogue:**
- None
"""

    def test_parses_structured_candidate_and_flags_unknown_visual(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, _, service = self._setup(root, self._candidate())

            candidate = service.list_candidates("moonsea")[0]

            self.assertEqual(candidate.candidate_id, "moonsea-test-a")
            self.assertEqual(candidate.title, "A Test")
            self.assertEqual(candidate.fields["Visible Elements"][0], "Tsaeytte: pointing toward Jero")

    def test_import_resolves_unique_resources_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "Characters" / "Tsaeytte" / "Adult").mkdir(parents=True)
            resources = [AuxiliaryResource("rin", "person", "Rin", "{{AUX:person:rin:rin}}")]
            _, _, service = self._setup(root, self._candidate(), resources)

            first = service.import_candidate("moonsea", "moonsea-test-a", "Moonsea")
            second = service.import_candidate("moonsea", "moonsea-test-a", "Moonsea")

            self.assertTrue(first.created)
            self.assertFalse(second.created)
            self.assertEqual(first.scene_slug, second.scene_slug)
            elements = {item["display_name"]: item for item in first.data["scene_elements"]}
            self.assertEqual(elements["Tsaeytte"]["resource_type"], "Character")
            self.assertEqual(elements["Rin"]["reference_set_id"], "rin")
            self.assertEqual(elements["Rin"]["fallback_visual_description"], "")
            self.assertEqual(elements["Jero"]["resource_type"], "Person")
            self.assertTrue(elements["Jero"]["notes"].startswith("UNRESOLVED:"))
            tsaeytte_placement = next(
                item for item in first.data["placements"]
                if item["scene_element_id"] == elements["Tsaeytte"]["id"]
            )
            self.assertEqual(tsaeytte_placement["pose"]["summary"], "")
            self.assertEqual(tsaeytte_placement["placement_notes"], "foreground, pointing toward Jero")
            self.assertNotIn("visual_scale", tsaeytte_placement)
            self.assertNotIn("left_arm_action", tsaeytte_placement["pose"])
            self.assertNotIn("author_notes", first.data["scene"])
            self.assertEqual(first.data["source_provenance"]["candidate_id"], "moonsea-test-a")
            self.assertIn("elements", first.interview_phases)
            self.assertIn("placements", first.interview_phases)
            tsaeytte_placement["pose"]["summary"] = "lower-center foreground, kneeling"
            self.assertIn("placements", service._interview_phases(first.data))
            self.assertEqual(service.list_candidates("moonsea")[0].imported_scene_slug, first.scene_slug)

    def test_import_uses_selected_story(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, story, service = self._setup(root, self._candidate())
            target_slug = story.safe_slug("Other Story")
            target_dir = root / "Stories" / target_slug
            target_dir.mkdir(parents=True)
            target_path = target_dir / f"{target_slug}.md"
            target_path.write_text("Title: `[Other Story]`\n", encoding="utf-8")
            story.save_story_settings(
                target_dir / f"{target_slug}.story.json",
                story.create_default_story_settings(target_path),
            )

            imported = service.import_candidate("moonsea", "moonsea-test-a", target_slug)

            self.assertEqual(imported.story_slug, target_slug)
            self.assertTrue(story.scene_builder_json_path(target_slug, imported.scene_slug).is_file())


    def test_changed_source_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source, _, service = self._setup(root, self._candidate())
            service.import_candidate("moonsea", "moonsea-test-a", "Moonsea")
            source.write_text(self._candidate(title="Changed Title"), encoding="utf-8")

            with self.assertRaisesRegex(SceneCandidateImportError, "confirm re-import"):
                service.import_candidate("moonsea", "moonsea-test-a", "Moonsea")

            updated = service.import_candidate("moonsea", "moonsea-test-a", "Moonsea", confirm_update=True)
            self.assertEqual(updated.data["scene"]["name"], "Changed Title")

    def test_pass_and_activate_restore_underlying_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, _, service = self._setup(root, self._candidate())

            passed = service.set_passed("moonsea", "moonsea-test-a", True)
            self.assertEqual(passed.import_state, "passed")

            activated = service.set_passed("moonsea", "moonsea-test-a", False)
            self.assertEqual(activated.import_state, "available")
            state = json.loads((root / "Config" / "Scene_Candidate_State.json").read_text(encoding="utf-8"))
            self.assertEqual(state["passed"], [])

    def test_rendered_candidate_exposes_image_and_cannot_be_passed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, story, service = self._setup(root, self._candidate())
            imported = service.import_candidate("moonsea", "moonsea-test-a", "Moonsea")
            image = story.scene_image_path(imported.story_slug, imported.scene_slug)
            image.parent.mkdir(parents=True, exist_ok=True)
            image.write_bytes(b"rendered")

            self.assertEqual(service.candidate_image_path("moonsea", "moonsea-test-a"), image)
            with self.assertRaisesRegex(SceneCandidateImportError, "cannot be passed"):
                service.set_passed("moonsea", "moonsea-test-a", True)


    def test_duplicate_ids_block_import_but_extra_sections_do_not(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            markdown = self._candidate() + "\n**Extra Field:** preserved\n" + self._candidate(title="Second")
            _, _, service = self._setup(root, markdown)

            candidates = service.list_candidates("moonsea")
            self.assertEqual(len(candidates), 2)
            self.assertTrue(all("Duplicate Candidate ID." in item.warnings for item in candidates))
            with self.assertRaisesRegex(SceneCandidateImportError, "Duplicate Candidate ID"):
                service.import_candidate("moonsea", "moonsea-test-a", "Moonsea")


if __name__ == "__main__":
    unittest.main()
