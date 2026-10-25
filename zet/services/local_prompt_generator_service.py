"""Private, packet-bound render prompt drafting and four-seed trials."""
from __future__ import annotations

import base64
from copy import deepcopy
from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import shutil
from uuid import uuid4

from zet.models.prompt_generator import (
    PROMPT_PACKET_VERSION, PromptPacket, PROMPT_SESSION_VERSION,
)
from zet.services.atomic_file_service import write_bytes_atomic
from zet.services.library_reference_service import pipeline_library_root_for_path, read_library_json, write_library_json
from zet.services.prompt_generator_cycle_service import PromptGeneratorCycle
from zet.services.workflow_storage import file_lock

_CITATION = re.compile(r"\{\{REF:([A-Za-z0-9_-]+)\}\}")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class LocalPromptGeneratorService(PromptGeneratorCycle):
    """Owns immutable packet snapshots, drafts, private render attempts and adoption."""

    PIPELINES = {"costume-dressing", "head-image-edit"}

    def __init__(self, app, project_root):
        self.app = app
        self.project_root = Path(project_root).resolve()

    def _workflow(self, pipeline, run_id, costume):
        if pipeline not in self.PIPELINES:
            raise ValueError("The prompt generator pilot supports Costume-Dressing and Head-Image Edit.")
        from zet.services.local_image_workflow_service import LocalImagePipelineWorkflowService
        workflow = LocalImagePipelineWorkflowService(self.app, self.project_root, pipeline)
        run = workflow.prompt_improvement.detail(run_id, costume if pipeline == "costume-dressing" else "")
        return workflow, run

    @staticmethod
    def _session_path(run, session_id):
        if not re.fullmatch(r"[a-f0-9]{32}", str(session_id or "")):
            raise ValueError("Invalid prompt-generator session ID.")
        return Path(run["root"]) / "prompt_generator" / session_id / "session.json"

    def _read(self, run, session_id):
        path = self._session_path(run, session_id)
        record = read_library_json(path, pipeline_library_root_for_path(path))
        if record.get("version") not in {1, PROMPT_SESSION_VERSION}:
            raise ValueError("Unsupported prompt-generator session version.")
        if record.get("universe_id") != self.app.universe_id or record.get("run_id") != run["run_id"]:
            raise ValueError("Prompt-generator session belongs to another universe or batch.")
        return self._upgrade_record(record)

    def _write(self, run, record):
        path = self._session_path(run, record["session_id"])
        record["version"] = PROMPT_SESSION_VERSION
        record["revision"] = int(record.get("revision", 0)) + 1
        write_library_json(path, record, pipeline_library_root_for_path(path))


    def _submit(self, method, pipeline, run_id, costume, session_id, task, owner):
        from zet.services.ai_workflow_service import AIWorkflowService
        AIWorkflowService(self.app).submit(method, [pipeline, run_id, costume, session_id, task],
            service="prompt_generator", key=f"promptgen_{session_id}_{task}", owner=owner)

    def _packet(self, workflow, run, view, session_dir, criteria):
        session_dir.mkdir(parents=True, exist_ok=True)
        output = session_dir / "compiled"
        baseline_dir = session_dir / "baseline-input"
        saved = workflow.slots.prepare_input(run, view, baseline_dir, recompile=True, output_dir=output)
        from zet.services.local_render_backend_service import LocalRenderBackendService
        preset_service = LocalRenderBackendService(self.app.config.state_file(self.project_root, "Local_Render_Presets.json"), config=self.app.config)
        saved["render_settings"] = deepcopy(saved.get("render_settings") or preset_service.preset(saved.get("preset", "")))
        prompt = str(saved.get("prompt") or "")
        if not prompt:
            raise ValueError("The compiler returned an empty baseline prompt.")
        from zet.services.prompt_packet_metadata import extract_prompt_packet_metadata
        prompt, declarations = extract_prompt_packet_metadata(prompt)
        declaration_ids = set()
        raw_declarations = [*declarations, *saved.get("prompt_packet_declarations", [])]
        for raw_declaration in raw_declarations:
            try:
                declaration = json.loads(raw_declaration) if isinstance(raw_declaration, str) else raw_declaration
            except ValueError as exc:
                raise ValueError("ZET:PROMPT_PACKET must contain valid JSON.") from exc
            if declaration.get("version") != PROMPT_PACKET_VERSION or not isinstance(declaration.get("references", []), list):
                raise ValueError("Unsupported ZET:PROMPT_PACKET declaration.")
            for reference in declaration.get("references", []):
                if not isinstance(reference, dict) or not isinstance(reference.get("source"), dict):
                    raise ValueError("Each ZET:PROMPT_PACKET reference needs an explicit source selector.")
                ref_id = str(reference.get("id") or "").strip()
                if not ref_id or ref_id in declaration_ids:
                    raise ValueError("ZET:PROMPT_PACKET reference IDs must be non-empty and unique.")
                declaration_ids.add(ref_id)
                if reference.get("audience", "analysis") not in {"analysis", "render", "both"}:
                    raise ValueError("Reference audience must be analysis, render, or both.")
                views = reference.get("views") or []
                if not isinstance(views, list):
                    raise ValueError("ZET:PROMPT_PACKET applicable views must be a list.")
                if views and any(not isinstance(item, str) or not re.fullmatch(r"[A-Z0-9_]+", item.upper()) for item in views):
                    raise ValueError("ZET:PROMPT_PACKET contains an invalid applicable view.")
                if not views or view in {str(item).upper() for item in views}:
                    declarations.append(reference)
        render_refs = []
        render_dir = session_dir / "render-references"
        render_dir.mkdir(parents=True, exist_ok=True)
        for index, ref in enumerate(saved.get("references") or [], 1):
            frozen = deepcopy(ref)
            source = Path(str(frozen.get("path") or ""))
            if not source.is_file():
                raise ValueError(f"Render reference {index} is missing while preparing the packet.")
            target = render_dir / f"{index}{source.suffix.lower()}"
            shutil.copy2(source, target)
            frozen.update(path=str(target), sha256=_sha(target.read_bytes()), id=f"render-{index}", audience="render")
            render_refs.append(frozen)
        analysis_refs = list(render_refs)
        for index, declaration in enumerate(declarations, 1):
            ref = self._resolve_declaration(run, declaration)
            target_dir = session_dir / "analysis-references"
            target_dir.mkdir(parents=True, exist_ok=True)
            source = Path(ref["path"])
            target = target_dir / f"{index}{source.suffix.lower()}"
            shutil.copy2(source, target)
            ref.update(id=str(declaration.get("id") or f"analysis-{index}"),
                       path=str(target), sha256=_sha(target.read_bytes()))
            audience = declaration.get("audience", "analysis")
            if audience not in {"analysis", "render", "both"}:
                raise ValueError("Reference audience must be analysis, render, or both.")
            if audience in {"analysis", "both"}:
                analysis_refs.append(ref)
            if audience in {"render", "both"}:
                render_refs.append(ref)
        # Rendering indices are assigned only after the complete ordered binding is fixed.
        for index, ref in enumerate(render_refs, 1):
            ref["render_index"] = index
        metadata = {"universe_id": self.app.universe_id, "pipeline": workflow.pipeline,
            "run_id": run["run_id"], "costume": str(run.get("costume") or ""), "view": view,
            "operation": "edit" if render_refs else "generate", "prompt": prompt,
            "baseline_prompt": prompt,
            "facts": deepcopy(saved.get("compiler_facts") or {}),
            "render_preset": saved.get("preset", ""),
            "render_settings": saved.get("render_settings", {}),
            "instruction_modules": self._instruction_modules(workflow.pipeline, "edit" if render_refs else "generate"),
            "references": [{k: ref.get(k) for k in ("id", "role", "label", "audience", "sha256", "render_index")}
                           for ref in render_refs],
            "analysis_references": [{k: ref.get(k) for k in ("id", "role", "label", "audience", "sha256", "render_index")}
                                    for ref in analysis_refs],
            "required_constraints": self._required_constraints(workflow, run, view, prompt),
            "sources": self._source_hashes(run, workflow, view), "criteria": list(criteria),
            "revision": 1, "version": PROMPT_PACKET_VERSION}
        packet_id = uuid4().hex
        packet_hash = _sha(json.dumps(metadata, sort_keys=True, ensure_ascii=False).encode())
        metadata.update(packet_id=packet_id, packet_hash=packet_hash,
            baseline_input={**saved, "prompt": prompt, "references": render_refs},
            analysis_references=analysis_refs)
        return PromptPacket(**{key: metadata[key] for key in PromptPacket.__dataclass_fields__ if key in metadata}).to_dict()

    @staticmethod
    def _instruction_modules(pipeline, operation):
        from zet.services.llm_role_service import get_role, skill_modules
        from zet.services.llm_skill_service import SKILL_ROOT
        role = get_role("prompt_generator")
        modules = skill_modules(role, operation)
        modules.append(f"adapters/prompt_generator-{pipeline}.md")
        manifest_bytes = (SKILL_ROOT / "manifest.json").read_bytes()
        manifest = json.loads(manifest_bytes)
        return {"package": "qwen-image-2.1", "integration_version": manifest["integration_version"],
                "manifest_sha256": _sha(manifest_bytes),
                "modules": [{"path": name, "sha256": _sha((SKILL_ROOT / name).read_bytes())} for name in modules]}

    @staticmethod
    def _revise_packet(record, **changes):
        history = record.setdefault("packet_revisions", [])
        history.append(deepcopy(record["packet"]))
        revised = deepcopy(record["packet"])
        revised.update(changes, revision=len(history) + 1, packet_id=uuid4().hex)
        revised["packet_hash"] = _sha(json.dumps({k: v for k, v in revised.items()
            if k not in {"packet_id", "packet_hash", "baseline_input", "analysis_references"}},
            sort_keys=True, ensure_ascii=False).encode())
        record["packet"] = revised
        record["active_draft"] = None
        return revised

    @staticmethod
    def _required_constraints(workflow, run, view, prompt):
        # Adapters may export explicit constraint lists without changing the prose compiler.
        provider = getattr(workflow.adapter, "prompt_packet_constraints", None)
        if callable(provider):
            return [str(item).strip() for item in provider(run, view) if str(item).strip()]
        return []

    @staticmethod
    def _source_hashes(run, workflow, view):
        result = {}
        for name, path_value in (("character", Path(workflow.adapter.character_root) / run["character"] / run["phase"] / "Character.md"),
                                 ("costume", Path(str(run.get("costume_path") or "")))):
            if path_value.is_file():
                result[name] = _sha(path_value.read_bytes())
        for ref in (run.get("sources") or {}).get(view, {}).values():
            result[str(ref.get("key") or ref.get("role") or uuid4().hex)] = str(ref.get("sha256") or "")
        return result

    def _resolve_declaration(self, run, declaration):
        source = declaration.get("source") or {}
        kind = source.get("kind")
        candidates = []
        if kind == "batch_view":
            view = str(source.get("view") or "").upper()
            if source.get("state") == "selected":
                cid = (run.get("selected_views") or {}).get(view)
                candidates = [item for item in run.get("candidates", []) if item.get("candidate_id") == cid and item.get("view") == view]
            elif source.get("state") == "locked":
                from zet.services.local_asset_store_service import LocalAssetStoreService
                asset_store = LocalAssetStoreService(self.app.config.base_library_path)
                key = asset_store.key("Costume-Dressing" if run["kind"] == "costume-dressing" else "Head-Image-Edit", view)
                record = (run.get("local_assets") or {}).get(key) or {}
                if record.get("locked"):
                    candidates = [{"image_path": record.get("locked_image_path"), "candidate_id": record.get("candidate_id"), "view": view, "label": f"Locked {view}"}]
        elif kind == "locked_pipeline":
            from zet.services.local_asset_store_service import LocalAssetStoreService
            pipeline = str(source.get("pipeline") or "")
            qualifier = str(source.get("qualifier") or "")
            assets = LocalAssetStoreService(self.app.config.base_library_path).locked_assets(
                run["character"], run["phase"], pipeline=pipeline, qualifier=qualifier)
            candidates = [item for item in assets if item.get("view") == str(source.get("view") or "").upper()]
        elif kind == "inventory_tag":
            tag = str(source.get("tag") or "").strip()
            refs = [ref for ref in run.get("render_inputs", {}).values() if ref.get("tag") == tag]
            if refs:
                candidates = refs
            else:
                from Scripts.Auxiliary_Resource_Tags import auxiliary_references_for_texts
                refs = auxiliary_references_for_texts(self.project_root, [f"{{{{IMAGE:{tag}}}}}" if tag.startswith("img_")
                    else f"{{{{LIB:REF:{tag}}}}}"], [], universe_root=self.app.config.base_library_path)
                candidates = refs
        elif kind == "render_reference":
            ref_id = str(source.get("id") or "")
            session_refs = run.get("render_inputs", {}).get(ref_id)
            if session_refs:
                candidates = [session_refs]
        if len(candidates) != 1:
            raise ValueError(f"Declared reference {declaration.get('id') or kind!r} is missing or ambiguous.")
        item = candidates[0]
        path = Path(str(item.get("image_path") or item.get("locked_image_path") or item.get("path") or ""))
        if not path.is_file():
            raise ValueError(f"Declared reference {declaration.get('id') or kind!r} is unavailable.")
        return {"path": str(path), "role": str(declaration.get("role") or "subject_reference"),
                "label": str(declaration.get("label") or item.get("label") or kind),
                "candidate_id": str(item.get("candidate_id") or ""), "view": str(item.get("view") or ""),
                "source": deepcopy(source)}


    @staticmethod
    def _owner(record):
        return {"universe_id": record["universe_id"], "pipeline": record["pipeline"],
                "local_run_id": record["run_id"], "prompt_generator_session_id": record["session_id"]}

    @staticmethod
    def _validate_draft(packet, draft):
        if (draft.get("packet_id") != packet["packet_id"]
                or draft.get("packet_hash") != packet["packet_hash"]):
            raise ValueError("Draft belongs to another prompt packet.")
        text = str(draft.get("prompt") or "").strip()
        if not text:
            raise ValueError("The generated prompt is empty.")
        allowed = {str(ref.get("id")) for ref in packet.get("analysis_references", [])}
        citations = set(_CITATION.findall(text))
        declared_ids = set(str(item) for item in draft.get("reference_ids", []))
        if declared_ids - allowed or declared_ids != citations:
            raise ValueError("Structured reference IDs must match the valid image citations in the prompt.")
        if citations - allowed:
            raise ValueError("Prompt refers to an image that was not supplied for analysis.")
        rendered = {str(ref.get("id")) for ref in packet["baseline_input"].get("references", [])}
        if citations - rendered:
            raise ValueError("Prompt cites a reference that is not attached to the renderer.")
        if re.search(r"\{\{(?!REF:)[^}]+\}\}", text):
            raise ValueError("Prompt contains an unresolved template placeholder.")
        required = list(packet.get("required_constraints") or [])
        normalized = _CITATION.sub(lambda match: LocalPromptGeneratorService._render_citation(match.group(1), packet["baseline_input"]["references"]), text)
        missing = [line for line in required if line not in normalized]
        if missing:
            raise ValueError("Prompt omits compiler constraints: " + " ".join(missing[:3]))
        return text


    @staticmethod
    def _render_citation(ref_id, refs):
        ref = next((item for item in refs if item.get("id") == ref_id), None)
        if ref is None or not ref.get("render_index"):
            raise ValueError(f"Prompt citation {ref_id!r} is not attached to the renderer.")
        return f"Image {ref['render_index']}"

    def _render_job(self, pipeline, run_id, costume, session_id, task_id):
        from zet.services.ai_workflow_service import AIPending
        from zet.services.ai_job_coordinator import image_services
        _, run = self._workflow(pipeline, run_id, costume)
        record = self._read(run, session_id)
        round_record = next((item for item in record["history"]
                             if item["id"] == task_id or any(attempt.get("dispatch_task_id") == task_id
                             for attempt in item.get("attempts", []))), None)
        if round_record is None:
            return
        if record["status"] in self.TERMINAL or not any(t["id"] == task_id for t in record["pending"]):
            return
        generation = image_services(self.app)[0]
        for attempt in round_record["attempts"]:
            if attempt["status"] not in {"QUEUED", "SUBMITTED"} or attempt.get("dispatch_task_id", task_id) != task_id:
                continue
            current = self._read(run, session_id)
            if current["status"] in self.TERMINAL or not any(item.get("id") == task_id for item in current.get("pending", [])):
                return
            try:
                saved = attempt["input"]
                profile = saved.get("render_settings") or {}
                refs = [{"label": str(ref.get("label") or ref.get("role") or f"Image {i}"),
                         "image": base64.b64encode(Path(ref["path"]).read_bytes()).decode("ascii")}
                        for i, ref in enumerate(saved["references"], 1)]
                spec = {"mode": "img2img" if refs else "txt2img", "prompt": saved["prompt"], "count": 1,
                    "width": profile.get("width", 832), "height": profile.get("height", 1216),
                    "render_config": {"preset": saved["preset"], "checkpoint": profile.get("diffusion_model", ""),
                        "disable_prompt_globals": True, "append_reference_labels": False,
                        "overrides": {key: profile[key] for key in ("steps", "cfg", "sampler_name", "scheduler", "denoise", "text_encoder", "vae") if key in profile}},
                    "ai_owner": {**self._owner(record), "attempt_id": attempt["id"]}, "ai_workflow": "Prompt Generator Pilot"}
                if refs:
                    spec["reference_images"] = refs
                try:
                    result = generation.status(attempt["request_id"])
                except KeyError:
                    result = generation.submit(spec, request_id=attempt["request_id"], seeds=[attempt["seed"]])
                if result.get("images"):
                    contents, mime = generation.image(attempt["request_id"], 0)
                    suffix = {"image/jpeg": ".jpg", "image/webp": ".webp"}.get(mime, ".png")
                    image_path = self._session_path(run, session_id).parent / "trials" / (attempt["id"] + suffix)
                    outcome = {"status": "READY", "image_path": str(image_path), "sha256": _sha(contents), "error": ""}
                elif result["status"] in {"ERROR", "FAILED", "CANCELLED", "PARTIAL"}:
                    outcome = {"status": "FAILED", "error": result.get("error") or "Render failed."}
                else:
                    outcome = {"status": "SUBMITTED", "error": ""}
            except AIPending:
                outcome = {"status": "SUBMITTED", "error": ""}
            except Exception as exc:
                outcome = {"status": "FAILED", "error": str(exc)}
            path = self._session_path(run, session_id)
            with file_lock(path.with_suffix(".lock")):
                current = self._read(run, session_id)
                target_round = next((item for item in current["history"]
                                     if item["id"] == task_id or any(
                                         value.get("dispatch_task_id") == task_id
                                         for value in item.get("attempts", []))), None)
                if not target_round or current["status"] in self.TERMINAL or not any(t["id"] == task_id for t in current["pending"]):
                    return
                if outcome["status"] == "READY":
                    write_bytes_atomic(Path(outcome["image_path"]), contents)
                target = next(item for item in target_round["attempts"] if item["id"] == attempt["id"])
                target.update(outcome)
                if all(item["status"] in {"READY", "FAILED"} for item in self._attempts(target_round)):
                    current["pending"] = [item for item in current.get("pending", []) if item.get("id") != task_id]
                    self._after_images(current, target_round)
                    target_round["completed_at"] = _stamp()
                    target_round["completed_count"] = sum(1 for item in self._attempts(target_round) if item["status"] == "READY")
                self._write(run, current)

        fresh = self._read(run, session_id)
        self._resume(run, fresh)
        if any(attempt["status"] in {"QUEUED", "SUBMITTED"}
               for item in fresh.get("history", [])
               if item.get("id") == task_id or any(value.get("dispatch_task_id") == task_id for value in item.get("attempts", []))
               for attempt in item.get("attempts", [])):
            raise AIPending()

    def adopt(self, pipeline, run_id, costume, session_id, payload):
        _, run = self._workflow(pipeline, run_id, costume)
        path = self._session_path(run, session_id)
        with file_lock(path.with_suffix(".lock")):
            record = self._read(run, session_id)
            round_record = next((item for item in record["history"] if item["id"] == payload.get("round_id")), None)
            attempt = next((item for item in (round_record or {}).get("attempts", []) if item["id"] == payload.get("attempt_id")), None)
            if not attempt or attempt.get("status") != "READY":
                raise ValueError("Choose a completed pilot render to adopt.")
            if record["status"] == "SCRAPPED" or record["status"] == "CANCELLED":
                raise ValueError("Archived runs are read-only.")
            if payload.get("revision") != record.get("revision"):
                raise ValueError("This run changed. Reload before adopting an image.")
            review = attempt.get("human_correction") or {}
            if not review.get("confirmed") or review.get("decision") != "accept":
                raise ValueError("Confirm an accepted image review before adoption.")
            if attempt.get("adopted_candidate_id"):
                raise ValueError("This image has already been adopted.")
            from zet.services.render_slot_service import slot_maps
            from zet.services.local_image_pipeline_policy import mutate_local_run_state
            slots = slot_maps(run)
            if None not in slots[record["view"]]:
                raise ValueError("Choose and clear an empty slot before adopting a pilot render.")
            cid = uuid4().hex
            source = Path(attempt["image_path"])
            from zet.services.prompt_generator_review_service import verified_images
            verified_images([attempt])
            destination = Path(run["root"]) / "renders" / cid / source.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            candidate = {"candidate_id": cid, "view": record["view"], "status": "COMPLETE",
                "render_status": "COMPLETE", "image_path": str(destination), "image_sha256": attempt["sha256"],
                "prompt": attempt["input"]["prompt"], "render_input": deepcopy(attempt["input"]),
                "prompt_generator": {"session_id": session_id, "packet_hash": round_record["packet_hash"],
                                     "packet_id": round_record["packet_id"],
                                     "packet_revision": round_record["packet_revision"],
                                     "round_id": round_record["id"], "attempt_id": attempt["id"],
                                     "prompt": attempt["input"]["prompt"],
                                     "authoring_prompt": round_record["prompt"],
                                     "preset": attempt["input"].get("preset", ""),
                                     "criteria": round_record.get("criteria", []),
                                     "seed": attempt["seed"], "model": round_record.get("model", ""),
                                     "references": [{k: ref.get(k) for k in ("id", "role", "label", "sha256", "render_index", "candidate_id", "view", "tag")}
                                                    for ref in attempt["input"].get("references", [])]},
                "human_review": {"decision": "undecided"}}
            def update(state):
                current_slots = slot_maps({**run, "slots_by_view": {
                    **(run.get("slots_by_view") or {}), **(state.get("slots_by_view") or {})}})
                if None not in current_slots[record["view"]]:
                    raise ValueError("The empty slot changed. Clear a slot and retry adoption.")
                current_slots[record["view"]][current_slots[record["view"]].index(None)] = cid
                state.setdefault("added_candidates", {})[cid] = candidate
                state["slots_by_view"] = current_slots
                state["slot_version"] = int(state.get("slot_version", 0)) + 1
            mutate_local_run_state(Path(run["root"]), update)
            attempt["adopted_candidate_id"] = cid
            record["adopted_candidate_id"] = cid
            self._write(run, record)
        return self.detail(pipeline, run_id, costume, session_id)


    def image_path(self, pipeline, run_id, costume, session_id, attempt_id):
        _, run = self._workflow(pipeline, run_id, costume)
        record = self._read(run, session_id)
        for round_record in record.get("history", []):
            for attempt in round_record.get("attempts", []):
                if attempt.get("id") == attempt_id and attempt.get("status") == "READY":
                    path = Path(str(attempt.get("image_path") or ""))
                    if path.is_file() and path.resolve().is_relative_to(self._session_path(run, session_id).parent.resolve()):
                        return path
        raise FileNotFoundError("Prompt-generator image is unavailable.")
