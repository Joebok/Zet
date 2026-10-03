from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from zet.services.local_image_ranking_service import rank_images_with_luna


def test_shared_luna_runner_uses_one_schema_and_keeps_reference_images_ahead_of_candidates(tmp_path):
    reference = tmp_path / "front.png"
    first = tmp_path / "one.png"
    second = tmp_path / "two.png"
    for image in (reference, first, second):
        image.write_bytes(b"image")
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        Path(command[command.index("--output-last-message") + 1]).write_text(json.dumps({
            "ranking": [
                {"candidate_id": "F-002", "reason": "Clearer view."},
                {"candidate_id": "F-001", "reason": "Less clear."},
            ]
        }), encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    entries, model = rank_images_with_luna(
        project_root=tmp_path, model="gpt-6-luna", prompt="Rank Tsaeytte’s images — preserve dialogue.",
        candidate_ids=["F-001", "F-002"], image_paths=[first, second],
        reference_image_paths=[reference], executable="codex", runner=runner,
    )

    command, kwargs = calls[0]
    image_args = [command[index + 1] for index, value in enumerate(command[:-1]) if value == "--image"]
    assert image_args == [str(reference), str(first), str(second)]
    assert kwargs["input"] == "Rank Tsaeytte’s images — preserve dialogue."
    assert kwargs["encoding"] == "utf-8"
    assert [item["candidate_id"] for item in entries] == ["F-002", "F-001"]
    assert model == "gpt-6-luna"


def test_shared_luna_runner_rejects_incomplete_image_sets():
    with pytest.raises(ValueError, match="exactly one image"):
        rank_images_with_luna(project_root=".", model="luna", prompt="", candidate_ids=["F-001"],
                              image_paths=[], executable="codex")
