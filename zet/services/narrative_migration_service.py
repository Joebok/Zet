"""Offline, resumable migration of reviewed legacy scenes into Narrative stubs.

This service never constructs ZetApp, starts workers, or normalizes source scenes.
The inventory and reviewed briefs are inputs, not a scene-generation pipeline.
"""
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import mimetypes
from pathlib import Path
import re
import shutil
import sqlite3
from types import SimpleNamespace
from uuid import NAMESPACE_URL, uuid5

from PIL import Image

from zet.models.narrative import NarrativeElement, NarrativeScene, NarrativeStory, NarrativeTarget
from zet.repositories.entity_library_repository import EntityLibraryRepository
from zet.repositories.narrative_repository import NarrativeRepository
from zet.services.atomic_file_service import write_json_atomic
from zet.services.entity_library_service import EntityLibraryService


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stable_id(*parts):
    return uuid5(NAMESPACE_URL, "zet:legacy:" + ":".join(parts)).hex


def story_brief(markdown, settings):
    premise = settings.get("story", {}).get("premise", "")
    if premise:
        return premise
    workspace = re.search(r"(?ms)^# Story Workspace\s*\n(.*?)(?=^---|^# |\Z)", markdown)
    text = workspace.group(1).strip() if workspace else ""
    return "" if text.startswith("Use this markdown file for human writing") else text


class NarrativeMigrationService:
    def __init__(self, source, destination, legacy_library, manifest, universe):
        self.source = Path(source).resolve()
        self.destination = Path(destination).resolve()
        self.legacy = Path(legacy_library).resolve()
        self.manifest = json.loads(Path(manifest).read_text(encoding="utf-8"))
        if self.manifest["universe_id"] != universe:
            raise ValueError("Manifest universe does not match the explicit destination universe.")
        descriptor = self.destination / "universe.json"
        if descriptor.exists() and json.loads(descriptor.read_text(encoding="utf-8"))["universe_id"] != universe:
            raise ValueError("Destination belongs to another universe.")
        self.universe = universe
        self.repository = NarrativeRepository(self.destination)
        self.journal_path = self.destination / "_state" / "NarrativeMigration" / "journal.json"
        self.database = self.destination / "catalog.sqlite3"
        self.assets = None
        self.stale_assets = set()
        for store in (self.destination / "_state" / "LocalAssets").glob("*/*/local_assets.json"):
            for record in json.loads(store.read_text(encoding="utf-8")).get("assets", {}).values():
                if record.get("stale") and record.get("entity_library_asset_id"):
                    self.stale_assets.add(record["entity_library_asset_id"])
        self.auxiliary = {}
        auxiliary_path = self.legacy / "AuxiliaryResources" / "AuxiliaryResources.json"
        if auxiliary_path.exists():
            for resource in json.loads(auxiliary_path.read_text(encoding="utf-8")).get("resources", []):
                for image in resource.get("images", []):
                    self.auxiliary[image["tag"]] = Path(image["image_path"])

    def query(self, sql, args=()):
        if not self.database.exists():
            return None
        with sqlite3.connect(self.database.as_uri() + "?mode=ro", uri=True) as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(sql, args).fetchone()
            return dict(row) if row else None

    def reference(self, element, ref, apply=False):
        key = ref.get("reference_key", "")
        tag = ref.get("tag", "")
        if tag.startswith("{{ASSET:"):
            view = tag.split("|")[1].strip() if "|" in tag else ""
            costume = element.get("costume") or tag.split("|")[-1].rstrip("}").strip()
            key = EntityLibraryService.logical_costume_reference_key(
                element.get("character") or tag.split(":")[1],
                element.get("phase") or tag.split(":")[2], costume, view)
        if key:
            current = self.query("SELECT a.asset_id,a.status,a.file_name FROM logical_references l JOIN assets a ON a.asset_id=l.asset_id WHERE l.reference_key=? AND l.status='active'", (key,))
            issue = "" if current and current["status"] == "approved" and current["asset_id"] not in self.stale_assets and (self.destination / "images" / current["file_name"]).is_file() else f"Unavailable current costume reference: {key}"
            return {"reference_key": key, "asset_id": ""}, issue
        if ref.get("asset_id"):
            current = self.query("SELECT asset_id,status,file_name FROM assets WHERE asset_id=?", (ref["asset_id"],))
            if current and current["status"] == "approved" and (self.destination / "images" / current["file_name"]).is_file():
                return {"asset_id": current["asset_id"], "reference_key": ""}, ""
        mapped = self.query("SELECT a.asset_id,a.status,a.file_name FROM legacy_image_references l JOIN assets a ON a.asset_id=l.asset_id WHERE l.reference_tag=?", (tag,)) if tag else None
        if mapped and mapped["status"] == "approved" and (self.destination / "images" / mapped["file_name"]).is_file():
            return {"asset_id": mapped["asset_id"], "reference_key": ""}, ""
        path = self.auxiliary.get(tag)
        if tag.startswith("{{SCENE_RENDER:"):
            story, scene, target = tag.removeprefix("{{SCENE_RENDER:").removesuffix("}}").split(":")
            path = self.source / "Stories" / story / "_Subscene_Renders" / scene / (target + ".png")
        elif tag.startswith("{{SCENE:"):
            story, scene = tag.removeprefix("{{SCENE:").removesuffix("}}").split(":")
            path = self.source / "Stories" / story / (scene + ".png")
        if path and path.is_file():
            checksum = digest(path)
            same = self.query("SELECT asset_id FROM assets WHERE checksum=? AND status='approved'", (checksum,))
            if same:
                return {"asset_id": same["asset_id"], "reference_key": ""}, ""
            if apply:
                asset = self.assets.import_asset(element.get("display_name") or path.stem,
                    mimetypes.guess_type(path.name)[0], path.read_bytes(), origin="legacy_reference",
                    origin_key="legacy-reference:" + checksum,
                    provenance_details={"source_path": str(path), "source_tag": tag, "checksum": checksum})
                if tag:
                    self.assets.register_legacy_reference(tag, asset["asset_id"])
                return {"asset_id": asset["asset_id"], "reference_key": ""}, ""
            return {"asset_id": "", "reference_key": ""}, ""
        if tag or ref.get("asset_id"):
            return {"asset_id": "", "reference_key": ""}, f"Unrecoverable reference: {tag or ref['asset_id']}"
        return {"asset_id": "", "reference_key": ""}, ""

    def scene_records(self, story, item, apply=False):
        folder = self.source / "Stories" / story["slug"]
        source_path = folder / (item["slug"] + ".scene.json")
        image_path = folder / (item["slug"] + ".png")
        if digest(source_path) != item["source_sha256"] or digest(image_path) != item["image_sha256"]:
            raise ValueError(f"Source changed since review: {story['slug']}/{item['slug']}")
        source = json.loads(source_path.read_text(encoding="utf-8"))
        review = item["image_review"]
        if not review.get("staging") or not review.get("backdrop"):
            raise ValueError(f"Image review is incomplete: {item['slug']}")
        scene = asdict(NarrativeScene(item["title"], id=item["id"]))
        environment = source.get("setup", {}).get("environment", {})
        settings = json.loads((folder / (story["slug"] + ".story.json")).read_text(encoding="utf-8"))
        style = settings.get("style_defaults", {}).get("canonical_art_style", {}).get("full_prompt_text", "")
        scene.update(intent=source["scene"].get("story_beat", ""), setting=review["backdrop"],
                     lighting=review.get("lighting") or environment.get("lighting", ""),
                     camera=review.get("camera", "Eye level"), perspective=review.get("perspective", "Natural perspective"),
                     style=review.get("style") or style or "Painterly semi-realistic fantasy illustration")
        issues = list(review.get("issues", []))
        id_map = {}
        aggregate_ids = {sub.get("element_id") for sub in source.get("subscenes", []) if sub.get("element_id")}
        # Old group elements have a target named <element-id>_subscene; keep their
        # source descriptions in provenance, not a second copy of their members.
        aggregate_ids.update(e["id"] for e in source["scene_elements"] if any(
            child.get("subscene_id") == e["id"] + "_subscene" for child in source["scene_elements"]))
        for element in source["scene_elements"]:
            if element["id"] in aggregate_ids:
                continue
            kind = "environment" if element.get("element_type") == "Backdrop" else "prop" if element.get("element_type") == "Prop" else "subject"
            if item["slug"] == "Roped-to-the-Road" and "rescued travelers" in element.get("display_name", ""):
                kind = "subject"
            record = asdict(NarrativeElement(element.get("display_name") or element["id"],
                id=stable_id(self.universe, story["slug"], item["slug"], element["id"]), kind=kind,
                appearance="\n".join(filter(None, (element.get("fallback_visual_description"), element.get("element_visual_override"), element.get("notes"))))))
            references = element.get("reference_images") or []
            if references:
                binding, issue = self.reference(element, references[0], apply)
                record.update(binding)
                if issue:
                    issues.append(record["name"] + ": " + issue)
            id_map[element["id"]] = record["id"]
            scene["elements"].append(record)
        with Image.open(image_path) as image:
            width, height = image.size
        scale = min(1344 / max(width, height), 1)
        width, height = (max(256, round(value * scale / 32) * 32) for value in (width, height))
        scene["canvas"] = f"{width}:{height}"
        backdrop_ids = [e["id"] for e in scene["elements"] if e["kind"] == "environment"]
        subject_ids = [e["id"] for e in scene["elements"] if e["kind"] != "environment"]
        targets = []
        def target(kind, title, members, staging, suffix):
            record = asdict(NarrativeTarget(title, kind, id=stable_id(self.universe, story["slug"], item["slug"], suffix),
                narrative=scene["intent"] if kind != "backdrop" else review["backdrop"], staging=staging,
                physical_context=review.get("physical_context", environment.get("weather_or_atmosphere", "")),
                framing=review.get("framing", "Match the legacy image framing"), width=width, height=height, element_ids=members))
            targets.append(record)
        target("backdrop", "Backdrop", backdrop_ids, review["backdrop"], "backdrop")
        groups = review.get("groups") or [{"title": "Scene subjects", "staging": review["staging"]}]
        assigned = set()
        for index, group in enumerate(groups):
            members = [e["id"] for e in scene["elements"] if e["id"] in subject_ids and
                       (not group.get("names") or e["name"] in group["names"])]
            assigned.update(members)
            target("subscene", group["title"], members, group.get("staging", review["staging"]), f"subscene-{index}")
        remaining = [e for e in subject_ids if e not in assigned]
        if remaining:
            targets[1]["element_ids"].extend(remaining)
        speakers = {e["id"]: e.get("display_name") or e["id"] for e in source["scene_elements"]}
        dialogue = "\n".join(f"{speakers.get(line.get('speaker_element_id'), 'Speaker unresolved')}: {line.get('text', '')}" +
                             (" — " + line["notes"] if line.get("notes") else "")
                             for line in source.get("dialogue", []) if isinstance(line, dict)) or "None"
        target("assembly", "Final assembly", [], review["staging"] + "\nVisible text from image review: " + review.get("visible_text", "None") +
               "\nSaved dialogue (review discrepancies before generating): " + dialogue, "assembly")
        scene["target_ids"] = [t["id"] for t in targets]
        scene["source_provenance"] = source.get("source_provenance", {})
        scene["migration"] = {"kind": "legacy_scene_stub", "story_slug": story["slug"], "scene_slug": item["slug"],
            "source_sha256": item["source_sha256"], "review_issues": issues,
            "image_review": review, "source_document": source,
            "source_markdown": (folder / (item["slug"] + ".md")).read_text(encoding="utf-8")}
        scene["legacy_image"] = {"source_path": str(image_path), "checksum": item["image_sha256"]}
        if apply:
            image = self.assets.import_asset(f"{story['title']} / {item['title']} · Legacy image", "image/png",
                image_path.read_bytes(), origin="legacy_scene", origin_key=f"legacy-scene:{self.universe}:{story['slug']}:{item['slug']}:{item['image_sha256']}",
                provenance_details=scene["legacy_image"])
            scene["legacy_image"]["asset_id"] = image["asset_id"]
        return scene, targets

    def prepare(self):
        report = {"stories": [], "scenes": 0, "images": 0, "issues": []}
        for story in self.manifest["stories"]:
            report["stories"].append({"title": story["title"], "id": story["id"], "scenes": len(story["scenes"])})
            for item in story["scenes"]:
                scene, targets = self.scene_records(story, item)
                report["scenes"] += 1
                report["images"] += 1
                report["issues"].extend({"scene": item["slug"], "issue": issue} for issue in scene["migration"]["review_issues"])
        return report

    def apply(self):
        self.prepare()  # Validate all immutable inputs before any destination write.
        journal = json.loads(self.journal_path.read_text(encoding="utf-8")) if self.journal_path.exists() else {"scenes": {}, "universe_id": self.universe}
        if not journal.get("backup"):
            backup = self.destination / "backups" / ("narrative-migration-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
            backup.mkdir(parents=True, exist_ok=False)
            if self.database.exists():
                with sqlite3.connect(self.database) as source, sqlite3.connect(backup / "catalog.sqlite3") as dest:
                    source.backup(dest)
            if self.repository.root.exists():
                shutil.copytree(self.repository.root, backup / "NarrativeStories")
            shutil.copytree(self.source / "Stories" / "FirstDay", backup / "FirstDay-source")
            shutil.copytree(self.source / "Stories" / "Phlan-Adventures", backup / "Phlan-source")
            journal["backup"] = str(backup)
            write_json_atomic(self.journal_path, journal)
        repository = EntityLibraryRepository(self.database)
        repository.initialize()
        paths = SimpleNamespace(entity_library_images_path=lambda: self.destination / "images")
        self.assets = EntityLibraryService(paths, repository)
        with self.repository.lock():
            for story in self.manifest["stories"]:
                parent_path = self.repository.path(story["id"])
                if parent_path.exists():
                    parent = self.repository.read(story["id"])
                    if parent.get("source_provenance", {}).get("story_slug") != story["slug"]:
                        raise ValueError("Migration story ID is occupied by another record.")
                else:
                    parent = asdict(NarrativeStory(story["title"], id=story["id"]))
                    parent["source_provenance"] = {"source_type": "legacy_story", "story_slug": story["slug"], "universe_id": self.universe}
                    parent["source_provenance"]["source_document"] = json.loads((self.source / "Stories" / story["slug"] / (story["slug"] + ".story.json")).read_text(encoding="utf-8"))
                    markdown = (self.source / "Stories" / story["slug"] / (story["slug"] + ".md")).read_text(encoding="utf-8")
                    parent["source_provenance"]["source_markdown"] = markdown
                    parent["brief"] = story_brief(markdown, parent["source_provenance"]["source_document"])
                    self.repository.write(parent, story["id"])
                for item in story["scenes"]:
                    key = story["slug"] + "/" + item["slug"]
                    path = self.repository.path(story["id"], item["id"])
                    if key not in journal["scenes"]:
                        if path.exists():
                            raise ValueError(f"Unjournaled destination exists; preserve it and inspect: {key}")
                        journal["scenes"][key] = {"state": "reserved", "story_id": story["id"], "scene_id": item["id"]}
                        write_json_atomic(self.journal_path, journal)
                    entry = journal["scenes"][key]
                    if entry["state"] == "complete":
                        # Never regenerate authored inputs, even after user edits.
                        continue
                    if path.exists():
                        current = self.repository.read(story["id"], item["id"])
                        if current.get("migration", {}).get("source_sha256") != item["source_sha256"]:
                            raise ValueError(f"Reserved scene changed; refusing overwrite: {key}")
                    else:
                        scene, targets = self.scene_records(story, item, True)
                        for target in targets:
                            self.repository.write(target, story["id"], item["id"], target["id"])
                        self.repository.write(scene, story["id"], item["id"])
                    if item["id"] not in parent["scene_ids"]:
                        parent["scene_ids"].append(item["id"])
                    self.repository.write(parent, story["id"])
                    entry["state"] = "complete"
                    write_json_atomic(self.journal_path, journal)
        self.assets.refresh_usages(self.destination)
        passed = Path(__file__).resolve().parents[2] / "Config" / "Scene_Candidate_State.json"
        state_path = self.destination / "_state" / "NarrativeCandidates" / "state.json"
        if self.universe == "Moonsea" and passed.exists() and not state_path.exists():
            write_json_atomic(state_path, json.loads(passed.read_text(encoding="utf-8")))
        archive = self.destination / "_state" / "NarrativeMigration" / "archive" / "FirstDay"
        archive.mkdir(parents=True, exist_ok=True)
        for suffix in (".md", ".scene.json"):
            source = self.source / "Stories" / "FirstDay" / ("Collision" + suffix)
            if source.exists() and not (archive / source.name).exists():
                shutil.copy2(source, archive / source.name)
        return self.verify()

    def verify(self):
        report = {"stories": 0, "scenes": 0, "images": 0, "errors": [], "issues": []}
        for story in self.manifest["stories"]:
            parent = self.repository.read(story["id"])
            report["stories"] += 1
            expected = [item["id"] for item in story["scenes"]]
            if [i for i in parent["scene_ids"] if i in expected] != expected:
                report["errors"].append(f"Scene order differs: {story['slug']}")
            for item in story["scenes"]:
                scene = self.repository.read(story["id"], item["id"])
                targets = [self.repository.read(story["id"], item["id"], t) for t in scene["target_ids"]]
                if not {"backdrop", "subscene", "assembly"}.issubset({t["kind"] for t in targets}):
                    report["errors"].append(f"Missing target kinds: {item['slug']}")
                members = {e["id"] for e in scene["elements"]}
                if any(set(t["element_ids"]) - members for t in targets):
                    report["errors"].append(f"Invalid element membership: {item['slug']}")
                asset = self.query("SELECT file_name,checksum FROM assets WHERE asset_id=?", (scene["legacy_image"].get("asset_id", ""),))
                if not asset or asset["checksum"] != item["image_sha256"] or digest(self.destination / "images" / asset["file_name"]) != item["image_sha256"]:
                    report["errors"].append(f"Legacy image mismatch: {item['slug']}")
                else:
                    report["images"] += 1
                report["scenes"] += 1
                report["issues"].extend({"scene": item["slug"], "issue": issue} for issue in scene["migration"]["review_issues"])
        return report
