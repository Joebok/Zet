from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from zet.services.image_quality_review_service import ImageQualityReviewService


class StubVisionService:
    image_count = 0
    def generate_json_with_evidence(self, model, system, prompt, schema, *, images):
        return self.generate_json(model, system, prompt, schema, images=images), {
            "requested_alias": model, "effective_alias": model, "digest": "sha256:test",
            "runtime_settings": {"num_ctx": 65536, "num_predict": 2048},
        }

    def generate_json(self, _model, _system, _prompt, _schema, *, images):
        self.image_count = len(images)
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
                "pose_orientation": 4,
                "composition_framing": 4,
                "style_fit": 3,
            },
            "failure_reasons": [],
            "evidence": "Visible reference traits match.",
        }


def test_reviews_experiment_and_preserves_human_decision(tmp_path: Path) -> None:
    reference = tmp_path / "reference.png"
    candidate = tmp_path / "candidate.png"
    pose = tmp_path / "pose.png"
    Image.new("RGB", (1024, 1536), "white").save(reference)
    Image.new("RGB", (832, 1216), "teal").save(candidate)
    Image.new("RGB", (832, 1216), "gray").save(pose)
    manifest = tmp_path / "experiment.json"
    manifest.write_text(json.dumps({
        "reference_image": str(reference),
        "pose_image": str(pose),
        "candidates": [{"candidate_id": "c001", "image_path": str(candidate)}],
    }), encoding="utf-8")

    model_service = StubVisionService()
    result = ImageQualityReviewService(
        Path(__file__).resolve().parents[1],
        model_service,
    ).review_experiment(manifest, model="vision")

    assert result["human_decision_required"] is True
    assert result["reviews"][0]["prefilter_pass"] is True
    assert result["reviews"][0]["weighted_mean"] == 3.417
    assert model_service.image_count == 3
    assert result["reviews"][0]["input_hashes"]["pose"]
    assert result["reviews"][0]["runtime_evidence"]["digest"] == "sha256:test"
    assert result["status"] == "COMPLETE"
    assert Path(result["output_path"]).is_file()
    cached_reference = next((tmp_path / "review_inputs").glob("reference-*.jpg"))
    assert max(Image.open(cached_reference).size) == 768
