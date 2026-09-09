from __future__ import annotations

from datetime import datetime
from functools import wraps
import hashlib
import json
from pathlib import Path

from zet.models.story import SceneImageReviewStatus
from zet.services.scene_render_target_service import SceneRenderTargetService
from zet.services.workflow_storage import atomic_copy, file_lock
from zet.services.atomic_file_service import write_json_atomic


def serialized_review(method):
    @wraps(method)
    def run(self, story_slug, scene_slug, *args, **kwargs):
        # Serialize all targets in a scene, including review comments and re-locks.
        path = self.path_service.story_pipeline_path(*self._slugs(story_slug, scene_slug))
        with file_lock(path / "Scene_Review.lock"):
            return method(self, story_slug, scene_slug, *args, **kwargs)
    return run


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

    _atomic_copy = staticmethod(atomic_copy)
    _write_json = staticmethod(write_json_atomic)

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
        if locked_path.is_file():
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

    @serialized_review
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
        with file_lock(self.path_service.story_pipeline_path(safe_story, safe_scene) / "Scene_Review.lock"):
            return self._apply_answer(answer_path, response_path, ask_manifest)

    def _apply_answer(self, answer_path: Path, response_path: Path, ask_manifest: dict) -> tuple[str, Path]:
        safe_story, safe_scene = self._slugs(ask_manifest.get("story_slug"), ask_manifest.get("scene_slug"))
        target_id = str(ask_manifest.get("render_target_id") or "main").strip()
        paths = self.target_service.review_paths(safe_story, safe_scene, target_id)
        answer_manifest_path = answer_path / "answer_manifest.json"
        try:
            answer_manifest = json.loads(answer_manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SceneImageReviewError(f"Invalid scene answer manifest: {answer_manifest_path}") from exc

        # Every response has an immutable recovery copy, independent of the current candidate.
        attempt = str(ask_manifest.get("ask_id") or answer_path.name)
        attempt_key = hashlib.sha256(attempt.encode("utf-8")).hexdigest()
        pipeline = self.target_service.pipeline_path(safe_story, safe_scene, target_id)
        history = pipeline / "Render_Attempts" / attempt_key
        archived_image = history / response_path.name
        if not archived_image.is_file():
            atomic_copy(response_path, archived_image)
        write_json_atomic(history / "ask_manifest.json", ask_manifest)
        active_path = pipeline / "Active_Render.json"
        active = json.loads(active_path.read_text(encoding="utf-8")) if active_path.is_file() else {}
        if active and active.get("ask_id") != attempt:
            answer_manifest.update(scene_image_applied=True, scene_image_disposition="stale")
            self._write_json(answer_manifest_path, answer_manifest)
            return "stale", archived_image
        if answer_manifest.get("scene_image_applied"):
            return str(answer_manifest.get("scene_image_disposition") or "candidate"), archived_image

        disposition = "candidate"
        # Preserve the previous candidate and provenance before installing another.
        if paths["candidate"].is_file():
            previous = hashlib.sha256(paths["candidate"].read_bytes()).hexdigest()
            atomic_copy(paths["candidate"], pipeline / "Render_Attempts" / previous / "candidate.png")
            old_metadata = paths["candidate"].with_suffix(".render.json")
            if old_metadata.is_file():
                atomic_copy(old_metadata, pipeline / "Render_Attempts" / previous / "candidate.render.json")
        answer_manifest["scene_image_disposition"] = disposition
        answer_manifest["scene_image_review_key"] = self.review_key(safe_story, safe_scene, target_id)

        target = paths["candidate"]
        self._atomic_copy(response_path, target)
        comment = str(answer_manifest.get("render_comment") or "").strip()
        comment_path = paths["comment"]
        if comment:
            comment_path.parent.mkdir(parents=True, exist_ok=True)
            comment_path.write_text(comment + "\n", encoding="utf-8")
        else:
            comment_path.unlink(missing_ok=True)
        self._write_json(target.with_suffix(".render.json"), {
            "ask_id": attempt,
            "image_sha256": hashlib.sha256(response_path.read_bytes()).hexdigest(),
            "render_bundle_hash": str(ask_manifest.get("render_bundle_hash") or ""),
            "story_slug": safe_story,
            "scene_slug": safe_scene,
            "render_target_id": target_id,
            "render_input_hash": str(ask_manifest.get("render_input_hash") or ""),
            "locked_at": "",
        })
        answer_manifest["scene_image_applied"] = True
        self._write_json(answer_manifest_path, answer_manifest)
        return disposition, target

    @serialized_review
    def promote(self, story_slug: str, scene_slug: str, render_target_id: str = "main") -> SceneImageReviewStatus:
        safe_story, safe_scene = self._slugs(story_slug, scene_slug)
        target_id = str(render_target_id or "main").strip()
        paths = self.target_service.review_paths(safe_story, safe_scene, target_id)
        candidate, locked = paths["candidate"], paths["locked"]
        journal_path = self.target_service.pipeline_path(safe_story, safe_scene, target_id) / "Promotion.json"
        journal = json.loads(journal_path.read_text(encoding="utf-8")) if journal_path.is_file() else {}
        if not candidate.is_file():
            if journal.get("status") == "COMMITTED" and locked.is_file() and journal.get("image_sha256") == hashlib.sha256(locked.read_bytes()).hexdigest():
                return self.status(safe_story, safe_scene, target_id)
            raise SceneImageReviewError("Scene has no candidate image to promote.")
        candidate_metadata = candidate.with_suffix(".render.json")
        # Parse provenance before touching either image. A malformed sidecar is recoverable.
        try:
            metadata = json.loads(candidate_metadata.read_text(encoding="utf-8"))
            if not isinstance(metadata, dict):
                raise ValueError("Expected an object")
        except (OSError, ValueError) as exc:
            raise SceneImageReviewError("Candidate provenance is missing or invalid; candidate was preserved.") from exc
        renderer = getattr(self.story_service, "story_render_service", None)
        if renderer is not None:
            current_hash = renderer._compile(safe_story, safe_scene, target_id)[-1]
            if metadata.get("render_input_hash") != current_hash:
                raise SceneImageReviewError("Candidate is out of date. Render the current scene before promoting.")
        digest = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if metadata.get("image_sha256") and metadata["image_sha256"] != digest:
            raise SceneImageReviewError("Candidate image and provenance do not match. Retry harvesting its answer before promotion.")
        if locked.is_file() and journal.get("image_sha256") != digest:
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup = paths["backups"] / f"{safe_scene}_{target_id}_{stamp}.png"
            self._atomic_copy(locked, backup)
            if paths["metadata"].is_file():
                self._atomic_copy(paths["metadata"], backup.with_suffix(".render.json"))
        self._write_json(journal_path, {"status": "PREPARED", "image_sha256": digest})
        self._atomic_copy(candidate, locked)
        metadata["locked_at"] = datetime.now().isoformat(timespec="seconds")
        self._write_json(paths["metadata"], metadata)
        self._write_json(journal_path, {"status": "COMMITTED", "image_sha256": digest})
        candidate.unlink()
        candidate_metadata.unlink()
        paths["comment"].unlink(missing_ok=True)
        try:
            candidate.parent.rmdir()
        except OSError:
            pass
        return self.status(safe_story, safe_scene, target_id)

    @serialized_review
    def relock_current(self, story_slug: str, scene_slug: str, render_target_id: str = "main") -> SceneImageReviewStatus:
        safe_story, safe_scene = self._slugs(story_slug, scene_slug)
        target_id = str(render_target_id or "main").strip()
        if target_id == "main":
            raise SceneImageReviewError("Only scene sub-scenes can be re-locked.")
        paths = self.target_service.review_paths(safe_story, safe_scene, target_id)
        if not paths["locked"].is_file():
            raise SceneImageReviewError("Scene subscene has no locked image to re-lock.")
        current_hash = self.story_service.story_render_service._compile(
            safe_story, safe_scene, target_id, allow_stale_dependencies=True
        )[-1]
        metadata = {}
        if paths["metadata"].is_file():
            try:
                loaded_metadata = json.loads(paths["metadata"].read_text(encoding="utf-8"))
                metadata = loaded_metadata if isinstance(loaded_metadata, dict) else {}
            except (OSError, json.JSONDecodeError):
                metadata = {}
        metadata.update({
            "story_slug": safe_story,
            "scene_slug": safe_scene,
            "render_target_id": target_id,
            "render_input_hash": current_hash,
            "locked_at": datetime.now().isoformat(timespec="seconds"),
        })
        self._write_json(paths["metadata"], metadata)
        return self.status(safe_story, safe_scene, target_id)

    @serialized_review
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
