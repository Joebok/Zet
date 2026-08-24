import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from zet.models.asset import Asset
from zet.services.workspace_summary_service import WorkspaceSummaryService


class WorkspaceSummaryServiceTests(unittest.TestCase):
    def _service(self, root: Path, assets=None):
        onboarding = Mock()
        onboarding.status.return_value = SimpleNamespace(complete=True, assets_exists=True)
        repository = Mock()
        repository.list_assets.return_value = assets or []
        identity = Mock()
        identity.list_identity_keys.return_value = []
        turnaround = Mock()
        turnaround.list_rows.return_value = []
        costume = Mock()
        costume.list_costumes.return_value = []
        expression = Mock()
        expression.list_expression_definitions.return_value = []
        story = Mock()
        story.list_stories.return_value = []
        story.list_scenes.return_value = []
        paths = Mock()
        paths.scene_locked_image_path.side_effect = lambda story_slug, scene_slug: root / story_slug / f"{scene_slug}.png"
        paths.scene_candidate_image_path.side_effect = lambda story_slug, scene_slug: root / story_slug / "Candidate" / f"{scene_slug}.png"
        return WorkspaceSummaryService(
            onboarding,
            repository,
            identity,
            turnaround,
            costume,
            expression,
            story,
            paths,
        )

    def test_character_summary_recommends_first_incomplete_step(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            assets = [
                Asset(1, "Test", "Adult", "Body-Reference", "Front", asset_state="LOCKED"),
                Asset(2, "Test", "Adult", "Character-Assembly", "Front"),
            ]
            summary = self._service(Path(temp_dir), assets).character_summary("Test", "Adult")

        self.assertEqual(summary.base_reference_locked, 1)
        self.assertEqual(summary.assembly_locked, 0)
        self.assertEqual(summary.recommended_destination, "assets")
        self.assertEqual(summary.recommended_action, "Complete character assembly")
        self.assertEqual([step.key for step in summary.steps], ["setup", "references", "assembly", "identity", "costumes"])

    def test_story_summary_reports_candidate_locked_and_next_action(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = self._service(root)
            service.story_service.list_stories.return_value = [SimpleNamespace(slug="demo", title="Demo")]
            service.story_service.list_scenes.return_value = [
                SimpleNamespace(slug="opening", title="Opening"),
                SimpleNamespace(slug="closing", title="Closing"),
            ]
            locked = root / "demo" / "opening.png"
            candidate = root / "demo" / "Candidate" / "closing.png"
            locked.parent.mkdir(parents=True)
            candidate.parent.mkdir(parents=True)
            locked.write_bytes(b"locked")
            candidate.write_bytes(b"candidate")

            summary = service.story_summary("demo")

        self.assertEqual(summary.scene_count, 2)
        self.assertEqual(summary.locked_count, 1)
        self.assertEqual(summary.candidate_count, 1)
        self.assertEqual(summary.recommended_scene_slug, "closing")
        self.assertEqual(summary.recommended_destination, "render-review")
        self.assertEqual([scene.image_state for scene in summary.scenes], ["Locked", "Candidate ready"])



if __name__ == "__main__":
    unittest.main()
