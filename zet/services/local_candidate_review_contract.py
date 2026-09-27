"""Shared state rules for reviewing rendered local pipeline candidates."""
from __future__ import annotations

from typing import Any


HUMAN_DECISIONS = frozenset({"keep", "reject", "undecided"})


def view_review_defaults() -> dict[str, Any]:
    """Return a fresh per-view record shared by manual and AI observations."""
    return {"observations": "", "ai_observations": {"status": "PENDING", "text": "", "auto_started": False}}


def normalize_human_decision(value: object) -> str:
    decision = str(value or "undecided")
    if decision not in HUMAN_DECISIONS:
        raise ValueError("Human decision must be keep, reject, or undecided.")
    return decision


def adjust_candidate_ranking(
    ranking: dict[str, Any], candidate_id: str, direction: str, *, timestamp: str,
) -> dict[str, Any]:
    """Apply one manual adjacent move while preserving Luna's original order."""
    order = list(ranking.get("ordered_candidate_ids") or [])
    if ranking.get("status") != "COMPLETE" or candidate_id not in order:
        raise ValueError("The candidate needs a current ranking before its rank can change.")
    if direction not in {"up", "down"}:
        raise ValueError("Rank direction must be up or down.")
    index = order.index(candidate_id)
    target = index + (-1 if direction == "up" else 1)
    if target < 0 or target >= len(order):
        return ranking
    adjusted = dict(ranking)
    adjusted.setdefault("luna_ordered_candidate_ids", list(order))
    order[index], order[target] = order[target], order[index]
    entries = {entry["candidate_id"]: entry for entry in ranking.get("entries") or []}
    adjusted["ordered_candidate_ids"] = order
    adjusted["entries"] = [entries[item] for item in order if item in entries]
    adjusted["adjusted_at"] = timestamp
    return adjusted
