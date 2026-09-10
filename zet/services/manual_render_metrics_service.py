from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from zet.services.ai_proxy_path_service import AIProxyPathService
from zet.services.config_service import Config
from zet.services.performance_instrumentation import record


REFINEMENT_TELEMETRY_START_DATE = "2026-09-09"


class ManualRenderMetricsService:
    """Summarize explicit ChatGPT refinement telemetry from manual renders."""

    def __init__(self, config: Config):
        self.path_service = AIProxyPathService(config)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def _answer_folders(self) -> Iterable[Path]:
        record("archive_traversals")
        live_root = self.path_service.manual_answer_root()
        if live_root.is_dir():
            yield from (
                path for path in live_root.iterdir()
                if path.is_dir() and not path.name.startswith(".")
            )
        archive_root = self.path_service.harvested_archive_root()
        if archive_root.is_dir():
            for date_path in archive_root.iterdir():
                if (
                    date_path.is_dir()
                    and date_path.name >= REFINEMENT_TELEMETRY_START_DATE
                ):
                    yield from (path.parent for path in date_path.rglob("answer_manifest.json"))

    @staticmethod
    def _refinement_record(answer: dict[str, Any]) -> tuple[bool, int] | None:
        record = answer.get("chatgpt_refinement")
        if not isinstance(record, dict) or record.get("schema_version") != 1:
            return None
        required = record.get("required")
        count = record.get("additional_image_generations")
        if not isinstance(required, bool) or isinstance(count, bool) or not isinstance(count, int):
            return None
        if (required and count < 1) or (not required and count != 0):
            return None
        return required, count

    @staticmethod
    def _aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
        refined = sum(1 for record in records if record["required"])
        total = len(records)
        additional = sum(record["additional_image_generations"] for record in records)
        return {
            "classified_count": total,
            "first_pass_count": total - refined,
            "first_pass_rate": (total - refined) / total if total else None,
            "refined_count": refined,
            "refinement_rate": refined / total if total else None,
            "additional_image_generations": additional,
            "average_additional_image_generations": additional / total if total else None,
            "average_when_refined": additional / refined if refined else None,
        }

    def summary(self) -> dict[str, Any]:
        submissions: dict[str, dict[str, Any]] = {}
        unknown_ids: set[str] = set()
        for folder in self._answer_folders():
            ask = self._read_json(folder / "ask_manifest.json")
            answer = self._read_json(folder / "answer_manifest.json")
            if ask.get("worker_type") != "manual_chatgpt_render" or answer.get("status") != "SUCCESS":
                continue
            ask_id = str(answer.get("ask_id") or ask.get("ask_id") or folder.name)
            refinement = self._refinement_record(answer)
            if refinement is None:
                if ask_id not in submissions:
                    unknown_ids.add(ask_id)
                continue
            unknown_ids.discard(ask_id)
            required, count = refinement
            submissions[ask_id] = {
                "required": required,
                "additional_image_generations": count,
                "engine_profile": str(ask.get("engine_profile") or "unspecified"),
                "pipeline": str(ask.get("pipeline") or "Story Scene"),
            }

        records = list(submissions.values())
        groups: dict[str, dict[str, list[dict[str, Any]]]] = {
            "engine_profile": defaultdict(list),
            "pipeline": defaultdict(list),
        }
        for record in records:
            for dimension in groups:
                groups[dimension][record[dimension]].append(record)

        return {
            **self._aggregate(records),
            "telemetry_start_date": REFINEMENT_TELEMETRY_START_DATE,
            "unknown_count": len(unknown_ids),
            "by_engine_profile": [
                {"value": value, **self._aggregate(items)}
                for value, items in sorted(groups["engine_profile"].items())
            ],
            "by_pipeline": [
                {"value": value, **self._aggregate(items)}
                for value, items in sorted(groups["pipeline"].items())
            ],
        }
