"""Resumable, image-only character true-ups with explicit same-slot adoption."""
from zet.services.llm_role_service import resolve_role_model
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
            model = str(resolve_role_model(self.app.config, "character_refinement", str(payload.get("model") or "")))
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
            if pipeline == "head-image-edit":
                task = (f"Review this {record['view']} head-only edit. Assess visible identity, requested view, head/ear framing, "
                        "authored hair shape and crop. Do not assess skirt, garment length, or body details outside the supplied image. "
                        "Report only evidence visible in the candidate and labeled comparison views.")
            elif pipeline == "character-assembly":
                task = (f"Review this {record['view']} assembled character for visible head/body identity and proportion continuity "
                        "against the selected FRONT and labeled source views. Do not propose template changes.")
            elif pipeline == "costume-dressing":
                task = (f"Review this {record['view']} dressed character for visible garment construction, coverage, length, "
                        "and continuity against the supplied selected views. Do not infer details hidden from the images.")
            elif pipeline == "body-reference":
                task = (f"Review this {record['view']} body reference for visible anatomy, silhouette, proportion, and view continuity. "
                        "Do not assess clothing or infer hidden details.")
            else:
                task = (f"Review this {record['view']} head reference for visible identity, hairstyle, head framing, "
                        "and orientation continuity. Do not infer details hidden from the images.")
            def ask(model, prompt, schema, images):
                return self.app.ai_proxy_service.ai_proxy_path_service.jobs.generate_json(model, "", prompt, schema, images,
                    task_type="character_image_refinement", role="character_refinement", render_context={"operation": "edit"}, workflow=pipeline)[0]
            report = ImageTrueUpService(ask).compare(analysis["model"], target,
                [analysis["image_path"], *[i["image_path"] for i in analysis["inputs"]]],
                {"view": record["view"], "roles": ["Selected image to improve", *["Selected " + i["view"] for i in analysis["inputs"]]],
                    "task": task + " Image improvement only; never propose template edits. Respect intentional asymmetry and occlusion. "
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
            operation = payload.get("operation", "correction")
            guide_view = str(payload.get("guide_view") or "").upper()
            if operation not in {"correction", "rear_hair"}:
                raise ValueError("Unknown refinement operation.")
            if (operation != "correction" or guide_view) and pipeline != "head-image-edit":
                raise ValueError("Render guides are supported only by Head-Image Edit.")
            if operation == "rear_hair":
                if record["view"] not in {"BACK_LEFT_3_4", "BACK_RIGHT_3_4"}:
                    raise ValueError("BACK-guided hair finishing requires a rear-quarter canvas.")
                guide_view = "BACK"
            guide = None
            if guide_view:
                from zet.services.local_view_reference_service import selected_reference
                guide = selected_reference(run, record["view"], {"mode": "selected_view", "source_view": guide_view})
            instructions = text(payload.get("instructions", ""), "Refinement instructions")
            if operation == "rear_hair" and not instructions:
                instructions = "Match lower-hair fullness and length to selected BACK while preserving the rear-quarter canvas."
            ids = payload.get("item_ids", [])
            analysis = record["analysis"]
            if ids and (analysis.get("attempt_id") != base_id or analysis.get("id") != payload.get("analysis_id")):
                raise ValueError("Analyze this attempt before applying its findings.")
            report = analysis.get("report", {"items": []}) if analysis.get("attempt_id") == base_id else {"items": []}
            corrections = correction_items(report, ids, instructions)
            direction = [c["correction"] for c in corrections] + ([instructions] if instructions else [])
            if operation == "rear_hair":
                direction.insert(0, "Edit only the lower hair mass in Image 1 using Image 2 as the hair-volume and length guide. Reproject the guide's lower-hair fullness into the canvas's existing rear-quarter pose. Preserve the canvas's crown height, head scale, ear attachment, ear silhouette and posterior surface, skin, neck proportions, hidden face, complete framing, background and rendering style. Do not copy the guide's camera or two-ear arrangement. Keep the same haircut; change only its lower fullness and length.")
            previous = base["accepted_direction"]
            prompt = ("Edit this selected character image. Change ONLY the requested details. Preserve unaffected identity, "
                "costume, art style, pose, camera and orientation. Latest feedback overrides earlier direction.\n"
                + "Earlier accepted direction (retain unless overridden):\n" + "\n".join(previous)
                + "\nRequested changes:\n" + "\n".join(direction))
            if guide and operation != "rear_hair":
                scope = text(payload.get("guide_scope", ""), "Guide transfer scope")
                if not scope.strip():
                    raise ValueError("Describe the feature the render guide should transfer.")
                prompt += "\nImage 1 is the canvas. Use Image 2 only for this feature: " + scope + ". Exclude its identity, material, style, camera, pose and background. Preserve all unaffected canvas content."
            with Image.open(source) as image:
                width, height = image.size
            aid = uuid4().hex
            reference_inputs = deepcopy(base.get("reference_inputs", record.get("reference_inputs", [])))
            render_refs = [{"label": "Selected image to refine", "image": base64.b64encode(source.read_bytes()).decode("ascii")}]
            render_references = [{"role": "head_image_source", "prompt_role": "edit_base", "image_index": 1,
                "path": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                "view": record["view"], "session_id": session_id, "attempt_id": base_id}]
            if guide:
                guide_source = Path(guide["path"])
                snapshot = path.parent / (aid + "_guide" + guide_source.suffix.lower())
                shutil.copy2(guide_source, snapshot)
                guide.update(path=str(snapshot), sha256=hashlib.sha256(snapshot.read_bytes()).hexdigest(),
                             prompt_role="subject_reference", role="head_edit_guide",
                             notes="Lower-hair volume and length only" if operation == "rear_hair" else scope)
                reference_inputs = [ref for ref in reference_inputs if ref.get("view") != guide_view] + [guide]
                render_refs.append({"label": guide["notes"], "image": base64.b64encode(snapshot.read_bytes()).decode("ascii")})
                render_references.append({**guide, "image_index": 2})
            spec = {"mode": "img2img", "prompt": prompt, "count": 1, "width": width, "height": height,
                "reference_images": render_refs,
                "ai_owner": {"character_refinement_pipeline_id": pipeline, "run_id": run_id,
                    "character_refinement_session_id": session_id, "attempt_id": aid, "view": record["view"],
                    "costume": costume, "character": run["character"], "phase": run["phase"]},
                "ai_workflow": "Character image refinement"}
            if pipeline == "head-image-edit":
                from zet.services.local_render_backend_service import LocalRenderBackendService
                profile = LocalRenderBackendService(self.app.config.state_file(self.project_root, "Local_Render_Presets.json"), config=self.app.config).preset("comfyui-qwen-head-image-edit-v1")
                spec.update(negative_prompt="", render_config={"preset": "comfyui-qwen-head-image-edit-v1",
                    "checkpoint": "qwen_image_2.1_int8_convrot.safetensors", "disable_prompt_globals": True,
                    "append_reference_labels": False,
                    "overrides": {key: profile[key] for key in ("steps", "cfg", "sampler_name", "scheduler", "denoise", "text_encoder", "vae") if key in profile}})
            accepted_direction = previous + direction
            if operation == "rear_hair":
                accepted_direction = previous + ["Retain the lower-hair fullness and length now established in this image, preserving pose, ears, identity and style."]
                if payload.get("instructions"):
                    accepted_direction.append(instructions)
            record["attempts"].append({"id": aid, "operation_id": operation_id, "status": "QUEUED", "image_path": "",
                **({"operation": operation, "guide_view": guide_view, "recipe_version": 1,
                    "reference_inputs": reference_inputs, "render_references": render_references} if pipeline == "head-image-edit" else {}),
                "base_attempt_id": base_id, "accepted_direction": accepted_direction, "payload": spec,
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
            if pipeline == "head-image-edit":
                for ref in attempt.get("reference_inputs", record.get("reference_inputs", [])):
                    source_view = ref.get("view")
                    if ref.get("candidate_id") and source_view and source_view != record["view"]:
                        current = next((c for c in run["candidates"] if c["candidate_id"] == run.get("selected_views", {}).get(source_view)), {})
                        image_path = Path(str(current.get("image_path") or ""))
                        if (current.get("candidate_id") != ref["candidate_id"] or not image_path.is_file()
                                or (current.get("human_review") or {}).get("decision") == "reject"
                                or (ref.get("sha256") and hashlib.sha256(image_path.read_bytes()).hexdigest() != ref["sha256"])):
                            raise ValueError("A refinement source or guide changed. Create a new attempt before adoption.")
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
                    "reference_inputs": attempt.get("reference_inputs", record.get("reference_inputs", [])),
                    **({"operation": attempt.get("operation", "correction"), "guide_view": attempt.get("guide_view", "")} if pipeline == "head-image-edit" else {})}}
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
