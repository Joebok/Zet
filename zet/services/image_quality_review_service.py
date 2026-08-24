from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import time
from typing import Any

from PIL import Image, ImageOps

from zet.services.ollama_model_service import OllamaModelService


class ImageQualityReviewError(ValueError):
    pass


class ImageQualityReviewService:
    """Prefilter Recipe Lab candidates with a local vision model."""

    def __init__(
        self,
        project_root: str | Path,
        model_service: OllamaModelService | None = None,
    ):
        self.project_root = Path(project_root).resolve()
        self.model_service = model_service or OllamaModelService(timeout_seconds=600)

    def _rubric(self) -> dict[str, Any]:
        path = self.project_root / "Config" / "Image_Quality_Rubric.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ImageQualityReviewError(f"Image quality rubric must be a JSON object: {path}")
        return value

    @staticmethod
    def _schema(rubric: dict[str, Any]) -> dict[str, Any]:
        gate_ids = [item["id"] for item in rubric["hard_gates"]]
        dimension_ids = [item["id"] for item in rubric["dimensions"]]
        return {
            "type": "object",
            "properties": {
                "hard_gates": {
                    "type": "object",
                    "properties": {key: {"type": "boolean"} for key in gate_ids},
                    "required": gate_ids,
                },
                "scores": {
                    "type": "object",
                    "properties": {
                        key: {"type": "integer", "minimum": 0, "maximum": 4}
                        for key in dimension_ids
                    },
                    "required": dimension_ids,
                },
                "failure_reasons": {
                    "type": "array",
                    "items": {"type": "string", "enum": rubric["failure_reasons"]},
                },
                "evidence": {"type": "string"},
            },
            "required": ["hard_gates", "scores", "failure_reasons", "evidence"],
        }

    @staticmethod
    def _weighted_mean(scores: dict[str, int], rubric: dict[str, Any]) -> float:
        weighted = sum(scores[item["id"]] * item["weight"] for item in rubric["dimensions"])
        weights = sum(item["weight"] for item in rubric["dimensions"])
        return round(weighted / weights, 3)

    @staticmethod
    def _prefilter_pass(review: dict[str, Any], rubric: dict[str, Any]) -> bool:
        acceptance = rubric["candidate_acceptance"]
        if acceptance["all_hard_gates_must_pass"] and not all(review["hard_gates"].values()):
            return False
        scores = review["scores"]
        return (
            scores["identity_fidelity"] >= acceptance["minimum_identity_fidelity"]
            and scores["costume_fidelity"] >= acceptance["minimum_costume_fidelity"]
            and review["weighted_mean"] >= acceptance["minimum_weighted_mean"]
        )

    @staticmethod
    def _review_image(source: Path, cache_dir: Path, max_side: int = 768) -> Path:
        cache_dir.mkdir(parents=True, exist_ok=True)
        output = cache_dir / f"{source.stem}.jpg"
        with Image.open(source) as image:
            resized = ImageOps.contain(image.convert("RGB"), (max_side, max_side))
        resized.save(output, quality=88, optimize=True)
        return output

    def review_experiment(self, manifest_path: str | Path, *, model: str) -> dict[str, Any]:
        path = Path(manifest_path).expanduser().resolve()
        experiment = json.loads(path.read_text(encoding="utf-8"))
        candidates = experiment.get("candidates")
        if not isinstance(candidates, list) or not candidates:
            raise ImageQualityReviewError("Recipe Lab experiment contains no candidates.")
        reference = Path(str(experiment.get("reference_image") or "")).resolve()
        if not reference.is_file():
            raise ImageQualityReviewError(f"Experiment reference image not found: {reference}")
        rubric = self._rubric()
        schema = self._schema(rubric)
        output = path.parent / "automatic_review.json"
        cached_reviews: dict[str, dict[str, Any]] = {}
        if output.is_file():
            existing = json.loads(output.read_text(encoding="utf-8"))
            if existing.get("experiment") == str(path) and existing.get("model") == model:
                cached_reviews = {
                    item["candidate_id"]: item
                    for item in existing.get("reviews", [])
                    if isinstance(item, dict) and item.get("candidate_id")
                }
        system = (
            "You are a strict visual QA prefilter. Compare the canonical reference (Image 1) "
            "with the generated candidate (Image 2). Judge only visible evidence. "
            "Do not infer whether the user likes the image and do not suggest prompt edits."
        )
        prompt = (
            "Score each supplied rubric dimension from 0 to 4 and evaluate every hard gate. "
            "Identity and costume fidelity compare Image 2 with Image 1. Technical quality and "
            "composition judge Image 2 itself. Use only the allowed failure reasons.\n\n"
            + json.dumps({
                "hard_gates": rubric["hard_gates"],
                "dimensions": rubric["dimensions"],
                "score_scale": rubric["score_scale"],
                "failure_reasons": rubric["failure_reasons"],
            }, ensure_ascii=False)
        )
        cache_dir = path.parent / "review_inputs"
        review_reference = self._review_image(reference, cache_dir, max_side=768)
        reviews = []
        for candidate in candidates:
            candidate_id = candidate["candidate_id"]
            if candidate_id in cached_reviews:
                reviews.append(cached_reviews[candidate_id])
                continue
            image_path = Path(str(candidate.get("image_path") or "")).resolve()
            if not image_path.is_file():
                raise ImageQualityReviewError(f"Candidate image not found: {image_path}")
            review_image = self._review_image(image_path, cache_dir, max_side=768)
            started = time.perf_counter()
            response = self.model_service.generate_json(
                model,
                system,
                prompt,
                schema,
                images=[review_reference, review_image],
            )
            weighted_mean = self._weighted_mean(response["scores"], rubric)
            review = {
                "candidate_id": candidate_id,
                **response,
                "weighted_mean": weighted_mean,
                "elapsed_seconds": round(time.perf_counter() - started, 3),
            }
            review["prefilter_pass"] = self._prefilter_pass(review, rubric)
            reviews.append(review)
            partial = {
                "schema_version": 1,
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "status": "RUNNING",
                "model": model,
                "experiment": str(path),
                "rubric": str((self.project_root / "Config" / "Image_Quality_Rubric.json").resolve()),
                "human_decision_required": True,
                "reviews": reviews,
            }
            output.write_text(json.dumps(partial, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        result = {
            "schema_version": 1,
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "status": "COMPLETE",
            "model": model,
            "experiment": str(path),
            "rubric": str((self.project_root / "Config" / "Image_Quality_Rubric.json").resolve()),
            "human_decision_required": True,
            "reviews": reviews,
        }
        output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return {**result, "output_path": str(output)}
