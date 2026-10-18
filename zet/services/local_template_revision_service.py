"""Frozen multi-view evidence, reviewed template versions and explicit promotion."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import difflib
import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4

from zet.services.atomic_file_service import write_text_atomic
from zet.services.library_reference_service import pipeline_library_root_for_path, read_library_json, write_library_json
from zet.services.template_source_service import active_revision, bind_revision_sources, template_sources
from zet.services.workflow_storage import file_lock


def _now():
    return datetime.now().astimezone().isoformat(timespec="microseconds")


def _digest(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def template_diff_rows(master: str, proposed: str) -> list[dict]:
    """Aligned, contextual source lines for the master/proposal review table."""
    before, after = master.splitlines(), proposed.splitlines()
    rows = []
    for group in difflib.SequenceMatcher(None, before, after, autojunk=False).get_grouped_opcodes(3):
        if rows:
            rows.append({"kind": "gap"})
        for kind, start, end, new_start, new_end in group:
            for offset in range(max(end - start, new_end - new_start)):
                left = start + offset if offset < end - start else None
                right = new_start + offset if offset < new_end - new_start else None
                rows.append({"kind": kind,
                             "master_line": left + 1 if left is not None else None,
                             "master_text": before[left] if left is not None else "",
                             "proposed_line": right + 1 if right is not None else None,
                             "proposed_text": after[right] if right is not None else ""})
    return rows


def compiler_guidance() -> str:
    from zet.services.view_conditioning_service import VIEW_ORDER, _sets
    return ("# Current character compiler contract\n\n"
            "Use complete existing templates; change only the requested facts/rules. Preserve section names and paired "
            "<!-- ZET:BEGIN NAME --> / <!-- ZET:END NAME --> markers and all {{PLACEHOLDER}} tokens. "
            "Generation/analysis use IMAGE_PROMPT_ONLY / ANALYSIS_PROMPT_ONLY; pipeline modes use "
            "LOCAL_PIPELINE_ONLY / TRADITIONAL_PIPELINE_ONLY. Do not nest variant/mode blocks.\n\n"
            "Inside marked source sections: <!-- ZET:VIEW_DOMAIN body --> or head chooses orientation; "
            "<!-- ZET:VIEW_DEFAULT frontish --> sets visibility. Tag individual bullets, e.g. '- [rearish] The rear hem reaches ankle height.' "
            "Use <!-- ZET:CANON_ONLY --> for canonical facts excluded from view prompts. "
            "Spatial bullets use <!-- ZET:SPATIAL asymmetry --> or <!-- ZET:SPATIAL fixed state=visible -->; "
            "fixed features require explicit visibility, and sides must be anatomical left/right. "
            "The compiler translates anatomical sides for the requested view. Hidden/occluded fixed details are omitted. "
            "Do not leak raw tags or spatial annotations into final render prompts.\n\n"
            f"Supported views: {', '.join(VIEW_ORDER)}.\nSupported tag sets (from current parser):\n"
            + json.dumps(_sets, indent=2) + "\n\n"
            "Image order and assigned roles are contracts. A reference from another view controls visible design details, "
            "not target orientation/pose/camera. Do not feed front references to rear views automatically. "
            "Report bad reference conditioning separately when prose alone cannot fix it.\n")


class LocalTemplateRevisionService:
    def __init__(self, app, project_root: str | Path):
        self.app = app
        self.project_root = Path(project_root).resolve()

    def _workflow(self, pipeline):
        from zet.services.local_image_workflow_service import LocalImagePipelineWorkflowService
        return LocalImagePipelineWorkflowService(self.app, self.project_root, pipeline)

    def _load(self, pipeline, run_id, costume=""):
        workflow = self._workflow(pipeline)
        run = workflow.prompt_improvement.detail(run_id, costume)
        return workflow, run, Path(run["root"]) / "template_improvement"

    @staticmethod
    def _read(path):
        return read_library_json(path, pipeline_library_root_for_path(path))

    @staticmethod
    def _write(path, record):
        write_library_json(path, record, pipeline_library_root_for_path(path))

    def _record(self, directory, revision_id):
        if not isinstance(revision_id, str) or not re.fullmatch(r"[a-f0-9]{32}", revision_id):
            raise ValueError("Invalid template revision identity.")
        record = self._read(directory / "revisions" / f"{revision_id}.json")
        return bind_revision_sources(record, Path(self.app.config.base_library_path), self.project_root)

    def _sources(self, workflow, run):
        character = Path(self.app.config.base_character_path) / run["character"] / run["phase"] / "Character.md"
        paths = [character, self.project_root / "Config" / "Prompt_Global_Sections.md",
                 self.project_root / "Config" / "Prompt_Templates" / f"{workflow.pipeline.replace('-', '_')}_v2.md"]
        if workflow.pipeline == "costume-dressing":
            paths.insert(0, workflow.adapter._costume_path(run["character"], run["phase"], run["costume"]))
        result = []
        library = Path(self.app.config.base_library_path).resolve()
        for path in paths:
            path = path.resolve()
            if not path.is_file():
                continue
            if path.is_relative_to(library):
                source_id = "library/" + path.relative_to(library).as_posix()
            elif path.is_relative_to(self.project_root):
                source_id = "project/" + path.relative_to(self.project_root).as_posix()
            else:
                raise ValueError("Template source is outside this universe/project.")
            text = path.read_text(encoding="utf-8")
            result.append({"source_id": source_id, "source_path": str(path), "label": path.name,
                           "text": text, "master_text": text, "master_sha256": _digest(text)})
        return result

    @staticmethod
    def representatives(run, choices=None):
        choices = choices or {}
        if not isinstance(choices, dict) or set(choices) - set(run.get("views", [])):
            raise ValueError("Representative choices must name views in this batch.")
        result, omitted = [], []
        for view in run.get("views", []):
            images = {c["candidate_id"]: c for c in run.get("candidates", []) if c["view"] == view
                      and Path(str(c.get("image_path") or "")).is_file()
                      and (c.get("human_review") or {}).get("decision") != "reject"}
            choice = choices.get(view)
            if choice == "skip":
                omitted.append({"view": view, "reason": "Excluded by operator"})
                continue
            selected = (run.get("selected_views") or {}).get(view) or (run.get("front_anchor") if view == "FRONT" else "")
            ranking = (run.get("rankings") or {}).get(view) or {}
            ordered = ranking.get("ordered_candidate_ids") or []
            ranked = ordered[0] if ranking.get("status") == "COMPLETE" and ordered else ""
            if ranked not in images or (ranking.get("input_hashes") or {}).get(ranked) != (images.get(ranked) or {}).get("image_sha256"):
                ranked = ""
            cid = choice or (selected if selected in images else ranked)
            if not cid:
                omitted.append({"view": view, "reason": "No selected image or current Luna #1"})
                continue
            if cid not in images:
                raise ValueError(f"Representative {view}/{cid} is unavailable, rejected or outside this view.")
            item = images[cid]
            image = Path(item["image_path"]).resolve()
            if not image.is_relative_to(Path(run["root"]).resolve()):
                raise ValueError("Representative image must belong to this batch.")
            reason = "explicit" if choice else "selected" if selected == cid else "Luna #1"
            result.append({"view": view, "candidate_id": cid, "image_path": str(image), "reason": reason})
        return result, omitted

    def detail(self, pipeline, run_id, costume="", revision_id=""):
        workflow, run, directory = self._load(pipeline, run_id, costume)
        reps, omitted = self.representatives(run)
        records = [self._read(path) for path in sorted((directory / "revisions").glob("*.json"))]
        records.sort(key=lambda r: r["created_at"], reverse=True)
        active = active_revision(Path(run["root"]))
        revision = self._record(directory, revision_id) if revision_id else (records[0] if records else None)
        if revision:
            if revision.get("version") == 2 and revision["status"] == "PROPOSING":
                from zet.services.ai_workflow_service import AIWorkflowService
                AIWorkflowService(self.app).submit(self._review_job, [pipeline, run_id, costume, revision["revision_id"]],
                    service="template_revision", key="template_" + revision["revision_id"], owner=revision["owner"])
            revision = deepcopy(revision)
            for source in revision["sources"]:
                source["diff"] = "".join(difflib.unified_diff(source.get("before_text", source["master_text"]).splitlines(True),
                    source["text"].splitlines(True), fromfile=source["label"] + " (before)", tofile=source["label"] + " (proposed)"))
                source["master_diff"] = "".join(difflib.unified_diff(source["master_text"].splitlines(True), source["text"].splitlines(True),
                    fromfile=source["label"] + " (master)", tofile=source["label"] + " (revision)"))
                source["master_diff_rows"] = template_diff_rows(source["master_text"], source["text"])
        return {"run_id": run_id, "active_revision_id": active.get("revision_id", ""),
                "sources": self._sources(workflow, run), "representatives": reps, "omitted_views": omitted,
                "history": [{k: item.get(k) for k in ("revision_id", "parent_revision_id", "created_at", "status", "summary", "error", "promoted_at")} for item in records],
                "revision": revision}

    def start(self, pipeline, run_id, payload, costume=""):
        workflow, run, directory = self._load(pipeline, run_id, costume)
        from zet.services.local_character_progression_service import enroll
        enroll(Path(run["root"]), run.get("views"))
        with file_lock(directory / "revisions.lock"):
            parent_id = payload.get("parent_revision_id")
            parent = self._record(directory, parent_id) if parent_id else active_revision(Path(run["root"]))
            live = self._sources(workflow, run)
            sources = deepcopy(parent["sources"] if parent else live)
            current = {s["source_id"]: s for s in live}
            for source in sources:
                if source["source_id"] not in current:
                    raise ValueError("A governing source is unavailable.")
                master = current[source["source_id"]]
                source.update(master_text=master["text"], master_sha256=master["master_sha256"],
                              source_path=master["source_path"], before_text=source["text"])
                for key in ("diff", "master_diff", "master_diff_rows"):
                    source.pop(key, None)
            editable = payload.get("source_ids", [s["source_id"] for s in sources])
            if not isinstance(editable, list) or not editable or set(editable) - set(current):
                raise ValueError("Choose existing governing templates to edit.")
            direction = payload.get("direction", "")
            if not isinstance(direction, str) or len(direction) > 20000:
                raise ValueError("Direction must be text of at most 20,000 characters.")
            manual = payload.get("replacements")
            if manual is not None:
                if not isinstance(manual, dict) or set(manual) - set(editable):
                    raise ValueError("Manual edits must name the chosen sources.")
                for source in sources:
                    if source["source_id"] in manual:
                        self._validate_text(source["text"], manual[source["source_id"]])
                        source["text"] = manual[source["source_id"]]
            model = str(payload.get("model") or "codex:" + self.app.config.codex_default_model.removeprefix("codex:"))
            if manual is None:
                from zet.services.ai_model_catalog_service import AIModelCatalogService
                AIModelCatalogService(self.app.config.base_ai_queue_path, config=self.app.config).validate(model, required=["text"])
            rid = uuid4().hex
            owner_key = {"body-reference": "local_body_reference_run_id", "head-image": "local_head_image_run_id"}.get(pipeline, "local_character_asset_run_id")
            record = {"version": 2, "revision_id": rid, "parent_revision_id": parent.get("revision_id", ""),
                "universe_id": self.app.universe_id, "pipeline": pipeline, "run_id": run_id, "created_at": _now(),
                "status": "PROPOSING", "model": model, "direction": direction, "source_ids": editable,
                "sources": sources, "representatives": [], "observations": {}, "findings": [], "selected_ids": [],
                "compiler_guidance": compiler_guidance(), "manual": manual is not None, "summary": "", "error": "",
                "owner": {owner_key: run_id, "pipeline": pipeline, "run_id": run_id, "revision_id": rid,
                    "character": run["character"], "phase": run["phase"], "costume": costume}}
            self._write(directory / "revisions" / f"{rid}.json", record)
            from zet.services.local_image_pipeline_policy import mutate_local_run_state
            def reviewing(state):
                flow = state["character_progression"]
                if flow["stage"] < 0:
                    flow["accepted_revision_id"] = ""
            mutate_local_run_state(Path(run["root"]), reviewing)
        from zet.services.ai_workflow_service import AIWorkflowService
        AIWorkflowService(self.app).submit(self._review_job, [pipeline, run_id, costume, rid],
            service="template_revision", key="template_" + rid, owner=record["owner"])
        return self.detail(pipeline, run_id, costume, rid)

    def _review_job(self, pipeline, run_id, costume, revision_id):
        workflow, run, directory = self._load(pipeline, run_id, costume)
        path = directory / "revisions" / f"{revision_id}.json"
        record = self._record(directory, revision_id)
        if record["status"] in {"REVIEW_READY", "READY", "FAILED"}:
            return
        try:
            from zet.services.local_prompt_preview_service import LocalPromptPreviewService
            if "compiled_views" not in record:
                with file_lock(Path(run["root"]) / "state.lock"):
                    if not path.is_file():
                        return
                    record["compiled_views"] = LocalPromptPreviewService(workflow).compile(run, record["sources"], directory / "compiled" / revision_id)
                    self._write(path, record)
            if "answer" not in record:
                properties = {key: {"type": "string"} for key in ("source_id", "before", "after", "rationale")}
                properties["views"] = {"type": "array", "items": {"type": "string"}}
                schema = {"type": "object", "properties": {"summary": {"type": "string"},
                    "findings": {"type": "array", "items": {"type": "object", "properties": properties,
                        "required": list(properties), "additionalProperties": False}}},
                    "required": ["summary", "findings"], "additionalProperties": False}
                prompt = ("Analyze ONLY the supplied governing template text and compiled prompts. No image analysis. "
                    "Check spelling, typos, unclear or contradictory wording and continuity across all eight views. "
                    "Respect intentional asymmetry, angle and occlusion. Propose small independently selectable corrections. "
                    "Each before must be an exact unique nonempty substring of one editable source, after its replacement. "
                    "Cite affected views and explain the problem. Do not invent design details or change intent. "
                    "Preserve markers, placeholders and reference order. Report compiler/config issues in the summary, "
                    "never change unlisted sources. Empty findings is valid. Operator instructions take precedence.\n"
                    + record["compiler_guidance"] + "\nOperator: " + record["direction"]
                    + "\nEditable source IDs: " + json.dumps(record["source_ids"])
                    + "\nSources: " + json.dumps([{k: s[k] for k in ("source_id", "text")} for s in record["sources"]], ensure_ascii=False)
                    + "\nCompiled prompts: " + json.dumps(record["compiled_views"], ensure_ascii=False))
                if record["manual"]:
                    answer = {"summary": "Manual child revision; review and accept the compiled text.", "findings": []}
                else:
                    answer, runtime = self.app.ai_proxy_service.ai_proxy_path_service.jobs.generate_json(
                        record["model"], "", prompt, schema, [], task_type="character_prompt_review",
                        workflow=pipeline, owner=record["owner"])
                    record["runtime"] = runtime
                record["answer"] = answer
            sources = {s["source_id"]: s for s in record["sources"]}
            findings = []
            for index, finding in enumerate(record["answer"]["findings"]):
                source = sources.get(finding["source_id"])
                if not source or finding["source_id"] not in record["source_ids"]:
                    raise ValueError("Correction names an unapproved source.")
                before = finding["before"]
                if not before or source["text"].count(before) != 1:
                    raise ValueError("Correction text must match one unique source location; analyze again.")
                self._validate_text(source["text"], source["text"].replace(before, finding["after"], 1))
                findings.append({**finding, "id": str(index + 1)})
            record.update(status="REVIEW_READY", findings=findings, summary=record["answer"]["summary"], completed_at=_now())
            with file_lock(Path(run["root"]) / "state.lock"):
                if not path.is_file():
                    return
                self._write(path, record)
        except Exception as exc:
            from zet.services.storage_health_service import pause_on_storage_error
            pause_on_storage_error(self.app.config, exc)
            record.update(status="FAILED", error=str(exc), completed_at=_now())
            with file_lock(Path(run["root"]) / "state.lock"):
                if not path.is_file():
                    return
                self._write(path, record)

    def decisions(self, pipeline, run_id, revision_id, payload, costume=""):
        _, _, directory = self._load(pipeline, run_id, costume)
        with file_lock(directory / "revisions.lock"):
            record = self._record(directory, revision_id)
            ids = payload.get("selected_ids", [])
            allowed = {f["id"] for f in record.get("findings", [])}
            if record["status"] != "REVIEW_READY" or not isinstance(ids, list) or set(ids) - allowed:
                raise ValueError("Choose corrections from the completed prompt review.")
            record["selected_ids"] = list(dict.fromkeys(ids))
            self._write(directory / "revisions" / f"{revision_id}.json", record)
        return self.detail(pipeline, run_id, costume, revision_id)

    def accept(self, pipeline, run_id, revision_id, payload, costume=""):
        workflow, run, directory = self._load(pipeline, run_id, costume)
        with file_lock(directory / "revisions.lock"):
            record = self._record(directory, revision_id)
            ids = payload.get("selected_ids", record.get("selected_ids", []))
            if record.get("accepted_revision_id"):
                if ids != record.get("selected_ids", []):
                    raise ValueError("This review was accepted with different choices. Create a child review.")
                return self.detail(pipeline, run_id, costume, record["accepted_revision_id"])
            if record["status"] != "REVIEW_READY" or not isinstance(ids, list) or set(ids) - {f["id"] for f in record["findings"]}:
                raise ValueError("Complete prompt analysis before accepting its corrections.")
            live = {s["source_id"]: s for s in self._sources(workflow, run)}
            sources = deepcopy(record["sources"])
            for source in sources:
                if live.get(source["source_id"], {}).get("master_sha256") != source["master_sha256"]:
                    raise ValueError("Governing source changed since analysis; analyze again before accepting.")
                original = source["text"]
                edits = []
                for finding in record["findings"]:
                    if finding["id"] in ids and finding["source_id"] == source["source_id"]:
                        start = original.index(finding["before"])
                        edits.append((start, start + len(finding["before"]), finding["after"]))
                edits.sort()
                if any(left[1] > right[0] for left, right in zip(edits, edits[1:])):
                    raise ValueError("Selected corrections overlap; choose one or request a revised analysis.")
                for start, end, after in reversed(edits):
                    source["text"] = source["text"][:start] + after + source["text"][end:]
                self._validate_text(original, source["text"])
            child_id = uuid4().hex
            from zet.services.local_prompt_preview_service import LocalPromptPreviewService
            compiled = LocalPromptPreviewService(workflow).compile(run, sources, directory / "compiled" / child_id)
            child = {**deepcopy(record), "revision_id": child_id, "parent_revision_id": revision_id,
                "status": "READY", "sources": sources, "compiled_views": compiled, "created_at": _now(),
                "selected_ids": ids, "accepted_at": _now(), "findings": []}
            child["owner"] = {**record["owner"], "revision_id": child_id}
            self._write(directory / "revisions" / f"{child_id}.json", child)
            self._write(directory / "active.json", {"revision_id": child_id, "updated_at": _now()})
            record.update(accepted_revision_id=child_id, selected_ids=ids)
            self._write(directory / "revisions" / f"{revision_id}.json", record)
            from zet.services.local_character_progression_service import accept_prompts
            accept_prompts(Path(run["root"]), child_id)
        return self.detail(pipeline, run_id, costume, child_id)

    @staticmethod
    def _prompt(record):
        evidence = [{**item, "image_path": "attached", "image_number": index} for index, item in enumerate(record["representatives"], 1)]
        observations = {}
        for view, review in record["observations"].items():
            ai = review.get("ai_observations") or {}
            observations[view] = {"human": review.get("observations", ""),
                                  "ai": ai.get("text", "") if ai.get("status") == "COMPLETE" else "Withheld: unavailable or stale"}
        return ("Improve governing character templates using targeted changes only. Return complete replacement text for changed editable sources. "
                "Operator direction and explicit human observations have priority over AI observations. Keep intended design and identity. "
                "Use one attached representative per view; discarded candidates are not targets. Existing observations describe recurrence across earlier candidates; "
                "do not claim to see their images. Do not generalize an isolated defect into a rule unless requested. "
                "Separate view-specific prompt defects, consistency between views, stochastic failures, and bad reference conditioning. "
                "Use current view tags for visibility; do not expose front details on rear surfaces or alter intended asymmetry. "
                "Cite representative view/candidate IDs and changed sections in each rationale. Do not invent new design details. "
                "If current source and submitted prompt disagree, state the uncertainty; do not silently reconstruct historical source text. "
                "Do not modify non-editable sources. Preserve section markers, placeholders, mode/variant blocks and image order contracts. "
                "No changes is valid: return an empty edits array and explain. Keep non-template recommendations separate.\n\n"
                + record["compiler_guidance"] + "\nOperator direction:\n" + record["direction"]
                + "\nEditable source IDs:\n" + json.dumps(record["source_ids"])
                + "\nCurrent complete sources:\n" + json.dumps([{k: s[k] for k in ("source_id", "text")} for s in record["sources"]], ensure_ascii=False)
                + "\nEvidence:\n" + json.dumps(evidence, ensure_ascii=False)
                + "\nObservations:\n" + json.dumps(observations, ensure_ascii=False)
                + "\nCurrent reference recipes:\n" + json.dumps(record["reference_recipes"])
                + "\nRead-only view configuration (report needed configuration changes separately):\n" + json.dumps(record["view_configuration"]))

    @staticmethod
    def _validate_text(before, after):
        if not isinstance(after, str) or not after.strip() or len(after) > 250000:
            raise ValueError("Replacement template is empty or too large.")
        markers = r"<!--\s*ZET:(?:BEGIN|END)\s+[A-Z0-9_]+\s*-->"
        placeholders = r"\{\{[^\n]+?\}\}"
        for pattern, label in ((markers, "section/variant markers"), (placeholders, "placeholders")):
            if sorted(re.findall(pattern, before)) != sorted(re.findall(pattern, after)):
                raise ValueError(f"Replacement changes compiler {label}; preserve the existing contracts.")

    def _propose_job(self, pipeline, run_id, costume, revision_id):
        workflow, run, directory = self._load(pipeline, run_id, costume)
        path = directory / "revisions" / f"{revision_id}.json"
        record = self._record(directory, revision_id)
        if record["status"] in {"READY", "FAILED"}:
            return
        try:
            if "answer" not in record:
                if record["replacements"] is not None:
                    answer = {"summary": record["direction"] or "Manual template revision", "recommendations": "",
                              "edits": [{"source_id": key, "text": text, "rationale": "Operator edit"} for key, text in record["replacements"].items()]}
                else:
                    for item in record["representatives"]:
                        if hashlib.sha256(Path(item["image_path"]).read_bytes()).hexdigest() != item["sha256"]:
                            raise ValueError("Frozen representative evidence changed; start a new revision.")
                    schema = {"type": "object", "properties": {
                        "summary": {"type": "string"}, "recommendations": {"type": "string"},
                        "edits": {"type": "array", "items": {"type": "object", "properties": {
                            key: {"type": "string"} for key in ("source_id", "text", "rationale")},
                            "required": ["source_id", "text", "rationale"], "additionalProperties": False}}},
                        "required": ["summary", "recommendations", "edits"], "additionalProperties": False}
                    answer, runtime = self.app.ai_proxy_service.ai_proxy_path_service.jobs.generate_json(
                        record["model"], "", self._prompt(record), schema,
                        [Path(item["image_path"]) for item in record["representatives"]], task_type="character_template_revision",
                        workflow=pipeline, owner=record["owner"])
                    record["runtime"] = runtime
                record["answer"] = answer
                self._write(path, record)
            answer = record["answer"]
            sources = {s["source_id"]: s for s in record["sources"]}
            seen = set()
            for edit in answer["edits"]:
                sid = edit["source_id"]
                if sid not in record["source_ids"] or sid in seen:
                    raise ValueError("Model changed an unapproved or duplicate source.")
                seen.add(sid)
                self._validate_text(sources[sid]["before_text"], edit["text"])
                sources[sid].update(text=edit["text"], rationale=edit["rationale"])
            record.update(status="VALIDATING", summary=answer["summary"], recommendations=answer["recommendations"])
            self._write(path, record)
            # Use the same compiler and ordered reference builder as individual renders.
            # Each revision gets separate artifacts; current prompts/asks remain intact.
            # Validate visibility/spatial syntax in every orientation, including
            # views with no rendered evidence or prerequisite images yet.
            from Scripts.Compile_Character_Template import load_template_sections_with_sources
            from zet.services.view_conditioning_service import condition_sections, ViewContext, VIEW_ORDER
            compiled = []
            with template_sources(record["sources"]):
                for source in record["sources"]:
                    if "/Prompt_Templates/" in source["source_path"].replace("\\", "/"):
                        continue
                    sections, provenance = load_template_sections_with_sources(source["source_path"])
                    for view in VIEW_ORDER:
                        condition_sections(sections, provenance, ViewContext(body_view=view, head_view=view))
                for view in dict.fromkeys(item["view"] for item in record["representatives"]):
                    output = directory / "compiled" / revision_id / view
                    saved = workflow.slots.prepare_input(run, view, output / "inputs", recompile=True, output_dir=output)
                    compiled.append({"view": view, "prompt": saved["prompt"], "reference_inputs": saved["references"]})
            record.update(status="READY", compiled_views=compiled, visibility_checked_views=list(VIEW_ORDER), completed_at=_now())
            self._write(path, record)
        except Exception as exc:
            from zet.services.storage_health_service import pause_on_storage_error
            pause_on_storage_error(self.app.config, exc)
            record.update(status="FAILED", error=str(exc), completed_at=_now())
            self._write(path, record)

    def activate(self, pipeline, run_id, revision_id, costume="", expected_active=None):
        _, run, directory = self._load(pipeline, run_id, costume)
        with file_lock(Path(run["root"]) / "state.lock"):
            current = active_revision(Path(run["root"]))
            if expected_active is not None and expected_active != current.get("revision_id", ""):
                raise ValueError("The active revision changed; refresh before switching templates.")
            if revision_id:
                record = self._record(directory, revision_id)
                if record["status"] != "READY":
                    raise ValueError("Compile the revision successfully before trying it.")
            if run.get("character_progression"):
                if not revision_id or not record.get("accepted_at"):
                    raise ValueError("Analyze and accept a prompt version before using it in this staged batch.")
                from zet.services.local_character_progression_service import accept_prompts
                accept_prompts(Path(run["root"]), revision_id)
            self._write(directory / "active.json", {"revision_id": revision_id, "updated_at": _now()})
        return self.detail(pipeline, run_id, costume, revision_id)

    def promote(self, pipeline, run_id, revision_id, payload, costume=""):
        workflow, run, directory = self._load(pipeline, run_id, costume)
        if payload.get("confirm") is not True:
            raise ValueError("Confirm the reviewed source edits before updating master templates.")
        with file_lock(Path(self.app.config.base_ai_queue_path) / "template_promotion.lock"):
            record = self._record(directory, revision_id)
            if record["status"] != "READY":
                raise ValueError("Only a successfully compiled revision can update master templates.")
            allowed = {s["source_id"]: s for s in self._sources(workflow, run)}
            changed = [s for s in record["sources"] if s["text"] != s["master_text"]]
            if not changed:
                raise ValueError("This revision has no master-template changes.")
            for source in changed:
                live = allowed.get(source["source_id"])
                if not live or Path(live["source_path"]).resolve() != Path(source["source_path"]).resolve():
                    raise ValueError("Template source ownership changed; start a new revision.")
                digest = _digest(live["text"])
                if digest not in {source["master_sha256"], _digest(source["text"])}:
                    raise ValueError(f"Master template changed since this revision: {source['label']}. Start a new revision before promoting.")
            # The immutable record contains every original and replacement. A journal
            # makes a partial multi-file write visible and permits explicit replay.
            record["promotion"] = {"status": "APPLYING", "started_at": _now(), "source_ids": [s["source_id"] for s in changed]}
            self._write(directory / "revisions" / f"{revision_id}.json", record)
            try:
                for source in changed:
                    digest = _digest(Path(source["source_path"]).read_text(encoding="utf-8"))
                    if digest not in {source["master_sha256"], _digest(source["text"])}:
                        raise ValueError(f"Master template changed during promotion: {source['label']}.")
                    write_text_atomic(Path(source["source_path"]), source["text"])
            except Exception as exc:
                record["promotion"].update(status="FAILED", error=str(exc))
                self._write(directory / "revisions" / f"{revision_id}.json", record)
                raise
            record["promotion"].update(status="COMPLETE", completed_at=_now())
            record["promoted_at"] = _now()
            self._write(directory / "revisions" / f"{revision_id}.json", record)
        return self.detail(pipeline, run_id, costume, revision_id)
