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
    MAX_CASE_LLM_CALLS, MAX_CASE_RENDER_SUBMISSIONS, PROMPT_PACKET_VERSION,
    PROMPT_SESSION_VERSION, SEED_COUNT, TRIAL_ROUNDS,
)
from zet.services.atomic_file_service import write_bytes_atomic, write_json_atomic
from zet.services.library_reference_service import pipeline_library_root_for_path, read_library_json, write_library_json
from zet.services.workflow_storage import file_lock

_CITATION = re.compile(r"\{\{REF:([A-Za-z0-9_-]+)\}\}")


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _stamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class LocalPromptGeneratorService:
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
        if record.get("version") != PROMPT_SESSION_VERSION:
            raise ValueError("Unsupported prompt-generator session version.")
        if record.get("universe_id") != self.app.universe_id or record.get("run_id") != run["run_id"]:
            raise ValueError("Prompt-generator session belongs to another universe or batch.")
        return record

    def _write(self, run, record):
        path = self._session_path(run, record["session_id"])
        write_library_json(path, record, pipeline_library_root_for_path(path))

    def _pilot_ledger_path(self):
        return (Path(self.app.config.base_library_path) / "_state" / "PromptGeneratorPilot"
                / f"{self.app.universe_id}.json")

    def _reserve_pilot_budget(self, record, kind, amount):
        path = self._pilot_ledger_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with file_lock(path.with_suffix(".lock")):
            try:
                ledger = read_library_json(path, Path(self.app.config.base_library_path))
            except FileNotFoundError:
                ledger = {"version": 1, "universe_id": self.app.universe_id,
                          "llm_calls": 0, "render_submissions": 0, "cases": {}}
            if ledger.get("version") != 1 or ledger.get("universe_id") != self.app.universe_id:
                raise ValueError("Prompt-generator pilot budget ledger is invalid or belongs to another universe.")
            field, limit = (("llm_calls", 36) if kind == "llm" else ("render_submissions", 48))
            if int(ledger.get(field, 0)) + amount > limit:
                raise ValueError(f"The three-case pilot has used its {limit} {field.replace('_', ' ')}.")
            counters = ledger.setdefault("cases", {}).setdefault(record["session_id"],
                {"pipeline": record["pipeline"], "run_id": record["run_id"], "costume": record["costume"],
                 "view": record["view"], "llm_calls": 0, "render_submissions": 0})
            ledger[field] = int(ledger.get(field, 0)) + amount
            counters[field] = int(counters.get(field, 0)) + amount
            write_library_json(path, ledger, Path(self.app.config.base_library_path))

    def _pilot_stats(self):
        try:
            ledger = read_library_json(self._pilot_ledger_path(), Path(self.app.config.base_library_path))
        except (FileNotFoundError, OSError, ValueError):
            ledger = {}
        return {"llm_calls": int(ledger.get("llm_calls", 0)),
                "render_submissions": int(ledger.get("render_submissions", 0)),
                "case_count": len(ledger.get("cases", {}))}

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

    def open(self, pipeline, run_id, costume, payload):
        workflow, run = self._workflow(pipeline, run_id, costume)
        view = str(payload.get("view") or "").upper()
        if view not in run.get("views", []):
            raise ValueError("Choose a rendered view for the prompt-generator pilot.")
        ledger_path = self._pilot_ledger_path()
        with file_lock(ledger_path.with_suffix(".lock")):
            try:
                ledger = read_library_json(ledger_path, Path(self.app.config.base_library_path))
            except FileNotFoundError:
                ledger = {"cases": {}}
        for existing_id, case in ledger.get("cases", {}).items():
            if (case.get("pipeline"), case.get("run_id"), case.get("costume"), case.get("view")) == (pipeline, run_id, costume, view):
                return self.detail(pipeline, run_id, costume, existing_id)
        if len(ledger.get("cases", {})) >= 3:
            raise ValueError("The three-case pilot already has three prepared cases.")
        selected = [item for item in run.get("candidates", []) if item.get("view") == view
                    and (item.get("candidate_id") == (run.get("selected_views") or {}).get(view)
                         or item.get("image_available") or Path(str(item.get("image_path") or "")).is_file())]
        if not selected:
            raise ValueError("Render this view before opening a prompt-generator session.")
        session_id = uuid4().hex
        session_dir = self._session_path(run, session_id).parent
        packet = self._packet(workflow, run, view, session_dir, payload.get("criteria") or [])
        seeds = list(payload.get("seeds") or [])
        if not seeds:
            import random
            seeds = random.sample(range(1, 2**31 - 1), SEED_COUNT)
        if len(seeds) != SEED_COUNT or len(set(seeds)) != SEED_COUNT or any(isinstance(x, bool) or not isinstance(x, int) for x in seeds):
            raise ValueError("Choose exactly four distinct integer seeds.")
        record = {"version": PROMPT_SESSION_VERSION, "session_id": session_id,
            "universe_id": self.app.universe_id, "pipeline": pipeline, "run_id": run_id,
            "costume": costume, "view": view, "created_at": _stamp(), "status": "READY",
            "packet": packet, "seeds": seeds, "llm_calls": 0, "render_submissions": 0,
            "active_draft": None, "history": [], "error": ""}
        ledger_path = self._pilot_ledger_path()
        ledger_path.parent.mkdir(parents=True, exist_ok=True)
        existing_session_id = ""
        with file_lock(ledger_path.with_suffix(".lock")):
            try:
                ledger = read_library_json(ledger_path, Path(self.app.config.base_library_path))
            except FileNotFoundError:
                ledger = {"version": 1, "universe_id": self.app.universe_id,
                          "llm_calls": 0, "render_submissions": 0, "cases": {}}
            if record["session_id"] not in ledger.setdefault("cases", {}):
                existing_session_id = next((existing_id for existing_id, case in ledger["cases"].items()
                    if (case.get("pipeline"), case.get("run_id"), case.get("costume"), case.get("view"))
                    == (pipeline, run_id, costume, view)), "")
                if existing_session_id:
                    pass
                elif len(ledger["cases"]) >= 3:
                    raise ValueError("The three-case pilot already has three prepared cases.")
                else:
                    ledger["cases"][record["session_id"]] = {"pipeline": pipeline, "run_id": run_id,
                        "costume": costume, "view": view, "llm_calls": 0, "render_submissions": 0}
                    write_library_json(ledger_path, ledger, Path(self.app.config.base_library_path))
                    self._write(run, record)
        if existing_session_id:
            return self.detail(pipeline, run_id, costume, existing_session_id)
        return self.detail(pipeline, run_id, costume, session_id)

    def detail(self, pipeline, run_id, costume, session_id):
        _, run = self._workflow(pipeline, run_id, costume)
        record = self._read(run, session_id)
        self._resume(run, record)
        public = deepcopy(record)
        packet = public["packet"]
        packet.pop("baseline_input", None)
        refs = packet.get("analysis_references", [])
        packet["analysis_references"] = [{k: ref.get(k) for k in ("id", "role", "label", "audience", "sha256", "render_index")}
                                         for ref in refs]
        public["packet"] = packet
        public["model_options"], public["default_model"], public["higher_tier_available"] = self._model_options(record)
        public["pilot_totals"] = self._pilot_stats()
        for draft in public.get("history", []):
            draft.pop("request_prompt", None)
            for attempt in draft.get("attempts", []):
                attempt.pop("image_path", None)
                attempt.pop("input", None)
        for packet_revision in public.get("packet_revisions", []):
            packet_revision.pop("baseline_input", None)
            packet_revision["analysis_references"] = [{k: ref.get(k) for k in
                ("id", "role", "label", "audience", "sha256", "render_index")}
                for ref in packet_revision.get("analysis_references", [])]
        active = public.get("active_draft") or {}
        if active.get("request_prompt"):
            active.pop("request_prompt", None)
        for item in active.get("feedback_images", []):
            item.pop("path", None)
        return public

    def _model_options(self, record):
        from zet.services.ai_model_catalog_service import AIModelCatalogService
        from zet.services.llm_role_service import resolve_role_model
        required = ["vision"] if record["packet"].get("analysis_references") else ["text"]
        models = AIModelCatalogService(self.app.config.base_ai_queue_path, config=self.app.config).models(required=required)
        allow_higher = bool(record.get("higher_tier_requested") or sum(
            1 for item in record.get("draft_history", []) if item.get("status") == "FAILED") >= 2)
        default_model = resolve_role_model(self.app.config, "prompt_generator")
        models = [item for item in models if item.get("provider") != "codex"
                  or allow_higher or item["id"] in {default_model, default_model.removeprefix("codex:")}]
        options = [{"id": item["id"], "provider": item.get("provider", ""),
                    "label": item.get("name") or item["id"]} for item in models]
        return options, default_model, allow_higher

    def _resume(self, run, record):
        for task in (record.get("pending") or []):
            self._submit(self._draft_job if task["kind"] == "draft" else self._render_job,
                record["pipeline"], record["run_id"], record["costume"], record["session_id"],
                task["id"], self._owner(record))

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
        missing = [line for line in required if line not in text]
        if missing:
            raise ValueError("Prompt omits compiler constraints: " + " ".join(missing[:3]))
        return text

    def draft(self, pipeline, run_id, costume, session_id, payload):
        _, run = self._workflow(pipeline, run_id, costume)
        from zet.services.llm_role_service import resolve_role_model
        model = str(payload.get("model") or resolve_role_model(self.app.config, "prompt_generator"))
        from zet.services.ai_model_catalog_service import AIModelCatalogService
        current = self._read(run, session_id)
        if not current.get("live_authorized_at"):
            raise ValueError("Explicitly authorize live pilot submissions before drafting.")
        model_info = AIModelCatalogService(self.app.config.base_ai_queue_path, config=self.app.config).validate(
            model, required=["vision"] if current["packet"].get("analysis_references") else ["text"])
        default_model = self._model_options(current)[1]
        if (model_info.get("provider") == "codex"
                and model not in {default_model, default_model.removeprefix("codex:")}
                and not current.get("higher_tier_requested")):
            raise ValueError("Request higher-tier escalation explicitly before selecting another Codex model.")
        if model.startswith("codex:"):
            usage = self.app.codex_usage_service.refresh()
            if not usage.get("known") or not usage.get("allowed"):
                raise ValueError("Codex usage is unknown or below the configured reserve; the session is preserved.")
        with file_lock(self._session_path(run, session_id).with_suffix(".lock")):
            record = self._read(run, session_id)
            if not record.get("live_authorized_at"):
                raise ValueError("Explicitly authorize live pilot submissions before drafting.")
            if record["llm_calls"] >= MAX_CASE_LLM_CALLS:
                raise ValueError("This case has used its 12 LLM calls.")
            if any(item.get("kind") == "draft" for item in record.get("pending", [])):
                raise ValueError("A prompt draft is already in progress.")
            direction = str(payload.get("direction") or "").strip()
            if not direction:
                raise ValueError("Add human direction before drafting a render prompt.")
            feedback_round = next((item for item in record.get("history", [])
                                   if item.get("id") == payload.get("feedback_round_id")), None)
            feedback_by_seed = {}
            for attempt in (feedback_round or {}).get("attempts", []):
                if attempt.get("status") != "READY":
                    continue
                image_path = Path(str(attempt.get("image_path") or ""))
                if not image_path.is_file() or _sha(image_path.read_bytes()) != attempt.get("sha256"):
                    raise ValueError("A frozen prior trial image is missing or changed; the draft was not submitted.")
                feedback_by_seed[attempt["seed"]] = {"attempt_id": attempt["id"], "seed": attempt["seed"],
                    "sha256": attempt["sha256"], "path": str(image_path)}
            feedback_images = list(feedback_by_seed.values())
            prior_attempts = ({"round_id": feedback_round["id"], "prompt": feedback_round.get("prompt", ""),
                "attempts": [{"attempt_id": item["attempt_id"], "seed": item["seed"], "sha256": item["sha256"],
                              "human_review": deepcopy(next((attempt.get("human_review") for attempt in feedback_round["attempts"]
                                  if attempt.get("id") == item["attempt_id"]), {}))}
                             for item in feedback_images]} if feedback_round else {})
            if (direction != record["packet"].get("direction", "")
                    or prior_attempts != record["packet"].get("prior_attempts", {})):
                self._revise_packet(record, direction=direction, prior_attempts=prior_attempts)
            task_id = uuid4().hex
            self._reserve_pilot_budget(record, "llm", 1)
            record["llm_calls"] += 1
            record["active_draft"] = {"id": task_id, "status": "QUEUED", "direction": direction,
                                      "prompt": "", "approved": False, "model": model, "error": "",
                                      "feedback_round_id": feedback_round.get("id", "") if feedback_round else "",
                                      "feedback_images": feedback_images}
            record.setdefault("pending", []).append({"id": task_id, "kind": "draft"})
            record["status"] = "DRAFTING"
            self._write(run, record)
        self._submit(self._draft_job, pipeline, run_id, costume, session_id, task_id, self._owner(record))
        return self.detail(pipeline, run_id, costume, session_id)

    def _draft_job(self, pipeline, run_id, costume, session_id, task_id):
        from zet.services.ai_workflow_service import AIPending
        _, run = self._workflow(pipeline, run_id, costume)
        record = self._read(run, session_id)
        draft = record.get("active_draft") or {}
        if (draft.get("id") != task_id or draft.get("status") not in {"QUEUED", "RUNNING"}
                or not any(item.get("id") == task_id for item in record.get("pending", []))):
            return
        try:
            from zet.services.llm_role_service import resolve_role_model
            packet = record["packet"]
            if packet.get("instruction_modules") != self._instruction_modules(pipeline, packet["operation"]):
                raise ValueError("Prompt-authoring instructions changed after packet preparation; prepare a new packet.")
            schema = {"type": "object", "properties": {"packet_id": {"type": "string"},
                "packet_hash": {"type": "string"},
                "prompt": {"type": "string"}, "reference_ids": {"type": "array", "items": {"type": "string"}},
                "proposals": {"type": "array", "items": {"type": "string"}}},
                "required": ["packet_id", "packet_hash", "prompt", "reference_ids", "proposals"], "additionalProperties": False}
            reference_map = [{k: ref.get(k) for k in ("id", "role", "label", "audience", "sha256", "render_index")}
                             for ref in packet.get("analysis_references", [])]
            feedback = draft.get("feedback_images", [])
            failures = [item for item in record.get("draft_history", []) if item.get("status") == "FAILED"][-3:]
            escalations = record.get("escalations", [])[-3:]
            feedback_map = [{"id": f"trial-{item['attempt_id']}", "role": "prior_trial_result",
                             "label": f"Prior trial output, seed {item['seed']}", "audience": "analysis",
                             "sha256": item["sha256"]} for item in feedback]
            prompt = ("Write the complete final image-render instruction using the compiler-owned baseline and facts. "
                "Do not invent facts or change reference numbering. Cite a render image with its exact {{REF:id}} token; "
                "only images also attached to the renderer may be cited. Preserve all compiler constraints verbatim. "
                "Return the exact packet ID and hash in packet_id and packet_hash. Propose durable source changes separately; do not apply them.\n"
                + "Packet:\n" + json.dumps({k: v for k, v in packet.items() if k not in {"analysis_references", "baseline_input"}}, ensure_ascii=False)
                + "\nImage reference IDs available to the generator (only cite IDs also marked with a render index):\n"
                + json.dumps(reference_map + feedback_map, ensure_ascii=False)
                + "\nPrior failure and escalation summary (diagnostic context, not new facts):\n"
                + json.dumps({"failures": failures, "escalations": escalations}, ensure_ascii=False)
                + "\nBaseline prompt:\n" + packet["baseline_prompt"] + "\nHuman direction:\n" + draft["direction"])
            images = []
            for ref in packet.get("analysis_references", []):
                image_path = Path(ref.get("path", ""))
                if not image_path.is_file() or _sha(image_path.read_bytes()) != ref.get("sha256"):
                    raise ValueError("A frozen analysis reference is missing or changed; prepare a new packet.")
                images.append(image_path)
            for item in feedback:
                image_path = Path(item["path"])
                if not image_path.is_file() or _sha(image_path.read_bytes()) != item.get("sha256"):
                    raise ValueError("A frozen prior trial image is missing or changed; prepare a new packet.")
                images.append(image_path)
            model = str(draft.get("model") or resolve_role_model(self.app.config, "prompt_generator"))
            answer, runtime = self.app.ai_proxy_service.ai_proxy_path_service.jobs.generate_json(
                model, "", prompt, schema, images, task_type="local_prompt_generator",
                role="prompt_generator", render_context={"operation": packet["operation"], "pipeline": pipeline,
                    "bindings_owned_by_zet": True},
                workflow=pipeline, owner=self._owner(record))
            answer["prompt"] = self._validate_draft(packet, answer)
            answer["approved"] = False
            outcome = {**answer, "runtime": runtime, "status": "READY"}
        except AIPending:
            raise
        except Exception as exc:
            outcome = {"status": "FAILED", "error": str(exc)}
        path = self._session_path(run, session_id)
        with file_lock(path.with_suffix(".lock")):
            current = self._read(run, session_id)
            target = current.get("active_draft") or {}
            if target.get("id") != task_id:
                return
            target.update(outcome)
            current.setdefault("draft_history", []).append({"id": task_id, "model": draft.get("model", ""),
                "status": target.get("status"), "error": target.get("error", ""),
                "runtime": deepcopy(target.get("runtime") or {}), "created_at": _stamp()})
            current["pending"] = [item for item in current.get("pending", []) if item.get("id") != task_id]
            current["status"] = "DRAFT_READY" if target["status"] == "READY" else "FAILED"
            self._write(run, current)

    def approve(self, pipeline, run_id, costume, session_id, payload):
        _, run = self._workflow(pipeline, run_id, costume)
        with file_lock(self._session_path(run, session_id).with_suffix(".lock")):
            record = self._read(run, session_id)
            if record.get("pending"):
                raise ValueError("Wait for the current prompt-generator task to finish before starting another.")
            draft = record.get("active_draft") or {}
            if draft.get("status") != "READY" or payload.get("packet_hash") != record["packet"]["packet_hash"]:
                raise ValueError("Refresh and validate the current draft before approval.")
            draft["prompt"] = self._validate_draft(record["packet"], {**draft,
                "packet_id": record["packet"]["packet_id"], "packet_hash": record["packet"]["packet_hash"]})
            draft.update(approved=True, approved_at=_stamp(), approved_hash=_sha(draft["prompt"].encode()),
                         approved_packet_hash=record["packet"]["packet_hash"])
            self._write(run, record)
        return self.detail(pipeline, run_id, costume, session_id)

    def authorize(self, pipeline, run_id, costume, session_id, payload):
        _, run = self._workflow(pipeline, run_id, costume)
        if payload.get("confirm") is not True:
            raise ValueError("Confirm the stated pilot allowance to authorize live submissions.")
        with file_lock(self._session_path(run, session_id).with_suffix(".lock")):
            record = self._read(run, session_id)
            record["live_authorized_at"] = _stamp()
            record["authorized_allowance"] = {"llm_calls_per_case": MAX_CASE_LLM_CALLS,
                "render_submissions_per_case": MAX_CASE_RENDER_SUBMISSIONS,
                "pilot_llm_calls": 36, "pilot_render_submissions": 48}
            self._write(run, record)
        return self.detail(pipeline, run_id, costume, session_id)

    def request_escalation(self, pipeline, run_id, costume, session_id, payload):
        _, run = self._workflow(pipeline, run_id, costume)
        reason = str(payload.get("reason") or "").strip()
        if not reason:
            raise ValueError("Describe the repeated constraint failure, conflicting evidence, or requested escalation.")
        with file_lock(self._session_path(run, session_id).with_suffix(".lock")):
            record = self._read(run, session_id)
            record["higher_tier_requested"] = True
            record.setdefault("escalations", []).append({"reason": reason, "created_at": _stamp()})
            self._write(run, record)
        return self.detail(pipeline, run_id, costume, session_id)

    def update_criteria(self, pipeline, run_id, costume, session_id, payload):
        _, run = self._workflow(pipeline, run_id, costume)
        criteria = [str(item).strip() for item in payload.get("criteria", []) if str(item).strip()]
        if not criteria:
            raise ValueError("Add at least one concrete visual acceptance criterion.")
        with file_lock(self._session_path(run, session_id).with_suffix(".lock")):
            record = self._read(run, session_id)
            packet = record["packet"]
            if criteria == packet.get("criteria"):
                return self.detail(pipeline, run_id, costume, session_id)
            if not record.get("original_criteria"):
                record["original_criteria"] = list(criteria)
            elif packet.get("criteria"):
                record.setdefault("criteria_change_history", []).append({"from": list(packet["criteria"]),
                    "to": list(criteria), "changed_at": _stamp()})
            self._revise_packet(record, criteria=criteria)
            record["status"] = "READY"
            self._write(run, record)
        return self.detail(pipeline, run_id, costume, session_id)

    def edit(self, pipeline, run_id, costume, session_id, payload):
        _, run = self._workflow(pipeline, run_id, costume)
        with file_lock(self._session_path(run, session_id).with_suffix(".lock")):
            record = self._read(run, session_id)
            draft = record.get("active_draft") or {}
            prompt = str(payload.get("prompt") or "")
            draft.update(prompt=prompt, reference_ids=sorted(set(_CITATION.findall(prompt))),
                         approved=False, approved_at="", approved_hash="")
            draft["prompt"] = self._validate_draft(record["packet"], {**draft,
                "packet_id": record["packet"]["packet_id"], "packet_hash": record["packet"]["packet_hash"]})
            record.setdefault("manual_edits", []).append({"packet_hash": record["packet"]["packet_hash"],
                "elapsed_seconds": max(0, min(86400, int(payload.get("elapsed_seconds") or 0))),
                "edit_volume_characters": max(0, min(200000, int(payload.get("edit_volume_characters") or 0))),
                "created_at": _stamp()})
            self._write(run, record)
        return self.detail(pipeline, run_id, costume, session_id)

    def edit_baseline(self, pipeline, run_id, costume, session_id, payload):
        _, run = self._workflow(pipeline, run_id, costume)
        with file_lock(self._session_path(run, session_id).with_suffix(".lock")):
            record = self._read(run, session_id)
            if record.get("pending") or any(item.get("kind") == "baseline" for item in record.get("history", [])):
                raise ValueError("The manual baseline prompt is frozen after baseline submission.")
            prompt = str(payload.get("prompt") or "").strip()
            validated = self._validate_draft(record["packet"], {"packet_id": record["packet"]["packet_id"],
                "packet_hash": record["packet"]["packet_hash"],
                "prompt": prompt, "reference_ids": sorted(set(_CITATION.findall(prompt)))})
            record["manual_baseline_prompt"] = validated
            record["manual_baseline_prompt_packet_hash"] = record["packet"]["packet_hash"]
            record["manual_baseline_prompt_hash"] = _sha(validated.encode())
            record.setdefault("manual_edits", []).append({"kind": "baseline",
                "packet_hash": record["packet"]["packet_hash"],
                "elapsed_seconds": max(0, min(86400, int(payload.get("elapsed_seconds") or 0))),
                "edit_volume_characters": max(0, min(200000, int(payload.get("edit_volume_characters") or 0))),
                "created_at": _stamp()})
            self._write(run, record)
        return self.detail(pipeline, run_id, costume, session_id)

    def render(self, pipeline, run_id, costume, session_id, payload):
        _, run = self._workflow(pipeline, run_id, costume)
        kind = str(payload.get("kind") or "trial")
        with file_lock(self._session_path(run, session_id).with_suffix(".lock")):
            record = self._read(run, session_id)
            if not record.get("live_authorized_at"):
                raise ValueError("Explicitly authorize live pilot submissions before rendering.")
            if not record["packet"].get("criteria"):
                raise ValueError("Set visual acceptance criteria before rendering the baseline.")
            if kind != "baseline" and not (record.get("active_draft") or {}).get("approved"):
                raise ValueError("Approve the current prompt before rendering a trial.")
            if kind != "baseline":
                approved = record["active_draft"]
                if (approved.get("approved_packet_hash") != record["packet"]["packet_hash"]
                        or approved.get("approved_hash") != _sha(str(approved.get("prompt") or "").encode())):
                    raise ValueError("The approved packet or prompt text changed; review and approve it again.")
            if record["render_submissions"] + SEED_COUNT > MAX_CASE_RENDER_SUBMISSIONS:
                raise ValueError("This case has used its 16 render submissions.")
            if kind == "baseline" and any(item.get("kind") == "baseline" for item in record["history"]):
                raise ValueError("The four-seed baseline has already been submitted.")
            if kind == "baseline" and (record.get("manual_baseline_prompt_packet_hash") != record["packet"]["packet_hash"]
                    or record.get("manual_baseline_prompt_hash") != _sha(str(record.get("manual_baseline_prompt") or "").encode())):
                raise ValueError("Edit and save the manual baseline prompt for this packet before rendering it.")
            round_number = 0 if kind == "baseline" else 1 + sum(1 for item in record["history"] if item.get("kind") == "trial")
            if kind != "baseline" and round_number > TRIAL_ROUNDS:
                raise ValueError("This case has completed its three trial rounds.")
            render_refs = record["packet"]["baseline_input"]["references"]
            for ref in render_refs:
                if not Path(ref["path"]).is_file() or _sha(Path(ref["path"]).read_bytes()) != ref.get("sha256"):
                    raise ValueError("A frozen render reference is missing or changed; prepare a new packet.")
            task_id = uuid4().hex
            self._reserve_pilot_budget(record, "render", SEED_COUNT)
            prompt = record["manual_baseline_prompt"] if kind == "baseline" else record["active_draft"]["prompt"]
            attempts = []
            for seed in record["seeds"]:
                aid = uuid4().hex
                request_prompt = _CITATION.sub(lambda match: self._render_citation(match.group(1), render_refs), prompt)
                saved = {**deepcopy(record["packet"]["baseline_input"]), "prompt": request_prompt}
                attempts.append({"id": aid, "seed": seed, "status": "QUEUED", "request_id": uuid4().hex,
                                 "input": saved, "error": ""})
            record["render_submissions"] += SEED_COUNT
            round_record = {"id": task_id, "kind": kind, "round": round_number,
                            "prompt": prompt, "model": (record.get("active_draft") or {}).get("model", ""),
                            "packet_hash": record["packet"]["packet_hash"],
                            "packet_id": record["packet"]["packet_id"],
                            "packet_revision": record["packet"].get("revision", 1),
                            "criteria": deepcopy(record["packet"].get("criteria", [])),
                            "criterion_sets": [{"version": "original", "criteria": deepcopy(record.get("original_criteria") or record["packet"].get("criteria", []))},
                                               {"version": "current", "criteria": deepcopy(record["packet"].get("criteria", []))}],
                            "attempts": attempts, "created_at": _stamp()}
            record["history"].append(round_record)
            record.setdefault("pending", []).append({"id": task_id, "kind": "render"})
            record["status"] = "RENDERING"
            self._write(run, record)
        self._submit(self._render_job, pipeline, run_id, costume, session_id, task_id, self._owner(record))
        return self.detail(pipeline, run_id, costume, session_id)

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
        generation = image_services(self.app)[0]
        for attempt in round_record["attempts"]:
            if attempt["status"] not in {"QUEUED", "SUBMITTED"}:
                continue
            current = self._read(run, session_id)
            if not any(item.get("id") == task_id for item in current.get("pending", [])):
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
                        "disable_prompt_globals": True, "append_reference_labels": False},
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
                if outcome["status"] == "READY":
                    write_bytes_atomic(Path(outcome["image_path"]), contents)
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
                if not target_round:
                    return
                target = next(item for item in target_round["attempts"] if item["id"] == attempt["id"])
                target.update(outcome)
                if all(item["status"] in {"READY", "FAILED"} for item in target_round["attempts"]):
                    current["pending"] = [item for item in current.get("pending", []) if item.get("id") != task_id]
                    current["status"] = "ROUND_READY"
                    target_round["completed_at"] = _stamp()
                    target_round["completed_count"] = sum(1 for item in target_round["attempts"] if item["status"] == "READY")
                self._write(run, current)

        fresh = self._read(run, session_id)
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
            from zet.services.render_slot_service import slot_maps
            from zet.services.local_image_pipeline_policy import mutate_local_run_state
            from zet.services.local_character_progression_service import select
            slots = slot_maps(run)
            if None not in slots[record["view"]]:
                raise ValueError("Choose and clear an empty slot before adopting a pilot render.")
            cid = uuid4().hex
            source = Path(attempt["image_path"])
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
                                     "criteria": record["packet"].get("criteria", []),
                                     "seed": attempt["seed"], "model": round_record.get("model", ""),
                                     "references": [{k: ref.get(k) for k in ("id", "role", "label", "sha256", "render_index", "candidate_id", "view", "tag")}
                                                    for ref in attempt["input"].get("references", [])]},
                "human_review": {"decision": "undecided"}}
            slot = slots[record["view"]].index(None)
            slots[record["view"]][slot] = cid
            def update(state):
                state.setdefault("added_candidates", {})[cid] = candidate
                state["slots_by_view"] = slots
                state["slot_version"] = int(state.get("slot_version", 0)) + 1
            mutate_local_run_state(Path(run["root"]), update)
            record["adopted_candidate_id"] = cid
            self._write(run, record)
        return {"candidate_id": cid, "view": record["view"], "selected": False}

    def retry(self, pipeline, run_id, costume, session_id, payload):
        _, run = self._workflow(pipeline, run_id, costume)
        path = self._session_path(run, session_id)
        with file_lock(path.with_suffix(".lock")):
            record = self._read(run, session_id)
            if not record.get("live_authorized_at"):
                raise ValueError("Explicitly authorize live pilot submissions before retrying.")
            if record.get("pending"):
                raise ValueError("Wait for the current prompt-generator task to finish before retrying.")
            if record["render_submissions"] >= MAX_CASE_RENDER_SUBMISSIONS:
                raise ValueError("This case has used its 16 render submissions.")
            round_record = next((item for item in record["history"] if item["id"] == payload.get("round_id")), None)
            prior = next((item for item in (round_record or {}).get("attempts", [])
                          if item["id"] == payload.get("attempt_id") and item.get("status") == "FAILED"), None)
            if not prior:
                raise ValueError("Retry a failed render attempt from this session.")
            self._reserve_pilot_budget(record, "render", 1)
            attempt = {"id": uuid4().hex, "seed": prior["seed"], "status": "QUEUED",
                       "request_id": uuid4().hex, "retry_of": prior["id"],
                       "input": deepcopy(prior["input"]), "error": ""}
            round_record["attempts"].append(attempt)
            record["render_submissions"] += 1
            task_id = uuid4().hex
            attempt["dispatch_task_id"] = task_id
            record.setdefault("pending", []).append({"id": task_id, "kind": "render"})
            record["status"] = "RENDERING"
            self._write(run, record)
        self._submit(self._render_job, pipeline, run_id, costume, session_id, task_id, self._owner(record))
        return self.detail(pipeline, run_id, costume, session_id)

    def set_edit_base(self, pipeline, run_id, costume, session_id, payload):
        workflow, run = self._workflow(pipeline, run_id, costume)
        with file_lock(self._session_path(run, session_id).with_suffix(".lock")):
            record = self._read(run, session_id)
            if record.get("pending"):
                raise ValueError("Wait for current work to finish before changing the packet reference strategy.")
            round_record = next((item for item in record["history"] if item["id"] == payload.get("round_id")), None)
            attempt = next((item for item in (round_record or {}).get("attempts", [])
                            if item["id"] == payload.get("attempt_id") and item.get("status") == "READY"), None)
            if not attempt:
                raise ValueError("Choose an available completed render as the new edit base.")
            source = Path(attempt["image_path"])
            if not source.is_file() or _sha(source.read_bytes()) != attempt.get("sha256"):
                raise ValueError("The selected edit-base image is missing or changed.")
            packet = record["packet"]
            history = record.setdefault("packet_revisions", [])
            history.append(deepcopy(packet))
            revised = deepcopy(packet)
            target_dir = self._session_path(run, session_id).parent / "packet-revisions" / str(len(history) + 1) / "references"
            target_dir.mkdir(parents=True, exist_ok=True)
            target = target_dir / f"edit-base{source.suffix.lower()}"
            shutil.copy2(source, target)
            refs = revised["baseline_input"]["references"]
            edit_ref = {"id": f"edit-base-{attempt['id']}", "role": "edit_base", "label": f"Selected trial image, seed {attempt['seed']}",
                        "path": str(target), "sha256": _sha(target.read_bytes()), "candidate_id": "",
                        "view": record["view"], "audience": "both"}
            refs = [edit_ref, *refs[1:]] if refs else [edit_ref]
            for index, ref in enumerate(refs, 1):
                ref["render_index"] = index
            revised["baseline_input"]["references"] = refs
            revised["analysis_references"] = [*revised.get("analysis_references", []), deepcopy(edit_ref)]
            revised["baseline_input"]["preset"] = getattr(workflow.adapter, "edit_preset", revised["baseline_input"].get("preset", ""))
            from zet.services.local_render_backend_service import LocalRenderBackendService
            preset_service = LocalRenderBackendService(self.app.config.state_file(self.project_root, "Local_Render_Presets.json"), config=self.app.config)
            revised["baseline_input"]["render_settings"] = preset_service.preset(revised["baseline_input"]["preset"])
            revised["render_preset"] = revised["baseline_input"]["preset"]
            revised["render_settings"] = deepcopy(revised["baseline_input"]["render_settings"])
            revised["operation"] = "edit"
            revised["references"] = [{k: ref.get(k) for k in ("id", "role", "label", "audience", "sha256", "render_index")}
                                      for ref in refs]
            revised["revision"] = len(history) + 1
            revised["packet_id"] = uuid4().hex
            revised["edit_base_attempt_id"] = attempt["id"]
            revised["packet_hash"] = _sha(json.dumps({k: v for k, v in revised.items()
                if k not in {"packet_id", "packet_hash", "baseline_input", "analysis_references"}},
                sort_keys=True, ensure_ascii=False).encode())
            record["packet"] = revised
            record.setdefault("strategy_changes", []).append({"type": "edit_base", "attempt_id": attempt["id"],
                "from_packet": packet["packet_hash"], "to_packet": revised["packet_hash"], "created_at": _stamp()})
            record["active_draft"] = None
            record["status"] = "READY"
            self._write(run, record)
        return self.detail(pipeline, run_id, costume, session_id)

    def review_image(self, pipeline, run_id, costume, session_id, payload):
        _, run = self._workflow(pipeline, run_id, costume)
        with file_lock(self._session_path(run, session_id).with_suffix(".lock")):
            record = self._read(run, session_id)
            round_record = next((item for item in record["history"] if item["id"] == payload.get("round_id")), None)
            attempt = next((item for item in (round_record or {}).get("attempts", [])
                            if item["id"] == payload.get("attempt_id")), None)
            if not attempt or attempt.get("status") != "READY":
                raise ValueError("Choose a completed pilot render to review.")
            decision = str(payload.get("decision") or "").lower()
            if decision not in {"accept", "reject"}:
                raise ValueError("Choose accept or reject for this image.")
            attempt["human_review"] = {"decision": decision,
                "criteria": deepcopy(payload.get("criteria") or []), "notes": str(payload.get("notes") or ""),
                "review_seconds": max(0, min(86400, int(payload.get("review_seconds") or 0))),
                "reviewed_at": _stamp()}
            self._write(run, record)
        return self.detail(pipeline, run_id, costume, session_id)

    def save_decision(self, pipeline, run_id, costume, session_id, payload):
        _, run = self._workflow(pipeline, run_id, costume)
        destination = str(payload.get("destination") or "")
        if destination not in {"costume_source", "Character.md", "pipeline_template", "shared_template"}:
            raise ValueError("Choose a reusable-decision destination.")
        text = str(payload.get("text") or "").strip()
        if not text:
            raise ValueError("Describe the proposed reusable change.")
        with file_lock(self._session_path(run, session_id).with_suffix(".lock")):
            record = self._read(run, session_id)
            record.setdefault("decisions", []).append({"id": uuid4().hex, "destination": destination,
                "text": text, "packet_hash": record["packet"]["packet_hash"],
                "status": "READY_FOR_REVIEW", "created_at": _stamp()})
            self._write(run, record)
        return self.detail(pipeline, run_id, costume, session_id)

    def cancel(self, pipeline, run_id, costume, session_id):
        _, run = self._workflow(pipeline, run_id, costume)
        path = self._session_path(run, session_id)
        with file_lock(path.with_suffix(".lock")):
            record = self._read(run, session_id)
            record["status"] = "CANCELLED"
            record["pending"] = []
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
