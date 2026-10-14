"""Field contracts and validated proposals for Narrative interview review."""

MOMENT_FIELDS = ("narrative", "staging", "physical_context", "framing")
VISUAL_FIELDS = ("setting", "camera", "perspective", "lighting", "style")
FIELD_PURPOSES = {
    "appearance": "Identity, anatomy, clothing, intrinsic size and scene-specific equipment changes. Shared across subscenes; put pose in the moment fields.",
    "narrative": "The visible event, emotion, expression and individual action.",
    "staging": "Pose, gaze, gestures, interaction, arrangement and relative-height comparisons.",
    "physical_context": "Ground plane, contact, support and physical conditions affecting the action.",
    "framing": "Crop and required visible body parts.",
    "visual_context": "Setting, camera, perspective, lighting and style. A nonblank local override replaces its shared value for this target.",
}


def interview_review(result: dict, detail: dict, job_id: str) -> dict:
    """Normalize old replies and bind proposals to server-owned submitted values."""
    if not isinstance(result, dict):
        raise ValueError("The interview returned invalid proposals.")
    questions = result.get("questions", [])
    conflicts = result.get("conflicts", [])
    if (not isinstance(questions, list) or len(questions) > 2
            or any(not isinstance(value, str) for value in questions)
            or not isinstance(conflicts, list) or any(not isinstance(value, str) for value in conflicts)):
        raise ValueError("The interview returned invalid conflicts or questions.")
    proposals = result.get("proposals")
    if proposals is None:
        if any(not isinstance(result.get(key), str) for key in MOMENT_FIELDS):
            raise ValueError("The interview returned invalid draft fields.")
        proposals = [{"scope": "moment", "field": key, "element_id": "", "text": result[key],
                      "reason": "Interview revision."} for key in MOMENT_FIELDS]
    if not isinstance(proposals, list):
        raise ValueError("The interview returned invalid proposals.")
    elements = {item["id"]: item for item in detail.get("elements", [])}
    seen = set()
    rows = []
    for proposal in proposals:
        if (not isinstance(proposal, dict) or set(proposal) != {"scope", "field", "element_id", "text", "reason"}
                or any(not isinstance(value, str) for value in proposal.values())):
            raise ValueError("The interview returned an invalid proposal.")
        scope, key, element_id = (proposal[name] for name in ("scope", "field", "element_id"))
        if scope == "appearance" and key == "appearance" and element_id in elements:
            old = elements[element_id].get("appearance", "")
        elif scope == "moment" and key in MOMENT_FIELDS and not element_id:
            old = detail[key]
        elif scope == "visual" and key in VISUAL_FIELDS and not element_id:
            old = detail["context"][key]
        else:
            raise ValueError("The interview proposed a field outside its editing authority.")
        destination = (scope, key, element_id)
        if destination in seen:
            raise ValueError("The interview returned duplicate field proposals.")
        seen.add(destination)
        if old != proposal["text"]:
            rows.append({**proposal, "id": f"{job_id}-{len(rows)}", "old": old,
                         "element_name": elements[element_id]["name"] if element_id else ""})
    return {"status": "pending", "proposals": rows, "conflicts": conflicts, "questions": questions}
