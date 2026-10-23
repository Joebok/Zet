"""Private, observation-led Character.md proposals and render trials."""
from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime
import hashlib
from pathlib import Path
import random
import shutil
from uuid import uuid4

from zet.services.atomic_file_service import write_bytes_atomic, write_text_atomic
from zet.services.library_reference_service import pipeline_library_root_for_path, read_library_json, write_library_json
from zet.services.local_template_revision_service import LocalTemplateRevisionService, template_diff_rows
from zet.services.template_source_service import active_revision, template_sources
from zet.services.workflow_storage import file_lock


def _now():
    return datetime.now().astimezone().isoformat(timespec="microseconds")


def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class LocalPostRenderPromptService:
    def __init__(self, app, project_root):
        self.app = app
        self.project_root = Path(project_root).resolve()
        self.revisions = LocalTemplateRevisionService(app, project_root)

    def _context(self, pipeline, run_id, costume=""):
        if pipeline not in {"body-reference", "head-image", "head-image-edit", "character-assembly", "costume-dressing"}:
            raise ValueError("Unknown character pipeline.")
        return self.revisions._load(pipeline, run_id, costume)[:2]

    def _path(self, run, session_id):
        if len(str(session_id)) != 32 or any(c not in "0123456789abcdef" for c in str(session_id)):
            raise ValueError("Invalid improvement session.")
        return Path(run["root"]) / "post_render_prompt" / session_id / "session.json"

    def _read(self, run, session_id):
        path = self._path(run, session_id)
        record = read_library_json(path, pipeline_library_root_for_path(path))
        if record["universe_id"] != self.app.universe_id or record["run_id"] != run["run_id"]:
            raise ValueError("Improvement session does not belong to this batch.")
        return record

    def _write(self, run, record):
        path = self._path(run, record["session_id"])
        write_library_json(path, record, pipeline_library_root_for_path(path))

    @staticmethod
    def _character_source(sources):
        matches = [source for source in sources if source["source_id"].endswith("/Character.md")]
        if len(matches) != 1:
            raise ValueError("Exactly one Character.md source is required.")
        return matches[0]

    def _submit(self, method, args, key, owner):
        from zet.services.ai_workflow_service import AIWorkflowService
        AIWorkflowService(self.app).submit(method, args, service="post_render_prompt", key=key, owner=owner)

    def open(self, pipeline, run_id, costume="", payload=None):
        workflow, run = self._context(pipeline, run_id, costume)
        payload = payload or {}
        view = str(payload.get("view") or "").upper()
        if view not in run["views"]:
            raise ValueError("Choose a batch view for Post Render Adjustments.")
        root = Path(run["root"])
        state = read_library_json(root / "state.json", pipeline_library_root_for_path(root))
        existing = str((state.get("post_render_prompt_sessions") or {}).get(view) or "")
        if existing:
            try:
                record = self._read(run, existing)
                if record.get("view") == view and record["status"] not in {"CANCELLED", "KEPT"}:
                    return self.detail(pipeline, run_id, costume, existing)
            except FileNotFoundError:
                pass
        choices = dict(payload.get("representatives") or {})
        representatives, omitted = self.revisions.representatives(run, choices)
        for item in omitted:
            omitted_view = item["view"]
            if omitted_view == view and omitted_view not in choices:
                available = next((c for c in run["candidates"] if c["view"] == omitted_view
                                  and Path(str(c.get("image_path") or "")).is_file()
                                  and (c.get("human_review") or {}).get("decision") != "reject"), None)
                if available:
                    choices[omitted_view] = available["candidate_id"]
        representatives, _ = self.revisions.representatives(run, choices)
        representatives = [item for item in representatives if item["view"] == view]
        if not representatives:
            raise ValueError("Render this view before starting Post Render Adjustments.")
        active = active_revision(Path(run["root"]))
        sources = deepcopy(active.get("sources") or self.revisions._sources(workflow, run))
        character = self._character_source(sources)
        master = Path(character["source_path"])
        master_bytes = master.read_bytes()
        session_id = uuid4().hex
        path = self._path(run, session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        frozen = []
        for item in representatives:
            source = Path(item["image_path"])
            target = path.parent / "evidence" / f"{item['view']}{source.suffix.lower()}"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            candidate = next(c for c in run["candidates"] if c["candidate_id"] == item["candidate_id"])
            prompt_path = Path(str(candidate.get("prompt_path") or ""))
            saved_prompt = (candidate.get("render_input") or {}).get("prompt") or candidate.get("prompt") or (
                prompt_path.read_text(encoding="utf-8") if prompt_path.is_file() else "")
            frozen.append({"view": item["view"], "candidate_id": item["candidate_id"],
                           "path": str(target), "sha256": _hash(target.read_bytes()), "reason": item["reason"],
                           "prompt": str(saved_prompt)})
        record = {"version": 1, "session_id": session_id, "universe_id": self.app.universe_id,
                  "pipeline": pipeline, "run_id": run_id, "costume": costume, "view": view,
                  "created_at": _now(), "status": "OBSERVING", "round": 0,
                  "base_revision_id": active.get("revision_id", ""), "sources": sources,
                  "character_source_id": character["source_id"], "master_sha256": _hash(master_bytes),
                  "master_before_text": master.read_text(encoding="utf-8"),
                  "base_text": character["text"], "current_text": character["text"], "representatives": frozen,
                  "analysis": {}, "trial": {}, "history": [], "error": ""}
        with file_lock(Path(run["root"]) / "state.lock"):
            self._write(run, record)
            from zet.services.local_image_pipeline_policy import mutate_local_run_state
            def remember(state):
                sessions = dict(state.get("post_render_prompt_sessions") or {})
                sessions[view] = session_id
                state["post_render_prompt_sessions"] = sessions
            mutate_local_run_state(Path(run["root"]), remember)
        return self.detail(pipeline, run_id, costume, session_id)

    def detail(self, pipeline, run_id, costume, session_id):
        workflow, run = self._context(pipeline, run_id, costume)
        record = self._read(run, session_id)
        if record["pipeline"] != pipeline or record["costume"] != costume:
            raise ValueError("Improvement session context changed.")
        if record["status"] == "CANCELLED":
            return {"session_id": session_id, "status": "CANCELLED", "run_id": run_id, "pipeline": pipeline}
        if record["status"] == "ANALYZING":
            self._submit(self._analysis_job, [pipeline, run_id, costume, session_id, record["round"]],
                         "post_analyze_" + session_id + "_" + str(record["round"]), self._owner(record))
        if record["status"] == "TRIAL_RUNNING":
            for attempt in record["trial"].get("attempts", []):
                if attempt["status"] == "QUEUED":
                    self._submit(self._render_job, [pipeline, run_id, costume, session_id, attempt["id"]],
                                 "post_render_" + attempt.get("workflow_key", attempt["id"]), self._owner(record))
        public = deepcopy(record)
        for item in public["sources"]:
            item.pop("text", None)
            item.pop("master_text", None)
        public.pop("master_sha256", None)
        public.pop("master_before_text", None)
        public.pop("base_text", None)
        public.pop("current_text", None)
        visible_views = [record["view"]] if record.get("view") else run["views"]
        public["observations"] = {view: run.get("view_reviews", {}).get(view, {}) for view in visible_views}
        public["views"] = [{"view": view, "candidates": [{"candidate_id": c["candidate_id"],
            "image_available": bool(c.get("image_available") or Path(str(c.get("image_path") or "")).is_file()),
            "selected": c["candidate_id"] == (run.get("selected_views") or {}).get(view)}
            for c in run["candidates"] if c["view"] == view]} for view in visible_views]
        proposed_text = record.get("trial", {}).get("text") or record["current_text"]
        if record["status"] == "REVIEW_READY":
            selected = set(record["analysis"].get("selected_ids") or [])
            findings = [finding for finding in record["analysis"].get("findings", []) if finding["id"] in selected]
            edits = sorted((record["current_text"].index(finding["before"]), finding["before"], finding["after"])
                           for finding in findings)
            if all(left[0] + len(left[1]) <= right[0] for left, right in zip(edits, edits[1:])):
                for start, before, after in reversed(edits):
                    proposed_text = proposed_text[:start] + after + proposed_text[start + len(before):]
        public["diff_rows"] = template_diff_rows(record.get("base_text", self._character_source(record["sources"])["text"]), proposed_text)
        public["history"] = [{"round": item["round"], "trial_id": item["trial_id"]} for item in public["history"]]
        public.get("trial", {}).pop("sources", None)
        public.get("trial", {}).pop("text", None)
        public.get("trial", {}).pop("preview", None)
        for item in public["representatives"]:
            item.pop("path", None)
        for item in public.get("trial", {}).get("attempts", []):
            item.pop("payload", None)
            item.pop("input", None)
            item.pop("image_path", None)
        return public

    @staticmethod
    def _owner(record):
        return {"pipeline": record["pipeline"], "run_id": record["run_id"],
                "post_render_prompt_session_id": record["session_id"]}

    def propose(self, pipeline, run_id, costume, session_id, payload):
        _, run = self._context(pipeline, run_id, costume)
        path = self._path(run, session_id)
        with file_lock(path.with_suffix(".lock")):
            record = self._read(run, session_id)
            if record["status"] not in {"OBSERVING", "TRIAL_READY", "REVIEW_READY", "FAILED"}:
                raise ValueError("Finish or cancel the current improvement step first.")
            if record["status"] == "TRIAL_READY" and any(a["status"] != "READY" for a in record["trial"]["attempts"]):
                raise ValueError("Retry failed trial renders before refining again.")
            if record["status"] == "TRIAL_READY":
                record["current_text"] = record["trial"]["text"]
                record["sources"] = deepcopy(record["trial"]["sources"])
            direction = payload.get("direction", "")
            if not isinstance(direction, str) or len(direction) > 20000:
                raise ValueError("Direction must be text of at most 20,000 characters.")
            record["round"] += 1
            record["status"] = "ANALYZING"
            observations = {}
            for view in ([record["view"]] if record.get("view") else run["views"]):
                review = (run.get("view_reviews") or {}).get(view) or {}
                ai = review.get("ai_observations") or {}
                observations[view] = {"human": str(review.get("observations") or ""),
                    "ai": str(ai.get("text") or "") if ai.get("status") == "COMPLETE" else "",
                    "ai_status": str(ai.get("status") or "PENDING")}
            record["analysis"] = {"status": "QUEUED", "direction": direction, "observations": observations,
                                  "findings": [], "selected_ids": [], "error": ""}
            record["error"] = ""
            self._write(run, record)
        self._submit(self._analysis_job, [pipeline, run_id, costume, session_id, record["round"]],
                     "post_analyze_" + session_id + "_" + str(record["round"]), self._owner(record))
        return self.detail(pipeline, run_id, costume, session_id)

    def representative(self, pipeline, run_id, costume, session_id, payload):
        _, run = self._context(pipeline, run_id, costume)
        path = self._path(run, session_id)
        view = str(payload.get("view") or "").upper()
        candidate_id = str(payload.get("candidate_id") or "")
        candidate = next((c for c in run["candidates"] if c["view"] == view and c["candidate_id"] == candidate_id), None)
        image = Path(str((candidate or {}).get("image_path") or ""))
        if not candidate or not image.is_file() or not image.resolve().is_relative_to(Path(run["root"]).resolve()) or (candidate.get("human_review") or {}).get("decision") == "reject":
            raise ValueError("Choose an available, non-rejected image from this view.")
        with file_lock(path.with_suffix(".lock")):
            record = self._read(run, session_id)
            if record.get("view") and view != record["view"]:
                raise ValueError("Choose an image from this adjustment view.")
            if record["status"] not in {"OBSERVING", "REVIEW_READY", "FAILED"}:
                raise ValueError("Evidence cannot change after a trial starts.")
            frozen = next((item for item in record["representatives"] if item["view"] == view), None)
            if not frozen:
                raise ValueError("This view is outside the improvement evidence set.")
            target = path.parent / "evidence" / f"{view}{image.suffix.lower()}"
            shutil.copy2(image, target)
            prompt_path = Path(str(candidate.get("prompt_path") or ""))
            frozen.update(candidate_id=candidate_id, path=str(target), sha256=_hash(target.read_bytes()), reason="explicit",
                          prompt=str((candidate.get("render_input") or {}).get("prompt") or candidate.get("prompt") or (
                              prompt_path.read_text(encoding="utf-8") if prompt_path.is_file() else "")))
            record["status"] = "OBSERVING"
            record["analysis"] = {}
            self._write(run, record)
        return self.detail(pipeline, run_id, costume, session_id)

    def _analysis_job(self, pipeline, run_id, costume, session_id, round_number):
        workflow, run = self._context(pipeline, run_id, costume)
        record = self._read(run, session_id)
        if record["status"] != "ANALYZING" or record["round"] != round_number:
            return
        try:
            from zet.services.llm_role_service import resolve_role_model
            character = self._character_source(record["sources"])
            observations = record["analysis"]["observations"]
            evidence = record["representatives"]
            if record["trial"].get("attempts") and all(a["status"] == "READY" for a in record["trial"]["attempts"]):
                evidence = [{"view": a["view"], "candidate_id": a["id"], "path": a["image_path"], "sha256": a.get("sha256"),
                             "prompt": a["input"]["prompt"]} for a in record["trial"]["attempts"]]
            for item in evidence:
                if not Path(item["path"]).is_file() or (item.get("sha256") and _hash(Path(item["path"]).read_bytes()) != item["sha256"]):
                    raise ValueError("Frozen review evidence changed; start a new session.")
            schema = {"type": "object", "properties": {"summary": {"type": "string"}, "findings": {"type": "array", "items": {"type": "object", "properties": {
                "before": {"type": "string"}, "after": {"type": "string"}, "rationale": {"type": "string"},
                "views": {"type": "array", "items": {"type": "string"}}},
                "required": ["before", "after", "rationale", "views"], "additionalProperties": False}}},
                "required": ["summary", "findings"], "additionalProperties": False}
            prompt = ("Use rendered evidence and observations to propose small independent changes ONLY to Character.md. "
                      "Human observations and direction take priority. Distinguish recurring prompt defects from isolated render mistakes. "
                      "Each before must match exactly once in the supplied Character.md. Keep markers, placeholders, view tags, identity and intended asymmetry valid. "
                      "Edits may target any valid Character.md location even when evidence comes from only one view. "
                      "Name views the text may affect; no change is valid. Do not modify other sources or treat suggestions as accepted.\n"
                      + "Character.md:\n" + record["current_text"] + "\nOther batch source IDs (read only): "
                      + str([s["source_id"] for s in record["sources"] if s["source_id"] != character["source_id"]])
                      + "\nDirection:\n" + record["analysis"]["direction"] + "\nObservations:\n" + str(observations)
                      + "\nEvidence view/id/prompt:\n" + str([{k: item[k] for k in ("view", "candidate_id", "prompt")}
                                                                 for item in evidence]))
            answer, runtime = self.app.ai_proxy_service.ai_proxy_path_service.jobs.generate_json(
                resolve_role_model(self.app.config, "post_render_character_prompt"), "", prompt, schema,
                [Path(item["path"]) for item in evidence], task_type="post_render_character_prompt",
                role="post_render_character_prompt", render_context={"operation": "mixed", "bindings_owned_by_zet": True},
                workflow=pipeline, owner=self._owner(record))
            findings = []
            from zet.services.view_conditioning_service import VIEW_ORDER
            available = set(VIEW_ORDER)
            for index, finding in enumerate(answer["findings"], 1):
                before = finding["before"]
                views = finding["views"]
                if not before or record["current_text"].count(before) != 1 or not isinstance(views, list) or not views or set(views) - available:
                    raise ValueError("A suggestion did not bind to one source location and rendered view; analyze again.")
                after = record["current_text"].replace(before, finding["after"], 1)
                self.revisions._validate_owned(pipeline, character, record["current_text"], after)
                self.revisions._validate_text(record["current_text"], after)
                findings.append({**finding, "id": str(index)})
            path = self._path(run, session_id)
            with file_lock(path.with_suffix(".lock")):
                current = self._read(run, session_id)
                if current["status"] == "ANALYZING" and current["round"] == round_number:
                    current["analysis"].update(status="READY", summary=answer["summary"], findings=findings, runtime=runtime)
                    current["status"] = "REVIEW_READY"
                    self._write(run, current)
        except Exception as exc:
            path = self._path(run, session_id)
            with file_lock(path.with_suffix(".lock")):
                current = self._read(run, session_id)
                if current["status"] == "ANALYZING" and current["round"] == round_number:
                    current["analysis"].update(status="FAILED", error=str(exc))
                    current["status"] = "FAILED"
                    self._write(run, current)

    def decisions(self, pipeline, run_id, costume, session_id, payload):
        _, run = self._context(pipeline, run_id, costume)
        path = self._path(run, session_id)
        with file_lock(path.with_suffix(".lock")):
            record = self._read(run, session_id)
            ids = payload.get("selected_ids")
            allowed = {f["id"] for f in record["analysis"].get("findings", [])}
            if record["status"] != "REVIEW_READY" or not isinstance(ids, list) or set(ids) - allowed:
                raise ValueError("Choose corrections from the current analysis.")
            record["analysis"]["selected_ids"] = list(dict.fromkeys(ids))
            self._write(run, record)
        return self.detail(pipeline, run_id, costume, session_id)

    def trial(self, pipeline, run_id, costume, session_id, payload):
        workflow, run = self._context(pipeline, run_id, costume)
        path = self._path(run, session_id)
        with file_lock(path.with_suffix(".lock")):
            record = self._read(run, session_id)
            if record["status"] != "REVIEW_READY":
                raise ValueError("Review suggestions before starting a trial.")
            ids = payload.get("selected_ids", record["analysis"].get("selected_ids", []))
            chosen = [f for f in record["analysis"]["findings"] if f["id"] in ids]
            if not chosen:
                raise ValueError("Choose at least one Character.md correction for a trial.")
            original = record["current_text"]
            edits = sorted((original.index(f["before"]), original.index(f["before"]) + len(f["before"]), f["after"]) for f in chosen)
            if any(left[1] > right[0] for left, right in zip(edits, edits[1:])):
                raise ValueError("Selected corrections overlap.")
            updated = original
            for start, end, after in reversed(edits):
                updated = updated[:start] + after + updated[end:]
            source = self._character_source(record["sources"])
            self.revisions._validate_owned(pipeline, source, original, updated)
            self.revisions._validate_text(original, updated)
            sources = deepcopy(record["sources"])
            self._character_source(sources)["text"] = updated
            trial_id = uuid4().hex
            from zet.services.local_prompt_preview_service import LocalPromptPreviewService
            preview = LocalPromptPreviewService(workflow).compile(run, sources, path.parent / "compiled" / trial_id / "preview", all_orientations=True)
            affected = {record["view"]} if record.get("view") else set().union(*(set(f["views"]) for f in chosen))
            attempts = []
            with template_sources(sources):
                for view in run["views"]:
                    if view not in affected:
                        continue
                    for index in range(2):
                        aid = uuid4().hex
                        directory = path.parent / "compiled" / trial_id / view / aid
                        saved = workflow.slots.prepare_input(run, view, directory / "inputs", recompile=True, output_dir=directory / "prompt")
                        attempts.append({"id": aid, "view": view, "number": index + 1, "status": "QUEUED",
                                         "input": saved, "request_id": uuid4().hex, "seed": random.SystemRandom().randrange(0, 2**63 - 1),
                                         "image_path": "", "error": ""})
            if not attempts:
                raise ValueError("Selected changes have no rendered view to trial.")
            record["history"].append({"round": record["round"], "analysis": deepcopy(record["analysis"]),
                                      "source_text": original, "trial_id": trial_id})
            record["trial"] = {"id": trial_id, "text": updated, "sources": sources, "preview": preview,
                               "affected_views": [v for v in run["views"] if v in affected], "attempts": attempts}
            record["status"] = "TRIAL_RUNNING"
            self._write(run, record)
        for attempt in attempts:
            self._submit(self._render_job, [pipeline, run_id, costume, session_id, attempt["id"]],
                         "post_render_" + attempt.get("workflow_key", attempt["id"]), self._owner(record))
        return self.detail(pipeline, run_id, costume, session_id)

    def _render_job(self, pipeline, run_id, costume, session_id, attempt_id):
        _, run = self._context(pipeline, run_id, costume)
        record = self._read(run, session_id)
        attempt = next((a for a in record["trial"].get("attempts", []) if a["id"] == attempt_id), None)
        if not attempt or record["status"] != "TRIAL_RUNNING" or attempt["status"] != "QUEUED":
            return
        try:
            from zet.services.ai_job_coordinator import image_services
            from zet.services.ai_workflow_service import AIPending
            from zet.services.local_render_backend_service import LocalRenderBackendService
            generation = image_services(self.app)[0]
            saved = attempt["input"]
            from zet.services.render_slot_service import verify_input
            verify_input(saved)
            profile = LocalRenderBackendService(self.app.config.state_file(self.project_root, "Local_Render_Presets.json"), config=self.app.config).preset(saved["preset"])
            refs = [{"label": str(ref.get("label") or ref.get("role") or f"Image {index}"),
                     "image": base64.b64encode(Path(ref["path"]).read_bytes()).decode("ascii")}
                    for index, ref in enumerate(saved["references"], 1)]
            spec = {"mode": "img2img" if refs else "txt2img", "prompt": saved["prompt"], "count": 1,
                    "width": profile.get("width", 832), "height": profile.get("height", 1216),
                    "render_config": {"preset": saved["preset"], "checkpoint": profile.get("diffusion_model", ""),
                        "disable_prompt_globals": True, "append_reference_labels": False},
                    "ai_owner": {**self._owner(record), "attempt_id": attempt_id}, "ai_workflow": "Character prompt trial"}
            if refs:
                spec["reference_images"] = refs
            try:
                result = generation.status(attempt["request_id"])
            except KeyError:
                result = generation.submit(spec, request_id=attempt["request_id"], seeds=[attempt["seed"]])
            if result.get("images"):
                contents, mime = generation.image(attempt["request_id"], 0)
                suffix = {"image/jpeg": ".jpg", "image/webp": ".webp"}.get(mime, ".png")
                image = self._path(run, session_id).parent / "trials" / (attempt_id + suffix)
                outcome = {"status": "READY", "image_path": str(image), "sha256": _hash(contents), "error": ""}
            elif result["status"] in {"ERROR", "FAILED", "CANCELLED", "PARTIAL"}:
                raise ValueError(result.get("error") or "Trial render failed.")
            else:
                raise AIPending()
        except Exception as exc:
            outcome = {"status": "FAILED", "error": str(exc)}
        path = self._path(run, session_id)
        with file_lock(path.with_suffix(".lock")):
            current = self._read(run, session_id)
            target = next((a for a in current["trial"].get("attempts", []) if a["id"] == attempt_id), None)
            if current["status"] != "TRIAL_RUNNING" or not target or target["status"] != "QUEUED":
                return
            if outcome["status"] == "READY":
                write_bytes_atomic(Path(outcome["image_path"]), contents)
            target.update(outcome)
            if all(a["status"] != "QUEUED" for a in current["trial"]["attempts"]):
                current["status"] = "TRIAL_READY"
            self._write(run, current)

    def retry(self, pipeline, run_id, costume, session_id, payload):
        _, run = self._context(pipeline, run_id, costume)
        path = self._path(run, session_id)
        with file_lock(path.with_suffix(".lock")):
            record = self._read(run, session_id)
            failed = next((a for a in record["trial"].get("attempts", []) if a["id"] == payload.get("attempt_id")), None)
            if record["status"] != "TRIAL_READY" or not failed or failed["status"] != "FAILED":
                raise ValueError("Choose a failed trial render to retry.")
            failed.update(status="QUEUED", request_id=uuid4().hex, error="")
            failed["workflow_key"] = failed["request_id"]
            record["status"] = "TRIAL_RUNNING"
            self._write(run, record)
        self._submit(self._render_job, [pipeline, run_id, costume, session_id, failed["id"]],
                     "post_render_" + failed["request_id"], self._owner(record))
        return self.detail(pipeline, run_id, costume, session_id)

    def image_path(self, pipeline, run_id, costume, session_id, attempt_id):
        _, run = self._context(pipeline, run_id, costume)
        record = self._read(run, session_id)
        attempt = next((a for a in record["trial"].get("attempts", []) if a["id"] == attempt_id), None)
        if not attempt or attempt["status"] != "READY":
            raise FileNotFoundError("Trial image unavailable.")
        path = Path(attempt["image_path"]).resolve()
        if not path.is_file() or not path.is_relative_to(self._path(run, session_id).parent.resolve()):
            raise FileNotFoundError("Trial image unavailable.")
        return path

    def cancel(self, pipeline, run_id, costume, session_id):
        _, run = self._context(pipeline, run_id, costume)
        path = self._path(run, session_id)
        with file_lock(path.with_suffix(".lock")):
            record = self._read(run, session_id)
            if record["status"] in {"KEPT", "KEEPING"}:
                raise ValueError("An accepted template change cannot be cancelled.")
            record = {key: record[key] for key in ("version", "session_id", "universe_id", "pipeline", "run_id", "costume", "created_at")}
            record.update(status="CANCELLED", cancelled_at=_now())
            self._write(run, record)
        root = path.parent.resolve()
        for name in ("evidence", "compiled", "trials"):
            target = (root / name).resolve()
            if target.is_relative_to(root) and target.is_dir():
                shutil.rmtree(target)
        return {"status": "CANCELLED"}

    def keep(self, pipeline, run_id, costume, session_id):
        workflow, run = self._context(pipeline, run_id, costume)
        path = self._path(run, session_id)
        from zet.services.template_publication_core import change_lock
        runtime = self.app.config.runtime_root
        from contextlib import nullcontext
        fence = change_lock(Path(runtime) / "state") if runtime else nullcontext()
        with fence, file_lock(Path(self.app.config.base_ai_queue_path) / "template_promotion.lock"), file_lock(path.with_suffix(".lock")):
            record = self._read(run, session_id)
            if record["status"] == "KEPT":
                if record.get("error"):
                    record["error"] = ""
                    self._write(run, record)
                return self.detail(pipeline, run_id, costume, session_id)
            if record["status"] not in {"TRIAL_READY", "KEEPING"} or any(a["status"] != "READY" for a in record["trial"].get("attempts", [])):
                raise ValueError("Complete both renders for every affected view before keeping changes.")
            master = Path(self._character_source(record["sources"])["source_path"])
            new_text = record["trial"]["text"]
            master_is_original = _hash(master.read_bytes()) == record["master_sha256"]
            if not master_is_original and master.read_text(encoding="utf-8") != new_text:
                raise ValueError("Character.md changed since this review. Start a new session.")
            revision_id = record.get("final_revision_id") or uuid4().hex
            if active_revision(Path(run["root"])).get("revision_id", "") not in {record["base_revision_id"], revision_id}:
                raise ValueError("The batch prompt version changed. Start a new session.")
            sources = record["trial"]["sources"]
            from zet.services.local_prompt_preview_service import LocalPromptPreviewService
            LocalPromptPreviewService(workflow).compile(run, sources, path.parent / "compiled" / record["trial"]["id"] / "final-preview", all_orientations=True)
            rendered_views = [view for view in run["views"] if any(
                c["view"] == view and Path(str(c.get("image_path") or "")).is_file() for c in run["candidates"])]
            with template_sources(sources):
                for view in rendered_views:
                    staging = path.parent / "compiled" / revision_id / "preflight" / view
                    workflow.slots.prepare_input(run, view, staging / "inputs", recompile=True, output_dir=staging / "prompt")
            directory = Path(run["root"]) / "template_improvement"
            revision = {"version": 2, "revision_id": revision_id, "parent_revision_id": record["base_revision_id"],
                "universe_id": self.app.universe_id, "pipeline": pipeline, "run_id": run_id,
                "created_at": _now(), "status": "READY", "sources": sources,
                "source_ids": [record["character_source_id"]], "summary": "Accepted post-render Character.md improvement",
                "compiled_views": record["trial"]["preview"], "accepted_at": _now(), "findings": []}
            directory.mkdir(parents=True, exist_ok=True)
            record["status"] = "KEEPING"
            record["final_revision_id"] = revision_id
            self._write(run, record)
            try:
                self.revisions._write(directory / "revisions" / (revision_id + ".json"), revision)
                if master_is_original:
                    write_text_atomic(master, new_text)
                self.revisions._write(directory / "active.json", {"revision_id": revision_id, "updated_at": _now()})
                from zet.services.local_character_progression_service import accept_prompts
                if run.get("character_progression") and pipeline != "character-assembly":
                    accept_prompts(Path(run["root"]), revision_id)
                with template_sources(sources):
                    for view in rendered_views:
                        workflow.slots.prepare_input(run, view, path.parent / "compiled" / revision_id / view / "inputs",
                                                     recompile=True, output_dir=Path(run["root"]) / "prompts" / view)
                        from zet.services.atomic_file_service import write_json_atomic
                        from zet.services.local_prompt_improvement_service import record_compiler_sources
                        prompt_dir = Path(run["root"]) / "prompts" / view
                        record_compiler_sources(prompt_dir)
                        write_json_atomic(prompt_dir / "Template_Revision.json", {"revision_id": revision_id})
                record["status"] = "KEPT"
                record["kept_at"] = _now()
                record["error"] = ""
                self._write(run, record)
            except Exception as exc:
                record["error"] = str(exc)
                self._write(run, record)
                raise
        return self.detail(pipeline, run_id, costume, session_id)
