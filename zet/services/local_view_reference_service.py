"""Explicit same-batch reference recipes for new individual character renders."""
from __future__ import annotations

from pathlib import Path

from zet.services.library_reference_service import pipeline_library_root_for_path, read_library_json
from zet.services.local_image_pipeline_policy import mutate_local_run_state


def reference_recipes(root: Path) -> dict:
    from zet.services.storage_health_service import guard_path
    guard_path(root)
    if not (root / "state.json").is_file() and not (root / "spec.json").is_file():
        return {}  # Initial compilation precedes creation of the run records.
    return read_library_json(root / "state.json", pipeline_library_root_for_path(root)).get("view_reference_recipes", {})


def selected_reference(run: dict, view: str, recipe: dict) -> dict | None:
    source_view = recipe.get("source_view")
    if recipe.get("mode") != "selected_view":
        return None
    if source_view == view or source_view not in run.get("views", []):
        raise ValueError("Choose a different view in this batch as the reference.")
    cid = (run.get("selected_views") or {}).get(source_view)
    if source_view == "FRONT":
        cid = cid or run.get("front_anchor")
    candidate = next((c for c in run.get("candidates", []) if c["candidate_id"] == cid and c["view"] == source_view), {})
    image = Path(str(candidate.get("image_path") or ""))
    if not cid or not image.is_file() or (candidate.get("human_review") or {}).get("decision") == "reject":
        raise ValueError(f"Select an available, non-rejected {source_view} image in this batch first.")
    if not image.resolve().is_relative_to(Path(run["root"]).resolve()):
        raise ValueError("The selected reference must belong to this batch.")
    return {"role": "batch_view_reference", "prompt_role": "subject_reference", "path": str(image),
            "view": source_view, "candidate_id": cid,
            "label": f"Selected {source_view} from this batch ({cid})",
            "preserve": ["visible identity and design details consistent with the authored target"],
            "ignore": ["source camera angle, pose, crop and visibility of surfaces hidden in the target view"],
            "notes": f"Design reference from {source_view}; output must show {view}. Do not rotate the target toward this image or invent hidden front details."}


def save_reference_recipe(run: dict, view: str, payload: dict) -> dict:
    view = str(view).upper()
    if view not in run.get("views", []):
        raise ValueError("Unknown character view.")
    mode = payload.get("mode")
    if mode not in {"default", "none", "selected_view"}:
        raise ValueError("Reference mode must be default, none or selected_view.")
    recipe = {"mode": mode, "source_view": str(payload.get("source_view") or "").upper() if mode == "selected_view" else ""}
    if run.get("character_progression"):
        from zet.services.local_prompt_preview_service import PREDECESSORS
        source = recipe["source_view"]
        valid = view == "BACK" and source in {"BACK_LEFT_3_4", "BACK_RIGHT_3_4"}
        valid = valid or view != "BACK" and source == PREDECESSORS.get(view) and bool(source)
        if recipe["mode"] != "selected_view" or not valid:
            raise ValueError("Staged batches use their selected same-side predecessor; BACK may use either rear quarter.")
    selected_reference(run, view, recipe)
    def update(state):
        state.setdefault("view_reference_recipes", {})[view] = recipe
        if view == "BACK" and state.get("character_progression"):
            state["character_progression"]["back_reference"] = recipe["source_view"]
    mutate_local_run_state(Path(run["root"]), update)
    return recipe


def custom_references(run: dict, view: str, pipeline: str, base: list[dict]) -> list[dict]:
    recipe = reference_recipes(Path(run["root"])).get(view) or {"mode": "default"}
    if recipe["mode"] == "default":
        return base
    # These replace only the batch anchor. Matching Body/Head/Assembly inputs and
    # costume-specific resources retain their own roles and order.
    anchor_roles = {"body_reference_front_anchor", "front_assembly", "front_costume", "batch_view_reference"}
    if pipeline == "head-image":
        anchor_roles.add("head_image_source")
    refs = [ref for ref in base if ref.get("role") not in anchor_roles]
    reference = selected_reference(run, view, recipe)
    if reference:
        if pipeline == "head-image":
            reference.update(role="head_image_source", prompt_role="edit_base")
        refs.append(reference)
    return refs


def recipe_requirement(run: dict, view: str) -> str | None:
    """None uses legacy prerequisites; an empty string explicitly needs no anchor."""
    recipe = reference_recipes(Path(run["root"])).get(view) or {"mode": "default"}
    if recipe["mode"] == "default":
        return None
    try:
        selected_reference(run, view, recipe)
    except ValueError as exc:
        return str(exc)
    return ""


def batch_reference_guidance(references: list[dict], target_view: str) -> str:
    lines = []
    for index, ref in enumerate(references, 1):
        if ref.get("role") == "batch_view_reference" or (ref.get("role") == "head_image_source" and ref.get("candidate_id")):
            lines.append(f"Image {index} is the selected {ref['view']} design reference from this batch. "
                         f"The output orientation remains {target_view}; do not copy this reference's camera angle, pose or framing. "
                         "Preserve only visible identity/design details supported by the target specification. "
                         "Front-facing details must not appear on hidden rear surfaces.")
    return "\n".join(lines)
