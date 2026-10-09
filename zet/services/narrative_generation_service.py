"""Durable interview, synthesis and candidate lifecycle; no legacy scene orchestration."""
from dataclasses import asdict
import json
import logging
from pathlib import Path
import random
import threading

from zet.models.narrative import NarrativeCandidate, new_id
from zet.services.atomic_file_service import write_bytes_atomic
from zet.services.narrative_prompt_service import assemble_prompt, llm_request
from zet.services.narrative_proxy_service import NarrativeProxyService
from zet.services.workflow_storage import validate_image


ACTIVE = {"SUBMITTING", "QUEUED", "RUNNING", "DISPATCHING"}


class NarrativeGenerationService:
    def __init__(self, author):
        self.author = author
        self.repository = author.repository
        self.proxy = NarrativeProxyService(author.app)
        self._stop = threading.Event()
        self._thread = None
        self._thread_lock = threading.Lock()

    def start_background(self):
        with self._thread_lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop.clear()
            self._thread = threading.Thread(target=self._poll_loop, name="zet-narrative-jobs", daemon=True)
            self._thread.start()

    def stop_background(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _poll_loop(self):
        while not self._stop.is_set():
            try:
                self.poll_pending()
            except Exception:
                logging.getLogger(__name__).exception("Unable to refresh narrative jobs")
            self._stop.wait(2)

    def poll_pending(self):
        for story in self.repository.stories():
            for scene in story["scene_ids"]:
                try:
                    for target in self.repository.read(story["id"], scene)["target_ids"]:
                        record = self.repository.read(story["id"], scene, target)
                        if any(job["status"] in ACTIVE for job in record["jobs"].values()):
                            self.detail(story["id"], scene, target)
                except KeyError:
                    # An author can delete a scene while the sweep is running.
                    continue

    def detail(self, story: str, scene: str, target: str) -> dict:
        with self.repository.lock():
            record = self.repository.read(story, scene, target)
            self._refresh(story, scene, target, record)
            return self.author.target(story, scene, target)

    def start(self, story: str, scene: str, target: str, data: dict) -> dict:
        with self.repository.lock():
            record = self.repository.read(story, scene, target)
            self._refresh(story, scene, target, record)
            kind = data.get("action", "generate")
            if kind not in {"interview", "synthesize", "generate", "render"}:
                raise ValueError("Unknown narrative generation action.")
            detail = self.author.target(story, scene, target)
            refs = self.author.references(detail)
            job = {"id": new_id(), "kind": kind, "status": "SUBMITTING", "error": "", "detail": detail_without_jobs(detail),
                   "references": refs, "candidate_ids": [], "result": None}
            if kind in {"generate", "render"}:
                count = data.get("count", 1)
                if isinstance(count, bool) or not isinstance(count, int) or count not in (1, 4):
                    raise ValueError("Generate one or four images.")
                slot = data.get("slot")
                if slot is not None:
                    if isinstance(slot, bool) or not isinstance(slot, int) or not 1 <= slot <= 8:
                        raise ValueError("Choose a slot from 1 to 8.")
                    slots = [slot - 1]
                else:
                    available = [index for index, item in enumerate(record["slots"])
                                 if item is None or (not record["candidates"][item]["locked"] and item != record["selected_id"])]
                    def priority(index):
                        candidate = record["candidates"].get(record["slots"][index])
                        return 0 if candidate is None or candidate["status"] == "FAILED" else 2 if candidate["status"] in ACTIVE else 1
                    slots = sorted(available, key=priority)[:count]
                if len(slots) != count:
                    raise ValueError("Not enough unprotected slots. Clear a protected slot with confirmation to make room.")
                if kind == "render" and not record["prompt"].strip():
                    raise ValueError("Enter a prompt before rendering.")
                for index in slots:
                    previous = record["slots"][index]
                    if previous:
                        old = record["candidates"][previous]
                        if old["locked"] or record["selected_id"] == previous:
                            raise ValueError("Clear the protected image with confirmation before replacing it.")
                        self._remove_candidate(story, scene, target, record, previous)
                    candidate = asdict(NarrativeCandidate(target, index + 1, random.SystemRandom().randrange(0, 2**63 - 1)))
                    record["candidates"][candidate["id"]] = candidate
                    record["slots"][index] = candidate["id"]
                    job["candidate_ids"].append(candidate["id"])
            record["jobs"][job["id"]] = job
            if kind != "render":
                record["active_llm_job"] = job["id"]
            self.repository.write(record, story, scene, target)
            try:
                if kind == "render":
                    job["result"] = record["prompt"]
                    job["status"] = "DISPATCHING"
                    self.repository.write(record, story, scene, target)
                    self._stage_renders(story, scene, target, record, job, record["prompt"])
                    job["status"] = "COMPLETE"
                else:
                    message = str(data.get("message") or "")
                    if kind == "interview":
                        record["interview"].append({"role": "user", "text": message})
                    request, schema = llm_request(detail, kind, message)
                    self.proxy.publish(story, scene, target, job, request, schema=schema)
                    job["status"] = "QUEUED"
            except Exception as exc:
                self._fail(record, job, str(exc))
            self.repository.write(record, story, scene, target)
            return self.author.target(story, scene, target)

    def _stage_renders(self, story, scene, target, record, parent, prompt):
        for candidate_id in parent["candidate_ids"]:
            candidate = record["candidates"].get(candidate_id)
            if candidate is None:
                continue
            if candidate["job_id"]:
                continue
            job = {"id": new_id(), "kind": "image", "status": "SUBMITTING", "error": "",
                   "candidate_id": candidate_id, "result": None}
            record["jobs"][job["id"]] = job
            candidate["job_id"] = job["id"]
            self.repository.write(record, story, scene, target)
            try:
                self.proxy.publish(story, scene, target, job, prompt, references=parent["references"],
                                   width=parent["detail"]["width"], height=parent["detail"]["height"], seed=candidate["seed"])
                job["status"] = candidate["status"] = "QUEUED"
            except Exception as exc:
                job["status"] = candidate["status"] = "FAILED"
                job["error"] = candidate["error"] = str(exc)
            self.repository.write(record, story, scene, target)

    def _refresh(self, story, scene, target, record):
        release = []
        for job in list(record["jobs"].values()):
            if job["status"] == "DISPATCHING":
                self._stage_renders(story, scene, target, record, job, job["result"])
                job["status"] = "COMPLETE"
                release.append(job)
                continue
            if job["status"] not in ACTIVE:
                release.append(job)
                continue
            state, result = self.proxy.poll(story, scene, target, job)
            job["status"] = state
            candidate = record["candidates"].get(job.get("candidate_id"))
            if candidate and candidate["job_id"] == job["id"]:
                candidate["status"] = state
            if state == "FAILED":
                self._fail(record, job, str(result))
            elif state == "COMPLETE":
                try:
                    if job["kind"] == "image":
                        if candidate and candidate["job_id"] == job["id"]:
                            validate_image(result)
                            relative = f"images/{candidate['id']}.png"
                            write_bytes_atomic(self.repository.folder(story, scene, target) / relative, result)
                            candidate["image"] = relative
                    else:
                        value = json.loads(result.decode("utf-8"))
                        if job["kind"] == "interview":
                            self._apply_interview(record, job, value)
                            job["result"] = value
                        else:
                            prompt = assemble_prompt(job["detail"], value, job["references"])
                            job["result"] = prompt
                            if record["active_llm_job"] == job["id"] and record["prompt"] == job["detail"]["prompt"]:
                                record["prompt"] = prompt
                            if job["kind"] == "generate":
                                job["status"] = "DISPATCHING"
                                self.repository.write(record, story, scene, target)
                                self._stage_renders(story, scene, target, record, job, prompt)
                                job["status"] = "COMPLETE"
                except (ValueError, KeyError, TypeError, OSError) as exc:
                    self._fail(record, job, str(exc))
            if state in {"COMPLETE", "FAILED"}:
                release.append(job)
        self.repository.write(record, story, scene, target)
        for job in release:
            self.proxy.release(story, scene, target, job)

    @staticmethod
    def _apply_interview(record, job, result):
        for key in ("narrative", "staging", "physical_context", "framing"):
            if not isinstance(result.get(key), str):
                raise ValueError("The interview returned invalid draft fields.")
        questions = result.get("questions", [])
        if not isinstance(questions, list) or any(not isinstance(item, str) for item in questions):
            raise ValueError("The interview returned invalid questions.")
        if record["active_llm_job"] == job["id"]:
            for key in ("narrative", "staging", "physical_context", "framing"):
                if record[key] == job["detail"][key]:
                    record[key] = result[key]
        record["interview"].append({"role": "assistant", "text": "\n".join(questions[:2]),
                                    "draft": {key: result[key] for key in ("narrative", "staging", "physical_context", "framing")}})

    @staticmethod
    def _fail(record, job, error):
        job.update(status="FAILED", error=error)
        for candidate_id in job.get("candidate_ids", [job.get("candidate_id")]):
            candidate = record["candidates"].get(candidate_id)
            if candidate and candidate["status"] in ACTIVE:
                candidate.update(status="FAILED", error=error)

    def candidate_action(self, story, scene, target, candidate_id, data):
        with self.repository.lock():
            record = self.repository.read(story, scene, target)
            candidate = record["candidates"].get(candidate_id)
            if candidate is None:
                raise KeyError("Candidate not found.")
            action = data.get("action")
            if action in {"select", "lock"} and not candidate["image"]:
                raise ValueError("Wait for an image before selecting or locking it.")
            if action == "select":
                record["selected_id"] = candidate_id
            elif action == "lock":
                candidate["locked"] = True
            elif action == "unlock":
                candidate["locked"] = False
            elif action == "clear":
                images = [{"id": candidate_id, "label": f"{record['title']} · slot {candidate['slot']}"}]
                if candidate["locked"] or record["selected_id"] == candidate_id:
                    self.author.confirm(images, data.get("confirm_ids") or [])
                self._remove_candidate(story, scene, target, record, candidate_id)
            else:
                raise ValueError("Unknown candidate action.")
            self.repository.write(record, story, scene, target)
            return self.author.target(story, scene, target)

    def _remove_candidate(self, story, scene, target, record, candidate_id):
        candidate = record["candidates"].pop(candidate_id)
        if candidate["image"]:
            (self.repository.folder(story, scene, target) / candidate["image"]).unlink(missing_ok=True)
        record["slots"][candidate["slot"] - 1] = None
        if record["selected_id"] == candidate_id:
            record["selected_id"] = None

    def image(self, story, scene, target, candidate_id) -> Path:
        record = self.repository.read(story, scene, target)
        candidate = record["candidates"].get(candidate_id)
        if not candidate or not candidate["image"]:
            raise KeyError("Image not found.")
        return self.repository.folder(story, scene, target) / candidate["image"]


def detail_without_jobs(detail):
    return {key: value for key, value in detail.items() if key not in {"jobs", "candidates", "slots"}}
