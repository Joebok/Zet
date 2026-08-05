import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from zet.services.path_service import PathService
from zet.services.scene_image_review_service import SceneImageReviewService


class _StoryService:
    def __init__(self, root: Path):
        config = SimpleNamespace(
            base_asset_path=str(root / "Assets"),
            base_library_path=str(root / "Library"),
        )
        self.path_service = PathService(config, root)

    @staticmethod
    def safe_slug(value: str) -> str:
        value = str(value or "").strip()
        if not value or any(part in value for part in ("/", "\\", "..")):
            raise ValueError("Invalid slug")
        return value

    def load_scene(self, story_slug: str, scene_slug: str):
        return SimpleNamespace(record=SimpleNamespace(title=f"Title {scene_slug}"))

    def list_stories(self):
        return [SimpleNamespace(slug="story"), SimpleNamespace(slug="other-story")]

    def list_scenes(self, story_slug: str):
        slug = "scene" if story_slug == "story" else "other-scene"
        return [SimpleNamespace(slug=slug, title=f"Title {slug}")]


class SceneImageReviewServiceTests(unittest.TestCase):
    def _answer(self, root: Path, name: str, payload: bytes, comment: str = "") -> tuple[Path, Path, dict]:
        answer = root / name
        answer.mkdir()
        response = answer / "scene.png"
        response.write_bytes(payload)
        (answer / "answer_manifest.json").write_text(
            json.dumps({"render_comment": comment}) + "\n",
            encoding="utf-8",
        )
        manifest = {
            "story_slug": "story",
            "scene_slug": "scene",
            "target_output_file": str(root / "legacy-direct-output.png"),
        }
        return answer, response, manifest

    def test_first_answer_locks_and_later_answers_replace_candidate(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = SceneImageReviewService(_StoryService(root))
            local_render = service.path_service.story_pipeline_path("story", "scene") / "Local_Test_Renders" / "test_1.png"
            local_render.parent.mkdir(parents=True)
            local_render.write_bytes(b"local")

            answer, response, manifest = self._answer(root, "answer-1", b"locked")
            disposition, target = service.apply_answer(answer, response, manifest)
            self.assertEqual(disposition, "locked")
            self.assertEqual(target.read_bytes(), b"locked")
            self.assertFalse(service.status("story", "scene").candidate_exists)

            answer, response, manifest = self._answer(root, "answer-2", b"candidate-1", "compare this")
            disposition, target = service.apply_answer(answer, response, manifest)
            self.assertEqual(disposition, "candidate")
            self.assertEqual(target.read_bytes(), b"candidate-1")
            self.assertEqual(service.status("story", "scene").comment, "compare this")

            answer, response, manifest = self._answer(root, "answer-3", b"candidate-2")
            service.apply_answer(answer, response, manifest)
            self.assertEqual(service.status("story", "scene").comment, "")
            self.assertEqual(target.read_bytes(), b"candidate-2")

    def test_candidate_without_locked_remains_candidate_and_can_be_promoted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = SceneImageReviewService(_StoryService(root))
            candidate = service.path_service.scene_candidate_image_path("story", "scene")
            candidate.parent.mkdir(parents=True)
            candidate.write_bytes(b"existing candidate")
            answer, response, manifest = self._answer(root, "answer", b"replacement")

            disposition, _ = service.apply_answer(answer, response, manifest)
            self.assertEqual(disposition, "candidate")
            self.assertFalse(service.status("story", "scene").locked_exists)
            service.promote("story", "scene")
            status = service.status("story", "scene")
            self.assertTrue(status.locked_exists)
            self.assertFalse(status.candidate_exists)
            self.assertEqual(Path(status.locked_image_path).read_bytes(), b"replacement")

    def test_list_pending_filters_by_story_and_scene(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service = SceneImageReviewService(_StoryService(Path(temp_dir)))
            for story_slug, scene_slug in (("story", "scene"), ("other-story", "other-scene")):
                candidate = service.path_service.scene_candidate_image_path(story_slug, scene_slug)
                candidate.parent.mkdir(parents=True)
                candidate.write_bytes(b"candidate")

            self.assertEqual(len(service.list_pending()), 2)
            filtered = service.list_pending("story", "scene")
            self.assertEqual([(item.story_slug, item.scene_slug) for item in filtered], [("story", "scene")])

    def test_promote_backs_up_locked_and_discard_preserves_it(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = SceneImageReviewService(_StoryService(root))
            locked = service.path_service.scene_locked_image_path("story", "scene")
            candidate = service.path_service.scene_candidate_image_path("story", "scene")
            locked.parent.mkdir(parents=True)
            candidate.parent.mkdir(parents=True)
            locked.write_bytes(b"old")
            candidate.write_bytes(b"new")

            service.promote("story", "scene")
            self.assertEqual(locked.read_bytes(), b"new")
            backups = list(service.path_service.scene_locked_backups_path("story", "scene").glob("*.png"))
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), b"old")

            candidate.parent.mkdir(parents=True)
            candidate.write_bytes(b"discard")
            service.discard("story", "scene")
            self.assertEqual(locked.read_bytes(), b"new")
            self.assertFalse(candidate.exists())

    def test_reapplying_answer_uses_recorded_disposition(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = SceneImageReviewService(_StoryService(root))
            answer, response, manifest = self._answer(root, "answer", b"first")
            service.apply_answer(answer, response, manifest)
            service.path_service.scene_locked_image_path("story", "scene").unlink()
            service.path_service.scene_candidate_image_path("story", "scene").parent.mkdir(parents=True)
            service.path_service.scene_candidate_image_path("story", "scene").write_bytes(b"other")

            disposition, target = service.apply_answer(answer, response, manifest)
            self.assertEqual(disposition, "locked")
            self.assertEqual(target, service.path_service.scene_locked_image_path("story", "scene"))
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
