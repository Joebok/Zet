"""Resumable, image-only character true-ups with explicit same-slot adoption."""
from copy import deepcopy
from pathlib import Path
import base64
import hashlib
import random
import re
import shutil
from uuid import uuid4

from PIL import Image

from zet.services.atomic_file_service import write_bytes_atomic
from zet.services.image_reconstruction_contract import correction_items, text
from zet.services.library_reference_service import read_library_json, write_library_json
from zet.services.local_image_pipeline_policy import mutate_local_run_state
from zet.services.workflow_storage import file_lock


class LocalCharacterRefinementService:
    def __init__(self, app, project_root):
        self.app, self.project_root = app, Path(project_root)

    def _context(self, pipeline, run_id, costume):
        from zet.services.local_image_workflow_service import LocalImagePipelineWorkflowService
        workflow = LocalImagePipelineWorkflowService(self.app, self.project_root, pipeline)
        run = workflow.prompt_improvement.detail(run_id, costume)
        return workflow, run

    def _path(self, run, session_id):
        if not isinstance(session_id, str) or not re.fullmatch(r"[a-f0-9]{32}", session_id):
            raise ValueError("Invalid refinement session.")
        return Path(run["root"]) / "refinements" / session_id / "session.json"

    def _read(self, run, session_id):
        record = read_library_json(self._path(run, session_id), self.app.config.base_library_path)
        if record["universe_id"] != self.app.universe_id or record["run_id"] != run["run_id"]:
            raise ValueError("Refinement belongs to another batch or universe.")
        return record

    def _write(self, run, record):
        write_library_json(self._path(run, record["session_id"]), record, self.app.config.base_library_path)

    @staticmethod
    def _attempt(record, attempt_id):
        attempt = next((a for a in record["attempts"] if a["id"] == attempt_id), None)
        if not attempt:
            raise ValueError("Choose an attempt in this refinement session.")
        return attempt

    def image_path(self, pipeline, run_id, costume, session_id, attempt_id):
        _, run = self._context(pipeline, run_id, costume)
        record = self._read(run, session_id)
        path = Path(self._attempt(record, attempt_id).get("image_path") or "").resolve()
        if not path.is_file() or not path.is_relative_to(self._path(run, session_id).parent.resolve()):
            raise ValueError("Refinement image is unavailable.")
        return path

    def detail(self, pipeline, run_id, costume, session_id):
        _, run = self._context(pipeline, run_id, costume)
        record = self._read(run, session_id)
        public = deepcopy(record)
        for attempt in public["attempts"]:
            attempt.pop("payload", None)
            attempt["image_available"] = Path(str(attempt.get("image_path") or "")).is_file()
        selected = run.get("selected_views", {})
        current = next((c for c in run["candidates"] if c["candidate_id"] == selected.get(record["view"])), {})
        owns_selection = (current.get("refinement") or {}).get("session_id") == session_id
        if owns_selection:
            public["adopted_candidate_id"] = current["candidate_id"]
            for attempt in public["attempts"]:
                if attempt["id"] == current["refinement"]["attempt_id"]:
                    attempt["adopted_candidate_id"] = current["candidate_id"]
        public["comparisons"] = [{"view": c["view"], "candidate_id": c["candidate_id"]}
            for c in run["candidates"] if selected.get(c["view"]) == c["candidate_id"]
            and c["view"] != record["view"] and Path(str(c.get("image_path") or "")).is_file()
            and (c.get("human_review") or {}).get("decision") != "reject"]
        public["can_adopt"] = owns_selection or selected.get(record["view"]) in {record["base_candidate_id"], record.get("adopted_candidate_id")}
        # Reattach the small record→continuation publication window after a restart.
        for attempt in record["attempts"]:
            if attempt["status"] == "QUEUED":
                self._submit(self._render_job, pipeline, run_id, costume, session_id, attempt["id"])
        if record["analysis"].get("status") == "RUNNING":
            self._submit(self._analysis_job, pipeline, run_id, costume, session_id, record["analysis"]["id"])
        return public

    def open(self, pipeline, run_id, costume, view):
        workflow, run = self._context(pipeline, run_id, costume)
        root = Path(run["root"])
        with file_lock(root / "state.lock"):
            run = workflow.prompt_improvement.detail(run_id, costume)
            cid = run.get("selected_views", {}).get(view)
            candidate = next((c for c in run["candidates"] if c["candidate_id"] == cid and c["view"] == view), None)
            if not candidate or not Path(str(candidate.get("image_path") or "")).is_file():
                raise ValueError("Select an available image in this view before refining.")
            state = read_library_json(root / "state.json", self.app.config.base_library_path)
            previous = (state.get("refinement_sessions") or {}).get(view)
            if previous:
                record = self._read(run, previous)
                if (cid in {record["base_candidate_id"], record.get("adopted_candidate_id")}
                        or (candidate.get("refinement") or {}).get("session_id") == previous):
                    return self.detail(pipeline, run_id, costume, previous)
            sid = uuid4().hex
            directory = self._path(run, sid).parent
            directory.mkdir(parents=True)
            source = Path(candidate["image_path"])
            target = directory / ("original" + source.suffix.lower())
            shutil.copy2(source, target)
            record = {"version": 1, "universe_id": self.app.universe_id, "pipeline": pipeline,
                "run_id": run_id, "costume": costume, "session_id": sid, "view": view,
                "base_candidate_id": cid, "adopted_candidate_id": "", "revision": 0,
                "reference_inputs": deepcopy((candidate.get("render_input") or {}).get("references") or (candidate.get("refinement") or {}).get("reference_inputs") or []),
                "analysis": {}, "attempts": [{"id": "original", "status": "READY", "image_path": str(target),
                    "accepted_direction": [], "base_attempt_id": "", "image_sha256": hashlib.sha256(target.read_bytes()).hexdigest()}]}
            self._write(run, record)
            mutate_local_run_state(root, lambda state: state.setdefault("refinement_sessions", {}).update({view: sid}))
        return self.detail(pipeline, run_id, costume, sid)

    def _submit(self, method, pipeline, run_id, costume, session_id, identity):
        from zet.services.ai_workflow_service import AIWorkflowService
        workflows = AIWorkflowService(self.app)
        key = "refinement_" + identity
        if (workflows.root / (key + ".json")).is_file() or (workflows.local_root / (key + ".json")).is_file():
            return  # The coordinator resumes known work; do not contend with its running continuation.
        _, run = self._context(pipeline, run_id, costume)
        record = self._read(run, session_id)
        owner = {"character_refinement_pipeline_id": pipeline, "run_id": run_id,
            "character_refinement_session_id": session_id, "attempt_id": identity,
            "view": record["view"], "costume": costume, "character": run["character"], "phase": run["phase"]}
        workflows.submit(method, [pipeline, run_id, costume, session_id, identity],
            service="character_refinement", key=key, owner=owner)

    def analyze(self, pipeline, run_id, costume, session_id, payload):
        _, run = self._context(pipeline, run_id, costume)
        path = self._path(run, session_id)
        with file_lock(Path(run["root"]) / "state.lock"), file_lock(path.with_suffix(".lock")):
            record = self._read(run, session_id)
            attempt_id = payload.get("attempt_id", "original")
            image = self.image_path(pipeline, run_id, costume, session_id, attempt_id)
            public = self.detail(pipeline, run_id, costume, session_id)
            views = payload.get("comparison_views", [c["view"] for c in public["comparisons"]])
            if not isinstance(views, list) or set(views) - {c["view"] for c in public["comparisons"]}:
                raise ValueError("Choose available selected views from this batch for comparison.")
            model = str(payload.get("model") or "codex:" + self.app.config.codex_default_model.removeprefix("codex:"))
            from zet.services.ai_model_catalog_service import AIModelCatalogService
            AIModelCatalogService(self.app.config.base_ai_queue_path, config=self.app.config).validate(model, required=["vision"])
            aid = uuid4().hex
            inputs = []
            directory = path.parent / "analysis" / aid
            directory.mkdir(parents=True)
            for view in dict.fromkeys(views):
                cid = run["selected_views"][view]
                c = next(c for c in run["candidates"] if c["candidate_id"] == cid)
                source = Path(c["image_path"])
                target = directory / (view + source.suffix.lower())
                shutil.copy2(source, target)
                inputs.append({"view": view, "candidate_id": cid, "image_path": str(target)})
            record["analysis"] = {"id": aid, "attempt_id": attempt_id, "model": model,
                "comparison_views": views, "inputs": inputs, "image_path": str(image), "status": "RUNNING", "error": ""}
            record["revision"] += 1
            self._write(run, record)
        self._submit(self._analysis_job, pipeline, run_id, costume, session_id, aid)
        return self.detail(pipeline, run_id, costume, session_id)

    def _analysis_job(self, pipeline, run_id, costume, session_id, analysis_id):
        _, run = self._context(pipeline, run_id, costume)
        record = self._read(run, session_id)
        analysis = record["analysis"]
        if analysis.get("id") != analysis_id or analysis["status"] != "RUNNING":
            return
        try:
            from zet.services.image_true_up_service import ImageTrueUpService
            attempt = self._attempt(record, analysis["attempt_id"])
            target = {"description": "Improve this selected image while preserving its identity, costume, art style and orientation.",
                "change_text": "\n".join(attempt["accepted_direction"]), "identity": "", "style": {}, "sources": [],
                "preserve": "Preserve unaffected visible details; selected comparison views establish continuity.", "proposals": [], "notes": ""}
            def ask(model, prompt, schema, images):
                return self.app.ai_proxy_service.ai_proxy_path_service.jobs.generate_json(model, "", prompt, schema, images,
                    task_type="character_image_refinement", workflow=pipeline)[0]
            report = ImageTrueUpService(ask).compare(analysis["model"], target,
                [analysis["image_path"], *[i["image_path"] for i in analysis["inputs"]]],
                {"view": record["view"], "roles": ["Selected image to improve", *["Selected " + i["view"] for i in analysis["inputs"]]],
                    "task": "Image improvement only. Never propose template edits. Check skirt/garment length, hair, proportions, "
                    "visible construction and continuity across labeled views. Respect intentional asymmetry and occlusion. "
                    "Treat earlier accepted direction as intentional; latest feedback wins."})
            result = {"status": "COMPLETE", "report": report, "error": ""}
        except Exception as exc:
            from zet.services.storage_health_service import pause_on_storage_error
            pause_on_storage_error(self.app.config, exc)
            result = {"status": "FAILED", "error": str(exc)}
        with file_lock(Path(run["root"]) / "state.lock"), file_lock(self._path(run, session_id).with_suffix(".lock")):
            if not self._path(run, session_id).is_file():
                return
            current = self._read(run, session_id)
            if current["analysis"].get("id") == analysis_id:
                current["analysis"].update(result)
                self._write(run, current)

    def edit(self, pipeline, run_id, costume, session_id, payload):
        _, run = self._context(pipeline, run_id, costume)
        path = self._path(run, session_id)
        with file_lock(Path(run["root"]) / "state.lock"), file_lock(path.with_suffix(".lock")):
            record = self._read(run, session_id)
            operation_id = payload.get("operation_id")
            if operation_id and any(a.get("operation_id") == operation_id for a in record["attempts"]):
                return self.detail(pipeline, run_id, costume, session_id)
            base_id = payload.get("attempt_id", "original")
            base = self._attempt(record, base_id)
            source = self.image_path(pipeline, run_id, costume, session_id, base_id)
            instructions = text(payload.get("instructions", ""), "Refinement instructions")
            ids = payload.get("item_ids", [])
            analysis = record["analysis"]
            if ids and (analysis.get("attempt_id") != base_id or analysis.get("id") != payload.get("analysis_id")):
                raise ValueError("Analyze this attempt before applying its findings.")
            report = analysis.get("report", {"items": []}) if analysis.get("attempt_id") == base_id else {"items": []}
            corrections = correction_items(report, ids, instructions)
            direction = [c["correction"] for c in corrections] + ([instructions] if instructions else [])
            previous = base["accepted_direction"]
            prompt = ("Edit this selected character image. Change ONLY the requested details. Preserve unaffected identity, "
                "costume, art style, pose, camera and orientation. Latest feedback overrides earlier direction.\n"
                + "Earlier accepted direction (retain unless overridden):\n" + "\n".join(previous)
                + "\nRequested changes:\n" + "\n".join(direction))
            with Image.open(source) as image:
                width, height = image.size
            aid = uuid4().hex
            spec = {"mode": "img2img", "prompt": prompt, "count": 1, "width": width, "height": height,
                "reference_images": [{"label": "Selected image to refine", "image": base64.b64encode(source.read_bytes()).decode("ascii")}],
                "ai_owner": {"character_refinement_pipeline_id": pipeline, "run_id": run_id,
                    "character_refinement_session_id": session_id, "attempt_id": aid, "view": record["view"],
                    "costume": costume, "character": run["character"], "phase": run["phase"]},
                "ai_workflow": "Character image refinement"}
            record["attempts"].append({"id": aid, "operation_id": operation_id, "status": "QUEUED", "image_path": "",
                "base_attempt_id": base_id, "accepted_direction": previous + direction, "payload": spec,
                "seeds": [random.SystemRandom().randrange(0, 2**63 - 1)], "request_id": uuid4().hex, "error": ""})
            record["revision"] += 1
            self._write(run, record)
        self._submit(self._render_job, pipeline, run_id, costume, session_id, aid)
        return self.detail(pipeline, run_id, costume, session_id)

    def _render_job(self, pipeline, run_id, costume, session_id, attempt_id):
        _, run = self._context(pipeline, run_id, costume)
        record = self._read(run, session_id)
        attempt = self._attempt(record, attempt_id)
        if attempt["status"] != "QUEUED":
            return
        try:
            from zet.services.ai_job_coordinator import image_services
            from zet.services.ai_workflow_service import AIPending
            generation = image_services(self.app)[0]
            try:
                result = generation.status(attempt["request_id"])
            except KeyError:
                result = generation.submit(attempt["payload"], request_id=attempt["request_id"], seeds=attempt["seeds"])
            if result.get("images"):
                contents, mime = generation.image(attempt["request_id"], 0)
                suffix = {"image/jpeg": ".jpg", "image/webp": ".webp"}.get(mime, ".png")
                output = self._path(run, session_id).parent / (attempt_id + suffix)
                result = {"status": "READY", "image_path": str(output), "image_sha256": hashlib.sha256(contents).hexdigest(), "error": ""}
            elif result["status"] in {"ERROR", "FAILED", "CANCELLED", "PARTIAL"}:
                raise ValueError(result.get("error") or "The refinement render failed.")
            else:
                raise AIPending()
        except Exception as exc:
            from zet.services.storage_health_service import pause_on_storage_error
            pause_on_storage_error(self.app.config, exc)
            result = {"status": "FAILED", "error": str(exc)}
        with file_lock(Path(run["root"]) / "state.lock"), file_lock(self._path(run, session_id).with_suffix(".lock")):
            if not self._path(run, session_id).is_file():
                return
            current = self._read(run, session_id)
            target = self._attempt(current, attempt_id)
            if target["status"] == "QUEUED" and target["request_id"] == attempt["request_id"]:
                if result["status"] == "READY":
                    write_bytes_atomic(Path(result["image_path"]), contents)
                target.update(result)
                self._write(run, current)

    def retry(self, pipeline, run_id, costume, session_id, payload):
        _, run = self._context(pipeline, run_id, costume)
        with file_lock(Path(run["root"]) / "state.lock"), file_lock(self._path(run, session_id).with_suffix(".lock")):
            record = self._read(run, session_id)
            previous = self._attempt(record, payload.get("attempt_id"))
            if previous["status"] != "FAILED" or not previous.get("payload"):
                raise ValueError("Choose a failed refinement render to retry.")
            attempt = {**deepcopy(previous), "id": uuid4().hex, "request_id": uuid4().hex, "status": "QUEUED", "error": "",
                "operation_id": uuid4().hex, "retry_of": previous["id"]}
            attempt["payload"]["ai_owner"]["attempt_id"] = attempt["id"]
            record["attempts"].append(attempt)
            self._write(run, record)
        self._submit(self._render_job, pipeline, run_id, costume, session_id, attempt["id"])
        return self.detail(pipeline, run_id, costume, session_id)

    def adopt(self, pipeline, run_id, costume, session_id, payload):
        workflow, run = self._context(pipeline, run_id, costume)
        root = Path(run["root"])
        with file_lock(root / "state.lock"), file_lock(self._path(run, session_id).with_suffix(".lock")):
            run = workflow.prompt_improvement.detail(run_id, costume)
            record = self._read(run, session_id)
            attempt = self._attempt(record, payload.get("attempt_id"))
            selected = run.get("selected_views", {}).get(record["view"])
            candidate = next((c for c in run["candidates"] if c["candidate_id"] == selected), {})
            owns_selection = (candidate.get("refinement") or {}).get("session_id") == session_id
            if not owns_selection and selected not in {record["base_candidate_id"], record.get("adopted_candidate_id")}:
                raise ValueError("The selected image changed elsewhere. Open refinement from the new selection.")
            if payload.get("expected_selected_id") != selected:
                raise ValueError("The selection changed. Refresh before adopting this attempt.")
            image = self.image_path(pipeline, run_id, costume, session_id, attempt["id"])
            if (attempt.get("adopted_candidate_id") == selected
                    or owns_selection and candidate["refinement"]["attempt_id"] == attempt["id"]):
                return self.detail(pipeline, run_id, costume, session_id)
            from zet.services.render_slot_service import slot_maps
            slots = slot_maps(run)
            if selected not in slots[record["view"]]:
                raise ValueError("Selected image no longer occupies a batch slot.")
            cid = uuid4().hex
            index = slots[record["view"]].index(selected)
            adopted_image = root / "renders" / cid / ("refined" + image.suffix.lower())
            adopted_image.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(image, adopted_image)
            adopted = {**deepcopy(candidate), "candidate_id": cid, "image_path": str(adopted_image),
                "image_sha256": attempt["image_sha256"], "status": "COMPLETE", "render_status": "COMPLETE",
                "ask_id": "", "render_error": "", "human_review": {"decision": "undecided"},
                "refinement": {"session_id": session_id, "attempt_id": attempt["id"], "base_candidate_id": record["base_candidate_id"],
                    "reference_inputs": record.get("reference_inputs", [])}}
            adopted.pop("render_input", None)
            adopted.pop("slot_managed", None)
            slots[record["view"]][index] = cid
            def update(state):
                state.setdefault("added_candidates", {})[cid] = adopted
                detached = state.setdefault("detached_candidates", [])
                if selected not in detached:
                    detached.append(selected)
                state["slots_by_view"] = slots
                state["slot_version"] = int(state.get("slot_version", 0)) + 1
                state.setdefault("selected_views", {})[record["view"]] = cid
                if record["view"] == "FRONT":
                    state["front_anchor"] = cid
            mutate_local_run_state(root, update)
            from zet.services.local_character_progression_service import select
            select(workflow, workflow.prompt_improvement.detail(run_id, costume), record["view"], cid)
            attempt["adopted_candidate_id"] = cid
            record["adopted_candidate_id"] = cid
            record["revision"] += 1
            self._write(run, record)
        return self.detail(pipeline, run_id, costume, session_id)
