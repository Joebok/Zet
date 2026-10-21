"""Human-controlled character stages and advisory reference provenance."""
from pathlib import Path

from zet.services.library_reference_service import read_library_json, pipeline_library_root_for_path
from zet.services.local_image_pipeline_policy import mutate_local_run_state
from zet.services.local_prompt_preview_service import PREDECESSORS
from zet.services.view_conditioning_service import VIEW_ORDER
from zet.services.workflow_storage import file_lock


STAGES = (("FRONT",), ("FRONT_LEFT_3_4", "FRONT_RIGHT_3_4"),
          ("LEFT_PROFILE", "RIGHT_PROFILE"), ("BACK_LEFT_3_4", "BACK_RIGHT_3_4"), ("BACK",))


def read_progression(root):
    return read_library_json(Path(root) / "state.json", pipeline_library_root_for_path(root)).get("character_progression")


def required_views(views):
    requested = set(views)
    if requested - set(VIEW_ORDER):
        raise ValueError("Unknown requested character view.")
    for view in list(requested):
        while view in PREDECESSORS:
            view = PREDECESSORS[view]
            requested.add(view)
    return [view for view in VIEW_ORDER if view in requested]


def planned_views(payload, defaults=VIEW_ORDER):
    requested = ["FRONT"] if payload.get("front_only") else payload.get("views", list(defaults))
    if not isinstance(requested, list) or not requested:
        raise ValueError("Choose at least one character view.")
    return required_views(requested)


def enroll(root, views=None):
    def update(state):
        state.setdefault("character_progression", {"version": 1, "accepted_revision_id": "", "stage": -1,
            "requested_views": required_views(views or VIEW_ORDER), "back_reference": "BACK_LEFT_3_4"})
    mutate_local_run_state(Path(root), update)


def accept_prompts(root, revision_id):
    def update(state):
        state["character_progression"]["accepted_revision_id"] = revision_id
    mutate_local_run_state(Path(root), update)


def prompt_review_required(run):
    return run.get("kind") != "character-assembly" and not (run.get("character_progression") or {}).get("accepted_revision_id")


def opened_views(run):
    flow = run.get("character_progression")
    if not flow:
        return set(run.get("views", []))
    if prompt_review_required(run):
        return set()
    return {view for stage in STAGES[:flow["stage"] + 1] for view in stage
            if view in flow["requested_views"]}


def guard_view(run, view):
    if run.get("character_progression") and view not in opened_views(run):
        raise ValueError("Use Continue to open this generation stage first." if run.get("kind") == "character-assembly"
                         else "Accept prompt review and use Continue to open this generation stage first.")


def execution_views(run, views=None):
    flow = run.get("character_progression")
    if not flow:
        return views
    if prompt_review_required(run) or flow["stage"] < 0:
        return set()
    current = set(STAGES[flow["stage"]]) & set(flow["requested_views"])
    return (set(views) & opened_views(run)) if views is not None else current


def prepare_candidate(workflow, run, candidate):
    if not run.get("character_progression") or candidate.get("render_input"):
        return candidate
    guard_view(run, candidate["view"])
    saved = workflow.slots.prepare_input(run, candidate["view"],
        Path(run["root"]) / "renders" / candidate["candidate_id"] / "inputs", recompile=True)
    return {**candidate, "render_input": saved}


def project(run):
    flow = run.get("character_progression")
    if not flow:
        return run
    run["character_progression"] = flow
    requested = flow["requested_views"]
    stage = flow["stage"]
    current = [v for v in (STAGES[stage] if stage >= 0 else ()) if v in requested]
    selected = run.get("selected_views", {})
    candidates = {c["candidate_id"]: c for c in run.get("candidates", [])}
    def available(view):
        candidate = candidates.get(selected.get(view), {})
        return (Path(str(candidate.get("image_path") or "")).is_file()
                and (candidate.get("human_review") or {}).get("decision") != "reject")
    busy = any(c.get("render_status", c.get("status")) in {"QUEUED", "RUNNING"}
               and not Path(str(c.get("image_path") or "")).is_file() for c in candidates.values())
    reason = ""
    if prompt_review_required(run):
        reason = "Analyze and accept the governing prompts first."
    elif run.get("stop_requested"):
        reason = "Resume the stopped batch first."
    elif busy:
        reason = "Wait for submitted renders to finish."
    elif any(not available(view) for view in current):
        reason = "Select an available image for each view in this stage."
    next_stage = next((i for i in range(stage + 1, len(STAGES)) if set(STAGES[i]) & set(requested)), None)
    run["progression"] = {"stage": stage, "current_views": current,
        "next_views": [v for v in STAGES[next_stage] if v in requested] if next_stage is not None else [],
        "can_continue": not reason and next_stage is not None, "reason": reason,
        "complete": all(available(v) for v in requested), "prompt_review_required": prompt_review_required(run)}
    warnings = []
    warned = set()
    for candidate in candidates.values():
        if selected.get(candidate["view"]) and selected[candidate["view"]] != candidate["candidate_id"]:
            continue
        for ref in (candidate.get("render_input") or {}).get("references") or (candidate.get("refinement") or {}).get("reference_inputs", []):
            source_view = ref.get("view")
            key = (candidate["view"], source_view)
            if ref.get("candidate_id") and source_view and selected.get(source_view) != ref["candidate_id"] and key not in warned:
                warned.add(key)
                warnings.append({"view": candidate["view"], "candidate_id": candidate["candidate_id"],
                    "message": f"Generated from an earlier {source_view} selection; your current choice has changed."})
    run["reference_warnings"] = warnings
    # Ranking/reference drift is advice, not a new gate on human choices.
    run["stale_selections"] = [v for v in selected if not available(v)]
    if run["progression"]["complete"] and not busy and not run.get("stop_requested"):
        run["status"] = "COMPLETE"
    return run


def advance(workflow, run_id, costume="", expected_stage=None, back_reference=None):
    root = Path(workflow.prompt_improvement.detail(run_id, costume)["root"])
    with file_lock(root / "state.lock"):
        run = project(workflow.prompt_improvement.detail(run_id, costume))
        flow = run["character_progression"]
        if expected_stage is not None and expected_stage != flow["stage"]:
            return {**run, "target_views": []}
        if not run["progression"]["can_continue"]:
            raise ValueError(run["progression"]["reason"] or "All requested stages are already open.")
        targets = run["progression"]["next_views"]
        next_stage = next(i for i, group in enumerate(STAGES) if targets[0] in group)
        back = "FRONT" if workflow.pipeline == "body-reference" else back_reference or flow.get("back_reference", "BACK_LEFT_3_4")
        back_sources = {"FRONT"} if workflow.pipeline == "body-reference" else {"BACK_LEFT_3_4", "BACK_RIGHT_3_4"}
        if workflow.pipeline != "character-assembly" and back not in back_sources:
            raise ValueError("Choose a selected back three-quarter reference.")
        from zet.services.local_view_reference_service import selected_reference
        recipes = {}
        for view in targets:
            if view == "FRONT" or workflow.pipeline == "character-assembly":
                continue
            source = back if view == "BACK" else PREDECESSORS[view]
            recipe = {"mode": "selected_view", "source_view": source}
            selected_reference(run, view, recipe)
            recipes[view] = recipe
        def update(state):
            state["character_progression"].update(stage=next_stage, back_reference=back)
            state.setdefault("view_reference_recipes", {}).update(recipes)
            state.update(target_views=targets, target_candidate_ids=[], status="QUEUED")
        mutate_local_run_state(root, update)
    return {**workflow.action("detail", run_id=run_id, costume=costume), "target_views": targets}


def select(workflow, run, view, candidate_id):
    """Select independently of advisory rankings; never invalidate later choices."""
    root = Path(run["root"])
    view = view.upper()
    if view not in run["views"]:
        raise ValueError("Unknown character view.")
    candidate = next((c for c in run["candidates"] if c["candidate_id"] == candidate_id and c["view"] == view), None)
    if candidate_id and (not candidate or not Path(str(candidate.get("image_path") or "")).is_file()
                         or (candidate.get("human_review") or {}).get("decision") == "reject"):
        raise ValueError("Choose an available, non-rejected candidate in this view.")
    adapter = workflow.adapter
    pipeline = {"body-reference": "Body-Reference", "head-image": "Head-Image",
                "character-assembly": "Character-Assembly", "costume-dressing": "Costume-Dressing"}[workflow.pipeline]
    qualifier = adapter._qualifier(run.get("costume", "")) if workflow.pipeline == "costume-dressing" else ""
    dependencies = [{"key": s["key"], "image_sha256": s.get("sha256", "")}
                    for s in (run.get("sources", {}).get(view) or {}).values() if s.get("key")]
    def update(state):
        selected = state.setdefault("selected_views", {})
        if candidate_id:
            selected[view] = candidate_id
        else:
            selected.pop(view, None)
        if view == "FRONT":
            state["front_anchor"] = candidate_id or None
        if state.get("status") not in {"RUNNING", "PREFLIGHT", "REEVALUATING", "STOPPING"}:
            state["status"] = "AWAITING_HUMAN_SELECTION"
    mutate_local_run_state(root, update)
    if candidate_id:
        adapter.asset_store.record_batch_selection(run["character"], run["phase"], pipeline, view,
            candidate_id=candidate_id, image_path=candidate["image_path"], batch_id=run["run_id"],
            qualifier=qualifier, dependencies=dependencies)
    else:
        adapter.asset_store.clear_batch_selection(run["character"], run["phase"], pipeline, view, run["run_id"], qualifier)
    return workflow.prompt_improvement.detail(run["run_id"], run.get("costume", ""))
