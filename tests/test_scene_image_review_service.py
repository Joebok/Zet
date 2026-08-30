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

    def test_subscene_answers_use_independent_paths_and_provenance(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = SceneImageReviewService(_StoryService(root))
            answer, response, manifest = self._answer(root, "background-answer", b"background")
            manifest.update({"render_target_id": "background", "render_input_hash": "hash-1"})

            disposition, target = service.apply_answer(answer, response, manifest)

            self.assertEqual("locked", disposition)
            self.assertEqual(
                service.path_service.scene_subscene_locked_path("story", "scene", "background"),
                target,
            )
            metadata = json.loads(
                service.path_service.scene_subscene_locked_metadata_path("story", "scene", "background").read_text(encoding="utf-8")
            )
            self.assertEqual("hash-1", metadata["render_input_hash"])
            self.assertFalse(service.path_service.scene_locked_image_path("story", "scene").exists())

    def test_relock_current_refreshes_subscene_provenance_without_replacing_image(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            story_service = _StoryService(root)
            story_service.load_scene_builder_data = lambda story, scene: SimpleNamespace(
                data={"subscenes": [{"id": "background", "name": "Background"}]}
            )
            story_service.story_render_service = SimpleNamespace(
                _compile=lambda story, scene, target, allow_stale_dependencies=False: (None, None, None, None, None, None, None, "hash-2")
            )
            service = SceneImageReviewService(story_service)
            paths = service.target_service.review_paths("story", "scene", "background")
            paths["locked"].parent.mkdir(parents=True)
            paths["locked"].write_bytes(b"current image")
            paths["metadata"].write_text(json.dumps({"render_input_hash": "hash-1"}), encoding="utf-8")

            updated = service.relock_current("story", "scene", "background")

            self.assertTrue(updated.locked_current)
            self.assertEqual(b"current image", paths["locked"].read_bytes())
            metadata = json.loads(paths["metadata"].read_text(encoding="utf-8"))
            self.assertEqual("hash-2", metadata["render_input_hash"])


if __name__ == "__main__":
    unittest.main()
