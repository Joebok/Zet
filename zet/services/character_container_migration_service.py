"""Reviewed, resumable import of current character pipeline Final locks."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
from urllib.parse import quote
from uuid import NAMESPACE_URL, uuid5

from zet.services.atomic_file_service import write_json_atomic
from zet.services.local_asset_store_service import LocalAssetStoreService
from zet.services.view_conditioning_service import VIEW_ORDER
from zet.services.workflow_storage import file_lock


PIPELINES = {
    "body-reference": "Body-Reference",
    "head-image-edit": "Head-Image-Edit",
    "character-assembly": "Character-Assembly",
    "costume-dressing": "Costume-Dressing",
}


class CharacterContainerMigrationError(ValueError):
    pass


class CharacterContainerMigrationService:
    def __init__(self, library_root: str | Path, character_root: str | Path, universe_id: str = ""):
        self.library_root = Path(library_root).resolve()
        self.character_root = Path(character_root).resolve()
        self.universe_id = str(universe_id or self.library_root.name)
        self.asset_store = LocalAssetStoreService(self.library_root)
        self.container_root = self.library_root / "_state" / "CharacterAssetContainers"

    @staticmethod
    def _stamp(record: dict) -> str:
        return str(record.get("locked_at") or record.get("updated_at") or "")

    def _catalog_approved(self, asset_id: str, character: str, phase: str, pipeline: str, costume: str) -> bool:
        if not asset_id:
            return False
        database = self.library_root / "catalog.sqlite3"
        if not database.is_file():
            return False
        from zet.repositories.entity_library_repository import EntityLibraryRepository
        row = EntityLibraryRepository(database).fetchone(
            "SELECT status,origin,origin_key FROM assets WHERE asset_id=?", (asset_id,))
        if not row or row["status"] != "approved" or row["origin"] != "pipeline":
            return False
        parts = str(row.get("origin_key") or "").split(":")
        if (len(parts) < 5 or parts[0].casefold() != "local"
                or parts[1].casefold() != pipeline.casefold()
                or parts[2].casefold() != character.casefold()
                or parts[3].casefold() != phase.casefold()):
            return False
        return pipeline.casefold() != "costume-dressing" or parts[4].casefold() == costume.casefold()

    def _locked_records(self, character: str, phase: str, pipeline: str, costume: str) -> tuple[list[dict], list[dict]]:
        from zet.services.library_reference_service import read_library_json
        state_path = self.asset_store.workspace_path(character, phase)
        if not state_path.is_file():
            return [], []
        try:
            state = read_library_json(state_path, self.library_root)
        except (OSError, ValueError) as exc:
            raise CharacterContainerMigrationError(f"Legacy lock store is unreadable: {state_path}") from exc
        records = state.get("assets", {}) if isinstance(state, dict) else {}
        if not isinstance(records, dict):
            raise CharacterContainerMigrationError(f"Legacy lock store has an invalid format: {state_path}")
        valid, skipped = [], []
        for key, record in records.items():
            if (not record.get("locked") or record.get("render_mode", "draft") != "final"
                    or str(record.get("pipeline") or "").casefold() != pipeline.casefold()
                    or str(record.get("qualifier") or "").casefold() != costume.casefold()
                    or record.get("view") not in VIEW_ORDER):
                continue
            image = Path(str(record.get("locked_image_path") or "")).resolve()
            if not image.is_relative_to(self.library_root) or not image.is_file():
                skipped.append({"key": key, "reason": "locked image bytes unavailable"})
                continue
            asset_id = str(record.get("entity_library_asset_id") or "")
            if not self._catalog_approved(asset_id, character, phase, pipeline, costume):
                skipped.append({"key": key, "inventory_asset_id": asset_id,
                                "reason": "current Inventory publication is unavailable"})
                continue
            observed_hash = hashlib.sha256(image.read_bytes()).hexdigest()
            valid.append({"key": key, **record, "image_path": str(image),
                          "image_sha256": observed_hash,
                          "legacy_recorded_image_sha256": record.get("image_sha256", "")})
        return valid, skipped

    def _scope_entries(self) -> list[dict]:
        entries = []
        if not self.character_root.is_dir():
            return entries
        for character_path in sorted(self.character_root.iterdir(), key=lambda path: path.name):
            if not character_path.is_dir() or character_path.resolve().parent != self.character_root:
                continue
            character = character_path.name
            char_root = character_path
            for phase_path in sorted(char_root.iterdir(), key=lambda path: path.name):
                if not phase_path.is_dir() or phase_path.resolve().parent != char_root.resolve():
                    continue
                phase = phase_path.name
                for pipeline, legacy_name in PIPELINES.items():
                    costumes = [""]
                    if pipeline == "costume-dressing":
                        from zet.services.costume_service import CostumeService
                        costumes = []
                        for path in sorted(phase_path.glob("Costume_*.md")):
                            costumes.append(CostumeService.safe_costume_slug(path.stem.removeprefix("Costume_")))
                    for costume in costumes:
                        entries.append({"character": character, "phase": phase, "pipeline": pipeline,
                                        "legacy_pipeline": legacy_name, "costume": costume})
        return entries

    def _legacy_state_files(self) -> list[Path]:
        root = self.library_root / "_state" / "LocalAssets"
        return sorted(root.rglob("local_assets.json")) if root.is_dir() else []

    def _legacy_work_files(self) -> list[Path]:
        root = self.library_root / "PipelineCandidates" / "Character-Pipeline"
        return sorted(root.rglob("spec.json")) if root.is_dir() else []

    @staticmethod
    def _import_candidate_id(item: dict) -> str:
        scope = item
        return str(uuid5(NAMESPACE_URL,
            f"zet-character-import:{scope['character']}:{scope['phase']}:{scope['pipeline']}:{scope['costume']}:{item['view']}:{item['source_key']}"))

    def _saved_phase_choices(self, scopes: list[dict], decisions: list[dict]) -> list[dict]:
        choices = []
        work_root = self.library_root / "PipelineCandidates" / "Character-Pipeline"
        for scope in scopes:
            if scope["pipeline"] != "head-image-edit":
                continue
            latest: dict[str, tuple[int, dict]] = {}
            for spec_path in self._legacy_work_files():
                try:
                    relative = spec_path.relative_to(work_root)
                    parts = relative.parts
                    if (len(parts) < 5 or parts[0].casefold() != scope["character"].casefold()
                            or parts[1].casefold() != scope["phase"].casefold()
                            or parts[2].casefold() != scope["legacy_pipeline"].casefold()):
                        continue
                    spec = json.loads(spec_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                records = spec.get("front_sources_by_mode") or {}
                for mode in ("draft", "final"):
                    record = records.get(mode)
                    if not record and spec.get("front_source") and (mode == "draft" or spec.get("apply_phase_change")):
                        record = {"path": spec.get("front_source"),
                                  "sha256": spec.get("front_source_sha256"),
                                  "origin": spec.get("front_source_origin") or {}}
                    if not isinstance(record, dict) or not record.get("path"):
                        continue
                    stamp = int(spec_path.stat().st_mtime_ns)
                    previous = latest.get(mode)
                    if previous and previous[0] > stamp:
                        continue
                    latest[mode] = (stamp, {"record": record, "run_id": parts[3],
                        "source_key": relative.as_posix()})
            for mode, (_, saved) in latest.items():
                record = saved["record"]
                origin = record.get("origin") or {}
                source_phase = str(origin.get("phase") or "").strip()
                source_pipeline = str(origin.get("pipeline") or "").strip().lower()
                if source_pipeline != "head-image-edit":
                    source_pipeline = scope["pipeline"]
                source_inventory_id = str(origin.get("asset_id") or "")
                source_key = str(origin.get("source_key") or "")
                upload_path = Path(str(record.get("path") or "")).resolve()
                upload_ok = False
                upload_hash = ""
                if origin.get("kind") == "upload" and upload_path.is_file():
                    try:
                        upload_ok = (upload_path.is_relative_to(self.library_root)
                            and upload_path.is_relative_to((spec_path.parent.resolve())))
                        if upload_ok and upload_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} and upload_path.stat().st_size <= 32 * 1024 * 1024:
                            from PIL import Image
                            with Image.open(upload_path) as image:
                                image.verify()
                            upload_hash = hashlib.sha256(upload_path.read_bytes()).hexdigest()
                        else:
                            upload_ok = False
                    except (OSError, ValueError):
                        upload_ok = False
                source_decision = next((item for item in decisions
                    if item.get("status") == "import" and item.get("character", "").casefold() == scope["character"].casefold()
                    and item.get("phase", "").casefold() == source_phase.casefold()
                    and item.get("pipeline") == source_pipeline and item.get("view") == "FRONT"
                    and ((source_inventory_id and item.get("inventory_asset_id") == source_inventory_id)
                         or (source_key and item.get("source_key") == source_key))), None)
                identity = hashlib.sha256(json.dumps({"target": scope, "mode": mode,
                    "run": saved["run_id"], "origin": origin}, sort_keys=True,
                    separators=(",", ":")).encode()).hexdigest()
                entry = {"character": scope["character"], "phase": scope["phase"],
                    "pipeline": scope["pipeline"], "costume": scope["costume"],
                    "mode": mode, "legacy_source_key": f"{saved['source_key']}:{mode}:{identity[:16]}",
                    "source_phase": source_phase, "source_pipeline": source_pipeline,
                    "source_inventory_asset_id": source_inventory_id,
                    "source_legacy_key": source_key, "source_kind": str(origin.get("kind") or ""),
                    "status": "import" if source_decision or upload_ok else "unavailable"}
                if upload_ok:
                    entry["upload_source_path"] = str(upload_path)
                    entry["upload_source_sha256"] = upload_hash
                    entry["upload_filename"] = upload_path.name
                elif source_decision:
                    entry["candidate_id"] = self._import_candidate_id(source_decision)
                else:
                    entry["reason"] = ("managed upload is unavailable or invalid" if origin.get("kind") == "upload"
                        else "source is not an imported current locked Final FRONT"
                        if origin.get("kind") == "locked_phase" else "source is not a recoverable locked-phase reference")
                choices.append(entry)
        return choices

    def _fingerprint(self, decisions: list[dict], source_choices: list[dict]) -> str:
        digest = hashlib.sha256()
        for path in self._legacy_state_files():
            digest.update(path.relative_to(self.library_root).as_posix().encode())
            digest.update(path.read_bytes())
        active = []
        for spec_path in self._legacy_work_files():
            state_path = spec_path.with_name("state.json")
            try:
                spec = json.loads(spec_path.read_text(encoding="utf-8"))
                state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
            except (OSError, ValueError):
                digest.update(spec_path.read_bytes())
                continue
            status = str(state.get("status") or spec.get("status") or "").upper()
            candidate_states = [str(item.get("status") or "").upper()
                                for item in (state.get("candidates") or {}).values()]
            if status in {"QUEUED", "RUNNING", "STOPPING", "DISPATCHING", "REEVALUATING"} or any(
                    item in {"QUEUED", "RUNNING", "DISPATCHING", "TRANSFERRING"} for item in candidate_states):
                active.append(str(spec_path.relative_to(self.library_root)))
            digest.update(spec_path.read_bytes())
            if state_path.is_file():
                digest.update(state_path.read_bytes())
        self._active_work = active
        digest.update(json.dumps(decisions, sort_keys=True, separators=(",", ":")).encode())
        digest.update(json.dumps(source_choices, sort_keys=True, separators=(",", ":")).encode())
        return digest.hexdigest()

    def dry_run(self) -> dict:
        decisions = []
        scopes = self._scope_entries()
        for scope in scopes:
            records, invalid = self._locked_records(scope["character"], scope["phase"], scope["legacy_pipeline"], scope["costume"])
            by_view: dict[str, list[dict]] = {}
            for record in records:
                by_view.setdefault(record["view"], []).append(record)
            for view in VIEW_ORDER:
                choices = by_view.get(view, [])
                # The catalog-approved current lock breaks timestamp ties, then key/Inventory identity is stable.
                choices.sort(key=lambda record: (self._stamp(record), bool(record.get("entity_library_asset_id")),
                                                 str(record.get("key") or ""),
                                                 str(record.get("entity_library_asset_id") or "")), reverse=True)
                chosen = choices[0] if choices else None
                skipped = [item for item in invalid if item["key"].lower().endswith(view.lower())]
                skipped.extend({"key": item.get("key"), "inventory_asset_id": item.get("entity_library_asset_id"),
                                "reason": "superseded current Final lock"} for item in choices[1:])
                if chosen:
                    image = Path(chosen["image_path"]).resolve()
                    if not image.is_relative_to(self.library_root) or not image.is_file():
                        skipped.append({"key": chosen.get("key"), "reason": "locked image bytes unavailable"})
                        chosen = None
                decisions.append({**scope, "view": view,
                    "source_key": chosen.get("key") if chosen else "",
                    "candidate_id": chosen.get("candidate_id") if chosen else "",
                    "inventory_asset_id": chosen.get("entity_library_asset_id") if chosen else "",
                    "locked_at": self._stamp(chosen) if chosen else "",
                    "image_sha256": chosen.get("image_sha256") if chosen else "",
                    "legacy_recorded_image_sha256": chosen.get("legacy_recorded_image_sha256") if chosen else "",
                    "image_path": chosen.get("image_path") if chosen else "",
                    "prompt": chosen.get("prompt") if chosen else "",
                    "skipped": skipped,
                    "status": "import" if chosen else "empty"})
        source_choices = self._saved_phase_choices(scopes, decisions)
        fingerprint = self._fingerprint(decisions, source_choices)
        return {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                "library_root": str(self.library_root), "universe_id": self.universe_id,
                "decisions": decisions, "source_choices": source_choices,
                "active_legacy_work": list(getattr(self, "_active_work", [])),
                "state_fingerprint": fingerprint}

    def apply(self, report: dict, *, reviewed_report: str | Path, backup_dir: str | Path,
              backup_verified: bool, legacy_quiesced: bool, approved: bool) -> dict:
        if not (backup_verified and legacy_quiesced and approved):
            raise CharacterContainerMigrationError("Apply requires a verified backup, quiesced legacy work, and separate approval.")
        if not backup_dir:
            raise CharacterContainerMigrationError("Specify the verified backup directory.")
        backup = Path(backup_dir).resolve()
        if not backup.is_dir() or not any(p.is_file() for p in backup.rglob("*")):
            raise CharacterContainerMigrationError("The verified backup directory must contain backup files.")
        reviewed_path = Path(reviewed_report).resolve()
        try:
            reviewed = json.loads(reviewed_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CharacterContainerMigrationError("The reviewed dry-run report is unavailable or invalid.") from exc
        if reviewed != report:
            raise CharacterContainerMigrationError("The reviewed report does not match the supplied dry-run report.")
        if (Path(str(report.get("library_root") or "")).resolve() != self.library_root
                or str(report.get("universe_id") or "") != self.universe_id):
            raise CharacterContainerMigrationError("The reviewed report belongs to a different universe library.")
        current = self.dry_run()
        if current.get("state_fingerprint") != report.get("state_fingerprint"):
            raise CharacterContainerMigrationError("Legacy state changed after review; create and review a new report.")
        if current["active_legacy_work"]:
            raise CharacterContainerMigrationError("Legacy work is active; quiesce it before applying the import.")
        imported = 0
        for item in report["decisions"]:
            if item["status"] != "import":
                continue
            scope = {key: item[key] for key in ("character", "phase", "pipeline", "costume")}
            path = self.container_root / quote(scope["character"], safe="-_.") / quote(scope["phase"], safe="-_.") / scope["pipeline"] / (quote(scope["costume"], safe="-_.") if scope["costume"] else "_") / "container.json"
            with file_lock(path.with_suffix(".lock")):
                if path.exists():
                    value = json.loads(path.read_text(encoding="utf-8"))
                    prior = value.get("legacy_migration", {}).get("views", {}).get(item["view"])
                    if prior == item["source_key"]:
                        continue
                    board = value.get("boards", {}).get(item["view"], {})
                    if board.get("candidates"):
                        raise CharacterContainerMigrationError(f"Container already has board work: {scope} {item['view']}.")
                else:
                    from zet.services.character_asset_container_service import CharacterAssetContainerService
                    value = CharacterAssetContainerService._empty({**scope, "universe_id": report["universe_id"],
                                                                    "views": list(VIEW_ORDER)})
                board = value["boards"][item["view"]]
                if board.get("candidates"):
                    raise CharacterContainerMigrationError(f"Container already has board work: {scope} {item['view']}.")
                source = Path(item["image_path"]).resolve()
                if not source.is_file() or not source.is_relative_to(self.library_root):
                    raise CharacterContainerMigrationError("A reviewed locked image is no longer available.")
                candidate_id = self._import_candidate_id(item)
                destination_dir = path.parent / "images"
                destination_dir.mkdir(parents=True, exist_ok=True)
                destination = destination_dir / f"{candidate_id}{source.suffix.lower()}"
                expected_hash = str(item.get("image_sha256") or "")
                if destination.is_file():
                    copied_hash = hashlib.sha256(destination.read_bytes()).hexdigest()
                else:
                    temporary = destination.with_name(f".{destination.name}.tmp")
                    try:
                        shutil.copy2(source, temporary)
                        copied_hash = hashlib.sha256(temporary.read_bytes()).hexdigest()
                        if expected_hash and copied_hash != expected_hash:
                            raise CharacterContainerMigrationError("Locked image bytes changed during migration.")
                        os.replace(temporary, destination)
                    finally:
                        temporary.unlink(missing_ok=True)
                if expected_hash and copied_hash != expected_hash:
                    raise CharacterContainerMigrationError("Existing imported image bytes do not match the reviewed report.")
                candidate = {"candidate_id": candidate_id, "slot": 1, "status": "COMPLETE",
                    "render_mode": "final", "image_path": str(destination), "locked_image_path": str(source),
                    "image_sha256": expected_hash or copied_hash,
                    "inventory_asset_id": item["inventory_asset_id"], "locked": True, "prompt": item["prompt"],
                    "input_snapshots": [], "provenance": {"kind": "legacy_import", "source_key": item["source_key"],
                                    "legacy_candidate_id": item["candidate_id"], "inventory_asset_id": item["inventory_asset_id"],
                                    "legacy_recorded_image_sha256": item.get("legacy_recorded_image_sha256", "")},
                    "legacy_dependencies": item.get("dependencies") or [],
                    "created_at": item["locked_at"]}
                board["slots"][0] = candidate_id
                board["selected_id"] = candidate_id
                board["candidates"][candidate_id] = candidate
                value.setdefault("legacy_migration", {}).setdefault("views", {})[item["view"]] = item["source_key"]
                value["revision"] = int(value.get("revision", 0)) + 1
                write_json_atomic(path, value)
                imported += 1
        for choice in report.get("source_choices", []):
            scope = {key: choice[key] for key in ("character", "phase", "pipeline", "costume")}
            path = self.container_root / quote(scope["character"], safe="-_.") / quote(scope["phase"], safe="-_.") / scope["pipeline"] / (quote(scope["costume"], safe="-_.") if scope["costume"] else "_") / "container.json"
            with file_lock(path.with_suffix(".lock")):
                if path.is_file():
                    value = json.loads(path.read_text(encoding="utf-8"))
                else:
                    from zet.services.character_asset_container_service import CharacterAssetContainerService
                    value = CharacterAssetContainerService._empty({**scope,
                        "universe_id": self.universe_id,
                        "views": list(VIEW_ORDER)})
                prior = value.get("legacy_migration", {}).get("phase_source_choices", {}).get(choice["mode"], {}).get("legacy_source_key")
                if prior == choice["legacy_source_key"]:
                    continue
                if choice.get("status") == "import" and choice.get("source_kind") == "upload":
                    source = Path(str(choice.get("upload_source_path") or "")).resolve()
                    expected_hash = str(choice.get("upload_source_sha256") or "")
                    if (not source.is_file() or not source.is_relative_to(self.library_root)
                            or hashlib.sha256(source.read_bytes()).hexdigest() != expected_hash):
                        raise CharacterContainerMigrationError("The reviewed uploaded phase source is unavailable or changed.")
                    destination_dir = path.parent / "inputs" / "phase-change"
                    destination_dir.mkdir(parents=True, exist_ok=True)
                    suffix = source.suffix.lower()
                    destination = destination_dir / f"{expected_hash}{suffix}"
                    if destination.is_file() and hashlib.sha256(destination.read_bytes()).hexdigest() != expected_hash:
                        raise CharacterContainerMigrationError("Managed phase source conflicts with the reviewed upload.")
                    if not destination.is_file():
                        temporary = destination.with_name(f".{destination.name}.tmp")
                        try:
                            shutil.copy2(source, temporary)
                            if hashlib.sha256(temporary.read_bytes()).hexdigest() != expected_hash:
                                raise CharacterContainerMigrationError("Uploaded phase source changed during migration.")
                            os.replace(temporary, destination)
                        finally:
                            temporary.unlink(missing_ok=True)
                    source_value = {"kind": "upload", "path": str(destination),
                        "sha256": expected_hash, "filename": choice.get("upload_filename") or source.name}
                    value.setdefault("sources", {})["phase_change"] = source_value
                elif choice.get("status") == "import":
                    source_decision = next((item for item in report["decisions"]
                        if item.get("character", "").casefold() == choice["character"].casefold()
                        and item.get("phase", "").casefold() == choice["source_phase"].casefold()
                        and item.get("pipeline") == choice["source_pipeline"]
                        and item.get("view") == "FRONT"
                        and item.get("inventory_asset_id") == choice["source_inventory_asset_id"]
                        and item.get("status") == "import"), None)
                    if (not source_decision
                            or self._import_candidate_id(source_decision) != choice.get("candidate_id")):
                        raise CharacterContainerMigrationError("The reviewed phase-change source identity is inconsistent.")
                    value.setdefault("sources", {})["phase_change"] = {
                        "phase": choice["source_phase"]}
                else:
                    # Choices are applied Draft then Final, so an unavailable saved
                    # Final source intentionally prevents fallback to Draft.
                    value.setdefault("sources", {}).pop("phase_change", None)
                value.setdefault("legacy_migration", {}).setdefault("phase_source_choices", {})[choice["mode"]] = {
                    key: choice.get(key, "") for key in (
                        "legacy_source_key", "source_phase", "source_pipeline",
                        "source_inventory_asset_id", "source_legacy_key", "source_kind", "status", "reason",
                        "upload_source_sha256", "upload_filename")}
                value["revision"] = int(value.get("revision", 0)) + 1
                write_json_atomic(path, value)
        return {"imported_views": imported, "dry_run_fingerprint": current["state_fingerprint"]}
