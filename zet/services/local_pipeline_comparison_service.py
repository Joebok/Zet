"""Explicit, read-only character batch prompt and reference comparisons."""
from __future__ import annotations

import hashlib
from pathlib import Path

from zet.services.local_pipeline_projection_service import LocalPipelineProjectionService
from zet.services.template_source_service import active_revision


def _prompt(candidate: dict) -> str:
    return str((candidate.get("render_input") or {}).get("prompt") or candidate.get("prompt") or "")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest() if value else ""


class LocalPipelineComparisonService:
    def __init__(self, workflow):
        self.workflow = workflow
        self.projections = LocalPipelineProjectionService(workflow)

    def report(self, run_id: str, kind: str, *, render_mode: str = "draft", costume: str = "") -> dict:
        if kind not in {"draft", "masters", "references"}:
            raise ValueError("Unknown comparison report.")
        mode = self.projections._mode(render_mode)
        run, _state = self.projections._load(run_id, costume)
        if kind == "draft":
            rows = self._draft(run)
        elif kind == "masters":
            rows = self._masters(run)
        else:
            rows = self._references(run, mode)
        return {"run_id": run_id, "render_mode": mode, "kind": kind, "rows": rows,
                "changed_count": sum(row.get("changed") is True for row in rows),
                "unavailable_count": sum(row.get("unavailable") is True for row in rows)}

    @staticmethod
    def _latest(run: dict, view: str, mode: str) -> dict:
        items = [item for item in run["candidates"] if item.get("view") == view
                 and item.get("render_mode", "draft") == mode]
        return items[-1] if items else {}

    def _draft(self, run: dict) -> list[dict]:
        rows = []
        for view in run.get("views") or []:
            draft, final = self._latest(run, view, "draft"), self._latest(run, view, "final")
            draft_prompt, final_prompt = _prompt(draft), _prompt(final)
            rows.append({"view": view, "draft_candidate_id": draft.get("candidate_id", ""),
                         "final_candidate_id": final.get("candidate_id", ""),
                         "draft_prompt_sha256": _digest(draft_prompt), "final_prompt_sha256": _digest(final_prompt),
                         "changed": draft_prompt != final_prompt if draft_prompt and final_prompt else None,
                         "unavailable": not bool(draft_prompt and final_prompt)})
        return rows

    def _masters(self, run: dict) -> list[dict]:
        from zet.services.local_template_revision_service import LocalTemplateRevisionService
        service = LocalTemplateRevisionService(self.workflow.app, self.workflow.project_root)
        current = {item["source_id"]: item for item in service._sources(self.workflow, run)}
        revision = active_revision(Path(run["root"]))
        saved = {item["source_id"]: item for item in revision.get("sources") or []}
        rows = []
        for source_id in sorted(set(current) | set(saved)):
            master, batch = current.get(source_id) or {}, saved.get(source_id) or {}
            master_text, batch_text = master.get("text", ""), batch.get("text", "")
            rows.append({"source_id": source_id, "label": master.get("label") or batch.get("label") or source_id,
                         "master_sha256": _digest(master_text), "batch_sha256": _digest(batch_text),
                         "batch_revision_id": revision.get("revision_id", ""),
                         "changed": master_text != batch_text if master_text and batch_text else None,
                         "unavailable": not bool(master_text and batch_text)})
        return rows

    def _references(self, run: dict, mode: str) -> list[dict]:
        selected = run["selected_views_by_mode"][mode]
        rows = []
        for view in run.get("views") or []:
            candidate = self._latest(run, view, mode)
            references = (candidate.get("render_input") or {}).get("references") or candidate.get("reference_images") or []
            for index, reference in enumerate(references):
                source_view = str(reference.get("view") or "")
                frozen_id = str(reference.get("candidate_id") or reference.get("source_candidate_id") or "")
                current_id = str(selected.get(source_view) or "") if source_view else ""
                path = Path(str(reference.get("path") or ""))
                rows.append({"view": view, "candidate_id": candidate.get("candidate_id", ""),
                             "index": index, "role": reference.get("role") or reference.get("prompt_role") or "",
                             "source_view": source_view, "frozen_candidate_id": frozen_id,
                             "frozen_sha256": reference.get("sha256") or "",
                             "current_candidate_id": current_id,
                             "changed": frozen_id != current_id if frozen_id and source_view else None,
                             "unavailable": bool(reference.get("path")) and not path.is_file()})
        return rows
