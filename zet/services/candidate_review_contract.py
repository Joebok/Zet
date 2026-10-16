"""Shared, pipeline-neutral validation for local image rankings."""

from __future__ import annotations



def validate_ranking(value: object, candidate_ids: list[str]) -> list[dict[str, str]]:
    """Validate an ordered comparison result against the exact submitted set."""
    if not isinstance(value, dict) or not isinstance(value.get("ranking"), list):
        raise ValueError("Ranking output must contain a ranking list.")
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in value["ranking"]:
        if not isinstance(item, dict):
            raise ValueError("Every ranking entry must be an object.")
        candidate_id = str(item.get("candidate_id") or "")
        reason = str(item.get("reason") or "").strip()
        if not candidate_id or candidate_id in seen or not reason:
            raise ValueError("Ranking entries require unique candidate IDs and concise reasons.")
        seen.add(candidate_id)
        normalized.append({"candidate_id": candidate_id, "reason": reason})
    if seen != set(candidate_ids) or len(normalized) != len(candidate_ids):
        raise ValueError("Ranking must contain every surviving candidate exactly once.")
    return normalized
