"""Durable interview, synthesis and candidate lifecycle; no legacy scene orchestration."""
from zet.services.llm_role_service import resolve_role_model
from dataclasses import asdict
from copy import deepcopy
import json
import hashlib
from pathlib import Path
import random

from zet.models.narrative import NarrativeCandidate, new_id
from zet.services.atomic_file_service import write_bytes_atomic
from zet.services.narrative_prompt_service import assemble_prompt, llm_request
from zet.services.narrative_interview_service import interview_review
from zet.services.narrative_proxy_service import NarrativeProxyService
from zet.services.workflow_storage import validate_image


ACTIVE = {"SUBMITTING", "QUEUED", "RUNNING", "DISPATCHING"}


class NarrativeGenerationService:
    def __init__(self, author):
        self.author = author
        self.repository = author.repository
        self.proxy = NarrativeProxyService(author.app)
        self.assembly = author.app.narrative_assembly_service
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
            restart_interview = kind == "restart_interview"
            if restart_interview:
                if data.get("retry_job_id"):
                    raise ValueError("Restart an interview from current inputs, without a retry job.")
                kind = "interview"
            replay = None
            if data.get("retry_job_id"):
                previous = record["jobs"].get(data["retry_job_id"], {})
                if previous.get("interview_history_cleared"):
                    raise ValueError("This interview was cleared. Continue the current interview instead.")
                if (previous.get("status") != "FAILED" or previous.get("kind") not in {"interview", "synthesize", "generate"}
                        or not (previous.get("detail", {}).get("kind") == "assembly"
                                or previous.get("detail", {}).get("source_snapshot", {}).get("image_file"))):
                    raise ValueError("Choose a failed assembly or backdrop adaptation job to retry.")
                replay = previous
                kind = previous["kind"]
            if kind in {"rerun_interview", "rerun_prompt"}:
                previous = record["jobs"].get(data.get("job_id"), {})
                if previous.get("interview_history_cleared"):
                    raise ValueError("This interview was cleared. Continue the current interview instead.")
                expected = {"interview"} if kind == "rerun_interview" else {"synthesize", "generate"}
                if previous.get("kind") not in expected:
                    raise ValueError("Choose a previous interview or prompt job.")
                replay = previous
                kind = "interview" if kind == "rerun_interview" else "synthesize"
            if kind not in {"interview", "synthesize", "generate", "render"}:
                raise ValueError("Unknown narrative generation action.")
            detail = self.author.target(story, scene, target)
            candidate_id = data.get("interview_candidate_id")
            if candidate_id and (data.get("action") not in {"interview", "restart_interview"} or detail["kind"] != "subscene"):
                raise ValueError("Images can only be attached to a new subscene interview.")
            model_field = "interview_model" if kind == "interview" else "prompt_model"
            model = resolve_role_model(self.author.app.config, "narrative_interview" if kind == "interview" else "narrative_prompt", record[model_field])
            evidence = deepcopy(replay.get("interview_evidence")) if replay else None
            payload = None
            if candidate_id:
                candidate = record["candidates"].get(candidate_id)
                if not candidate or candidate.get("status") != "COMPLETE" or not candidate.get("image"):
                    raise ValueError("The chosen rendered image is no longer available. Choose another image.")
                folder = self.repository.folder(story, scene, target).resolve()
                source = (folder / candidate["image"]).resolve()
                if not source.is_relative_to(folder) or not source.is_file():
                    raise ValueError("The chosen rendered image is unavailable.")
                payload = source.read_bytes()
                evidence = {"candidate_id": candidate_id, "slot": candidate["slot"], "sha256": hashlib.sha256(payload).hexdigest(), "suffix": source.suffix}
            elif evidence:
                folder = self.repository.folder(story, scene, target).resolve()
                source = (folder / evidence["file"]).resolve()
                if not source.is_relative_to(folder) or not source.is_file():
                    raise ValueError("The saved interview image is unavailable.")
                payload = source.read_bytes()
                if hashlib.sha256(payload).hexdigest() != evidence["sha256"]:
                    raise ValueError("The saved interview image has changed.")
            if evidence:
                from zet.services.ai_model_catalog_service import AIModelCatalogService
                AIModelCatalogService(self.author.app.config.base_ai_queue_path, config=self.author.app.config).validate(model, required=["vision"])
            if not replay and kind != "render" and detail.get("universe_style") and detail.get("style_source") != "target override" and not detail["universe_style"]["text"]:
                raise ValueError("Set the selected universe style before generating a prompt.")
            if restart_interview:
                record["interview"] = []
                detail["interview"] = []
                for previous in record["jobs"].values():
                    if previous["kind"] == "interview":
                        previous["interview_history_cleared"] = True
                        if previous.get("review", {}).get("status") == "pending":
                            previous["review"]["status"] = "superseded"
            baseline = detail_without_jobs(detail)
            if replay:
                detail = deepcopy(replay["detail"])
            if detail["kind"] == "backdrop" and detail.get("source_snapshot", {}).get("image_file"):
                if kind in {"generate", "render", "interview", "synthesize"} and detail.get("backdrop_link_mode") == "unmodified":
                    raise ValueError("Use the local reuse action for this backdrop mode.")
            if kind == "render" and detail["kind"] == "assembly" and record["prompt_provenance"].get("assembly_mode", "finish_composite") != detail.get("assembly_mode", "finish_composite"):
                raise ValueError("The prompt belongs to another assembly mode. Write or edit the prompt before rendering.")
            refs = [] if detail["kind"] == "assembly" else (deepcopy(replay["references"]) if replay else self.author.references(detail))
            job = {"id": new_id(), "kind": kind, "status": "SUBMITTING", "error": "", "detail": detail_without_jobs(detail),
                   "references": refs, "candidate_ids": [], "result": None, "baseline": baseline,
                   "model": model, "provider": "codex" if model.startswith("codex:") else "ollama",
                   "provenance": {"model": model, "provider": "codex" if model.startswith("codex:") else "ollama"}}
            if evidence:
                evidence["file"] = f"snapshots/{job['id']}/interview-image{evidence.get('suffix', '.png')}"
                write_bytes_atomic(self.repository.folder(story, scene, target) / evidence["file"], payload)
                job["interview_evidence"] = evidence
            job["provenance"]["visual_style"] = {"source": detail.get("style_source", "saved scene"),
                                                  "text": detail["context"].get("style", ""),
                                                  "universe": detail.get("universe_style")}
            if kind == "render":
                job["provenance"]["visual_style"] = deepcopy(detail.get("prompt_provenance", {}).get(
                    "visual_style", {"source": "saved prompt; style metadata unavailable", "text": ""}))
            if detail["kind"] == "assembly":
                mode = detail.get("assembly_mode", "finish_composite")
                job["assembly_mode"] = job["provenance"]["assembly_mode"] = mode
                snapshot, refs = self.assembly.snapshot(story, scene, detail, job["id"],
                                                        include_composite=kind in {"generate", "render"})
                job["assembly_snapshot"], job["references"] = snapshot, refs
                job["detail"]["layers"] = snapshot["layers"]
                job["detail"]["assembly_references"] = refs
                detail = job["detail"]
            else:
                # Freeze reference bytes as well as their ordered bindings before dispatch.
                if replay:
                    refs = deepcopy(replay["references"])
                frozen = []
                for index, reference in enumerate(refs):
                    source = Path(reference["path"])
                    path = self.repository.folder(story, scene, target) / "snapshots" / job["id"] / f"reference-{index}{source.suffix}"
                    write_bytes_atomic(path, source.read_bytes())
                    frozen.append({**reference, "path": str(path)})
                job["references"] = frozen
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
                    if detail["kind"] == "assembly":
                        candidate["assembly_mode"] = job["assembly_mode"]
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
                    message = replay.get("message", "") if replay else str(data.get("message") or "")
                    job["message"] = message
                    if kind == "interview":
                        record["interview"].append({"role": "user", "text": message})
                    request, schema = llm_request(detail, kind, message, interview_evidence=evidence)
                    job["request"], job["schema"] = request, schema
                    # Exact replay also retains original request wording and interview history.
                    if replay and replay.get("request"):
                        job["request"] = replay["request"]
                        schema = deepcopy(replay.get("schema", schema))
                        job["schema"] = schema
                    self.repository.write(record, story, scene, target)
                    self.proxy.publish(story, scene, target, job, job["request"], schema=schema)
                    job["status"] = "QUEUED"
            except Exception as exc:
                from zet.services.storage_health_service import pause_on_storage_error
                pause_on_storage_error(self.author.app.config, exc)
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
            candidate["prompt"] = prompt
            if parent["detail"].get("source_snapshot", {}).get("image_file"):
                candidate["source_snapshot"] = deepcopy(parent["detail"]["source_snapshot"])
                candidate["backdrop_adaptation"] = deepcopy(parent["detail"].get("backdrop_adaptation", {}))
            candidate["prompt_provenance"] = deepcopy(parent["detail"].get("prompt_provenance", {}) if parent["kind"] == "render" else
                                                        {**parent.get("provenance", {}), "job_id": parent["id"], "edited": False})
            if parent.get("assembly_snapshot"):
                candidate["assembly_snapshot"] = parent["assembly_snapshot"]
                candidate["assembly_mode"] = job["assembly_mode"] = parent.get("assembly_mode", "finish_composite")
            self.repository.write(record, story, scene, target)
            try:
                self.proxy.publish(story, scene, target, job, prompt, references=parent["references"],
                                   width=parent["detail"]["width"], height=parent["detail"]["height"], seed=candidate["seed"])
                job["status"] = candidate["status"] = "QUEUED"
            except Exception as exc:
                from zet.services.storage_health_service import pause_on_storage_error
                pause_on_storage_error(self.author.app.config, exc)
                job["status"] = candidate["status"] = "FAILED"
                job["error"] = candidate["error"] = str(exc)
            self.repository.write(record, story, scene, target)

    def _refresh(self, story, scene, target, record):
        release = []
        for job in list(record["jobs"].values()):
            if job["status"] == "SUBMITTING":
                if job["kind"] == "image":
                    candidate = record["candidates"].get(job.get("candidate_id"))
                    if not candidate or candidate.get("job_id") != job["id"]:
                        job.update(status="SUPERSEDED", error="")
                        continue
                    parent = next((item for item in record["jobs"].values()
                                   if candidate["id"] in item.get("candidate_ids", [])), None)
                    if not parent:
                        self._fail(record, job, "Recovery requires the saved parent request and frozen references.")
                        continue
                    self.proxy.publish(story, scene, target, job, candidate["prompt"],
                        references=parent["references"], width=parent["detail"]["width"],
                        height=parent["detail"]["height"], seed=candidate["seed"])
                elif job.get("request") and job.get("schema") is not None:
                    self.proxy.publish(story, scene, target, job, job["request"], schema=job["schema"])
                else:
                    self._fail(record, job, "Recovery requires the saved request and schema; restore them or explicitly retry this task.")
                    continue
                job["status"] = "QUEUED"
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
                            if candidate.get("assembly_snapshot"):
                                result = self.assembly.finish(story, scene, target, candidate["assembly_snapshot"], result)
                            relative = f"images/{candidate['id']}.png"
                            write_bytes_atomic(self.repository.folder(story, scene, target) / relative, result)
                            candidate["image"] = relative
                    else:
                        value = json.loads(result.decode("utf-8"))
                        if job["kind"] == "interview":
                            self._store_interview_review(record, job, value)
                            job["result"] = value
                        else:
                            prompt = assemble_prompt(job["detail"], value, job["references"])
                            job["result"] = prompt
                            if (record["active_llm_job"] == job["id"] and record["prompt"] == job.get("baseline", job["detail"])["prompt"]
                                    and self._same_mode(record, job["detail"])):
                                record["prompt"] = prompt
                                record["prompt_provenance"] = {**job.get("provenance", {}), "job_id": job["id"], "edited": False}
                            if job["kind"] == "generate":
                                job["status"] = "DISPATCHING"
                                self.repository.write(record, story, scene, target)
                                self._stage_renders(story, scene, target, record, job, prompt)
                                job["status"] = "COMPLETE"
                except (ValueError, KeyError, TypeError, OSError) as exc:
                    self._fail(record, job, str(exc))
                    if job["kind"] == "image" and candidate:
                        candidate.update(status="FAILED", error=str(exc))
            if state in {"COMPLETE", "FAILED"}:
                release.append(job)
        self.repository.write(record, story, scene, target)
        for job in release:
            self.proxy.release(story, scene, target, job)

    @staticmethod
    def _same_mode(record, frozen):
        return (record.get("backdrop_link_mode", "reference") == frozen.get("backdrop_link_mode", "reference")
                and record.get("assembly_mode", "finish_composite") == frozen.get("assembly_mode", "finish_composite")
                and (record.get("kind") != "subscene"
                     or record.get("use_transparent_background", True) == frozen.get("use_transparent_background"))
                and record.get("backdrop_adaptation", {}) == frozen.get("backdrop_adaptation", {})
                and record.get("source_snapshot", {}).get("snapshot_id") == frozen.get("source_snapshot", {}).get("snapshot_id"))

    @staticmethod
    def _store_interview_review(record, job, result):
        review = interview_review(result, job["detail"], job["id"])
        findings = result.get("visual_findings", "")
        if job.get("interview_evidence") and not isinstance(findings, str):
            raise ValueError("The interview returned invalid visual findings.")
        if (record["active_llm_job"] != job["id"]
                or job.get("interview_history_cleared")
                or not NarrativeGenerationService._same_mode(record, job["detail"])):
            review["status"] = "superseded"
        job["review"] = review
        if job.get("interview_history_cleared"):
            return
        record["interview"].append({"role": "assistant", "text": "\n".join(review["questions"]),
                                    "job_id": job["id"], "provenance": job.get("provenance", {}),
                                    "conflicts": review["conflicts"],
                                    **({"visual_findings": findings, "image_slot": job["interview_evidence"]["slot"]} if job.get("interview_evidence") else {})})

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
            if action in {"select", "lock"} and (record.get("scene_text") or candidate.get("scene_text_final")):
                state = self.author.app.narrative_scene_text_service.state(story, scene, target, candidate_id)
                if candidate.get("scene_text_final", {}).get("token") != state["token"]:
                    raise ValueError("Confirm scene text on this image before selecting or locking.")
            if action == "select":
                record["selected_id"] = candidate_id
            elif action == "lock":
                for other_id, other in record["candidates"].items():
                    other["locked"] = other_id == candidate_id
            elif action == "unlock":
                candidate["locked"] = False
            elif action == "retry":
                if candidate["status"] != "FAILED" or not (candidate.get("assembly_snapshot") or candidate.get("source_snapshot")):
                    raise ValueError("Choose a failed assembly or backdrop adaptation candidate to retry.")
                parent = next((job for job in record["jobs"].values() if candidate_id in job.get("candidate_ids", [])), None)
                if parent is None or not candidate.get("prompt"):
                    raise ValueError("This candidate has no frozen render request. Generate from inputs again.")
                candidate.update(job_id=None, status="SUBMITTING", error="")
                self._stage_renders(story, scene, target, record, {**parent, "candidate_ids": [candidate_id]}, candidate["prompt"])
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
        import shutil
        lettering_root = (self.repository.folder(story, scene, target) / "lettering").resolve()
        lettering = (lettering_root / candidate_id).resolve()
        if lettering.parent != lettering_root:
            raise ValueError("Invalid lettering artifact identity.")
        if lettering.is_dir():
            shutil.rmtree(lettering)
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
    return {key: deepcopy(value) for key, value in detail.items() if key not in {"jobs", "candidates", "slots", "assembly_sources"}}
