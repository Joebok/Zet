"""Human-reviewed costume source improvements with persistent visual targets."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import random

from zet.services.costume_adjustment_criteria_service import CostumeAdjustmentCriteriaService
from zet.services.costume_mode_conditioning_service import MODES, scoped_replacement
from zet.services.costume_render_mode_service import CostumeRenderModeService, render_settings
from zet.services.local_post_render_prompt_service import LocalPostRenderPromptService, _hash
from zet.services.llm_role_service import resolve_role_model
from zet.services.template_source_service import active_revision
from zet.services.view_conditioning_service import VIEW_ORDER
from zet.services.workflow_storage import file_lock

MIRRORS = {"FRONT_LEFT_3_4": "FRONT_RIGHT_3_4", "LEFT_PROFILE": "RIGHT_PROFILE", "BACK_LEFT_3_4": "BACK_RIGHT_3_4",
           "FRONT_RIGHT_3_4": "FRONT_LEFT_3_4", "RIGHT_PROFILE": "LEFT_PROFILE", "BACK_RIGHT_3_4": "BACK_LEFT_3_4"}


class LocalCostumePostRenderService(LocalPostRenderPromptService):
    session_kind = "costume"
    source_label = "Costume template"
    workflow_service = "post_render_costume"
    trial_count = 4

    def _context(self, pipeline, run_id, costume=""):
        if pipeline != "costume-dressing":
            raise ValueError("Costume adjustments require Costume Dressing.")
        return super()._context(pipeline, run_id, costume)

    @staticmethod
    def _character_source(sources):
        # Compatibility hook name belongs to the shared private-trial lifecycle.
        matches = [source for source in sources if Path(source["source_path"]).name.startswith("Costume_")
                   and source["source_id"].startswith("library/")]
        if len(matches) != 1:
            raise ValueError("Exactly one costume-owned source is required.")
        return matches[0]

    @staticmethod
    def _contract(workflow, run, view):
        settings = render_settings(run, view)
        references = CostumeRenderModeService(workflow).references(run, view, settings)
        return {"settings": settings, "references": [{"role": ref["role"], "view": ref.get("view"),
            "candidate_id": ref.get("candidate_id"), "sha256": hashlib.sha256(Path(ref["path"]).read_bytes()).hexdigest()}
            for ref in references]}

    def _initialize(self, record, workflow, run):
        from zet.services.local_render_backend_service import LocalRenderBackendService
        record.update(version=2, revision=0, seeds=[random.SystemRandom().randrange(0, 2**63 - 1) for _ in range(4)],
                      render_profile=LocalRenderBackendService(self.app.config.state_file(self.project_root, "Local_Render_Presets.json"),
                          config=self.app.config).preset(workflow.adapter.definition["preset"]),
                      render_contract=self._contract(workflow, run, record["view"]),
                      criteria_snapshot=CostumeAdjustmentCriteriaService(workflow).detail(run, record["view"]))

    def _freeze_trial_input(self, record, saved):
        return {**saved, "render_profile": record["render_profile"]}

    def _write(self, run, record):
        record["revision"] = int(record.get("revision", 0)) + 1
        super()._write(run, record)

    def _validate_round(self, record, workflow, run, operation, payload=None):
        if self._contract(workflow, run, record["view"]) != record["render_contract"]:
            raise ValueError("Rendering mode or reference inputs changed. Cancel this session and open a new review.")
        if active_revision(Path(run["root"])).get("revision_id", "") not in {record["base_revision_id"], record.get("final_revision_id")}:
            raise ValueError("The active batch revision changed. Start a new review.")
        source = Path(self._character_source(record["sources"])["source_path"])
        if operation != "keep" and _hash(source.read_bytes()) != record["master_sha256"]:
            raise ValueError("The costume master changed. Start a new review.")
        criteria = CostumeAdjustmentCriteriaService(workflow).detail(run, record["view"])
        if operation == "propose":
            if not any(item["status"] == "in_progress" for item in criteria["items"]):
                raise ValueError("Add or reopen a visual acceptance criterion before analysis.")
            record["criteria_snapshot"] = criteria
        elif operation == "trial":
            if criteria["revision"] != record["criteria_snapshot"]["revision"]:
                raise ValueError("Acceptance criteria changed after analysis; analyze again before approving trials.")
            if payload and payload.get("selected_ids", record["analysis"]["selected_ids"]) != record["analysis"]["selected_ids"]:
                raise ValueError("Save suggestion choices before approving the diff.")
            chosen = [f for f in record["analysis"]["findings"] if f["id"] in record["analysis"].get("selected_ids", [])]
            digest = _hash(self._apply_findings(record, chosen).encode("utf-8"))
            if not payload or payload.get("diff_sha256") != digest or payload.get("expected_revision") != record["revision"]:
                raise ValueError("The reviewed diff changed; refresh and accept the current diff.")

    def _decorate(self, public, record, workflow, run):
        public["criteria"] = CostumeAdjustmentCriteriaService(workflow).detail(run, record["view"])
        public["render_settings"] = record["render_contract"]["settings"]
        public["all_views"] = list(VIEW_ORDER)
        public["render_modes"] = list(MODES)
        public["trial_count"] = 4
        public["source_label"] = Path(self._character_source(record["sources"])["source_path"]).name
        if record["status"] == "TRIAL_READY" and all(a["status"] == "READY" for a in record["trial"]["attempts"]):
            assessment = record["trial"].get("assessment") or {}
            if not assessment:
                self._submit(self._evaluation_job, [record["pipeline"], record["run_id"], record["costume"], record["session_id"], record["trial"]["id"]],
                             "costume_assess_" + record["trial"]["id"], self._owner(record))
                public["trial"]["assessment"] = {"status": "QUEUED"}
        return public

    def _suggestions(self, record, workflow, run, evidence):
        fields = {key: {"type": "string"} for key in ("before", "after", "rationale")}
        fields.update({key: {"type": "array", "items": {"type": "string"}} for key in ("views", "modes", "criteria_ids")})
        fields["asymmetric"] = {"type": "boolean"}
        schema = {"type": "object", "properties": {"summary": {"type": "string"}, "findings": {"type": "array", "items": {
            "type": "object", "properties": fields, "required": list(fields), "additionalProperties": False}}},
            "required": ["summary", "findings"], "additionalProperties": False}
        unfinished = [item for item in record["criteria_snapshot"]["items"] if item["status"] == "in_progress"]
        prompt = ("Propose small independent SINGLE-LINE edits ONLY to the supplied costume Markdown. Each before is one exact complete unique prose line "
            "inside a marked COSTUME_ or EQUIPMENT_ body section; after is one replacement prose line. Do not edit Character.md, headings, metadata, "
            "section markers, placeholders or resource declarations. Preserve intended design, anatomy, references and asymmetry. "
            "Focus ONLY on the target view and unfinished acceptance criteria; cite their stable IDs in criteria_ids. "
            "Use submitted prompts and images as evidence, distinguish recurring instruction failures from isolated stochastic errors or wrong references. "
            "Consider cross-view impacts and existing selections. Recommend the target plus its mirror unless intentionally asymmetric; "
            "other selected views should usually be excluded. Set asymmetric=true when mirroring would change intentional asymmetry. "
            "Views use the eight canonical view names. modes uses doll-dressing-ref, doll-dressing-no-ref, rotate. Default modes to all three: "
            "restrict only if the same source instruction would otherwise enter multiple render modes and is specific to the current mode. "
            "Reference binding is compiler-owned, so it is not itself a reason to mode-tag prose. "
            "Existing [view] tags compose with inline <!-- ZET:RENDER_MODES mode,mode -->. The operator controls final scopes. "
            "Empty findings is valid. Never mark a criterion accomplished.\n"
            + "Target: " + record["view"] + "\nRender contract: " + json.dumps(record["render_contract"])
            + "\nUnfinished criteria: " + json.dumps(unfinished)
            + "\nHuman direction: " + record["analysis"]["direction"]
            + "\nObservations: " + json.dumps(record["analysis"]["observations"])
            + "\nCostume Markdown:\n" + record["current_text"]
            + "\nOther views/selections (read only): " + json.dumps(run.get("selected_views") or {})
            + "\nRead-only character context: " + json.dumps([{k: s[k] for k in ("source_id", "text")} for s in record["sources"] if s["source_id"].endswith("/Character.md")])
            + "\nEvidence prompts: " + json.dumps([{k: item[k] for k in ("view", "candidate_id", "prompt")} for item in evidence]))
        return self.app.ai_proxy_service.ai_proxy_path_service.jobs.generate_json(
            resolve_role_model(self.app.config, "post_render_costume_template"), "", prompt, schema,
            [Path(item["path"]) for item in evidence], task_type="post_render_costume_template", role="post_render_costume_template",
            render_context={"operation": "mixed", "bindings_owned_by_zet": True}, workflow="costume-dressing", owner=self._owner(record))

    def _prepare_finding(self, record, finding, run):
        criteria = {item["id"] for item in record["criteria_snapshot"]["items"] if item["status"] == "in_progress"}
        if not finding.get("criteria_ids") or set(finding["criteria_ids"]) - criteria:
            raise ValueError("A costume suggestion must target unfinished criteria from this analysis.")
        modes = finding.get("modes")
        if not isinstance(modes, list) or not modes or set(modes) - set(MODES):
            raise ValueError("A suggestion names invalid rendering modes.")
        views = list(dict.fromkeys(finding["views"]))
        target = record["view"]
        if target not in views:
            views.insert(0, target)
        mirror = MIRRORS.get(target)
        if not finding.get("asymmetric") and mirror and mirror not in views:
            views.append(mirror)
        selected_views = [v for v in views if v == target or not (run.get("selected_views") or {}).get(v)]
        if finding.get("asymmetric") and mirror in selected_views and mirror != target:
            selected_views.remove(mirror)
        result = {**finding, "views": views, "selected_views": selected_views, "selected_modes": list(dict.fromkeys(modes)),
                  "scope_note": "Target included; selected other views default unchecked. Mirror recommended unless costume asymmetry prevents it."}
        scoped_replacement(record["current_text"], result["before"], result["after"], selected_views, modes)
        return result

    def _apply_findings(self, record, findings):
        original = record["current_text"]
        if len({f["before"] for f in findings}) != len(findings):
            raise ValueError("Selected corrections overlap; choose one per source line.")
        result = original
        for finding in findings:
            result = scoped_replacement(result, finding["before"], finding["after"], finding["selected_views"], finding["selected_modes"])
        self.revisions._validate_text(original, result)
        return result

    def decisions(self, pipeline, run_id, costume, session_id, payload):
        _, run = self._context(pipeline, run_id, costume)
        path = self._path(run, session_id)
        with file_lock(path.with_suffix(".lock")):
            record = self._read(run, session_id)
            if record["status"] != "REVIEW_READY" or payload.get("expected_revision") != record["revision"]:
                raise ValueError("Suggestions changed; refresh before choosing corrections.")
            choices = payload.get("choices")
            if not isinstance(choices, list) or len({c.get("id") for c in choices}) != len(choices):
                raise ValueError("Supply unique current suggestion choices.")
            by_id = {f["id"]: f for f in record["analysis"]["findings"]}
            if any(c.get("id") not in by_id for c in choices):
                raise ValueError("Choose suggestions from this analysis.")
            for choice in choices:
                finding = by_id[choice["id"]]
                finding["selected_views"] = choice.get("views", [])
                finding["selected_modes"] = choice.get("modes", [])
            record["analysis"]["selected_ids"] = [c["id"] for c in choices]
            self._apply_findings(record, [by_id[c["id"]] for c in choices])
            self._write(run, record)
        return self.detail(pipeline, run_id, costume, session_id)

    def _evaluation_job(self, pipeline, run_id, costume, session_id, trial_id):
        workflow, run = self._context(pipeline, run_id, costume)
        path = self._path(run, session_id)
        with file_lock(path.with_suffix(".lock")):
            record = self._read(run, session_id)
            if record["status"] != "TRIAL_READY" or record["trial"]["id"] != trial_id or (record["trial"].get("assessment") or {}).get("status") in {"COMPLETE", "FAILED"}:
                return
            record["trial"]["assessment"] = {"status": "RUNNING"}
            self._write(run, record)
        try:
            criteria = [c for c in record["criteria_snapshot"]["items"] if c["status"] == "in_progress"]
            schema = {"type": "object", "properties": {"summary": {"type": "string"}, "items": {"type": "array", "items": {
                "type": "object", "properties": {key: {"type": "string"} for key in ("criterion_id", "assessment", "evidence")},
                "required": ["criterion_id", "assessment", "evidence"], "additionalProperties": False}}},
                "required": ["summary", "items"], "additionalProperties": False}
            attempts = record["trial"]["attempts"]
            for attempt in attempts:
                if attempt["status"] != "READY" or _hash(Path(attempt["image_path"]).read_bytes()) != attempt["sha256"]:
                    raise ValueError("Frozen trial image changed.")
            answer, runtime = self.app.ai_proxy_service.ai_proxy_path_service.jobs.generate_json(
                resolve_role_model(self.app.config, "post_render_costume_evaluation"), "",
                "Assess each unfinished acceptance criterion across these four target-view test images. Cite image numbers and uncertainty; "
                "do not mark criteria accomplished or propose source edits. Return one item per criterion ID.\nCriteria: " + json.dumps(criteria)
                + "\nView: " + record["view"] + "\nPrompt: " + attempts[0]["input"]["prompt"], schema,
                [Path(a["image_path"]) for a in attempts], task_type="post_render_costume_evaluation", role="post_render_costume_evaluation",
                render_context={"operation": "mixed", "bindings_owned_by_zet": True}, workflow=pipeline, owner=self._owner(record))
            if sorted(item["criterion_id"] for item in answer["items"]) != sorted(c["id"] for c in criteria):
                raise ValueError("Assessment must address exactly the unfinished criteria.")
            outcome = {"status": "COMPLETE", **answer, "runtime": runtime}
        except Exception as exc:
            outcome = {"status": "FAILED", "error": str(exc)}
        with file_lock(path.with_suffix(".lock")):
            current = self._read(run, session_id)
            if current["status"] == "TRIAL_READY" and current["trial"]["id"] == trial_id:
                current["trial"]["assessment"] = outcome
                self._write(run, current)

    def retry(self, pipeline, run_id, costume, session_id, payload):
        if not payload.get("evaluation"):
            return super().retry(pipeline, run_id, costume, session_id, payload)
        _, run = self._context(pipeline, run_id, costume)
        path = self._path(run, session_id)
        with file_lock(path.with_suffix(".lock")):
            record = self._read(run, session_id)
            if record["status"] != "TRIAL_READY" or (record["trial"].get("assessment") or {}).get("status") != "FAILED":
                raise ValueError("Only a failed assessment can be retried.")
            record["trial"].pop("assessment", None)
            from uuid import uuid4
            key = "costume_assess_retry_" + uuid4().hex
            self._write(run, record)
        self._submit(self._evaluation_job, [pipeline, run_id, costume, session_id, record["trial"]["id"]], key, self._owner(record))
        return self.detail(pipeline, run_id, costume, session_id)
