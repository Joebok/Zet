"""Human-reviewed costume source improvements with persistent visual targets."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import random
import re

from zet.services.costume_adjustment_criteria_service import CostumeAdjustmentCriteriaService
from zet.services.costume_mode_conditioning_service import MODES, condition_mode_line, scoped_replacement
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

    @staticmethod
    def _editable_lines(record):
        from zet.services.view_conditioning_service import _TAG, _SPATIAL
        text = record["current_text"]
        section, result = "", []
        for number, line in enumerate(text.splitlines(), 1):
            marker = re.match(r"\s*<!--\s*ZET:(BEGIN|END)\s+(\w+)\s*-->", line)
            if marker:
                section = marker[2] if marker[1] == "BEGIN" else ""
            if not section.startswith(("COSTUME_", "EQUIPMENT_")) or not line.strip():
                continue
            try:
                # Reuse the actual scope gate, including inherited defaults, head
                # domains, compiler declarations and placeholders. No source is written.
                scoped_replacement(text, line, "Replacement prose.", [record["view"]], MODES, source_line=number)
            except ValueError:
                continue
            clean, _, _ = condition_mode_line(line, None)
            tag = _TAG.match(clean)
            body = tag[3] if tag else re.sub(r"^\s*[-*+]\s+", "", clean)
            prose = _SPATIAL.sub("", body).strip()
            if not prose:
                continue
            result.append({"source_line_id": f"{section}:{number}:{_hash(line.encode('utf-8'))[:16]}",
                           "section": section, "source_line": number, "before": line, "prose": prose})
        return result

    def _suggestions(self, record, workflow, run, evidence, repair=None):
        catalog = self._editable_lines(record)
        fields = {key: {"type": "string"} for key in ("source_line_id", "after", "rationale")}
        if catalog:
            fields["source_line_id"]["enum"] = [line["source_line_id"] for line in catalog]
        fields.update({key: {"type": "array", "items": {"type": "string"}} for key in ("views", "modes", "criteria_ids")})
        fields["views"]["items"]["enum"] = list(VIEW_ORDER)
        fields["modes"]["items"]["enum"] = list(MODES)
        fields["asymmetric"] = {"type": "boolean"}
        schema = {"type": "object", "properties": {"summary": {"type": "string"}, "findings": {"type": "array", "items": {
            "type": "object", "properties": fields, "required": list(fields), "additionalProperties": False}}},
            "required": ["summary", "findings"], "additionalProperties": False}
        unfinished = [item for item in record["criteria_snapshot"]["items"] if item["status"] == "in_progress"]
        prompt = ("Propose small independent SINGLE-LINE edits ONLY to the supplied editable costume lines. "
            "Select source_line_id EXACTLY from the editable-line catalog; never invent an ID or copy original text as an address. "
            "Identical prose in different locations has separate IDs. Return at most one finding per ID. "
            "after is replacement PROSE ONLY: no bullet prefix, view tags, mode annotations or spatial annotations. "
            "Zet preserves original spatial annotations and generates view/mode tags from the selected scopes. "
            "For spatially annotated lines, retain anatomical-left/anatomical-right qualifications in the replacement prose; "
            "do not use unqualified left/right or remove the anatomical side. "
            "To suppress visibility, write explicit replacement prose saying what must be hidden and what to ignore in reference images; "
            "removing or changing a view tag cannot suppress a source instruction. Do not edit Character.md, headings, metadata, "
            "section markers, placeholders or resource declarations. Preserve intended design, anatomy, references and asymmetry. "
            "Focus ONLY on the target view and unfinished acceptance criteria; cite their stable IDs in criteria_ids. "
            "Use submitted prompts and images as evidence, distinguish recurring instruction failures from isolated stochastic errors or wrong references. "
            "Consider cross-view impacts and existing selections. Recommend a mirror ONLY when the correction is symmetric. "
            "A weapon or accessory attached to one anatomical side has asymmetric visibility and occlusion across mirrored views, "
            "even when a source line is marked SPATIAL fixed. Do not hide it in the mirror merely because it must be hidden in the target. "
            "For side-specific placement, visibility, occlusion or uncertain mirror effects, set asymmetric=true and recommend only the target. "
            "Other selected views should usually be excluded. Human direction takes priority. "
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
            + "\nEditable-line catalog (only these IDs may be changed): " + json.dumps(catalog)
            + "\nOther views/selections (read only): " + json.dumps(run.get("selected_views") or {})
            + "\nRead-only character context: " + json.dumps([{k: s[k] for k in ("source_id", "text")} for s in record["sources"] if s["source_id"].endswith("/Character.md")])
            + "\nEvidence prompts: " + json.dumps([{k: item[k] for k in ("view", "candidate_id", "prompt")} for item in evidence]))
        if repair:
            prompt += ("\nREPAIR ONLY the rejected findings below using the diagnostics. Previously accepted IDs must not be repeated. "
                       "Return only corrected rejected findings, or empty findings when no valid correction is possible.\n"
                       + json.dumps(repair))
        return self.app.ai_proxy_service.ai_proxy_path_service.jobs.generate_json(
            resolve_role_model(self.app.config, "post_render_costume_template"), "", prompt, schema,
            [Path(item["path"]) for item in evidence], task_type="post_render_costume_template", role="post_render_costume_template",
            render_context={"operation": "mixed", "bindings_owned_by_zet": True}, workflow="costume-dressing", owner=self._owner(record))

    def _validate_finding(self, record, finding, run, index):
        from zet.services.view_conditioning_service import _SPATIAL, _TAG, condition_section, ViewContext
        locations = {line["source_line_id"]: line for line in self._editable_lines(record)}
        location = locations.get(finding.get("source_line_id"))
        if location is None:
            raise ValueError("Unknown or stale source_line_id; select an ID from the editable-line catalog.")
        prose = finding.get("after")
        if (not isinstance(prose, str) or not prose.strip() or "\n" in prose or "\r" in prose
                or "<!--" in prose or "ZET:" in prose or "{{" in prose
                or re.match(r"^\s*(?:[-*+]\s+|\[)", prose)):
            raise ValueError("after must be one prose line without bullet prefixes, view tags or compiler annotations; Zet owns scopes.")
        if prose.strip() == location["prose"]:
            raise ValueError("Replacement prose is unchanged; changing tags alone cannot suppress visibility.")
        views = finding.get("views")
        if not isinstance(views, list) or not views or any(v not in VIEW_ORDER for v in views):
            raise ValueError("Choose nonempty canonical affected view names.")
        if not isinstance(finding.get("asymmetric"), bool):
            raise ValueError("asymmetric must explicitly describe whether mirroring is safe.")
        clean, _, _ = condition_mode_line(location["before"], None)
        tag = _TAG.match(clean)
        spatial = _SPATIAL.search(tag[3] if tag else clean)
        after = (spatial[0] + " " if spatial else "") + prose.strip()
        bound = {**finding, "before": location["before"], "after": after,
                 "source_line": location["source_line"], "section": location["section"]}
        prepared = self._prepare_finding(record, bound, run)
        for view in prepared["selected_views"]:
            condition_section("* [body:all] " + after, location["section"], {}, ViewContext(body_view=view))
        return {**prepared, "id": str(index)}

    def _analyze_suggestions(self, record, workflow, run, evidence):
        answer, runtime = self._suggestions(record, workflow, run, evidence)
        findings = []

        def collect(items):
            errors = []
            for index, finding in enumerate(items, 1):
                try:
                    prepared = self._validate_finding(record, finding, run, len(findings) + 1)
                    self._apply_findings(record, [*findings, prepared])
                    findings.append(prepared)
                except (ValueError, KeyError, TypeError) as exc:
                    errors.append({"suggestion": index, "finding": finding, "error": str(exc)})
            return errors

        rejected = collect(answer["findings"])
        if rejected:
            current = self._read(run, record["session_id"])
            if current["status"] != "ANALYZING" or current["round"] != record["round"]:
                return answer, runtime, findings
            original_rejections = rejected
            accepted_count = len(findings)
            try:
                repaired, repair_runtime = self._suggestions(record, workflow, run, evidence, repair={
                    "rejected": rejected, "accepted_source_line_ids": [f["source_line_id"] for f in findings]})
                runtime = {**runtime, "repair": repair_runtime}
                rejected = collect(repaired["findings"])
                if not rejected and len(findings) - accepted_count < len(original_rejections):
                    rejected = original_rejections
            except Exception as exc:
                rejected.append({"error": "Repair request failed: " + str(exc)})
            if rejected or not findings:
                diagnostics = "; ".join(f"Suggestion {item.get('suggestion', '?')}: {item['error']}" for item in rejected)
                diagnostics = diagnostics or "No valid replacement was returned by the repair request."
                if not findings:
                    raise ValueError("No valid costume suggestions after one repair attempt. " + diagnostics)
                answer = {**answer, "summary": answer["summary"] + "\nSome suggestions were omitted after one repair attempt: " + diagnostics}
        return answer, runtime, findings

    def _prepare_finding(self, record, finding, run):
        criteria = {item["id"] for item in record["criteria_snapshot"]["items"] if item["status"] == "in_progress"}
        if not isinstance(finding.get("criteria_ids"), list) or not finding["criteria_ids"] or set(finding["criteria_ids"]) - criteria:
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
        scope_note = ("Mirror unchecked because placement or visibility is asymmetric." if finding.get("asymmetric")
                      else "Mirror recommended for this symmetric correction.")
        result = {**finding, "views": views, "selected_views": selected_views, "selected_modes": list(dict.fromkeys(modes)),
                  "scope_note": "Target included; selected other views default unchecked. " + scope_note}
        scoped_replacement(record["current_text"], result["before"], result["after"], selected_views, modes,
                           source_line=result.get("source_line"))
        return result

    def _apply_findings(self, record, findings):
        original = record["current_text"]
        if len({f.get("source_line_id", f["before"]) for f in findings}) != len(findings):
            raise ValueError("Selected corrections overlap; choose one per source line.")
        result = original
        # Descending original positions keep IDs valid when preceding edits add lines.
        for finding in sorted(findings, key=lambda f: f.get("source_line", 0), reverse=True):
            if finding.get("source_line_id"):
                locations = {line["source_line_id"]: line for line in self._editable_lines(record)}
                location = locations.get(finding["source_line_id"])
                if not location or location["before"] != finding["before"] or location["source_line"] != finding["source_line"]:
                    raise ValueError("Suggestion source changed; analyze again before applying edits.")
            result = scoped_replacement(result, finding["before"], finding["after"], finding["selected_views"], finding["selected_modes"],
                                        source_line=finding.get("source_line"))
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
