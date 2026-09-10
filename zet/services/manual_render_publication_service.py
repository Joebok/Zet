"""Durable publication and recovery for manual render queue bundles."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

from zet.services.ai_proxy_path_service import AIProxyPathService
from zet.services.atomic_file_service import replace_with_retry, write_json_atomic
from zet.services.config_service import Config
from zet.services.workflow_storage import file_lock, subject_key, supersede_task, task_state_path


class ManualRenderPublicationError(RuntimeError):
    """A manual render bundle cannot be safely published or recovered."""


class ManualRenderPublicationConflict(ManualRenderPublicationError):
    """Publication would overwrite a different task or newer active render."""


DependencyValidator = Callable[[dict[str, Any]], bool | str]


class ManualRenderPublicationService:
    """Publish complete manual-render asks with a durable recovery journal.

    The journal lives beside the queue rather than inside a bundle, so a crash
    before the staging-directory rename still leaves enough information for a
    later, explicit recovery attempt.
    """

    JOURNAL_SCHEMA_VERSION = 1
    JOURNAL_KIND = "Manual_Render_Publications"

    def __init__(self, config: Config):
        self.config = config
        self.path_service = AIProxyPathService(config)

    @property
    def queue_root(self) -> Path:
        return Path(self.config.base_ai_queue_path)

    @property
    def journal_root(self) -> Path:
        return self.queue_root / "Zet_File_Proxy_State" / self.JOURNAL_KIND

    def intent_path(self, ask_id: str) -> Path:
        return task_state_path(self.queue_root, self.JOURNAL_KIND, str(ask_id))

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _inside(path: Path, root: Path) -> bool:
        try:
            path.resolve().relative_to(root.resolve())
            return True
        except ValueError:
            return False

    def _relative_member(self, value: str, bundle_root: Path, ready_path: Path) -> Path:
        raw = Path(str(value or ""))
        if raw.is_absolute():
            try:
                return raw.resolve().relative_to(ready_path.resolve())
            except ValueError:
                # Older snapshots sometimes stored a path rooted at the
                # staging directory. Accept it only when it is still local.
                try:
                    return raw.resolve().relative_to(bundle_root.resolve())
                except ValueError as exc:
                    raise ManualRenderPublicationError(
                        f"Bundle member is outside the publication root: {value}"
                    ) from exc
        return raw

    def _member_path(self, value: str, bundle_root: Path, ready_path: Path) -> Path:
        relative = self._relative_member(value, bundle_root, ready_path)
        if not relative.parts or relative.is_absolute() or ".." in relative.parts:
            raise ManualRenderPublicationError(f"Invalid bundle member path: {value}")
        path = bundle_root / relative
        if not self._inside(path, bundle_root):
            raise ManualRenderPublicationError(f"Invalid bundle member path: {value}")
        return path

    def _bundle_inventory(self, bundle_root: Path) -> list[dict[str, Any]]:
        return [
            {"path": str(path.relative_to(bundle_root)), "sha256": self._sha256(path)}
            for path in sorted(bundle_root.rglob("*"))
            if path.is_file()
        ]

    def _validate_bundle(
        self,
        bundle_root: Path,
        ready_path: Path,
        *,
        expected_bundle_hash: str = "",
        expected_inventory: list[dict[str, Any]] | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        if not bundle_root.is_dir():
            raise ManualRenderPublicationError(f"Manual render staging bundle is missing: {bundle_root}")
        manifest_path = bundle_root / "ask_manifest.json"
        manifest = self._read_json(manifest_path)
        if not manifest:
            raise ManualRenderPublicationError(f"Manual render ask manifest is invalid: {manifest_path}")
        ask_id = str(manifest.get("ask_id") or "")
        if not ask_id or ask_id != ready_path.name:
            raise ManualRenderPublicationError("Manual render bundle identity does not match its destination.")
        if str(manifest.get("worker_type") or "") != "manual_chatgpt_render":
            raise ManualRenderPublicationError("Publication requires a manual ChatGPT render bundle.")

        prompt_file = str(manifest.get("prompt_file") or "")
        prompt_path = self._member_path(prompt_file, bundle_root, ready_path)
        if not prompt_path.is_file():
            raise ManualRenderPublicationError(f"Manual render prompt is missing: {prompt_file}")
        prompt_hash = self._sha256(prompt_path)
        if str(manifest.get("prompt_sha256") or "") != prompt_hash:
            raise ManualRenderPublicationError("Manual render prompt hash does not match the bundle.")
        for required_file in manifest.get("publication_files") or []:
            required_path = self._member_path(str(required_file), bundle_root, ready_path)
            if not required_path.is_file():
                raise ManualRenderPublicationError(f"Manual render bundle member is missing: {required_file}")

        reference_hashes: list[str] = []
        for reference in manifest.get("reference_files") or []:
            if not isinstance(reference, dict):
                raise ManualRenderPublicationError("Manual render reference metadata is invalid.")
            reference_path = self._member_path(str(reference.get("path") or ""), bundle_root, ready_path)
            if not reference_path.is_file():
                raise ManualRenderPublicationError(f"Manual render reference is missing: {reference_path.name}")
            digest = self._sha256(reference_path)
            if str(reference.get("sha256") or "") != digest:
                raise ManualRenderPublicationError(f"Manual render reference hash does not match: {reference_path.name}")
            reference_hashes.append(digest)

        calculated_bundle_hash = hashlib.sha256(json.dumps({
            "prompt": prompt_hash,
            "inputs": [
                {key: value for key, value in item.items() if key != "path"}
                for item in manifest.get("image_inputs") or []
                if isinstance(item, dict)
            ],
            "images": reference_hashes,
        }, sort_keys=True).encode()).hexdigest()
        bundle_hash = str(manifest.get("render_bundle_hash") or "")
        if not bundle_hash or bundle_hash != calculated_bundle_hash:
            raise ManualRenderPublicationError("Manual render bundle hash does not match its contents.")
        if expected_bundle_hash and expected_bundle_hash != bundle_hash:
            raise ManualRenderPublicationError("Manual render bundle hash changed after the publication intent was recorded.")

        inventory = self._bundle_inventory(bundle_root)
        if expected_inventory is not None and inventory != expected_inventory:
            raise ManualRenderPublicationError("Manual render bundle contents changed after the publication intent was recorded.")
        return manifest, inventory

    def _read_intent(self, ask_id: str) -> dict[str, Any]:
        intent = self._read_json(self.intent_path(ask_id))
        if intent and intent.get("schema_version") != self.JOURNAL_SCHEMA_VERSION:
            raise ManualRenderPublicationError(f"Unsupported manual render publication journal: {ask_id}")
        return intent

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")

    def _active_conflict(self, active_path: Path | None, ask_id: str, previous_active: dict[str, Any] | None) -> None:
        if active_path is None or not active_path.is_file():
            return
        active = self._read_json(active_path)
        current_id = str(active.get("ask_id") or "")
        previous_id = str((previous_active or {}).get("ask_id") or "")
        if current_id and current_id not in {ask_id, previous_id}:
            raise ManualRenderPublicationConflict(
                f"Active render {current_id} is newer than the publication for {ask_id}; recover it first."
            )

    def _supersede_previous(self, ask_id: str, target: tuple, reason: str) -> None:
        for root in (self.path_service.manual_ask_root(), self.path_service.manual_answer_root()):
            if not root.is_dir():
                continue
            for item in sorted(root.iterdir()):
                if not item.is_dir() or item.name.startswith(".") or item.name == ask_id:
                    continue
                manifest = self._read_json(item / "ask_manifest.json")
                if manifest.get("auxiliary") or subject_key(manifest) != target:
                    continue
                supersede_task(self.queue_root, item, reason)

    def publish(
        self,
        staging_path: Path,
        ready_path: Path,
        *,
        active_render_path: Path | None = None,
        active_render: dict[str, Any] | None = None,
        publication_subject: tuple | None = None,
        supersede_reason: str = "A newer render attempt was staged.",
        dependency_validator: DependencyValidator | None = None,
    ) -> Path:
        """Publish a complete staging bundle, or leave it journaled for recovery."""
        staging_path = Path(staging_path)
        ready_path = Path(ready_path)
        if not self._inside(staging_path, self.path_service.manual_ask_root()) or not self._inside(
            ready_path, self.path_service.manual_ask_root()
        ):
            raise ManualRenderPublicationError("Manual render publication paths must be inside the manual ask queue.")
        ask_id = ready_path.name
        lock_path = task_state_path(self.queue_root, "Locks", ask_id)
        with file_lock(lock_path, timeout=15):
            intent = self._read_intent(ask_id)
            if intent.get("status") == "COMMITTED" and ready_path.is_dir():
                self._validate_bundle(
                    ready_path,
                    ready_path,
                    expected_bundle_hash=str(intent.get("bundle_hash") or ""),
                    expected_inventory=intent.get("bundle_inventory"),
                )
                return ready_path

            previous_active = intent.get("previous_active") if intent else None
            if active_render_path is not None and previous_active is None:
                previous_active = self._read_json(active_render_path) if active_render_path.is_file() else None
            if intent:
                if str(intent.get("ready_path") or "") != str(ready_path):
                    raise ManualRenderPublicationConflict("Publication intent points to a different destination.")
                if active_render_path is None and intent.get("active_render_path"):
                    active_render_path = Path(str(intent["active_render_path"]))
                if active_render is None and isinstance(intent.get("active_render"), dict):
                    active_render = dict(intent["active_render"])
                if publication_subject is None and isinstance(intent.get("publication_subject"), list):
                    publication_subject = tuple(intent["publication_subject"])
                if not supersede_reason and intent.get("supersede_reason"):
                    supersede_reason = str(intent["supersede_reason"])

            source_path = Path(str(intent.get("staging_path") or staging_path)) if intent else staging_path
            if ready_path.is_dir():
                try:
                    manifest, inventory = self._validate_bundle(
                        ready_path,
                        ready_path,
                        expected_bundle_hash=str(intent.get("bundle_hash") or "") if intent else "",
                        expected_inventory=intent.get("bundle_inventory") if intent else None,
                    )
                except ManualRenderPublicationError as exc:
                    raise ManualRenderPublicationConflict(
                        f"Ready destination already contains a different manual render task: {ready_path}"
                    ) from exc
            else:
                manifest, inventory = self._validate_bundle(
                    source_path,
                    ready_path,
                    expected_bundle_hash=str(intent.get("bundle_hash") or "") if intent else "",
                    expected_inventory=intent.get("bundle_inventory") if intent else None,
                )
            if str(manifest.get("ask_id") or "") != ask_id:
                raise ManualRenderPublicationError("Manual render publication identity changed.")
            if dependency_validator is not None:
                dependency_result = dependency_validator(manifest)
                if dependency_result is False or (
                    isinstance(dependency_result, str)
                    and dependency_result != str(manifest.get("render_input_hash") or "")
                ):
                    raise ManualRenderPublicationError("Manual render dependencies changed; recompile before recovery.")

            if not intent:
                intent = {
                    "schema_version": self.JOURNAL_SCHEMA_VERSION,
                    "ask_id": ask_id,
                    "staging_path": str(source_path),
                    "ready_path": str(ready_path),
                    "active_render_path": str(active_render_path) if active_render_path else "",
                    "active_render": active_render or {},
                    "previous_active": previous_active or {},
                    "publication_subject": list(publication_subject) if publication_subject is not None else list(subject_key(manifest)),
                    "supersede_reason": supersede_reason,
                    "bundle_hash": str(manifest["render_bundle_hash"]),
                    "bundle_inventory": inventory,
                    "created_at": self._now(),
                    "status": "PREPARED",
                }
                write_json_atomic(self.intent_path(ask_id), intent)

            if not ready_path.is_dir():
                try:
                    replace_with_retry(source_path, ready_path, timeout_seconds=15.0)
                except Exception:
                    # The complete source remains available and the journal is
                    # the durable recovery signal after an exhausted retry.
                    raise
                intent["status"] = "BUNDLE_PUBLISHED"
                write_json_atomic(self.intent_path(ask_id), intent)

            self._active_conflict(active_render_path, ask_id, previous_active)
            if active_render_path is not None and active_render:
                write_json_atomic(active_render_path, active_render)
                intent["status"] = "ACTIVE_RECORDED"
                write_json_atomic(self.intent_path(ask_id), intent)

            target = tuple(publication_subject or intent.get("publication_subject") or subject_key(manifest))
            self._supersede_previous(ask_id, target, supersede_reason)
            intent["status"] = "COMMITTED"
            write_json_atomic(self.intent_path(ask_id), intent)
            return ready_path

    def _intent_for_staging(self, staging_path: Path) -> dict[str, Any]:
        manifest = self._read_json(staging_path / "ask_manifest.json")
        ask_id = str(manifest.get("ask_id") or "")
        if not ask_id:
            return {}
        return {
            "ask_id": ask_id,
            "staging_path": str(staging_path),
            "ready_path": str(self.path_service.manual_ask_path(ask_id)),
            "active_render_path": "",
            "active_render": {},
            "previous_active": {},
            "publication_subject": list(subject_key(manifest)),
            "supersede_reason": "A newer render attempt was staged.",
        }

    def inspect(self, dependency_validator: DependencyValidator | None = None) -> list[dict[str, Any]]:
        """Inspect journals and untracked staging folders without mutating them."""
        records: dict[str, dict[str, Any]] = {}
        if self.journal_root.is_dir():
            for path in sorted(self.journal_root.glob("*.json")):
                intent = self._read_json(path)
                ask_id = str(intent.get("ask_id") or "")
                if ask_id:
                    records[ask_id] = intent
        if self.path_service.manual_ask_root().is_dir():
            for staging in sorted(self.path_service.manual_ask_root().glob(".*.staging")):
                intent = self._intent_for_staging(staging)
                ask_id = str(intent.get("ask_id") or staging.name[1:-len(".staging")])
                records.setdefault(ask_id, intent or {"ask_id": ask_id, "staging_path": str(staging)})

        result: list[dict[str, Any]] = []
        for ask_id, intent in sorted(records.items()):
            staging = Path(str(intent.get("staging_path") or self.path_service.manual_ask_path(f".{ask_id}.staging")))
            ready = Path(str(intent.get("ready_path") or self.path_service.manual_ask_path(ask_id)))
            if str(intent.get("status") or "") == "COMMITTED" and not staging.is_dir() and not ready.is_dir():
                continue
            errors: list[str] = []
            locations: list[str] = []
            manifest: dict[str, Any] = {}
            if staging.is_dir():
                locations.append("staging")
                try:
                    manifest, _ = self._validate_bundle(
                        staging,
                        ready,
                        expected_bundle_hash=str(intent.get("bundle_hash") or "") if intent.get("bundle_hash") else "",
                        expected_inventory=intent.get("bundle_inventory") if intent.get("bundle_inventory") else None,
                    )
                except ManualRenderPublicationError as exc:
                    errors.append(str(exc))
            if ready.is_dir():
                locations.append("ready")
                try:
                    manifest, _ = self._validate_bundle(
                        ready,
                        ready,
                        expected_bundle_hash=str(intent.get("bundle_hash") or "") if intent.get("bundle_hash") else "",
                        expected_inventory=intent.get("bundle_inventory") if intent.get("bundle_inventory") else None,
                    )
                except ManualRenderPublicationError as exc:
                    errors.append(str(exc))
            if manifest and dependency_validator is not None:
                try:
                    dependency_result = dependency_validator(manifest)
                    if dependency_result is False or (
                        isinstance(dependency_result, str)
                        and dependency_result != str(manifest.get("render_input_hash") or "")
                    ):
                        errors.append("Manual render dependencies changed; recompile before recovery.")
                except Exception as exc:
                    errors.append(f"Unable to validate current dependencies: {exc}")
            status = "ready" if ready.is_dir() and not errors else "recoverable" if staging.is_dir() and not errors else "blocked"
            result.append({
                "ask_id": ask_id,
                "status": status,
                "journal_status": str(intent.get("status") or "UNTRACKED"),
                "recoverable": status == "recoverable" or (status == "ready" and str(intent.get("status")) != "COMMITTED"),
                "staging_path": str(staging) if staging.is_dir() else None,
                "ready_path": str(ready) if ready.is_dir() else str(ready),
                "locations": locations,
                "bundle_hash": str(intent.get("bundle_hash") or manifest.get("render_bundle_hash") or ""),
                "errors": errors,
            })
        return result

    def recover(
        self,
        ask_id: str,
        *,
        dependency_validator: DependencyValidator | None = None,
    ) -> Path:
        """Explicitly recover one journaled or complete untracked staging bundle."""
        ask_id = str(ask_id or "").strip()
        if not ask_id or Path(ask_id).name != ask_id:
            raise ManualRenderPublicationError("A valid manual render ask ID is required for recovery.")
        intent = self._read_intent(ask_id)
        if not intent:
            staging = self.path_service.manual_ask_path(f".{ask_id}.staging")
            intent = self._intent_for_staging(staging)
            if not intent:
                raise ManualRenderPublicationError(f"No publication intent or staging bundle found for {ask_id}.")
            active_path = Path(str(self._read_json(staging / "ask_manifest.json").get("pipeline_path") or "")) / "Active_Render.json"
            if active_path.parent != Path("."):
                current = self._read_json(active_path)
                if current and current.get("ask_id") != ask_id:
                    raise ManualRenderPublicationConflict("A different active render exists; the untracked bundle was preserved.")
                intent["active_render_path"] = str(active_path)
                intent["active_render"] = {
                    "ask_id": ask_id,
                    "attempt_id": str(self._read_json(staging / "ask_manifest.json").get("ollama_attempt_id") or ""),
                    "render_input_hash": str(self._read_json(staging / "ask_manifest.json").get("render_input_hash") or ""),
                    "render_bundle_hash": str(self._read_json(staging / "ask_manifest.json").get("render_bundle_hash") or ""),
                    "ask_path": str(self.path_service.manual_ask_path(ask_id)),
                }
        staging = Path(str(intent.get("staging_path") or self.path_service.manual_ask_path(f".{ask_id}.staging")))
        ready = Path(str(intent.get("ready_path") or self.path_service.manual_ask_path(ask_id)))
        active_path = Path(str(intent["active_render_path"])) if intent.get("active_render_path") else None
        active_render = dict(intent.get("active_render") or {}) or None
        previous_active = intent.get("previous_active") or {}
        self._active_conflict(active_path, ask_id, previous_active)
        return self.publish(
            staging,
            ready,
            active_render_path=active_path,
            active_render=active_render,
            publication_subject=tuple(intent.get("publication_subject") or ()) or None,
            supersede_reason=str(intent.get("supersede_reason") or "A newer render attempt was staged."),
            dependency_validator=dependency_validator,
        )
