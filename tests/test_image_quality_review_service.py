from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from zet.services.image_quality_review_service import ImageQualityReviewService


class StubVisionService:
    def generate_json(self, _model, _system, _prompt, _schema, *, images):
        assert len(images) == 2
        return {
            "hard_gates": {
                "identity": True,
                "costume": True,
                "anatomy": True,
                "composition": True,
            },
            "scores": {
                "identity_fidelity": 3,
                "costume_fidelity": 3,
                "technical_quality": 4,
                "composition_control": 4,
                "style_fit": 3,
            },
            "failure_reasons": [],
            "evidence": "Visible reference traits match.",
        }


def test_reviews_experiment_and_preserves_human_decision(tmp_path: Path) -> None:
    reference = tmp_path / "reference.png"
    candidate = tmp_path / "candidate.png"
    Image.new("RGB", (1024, 1536), "white").save(reference)
    Image.new("RGB", (832, 1216), "teal").save(candidate)
    manifest = tmp_path / "experiment.json"
    manifest.write_text(json.dumps({
        "reference_image": str(reference),
        "candidates": [{"candidate_id": "c001", "image_path": str(candidate)}],
    }), encoding="utf-8")

    result = ImageQualityReviewService(
        Path(__file__).resolve().parents[1],
        StubVisionService(),
    ).review_experiment(manifest, model="vision")

    assert result["human_decision_required"] is True
    assert result["reviews"][0]["prefilter_pass"] is True
    assert result["reviews"][0]["weighted_mean"] == 3.3
    assert result["status"] == "COMPLETE"
    assert Path(result["output_path"]).is_file()
    assert max(Image.open(tmp_path / "review_inputs" / "reference.jpg").size) == 768
