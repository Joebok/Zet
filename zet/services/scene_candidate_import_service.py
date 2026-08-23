from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from zet.models.scene_candidate import SceneCandidate, SceneCandidateImportResult, SceneCandidateSource
from zet.services.story_cast_service import StoryCastService


class SceneCandidateImportError(Exception):
    pass


class SceneCandidateImportService:
    """Read scene-candidate indexes and create provenance-linked Scene Builder drafts."""

    FIELD_RE = re.compile(r"^\*\*(?P<label>[^*]+):\*\*\s*(?P<value>.*)$")
    HEADING_RE = re.compile(r"^###\s+Scene\s+(.+?)\s+[—-]\s+(.+?)\s*$")

    def __init__(self, config, story_service):
        self.config = config
        self.story_service = story_service
        self.story_cast_service = StoryCastService(story_service)

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())

    @staticmethod
    def _known(value: str) -> str:
        text = str(value or "").strip()
        return "" if text.casefold().startswith("unknown") else text

    def list_sources(self) -> list[SceneCandidateSource]:
        sources = []
        for configured in self.config.scene_candidate_sources:
            path = Path(configured.path).expanduser()
            exists = path.is_file()
            modified = datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds") if exists else ""
            error = "" if exists else f"Scene candidate index not found: {path}"
            sources.append(SceneCandidateSource(
                key=configured.key,
                label=configured.label,
                path=str(path),
                default_story_slug=configured.default_story_slug,
                read_only=configured.read_only,
                exists=exists,
                modified_at=modified,
                error=error,
            ))
        return sources

    def _source(self, source_key: str) -> SceneCandidateSource:
        for source in self.list_sources():
            if source.key == str(source_key or "").strip():
                if not source.read_only:
                    raise SceneCandidateImportError(f"Scene candidate source must be read-only: {source.key}")
                if not source.exists:
                    raise SceneCandidateImportError(source.error)
                return source
        raise SceneCandidateImportError(f"Unknown scene candidate source: {source_key}")

    @staticmethod
    def _field_value(lines: list[str]) -> object:
        cleaned = [line.rstrip() for line in lines]
        while cleaned and not cleaned[0].strip():
            cleaned.pop(0)
        while cleaned and not cleaned[-1].strip():
            cleaned.pop()
        bullets = [re.sub(r"^\s*[-*]\s+", "", line).strip() for line in cleaned if re.match(r"^\s*[-*]\s+", line)]
        nonblank = [line.strip() for line in cleaned if line.strip()]
        if bullets and len(bullets) == len(nonblank):
            return bullets
        return "\n".join(nonblank).strip()

    def _parse_block(self, source_key: str, heading_id: str, title: str, lines: list[str]) -> SceneCandidate:
        fields: dict[str, object] = {}
        current = ""
        buffer: list[str] = []
        for line in lines:
            match = self.FIELD_RE.match(line.strip())
            if match:
                if current:
                    fields[current] = self._field_value(buffer)
                current = match.group("label").strip()
                buffer = [match.group("value")] if match.group("value").strip() else []
            elif current:
                buffer.append(line)
        if current:
            fields[current] = self._field_value(buffer)
        candidate_id = str(fields.get("Candidate ID") or heading_id).strip()
        session = str(fields.get("Source Session") or "").strip()
        raw = "\n".join([f"### Scene {heading_id} — {title}", *lines]).strip()
        warnings = []
        if not fields.get("Candidate ID"):
            warnings.append("Candidate ID is inherited from the heading; add an explicit stable Candidate ID.")
        if "TBD" in candidate_id.upper():
            warnings.append("Candidate ID is not stable because it contains TBD.")
        for required in ("Story Beat", "Location"):
            if not fields.get(required):
                warnings.append(f"Missing required field: {required}.")
        return SceneCandidate(
            source_key=source_key,
            candidate_id=candidate_id,
            session=session,
            title=title.strip(),
            status=str(fields.get("Status") or "Candidate").strip(),
            fields=fields,
            content_hash=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            warnings=warnings,
        )

    def _parse(self, source: SceneCandidateSource) -> list[SceneCandidate]:
        text = Path(source.path).read_text(encoding="utf-8")
        lines = text.splitlines()
        candidates = []
        current: tuple[str, str] | None = None
        buffer: list[str] = []
        for line in lines:
            match = self.HEADING_RE.match(line.strip())
            if match and "[Scene Title]" not in match.group(2):
                if current:
                    candidates.append(self._parse_block(source.key, current[0], current[1], buffer))
                current = (match.group(1).strip(), match.group(2).strip())
                buffer = []
            elif current:
                buffer.append(line)
        if current:
            candidates.append(self._parse_block(source.key, current[0], current[1], buffer))
        counts: dict[str, int] = {}
        for candidate in candidates:
            counts[candidate.candidate_id] = counts.get(candidate.candidate_id, 0) + 1
        return [
            replace(candidate, warnings=[*candidate.warnings, "Duplicate Candidate ID."])
            if counts[candidate.candidate_id] > 1 else candidate
            for candidate in candidates
        ]

    def _imported_scenes(self) -> dict[tuple[str, str], tuple[str, str, dict]]:
        imported = {}
        for story in self.story_service.list_stories():
            folder = self.story_service.path_service.story_folder_path(story.slug)
            for path in folder.glob("*.scene.json") if folder.is_dir() else []:
                try:
                    data = json.loads(path.read_text(encoding="utf-8"))
                except Exception:
                    continue
                provenance = data.get("source_provenance") if isinstance(data, dict) else None
                if not isinstance(provenance, dict):
                    continue
                key = (str(provenance.get("source_key") or ""), str(provenance.get("candidate_id") or ""))
                if all(key):
                    imported[key] = (story.slug, path.name.removesuffix(".scene.json"), data)
        return imported

    def list_candidates(self, source_key: str) -> list[SceneCandidate]:
        source = self._source(source_key)
        imported = self._imported_scenes()
        output = []
        for candidate in self._parse(source):
            record = imported.get((source.key, candidate.candidate_id))
            if not record:
                output.append(candidate)
                continue
            story_slug, scene_slug, data = record
            provenance = data.get("source_provenance") or {}
            readiness = self.readiness(data)
            state = "source_changed" if provenance.get("content_hash") != candidate.content_hash else str(readiness["status"])
            if self.story_service.scene_image_path(story_slug, scene_slug).is_file():
                state = "rendered"
            output.append(replace(
                candidate,
                imported_story_slug=story_slug,
                imported_scene_slug=scene_slug,
                import_state=state,
                readiness=readiness,
            ))
        return output

    def get_candidate(self, source_key: str, candidate_id: str) -> SceneCandidate:
        for candidate in self.list_candidates(source_key):
            if candidate.candidate_id == candidate_id:
                return candidate
        raise SceneCandidateImportError(f"Scene candidate not found: {source_key}/{candidate_id}")

    @staticmethod
    def _list_field(candidate: SceneCandidate, *names: str) -> list[str]:
        for name in names:
            value = candidate.fields.get(name)
            if isinstance(value, list):
                return [str(item).strip() for item in value if str(item).strip()]
            if isinstance(value, str) and value.strip():
                return [line.strip(" -*\t") for line in value.splitlines() if line.strip(" -*\t")]
        return []

    @staticmethod
    def _text_field(candidate: SceneCandidate, *names: str) -> str:
        for name in names:
            value = candidate.fields.get(name)
            if isinstance(value, list):
                return "\n".join(str(item) for item in value)
            if str(value or "").strip():
                return str(value).strip()
        return ""

    def _named_details(self, candidate: SceneCandidate, *names: str) -> dict[str, str]:
        details = {}
        for item in self._list_field(candidate, *names):
            match = re.match(r"^([^:—]+?)\s*(?::|—)\s*(.+)$", item)
            if match:
                details[self._normalize(match.group(1))] = match.group(2).strip()
        return details

    def _resource_indexes(self) -> tuple[dict[str, list[str]], dict[str, list[Any]]]:
        character_root = Path(self.story_service.path_service.config.base_character_path)
        characters: dict[str, list[str]] = {}
        if character_root.is_dir():
            for path in character_root.iterdir():
                if path.is_dir() and not path.name.startswith("_"):
                    characters.setdefault(self._normalize(path.name), []).append(path.name)
        auxiliary: dict[str, list[Any]] = {}
        for resource in self.story_service.auxiliary_resource_repository.list_resources():
            auxiliary.setdefault(self._normalize(resource.label), []).append(resource)
        return characters, auxiliary

    def _element(self, name: str, element_type: str, details: str, characters, auxiliary) -> dict:
        normalized = self._normalize(name)
        element_id = self.story_service.normalize_scene_element_id(name)
        character_matches = characters.get(normalized, [])
        auxiliary_matches = auxiliary.get(normalized, [])
        value = {
            "id": element_id,
            "display_name": name,
            "resource_type": "Scene-Only",
            "element_type": element_type,
            "character": "",
            "phase": "",
            "costume": "",
            "aux_category": "",
            "aux_resource_id": "",
            "reference_images": [],
            "element_visual_override": "",
            "fallback_visual_description": self._known(details),
            "notes": "",
        }
        if len(character_matches) == 1:
            character = character_matches[0]
            phases = [path.name for path in (Path(self.story_service.path_service.config.base_character_path) / character).iterdir() if path.is_dir() and not path.name.startswith("_")]
            value.update(resource_type="Character", character=character, phase="Adult" if "Adult" in phases else (phases[0] if len(phases) == 1 else ""))
        elif len(auxiliary_matches) == 1:
            resource = auxiliary_matches[0]
            resource_type = {"person": "Person", "place": "Place", "thing": "Object"}.get(resource.category, "Scene-Only")
            tags = [str(image.get("tag") or "") for image in resource.images if str(image.get("tag") or "")]
            value.update(
                resource_type=resource_type,
                element_type="Character" if resource_type == "Person" else element_type,
                aux_category=resource.category,
                aux_resource_id=resource.resource_id,
                reference_images=[{"tag": tags[0]}] if tags else [],
            )
        elif len(character_matches) > 1 or len(auxiliary_matches) > 1:
            matches = [f"Character {item}" for item in character_matches]
            matches.extend(f"Auxiliary {item.resource_id}" for item in auxiliary_matches)
            value["notes"] = f"UNRESOLVED: Multiple canonical resources match this element: {', '.join(matches)}."
        elif not self._known(details):
            value["notes"] = "UNRESOLVED: Canonical visual appearance is not established."
        return value

    def _candidate_data(self, candidate: SceneCandidate, story_slug: str, scene_slug: str) -> dict:
        data = self.story_service.create_default_scene_builder_data(story_slug, scene_slug)
        visual_details = self._named_details(candidate, "Known Visual Facts", "Visible Elements")
        character_references = self._named_details(candidate, "Character References")
        acting = self._named_details(candidate, "Acting and Placement", "Visual Action")
        visible = self._list_field(candidate, "Visible Elements", "Characters Present")
        present_names = {
            self._normalize(re.split(r"\s*(?::|—)\s*", name, maxsplit=1)[0])
            for name in self._list_field(candidate, "Characters Present")
        }
        props = self._list_field(candidate, "Important Props / Objects")
        characters, auxiliary = self._resource_indexes()
        elements = []
        seen = set()
        for name in visible:
            clean_name = re.split(r"\s*(?::|—)\s*", name, maxsplit=1)[0].strip()
            key = self._normalize(clean_name)
            if key and key not in seen:
                if key in self._normalize(self._text_field(candidate, "Location")) and key not in present_names:
                    continue
                seen.add(key)
                element_type = "Character" if key in present_names else "Prop"
                element = self._element(clean_name, element_type, visual_details.get(key, ""), characters, auxiliary)
                if element["resource_type"] == "Character":
                    resolved = self.story_cast_service.resolve(
                        story_slug,
                        element["character"],
                        element["phase"],
                        character_references.get(key, ""),
                    )
                    element["phase"] = resolved["phase"] or element["phase"]
                    element["costume"] = resolved["costume"]
                    if resolved["tag"]:
                        element["reference_images"] = [{"tag": resolved["tag"]}]
                    else:
                        element["notes"] = f"UNRESOLVED: {resolved['error']}"
                elements.append(element)
        for name in props:
            clean_name = re.split(r"\s*(?::|—)\s*", name, maxsplit=1)[0].strip()
            key = self._normalize(clean_name)
            if key and key not in seen:
                seen.add(key)
                elements.append(self._element(clean_name, "Prop", visual_details.get(key, ""), characters, auxiliary))
        location = self._text_field(candidate, "Location")
        location_name = location.split(",", 1)[0].strip().rstrip(".") or "Scene backdrop"
        backdrop = self._element(location_name, "Backdrop", location, characters, auxiliary)
        backdrop["id"] = self.story_service.normalize_scene_element_id(location_name)
        elements.insert(0, backdrop)
        moment = self._text_field(candidate, "Depicted Moment")
        story_beat = self._known(moment) or self._text_field(candidate, "Story Beat")
        composition = self._text_field(candidate, "Suggested Composition", "Composition")
        focal_point = self._text_field(candidate, "Focal Point")
        if not focal_point and "Tsaeytte" in " ".join(visible):
            focal_point = "Tsaeytte"
        by_name = {self._normalize(item["display_name"]): item["id"] for item in elements}
        reading_names = self._list_field(candidate, "Reading Order")
        left_to_right = [by_name[self._normalize(name)] for name in reading_names if self._normalize(name) in by_name]
        if not left_to_right:
            left_to_right = [item["id"] for item in elements if item["element_type"] != "Backdrop"]
        placements = []
        for index, element in enumerate(elements, start=1):
            backdrop_element = element["element_type"] == "Backdrop"
            detail = acting.get(self._normalize(element["display_name"]), "")
            placements.append({
                "id": f"placement_{index:03d}",
                "scene_element_id": element["id"],
                "position_within_cell": "" if backdrop_element else "center",
                "depth": "background" if backdrop_element else "midground",
                "world_position": "",
                "frame_coverage": "",
                "distance_from_camera": "",
                "visual_scale": "",
                "pose": {
                    "summary": detail,
                    "temporary_condition": "",
                    "gaze_target_element_id": "",
                    "expression": "",
                    "left_arm_action": "",
                    "right_arm_action": "",
                    "leg_foot_detail": "",
                    "balance_weight_detail": "",
                },
                "motion": {"state": "stationary", "direction_screen": "", "cue": ""},
                "placement_notes": "",
            })
        dialogue = []
        for item in self._list_field(candidate, "Visible Dialogue"):
            match = re.match(r'^([^:]+):\s*[“\"](.+?)[”\"]$', item)
            speaker_id = by_name.get(self._normalize(match.group(1))) if match else None
            if match and speaker_id:
                dialogue.append({
                    "id": f"dialogue_{len(dialogue) + 1:03d}",
                    "speaker_element_id": speaker_id,
                    "text": match.group(2),
                    "target_element_id": "",
                    "pointer_target": "speaker mouth",
                    "max_lines": 3,
                    "notes": "",
                })
        data["scene"].update(
            name=candidate.title,
            story_beat=story_beat,
            author_notes="\n\n".join(part for part in [
                self._text_field(candidate, "Why It Matters"),
                self._text_field(candidate, "Continuity Requirements"),
                self._text_field(candidate, "Exact Details to Preserve"),
            ] if part),
        )
        data["setup"]["environment"].update(
            location=location,
            lighting=self._known(self._text_field(candidate, "Lighting")),
            mood=self._known(self._text_field(candidate, "Mood")),
            weather_or_atmosphere=self._known(self._text_field(candidate, "Atmosphere", "Weather or Atmosphere")),
        )
        data["setup"]["composition"].update(
            focal_point=focal_point,
            left_to_right=left_to_right,
            composition_notes=composition,
        )
        framing = self._known(self._text_field(candidate, "Framing")).casefold()
        if "portrait" in framing or "vertical" in framing:
            data["setup"]["canvas"].update(orientation="portrait", aspect_ratio="4:5")
        elif "square" in framing:
            data["setup"]["canvas"].update(orientation="square", aspect_ratio="1:1")
        elif "landscape" in framing or "wide" in framing:
            data["setup"]["canvas"].update(orientation="landscape", aspect_ratio="16:9")
        data["scene_elements"] = elements
        data["placements"] = placements
        data["dialogue"] = dialogue
        data["source_provenance"] = {
            "source_type": "scene_candidate_markdown",
            "source_key": candidate.source_key,
            "candidate_id": candidate.candidate_id,
            "source_session": candidate.session,
            "content_hash": candidate.content_hash,
            "imported_at": datetime.now().isoformat(timespec="seconds"),
            "constraints": {
                "continuity_requirements": self._list_field(candidate, "Continuity Requirements"),
                "exact_details": self._list_field(candidate, "Exact Details to Preserve"),
            },
            "depicted_moment": moment,
            "depicted_moment_unresolved": not bool(self._known(moment)),
            "framing": self._text_field(candidate, "Framing"),
            "visible_dialogue": self._text_field(candidate, "Visible Dialogue"),
        }
        return data

    def readiness(self, data: dict) -> dict[str, object]:
        blockers = []
        advisories = []
        scene = data.get("scene") or {}
        setup = data.get("setup") or {}
        environment = setup.get("environment") or {}
        composition = setup.get("composition") or {}
        elements = [item for item in data.get("scene_elements") or [] if isinstance(item, dict)]
        placements = [item for item in data.get("placements") or [] if isinstance(item, dict)]
        visible = [item for item in elements if item.get("element_type") != "Backdrop"]
        if not str(scene.get("story_beat") or "").strip():
            blockers.append("Story beat is missing.")
        if (data.get("source_provenance") or {}).get("depicted_moment_unresolved"):
            blockers.append("The candidate does not yet identify one exact depicted moment.")
        if not visible:
            blockers.append("No visible scene elements are defined.")
        placement_ids = {str(item.get("scene_element_id") or "") for item in placements}
        for element in visible:
            if element.get("id") not in placement_ids:
                blockers.append(f"{element.get('display_name')} has no placement.")
            if str(element.get("notes") or "").startswith("UNRESOLVED:"):
                blockers.append(f"{element.get('display_name')} has an unresolved canonical resource or appearance.")
            if element.get("resource_type") == "Character" and not element.get("reference_images"):
                blockers.append(f"{element.get('display_name')} has no canonical character image reference.")
            if not (element.get("reference_images") or str(element.get("fallback_visual_description") or "").strip()):
                blockers.append(f"{element.get('display_name')} has no visual source or fallback description.")
        if not str(environment.get("location") or "").strip():
            blockers.append("Location is missing.")
        if not str(environment.get("lighting") or "").strip():
            blockers.append("Lighting is missing.")
        if not str(composition.get("focal_point") or "").strip():
            blockers.append("Focal point is missing.")
        if not composition.get("left_to_right"):
            blockers.append("Reading order is missing.")
        advisories.extend(self.story_service.validate_scene_builder_data(data))
        status = "ready" if not blockers else ("draft" if not scene.get("story_beat") or not visible else "needs_attention")
        return {"status": status, "blockers": list(dict.fromkeys(blockers)), "advisories": list(dict.fromkeys(advisories))}

    def _interview_text(self, candidate: SceneCandidate) -> str:
        parts = [f"SCENE CANDIDATE: {candidate.title}", f"SOURCE SESSION: {candidate.session}"]
        for label, value in candidate.fields.items():
            rendered = "\n".join(str(item) for item in value) if isinstance(value, list) else str(value)
            if rendered.strip():
                parts.append(f"{label.upper()}:\n{rendered.strip()}")
        return "\n\n".join(parts)

    def _interview_phases(self, data: dict) -> list[str]:
        phases = []
        elements = data.get("scene_elements") or []
        if any(
            str(item.get("notes") or "").startswith("UNRESOLVED:")
            or (item.get("resource_type") == "Character" and not item.get("reference_images"))
            for item in elements
            if isinstance(item, dict)
        ):
            phases.append("elements")
        if not str((data.get("scene") or {}).get("story_beat") or "").strip():
            phases.append("story")
        if (data.get("source_provenance") or {}).get("depicted_moment_unresolved"):
            phases.append("story")
        framing = self._known(str((data.get("source_provenance") or {}).get("framing") or "")).casefold()
        if not any(term in framing for term in ("portrait", "vertical", "square", "landscape", "wide")):
            phases.append("canvas")
        environment = (data.get("setup") or {}).get("environment") or {}
        if not environment.get("lighting") or not environment.get("location"):
            phases.append("environment")
        composition = (data.get("setup") or {}).get("composition") or {}
        if not composition.get("composition_notes") or not composition.get("focal_point"):
            phases.append("composition")
        placements = data.get("placements") or []
        if any(item.get("element_type") != "Backdrop" and not str(next((p.get("pose", {}).get("summary") for p in placements if p.get("scene_element_id") == item.get("id")), "") or "").strip() for item in elements):
            phases.append("placements")
        visible_dialogue = str((data.get("source_provenance") or {}).get("visible_dialogue") or "")
        if visible_dialogue and not visible_dialogue.casefold().startswith("none") and not data.get("dialogue"):
            phases.append("relationships")
        return list(dict.fromkeys(phases))

    def interview_seed(self, data: dict) -> dict[str, object]:
        provenance = data.get("source_provenance") if isinstance(data, dict) else None
        if not isinstance(provenance, dict) or provenance.get("source_type") != "scene_candidate_markdown":
            raise SceneCandidateImportError("This scene was not imported from a scene candidate.")
        candidate = self.get_candidate(
            str(provenance.get("source_key") or ""),
            str(provenance.get("candidate_id") or ""),
        )
        return {
            "narrative": self._interview_text(candidate),
            "phases": self._interview_phases(data),
        }

    def import_candidate(self, source_key: str, candidate_id: str, story_slug: str, confirm_update: bool = False) -> SceneCandidateImportResult:
        candidate = self.get_candidate(source_key, candidate_id)
        if any("Duplicate Candidate ID" in warning for warning in candidate.warnings):
            raise SceneCandidateImportError("Duplicate Candidate ID must be fixed before import.")
        story_slug = self.story_service.safe_slug(story_slug)
        if not any(story.slug == story_slug for story in self.story_service.list_stories()):
            raise SceneCandidateImportError(f"Target story does not exist: {story_slug}")
        imported = self._imported_scenes().get((source_key, candidate_id))
        created = imported is None
        if imported:
            imported_story, scene_slug, existing = imported
            source_changed = (existing.get("source_provenance") or {}).get("content_hash") != candidate.content_hash
            if source_changed and not confirm_update:
                raise SceneCandidateImportError("The source candidate changed; confirm re-import before updating the scene.")
            story_slug = imported_story
            if not source_changed:
                readiness = self.readiness(existing)
                return SceneCandidateImportResult(
                    candidate=candidate,
                    story_slug=story_slug,
                    scene_slug=scene_slug,
                    created=False,
                    data=existing,
                    interview_narrative=self._interview_text(candidate),
                    interview_phases=self._interview_phases(existing),
                    readiness=readiness,
                )
        else:
            base_slug = self.story_service.safe_slug(candidate.title)
            scene_slug = base_slug
            existing_slugs = {scene.slug for scene in self.story_service.list_scenes(story_slug)}
            if scene_slug in existing_slugs:
                suffix = self.story_service.safe_slug(candidate.session or candidate.candidate_id)
                scene_slug = self.story_service.safe_slug(f"{base_slug}-{suffix}")
                counter = 2
                while scene_slug in existing_slugs:
                    scene_slug = self.story_service.safe_slug(f"{base_slug}-{suffix}-{counter}")
                    counter += 1
            create_title = candidate.title if scene_slug == base_slug else scene_slug.replace("-", " ")
            created_document = self.story_service.create_scene(story_slug, create_title)
            scene_slug = created_document.record.slug
        data = self._candidate_data(candidate, story_slug, scene_slug)
        document = self.story_service.save_scene_builder_data(story_slug, scene_slug, data)
        readiness = self.readiness(document.data)
        return SceneCandidateImportResult(
            candidate=candidate,
            story_slug=story_slug,
            scene_slug=scene_slug,
            created=created,
            data=document.data,
            interview_narrative=self._interview_text(candidate),
            interview_phases=self._interview_phases(document.data),
            readiness=readiness,
        )
