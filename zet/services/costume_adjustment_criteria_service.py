"""Costume/view acceptance targets, independent of batches and rendering modes."""
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from zet.services.library_reference_service import pipeline_library_root_for_path, read_library_json, write_library_json
from zet.services.workflow_storage import file_lock


class CostumeAdjustmentCriteriaService:
    def __init__(self, workflow):
        if workflow.pipeline != "costume-dressing":
            raise ValueError("Costume criteria require Costume Dressing.")
        self.workflow = workflow

    def _path(self, run):
        return self.workflow.adapter._workspace(run["character"], run["phase"], run["costume"]) / "adjustment_criteria.json"

    def detail(self, run, view):
        if view not in run["views"]:
            raise ValueError("Unknown costume view.")
        path = self._path(run)
        record = read_library_json(path, pipeline_library_root_for_path(path)) if path.is_file() else {"version": 1, "views": {}}
        return deepcopy(record["views"].get(view, {"revision": 0, "items": []}))

    def save(self, run, view, payload):
        path = self._path(run)
        path.parent.mkdir(parents=True, exist_ok=True)
        with file_lock(path.with_suffix(".lock")):
            current = self.detail(run, view)
            if payload.get("expected_revision") != current["revision"]:
                raise ValueError("Acceptance criteria changed; refresh before saving.")
            previous = {item["id"]: item for item in current["items"]}
            items = payload.get("items")
            if not isinstance(items, list) or len(items) > 100:
                raise ValueError("Supply at most 100 acceptance criteria.")
            saved, identities = [], set()
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError("Invalid acceptance criterion.")
                identity = item.get("id") or uuid4().hex
                text = item.get("text")
                status = item.get("status", "in_progress")
                if identity in identities or item.get("id") and identity not in previous:
                    raise ValueError("Criterion identities must be unique existing IDs or omitted for new items.")
                if not isinstance(text, str) or not text.strip() or len(text) > 4000 or status not in {"in_progress", "accomplished"}:
                    raise ValueError("Each criterion needs text and an in_progress or accomplished status.")
                old = previous.get(identity)
                if old and old["status"] == "accomplished" and text != old["text"]:
                    raise ValueError("Reopen an accomplished criterion before editing its text.")
                identities.add(identity)
                saved.append({"id": identity, "text": text.strip(), "status": status})
            if set(previous) - identities:
                raise ValueError("Keep existing criteria; change their status or text instead of removing them.")
            record = read_library_json(path, pipeline_library_root_for_path(path)) if path.is_file() else {"version": 1, "views": {}}
            record["views"][view] = {"revision": current["revision"] + 1, "items": saved}
            write_library_json(path, record, pipeline_library_root_for_path(path))
            return deepcopy(record["views"][view])
