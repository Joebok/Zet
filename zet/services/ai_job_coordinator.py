"""One page-independent collection host with universe-bound domain handlers."""
from __future__ import annotations

import json
import logging
from pathlib import Path
import socket
import threading
from datetime import datetime, timedelta, timezone

from zet.repositories.ai_job_repository import AIJobRepository, timestamp
from zet.services.ai_workflow_service import AIWorkflowService
from zet.services.atomic_file_service import write_json_atomic
from zet.services.workflow_storage import file_lock


def image_services(app):
    generation = getattr(app, "_image_generation_service", None)
    if generation is None:
        from zet.services.ad_hoc_image_generation_service import AdHocImageGenerationService
        generation = app._image_generation_service = AdHocImageGenerationService(app, Path(__file__).resolve().parents[2])
        app.quick_character_wizard_service.generation_service = generation
    prompt = getattr(app, "_image_prompt_generation_service", None)
    if prompt is None:
        from zet.services.image_prompt_generation_service import ImagePromptGenerationService
        prompt = app._image_prompt_generation_service = ImagePromptGenerationService(app, Path(__file__).resolve().parents[2])
    return generation, prompt


class AIJobCoordinator:
    def __init__(self, app, resolve_app=None, interval=2):
        self.app = app
        self.resolve_app = resolve_app or (lambda universe: app if universe == app.universe_id else self._load(universe))
        self.interval = interval
        self.root = app.ai_proxy_service.ai_proxy_path_service.lifecycle.root
        self.repository = AIJobRepository(self.root)
        self._apps = {app.universe_id: app}
        self._stop = threading.Event()
        self._thread = None
        self._discovered = set()
        from zet.services.storage_recovery_service import StorageRecoveryService
        self.recovery = StorageRecoveryService(app)
        self.handlers = {
            "zet-narrative-scenes": self._narrative,
            "zet-image-generation": self._images,
            "zet-structured": self._structured,
            "zet_ollama_model_service": self._structured,
        }

    def register_handler(self, consumer, handler):
        self.handlers[consumer] = handler

    @staticmethod
    def _narrative(app, record, jobs):
        ask = record["manifest"]
        app.narrative_generation_service.detail(ask["narrative_story_id"], ask["narrative_scene_id"], ask["narrative_target_id"])

    @staticmethod
    def _images(app, record, jobs):
        generation = image_services(app)[0]
        request_id = record["manifest"]["ad_hoc_request_id"]
        generation.status(request_id)

    @staticmethod
    def _structured(app, record, jobs):
        job_id = record["ask_id"]
        result = jobs.result(job_id)
        if result is not None:
            contents, answer = result
            value = json.loads(contents)
            write_json_atomic(jobs.lifecycle.root / "StructuredResults" / f"{job_id}.json",
                              {"result": value, "runtime": answer.get("runtime", answer.get("ollama_runtime", {}))})
            jobs.finish(job_id)

    def _load(self, universe):
        from zet.app import ZetApp
        if universe not in self._apps:
            self._apps[universe] = ZetApp.from_config(self.app.config_path, universe_id=universe, validate_catalog=False)
        return self._apps[universe]

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="zet-ai-collection", daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _loop(self):
        while not self._stop.is_set():
            try:
                self.sweep()
            except TimeoutError:
                pass
            except Exception:
                logging.getLogger(__name__).exception("AI background collection failed")
            self._stop.wait(self.interval)

    def adopt(self):
        client = self.app.ai_proxy_service.ai_proxy_path_service.file_proxy_client
        for root in (client.ask_root, client.running_root, client.answer_root):
            if not root.is_dir():
                continue
            for path in root.iterdir():
                if not path.is_dir():
                    continue
                if path.name.startswith("."):
                    # Recover publication only when its complete immutable envelope was persisted.
                    if root == client.ask_root and path.name.endswith(".staging"):
                        try:
                            if not (path / "job.json").is_file():
                                pending_id = path.name[1:-len(".staging")]
                                pending = self.repository.get(pending_id)
                                envelope = pending.get("envelope")
                                if not envelope or not client._inventory_complete(path, envelope.get("files")):
                                    continue
                                write_json_atomic(path / "job.json", envelope)
                            envelope = json.loads((path / "job.json").read_text(encoding="utf-8"))
                            job_id = envelope["job_id"]
                            if (str(envelope.get("producer_id", "")).casefold() == socket.gethostname().casefold()
                                    and self.repository.get(job_id) and client._inventory_complete(path, envelope["files"])):
                                with file_lock(self.app.ai_proxy_service.ai_proxy_path_service.lifecycle.lock_path(job_id)):
                                    if path.is_dir() and not (client.ask_root / job_id).exists():
                                        client._replace_with_retry(path, client.ask_root / job_id)
                        except (OSError, ValueError, KeyError):
                            pass
                    continue
                try:
                    envelope = json.loads((path / "job.json").read_text(encoding="utf-8"))
                    if str(envelope.get("producer_id", "")).casefold() != socket.gethostname().casefold():
                        continue
                    ask = json.loads((path / "ask_manifest.json").read_text(encoding="utf-8"))
                    self.repository.register(path.name, ask, envelope)
                except (OSError, ValueError, KeyError):
                    continue

    def sweep(self, *, retry_failed=False):
        from zet.services.storage_health_service import StorageUnavailable
        self._refresh_host_app()
        try:
            self.recovery.health.require("queue", "application")
        except StorageUnavailable:
            return []
        try:
            with file_lock(self.root / "Locks/coordinator.lock", timeout=0.05):
                return self._sweep(retry_failed=retry_failed)
        except TimeoutError:
            return []

    def _refresh_host_app(self):
        app = self.resolve_app(self.app.universe_id)
        if app is self.app:
            return
        self.app = app
        self.root = app.ai_proxy_service.ai_proxy_path_service.lifecycle.root
        self.repository = AIJobRepository(self.root)
        from zet.services.storage_recovery_service import StorageRecoveryService
        self.recovery = StorageRecoveryService(app)

    def _sweep(self, *, retry_failed=False):
        from zet.services.storage_health_service import StorageUnavailable
        lifecycle = self.app.ai_proxy_service.ai_proxy_path_service.lifecycle
        before = {row.get("ask_id") for _, row in lifecycle.iter_receipts() or ()}
        self.import_legacy_history()
        self.adopt()
        records = list(self.repository.summaries())
        for record in records:
            retry_at = record.get("collection_retry_at")
            if record.get("harvest_state") == "HARVEST_FAILED" and retry_at and retry_at <= timestamp():
                self.repository.update(record["ask_id"], harvest_state="AWAITING_HARVEST", collection_retry_at="")
                record.update(harvest_state="AWAITING_HARVEST", collection_retry_at="")
        if retry_failed:
            for record in records:
                if record.get("harvest_state") == "HARVEST_FAILED":
                    self.repository.update(record["ask_id"], harvest_state="AWAITING_HARVEST", error="")
                    record.update(harvest_state="AWAITING_HARVEST", error="")
        universes = {self.app.universe_id}
        universes.update(item["universe_id"] for item in self.app.universe_service.list_universes())
        universes.update(row.get("universe_id") for row in records if row.get("harvest_state") not in {"APPLIED", "FAILED", "SUPERSEDED"})
        workflow_root = self.root / "Workflows"
        if workflow_root.is_dir():
            for path in workflow_root.glob("*.json"):
                try:
                    task = json.loads(path.read_text(encoding="utf-8"))
                    if task.get("status") in {"WAITING", "RUNNING"}:
                        universes.add(task["universe_id"])
                except (OSError, ValueError, KeyError):
                    continue
        for universe in universes - {"", None}:
            try:
                app = self.resolve_app(universe)
                if not hasattr(app, "_storage_recovery"):
                    from zet.services.storage_recovery_service import StorageRecoveryService
                    app._storage_recovery = StorageRecoveryService(app)
                try:
                    app._storage_recovery.recover()
                except StorageUnavailable:
                    continue
                except Exception:
                    logging.getLogger(__name__).exception("Unable to recover local batches for %s; continuing AI collection", universe)
                if universe not in self._discovered:
                    self._adopt_narrative(app)
                    self._discovered.add(universe)
                receipt_ids = {row.get("ask_id") for _, row in lifecycle.iter_receipts() or ()}
                candidates = [row for row in records if row.get("universe_id") == universe
                              and row.get("ask_id") not in receipt_ids
                              and row.get("harvest_state") not in {"SUPERSEDED", "HARVEST_FAILED"}
                              and not self.repository.is_deleted(row.get("ask_id", ""))]
                self._collect_app(app, [self.repository.get(row["ask_id"]) for row in candidates])
            except StorageUnavailable:
                continue
            except Exception:
                logging.getLogger(__name__).exception("Unable to collect AI work for %s", universe)
        try:
            from zet.services.storage_maintenance_service import StorageMaintenanceService
            StorageMaintenanceService(self.app.config).run_if_due()
        except Exception:
            logging.getLogger(__name__).exception("Zet local storage maintenance failed")
        return [row for _, row in lifecycle.iter_receipts() or () if row.get("ask_id") not in before]

    def import_legacy_history(self, batch_size=200):
        """Bounded metadata-only adoption; archived payloads remain untouched."""
        paths = self.app.ai_proxy_service.ai_proxy_path_service
        marker = self.root / "history-import.json"
        try:
            progress = json.loads(marker.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            progress = {}
        if progress.get("complete"):
            return
        archive = paths.harvested_archive_root()
        candidates = sorted(path for path in archive.glob("*/*/harvest_manifest.json")
                            if str(path) > progress.get("cursor", "")) if archive.is_dir() else []
        for path in candidates[:batch_size]:
            try:
                harvest = json.loads(path.read_text(encoding="utf-8"))
                ask = json.loads((path.parent / "ask_manifest.json").read_text(encoding="utf-8"))
                envelope_path = path.parent / "job.json"
                envelope = json.loads(envelope_path.read_text(encoding="utf-8")) if envelope_path.is_file() else {}
                producer = str(envelope.get("producer_id") or "")
                if producer and producer.casefold() != socket.gethostname().casefold():
                    continue
                job_id = ask.get("ask_id") or harvest.get("ask_id")
                if not job_id or self.repository.is_deleted(job_id) or paths.lifecycle.read_receipt(job_id) or harvest.get("status") == "HARVESTED_FOR_EXTERNAL_CONSUMER":
                    continue
                answer_path = path.parent / "answer_manifest.json"
                answer = json.loads(answer_path.read_text(encoding="utf-8")) if answer_path.is_file() else {}
                completion_stamp = str(harvest.get("harvested_at") or answer.get("completed_at") or "")
                if completion_stamp:
                    try:
                        completed = datetime.fromisoformat(completion_stamp.replace("Z", "+00:00"))
                        completed = completed.replace(tzinfo=timezone.utc) if completed.tzinfo is None else completed
                        if completed.astimezone(timezone.utc) < datetime.now(timezone.utc) - timedelta(
                            days=max(1, int(self.app.config.storage_completed_retention_days))
                        ):
                            continue
                    except (ValueError, OverflowError):
                        pass
                self.repository.register(job_id, ask, {"created_at": envelope.get("created_at", ""), "producer_id": producer, "files": []})
                record = self.repository.get(job_id)
                paths.lifecycle.write_receipt(job_id, {"ask_id": job_id, "universe_id": ask.get("universe_id", ""),
                    "provider": record.get("provider", ""), "model": record.get("model", ""), "owner": record.get("owner", {}),
                    "task_type": ask.get("task_type", ""), "asset_id": ask.get("asset_id"),
                    "status": harvest.get("status", "COMPLETE"), "answer_status": answer.get("status", ""),
                    "message": harvest.get("message", ""), "error_message": answer.get("error_message", ""),
                    "harvested_at": harvest.get("harvested_at") or answer.get("completed_at", ""),
                    "recorded_at": harvest.get("harvested_at") or answer.get("completed_at", ""),
                    "imported_at": timestamp(), "legacy_source": str(path)})
            except (OSError, ValueError, KeyError):
                continue
        write_json_atomic(marker, {"cursor": str(candidates[min(batch_size, len(candidates)) - 1]) if candidates else progress.get("cursor", ""),
                                   "complete": len(candidates) <= batch_size})

    @staticmethod
    def _adopt_narrative(app):
        repository = app.narrative_scene_service.repository
        for story in repository.stories():
            for scene in story["scene_ids"]:
                try:
                    for target in repository.read(story["id"], scene)["target_ids"]:
                        record = repository.read(story["id"], scene, target)
                        if any(job.get("status") in {"SUBMITTING", "QUEUED", "RUNNING", "DISPATCHING"} for job in record["jobs"].values()):
                            app.narrative_generation_service.detail(story["id"], scene, target)
                except KeyError:
                    continue

    def _collect_app(self, app, records):
        paths = app.ai_proxy_service.ai_proxy_path_service
        jobs = paths.jobs
        try:
            app._harvest_current_universe()
        except Exception:
            logging.getLogger(__name__).exception("Legacy collection failed for %s; continuing other consumers", app.universe_id)
        for record in records:
            job_id = record["ask_id"]
            if record.get("logical_job_id"):
                continue
            if record.get("harvest_state") == "SUPERSEDED":
                continue
            if self.repository.is_deleted(job_id):
                continue
            if paths.lifecycle.read_receipt(job_id):
                continue
            if record.get("harvest_state") == "HARVEST_FAILED":
                continue
            ask = record.get("manifest", {})
            consumer = record.get("consumer", "zet")
            try:
                handler = self.handlers.get(consumer)
                if handler is not None:
                    if jobs.ready_answer(job_id):
                        jobs.repository.update(job_id, harvest_state="HARVESTING")
                    handler(app, record, jobs)
                elif consumer != "zet" and jobs.ready_answer(job_id):
                    raise ValueError(f"No registered result handler for {consumer}; result retained")
            except Exception as exc:
                from zet.services.ai_job_service import AIExecutionError
                if consumer in {"zet-structured", "zet_ollama_model_service"} and isinstance(exc, AIExecutionError):
                    write_json_atomic(paths.lifecycle.root / "StructuredResults" / f"{job_id}.json", {"error": str(exc)})
                    jobs.finish(job_id, status="FAILED", message=str(exc))
                else:
                    jobs.repository.collection_failed(job_id, exc, stage="consumer_application")
        # These handlers apply render/review transitions; they never run provider calls.
        try:
            minor = app.minor_character_service
            for session in minor._records():
                if not any(candidate.get("status") in {"QUEUING", "QUEUED", "RUNNING", "REVIEWING"} for candidate in session.get("candidates", [])):
                    continue
                try:
                    minor.get_character(session["session_id"])
                except Exception:
                    logging.getLogger(__name__).exception("Minor Character result application failed")
        except Exception:
            logging.getLogger(__name__).exception("Unable to discover Minor Character work")
        AIWorkflowService(app).resume()
