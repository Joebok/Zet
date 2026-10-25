"""Operator-gated pilot lifecycle; all durable transitions stay outside the web layer."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import random
from uuid import uuid4

from zet.models.prompt_generator import PROMPT_SESSION_VERSION, SEED_COUNT
from zet.services.atomic_file_service import write_json_atomic
from zet.services.workflow_storage import file_lock


def stamp():
    return datetime.now().astimezone().isoformat(timespec="seconds")


def criterion_records(values):
    """Text-based identities survive legacy prefixes and unchanged criterion revisions."""
    unique = dict.fromkeys(str(value).strip() for value in values if str(value).strip())
    return [{"id": hashlib.sha256(value.encode()).hexdigest()[:16], "text": value} for value in unique]


class PromptGeneratorCycle:
    TERMINAL = {"SCRAPPED", "FINISHED", "CANCELLED"}
    ACTIVE = {"RENDERING", "EVALUATING", "DIRECTIONS_GENERATING", "DRAFTING"}

    @staticmethod
    def _rendering_mode(pipeline, value=None):
        if pipeline == "costume-dressing":
            mode = "doll-dressing" if value is None else value
            if isinstance(mode, str) and mode in {"doll-dressing", "rotate"}:
                return mode
            raise ValueError("Choose Doll-dressing or Rotate for Costume Dressing.")
        if value not in (None, ""):
            raise ValueError("Rendering modes are available only for Costume Dressing.")
        return ""

    @staticmethod
    def _record_mode(record):
        return record.get("packet", {}).get("rendering_mode") or (
            "doll-dressing" if record["pipeline"] == "costume-dressing" else "")

    @staticmethod
    def _attempts(round_record):
        return list({item["seed"]: item for item in round_record.get("attempts", [])}.values())

    def _upgrade_record(self, record):
        if record.get("version") == PROMPT_SESSION_VERSION:
            return record
        record["version"] = PROMPT_SESSION_VERSION
        record.setdefault("revision", 0)
        record["legacy_pending"] = record.pop("pending", [])
        record["pending"] = []
        record["criteria_revision"] = 1
        record["criteria_records"] = criterion_records(record["packet"].get("criteria", []))
        record["criteria_history"] = [{"revision": 1, "criteria": deepcopy(record["criteria_records"])}]
        for round_record in record.get("history", []):
            round_record["criteria_records"] = criterion_records(round_record.get("criteria") or record["packet"].get("criteria", []))
            round_record["criteria_revision"] = 1
            round_record["legacy"] = True
            for attempt in round_record.get("attempts", []):
                old = attempt.get("human_review")
                if not old:
                    continue
                attempt["review_history"] = [{"legacy_review": deepcopy(old)}]
                scores = {str(item.get("criterion", "")).removeprefix("original: ").removeprefix("current: "): item.get("result")
                          for item in old.get("criteria", [])}
                attempt["human_correction"] = {"criteria": [
                    {"id": c["id"], "result": scores.get(c["text"], "unclear"), "explanation": ""}
                    for c in round_record["criteria_records"]], "notes": old.get("notes", ""),
                    "decision": old.get("decision", "reject"), "confirmed": False, "criteria_revision": 1}
        if record.get("status") not in self.TERMINAL:
            record["legacy_draft"] = deepcopy(record.get("active_draft"))
            record["active_draft"] = None
            record["status"] = "NEEDS_EVALUATION" if record.get("history") else "SETUP"
        return record

    @staticmethod
    def _registry_path(run):
        return Path(run["root"]) / "prompt_generator" / "sessions.json"

    def _registry(self, run):
        """Discover pre-registry sessions as well as current sessions; no global ledger."""
        result = []
        path = self._registry_path(run)
        registered = json.loads(path.read_text(encoding="utf-8"))["sessions"] if path.is_file() else []
        session_ids = dict.fromkeys([item["session_id"] for item in registered] + [
            p.parent.name for p in sorted(path.parent.glob("*/session.json"))])
        for session_id in session_ids:
            record = self._read(run, session_id)
            result.append({"session_id": record["session_id"], "view": record["view"],
                           "rendering_mode": self._record_mode(record),
                           "status": record["status"], "created_at": record["created_at"]})
        return sorted(result, key=lambda item: item["created_at"])

    def _save_registry(self, run):
        write_json_atomic(self._registry_path(run), {"version": 1, "sessions": self._registry(run)})

    def _new_record(self, workflow, run, pipeline, costume, view, criteria, rendering_mode=""):
        session_id = uuid4().hex
        records = criterion_records(criteria)
        packet = self._packet(workflow, run, view, self._session_path(run, session_id).parent, [c["text"] for c in records], rendering_mode)
        return {"version": PROMPT_SESSION_VERSION, "revision": 0, "session_id": session_id,
                "universe_id": self.app.universe_id, "pipeline": pipeline, "run_id": run["run_id"],
                "costume": costume, "view": view, "created_at": stamp(), "status": "SETUP",
                "packet": packet, "criteria_records": records, "criteria_revision": 1,
                "criteria_history": [{"revision": 1, "criteria": deepcopy(records)}],
                "seeds": random.SystemRandom().sample(range(1, 2**31 - 1), SEED_COUNT),
                "pending": [], "history": [], "active_draft": None, "error": ""}

    def open(self, pipeline, run_id, costume, payload):
        workflow, run = self._workflow(pipeline, run_id, costume)
        view = str(payload.get("view") or "").upper()
        if view not in run.get("views", []):
            raise ValueError("Choose a valid pipeline view.")
        rendering_mode = self._rendering_mode(pipeline, payload.get("rendering_mode"))
        path = self._registry_path(run)
        with file_lock(path.with_suffix(".lock")):
            existing = next((item for item in reversed(self._registry(run))
                             if item["view"] == view and item["rendering_mode"] == rendering_mode
                             and item["status"] not in self.TERMINAL), None)
            if existing:
                session_id = existing["session_id"]
            else:
                record = self._new_record(workflow, run, pipeline, costume, view, payload.get("criteria") or [], rendering_mode)
                self._write(run, record)
                self._save_registry(run)
                session_id = record["session_id"]
        return self.detail(pipeline, run_id, costume, session_id)

    def detail(self, pipeline, run_id, costume, session_id):
        _, run = self._workflow(pipeline, run_id, costume)
        record = self._read(run, session_id)
        self._resume(run, record)
        public = deepcopy(record)
        public["rendering_mode"] = self._record_mode(record)
        public["stage"] = record["status"]
        public["next_action"] = {
            "SETUP": "Set acceptance criteria, then start four baseline images.",
            "NEEDS_EVALUATION": "Evaluate the existing round; no replacement images will be generated.",
            "RENDERING": "Wait for four images; AI evaluation follows automatically.",
            "EVALUATING": "Wait for AI image evaluations.",
            "REVIEW_IMAGES": "Confirm or correct each image’s AI evaluation.",
            "REVIEW_ROUND": "Review the four-image results, then approve another round or finish.",
            "DIRECTIONS_GENERATING": "Wait for suggested directions based on your confirmed reviews.",
            "DIRECTIONS_REVIEW": "Edit or approve the suggested directions.",
            "DRAFTING": "Wait for the automated prompt draft.",
            "DRAFT_REVIEW": "Approve the generated draft to render four images, or revise directions.",
            "FAILED": "Retry the failed step or revise directions; completed work is preserved.",
            "FINISHED": "Review results or adopt an accepted image into an empty batch slot.",
            "SCRAPPED": "This run is archived. Start over to prepare a fresh baseline.",
            "CANCELLED": "This run is archived. Start over to prepare a fresh baseline.",
        }[record["status"]]
        public["sessions"] = [item for item in self._registry(run) if item["view"] == record["view"]]
        # Prompt text is served only by the exact-revision, read-only prompt endpoint.
        def redact(value):
            if isinstance(value, dict):
                return {key: redact(item) for key, item in value.items() if key not in {
                    "baseline_input", "input", "image_path", "path", "prompt", "baseline_prompt",
                    "request_prompt", "raw_answer", "feedback_images", "manual_baseline_prompt"}}
            if isinstance(value, list):
                return [redact(item) for item in value]
            return value
        return redact(public)

    def prompt_text(self, pipeline, run_id, costume, session_id, target):
        _, run = self._workflow(pipeline, run_id, costume)
        record = self._read(run, session_id)
        if target == "baseline":
            baseline = next((r for r in record["history"] if r["kind"] == "baseline"), None)
            return (baseline or {}).get("prompt") or record["packet"]["baseline_prompt"]
        for item in [record.get("active_draft") or {}, record.get("legacy_draft") or {},
                     *record.get("drafts", []), *record.get("history", [])]:
            if item.get("id") == target:
                return item.get("prompt") or (item.get("raw_answer") or {}).get("prompt") or "No prompt text was retained for this failed legacy draft."
        raise FileNotFoundError("That prompt revision does not exist in this run.")

    def _resume(self, run, record):
        if record["status"] in self.TERMINAL:
            return
        methods = {"render": self._render_job, "evaluation": self._evaluation_job,
                   "direction": self._direction_job, "draft": self._draft_job}
        for task in record.get("pending", []):
            self._submit(methods[task["kind"]], record["pipeline"], record["run_id"], record["costume"],
                         record["session_id"], task["id"], self._owner(record))

    def _checked(self, run, session_id, payload, stages):
        record = self._read(run, session_id)
        if payload.get("revision") != record.get("revision", 0):
            raise ValueError("This run changed in another request. Reload the current stage before trying again.")
        if record["status"] not in stages:
            raise ValueError("That action is unavailable at this stage. Reload the current stage.")
        return record

    def _queue(self, record, kind, **values):
        task = {"id": uuid4().hex, "kind": kind, **values}
        record.setdefault("pending", []).append(task)
        record["status"] = {"render": "RENDERING", "evaluation": "EVALUATING",
                            "direction": "DIRECTIONS_GENERATING", "draft": "DRAFTING"}[kind]
        record["error"] = ""
        return task

    def _models(self):
        from zet.services.llm_role_service import resolve_role_model
        return {role: resolve_role_model(self.app.config, role) for role in (
            "prompt_generator", "prompt_generator_evaluation", "prompt_generator_direction")}

    def _make_round(self, record, prompt, kind):
        packet = record["packet"]
        refs = packet["baseline_input"]["references"]
        from zet.services.prompt_generator_review_service import verified_images
        verified_images(refs)
        import re
        expanded = re.sub(r"\{\{REF:([A-Za-z0-9_-]+)\}\}", lambda m: self._render_citation(m.group(1), refs), prompt)
        round_record = {"id": uuid4().hex, "kind": kind, "round": len(record["history"]),
                        "prompt": prompt, "packet_hash": packet["packet_hash"], "packet_id": packet["packet_id"],
                        "packet_revision": packet["revision"], "criteria": [c["text"] for c in record["criteria_records"]],
                        "criteria_records": deepcopy(record["criteria_records"]), "criteria_revision": record["criteria_revision"],
                        "models": deepcopy(record["round_authorization"]["models"]), "authorized_at": record["round_authorization"]["approved_at"],
                        "approved_directions": (record.get("directions") or {}).get("approved_text", "") if kind == "trial" else "",
                        "draft_summary": (record.get("active_draft") or {}).get("summary", "") if kind == "trial" else "",
                        "model": record["round_authorization"]["models"]["prompt_generator"], "attempts": [], "created_at": stamp()}
        for seed in record["seeds"]:
            round_record["attempts"].append({"id": uuid4().hex, "seed": seed, "request_id": uuid4().hex,
                "status": "QUEUED", "error": "", "input": {**deepcopy(packet["baseline_input"]), "prompt": expanded}})
        record["history"].append(round_record)
        task = self._queue(record, "render", round_id=round_record["id"])
        for attempt in round_record["attempts"]:
            attempt["dispatch_task_id"] = task["id"]

    def _evaluation_tasks(self, record, round_record):
        round_record["criteria_records"] = deepcopy(record["criteria_records"])
        round_record["criteria_revision"] = record["criteria_revision"]
        round_record.setdefault("models", self._models())
        for attempt in self._attempts(round_record):
            if attempt["status"] != "READY":
                continue
            evaluation = attempt.get("ai_evaluation") or {}
            if evaluation.get("status") == "READY" and evaluation.get("criteria_revision") == record["criteria_revision"]:
                continue
            if evaluation:
                attempt.setdefault("evaluation_history", []).append(deepcopy(evaluation))
            task = self._queue(record, "evaluation", round_id=round_record["id"], attempt_id=attempt["id"],
                               criteria_revision=record["criteria_revision"], model=round_record["models"]["prompt_generator_evaluation"])
            attempt["ai_evaluation"] = {"id": task["id"], "status": "QUEUED", "criteria_revision": record["criteria_revision"]}

    def _after_images(self, record, round_record):
        attempts = self._attempts(round_record)
        if any(a["status"] == "FAILED" for a in attempts):
            record.update(status="FAILED", error="An image failed. Retry that image; completed images are retained.", failed_step="render")
        elif any(a["status"] != "READY" for a in attempts):
            record["status"] = "RENDERING"
        elif not round_record.get("authorized_at"):
            record["status"] = "NEEDS_EVALUATION"
        else:
            self._evaluation_tasks(record, round_record)
            if not record["pending"]:
                record["status"] = "REVIEW_IMAGES"

    def transition(self, pipeline, run_id, costume, session_id, operation, payload):
        workflow, run = self._workflow(pipeline, run_id, costume)
        models = self._models() if operation in {"start", "next-round", "evaluate"} else None
        with file_lock(self._session_path(run, session_id).with_suffix(".lock")):
            stages = {
                "start": {"SETUP"}, "criteria": {"SETUP", "REVIEW_IMAGES", "REVIEW_ROUND", "DIRECTIONS_REVIEW", "DRAFT_REVIEW"},
                "evaluate": {"NEEDS_EVALUATION"}, "review": {"REVIEW_IMAGES", "REVIEW_ROUND"},
                "next-round": {"REVIEW_ROUND"}, "directions": {"DIRECTIONS_REVIEW"}, "approve": {"DRAFT_REVIEW"},
                "revise": {"DRAFT_REVIEW", "FAILED"}, "retry-step": {"FAILED"}, "finish": {"REVIEW_ROUND"},
            }
            if operation not in stages:
                raise ValueError("Unknown guided pilot action.")
            record = self._checked(run, session_id, payload, stages[operation])
            current = record["history"][-1] if record["history"] else None
            if operation in {"start", "criteria"}:
                criteria = criterion_records(payload.get("criteria") or [])
                if not criteria:
                    raise ValueError("Add at least one concrete visual acceptance criterion.")
                if criteria != record["criteria_records"]:
                    record["criteria_revision"] += 1
                    record["criteria_records"] = criteria
                    record["criteria_history"].append({"revision": record["criteria_revision"], "criteria": deepcopy(criteria), "created_at": stamp()})
                    if record.get("active_draft"):
                        record.setdefault("drafts", []).append(deepcopy(record["active_draft"]))
                    self._revise_packet(record, criteria=[c["text"] for c in criteria])
                    if record.get("directions"):
                        record.setdefault("direction_history", []).append(deepcopy(record["directions"]))
                    record["directions"] = None
                    if current:
                        current.setdefault("assessment_history", []).append({"criteria_revision": current["criteria_revision"],
                            "criteria_records": deepcopy(current["criteria_records"]), "attempts": [{"id": a["id"],
                            "ai_evaluation": deepcopy(a.get("ai_evaluation")), "human_correction": deepcopy(a.get("human_correction"))}
                            for a in self._attempts(current)]})
                        for a in self._attempts(current):
                            if a.get("human_correction"):
                                a.setdefault("review_history", []).append(deepcopy(a["human_correction"]))
                                a["human_correction"]["confirmed"] = False
                        self._evaluation_tasks(record, current)
            if operation == "start":
                record["round_authorization"] = {"round": 0, "approved_at": stamp(), "models": models}
                self._make_round(record, record["packet"]["baseline_prompt"], "baseline")
            elif operation == "evaluate":
                current["models"] = models
                current["authorized_at"] = stamp()
                missing = [a for a in self._attempts(current) if a["status"] != "READY"]
                if missing:
                    task = self._queue(record, "render", round_id=current["id"])
                    for a in missing:
                        a.update(status="QUEUED", dispatch_task_id=task["id"])
                else:
                    self._evaluation_tasks(record, current)
            elif operation == "review":
                self._save_review(record, current, payload)
            elif operation == "next-round":
                if not all(a.get("human_correction", {}).get("confirmed") for a in self._attempts(current)):
                    raise ValueError("Confirm all four image reviews first.")
                record["round_authorization"] = {"round": len(record["history"]), "approved_at": stamp(), "models": models}
                if record.get("directions"):
                    record.setdefault("direction_history", []).append(deepcopy(record["directions"]))
                task = self._queue(record, "direction", round_id=current["id"], model=models["prompt_generator_direction"])
                record["directions"] = {"id": task["id"], "status": "QUEUED"}
            elif operation == "directions":
                direction = str(payload.get("direction") or "").strip()
                if not direction:
                    raise ValueError("Enter a direction before approving it.")
                record["directions"].update(approved_text=direction, approved_at=stamp())
                self._start_draft(record)
            elif operation == "approve":
                draft = record["active_draft"]
                if payload.get("draft_id") != draft["id"] or draft["packet_hash"] != record["packet"]["packet_hash"]:
                    raise ValueError("The draft changed. Review the current draft before approval.")
                draft["prompt"] = self._validate_draft(record["packet"], draft)
                draft.update(approved=True, approved_at=stamp(), approved_hash=hashlib.sha256(draft["prompt"].encode()).hexdigest())
                self._make_round(record, draft["prompt"], "trial")
            elif operation == "revise":
                if record.get("failed_step") not in {None, "draft"} and record["status"] == "FAILED":
                    raise ValueError("Retry the failed step before revising directions.")
                if not record.get("directions"):
                    raise ValueError("There are no directions to revise yet.")
                record.setdefault("drafts", []).append(deepcopy(record.get("active_draft") or {}))
                record["active_draft"] = None
                record["draft_feedback"] = str(payload.get("feedback") or "")
                record.update(status="DIRECTIONS_REVIEW", error="", failed_step=None)
            elif operation == "retry-step":
                self._retry_step(record, current, payload)
            elif operation == "finish":
                record.update(status="FINISHED", finished_at=stamp())
            self._write(run, record)
        return self.detail(pipeline, run_id, costume, session_id)

    def _save_review(self, record, current, payload):
        attempt = next((a for a in self._attempts(current) if a["id"] == payload.get("attempt_id")), None)
        if not attempt or (attempt.get("ai_evaluation") or {}).get("status") != "READY":
            raise ValueError("Wait for this image’s AI evaluation before reviewing it.")
        criteria = payload.get("criteria") or []
        expected = {c["id"] for c in current["criteria_records"]}
        if len(criteria) != len(expected) or {c.get("id") for c in criteria} != expected or any(c.get("result") not in {"", "pass", "fail", "unclear"} for c in criteria):
            raise ValueError("Review every current criterion exactly once.")
        confirmed = payload.get("confirm") is True
        if confirmed and any(not c.get("result") or c.get("chosen") is not True for c in criteria):
            raise ValueError("Choose Pass, Fail or Unclear for every criterion before confirming this image.")
        criteria = [{**c, "result": c["result"] if c.get("chosen") is True else ""} for c in criteria]
        previous = attempt.get("human_correction") or {}
        if previous.get("confirmed") or any("chosen" not in c for c in previous.get("criteria", [])):
            attempt.setdefault("review_history", []).append(deepcopy(previous))
        attempt["human_correction"] = {"criteria": deepcopy(criteria), "notes": str(payload.get("notes") or ""),
            "decision": "undecided" if any(not c["result"] for c in criteria) else ("accept" if all(c["result"] == "pass" for c in criteria) else "reject"),
            "criteria_revision": current["criteria_revision"], "confirmed": confirmed, "saved_at": stamp()}
        record["status"] = "REVIEW_ROUND" if all(a.get("human_correction", {}).get("confirmed") for a in self._attempts(current)) else "REVIEW_IMAGES"

    def _start_draft(self, record):
        if record.get("active_draft"):
            record.setdefault("drafts", []).append(deepcopy(record["active_draft"]))
        direction = record["directions"]["approved_text"]
        self._revise_packet(record, direction=direction)
        model = record["round_authorization"]["models"]["prompt_generator"]
        task = self._queue(record, "draft", model=model, round_id=record["history"][-1]["id"])
        record["active_draft"] = {"id": task["id"], "status": "QUEUED", "model": model,
            "direction": direction, "packet_id": record["packet"]["packet_id"], "packet_hash": record["packet"]["packet_hash"], "approved": False}

    def _retry_step(self, record, current, payload):
        step = record.get("failed_step")
        if step == "draft":
            self._start_draft(record)
        elif step == "direction":
            task = self._queue(record, "direction", round_id=current["id"], model=record["round_authorization"]["models"]["prompt_generator_direction"])
            record.setdefault("direction_history", []).append(deepcopy(record["directions"]))
            record["directions"] = {"id": task["id"], "status": "QUEUED"}
        elif step == "evaluation":
            self._evaluation_tasks(record, current)
        elif step == "render":
            prior = next((a for a in self._attempts(current) if a["id"] == payload.get("attempt_id") and a["status"] == "FAILED"), None)
            if not prior:
                raise ValueError("Choose a failed image to retry.")
            task = self._queue(record, "render", round_id=current["id"])
            current["attempts"].append({"id": uuid4().hex, "seed": prior["seed"], "status": "QUEUED", "error": "",
                "request_id": uuid4().hex, "retry_of": prior["id"], "dispatch_task_id": task["id"], "input": deepcopy(prior["input"])})
        else:
            raise ValueError("There is no failed step to retry.")
        record["failed_step"] = None

    def archive(self, pipeline, run_id, costume, session_id, payload, restart=False):
        workflow, run = self._workflow(pipeline, run_id, costume)
        registry_path = self._registry_path(run)
        with file_lock(registry_path.with_suffix(".lock")), file_lock(self._session_path(run, session_id).with_suffix(".lock")):
            record = self._checked(run, session_id, payload, set(self.ACTIVE) | {
                "SETUP", "NEEDS_EVALUATION", "REVIEW_IMAGES", "REVIEW_ROUND", "DIRECTIONS_REVIEW", "DRAFT_REVIEW", "FAILED", *self.TERMINAL})
            other = next((s for s in self._registry(run) if s["view"] == record["view"]
                          and s["rendering_mode"] == self._record_mode(record)
                          and s["session_id"] != session_id and s["status"] not in self.TERMINAL), None)
            if restart and other:
                raise ValueError("Another active run already exists for this view and mode. Open it from run history.")
            fresh = self._new_record(workflow, run, pipeline, costume, record["view"],
                [c["text"] for c in record["criteria_records"]], self._record_mode(record)) if restart else None
            if record["status"] not in self.TERMINAL:
                record.update(status="SCRAPPED", archived_at=stamp(), pending=[])
                self._write(run, record)
            if fresh:
                fresh["restarted_from"] = session_id
                self._write(run, fresh)
            self._save_registry(run)
        return self.detail(pipeline, run_id, costume, fresh["session_id"] if fresh else session_id)

    def _job_context(self, pipeline, run_id, costume, session_id, task_id):
        _, run = self._workflow(pipeline, run_id, costume)
        record = self._read(run, session_id)
        task = next((t for t in record["pending"] if t["id"] == task_id), None)
        if record["status"] in self.TERMINAL or not task:
            return run, record, None
        return run, record, task

    def _ai_job(self, pipeline, run_id, costume, session_id, task_id, kind):
        from zet.services.ai_workflow_service import AIPending
        from zet.services.prompt_generator_review_service import PilotAIReview
        run, record, task = self._job_context(pipeline, run_id, costume, session_id, task_id)
        if not task:
            return
        response = None
        try:
            response, runtime = PilotAIReview(self).generate(record, task)
            if kind == "draft":
                response["prompt"] = self._validate_draft(record["packet"], response)
            outcome = {**response, "runtime": runtime, "status": "READY"}
        except AIPending:
            raise
        except Exception as exc:
            outcome = {"status": "FAILED", "error": str(exc), "raw_answer": response}
        with file_lock(self._session_path(run, session_id).with_suffix(".lock")):
            current = self._read(run, session_id)
            if current["status"] in self.TERMINAL or not any(t["id"] == task_id for t in current["pending"]):
                return
            current["pending"] = [t for t in current["pending"] if t["id"] != task_id]
            if kind == "evaluation":
                round_record = next(r for r in current["history"] if r["id"] == task["round_id"])
                attempt = next(a for a in round_record["attempts"] if a["id"] == task["attempt_id"])
                attempt["ai_evaluation"].update(outcome)
                if not current["pending"]:
                    failed = any(a.get("ai_evaluation", {}).get("status") == "FAILED" for a in self._attempts(round_record))
                    current.update(status="FAILED" if failed else "REVIEW_IMAGES", failed_step="evaluation" if failed else None,
                                   error="An AI evaluation failed. Retry the failed evaluations." if failed else "")
            else:
                target = current["active_draft"] if kind == "draft" else current["directions"]
                target.update(outcome)
                current.update(status="FAILED" if outcome["status"] == "FAILED" else ("DRAFT_REVIEW" if kind == "draft" else "DIRECTIONS_REVIEW"),
                               failed_step=kind if outcome["status"] == "FAILED" else None, error=outcome.get("error", ""))
            self._write(run, current)

    def _evaluation_job(self, *args):
        return self._ai_job(*args, "evaluation")

    def _direction_job(self, *args):
        return self._ai_job(*args, "direction")

    def _draft_job(self, *args):
        return self._ai_job(*args, "draft")
