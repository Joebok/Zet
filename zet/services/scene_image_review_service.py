from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import shutil
import tempfile

from zet.models.story import SceneImageReviewStatus
from zet.services.scene_render_target_service import SceneRenderTargetService


class SceneImageReviewError(Exception):
    pass


class SceneImageReviewService:
    """Manage published and candidate images for story scenes."""

    def __init__(self, story_service):
        self.story_service = story_service
        self.path_service = story_service.path_service
        self.target_service = getattr(
            story_service,
            "scene_render_target_service",
            SceneRenderTargetService(story_service, SceneImageReviewError),
        )

    def _slugs(self, story_slug: str, scene_slug: str) -> tuple[str, str]:
        return self.story_service.safe_slug(story_slug), self.story_service.safe_slug(scene_slug)

    @staticmethod
    def review_key(story_slug: str, scene_slug: str, render_target_id: str = "main") -> str:
        suffix = "" if render_target_id == "main" else f":{render_target_id}"
        return f"scene:{story_slug}:{scene_slug}{suffix}"

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

    def status(self, story_slug: str, scene_slug: str, render_target_id: str = "main") -> SceneImageReviewStatus:
        safe_story, safe_scene = self._slugs(story_slug, scene_slug)
        target_id = str(render_target_id or "main").strip()
        target_service = self.target_service
        paths = target_service.review_paths(safe_story, safe_scene, target_id)
        locked_path, candidate_path, comment_path = paths["locked"], paths["candidate"], paths["comment"]
        title = safe_scene
        scene = next(
            (item for item in self.story_service.list_scenes(safe_story) if item.slug == safe_scene),
            None,
        )
        if scene is not None:
            title = scene.title
        document = self.story_service.load_scene_builder_data(safe_story, safe_scene) if target_id != "main" else None
        target_label = target_service.target_label(document.data, target_id) if document else "Full Scene"
        freshness = {"locked_current": locked_path.is_file(), "stale_reason": ""}
        if target_id != "main":
            if target_service.definition(document.data, target_id) is None:
                raise SceneImageReviewError(f"Scene subscene not found: {target_id}")
            try:
                current_hash = self.story_service.story_render_service._compile(safe_story, safe_scene, target_id)[-1]
                freshness = target_service.freshness(safe_story, safe_scene, target_id, current_hash)
            except Exception as exc:
                freshness = {"locked_current": False, "stale_reason": f"Unable to validate locked image: {exc}"}
        return SceneImageReviewStatus(
            story_slug=safe_story,
            scene_slug=safe_scene,
            title=title,
            review_kind="scene",
            review_key=self.review_key(safe_story, safe_scene, target_id),
            locked_image_path=str(locked_path),
            candidate_image_path=str(candidate_path),
            locked_exists=locked_path.is_file(),
            candidate_exists=candidate_path.is_file(),
            comment=comment_path.read_text(encoding="utf-8").strip() if comment_path.is_file() else "",
            render_target_id=target_id,
            render_target_label=target_label,
            locked_current=bool(freshness.get("locked_current")),
            stale_reason=str(freshness.get("stale_reason") or ""),
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
                document = self.story_service.load_scene_builder_data(story.slug, scene.slug)
                for definition in document.data.get("subscenes") or []:
                    target_id = str(definition.get("id") or "")
                    if not target_id:
                        continue
                    target_status = self.status(story.slug, scene.slug, target_id)
                    if target_status.candidate_exists:
                        rows.append(target_status)
        return rows

    def save_comment(self, story_slug: str, scene_slug: str, comment: str, render_target_id: str = "main") -> str:
        status = self.status(story_slug, scene_slug, render_target_id)
        if not status.candidate_exists:
            raise SceneImageReviewError("Scene has no candidate image to review.")
        path = self.target_service.review_paths(status.story_slug, status.scene_slug, status.render_target_id)["comment"]
        clean = str(comment or "").strip()
        if clean:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(clean + "\n", encoding="utf-8")
        else:
            path.unlink(missing_ok=True)
        return clean

    def apply_answer(self, answer_path: Path, response_path: Path, ask_manifest: dict) -> tuple[str, Path]:
        safe_story, safe_scene = self._slugs(ask_manifest.get("story_slug"), ask_manifest.get("scene_slug"))
        target_id = str(ask_manifest.get("render_target_id") or "main").strip()
        paths = self.target_service.review_paths(safe_story, safe_scene, target_id)
        answer_manifest_path = answer_path / "answer_manifest.json"
        try:
            answer_manifest = json.loads(answer_manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SceneImageReviewError(f"Invalid scene answer manifest: {answer_manifest_path}") from exc

        disposition = str(answer_manifest.get("scene_image_disposition") or "").strip().lower()
        if disposition not in {"locked", "candidate"}:
            locked = paths["locked"]
            candidate = paths["candidate"]
            disposition = "locked" if not locked.is_file() and not candidate.is_file() else "candidate"
            answer_manifest["scene_image_disposition"] = disposition
            answer_manifest["scene_image_review_key"] = self.review_key(safe_story, safe_scene, target_id)
            self._write_json(answer_manifest_path, answer_manifest)

        target = (
            paths["locked"]
            if disposition == "locked"
            else paths["candidate"]
        )
        if not bool(answer_manifest.get("scene_image_applied")):
            self._atomic_copy(response_path, target)
            comment = str(answer_manifest.get("render_comment") or "").strip()
            comment_path = paths["comment"]
            if disposition == "candidate":
                if comment:
                    comment_path.parent.mkdir(parents=True, exist_ok=True)
                    comment_path.write_text(comment + "\n", encoding="utf-8")
                else:
                    comment_path.unlink(missing_ok=True)
            else:
                comment_path.unlink(missing_ok=True)
            metadata_path = paths["metadata"] if disposition == "locked" else paths["candidate"].with_suffix(".render.json")
            self._write_json(metadata_path, {
                "story_slug": safe_story,
                "scene_slug": safe_scene,
                "render_target_id": target_id,
                "render_input_hash": str(ask_manifest.get("render_input_hash") or ""),
                "locked_at": datetime.now().isoformat(timespec="seconds") if disposition == "locked" else "",
            })
            answer_manifest["scene_image_applied"] = True
            self._write_json(answer_manifest_path, answer_manifest)
        return disposition, target

    def promote(self, story_slug: str, scene_slug: str, render_target_id: str = "main") -> SceneImageReviewStatus:
        safe_story, safe_scene = self._slugs(story_slug, scene_slug)
        target_id = str(render_target_id or "main").strip()
        paths = self.target_service.review_paths(safe_story, safe_scene, target_id)
        candidate, locked = paths["candidate"], paths["locked"]
        if not candidate.is_file():
            raise SceneImageReviewError("Scene has no candidate image to promote.")
        if locked.is_file():
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup = paths["backups"] / f"{safe_scene}_{target_id}_{stamp}.png"
            self._atomic_copy(locked, backup)
        self._atomic_copy(candidate, locked)
        candidate.unlink()
        candidate_metadata = candidate.with_suffix(".render.json")
        if candidate_metadata.is_file():
            metadata = json.loads(candidate_metadata.read_text(encoding="utf-8"))
            metadata["locked_at"] = datetime.now().isoformat(timespec="seconds")
            self._write_json(paths["metadata"], metadata)
            candidate_metadata.unlink()
        paths["comment"].unlink(missing_ok=True)
        try:
            candidate.parent.rmdir()
        except OSError:
            pass
        return self.status(safe_story, safe_scene, target_id)

    def discard(self, story_slug: str, scene_slug: str, render_target_id: str = "main") -> SceneImageReviewStatus:
        safe_story, safe_scene = self._slugs(story_slug, scene_slug)
        target_id = str(render_target_id or "main").strip()
        paths = self.target_service.review_paths(safe_story, safe_scene, target_id)
        candidate = paths["candidate"]
        if not candidate.is_file():
            raise SceneImageReviewError("Scene has no candidate image to discard.")
        candidate.unlink()
        candidate.with_suffix(".render.json").unlink(missing_ok=True)
        paths["comment"].unlink(missing_ok=True)
        try:
            candidate.parent.rmdir()
        except OSError:
            pass
        return self.status(safe_story, safe_scene, target_id)
