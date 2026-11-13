"""Explicit, candidate-backed Character.md proposals for Asset Containers."""
from __future__ import annotations

import difflib
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
from uuid import uuid4

from zet.services.atomic_file_service import write_json_atomic
from zet.services.character_asset_container_service import CharacterAssetContainerService
from zet.services.local_template_revision_service import LocalTemplateRevisionService, template_diff_rows
from zet.services.template_source_service import template_sources
from zet.services.workflow_storage import file_lock


class CharacterContainerTemplateError(ValueError):
    pass


class CharacterContainerTemplateService:
    PIPELINES = {"body-reference", "head-image", "head-image-edit", "character-assembly", "costume-dressing"}

    def __init__(self, app, project_root: str | Path):
        self.app = app
        self.project_root = Path(project_root).resolve()
        self.containers = CharacterAssetContainerService(app)

    @staticmethod
    def _hash(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def _proposal_path(self, scope: dict, proposal_id: str) -> Path:
        if len(proposal_id) != 32 or any(char not in "0123456789abcdef" for char in proposal_id):
            raise CharacterContainerTemplateError("Invalid template proposal identity.")
        root = self.containers._path(scope).parent / "template-proposals"
        return root / f"{proposal_id}.json"

    def _read(self, scope: dict, proposal_id: str) -> dict:
        path = self._proposal_path(scope, proposal_id)
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CharacterContainerTemplateError("Template proposal is unavailable.") from exc
        if value.get("scope") != scope or value.get("proposal_id") != proposal_id:
            raise CharacterContainerTemplateError("Template proposal belongs to another Asset Container.")
        return value

    @staticmethod
    def _public(record: dict) -> dict:
        public = {key: value for key, value in record.items()
                  if key not in {"master_text", "proposed_text", "sources", "answer"}}
        if record.get("schema_version") == 2:
            public["sources"] = [{k: v for k, v in source.items() if k != "text"}
                                 for source in record["sources"]]
            return public
        public["diff_rows"] = template_diff_rows(record["master_text"], record["proposed_text"])
        public["diff"] = "".join(difflib.unified_diff(
            record["master_text"].splitlines(True), record["proposed_text"].splitlines(True),
            fromfile="Character.md (current master)", tofile="Character.md (proposal)"))
        return public

    def _sources(self, scope: dict) -> list[dict]:
        character = self.containers.governing_template(scope["character"], scope["phase"],
                                                        scope["pipeline"], scope["costume"])
        paths = [character]
        if scope["pipeline"] == "costume-dressing":
            costume = next(item for item in self.app.costume_service.list_costumes(
                scope["character"], scope["phase"]) if item.slug == scope["costume"])
            paths.append(Path(costume.path).resolve())
        root = Path(self.app.config.base_character_path).resolve()
        if any(not path.is_relative_to(root) or not path.is_file() for path in paths):
            raise CharacterContainerTemplateError("A governing template is unavailable in this universe.")
        return [{"source_id": path.name, "source_path": str(path), "kind":
                 "character" if path.name == "Character.md" else "costume",
                 "text": path.read_text(encoding="utf-8"),
                 "sha256": self._hash(path.read_bytes())} for path in paths]

    @staticmethod
    def _finding_views(values: object, scope: dict) -> list[str]:
        from zet.services.view_conditioning_service import VIEW_ORDER, ViewConditioningError, _expand
        if not isinstance(values, list) or not values or any(not isinstance(value, str) for value in values):
            raise ValueError("views must be a nonempty list of view names.")
        result = set()
        expected_domain = "head" if scope["pipeline"].startswith("head-image") else "body"
        for value in values:
            if value in VIEW_ORDER:
                result.add(value)
                continue
            try:
                domain, expanded = _expand(value, path="<review>", section="views", line=1)
            except ViewConditioningError as exc:
                raise ValueError(f"Unknown affected view {value!r}.") from exc
            if domain and domain != expected_domain:
                raise ValueError(f"Affected view {value!r} belongs to the {domain} domain.")
            result.update(expanded)
        return [view for view in VIEW_ORDER if view in result]

    @classmethod
    def _review_findings(cls, answer: dict, record: dict) -> tuple[list[dict], list[dict]]:
        sources = {source["source_id"]: source for source in record["sources"]}
        accepted, rejected = [], []
        for index, finding in enumerate(answer["findings"], 1):
            source_id = finding.get("source_id") if isinstance(finding, dict) else None
            reasons = []
            source = sources.get(source_id) if isinstance(source_id, str) else None
            if not source or source_id not in record["source_ids"]:
                reasons.append("Source is not selected for this review.")
            before = finding.get("before") if isinstance(finding, dict) else None
            after = finding.get("after") if isinstance(finding, dict) else None
            rationale = finding.get("rationale") if isinstance(finding, dict) else None
            if not isinstance(before, str) or not before or not isinstance(after, str) or before == after or not isinstance(rationale, str):
                reasons.append("Correction needs distinct nonempty before/after text and a rationale.")
            elif source:
                if source["text"].count(before) != 1:
                    reasons.append("Before text must match exactly one location in the selected source.")
                else:
                    replacement = source["text"].replace(before, after, 1)
                    try:
                        LocalTemplateRevisionService._validate_text(source["text"], replacement)
                        LocalTemplateRevisionService._validate_owned(record["pipeline"], source, source["text"], replacement)
                    except ValueError as exc:
                        reasons.append(str(exc))
            raw_views = finding.get("views") if isinstance(finding, dict) else None
            try:
                views = cls._finding_views(raw_views, record["scope"])
            except ValueError as exc:
                views = []
                reasons.append(str(exc))
            if reasons:
                rejected.append({"number": index, "source_id": str(source_id or "")[:100],
                                 "reported_views": [str(item)[:80] for item in raw_views[:16]] if isinstance(raw_views, list) else [],
                                 "reasons": [reason[:300] for reason in reasons]})
            else:
                accepted.append({**finding, "id": str(index), "views": views})
        return accepted, rejected

    def start_review(self, character: str, phase: str, pipeline: str, costume: str,
                     payload: dict) -> dict:
        container = self.containers.detail(character, phase, pipeline, costume)
        scope = container["scope"]
        mode = payload.get("mode", "text")
        direction = payload.get("direction", "")
        if mode not in {"text", "candidate"} or not isinstance(direction, str) or len(direction) > 20000:
            raise CharacterContainerTemplateError("Choose text or candidate analysis and a valid direction.")
        if payload.get("expected_revision") != container["revision"]:
            raise CharacterContainerTemplateError("The container changed. Refresh before analyzing templates.")
        sources = self._sources(scope)
        selected = payload.get("source_ids", [source["source_id"] for source in sources])
        if (not isinstance(selected, list) or not selected or len(set(selected)) != len(selected)
                or set(selected) - {source["source_id"] for source in sources}):
            raise CharacterContainerTemplateError("Choose governing templates in this container.")
        candidate = None
        evidence_path = ""
        view = str(payload.get("view") or "")
        candidate_id = str(payload.get("candidate_id") or "")
        if mode == "candidate":
            board = container["boards"].get(view) or {}
            candidate = (board.get("candidates") or {}).get(candidate_id)
            if (not candidate or candidate_id not in board.get("slots", [])
                    or candidate.get("status") != "COMPLETE"):
                raise CharacterContainerTemplateError("Choose a finished candidate from this container.")
            evidence = Path(str(candidate.get("image_path") or "")).resolve()
            if not evidence.is_relative_to(self.containers._path(scope).parent) or not evidence.is_file():
                raise CharacterContainerTemplateError("The candidate image is unavailable.")
            request = candidate.get("render_request") or {}
            if (request.get("universe_id") != scope["universe_id"]
                    or request.get("target_id") != f"{container['container_id']}:{view}"
                    or request.get("candidate_id") != candidate_id):
                raise CharacterContainerTemplateError("Candidate production evidence does not match this view.")
            from zet.services.render_slot_service import verify_input
            verify_input({"references": request.get("inputs", [])})
        elif view or candidate_id:
            raise CharacterContainerTemplateError("Text analysis does not use candidate evidence.")
        proposal_id = uuid4().hex
        directory = self._proposal_path(scope, proposal_id).parent / proposal_id
        directory.mkdir(parents=True, exist_ok=False)
        if candidate:
            evidence_copy = directory / f"evidence{evidence.suffix.lower()}"
            shutil.copy2(evidence, evidence_copy)
            evidence_path = str(evidence_copy)
        record = {"schema_version": 2, "proposal_id": proposal_id, "container_id": container["container_id"],
                  "scope": scope, "pipeline": pipeline, "mode": mode, "direction": direction,
                  "model": str(payload.get("model") or ""), "source_ids": selected, "sources": sources,
                  "view": view, "candidate_id": candidate_id, "candidate_request": candidate.get("render_request") if candidate else None,
                  "render_mode": candidate.get("render_mode", "draft") if candidate else "draft",
                  "evidence_path": evidence_path,
                  "evidence_sha256": self._hash(Path(evidence_path).read_bytes()) if evidence_path else "",
                  "status": "PROPOSING", "findings": [], "selected_ids": [], "created_at": datetime.now().astimezone().isoformat()}
        write_json_atomic(self._proposal_path(scope, proposal_id), record)
        from zet.services.ai_workflow_service import AIWorkflowService
        AIWorkflowService(self.app).submit(self._review_job, [scope, proposal_id], service="container_template_revision",
            key="container_template_" + proposal_id, owner={"container_id": container["container_id"], "proposal_id": proposal_id})
        return self._public(record)

    def _review_job(self, scope: dict, proposal_id: str) -> None:
        path = self._proposal_path(scope, proposal_id)
        record = self._read(scope, proposal_id)
        if record["status"] != "PROPOSING":
            return
        stage = "compile prompts"
        try:
            from zet.services.llm_role_service import resolve_role_model
            from zet.services.character_container_text_preview_service import CharacterContainerTextPreviewService
            preview = CharacterContainerTextPreviewService(self.app, self.project_root)
            if record["mode"] == "text":
                prompts = preview.compile(scope, path.parent / proposal_id / "current", record["sources"])
                images = []
            else:
                request = record["candidate_request"]
                prompts = [{"view": record["view"], "prompt": request.get("prompt", ""),
                            "reference_inputs": request.get("inputs", [])}]
                images = [Path(record["evidence_path"])]
            schema = {"type": "object", "properties": {"summary": {"type": "string"},
                "findings": {"type": "array", "items": {"type": "object", "properties": {
                    "source_id": {"type": "string"}, "before": {"type": "string"},
                    "after": {"type": "string"}, "rationale": {"type": "string"},
                    "views": {"type": "array", "items": {"type": "string", "enum": scope["views"]}}},
                    "required": ["source_id", "before", "after", "rationale", "views"],
                    "additionalProperties": False}}}, "required": ["summary", "findings"],
                    "additionalProperties": False}
            prompt = ("Suggest focused, independent exact-text corrections to selected governing templates. "
                "Return no findings when no justified edit exists. Preserve identity, markers, placeholders, "
                "view annotations and reference order. Do not edit unselected sources. "
                "Write the summary as one sentence and keep each finding rationale brief. "
                "Use the shortest exact before excerpt that matches once in its source, adding enough surrounding "
                "text to disambiguate repeated wording. Keep each after replacement focused on the correction, "
                "update every conflicting editable occurrence relevant to the request, and group views that share "
                "the same edit. Omit unchanged text and full-section rewrites. "
                "Report affected views using only these "
                f"full names: {', '.join(scope['views'])}; views are not source tags or pipeline names. "
                + ("Use the editable sources and compiled prompts as evidence. No baseline image is supplied. "
                   if record["mode"] == "text" else "Use the attached candidate image as additional evidence. ")
                + ("For Head Image Edit, change only text inside HEAD_EDIT_* sections of Character.md. "
                   "Other Character.md sections are read-only context. "
                   if scope["pipeline"] == "head-image-edit" else "") + "\n"
                f"Pipeline: {scope['pipeline']}; mode: {record['mode']}; direction: {record['direction']}\n"
                f"Editable sources: {record['source_ids']}\n"
                f"Sources: {[(s['source_id'], s['text']) for s in record['sources']]}\n"
                f"Compiled prompts: {prompts}")
            model = str(resolve_role_model(self.app.config, "character_prompt_review", record["model"]))
            stage = "model response"
            answer, runtime = self.app.ai_proxy_service.ai_proxy_path_service.jobs.generate_json(
                model, "", prompt, schema, images, task_type="character_template_revision",
                role="template_revision", render_context={"operation": "mixed", "bindings_owned_by_zet": True},
                workflow=scope["pipeline"], owner={"container_id": record["container_id"], "proposal_id": proposal_id})
            if not isinstance(answer, dict) or not isinstance(answer.get("summary"), str) or not isinstance(answer.get("findings"), list):
                raise ValueError("Template analysis returned an invalid response.")
            stage = "validate findings"
            findings, rejected = self._review_findings(answer, record)
            record.update(status="REVIEW_READY" if findings or not answer["findings"] else "FAILED",
                          findings=findings, rejected_findings=rejected, summary=answer["summary"],
                          runtime=runtime, current_prompts=prompts, model=model)
            if record["status"] == "FAILED":
                record.update(error="All proposed corrections were rejected.", failure_stage=stage)
        except Exception as exc:
            record.update(status="FAILED", error=str(exc), failure_stage=stage)
        write_json_atomic(path, record)

    def propose(self, character: str, phase: str, pipeline: str, costume: str,
                view: str, candidate_id: str, *, direction: str = "", model: str = "",
                expected_revision: int) -> dict:
        if pipeline not in self.PIPELINES:
            raise CharacterContainerTemplateError("Choose a character Asset Container.")
        if not isinstance(direction, str) or len(direction) > 20000:
            raise CharacterContainerTemplateError("Improvement direction must be text of at most 20,000 characters.")
        container = self.containers.detail(character, phase, pipeline, costume)
        if container["revision"] != expected_revision:
            raise CharacterContainerTemplateError("The container changed. Refresh before proposing a template edit.")
        board = container["boards"].get(view)
        candidate = (board or {}).get("candidates", {}).get(candidate_id)
        if not candidate or candidate_id not in board["slots"] or candidate.get("status") != "COMPLETE":
            raise CharacterContainerTemplateError("Choose a finished candidate from this view as evidence.")
        evidence = Path(str(candidate.get("image_path") or "")).resolve()
        if not evidence.is_relative_to(self.containers._path(container["scope"]).parent) or not evidence.is_file():
            raise CharacterContainerTemplateError("The candidate image is unavailable in this Asset Container.")
        request = candidate.get("render_request") or {}
        if (request.get("universe_id") != container["scope"]["universe_id"]
                or request.get("target_id") != f"{container['container_id']}:{view}"
                or request.get("candidate_id") != candidate_id):
            raise CharacterContainerTemplateError("Candidate production evidence does not match this view.")
        from zet.services.render_slot_service import verify_input
        try:
            verify_input({"references": request.get("inputs", [])})
        except (OSError, ValueError, KeyError) as exc:
            raise CharacterContainerTemplateError(f"Candidate input snapshots are unavailable: {exc}") from exc

        source = self.containers.governing_template(character, phase, pipeline, costume)
        raw = source.read_bytes()
        before = raw.decode("utf-8")
        source_hash = self._hash(raw)
        proposal_id = uuid4().hex
        directory = self._proposal_path(container["scope"], proposal_id).parent / proposal_id
        directory.mkdir(parents=True, exist_ok=False)
        evidence_copy = directory / f"evidence{evidence.suffix.lower()}"
        shutil.copy2(evidence, evidence_copy)
        evidence_hash = self._hash(evidence_copy.read_bytes())
        prompt = ("Review this finished character candidate and its exact submitted prompt. Suggest a focused revision to "
            "the editable Character.md source that could improve future renders. The image is evidence, not a target to "
            "recreate. Preserve intentional design, markers, placeholders, reference order, and all unrelated source text. "
            "Do not change character identity or add unsupported design facts. Return the complete replacement Character.md "
            "text only in the replacement field. If no justified edit exists, return the original text unchanged and explain.\n\n"
            f"Pipeline: {pipeline}; view: {view}; candidate: {candidate_id}; quality: {candidate.get('render_mode', 'draft')}\n"
            f"Operator direction: {direction}\nSubmitted prompt:\n{request.get('prompt') or candidate.get('prompt') or ''}\n\n"
            f"Current complete Character.md:\n{before}")
        schema = {"type": "object", "properties": {"summary": {"type": "string"},
            "rationale": {"type": "string"}, "replacement": {"type": "string"}},
            "required": ["summary", "rationale", "replacement"], "additionalProperties": False}
        from zet.services.llm_role_service import resolve_role_model
        selected_model = str(resolve_role_model(self.app.config, "character_prompt_review", model))
        try:
            answer, runtime = self.app.ai_proxy_service.ai_proxy_path_service.jobs.generate_json(
                selected_model, "", prompt, schema, [evidence_copy],
                task_type="character_template_revision", role="template_revision",
                render_context={"operation": "mixed", "bindings_owned_by_zet": True},
                workflow=pipeline, owner={"container_id": container["container_id"],
                    "candidate_id": candidate_id, "view": view, "proposal_id": proposal_id})
        except Exception:
            shutil.rmtree(directory, ignore_errors=True)
            raise
        try:
            if not isinstance(answer, dict) or any(not isinstance(answer.get(key), str)
                    for key in ("summary", "rationale", "replacement")):
                raise ValueError("Template review returned an invalid proposal.")
            replacement = answer["replacement"]
            LocalTemplateRevisionService._validate_text(before, replacement)
            LocalTemplateRevisionService._validate_owned(pipeline,
                {"source_path": str(source)}, before, replacement)
            from zet.services.template_validation_service import TemplateValidationService
            analysis = TemplateValidationService(self.app).analyze(source, replacement, "character")
            if analysis["diagnostics"]:
                errors = "; ".join(item["message"] for item in analysis["diagnostics"][:5])
                raise ValueError(f"Proposed template does not validate: {errors}")
            from zet.services.character_container_prompt_service import CharacterContainerPromptService
            provenance = request.get("provenance") or {}
            preview_dir = directory / "compiled" / view
            with template_sources([{"source_path": str(source), "text": replacement}]):
                preview = CharacterContainerPromptService(self.app, self.project_root).compile(
                    container["scope"], view, preview_dir, request.get("inputs", []),
                    apply_phase_change=provenance.get("apply_phase_change") is True,
                    assembly_style_mode=str(provenance.get("assembly_style_mode") or ""),
                    render_mode=str(candidate.get("render_mode") or "draft"),
                    costume_settings=provenance.get("costume_settings"))
        except Exception as exc:
            shutil.rmtree(directory, ignore_errors=True)
            raise CharacterContainerTemplateError(str(exc)) from exc
        record = {"schema_version": 1, "proposal_id": proposal_id,
            "container_id": container["container_id"], "scope": container["scope"],
            "pipeline": pipeline, "view": view, "candidate_id": candidate_id,
            "render_mode": candidate.get("render_mode", "draft"),
            "created_at": datetime.now().astimezone().isoformat(timespec="microseconds"),
            "status": "PROPOSED", "model": selected_model,
            "summary": answer["summary"], "rationale": answer["rationale"],
            "direction": direction, "evidence_path": str(evidence_copy),
            "evidence_sha256": evidence_hash, "submitted_prompt": str(request.get("prompt") or candidate.get("prompt") or ""),
            "master_path": str(source), "master_sha256": source_hash, "master_text": before,
            "proposed_text": replacement, "compiled_prompt": preview["prompt"],
            "compiled_references": preview["reference_inputs"], "template_revision_id": preview.get("template_revision_id", ""),
            "runtime": runtime}
        write_json_atomic(self._proposal_path(container["scope"], proposal_id), record)
        return self._public(record)

    def detail(self, character: str, phase: str, pipeline: str, costume: str,
               proposal_id: str) -> dict:
        scope = self.containers._scope(character, phase, pipeline, costume)
        return self._public(self._read(scope, proposal_id))

    def latest(self, character: str, phase: str, pipeline: str, costume: str) -> dict:
        scope = self.containers._scope(character, phase, pipeline, costume)
        root = self.containers._path(scope).parent / "template-proposals"
        records = []
        for path in root.glob("*.json") if root.is_dir() else ():
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if value.get("scope") == scope and value.get("proposal_id") == path.stem:
                records.append(value)
        records.sort(key=lambda value: value.get("created_at") or "", reverse=True)
        return {"proposal": self._public(records[0]) if records else None}

    def _selected(self, record: dict, ids: list[str]) -> list[dict]:
        if record.get("schema_version") != 2 or record["status"] not in {"REVIEW_READY", "ACCEPTED"}:
            raise CharacterContainerTemplateError("Wait for template suggestions before selecting edits.")
        if (not isinstance(ids, list) or len(set(ids)) != len(ids)
                or set(ids) - {finding["id"] for finding in record["findings"]}):
            raise CharacterContainerTemplateError("Choose findings from this review.")
        sources = [dict(source) for source in record["sources"]]
        by_id = {source["source_id"]: source for source in sources}
        edits = {}
        for finding in record["findings"]:
            if finding["id"] not in ids:
                continue
            source = by_id[finding["source_id"]]
            before = finding["before"]
            if source["text"].count(before) != 1:
                raise CharacterContainerTemplateError("A selected correction is no longer unique.")
            start = source["text"].index(before)
            edits.setdefault(source["source_id"], []).append((start, start + len(before), finding["after"]))
        from zet.services.template_validation_service import TemplateValidationService
        for source in sources:
            ranges = sorted(edits.get(source["source_id"], []))
            if any(left[1] > right[0] for left, right in zip(ranges, ranges[1:])):
                raise CharacterContainerTemplateError("Selected corrections overlap.")
            replacement = source["text"]
            for start, end, after in reversed(ranges):
                replacement = replacement[:start] + after + replacement[end:]
            if replacement != source["text"]:
                LocalTemplateRevisionService._validate_text(source["text"], replacement)
                LocalTemplateRevisionService._validate_owned(record["pipeline"], source, source["text"], replacement)
                diagnostics = TemplateValidationService(self.app).analyze(
                    Path(source["source_path"]), replacement, source["kind"])["diagnostics"]
                if diagnostics:
                    raise CharacterContainerTemplateError(diagnostics[0]["message"])
            source["replacement"] = replacement
        return sources

    def decide(self, character: str, phase: str, pipeline: str, costume: str,
               proposal_id: str, ids: list[str]) -> dict:
        scope = self.containers._scope(character, phase, pipeline, costume)
        path = self._proposal_path(scope, proposal_id)
        with file_lock(path.with_suffix(".lock")):
            record = self._read(scope, proposal_id)
            sources = self._selected(record, ids)
            if record["status"] == "ACCEPTED" and ids != record["selected_ids"]:
                raise CharacterContainerTemplateError("This review was accepted with different choices.")
            from zet.services.character_container_text_preview_service import CharacterContainerTextPreviewService
            previewer = CharacterContainerTextPreviewService(self.app, self.project_root)
            overlays = [{"source_path": source["source_path"], "text": source["replacement"]}
                        for source in sources]
            if record["mode"] == "text":
                previews = previewer.compile(scope, path.parent / proposal_id / "selected", overlays)
            else:
                from zet.services.character_container_prompt_service import CharacterContainerPromptService
                request = record["candidate_request"]
                with template_sources(overlays):
                    compiled = CharacterContainerPromptService(self.app, self.project_root).compile(
                        scope, record["view"], path.parent / proposal_id / "selected" / record["view"],
                        request.get("inputs", []), render_mode=record["render_mode"],
                        apply_phase_change=(request.get("provenance") or {}).get("apply_phase_change") is True,
                        assembly_style_mode=str((request.get("provenance") or {}).get("assembly_style_mode") or ""),
                        costume_settings=(request.get("provenance") or {}).get("costume_settings"))
                previews = [compiled]
            record["selected_ids"] = ids
            record["previews"] = previews
            record["diffs"] = [{"source_id": source["source_id"], "rows": template_diff_rows(
                source["text"], source["replacement"])} for source in sources]
            write_json_atomic(path, record)
            return self._public(record)

    def accept_review(self, character: str, phase: str, pipeline: str, costume: str,
                      proposal_id: str, *, confirm: bool) -> dict:
        if not confirm:
            raise CharacterContainerTemplateError("Confirm the reviewed edits before updating masters.")
        scope = self.containers._scope(character, phase, pipeline, costume)
        path = self._proposal_path(scope, proposal_id)
        from zet.services.source_editor_service import SourceEditorService
        editor = SourceEditorService(self.app, self.project_root)
        with file_lock(path.with_suffix(".lock")):
            record = self._read(scope, proposal_id)
            if record.get("status") == "ACCEPTED":
                return self._public(record)
            if "previews" not in record:
                raise CharacterContainerTemplateError("Review selected edits and prompt previews before accepting.")
            sources = self._selected(record, record["selected_ids"])
            current = {source["source_id"]: source for source in self._sources(scope)}
            changed = [source for source in sources if source["replacement"] != source["text"]]
            for source in sources:
                live = current.get(source["source_id"])
                if (not live or live["source_path"] != source["source_path"]
                        or (live["sha256"] != source["sha256"]
                            and live["text"].replace("\r\n", "\n") != source["replacement"])):
                    raise CharacterContainerTemplateError("A governing master changed. Analyze again from current masters.")
            record["promotion"] = {"status": "APPLYING", "source_ids": [s["source_id"] for s in changed]}
            write_json_atomic(path, record)
            try:
                for source in changed:
                    if Path(source["source_path"]).read_text(encoding="utf-8").replace("\r\n", "\n") == source["replacement"]:
                        continue  # A prior partial promotion already saved this exact source.
                    result = editor.save({"path": source["source_path"], "editor_type": "markdown_file",
                        "text": source["replacement"], "master_revision": source["sha256"]})
                    if result.get("status") != "SAVED":
                        raise CharacterContainerTemplateError(result.get("message") or "Master save failed.")
            except Exception as exc:
                record["promotion"] = {"status": "FAILED", "error": str(exc),
                                       "source_ids": [s["source_id"] for s in changed]}
                write_json_atomic(path, record)
                raise
            record.update(status="ACCEPTED", accepted_at=datetime.now().astimezone().isoformat(),
                          promotion={"status": "COMPLETE", "source_ids": [s["source_id"] for s in changed]})
            write_json_atomic(path, record)
            return self._public(record)

    def accept(self, character: str, phase: str, pipeline: str, costume: str,
               proposal_id: str, *, confirm: bool) -> dict:
        if confirm is not True:
            raise CharacterContainerTemplateError("Confirm the reviewed Character.md proposal before saving it.")
        scope = self.containers._scope(character, phase, pipeline, costume)
        path = self._proposal_path(scope, proposal_id)
        record = self._read(scope, proposal_id)
        if record.get("status") == "ACCEPTED":
            return self._public(record)
        if record.get("status") != "PROPOSED":
            raise CharacterContainerTemplateError("This template proposal is no longer available for acceptance.")
        evidence = Path(record["evidence_path"]).resolve()
        if (not evidence.is_relative_to(path.parent / proposal_id)
                or not evidence.is_file()
                or self._hash(evidence.read_bytes()) != record.get("evidence_sha256")):
            raise CharacterContainerTemplateError("The saved candidate evidence changed; create a new proposal.")
        current = Path(record["master_path"]).resolve()
        if not current.is_file():
            raise CharacterContainerTemplateError("The governing Character.md is unavailable.")
        current_hash = self._hash(current.read_bytes())
        if current_hash == self._hash(record["proposed_text"].encode("utf-8")):
            record.update(status="ACCEPTED", accepted_at=datetime.now().astimezone().isoformat(timespec="microseconds"))
            write_json_atomic(path, record)
            return self._public(record)
        if current_hash != record.get("master_sha256"):
            raise CharacterContainerTemplateError("Character.md changed since this proposal. Review the current master and create a new proposal.")
        from zet.services.source_editor_service import SourceEditorService
        result = SourceEditorService(self.app, self.project_root).save({
            "path": str(current), "editor_type": "markdown_file", "text": record["proposed_text"],
            "master_revision": current_hash})
        if result.get("status") != "SAVED":
            raise CharacterContainerTemplateError(result.get("message") or "The proposed Character.md could not be saved.")
        record.update(status="ACCEPTED", accepted_at=datetime.now().astimezone().isoformat(timespec="microseconds"),
                      accepted_master_sha256=result.get("master_revision", ""))
        write_json_atomic(path, record)
        return self._public(record)
