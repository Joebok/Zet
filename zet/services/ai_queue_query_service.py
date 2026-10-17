"""Complete producer-local AI activity, independent of page visits and index lag."""
from __future__ import annotations

import json
import socket
from datetime import datetime, timedelta, timezone

from zet.repositories.ai_job_repository import AIJobRepository


class AIQueueQueryService:
    TERMINAL = {"APPLIED", "COMPLETE", "FAILED", "SUPERSEDED"}

    def __init__(self, paths):
        self.paths = paths
        self.repository = AIJobRepository(paths.lifecycle.root)

    def rows(self):
        from zet.services.storage_health_service import storage_health
        health = storage_health(self.paths.config)
        status = health.poll()
        if any(status["resources"][name]["status"] != "AVAILABLE" for name in ("queue", "application")):
            return self.cached(self.paths.config)["items"]
        receipts = list(self.paths.lifecycle.iter_receipts() or ())
        from zet.services.storage_maintenance_service import StorageMaintenanceService
        cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, int(self.paths.config.storage_completed_retention_days)))
        expired = set()
        for _, receipt in receipts:
            completed = None
            for key in ("completed_at", "harvested_at", "recorded_at"):
                if receipt.get(key):
                    try:
                        completed = datetime.fromisoformat(str(receipt[key]).replace("Z", "+00:00"))
                        completed = completed.replace(tzinfo=timezone.utc) if completed.tzinfo is None else completed.astimezone(timezone.utc)
                        break
                    except (ValueError, OverflowError):
                        continue
            job_id = str(receipt.get("ask_id") or "")
            expired_success = (StorageMaintenanceService._verified_completed(receipt)
                               and completed is not None and completed < cutoff)
            if job_id and (receipt.get("retention_compacted") or expired_success):
                expired.add(job_id)
        rows = {row["ask_id"]: {**row, "status": "HARVEST_FAILED" if row.get("harvest_state") == "HARVEST_FAILED" else "RECONCILING", "details": row.get("error", "")}
                for row in self.repository.all() if row["ask_id"] not in expired}
        client = self.paths.file_proxy_client
        try:
            execution = json.loads((client.root / "Control/execution_status.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            execution = {}
        locations = [(client.ask_root, "QUEUED"), (client.running_root, "RUNNING"),
                     (client.answer_root, "AWAITING_HARVEST"), (self.paths.lifecycle.inbox_root, "AWAITING_HARVEST"),
                     (self.paths.manual_ask_root(), "MANUAL"), (self.paths.manual_answer_root(), "AWAITING_HARVEST")]
        for root, status in locations:
            if not root.is_dir():
                continue
            for path in root.iterdir():
                if not path.is_dir() or path.name.startswith(".") or self.repository.is_deleted(path.name):
                    continue
                if path.name in expired:
                    continue
                try:
                    ask = json.loads((path / "ask_manifest.json").read_text(encoding="utf-8"))
                    envelope = json.loads((path / "job.json").read_text(encoding="utf-8")) if (path / "job.json").is_file() else {}
                    producer = str(envelope.get("producer_id") or "")
                    if producer and producer.casefold() != socket.gethostname().casefold():
                        continue
                    model = str(ask.get("model") or ask.get("ollama_model") or ask.get("checkpoint") or "")
                    provider = "manual" if status == "MANUAL" else "codex" if model.startswith("codex:") else "comfyui" if ask.get("worker_type") == "local_image_render" else "ollama"
                    row = {**rows.get(path.name, {}), "ask_id": path.name, "status": status,
                           "universe_id": ask.get("universe_id", ""), "provider": provider, "model": model,
                           "task_type": ask.get("task_type", ""), "worker_type": ask.get("worker_type", ""),
                           "created_at": envelope.get("created_at", rows.get(path.name, {}).get("created_at", "")),
                           "owner": {key: value for key, value in ask.items() if key.endswith("_id") or key in {"character", "phase", "view", "costume"}}, "details": ""}
                    if status == "QUEUED" and provider in {"ollama", "comfyui"} and execution.get("local_execution_blocked"):
                        row.update(status="HELD", details=execution.get("reason", "Local execution is blocked"))
                    if root == self.paths.manual_ask_root():
                        from zet.services.workflow_storage import task_state_path
                        if task_state_path(self.paths.lifecycle.queue_root, "Superseded", path.name,
                                           state_root=self.paths.lifecycle.storage_root).is_file():
                            row["status"] = "SUPERSEDED"
                        elif (path / "submission.json").is_file():
                            row["status"] = "AWAITING_HARVEST"
                    marker = path / "harvest_manifest.json"
                    if marker.is_file():
                        harvested = json.loads(marker.read_text(encoding="utf-8"))
                        if harvested.get("status") != "HARVESTED_FOR_EXTERNAL_CONSUMER":
                            row.update(status="FAILED" if "FAIL" in str(harvested.get("status", "")) else "COMPLETE",
                                       harvested_at=harvested.get("harvested_at", ""), details=harvested.get("message", ""))
                    if status == "AWAITING_HARVEST" and root in {client.answer_root, self.paths.lifecycle.inbox_root}:
                        block = client.answer_block(path)
                        if block:
                            row.update(block, details=block["blocking_reason"])
                        elif not ask.get("universe_id") or not envelope.get("producer_id"):
                            row.update(status="RECOVERY_REQUIRED", reason_code="MISSING_OWNER_METADATA",
                                       details="Universe or producer ownership is missing; preserve this answer for recovery.")
                    if rows.get(path.name, {}).get("harvest_state") == "HARVEST_FAILED":
                        row.update(status="HARVEST_FAILED", details=rows[path.name].get("error", ""))
                    elif rows.get(path.name, {}).get("harvest_state") == "HARVESTING":
                        row["status"] = "HARVESTING"
                    rows[path.name] = row
                except (OSError, ValueError):
                    if not path.is_dir():
                        continue
                    rows.setdefault(path.name, {"ask_id": path.name, "status": "RECOVERY_REQUIRED",
                                    "reason_code": "MISSING_OWNER_METADATA", "details": "Job ownership metadata is missing or unreadable; preserve the folder for recovery.",
                                    "created_at": ""})
        for _, receipt in receipts:
            job_id = receipt.get("ask_id")
            if not job_id or job_id in expired or self.repository.is_deleted(job_id):
                continue
            status = str(receipt.get("status", "APPLIED"))
            normalized = "FAILED" if "FAIL" in status or receipt.get("answer_status") in {"FAILED", "ERROR"} else "SUPERSEDED" if "SUPERSEDED" in status else "COMPLETE"
            rows[job_id] = {**rows.get(job_id, {}), **receipt, "status": normalized,
                           "harvested_at": receipt.get("harvested_at") or receipt.get("recorded_at", ""),
                           "details": receipt.get("error_message") or receipt.get("message", "")}
        deleted_root = self.repository.root.parent / "DeletedJobs"
        for path in deleted_root.glob("*.json"):
            try:
                deleted = json.loads(path.read_text(encoding="utf-8"))
                if not deleted.get("cleanup_complete"):
                    rows[deleted["ask_id"]] = {**deleted, "status": "HARVEST_FAILED",
                        "failure_stage": "deletion", "details": deleted.get("error") or "Cleanup interrupted; retry Delete job.",
                        "created_at": deleted.get("deleted_at", "")}
            except (OSError, ValueError, KeyError):
                continue
        for row in rows.values():
            try:
                row["age_seconds"] = max(0, int((datetime.now(timezone.utc) - datetime.fromisoformat(str(row.get("created_at") or "").replace("Z", "+00:00"))).total_seconds()))
            except (ValueError, TypeError):
                row["age_seconds"] = None
            row["recovery_action"] = "Retry Delete job to finish removing files." if row.get("failure_stage") == "deletion" else ({"HARVEST_FAILED": "Fix the collection error, then retry harvesting this retained answer.",
                "RECOVERY_REQUIRED": "Inspect the recovery report and restore verified ownership/routes before retrying.",
                "TRANSFERRING": "Wait for complete files and matching checksums; preserve the payload.",
                "RECONCILING": "Inspect request and receipt evidence before creating another attempt.",
                "FAILED": "Execution failed; explicitly retry the owning workflow when its cause is resolved."}).get(row["status"], "")
            owner = row.get("owner") or {}
            row["workflow"] = row.get("workflow") or row.get("task_type") or row.get("consumer") or row.get("worker_type", "")
            row["target"] = " / ".join(str(owner[key]) for key in ("character", "phase", "session_id", "run_id", "narrative_story_id", "narrative_scene_id", "narrative_target_id", "candidate_id", "view") if owner.get(key))
            row["workflow_url"] = self.workflow_url(row, owner)
            for internal in ("request", "manifest", "input_inventory", "envelope"):
                row.pop(internal, None)
        # Replacement envelopes are transport details, not independent user tasks.
        for job_id, row in list(rows.items()):
            saved = self.repository.get(job_id)
            if saved.get("logical_job_id"):
                del rows[job_id]
                continue
            universe = row.get("universe_id")
            if universe and universe != self.paths.config.universe_id:
                info = {"status": "RECOVERING", "recovery_stage": saved.get("recovery_stage", ""),
                        "current_attempt_id": saved.get("current_attempt_id", job_id)} if saved.get("current_attempt_id") else {}
                app = getattr(self.paths, "app", None)
                if app and row["status"] not in self.TERMINAL:
                    try:
                        bound = app.universe_service.bind_config(self.paths.config, universe)
                        if not storage_health(bound).poll()["available"]:
                            info.update(status="PAUSED_STORAGE", blocking_reason="This universe's storage is unavailable")
                    except (ValueError, OSError):
                        info.update(status="RECOVERY_REQUIRED", blocking_reason="Universe ownership cannot currently be resolved")
            else:
                info = self.paths.jobs.inspect(job_id)
            if info.get("status") == "PAUSED_STORAGE" and row["status"] not in self.TERMINAL:
                row.update(status="PAUSED_STORAGE", details=info.get("blocking_reason", ""))
            if info.get("recovery_stage"):
                row.update({key: info.get(key, "") for key in ("logical_job_id", "current_attempt_id", "recovery_stage", "last_recovered_at")})
                if info["status"] in {"RECOVERING", "PAUSED_STORAGE", "HELD", "SUPERSEDED"}:
                    row.update(status=info["status"], details=info.get("blocking_reason", ""),
                               recovery_action="Work will resume automatically.")
        result = sorted(rows.values(), key=lambda row: (row["status"] not in self.TERMINAL,
                      row.get("harvested_at") or row.get("created_at") or "", row["ask_id"]), reverse=True)
        from zet.services.atomic_file_service import write_json_atomic
        write_json_atomic(self.cache_path(self.paths.config), {"items": result})
        return result

    @staticmethod
    def cache_path(config):
        import hashlib
        from zet.services.storage_health_service import recovery_root
        return recovery_root(config).parent / "Activity" / (hashlib.sha256(str(config.base_ai_queue_path).encode()).hexdigest() + ".json")

    @classmethod
    def cached(cls, config):
        try:
            rows = json.loads(cls.cache_path(config).read_text(encoding="utf-8"))["items"]
        except FileNotFoundError:
            rows = []
        from zet.services.storage_health_service import request_journal_root
        known = {row["ask_id"]: row for row in rows}
        for path in request_journal_root(config).glob("*.json"):
            row = json.loads(path.read_text(encoding="utf-8"))
            if row.get("logical_job_id") or row.get("status") == "DELETED":
                known.pop(row["ask_id"], None)
                continue
            known[row["ask_id"]] = {**known.get(row["ask_id"], {}), **row}
        rows = list(known.values())
        rows = [dict(row, status="PAUSED_STORAGE", details="Storage unavailable; resumption is automatic")
                if row.get("status") not in cls.TERMINAL else row for row in rows]
        return {"items": rows, "total": None, "counts": None, "next_cursor": None, "stale": True}

    @staticmethod
    def workflow_url(row, owner):
        from urllib.parse import urlencode
        params = {"task_universe": row.get("universe_id", "")}
        if owner.get("narrative_story_id"):
            params.update(page="narrative", story=owner["narrative_story_id"], scene=owner.get("narrative_scene_id", ""), target=owner.get("narrative_target_id", ""))
        elif owner.get("session_id"):
            params.update(page="minor-characters", minor_character=owner["session_id"])
        elif any(owner.get(key) for key in ("local_body_reference_run_id", "local_head_image_run_id", "local_character_asset_run_id")):
            pipeline = row.get("workflow", "").lower()
            if owner.get("local_body_reference_run_id"):
                page, batch = "local-body-reference", owner["local_body_reference_run_id"]
            elif owner.get("local_head_image_run_id"):
                page, batch = "local-head-image", owner["local_head_image_run_id"]
            else:
                page = "local-costume-dressing" if "dressing" in pipeline else "local-character-assembly"
                batch = owner["local_character_asset_run_id"]
            params.update(page=page, local_batch=batch, task_context="1")
            if owner.get("costume"):
                params["local_costume"] = owner["costume"]
            for key in ("character", "phase"):
                if owner.get(key):
                    params["task_" + key] = owner[key]
        else:
            return ""
        return "/?" + urlencode(params)

    def query(self, *, universe="", provider="", workflow="", status="", cursor="", limit=50, history=False):
        all_rows = self.rows()
        rows = [row for row in all_rows if (not universe or row.get("universe_id") == universe)
                and (not provider or row.get("provider") == provider)
                and (not workflow or row.get("workflow") == workflow)
                and (not status or row["status"] == status)
                and (not history or row["status"] in self.TERMINAL)]
        offset = 0
        if cursor:
            offset = next((index + 1 for index, row in enumerate(rows) if row["ask_id"] == cursor), len(rows))
        items = rows[offset:offset + limit]
        return {"items": items, "total": len(rows), "next_cursor": items[-1]["ask_id"] if offset + limit < len(rows) else None,
                "recent_harvests": [row for row in all_rows if row["status"] in self.TERMINAL][:20],
                "counts": {state: sum(row["status"] == state for row in all_rows) for state in
                           {row["status"] for row in all_rows}},
                "facets": {"universes": sorted({row.get("universe_id", "") for row in all_rows} - {""}),
                           "workflows": sorted({row.get("workflow", "") for row in all_rows} - {""})}}

    def snapshot(self):
        rows = self.rows()
        return {"ask": [row for row in rows if row["status"] in {"QUEUED", "HELD", "MANUAL", "RECONCILING"}],
                "running": [row for row in rows if row["status"] == "RUNNING"],
                "answer": [row for row in rows if row["status"] in {"AWAITING_HARVEST", "HARVESTING", "TRANSFERRING", "HARVEST_FAILED", "RECOVERY_REQUIRED"}]}
