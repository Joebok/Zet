"""Explicitly choose current masters and report new-render inputs by view."""
from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory



class LocalCurrentMastersService:
    def __init__(self, workflow):
        self.workflow = workflow

    def use(self, run_id: str, *, render_mode: str = "draft", costume: str = "") -> dict:
        if render_mode not in {"draft", "final"}:
            raise ValueError("Render mode must be draft or final.")
        workflow = self.workflow
        run = workflow.prompt_improvement.detail(run_id, costume)
        root = Path(run["root"])
        revision_id = ""
        views = (run.get("character_progression") or {}).get("requested_views") or run.get("views") or []
        rows = []
        with TemporaryDirectory(prefix="current-masters-", dir=root) as directory:
            for view in views:
                try:
                    reason = workflow.slots._prerequisite(run, view, render_mode)
                    if reason:
                        raise ValueError(reason)
                    output = Path(directory) / view
                    saved = workflow.slots.prepare_input(run, view, output / "inputs", recompile=True,
                        output_dir=output, render_mode=render_mode)
                    rows.append({"view": view, "status": "ready", "revision_id": revision_id,
                                 "prompt_sha256": hashlib.sha256(saved["prompt"].encode("utf-8")).hexdigest(),
                                 "prompt": saved["prompt"],
                                 "references": [{key: reference.get(key, "") for key in
                                                 ("role", "candidate_id", "view", "render_mode", "sha256")}
                                                for reference in saved.get("references") or []]})
                except (ValueError, OSError, KeyError) as exc:
                    rows.append({"view": view, "status": "blocked", "revision_id": revision_id,
                                 "reason": str(exc)})
        return {"run_id": run_id, "render_mode": render_mode, "revision_id": revision_id,
                "all_ready": all(row["status"] == "ready" for row in rows), "views": rows}

    def preview_view(self, run_id: str, view: str, *, render_mode: str = "draft", costume: str = "") -> str:
        if render_mode not in {"draft", "final"}:
            raise ValueError("Render mode must be draft or final.")
        run = self.workflow.prompt_improvement.detail(run_id, costume)
        view = view.upper()
        if view not in run.get("views", []):
            raise ValueError("Unknown character view.")
        reason = self.workflow.slots._prerequisite(run, view, render_mode)
        if reason:
            raise ValueError(reason)
        with TemporaryDirectory(prefix="current-view-prompt-", dir=Path(run["root"])) as directory:
            output = Path(directory) / view
            saved = self.workflow.slots.prepare_input(run, view, output / "inputs", output_dir=output,
                                                      render_mode=render_mode)
            return saved["prompt"]
