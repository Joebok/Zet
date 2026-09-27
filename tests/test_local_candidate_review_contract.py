from __future__ import annotations

import pytest

from zet.services.local_candidate_review_contract import (
    adjust_candidate_ranking, normalize_human_decision, view_review_defaults,
)


@pytest.mark.parametrize("pipeline", ["body-reference", "head-image", "character-assembly", "costume-dressing"])
def test_shared_review_state_has_manual_and_ai_observations(pipeline):
    first = view_review_defaults()
    second = view_review_defaults()
    assert first == {"observations": "", "ai_observations": {"status": "PENDING", "text": "", "auto_started": False}}
    assert first["ai_observations"] is not second["ai_observations"]


@pytest.mark.parametrize("value,expected", [("keep", "keep"), ("reject", "reject"), ("undecided", "undecided")])
def test_shared_human_decisions(value, expected):
    assert normalize_human_decision(value) == expected


def test_shared_ranking_adjustment_keeps_luna_order_and_handles_edges():
    ranking = {"status": "COMPLETE", "ordered_candidate_ids": ["F-001", "F-002"],
               "entries": [{"candidate_id": "F-001"}, {"candidate_id": "F-002"}]}
    moved = adjust_candidate_ranking(ranking, "F-002", "up", timestamp="now")
    assert moved["ordered_candidate_ids"] == ["F-002", "F-001"]
    assert moved["luna_ordered_candidate_ids"] == ["F-001", "F-002"]
    assert [entry["candidate_id"] for entry in moved["entries"]] == ["F-002", "F-001"]
    assert adjust_candidate_ranking(ranking, "F-001", "up", timestamp="now") is ranking


@pytest.mark.parametrize("ranking,candidate,direction", [
    ({"status": "STALE", "ordered_candidate_ids": ["F-001"]}, "F-001", "up"),
    ({"status": "COMPLETE", "ordered_candidate_ids": ["F-001"]}, "F-002", "up"),
    ({"status": "COMPLETE", "ordered_candidate_ids": ["F-001"]}, "F-001", "sideways"),
])
def test_shared_ranking_rejects_invalid_adjustments(ranking, candidate, direction):
    with pytest.raises(ValueError):
        adjust_candidate_ranking(ranking, candidate, direction, timestamp="now")
