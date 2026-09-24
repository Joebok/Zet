from pathlib import Path

import pytest

from zet.services.local_image_pipeline_policy import clear_candidate_artifacts, gate_result_is_current


def test_gate_freshness_requires_image_anchor_and_prompt_hashes():
    record = {
        "status": "COMPLETE", "verdict": "FALSE",
        "input_hashes": {"candidate": "image", "front_anchor": "anchor"},
        "prompt_sha256": "prompt",
    }

    assert gate_result_is_current(
        record, input_hashes={"candidate": "image", "front_anchor": "anchor"}, prompt_sha256="prompt"
    )
    assert not gate_result_is_current(
        {**record, "prompt_sha256": ""}, input_hashes=record["input_hashes"], prompt_sha256="prompt"
    )
    assert not gate_result_is_current(
        record, input_hashes={"candidate": "image", "front_anchor": "changed"}, prompt_sha256="prompt"
    )


def test_artifact_cleanup_is_scoped_to_one_run_and_candidate(tmp_path: Path):
    run = tmp_path / "run-a"
    owned = run / "renders" / "c001" / "Local_Test_Renders" / "image.png"
    other_candidate = run / "renders" / "c002" / "Local_Test_Renders" / "image.png"
    other_run = tmp_path / "run-b" / "renders" / "c001" / "Local_Test_Renders" / "image.png"
    for path in (owned, other_candidate, other_run):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"image")

    clear_candidate_artifacts(run, "c001", owned)

    assert not owned.exists()
    assert other_candidate.is_file()
    assert other_run.is_file()
    with pytest.raises(ValueError, match="Invalid local image candidate ID"):
        clear_candidate_artifacts(run, "../c002")
