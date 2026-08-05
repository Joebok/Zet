from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import tempfile

from zet.models.story import SceneImageReviewStatus


class SceneImageReviewError(Exception):
    pass


class SceneImageReviewService:
    """Manage published and candidate images for story scenes."""

    def __init__(self, story_service):
        self.story_service = story_service
        self.path_service = story_service.path_service

    def _slugs(self, story_slug: str, scene_slug: str) -> tuple[str, str]:
        return self.story_service.safe_slug(story_slug), self.story_service.safe_slug(scene_slug)

    @staticmethod
    def review_key(story_slug: str, scene_slug: str) -> str:
        return f"scene:{story_slug}:{scene_slug}"

    @staticmethod
    def _atomic_copy(source: Path, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
        os.close(descriptor)
        temporary_path = Path(temporary_name)
        try:
            shutil.copy2(source, temporary_path)
            temporary_path.replace(target)
        finally:
            temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _write_json(path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        os.close(descriptor)
        temporary_path = Path(temporary_name)
        try:
            temporary_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            temporary_path.replace(path)
        finally:
            temporary_path.unlink(missing_ok=True)

    def status(self, story_slug: str, scene_slug: str) -> SceneImageReviewStatus:
        safe_story, safe_scene = self._slugs(story_slug, scene_slug)
        locked_path = self.path_service.scene_locked_image_path(safe_story, safe_scene)
        candidate_path = self.path_service.scene_candidate_image_path(safe_story, safe_scene)
        comment_path = self.path_service.scene_render_review_comment_path(safe_story, safe_scene)
        title = safe_scene
        scene = next(
            (item for item in self.story_service.list_scenes(safe_story) if item.slug == safe_scene),
            None,
        )
        if scene is not None:
            title = scene.title
        return SceneImageReviewStatus(
            story_slug=safe_story,
            scene_slug=safe_scene,
            title=title,
            review_kind="scene",
            review_key=self.review_key(safe_story, safe_scene),
            locked_image_path=str(locked_path),
            candidate_image_path=str(candidate_path),
            locked_exists=locked_path.is_file(),
            candidate_exists=candidate_path.is_file(),
            comment=comment_path.read_text(encoding="utf-8").strip() if comment_path.is_file() else "",
        )

    def list_pending(self, story_slug: str = "", scene_slug: str = "") -> list[SceneImageReviewStatus]:
        safe_story = self.story_service.safe_slug(story_slug) if story_slug else ""
        safe_scene = self.story_service.safe_slug(scene_slug) if scene_slug else ""
        rows: list[SceneImageReviewStatus] = []
        for story in self.story_service.list_stories():
            if safe_story and story.slug != safe_story:
                continue
            for scene in self.story_service.list_scenes(story.slug):
                if safe_scene and scene.slug != safe_scene:
                    continue
                status = self.status(story.slug, scene.slug)
                if status.candidate_exists:
                    rows.append(status)
        return rows

    def save_comment(self, story_slug: str, scene_slug: str, comment: str) -> str:
        status = self.status(story_slug, scene_slug)
        if not status.candidate_exists:
            raise SceneImageReviewError("Scene has no candidate image to review.")
        path = self.path_service.scene_render_review_comment_path(status.story_slug, status.scene_slug)
        clean = str(comment or "").strip()
        if clean:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(clean + "\n", encoding="utf-8")
        else:
            path.unlink(missing_ok=True)
        return clean

    def apply_answer(self, answer_path: Path, response_path: Path, ask_manifest: dict) -> tuple[str, Path]:
        safe_story, safe_scene = self._slugs(ask_manifest.get("story_slug"), ask_manifest.get("scene_slug"))
        answer_manifest_path = answer_path / "answer_manifest.json"
        try:
            answer_manifest = json.loads(answer_manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SceneImageReviewError(f"Invalid scene answer manifest: {answer_manifest_path}") from exc

        disposition = str(answer_manifest.get("scene_image_disposition") or "").strip().lower()
        if disposition not in {"locked", "candidate"}:
            locked = self.path_service.scene_locked_image_path(safe_story, safe_scene)
            candidate = self.path_service.scene_candidate_image_path(safe_story, safe_scene)
            disposition = "locked" if not locked.is_file() and not candidate.is_file() else "candidate"
            answer_manifest["scene_image_disposition"] = disposition
            answer_manifest["scene_image_review_key"] = self.review_key(safe_story, safe_scene)
            self._write_json(answer_manifest_path, answer_manifest)

        target = (
            self.path_service.scene_locked_image_path(safe_story, safe_scene)
            if disposition == "locked"
            else self.path_service.scene_candidate_image_path(safe_story, safe_scene)
        )
        if not bool(answer_manifest.get("scene_image_applied")):
            self._atomic_copy(response_path, target)
            comment = str(answer_manifest.get("render_comment") or "").strip()
            comment_path = self.path_service.scene_render_review_comment_path(safe_story, safe_scene)
            if disposition == "candidate":
                if comment:
                    comment_path.parent.mkdir(parents=True, exist_ok=True)
                    comment_path.write_text(comment + "\n", encoding="utf-8")
                else:
                    comment_path.unlink(missing_ok=True)
            else:
                comment_path.unlink(missing_ok=True)
            answer_manifest["scene_image_applied"] = True
            self._write_json(answer_manifest_path, answer_manifest)
        return disposition, target

    def promote(self, story_slug: str, scene_slug: str) -> SceneImageReviewStatus:
        safe_story, safe_scene = self._slugs(story_slug, scene_slug)
        candidate = self.path_service.scene_candidate_image_path(safe_story, safe_scene)
        locked = self.path_service.scene_locked_image_path(safe_story, safe_scene)
        if not candidate.is_file():
            raise SceneImageReviewError("Scene has no candidate image to promote.")
        if locked.is_file():
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup = self.path_service.scene_locked_backups_path(safe_story, safe_scene) / f"{safe_scene}_{stamp}.png"
            self._atomic_copy(locked, backup)
        self._atomic_copy(candidate, locked)
        candidate.unlink()
        self.path_service.scene_render_review_comment_path(safe_story, safe_scene).unlink(missing_ok=True)
        try:
            candidate.parent.rmdir()
        except OSError:
            pass
        return self.status(safe_story, safe_scene)

    def discard(self, story_slug: str, scene_slug: str) -> SceneImageReviewStatus:
        safe_story, safe_scene = self._slugs(story_slug, scene_slug)
        candidate = self.path_service.scene_candidate_image_path(safe_story, safe_scene)
        if not candidate.is_file():
            raise SceneImageReviewError("Scene has no candidate image to discard.")
        candidate.unlink()
        self.path_service.scene_render_review_comment_path(safe_story, safe_scene).unlink(missing_ok=True)
        try:
            candidate.parent.rmdir()
        except OSError:
            pass
        return self.status(safe_story, safe_scene)
