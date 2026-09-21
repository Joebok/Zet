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
                "uncertainty": {"type": "string"},
            },
            "required": ["hard_gates", "scores", "failure_reasons", "evidence"],
        }

    @classmethod
    def review_contract(cls, rubric: dict[str, Any]) -> tuple[str, str, dict[str, Any]]:
        system = (
            "You are a strict visual QA prefilter. Compare the canonical reference (Image 1) "
            "with the requested pose and generated candidate. Judge only visible evidence. "
            "Do not infer whether the user likes the image and do not suggest prompt edits."
        )
        prompt = (
            "Score each supplied rubric dimension from 0 to 4 and evaluate every hard gate. "
            "Image 1 is the appearance reference. Image 2 is the requested pose when supplied. "
            "The final image is the candidate. Identity and costume fidelity compare the candidate with Image 1; "
            "pose/orientation compares it with Image 2; composition and technical quality judge the candidate. "
            "Use only the allowed failure reasons and state uncertainty when evidence is ambiguous.\n\n"
            + json.dumps({
                "hard_gates": rubric["hard_gates"],
                "dimensions": rubric["dimensions"],
                "score_scale": rubric["score_scale"],
                "failure_reasons": rubric["failure_reasons"],
            }, ensure_ascii=False)
        )
        return system, prompt, cls._schema(rubric)

    @classmethod
    def finalize_review(
        cls,
        candidate_id: str,
        response: dict[str, Any],
        rubric: dict[str, Any],
        input_hashes: dict[str, str],
        *,
        runtime_evidence: dict[str, Any] | None = None,
        elapsed_seconds: float | None = None,
    ) -> dict[str, Any]:
        gate_ids = {item["id"] for item in rubric["hard_gates"]}
        dimension_ids = {item["id"] for item in rubric["dimensions"]}
        gates = response.get("hard_gates")
        scores = response.get("scores")
        if not isinstance(gates, dict) or not gate_ids.issubset(gates):
            raise ImageQualityReviewError("Automatic review response omitted required hard gates.")
        if not isinstance(scores, dict) or not dimension_ids.issubset(scores):
            raise ImageQualityReviewError("Automatic review response omitted required component scores.")
        review = {
            "candidate_id": candidate_id,
            **response,
            "runtime_evidence": runtime_evidence or {},
            "weighted_mean": cls._weighted_mean(scores, rubric),
            "uncertainty": str(response.get("uncertainty") or ""),
            "input_hashes": input_hashes,
        }
        if elapsed_seconds is not None:
            review["elapsed_seconds"] = round(float(elapsed_seconds), 3)
        review["prefilter_pass"] = cls._prefilter_pass(review, rubric)
        return review

    @staticmethod
    def _weighted_mean(scores: dict[str, int], rubric: dict[str, Any]) -> float:
        scored = [item for item in rubric["dimensions"] if item["id"] in scores]
        weighted = sum(scores[item["id"]] * item["weight"] for item in scored)
        weights = sum(item["weight"] for item in scored)
        return round(weighted / weights, 3) if weights else 0.0

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
        fingerprint = __import__("hashlib").sha256(source.read_bytes()).hexdigest()[:12]
        output = cache_dir / f"{source.stem}-{fingerprint}.jpg"
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
        pose_value = str(experiment.get("pose_image") or "").strip()
        pose = Path(pose_value).resolve() if pose_value else None
        if pose is not None and not pose.is_file():
            raise ImageQualityReviewError(f"Experiment pose image not found: {pose}")
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
        system, prompt, schema = self.review_contract(rubric)
        cache_dir = path.parent / "review_inputs"
        review_reference = self._review_image(reference, cache_dir, max_side=768)
        review_pose = self._review_image(pose, cache_dir, max_side=768) if pose is not None else None
        reviews = []
        appearance_hash = __import__("hashlib").sha256(reference.read_bytes()).hexdigest()
        pose_hash = __import__("hashlib").sha256(pose.read_bytes()).hexdigest() if pose else ""
        for candidate in candidates:
            candidate_id = candidate["candidate_id"]
            image_path = Path(str(candidate.get("image_path") or "")).resolve()
            if not image_path.is_file():
                raise ImageQualityReviewError(f"Candidate image not found: {image_path}")
            input_hashes = {
                "appearance": appearance_hash,
                "pose": pose_hash,
                "candidate": __import__("hashlib").sha256(image_path.read_bytes()).hexdigest(),
            }
            if candidate_id in cached_reviews and cached_reviews[candidate_id].get("input_hashes") == input_hashes:
                reviews.append(cached_reviews[candidate_id])
                continue
            review_image = self._review_image(image_path, cache_dir, max_side=768)
            started = time.perf_counter()
            if hasattr(self.model_service, "generate_json_with_evidence"):
                response, runtime_evidence = self.model_service.generate_json_with_evidence(
                    model, system, prompt, schema,
                    images=[review_reference, *([review_pose] if review_pose else []), review_image]
                )
            else:
                response = self.model_service.generate_json(
                    model, system, prompt, schema,
                    images=[review_reference, *([review_pose] if review_pose else []), review_image]
                )
                runtime_evidence = {}
            review = self.finalize_review(
                candidate_id,
                response,
                rubric,
                input_hashes,
                runtime_evidence=runtime_evidence,
                elapsed_seconds=time.perf_counter() - started,
            )
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
