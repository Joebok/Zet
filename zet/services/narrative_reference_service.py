"""Pinned backdrop images and independent subscene imports for Narrative scenes."""
# Input validation uses ValueError to match the Narrative router's HTTP 400 contract.
# ruff: noqa: TRY004
import hashlib
import math
import shutil
from copy import deepcopy
from dataclasses import asdict
from io import BytesIO

from PIL import Image, ImageOps

from zet.models.narrative import NarrativeCandidate, NarrativeTarget, new_id
from zet.services.atomic_file_service import write_bytes_atomic
from zet.services.narrative_scene_service import VISUAL_FIELDS
from zet.services.workflow_storage import validate_image

INPUT_FIELDS = ("narrative", "staging", "physical_context", "framing", "width", "height")


class NarrativeReferenceService:
    def __init__(self, author):
        self.author = author
        self.repository = author.repository

    def sources(self, kind):
        if kind not in {"backdrop", "subscene"}:
            raise ValueError("Choose backdrop or subscene sources.")
        with self.repository.lock():
            result = []
            for story in self.repository.stories():
                for scene_id in story["scene_ids"]:
                    scene = self.repository.read(story["id"], scene_id)
                    for target_id in scene["target_ids"]:
                        target = self.repository.read(story["id"], scene_id, target_id)
                        if target["kind"] != kind:
                            continue
                        candidates = []
                        for candidate in target["candidates"].values():
                            if candidate["status"] == "COMPLETE" and candidate["image"]:
                                path = self._file(story["id"], scene_id, target_id, candidate["image"])
                                if path.is_file():
                                    candidates.append({"id": candidate["id"], "slot": candidate["slot"]})
                        result.append({"story_id": story["id"], "story_title": story["title"],
                                       "scene_id": scene_id, "scene_title": scene["title"],
                                       "target_id": target_id, "title": target["title"], "kind": kind,
                                       "selected_id": target["selected_id"], "candidates": candidates})
            return result

    def _file(self, story, scene, target, relative):
        folder = self.repository.folder(story, scene, target).resolve()
        if not isinstance(relative, str) or not relative:
            raise ValueError("Source image is unavailable.")
        path = (folder / relative).resolve()
        if not path.is_relative_to(folder) or path == folder:
            raise ValueError("Image must stay inside its narrative target.")
        return path

    def preview(self, source):
        with self.repository.lock():
            if not isinstance(source, dict):
                raise ValueError("Choose a source using story, scene and target IDs.")
            story, scene, target = (source.get(key, "") for key in ("story_id", "scene_id", "target_id"))
            if not all(isinstance(value, str) and value for value in (story, scene, target)):
                raise ValueError("Choose a source story, scene and target.")
            if source.get("candidate_id") is not None and not isinstance(source["candidate_id"], str):
                raise ValueError("Choose a candidate by its ID.")
            story_record = self.repository.read(story)
            scene_record = self.repository.read(story, scene)
            if scene not in story_record["scene_ids"] or target not in scene_record["target_ids"]:
                raise ValueError("Source does not belong to the chosen scene.")
            detail = self.author.target(story, scene, target)
            if detail["kind"] not in {"backdrop", "subscene"}:
                raise ValueError("Choose a backdrop or subscene.")
            candidate_id = source.get("candidate_id") or detail["selected_id"]
            candidate = detail["candidates"].get(candidate_id, {})
            if candidate_id and (not candidate or candidate["status"] != "COMPLETE" or not candidate["image"]):
                raise ValueError("Choose a completed source candidate.")
            parent = next((job for job in reversed(list(detail["jobs"].values()))
                           if candidate_id and candidate_id in job.get("candidate_ids", [])), {})
            inputs = parent.get("detail")
            prompt = candidate.get("prompt") or (parent.get("result") if isinstance(parent.get("result"), str) else "")
            generation_inputs = ({key: deepcopy(inputs[key]) for key in (*INPUT_FIELDS, "context", "elements", "backdrop_adaptation") if key in inputs}
                                 if isinstance(inputs, dict) else None)
            # Locally reused/cropped candidates have no generation job of their own.
            if generation_inputs is None and candidate.get("source_snapshot"):
                generation_inputs = deepcopy(candidate["source_snapshot"].get("generation_inputs"))
            return {"story_id": story, "scene_id": scene, "target_id": target, "candidate_id": candidate_id,
                    "story_title": story_record["title"], "scene_title": scene_record["title"],
                    "title": detail["title"], "kind": detail["kind"], "prompt": prompt or "",
                    "prompt_provenance": deepcopy(candidate.get("prompt_provenance", {})),
                    "generation_inputs": generation_inputs,
                    "current_inputs": {key: deepcopy(detail[key]) for key in (*INPUT_FIELDS, "context", "elements", "backdrop_adaptation", "prompt")}}

    def _pin(self, story, scene, target, source):
        snapshot = self.preview(source)
        if snapshot["kind"] != "backdrop" or not snapshot["candidate_id"]:
            raise ValueError("Choose a completed backdrop image explicitly when there is no selection.")
        if (story, scene, target) == tuple(snapshot[key] for key in ("story_id", "scene_id", "target_id")):
            raise ValueError("Choose a different source backdrop.")
        original = self.repository.read(snapshot["story_id"], snapshot["scene_id"], snapshot["target_id"])
        candidate = original["candidates"][snapshot["candidate_id"]]
        payload = self._file(snapshot["story_id"], snapshot["scene_id"], snapshot["target_id"], candidate["image"]).read_bytes()
        validate_image(payload)
        with Image.open(BytesIO(payload)) as image:
            image = ImageOps.exif_transpose(image)
            snapshot["image_width"], snapshot["image_height"] = image.size
        snapshot["image_sha256"] = hashlib.sha256(payload).hexdigest()
        snapshot["snapshot_id"] = new_id()
        snapshot["destination_story_id"], snapshot["destination_scene_id"] = story, scene
        snapshot["image_file"] = f"sources/{snapshot['snapshot_id']}/image.png"
        write_bytes_atomic(self.repository.folder(story, scene, target) / snapshot["image_file"], payload)
        return snapshot

    def create(self, story, scene, data):
        """Validate first; publish the target and its new elements together under the workflow lock."""
        with self.repository.lock():
            parent = self.repository.read(story, scene)
            source = self.preview(data.get("source", {}))
            kind = source["kind"]
            record = asdict(NarrativeTarget(self.author._title({"title": data.get("title") or source["title"]}), kind))
            for key in INPUT_FIELDS:
                record[key] = deepcopy(source["current_inputs"][key])
            if data.get("copy_visual_context", False):
                record["visual_overrides"] = deepcopy(source["current_inputs"]["context"])
            mappings = data.get("element_mappings", {})
            if not isinstance(mappings, dict):
                raise ValueError("Element mappings must be an object.")
            available = {item["id"] for item in parent["elements"]}
            source_elements = source["current_inputs"]["elements"]
            if any(key not in {item["id"] for item in source_elements} for key in mappings):
                raise ValueError("Map only source elements.")
            for element in source_elements:
                mapped = mappings.get(element["id"])
                if mapped is not None and not isinstance(mapped, str):
                    raise ValueError("Element mappings must contain destination IDs or blank values.")
                if mapped:
                    if mapped not in available:
                        raise ValueError("Map to an element in the destination scene.")
                    identifier = mapped
                else:
                    copied = {key: deepcopy(element[key]) for key in
                              ("name", "kind", "asset_id", "appearance", "reference_role")}
                    copied["id"] = identifier = new_id()
                    parent["elements"].append(copied)
                record["element_ids"].append(identifier)
            self.author._validate_target(record, parent)
            folder = self.repository.folder(story, scene, record["id"])
            try:
                record["source_snapshot"] = self._pin(story, scene, record["id"], data["source"]) if kind == "backdrop" else source
                self.repository.write(record, story, scene, record["id"])
                parent["target_ids"].append(record["id"])
                self.repository.write(parent, story, scene)
            except Exception:
                if folder.is_dir() and folder.resolve().is_relative_to(self.repository.root):
                    shutil.rmtree(folder)
                raise
            return self.author.target(story, scene, record["id"])

    def backdrop_action(self, story, scene, target, data):
        with self.repository.lock():
            record = self.repository.read(story, scene, target)
            if record["kind"] != "backdrop":
                raise ValueError("Only backdrops can attach source images.")
            action = data.get("action")
            if action in {"attach", "refresh"}:
                source = data.get("source")
                if source is None and action == "refresh":
                    old = record["source_snapshot"]
                    source = {key: old.get(key, "") for key in ("story_id", "scene_id", "target_id")}
                record["source_snapshot"] = self._pin(story, scene, target, source or {})
            elif action == "copy_inputs":
                basis = data.get("basis", "current")
                if basis not in {"current", "generation"}:
                    raise ValueError("Choose current or generation inputs.")
                inputs = record["source_snapshot"].get(basis + "_inputs")
                if not inputs:
                    raise ValueError("Source inputs are not recorded.")
                for key in INPUT_FIELDS:
                    if key in inputs:
                        record[key] = deepcopy(inputs[key])
                record["visual_overrides"] = {key: value for key, value in inputs.get("context", {}).items() if key in VISUAL_FIELDS}
                self.author._validate_target(record, self.repository.read(story, scene))
                # An old text response must not overwrite this explicit replacement.
                record["active_llm_job"] = None
            elif action in {"reuse", "crop"}:
                self._local_candidate(story, scene, target, record, action)
            else:
                raise ValueError("Unknown backdrop reference action.")
            self.repository.write(record, story, scene, target)
            return self.author.target(story, scene, target)

    @staticmethod
    def validate_adaptation(record):
        settings = record["backdrop_adaptation"]
        if not isinstance(settings, dict):
            raise ValueError("Backdrop adaptation must be an object.")
        if settings and record["kind"] != "backdrop":
            raise ValueError("Only backdrops have adaptation settings.")
        operation = settings.get("operation", "edit")
        if not isinstance(operation, str) or operation not in {"edit", "expand", "viewpoint", "crop", "unchanged"}:
            raise ValueError("Choose an available backdrop operation.")
        if not isinstance(settings.get("direction", ""), str):
            raise ValueError("Adaptation direction must be text.")
        side = settings.get("expand_side", "right")
        if not isinstance(side, str) or side not in {"left", "right", "top", "bottom", "all"}:
            raise ValueError("Choose where to expand the backdrop.")
        crop = settings.get("crop", {})
        if not isinstance(crop, dict):
            raise ValueError("Crop settings must be an object.")
        for key, default, low, high in (("center_x", .5, 0, 1), ("center_y", .5, 0, 1), ("zoom", 1, 1, 20)):
            value = crop.get(key, default)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
                raise ValueError("Crop centers must be between 0 and 1; zoom must be between 1 and 20.")

    def image(self, story, scene, target):
        snapshot = self.repository.read(story, scene, target)["source_snapshot"]
        path = self._file(story, scene, target, snapshot.get("image_file"))
        if not path.is_file():
            raise FileNotFoundError("Pinned source image is unavailable.")
        return path

    def crop(self, story, scene, target, record=None):
        record = record or self.repository.read(story, scene, target)
        self.validate_adaptation(record)
        settings = record["backdrop_adaptation"].get("crop", {})
        with Image.open(self._file(story, scene, target, record["source_snapshot"].get("image_file"))) as source:
            source = ImageOps.exif_transpose(source).convert("RGBA")
            aspect = record["width"] / record["height"]
            width = min(source.width, source.height * aspect) / settings.get("zoom", 1)
            height = width / aspect
            x = min(source.width - width / 2, max(width / 2, settings.get("center_x", .5) * source.width))
            y = min(source.height - height / 2, max(height / 2, settings.get("center_y", .5) * source.height))
            box = (x - width / 2, y - height / 2, x + width / 2, y + height / 2)
            image = source.resize((record["width"], record["height"]), Image.Resampling.LANCZOS, box=box)
            stream = BytesIO()
            image.save(stream, format="PNG")
            return stream.getvalue()

    def _local_candidate(self, story, scene, target, record, action):
        if None not in record["slots"]:
            raise ValueError("Clear a slot before adding a reused or cropped backdrop.")
        payload = (self.crop(story, scene, target, record) if action == "crop" else
                   self._file(story, scene, target, record["source_snapshot"].get("image_file")).read_bytes())
        validate_image(payload)
        index = record["slots"].index(None)
        candidate = asdict(NarrativeCandidate(target, index + 1, 0, status="COMPLETE"))
        candidate.update(image=f"images/{candidate['id']}.png", prompt=record["source_snapshot"].get("prompt", ""),
                         prompt_provenance=deepcopy(record["source_snapshot"].get("prompt_provenance", {})),
                         source_snapshot=deepcopy(record["source_snapshot"]),
                         backdrop_adaptation={**deepcopy(record["backdrop_adaptation"]), "operation": "crop" if action == "crop" else "unchanged"})
        write_bytes_atomic(self.repository.folder(story, scene, target) / candidate["image"], payload)
        record["candidates"][candidate["id"]] = candidate
        record["slots"][index] = candidate["id"]
        if not record["selected_id"]:
            record["selected_id"] = candidate["id"]
