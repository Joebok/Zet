"""Authoring and image ownership for narrative scenes, independent of Scene Builder."""
from dataclasses import asdict
from pathlib import Path

from zet.models.narrative import NarrativeElement, NarrativeScene, NarrativeStory, NarrativeTarget
from zet.repositories.narrative_repository import NarrativeRepository
from zet.services.entity_library_service import EntityLibraryServiceError
from zet.services.narrative_interview_service import FIELD_PURPOSES, MOMENT_FIELDS, VISUAL_FIELDS
from zet.services.universe_style_service import universe_style


TARGET_FIELDS = ("title", "narrative", "staging", "physical_context", "framing", "width", "height",
                 "use_transparent_background",
                 "element_ids", "visual_overrides", "prompt", "interview_model", "prompt_model", "layers", "assembly_mode",
                 "backdrop_adaptation")
SCENE_FIELDS = ("title", "intent", *VISUAL_FIELDS, "canvas", "use_universe_style")


class ProtectedNarrativeImages(ValueError):
    def __init__(self, images: list[dict]):
        super().__init__("Confirm deletion of the selected or locked images.")
        self.images = images


class NarrativeSceneService:
    def __init__(self, zet_app):
        self.app = zet_app
        self.repository = NarrativeRepository(zet_app.config.base_library_path)
        self.repository.usage_provider = lambda: getattr(self.app, "entity_library_service", None)

    def persist(self, record, story: str, scene: str = "", target: str = "") -> dict:
        return self.repository.write(record, story, scene, target)

    def stories(self) -> list[dict]:
        with self.repository.lock():
            stories = self.repository.stories()
            for story in stories:
                story["scenes"] = []
                for scene_id in story["scene_ids"]:
                    scene = self.repository.read(story["id"], scene_id)
                    assembly = next((target for target in self.list_targets(story["id"], scene_id)
                                     if target["kind"] == "assembly"), None)
                    story["scenes"].append({"id": scene_id, "title": scene["title"],
                                            "final_assembly": {"target_id": assembly["id"],
                                                               "candidate_id": assembly["selected_id"]}
                                            if assembly and assembly["selected_id"] else None})
            return stories

    def create_story(self, data: dict) -> dict:
        with self.repository.lock():
            record = NarrativeStory(self._title(data), brief=str(data.get("brief") or ""))
            return self.persist(record, record.id)

    def story(self, story: str) -> dict:
        record = self.repository.read(story)
        return {**record, "scenes": [self.repository.read(story, item) for item in record["scene_ids"]]}

    def update_story(self, story: str, data: dict) -> dict:
        with self.repository.lock():
            record = self.repository.read(story)
            self._patch(record, data, ("title", "brief"))
            return self.persist(record, story)

    def create_scene(self, story: str, data: dict) -> dict:
        with self.repository.lock():
            parent = self.repository.read(story)
            record = asdict(NarrativeScene(self._title(data)))
            self._patch(record, data, SCENE_FIELDS)
            self.persist(record, story, record["id"])
            parent["scene_ids"].append(record["id"])
            self.persist(parent, story)
            return record

    def scene(self, story: str, scene: str) -> dict:
        record = self.repository.read(story, scene)
        record["elements"] = [self.element_detail(element) for element in record["elements"]]
        return {**record, "targets": self.list_targets(story, scene), "field_purposes": FIELD_PURPOSES,
                "universe_style": universe_style(self.app.config.base_library_path)}

    def element_asset(self, element: dict) -> dict | None:
        if element.get("reference_key"):
            try:
                asset = self.app.entity_library_service.resolve_reference(element["reference_key"])
            except EntityLibraryServiceError as exc:
                raise ValueError(str(exc)) from exc
            return self.library_asset(asset["asset_id"])
        if element.get("asset_id"):
            return self.library_asset(element["asset_id"])
        return None

    def element_detail(self, value: dict) -> dict:
        element = {**value, "reference_key": value.get("reference_key", "")}
        try:
            asset = self.element_asset(element)
            if asset:
                element["reference"] = {"asset_id": asset["asset_id"], "label": asset.get("label") or element["name"]}
        except (KeyError, ValueError, FileNotFoundError) as exc:
            element["reference_error"] = str(exc)
        return element

    def list_targets(self, story: str, scene: str) -> list[dict]:
        record = self.repository.read(story, scene)
        targets = [self.repository.read(story, scene, item) for item in record["target_ids"]]
        targets.sort(key=lambda item: item["kind"] != "backdrop")
        return [{key: item[key] for key in ("id", "title", "kind", "selected_id")} for item in targets]

    def update_scene(self, story: str, scene: str, data: dict) -> dict:
        with self.repository.lock():
            record = self.repository.read(story, scene)
            self._patch(record, data, SCENE_FIELDS)
            return self.persist(record, story, scene)

    def save_element(self, story: str, scene: str, data: dict, element_id: str = "") -> dict:
        with self.repository.lock():
            record = self.repository.read(story, scene)
            if element_id:
                element = next((item for item in record["elements"] if item["id"] == element_id), None)
                if element is None:
                    raise KeyError("Element not found.")
            else:
                element = asdict(NarrativeElement(str(data.get("name") or "New element")))
                record["elements"].append(element)
            element.setdefault("reference_key", "")
            previous_binding = (element.get("asset_id"), element.get("reference_key"))
            self._patch(element, data, ("name", "kind", "asset_id", "reference_key", "appearance", "reference_role"))
            if not element["name"].strip() or element["kind"] not in {"subject", "prop", "environment"}:
                raise ValueError("An element needs a name and subject, prop, or environment type.")
            if element["asset_id"] and element["reference_key"]:
                raise ValueError("Choose either a library asset or a logical reference.")
            # Unavailable logical bindings are retained in editable migration stubs.
            if element["asset_id"] and (not element_id or previous_binding != (element["asset_id"], element["reference_key"])):
                self.library_asset(element["asset_id"])
            self.persist(record, story, scene)
            return element

    def delete_element(self, story: str, scene: str, element_id: str) -> None:
        with self.repository.lock():
            record = self.repository.read(story, scene)
            if not any(item["id"] == element_id for item in record["elements"]):
                raise KeyError("Element not found.")
            for target_id in record["target_ids"]:
                target = self.repository.read(story, scene, target_id)
                target["element_ids"] = [item for item in target["element_ids"] if item != element_id]
                self.persist(target, story, scene, target_id)
            record["elements"] = [item for item in record["elements"] if item["id"] != element_id]
            self.persist(record, story, scene)

    def create_target(self, story: str, scene: str, data: dict) -> dict:
        with self.repository.lock():
            parent = self.repository.read(story, scene)
            kind = data.get("kind", "subscene")
            if kind not in {"subscene", "backdrop", "assembly"}:
                raise ValueError("Choose subscene, backdrop or assembly.")
            if kind == "assembly":
                existing_id = next((target_id for target_id in parent["target_ids"]
                                    if self.repository.read(story, scene, target_id)["kind"] == "assembly"), None)
                if existing_id:
                    return self.repository.read(story, scene, existing_id)
            record = NarrativeTarget(self._title(data), kind)
            if kind == "backdrop":
                record.width, record.height, record.framing = 1344, 768, "Wide environment"
            elif kind == "assembly":
                record.width, record.height, record.framing = 1344, 768, "Final scene"
                record.narrative = parent["intent"]
            record = asdict(record)
            if kind == "assembly":
                record["assembly_mode"] = "harmonize_composite"
            self._patch(record, data, TARGET_FIELDS)
            self._validate_target(record, parent)
            if kind == "assembly":
                record["layers"] = self.app.narrative_assembly_service.bind_layers(story, scene, record, [])
                if record["prompt"]:
                    record["prompt_provenance"] = {"assembly_mode": record["assembly_mode"], "edited": True}
            self.persist(record, story, scene, record["id"])
            parent["target_ids"].append(record["id"])
            self.persist(parent, story, scene)
            return record

    def update_target(self, story: str, scene: str, target: str, data: dict) -> dict:
        with self.repository.lock():
            record = self.repository.read(story, scene, target)
            previous_layers = record["layers"]
            previous_prompt = record["prompt"]
            self._patch(record, data, TARGET_FIELDS)
            self._validate_target(record, self.repository.read(story, scene))
            if record["kind"] == "assembly" and "layers" in data:
                record["layers"] = self.app.narrative_assembly_service.bind_layers(story, scene, record, previous_layers)
            if record["prompt"] != previous_prompt:
                record["prompt_provenance"] = {**record["prompt_provenance"], "edited": True}
                if record["kind"] == "assembly":
                    record["prompt_provenance"]["assembly_mode"] = record["assembly_mode"]
            history_id = data.get("use_prompt_job")
            if history_id:
                job = record["jobs"].get(history_id, {})
                if job.get("kind") not in {"synthesize", "generate"} or not isinstance(job.get("result"), str):
                    raise ValueError("Choose a completed prompt output.")
                record["prompt"] = job["result"]
                record["prompt_provenance"] = {**job.get("provenance", {}), "job_id": history_id, "edited": False}
                if record["kind"] == "assembly":
                    record["assembly_mode"] = job["detail"].get("assembly_mode", "finish_composite")
                    record["prompt_provenance"]["assembly_mode"] = record["assembly_mode"]
                record["active_llm_job"] = None
            return self.persist(record, story, scene, target)

    @staticmethod
    def _validate_target(record, parent):
        from zet.services.narrative_reference_service import NarrativeReferenceService
        NarrativeReferenceService.validate_adaptation(record)
        if not isinstance(record["use_transparent_background"], bool):
            raise ValueError("Use transparent background must be a boolean.")
        if record["assembly_mode"] not in ("finish_composite", "assemble_references", "harmonize_composite"):
            raise ValueError("Choose finish_composite, assemble_references or harmonize_composite.")
        if record["kind"] != "assembly" and record["assembly_mode"] != "finish_composite":
            raise ValueError("Only final assemblies have an assembly mode.")
        for key in ("width", "height"):
            value = record[key]
            if isinstance(value, bool) or not isinstance(value, int) or not 256 <= value <= 4096 or value % 32:
                raise ValueError("Image dimensions must be multiples of 32 between 256 and 4096.")
        available = {element["id"] for element in parent["elements"]}
        if not isinstance(record["element_ids"], list) or any(not isinstance(item, str) or item not in available for item in record["element_ids"]):
            raise ValueError("Assign elements from this scene.")
        record["element_ids"] = list(dict.fromkeys(record["element_ids"]))
        overrides = record["visual_overrides"]
        if not isinstance(overrides, dict) or any(key not in VISUAL_FIELDS or not isinstance(value, str) for key, value in overrides.items()):
            raise ValueError("Visual overrides must contain scene visual fields as text.")
        for key in ("interview_model", "prompt_model"):
            value = record[key]
            if not isinstance(value, str) or len(value) > 200 or any(char.isspace() for char in value):
                raise ValueError("Model identifiers must be text without whitespace.")
            if value == "codex:":
                raise ValueError("Enter a Codex model after codex:.")
        if not isinstance(record["layers"], list) or len(record["layers"]) > 32:
            raise ValueError("Choose up to 32 source layers.")
        if record["kind"] != "assembly" and record["layers"]:
            raise ValueError("Only final assemblies have source layers.")

    def target(self, story: str, scene: str, target: str) -> dict:
        record = self.repository.read(story, scene, target)
        parent = self.repository.read(story, scene)
        by_id = {item["id"]: item for item in parent["elements"]}
        elements = []
        for element_id in record["element_ids"]:
            element = self.element_detail(by_id[element_id])
            elements.append(element)
        inherited = {key: parent[key] for key in VISUAL_FIELDS}
        style = universe_style(self.app.config.base_library_path) if parent.get("use_universe_style") else None
        if style is not None:
            inherited["style"] = style["text"]
        effective = {key: record["visual_overrides"].get(key) or value for key, value in inherited.items()}
        detail = {**record, "elements": elements, "inherited_context": inherited, "context": effective,
                  "style_source": ("target override" if record["visual_overrides"].get("style") else
                                   "universe" if style is not None else "saved scene"),
                  "universe_style": style,
                  "field_purposes": FIELD_PURPOSES,
                  "scene_title": parent["title"], "effective_models": {
                      key: record[key] or self.app.config.ai_narrative_scene_model
                      for key in ("interview_model", "prompt_model")}}
        if record["kind"] == "assembly":
            detail["assembly_sources"] = self.app.narrative_assembly_service.sources(story, scene)
            detail["source_groups"] = [{"title": layer["label"], "narrative": layer.get("narrative", ""),
                                        "role": layer["role"]} for layer in record["layers"] if layer["visible"]]
        return detail

    def apply_interview(self, story: str, scene: str, target: str, data: dict) -> dict:
        """Apply selected server-owned replacements, preserving unrelated current fields."""
        with self.repository.lock():
            record = self.repository.read(story, scene, target)
            job = record["jobs"].get(data.get("job_id", ""), {})
            review = job.get("review", {})
            if job.get("kind") != "interview" or job.get("status") != "COMPLETE":
                raise ValueError("Choose a completed interview review.")
            if review.get("status") == "applied":
                return self.target(story, scene, target)
            if review.get("status") != "pending":
                raise ValueError("This interview has no pending review.")
            choices = data.get("choices")
            rows = review["proposals"]
            if not isinstance(choices, dict) or set(choices) != {row["id"] for row in rows}:
                raise ValueError("Choose an action for every proposal.")
            parent = self.repository.read(story, scene)
            elements = {item["id"]: item for item in parent["elements"]}
            scene_changed = False
            for row in rows:
                choice = choices[row["id"]]
                allowed = ("override", "shared", "reject") if row["scope"] == "visual" else ("accept", "reject")
                if choice not in allowed:
                    raise ValueError("Choose a valid proposal action.")
                if choice == "reject":
                    continue
                key = row["field"]
                if row["scope"] == "moment" and key in MOMENT_FIELDS:
                    record[key] = row["text"]
                elif row["scope"] == "appearance" and key == "appearance":
                    if row["element_id"] not in record["element_ids"] or row["element_id"] not in elements:
                        raise ValueError("A proposed element is no longer assigned to this target.")
                    elements[row["element_id"]]["appearance"] = row["text"]
                    scene_changed = True
                elif row["scope"] == "visual" and key in VISUAL_FIELDS:
                    if choice == "shared":
                        parent[key] = row["text"]
                        if key == "style":
                            parent["use_universe_style"] = False
                        record["visual_overrides"].pop(key, None)
                        scene_changed = True
                    else:
                        record["visual_overrides"][key] = row["text"]
                else:
                    raise ValueError("The proposal is outside interview editing authority.")
            self._validate_target(record, parent)
            # Validate every choice before writing either file. If a write fails, retrying
            # applies the same replacements; per-file atomic writes are not a transaction.
            if scene_changed:
                self.persist(parent, story, scene)
            review.update(status="applied", choices=choices)
            self.persist(record, story, scene, target)
            return self.target(story, scene, target)

    def references(self, detail: dict) -> list[dict]:
        refs = []
        snapshot = detail.get("source_snapshot") or {}
        if detail["kind"] == "backdrop" and snapshot.get("image_file"):
            path = self.app.narrative_reference_service.image(snapshot["destination_story_id"],
                                                             snapshot["destination_scene_id"], detail["id"])
            refs.append({"path": str(path), "label": snapshot["title"], "role": "backdrop source", "image_index": 1})
        for element in detail["elements"]:
            asset = self.element_asset(element)
            if asset:
                refs.append({"path": asset["image_path"], "asset_id": asset["asset_id"],
                             "reference_key": element.get("reference_key", ""),
                             "label": element["name"], "role": element["reference_role"], "image_index": len(refs) + 1})
        if len(refs) > 10:
            raise ValueError("The renderer accepts up to ten reference images.")
        return refs

    def library_asset(self, asset_id: str) -> dict:
        try:
            asset = self.app.entity_library_service.image_binding(asset_id)
        except EntityLibraryServiceError as exc:
            raise ValueError(str(exc)) from exc
        if not Path(asset["image_path"]).is_file():
            raise FileNotFoundError("Reference image is unavailable.")
        return asset

    def library_options(self, query: str = "") -> list[dict]:
        library = self.app.entity_library_service
        assets = library.search_picker(q=query)
        keys = {}
        for reference in library.list_logical_references():
            if reference["status"] == "active" and "costume-dressing" in reference["reference_key"]:
                keys.setdefault(reference["asset_id"], []).append(reference["reference_key"])
        return [{"asset_id": item["asset_id"], "label": item.get("label") or item["file_name"],
                 "reference_key": keys[item["asset_id"]][0] if len(keys.get(item["asset_id"], [])) == 1 else "",
                 "entities": item.get("entities", [])} for item in assets[:100]]

    def protected_images(self, story: str, scene: str = "", target: str = "") -> list[dict]:
        if not scene:
            parent = self.repository.read(story)
            return [image for item in parent["scene_ids"] for image in self.protected_images(story, item)]
        if not target:
            parent = self.repository.read(story, scene)
            return [image for item in parent["target_ids"] for image in self.protected_images(story, scene, item)]
        record = self.repository.read(story, scene, target)
        return [{"id": candidate["id"], "label": f"{record['title']} · slot {candidate['slot']}"}
                for candidate in record["candidates"].values()
                if candidate["locked"] or record["selected_id"] == candidate["id"]]

    @staticmethod
    def confirm(images: list[dict], confirmed: list[str]) -> None:
        if images and set(confirmed) != {item["id"] for item in images}:
            raise ProtectedNarrativeImages(images)

    def delete(self, story: str, scene: str = "", target: str = "", confirmed: list[str] | None = None) -> None:
        with self.repository.lock():
            self.confirm(self.protected_images(story, scene, target), confirmed or [])
            with self.app.entity_library_service.image_usages.mutation(
                    self.repository.folder(story, scene, target), tree=True):
                self.repository.delete(story, scene, target)
            if target:
                parent = self.repository.read(story, scene)
                parent["target_ids"].remove(target)
                self.persist(parent, story, scene)
            elif scene:
                parent = self.repository.read(story)
                parent["scene_ids"].remove(scene)
                self.persist(parent, story)

    def legacy_location(self, story_slug: str, scene_slug: str = "") -> dict:
        for story in self.repository.stories():
            if story.get("source_provenance", {}).get("story_slug") != story_slug:
                continue
            if not scene_slug:
                return {"story_id": story["id"]}
            for scene_id in story["scene_ids"]:
                scene = self.repository.read(story["id"], scene_id)
                if scene.get("migration", {}).get("scene_slug") == scene_slug:
                    return {"story_id": story["id"], "scene_id": scene_id}
        raise KeyError("This legacy story or scene has not been migrated.")

    def legacy_image(self, story: str, scene: str) -> dict:
        binding = self.repository.read(story, scene).get("legacy_image") or {}
        if not binding.get("asset_id"):
            raise KeyError("This scene has no legacy image.")
        return self.library_asset(binding["asset_id"])

    def finished_sources(self, story: str = "") -> list[dict]:
        """Selected final assemblies for discovery/print; legacy images stay separate."""
        result = []
        parents = [self.repository.read(story)] if story else self.repository.stories()
        for parent in parents:
            for scene_id in parent["scene_ids"]:
                scene = self.repository.read(parent["id"], scene_id)
                for target_id in scene["target_ids"]:
                    target = self.repository.read(parent["id"], scene_id, target_id)
                    candidate = target.get("candidates", {}).get(target.get("selected_id"))
                    if target["kind"] != "assembly" or not candidate or not candidate.get("image"):
                        continue
                    path = self.repository.folder(parent["id"], scene_id, target_id) / candidate["image"]
                    if path.is_file():
                        result.append({"story_id": parent["id"], "scene_id": scene_id, "target_id": target_id,
                            "candidate_id": candidate["id"], "title": scene["title"], "image_path": str(path),
                            "locked": candidate.get("locked", False),
                            "tag": f"{{{{NARRATIVE:{parent['id']}:{scene_id}:{target_id}:{candidate['id']}}}}}"})
        return result

    @staticmethod
    def _title(data: dict) -> str:
        title = str(data.get("title") or "").strip()
        if not title:
            raise ValueError("A title is required.")
        return title

    @staticmethod
    def _patch(record: dict, data: dict, fields) -> None:
        for key in fields:
            if key in data:
                value = data[key]
                if isinstance(record[key], bool) and not isinstance(value, bool):
                    raise ValueError(f"{key} must be a boolean.")
                if isinstance(record[key], str) and not isinstance(value, str):
                    raise ValueError(f"{key} must be text.")
                if key == "title" and not str(value).strip():
                    raise ValueError("A title is required.")
                record[key] = value
