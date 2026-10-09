"""Authoring and image ownership for narrative scenes, independent of Scene Builder."""
from dataclasses import asdict
from pathlib import Path

from zet.models.narrative import NarrativeElement, NarrativeScene, NarrativeStory, NarrativeTarget
from zet.repositories.narrative_repository import NarrativeRepository
from zet.services.entity_library_service import EntityLibraryServiceError


VISUAL_FIELDS = ("setting", "camera", "perspective", "lighting", "style")
TARGET_FIELDS = ("title", "narrative", "staging", "physical_context", "framing", "width", "height",
                 "element_ids", "visual_overrides", "prompt")
SCENE_FIELDS = ("title", "intent", *VISUAL_FIELDS, "canvas")


class ProtectedNarrativeImages(ValueError):
    def __init__(self, images: list[dict]):
        super().__init__("Confirm deletion of the selected or locked images.")
        self.images = images


class NarrativeSceneService:
    def __init__(self, zet_app):
        self.app = zet_app
        self.repository = NarrativeRepository(zet_app.config.base_library_path)

    def stories(self) -> list[dict]:
        return self.repository.stories()

    def create_story(self, data: dict) -> dict:
        with self.repository.lock():
            record = NarrativeStory(self._title(data), brief=str(data.get("brief") or ""))
            return self.repository.write(record, record.id)

    def story(self, story: str) -> dict:
        record = self.repository.read(story)
        return {**record, "scenes": [self.repository.read(story, item) for item in record["scene_ids"]]}

    def update_story(self, story: str, data: dict) -> dict:
        with self.repository.lock():
            record = self.repository.read(story)
            self._patch(record, data, ("title", "brief"))
            return self.repository.write(record, story)

    def create_scene(self, story: str, data: dict) -> dict:
        with self.repository.lock():
            parent = self.repository.read(story)
            record = asdict(NarrativeScene(self._title(data)))
            self._patch(record, data, SCENE_FIELDS)
            self.repository.write(record, story, record["id"])
            parent["scene_ids"].append(record["id"])
            self.repository.write(parent, story)
            return record

    def scene(self, story: str, scene: str) -> dict:
        record = self.repository.read(story, scene)
        return {**record, "targets": self.list_targets(story, scene)}

    def list_targets(self, story: str, scene: str) -> list[dict]:
        record = self.repository.read(story, scene)
        targets = [self.repository.read(story, scene, item) for item in record["target_ids"]]
        targets.sort(key=lambda item: item["kind"] != "backdrop")
        return [{key: item[key] for key in ("id", "title", "kind", "selected_id")} for item in targets]

    def update_scene(self, story: str, scene: str, data: dict) -> dict:
        with self.repository.lock():
            record = self.repository.read(story, scene)
            self._patch(record, data, SCENE_FIELDS)
            return self.repository.write(record, story, scene)

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
            self._patch(element, data, ("name", "kind", "asset_id", "appearance", "reference_role"))
            if not element["name"].strip() or element["kind"] not in {"subject", "prop", "environment"}:
                raise ValueError("An element needs a name and subject, prop, or environment type.")
            if element["asset_id"]:
                self.library_asset(element["asset_id"])
            self.repository.write(record, story, scene)
            return element

    def delete_element(self, story: str, scene: str, element_id: str) -> None:
        with self.repository.lock():
            record = self.repository.read(story, scene)
            if not any(item["id"] == element_id for item in record["elements"]):
                raise KeyError("Element not found.")
            for target_id in record["target_ids"]:
                target = self.repository.read(story, scene, target_id)
                target["element_ids"] = [item for item in target["element_ids"] if item != element_id]
                self.repository.write(target, story, scene, target_id)
            record["elements"] = [item for item in record["elements"] if item["id"] != element_id]
            self.repository.write(record, story, scene)

    def create_target(self, story: str, scene: str, data: dict) -> dict:
        with self.repository.lock():
            parent = self.repository.read(story, scene)
            kind = data.get("kind", "subscene")
            if kind not in {"subscene", "backdrop"}:
                raise ValueError("Choose subscene or backdrop.")
            record = NarrativeTarget(self._title(data), kind)
            if kind == "backdrop":
                record.width, record.height, record.framing = 1344, 768, "Wide environment"
            record = asdict(record)
            self._patch(record, data, TARGET_FIELDS)
            self._validate_target(record, parent)
            self.repository.write(record, story, scene, record["id"])
            parent["target_ids"].append(record["id"])
            self.repository.write(parent, story, scene)
            return record

    def update_target(self, story: str, scene: str, target: str, data: dict) -> dict:
        with self.repository.lock():
            record = self.repository.read(story, scene, target)
            self._patch(record, data, TARGET_FIELDS)
            self._validate_target(record, self.repository.read(story, scene))
            return self.repository.write(record, story, scene, target)

    @staticmethod
    def _validate_target(record, parent):
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

    def target(self, story: str, scene: str, target: str) -> dict:
        record = self.repository.read(story, scene, target)
        parent = self.repository.read(story, scene)
        by_id = {item["id"]: item for item in parent["elements"]}
        elements = []
        for element_id in record["element_ids"]:
            element = dict(by_id[element_id])
            if element["asset_id"]:
                try:
                    asset = self.library_asset(element["asset_id"])
                    element["reference"] = {"asset_id": asset["asset_id"], "label": asset.get("label") or element["name"]}
                except (KeyError, ValueError, FileNotFoundError) as exc:
                    element["reference_error"] = str(exc)
            elements.append(element)
        inherited = {key: parent[key] for key in VISUAL_FIELDS}
        effective = {key: record["visual_overrides"].get(key) or value for key, value in inherited.items()}
        return {**record, "elements": elements, "inherited_context": inherited, "context": effective,
                "scene_title": parent["title"]}

    def references(self, detail: dict) -> list[dict]:
        refs = []
        for element in detail["elements"]:
            if element["asset_id"]:
                asset = self.library_asset(element["asset_id"])
                refs.append({"path": asset["image_path"], "asset_id": element["asset_id"],
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
        assets = self.app.entity_library_service.list_assets(q=query)
        return [{"asset_id": item["asset_id"], "label": item.get("label") or item["file_name"],
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
            self.repository.delete(story, scene, target)
            if target:
                parent = self.repository.read(story, scene)
                parent["target_ids"].remove(target)
                self.repository.write(parent, story, scene)
            elif scene:
                parent = self.repository.read(story)
                parent["scene_ids"].remove(scene)
                self.repository.write(parent, story)

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
                if isinstance(record[key], str) and not isinstance(value, str):
                    raise ValueError(f"{key} must be text.")
                if key == "title" and not str(value).strip():
                    raise ValueError("A title is required.")
                record[key] = value
