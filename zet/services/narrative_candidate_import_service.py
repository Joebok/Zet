"""Adventure Log briefs become editable Narrative stubs, without dispatch."""
from dataclasses import asdict
import json
from pathlib import Path
import re
from uuid import NAMESPACE_URL, uuid5

from zet.models.narrative import NarrativeScene
from zet.services.narrative_scene_service import SCENE_FIELDS

from zet.services.atomic_file_service import write_json_atomic
from zet.services.scene_candidate_source_service import SceneCandidateSourceService


class NarrativeCandidateImportService:
    def __init__(self, app):
        self.app = app
        self.author = app.narrative_scene_service
        self.repository = self.author.repository
        self.sources = SceneCandidateSourceService(app.config)
        self.state_path = Path(app.config.base_library_path) / "_state" / "NarrativeCandidates" / "state.json"

    def associations(self, source_key, candidate_id):
        result = []
        for story in self.repository.stories():
            for scene_id in story["scene_ids"]:
                scene = self.repository.read(story["id"], scene_id)
                provenance = scene.get("source_provenance", {})
                if (provenance.get("source_key"), provenance.get("candidate_id")) == (source_key, candidate_id):
                    result.append({"story_id": story["id"], "scene_id": scene_id, "title": scene["title"],
                                   "content_hash": provenance.get("content_hash", "")})
        return result

    def state(self):
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        # The pre-Narrative state belongs to the configured Moonsea source only.
        if getattr(self.app, "universe_id", "") == "Moonsea":
            old = self.app.path_service.project_root / "Config" / "Scene_Candidate_State.json"
            if old.exists():
                return json.loads(old.read_text(encoding="utf-8"))
        return {"passed": []}

    def list_sources(self):
        result = []
        for source in self.sources.list_sources():
            value = asdict(source)
            try:
                value["default_story_id"] = self.author.legacy_location(source.default_story_slug)["story_id"]
            except KeyError:
                value["default_story_id"] = ""
            result.append(value)
        return result

    def list_candidates(self, source_key):
        source = self.sources._source(source_key)
        passed = {(p["source_key"], p["candidate_id"]) for p in self.state().get("passed", [])}
        result = []
        for candidate in self.sources._parse(source):
            value = asdict(candidate)
            value["imported_scenes"] = self.associations(source_key, candidate.candidate_id)
            value["import_state"] = "source_changed" if any(s["content_hash"] != candidate.content_hash for s in value["imported_scenes"]) else "imported" if value["imported_scenes"] else "passed" if (source_key, candidate.candidate_id) in passed else "available"
            result.append(value)
        return result

    def get_candidate(self, source_key, candidate_id):
        matches = [c for c in self.list_candidates(source_key) if c["candidate_id"] == candidate_id]
        if len(matches) != 1:
            raise ValueError("Candidate ID must identify exactly one source brief.")
        return matches[0]

    def set_passed(self, source_key, candidate_id, passed):
        self.get_candidate(source_key, candidate_id)
        with self.repository.lock():
            state = self.state()
            entries = {(p["source_key"], p["candidate_id"]) for p in state.get("passed", [])}
            entries.discard((source_key, candidate_id))
            if passed:
                entries.add((source_key, candidate_id))
            state["passed"] = [{"source_key": key, "candidate_id": value} for key, value in sorted(entries)]
            write_json_atomic(self.state_path, state)
        return self.get_candidate(source_key, candidate_id)

    @staticmethod
    def text(fields, name):
        value = fields.get(name, "")
        return "\n".join(str(item) for item in value) if isinstance(value, list) else str(value)

    def import_candidate(self, source_key, candidate_id, story_id):
        with self.repository.lock():
            candidate = self.get_candidate(source_key, candidate_id)
            if candidate["imported_scenes"]:
                association = candidate["imported_scenes"][0]
                current = self.repository.read(association["story_id"], association["scene_id"])
                if current.get("source_provenance", {}).get("import_status") != "building":
                    return {"created": False, "imported_scenes": candidate["imported_scenes"],
                            **association, "review_issues": candidate["warnings"]}
                story_id = association["story_id"]
            state = self.state()
            import_key = source_key + ":" + candidate_id
            reservation = state.get("imports", {}).get(import_key)
            if reservation:
                story_id = reservation["story_id"]
            parent = self.repository.read(story_id)
            if not reservation:
                scene_id = uuid5(NAMESPACE_URL, f"zet:candidate:{self.app.universe_id}:{import_key}").hex
                reservation = {"story_id": story_id, "scene_id": scene_id}
                state.setdefault("imports", {})[import_key] = reservation
                write_json_atomic(self.state_path, state)
            fields = candidate["fields"]
            text = lambda name: self.text(fields, name)
            intent = text("Depicted Moment") or text("Story Beat")
            constraints = "\n".join(filter(None, (text("Continuity Requirements"), text("Exact Details to Preserve"), text("Visible Dialogue"))))
            scene_id = reservation["scene_id"]
            if self.repository.path(story_id, scene_id).exists():
                scene = self.repository.read(story_id, scene_id)
                provenance = scene.get("source_provenance", {})
                if (provenance.get("source_key"), provenance.get("candidate_id"), provenance.get("content_hash")) != (source_key, candidate_id, candidate["content_hash"]):
                    raise ValueError("Reserved candidate destination changed; review it before resuming.")
            else:
                scene = asdict(NarrativeScene(candidate["title"], id=scene_id))
                self.author._patch(scene, {"intent": intent + "\n" + constraints, "setting": text("Location"),
                    "lighting": text("Lighting")}, SCENE_FIELDS)
                scene["source_provenance"] = {"source_type": "scene_candidate_markdown", "source_key": source_key,
                    "candidate_id": candidate_id, "content_hash": candidate["content_hash"],
                    "source_session": candidate["session"], "imported_baseline": fields, "import_status": "building"}
                self.repository.write(scene, story_id, scene_id)
            if scene_id not in parent["scene_ids"]:
                parent["scene_ids"].append(scene_id)
                self.repository.write(parent, story_id)
            visible = fields.get("Visible Elements") or fields.get("Characters Present") or []
            if isinstance(visible, str):
                visible = [visible]
            hidden = fields.get("Continuity-Only Participants") or []
            if isinstance(hidden, str):
                hidden = [hidden]
            hidden = {v.strip().casefold() for v in hidden}
            names = []
            for value in [*visible, *(fields.get("Important Props / Objects") if isinstance(fields.get("Important Props / Objects"), list) else [])]:
                name = re.split(r"\s*[:—]\s*", value, maxsplit=1)[0].strip()
                if name and name.casefold() not in hidden and name not in names:
                    names.append(name)
            issues = list(candidate["warnings"])
            member_ids = []
            backdrop_ids = []
            for name in names:
                existing = next((e for e in scene["elements"] if e["name"] == name), None)
                if existing:
                    (backdrop_ids if existing["kind"] == "environment" else member_ids).append(existing["id"])
                    continue
                appearance = "\n".join(v for v in text("Known Visual Facts").splitlines() if v.casefold().startswith(name.casefold() + ":"))
                choices = [a for a in self.app.entity_library_service.list_assets(q=name) if a["status"] == "approved" and a.get("label", "").casefold() == name.casefold()]
                asset_id = choices[0]["asset_id"] if len(choices) == 1 else ""
                if not asset_id:
                    issues.append(f"Choose an exact current visual reference for {name}.")
                brief = next((str(v) for v in visible if str(v).startswith(name + ":")), "")
                kind = "environment" if "backdrop" in brief.casefold() or name.casefold() in text("Location").casefold() else "prop" if any(str(v).startswith(name) for v in fields.get("Important Props / Objects", []) if isinstance(v, str)) else "subject"
                element_id = self.author.save_element(story_id, scene["id"], {"name": name, "kind": kind, "appearance": appearance, "asset_id": asset_id})["id"]
                (backdrop_ids if kind == "environment" else member_ids).append(element_id)
            staging = "\n".join(filter(None, (text("Subject Groups"), text("Acting and Placement"), text("Visual Action"), text("Suggested Composition"), text("Reading Order"))))
            context = "\n".join(filter(None, (text("Location"), text("Atmosphere"), text("Mood"))))
            existing_kinds = {t["kind"] for t in self.author.list_targets(story_id, scene["id"])}
            if "backdrop" not in existing_kinds:
                self.author.create_target(story_id, scene["id"], {"title": "Backdrop", "kind": "backdrop", "narrative": text("Backdrop Brief") or context, "staging": text("Location"), "physical_context": context, "element_ids": backdrop_ids})
            if "subscene" not in existing_kinds:
                self.author.create_target(story_id, scene["id"], {"title": "Scene subjects", "kind": "subscene", "narrative": intent, "staging": staging, "physical_context": context, "element_ids": member_ids, "framing": text("Framing") or "Review framing"})
            if "assembly" not in existing_kinds:
                self.author.create_target(story_id, scene["id"], {"title": "Final assembly", "kind": "assembly", "narrative": intent + "\n" + constraints, "staging": staging, "physical_context": context})
            record = self.repository.read(story_id, scene["id"])
            record["source_provenance"] = {"source_type": "scene_candidate_markdown", "source_key": source_key, "candidate_id": candidate_id,
                "content_hash": candidate["content_hash"], "source_session": candidate["session"], "imported_baseline": fields, "import_status": "complete"}
            record["migration"] = {"kind": "candidate_stub", "review_issues": issues}
            self.repository.write(record, story_id, scene["id"])
            return {"story_id": story_id, "scene_id": scene["id"], "created": True, "review_issues": issues}

    def review(self, source_key, candidate_id, story_id, scene_id, acknowledge=False):
        with self.repository.lock():
            candidate = self.get_candidate(source_key, candidate_id)
            scene = self.repository.read(story_id, scene_id)
            provenance = scene.get("source_provenance", {})
            if (provenance.get("source_key"), provenance.get("candidate_id")) != (source_key, candidate_id):
                raise ValueError("This scene does not belong to this candidate.")
            result = {"previous": provenance.get("imported_baseline", provenance.get("constraints", {})), "incoming": candidate["fields"],
                      "message": "Review the source brief and edit scene inputs manually. Acknowledging preserves all authored inputs and images."}
            if acknowledge:
                provenance.update(content_hash=candidate["content_hash"], imported_baseline=candidate["fields"])
                self.repository.write(scene, story_id, scene_id)
            return result
