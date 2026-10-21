"""Import an operator's image as a character view's working candidate."""
from __future__ import annotations

import hashlib
import io
from pathlib import Path
from uuid import uuid4

from PIL import Image

from zet.services.local_image_pipeline_policy import mutate_local_run_state
from zet.services.render_slot_service import RenderSlotConflict, slot_maps
from zet.services.workflow_storage import file_lock, runner_lock_active, validate_image


class LocalCharacterOverrideService:
    def __init__(self, workflow):
        self.workflow = workflow

    def import_image(self, run_id: str, view: str, costume: str, filename: str,
                     contents: bytes, expected_selected_id: str) -> dict:
        if not contents or len(contents) > 32 * 1024 * 1024:
            raise ValueError("Choose an image under 32 MB.")
        try:
            validate_image(contents)
            with Image.open(io.BytesIO(contents)) as image:
                suffix = {"PNG": ".png", "JPEG": ".jpg", "WEBP": ".webp"}[image.format]
        except Exception as exc:
            raise ValueError("Choose a readable PNG, JPEG or WebP image.") from exc
        workflow = self.workflow
        load = lambda: workflow.prompt_improvement.detail(run_id, costume)
        run = load()
        root = Path(run["root"])
        view = view.upper()
        with file_lock(root / "state.lock"):
            run = load()
            if view not in run["views"]:
                raise ValueError("Unknown character view.")
            if (runner_lock_active(root) or run.get("slot_work_pending") or run.get("slot_render_ids")
                    or run.get("status") in {"RUNNING", "PREFLIGHT", "REEVALUATING", "STOPPING"}
                    and not run.get("interrupted")):
                raise RenderSlotConflict("Wait for active batch work to finish before importing an override.")
            selected = run.get("selected_views", {}).get(view) or ""
            if selected != expected_selected_id:
                raise RenderSlotConflict("The selected image changed. Refresh before applying this override.")
            maps = slot_maps(run)
            slots = maps[view]
            if selected and selected in slots:
                index = slots.index(selected)
            elif None in slots:
                index = slots.index(None)
            else:
                available = {c["candidate_id"] for c in run["candidates"]
                             if not c.get("image_path") and not workflow.slots._protected(run, c)}
                index = next((i for i, cid in enumerate(slots) if cid in available), None)
                if index is None:
                    raise RenderSlotConflict("Select a candidate to replace, or clear a slot before importing an override.")
            replaced = slots[index]
            cid = uuid4().hex
            template = next((c for c in run["candidates"] if c["candidate_id"] == selected), None)
            template = template or next((c for c in run["candidates"] if c["view"] == view), {})
            recipe = {key: template[key] for key in (
                "seed", "ordinal", "view_index", "method", "prompt", "prompt_sha256", "template_revision_id"
            ) if key in template}
            image_path = root / "renders" / cid / ("override" + suffix)
            image_path.parent.mkdir(parents=True, exist_ok=True)
            image_path.write_bytes(contents)
            candidate = {**recipe, "candidate_id": cid, "view": view, "image_path": str(image_path),
                "image_sha256": hashlib.sha256(contents).hexdigest(), "status": "COMPLETE",
                "render_status": "COMPLETE", "human_review": {"decision": "keep"}, "retry_count": 0,
                "override": {"filename": Path(filename).name, "replaced_candidate_id": replaced or ""}}
            slots[index] = cid

            def update(state):
                state.setdefault("added_candidates", {})[cid] = candidate
                if replaced:
                    detached = state.setdefault("detached_candidates", [])
                    if replaced not in detached:
                        detached.append(replaced)
                state["slots_by_view"] = maps
                state["slot_version"] = int(state.get("slot_version", 0)) + 1

            mutate_local_run_state(root, update)
            # Shared manual selection preserves downstream choices and published locks,
            # including for retained batches predating staged progression.
            from zet.services.local_character_progression_service import select
            select(workflow, load(), view, cid)
        return workflow.action("detail", run_id=run_id, costume=costume)
