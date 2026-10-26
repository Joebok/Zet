"""Current-board lifecycle and rendering for Minor Characters.

Private candidates remain immutable render dependencies. Only current slot membership
grants working-image access; undo restores a recipe, never candidate membership.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from pathlib import Path
from uuid import uuid4, uuid5, NAMESPACE_URL

from zet.services.image_reconstruction_contract import correction_items, text
from zet.services.quick_character_wizard_service import QuickCharacterWizardError, QuickCharacterWizardConflict


class MinorCharacterWorkflow:
    @staticmethod
    def _views(session):
        side = session["side"].upper()
        return ["STYLE", "FRONT", f"FRONT_{side}_3_4", f"{side}_PROFILE"]

    def _initialize_workflow(self, session):
        session.update(workflow_version=1, boards={view: self._empty_board(session, view) for view in self._views(session)})

    @staticmethod
    def _empty_board(session, view):
        return {"board_id": uuid5(NAMESPACE_URL, f"minor-board:{session['session_id']}:{view}").hex,
                "view": view, "revision": 0, "mode": "alignment", "slots": [None] * 4,
                "selected_id": "", "prior_selection_id": "", "template_candidate_id": "",
                "restored_source_id": "",
                "edit": {"candidate_id": "", "item_ids": [], "instructions": ""}, "undo": None}

    def _board(self, session, view, expected=None):
        if view not in self._views(session):
            raise QuickCharacterWizardError("Choose a character stage or view.")
        board = session["boards"].setdefault(view, self._empty_board(session, view))
        if expected is not None and (type(expected) is not int or board["revision"] != expected):
            raise QuickCharacterWizardConflict("This board changed. Reload it before trying again.")
        return board

    @staticmethod
    def _working_ids(session):
        return {cid for board in session.get("boards", {}).values() for cid in board["slots"] if cid}

    def _public(self, session):
        value = super()._public(session)
        working = self._working_ids(session)
        value["candidates"] = [c for c in value["candidates"] if c["candidate_id"] in working]
        by_id = {c["candidate_id"]: c for c in session["candidates"]}
        for view, board in value["boards"].items():
            board["can_undo"] = bool(board.pop("undo", None))
            template = by_id.get(board["template_candidate_id"], {})
            board["prompt"] = template.get("prompt", "")
            source = by_id.get(board["edit"]["candidate_id"], {})
            board["findings"] = board.get("restored_findings") or {k: deepcopy(source[k]) for k in ("comparison", "review", "error") if k in source}
            board["can_continue"] = bool(board["selected_id"] and board["mode"] == "alignment" and view != "STYLE")
        for candidate in value["candidates"]:
            candidate["can_lock"] = bool(candidate.get("image_url")) and candidate.get("kind") == "true_up" and candidate["view"] != "STYLE"
        value.pop("analysis_inputs", None)
        return value

    @staticmethod
    def alignment_prompt(view):
        preserve = ("Preserve the character's identity, facial features, costume, equipment, "
                    "anatomical asymmetry, colors, and art style from the image.")
        if view == "FRONT":
            return ("Turn the character in the image to a straight-on front view. Head, torso, and hips face the camera; "
                    "both shoulders are equally visible. " + preserve)
        side = "left" if "LEFT" in view else "right"
        if "3_4" in view:
            orientation = (f"Turn the character in the image to a front three-quarter view showing the character's anatomical {side} side. "
                           "Keep part of the far side of the face and front of the torso visible.")
        else:
            orientation = (f"Turn the character in the image to a strict profile showing the character's anatomical {side} side. "
                           "The near side of the face is visible; the far eye is hidden.")
        return (orientation + " Head, torso, and hips share the same rotation; gaze follows the face. " + preserve)

    @staticmethod
    def _style_reference_prompt(references):
        if len(references) == 1:
            return f"Use the image as the primary identity and appearance reference ({references[0][0]})."
        return " ".join(
            f"Use <image{index}> as {'the primary identity and appearance reference' if index == 1 else 'a supporting reference'} ({label})."
            for index, (label, _) in enumerate(references, start=1))

    def _forget_selection(self, session, board, candidate_id=None):
        if candidate_id is None or board["selected_id"] == candidate_id:
            board["selected_id"] = ""
            session["selected"].pop(board["view"], None)
        if candidate_id is None or board["prior_selection_id"] == candidate_id:
            board["prior_selection_id"] = ""

    def _new_candidate(self, session, view, instructions="", candidate_id="", item_ids=None, expected=None):
        board = self._board(session, view, expected)
        by_id = {c["candidate_id"]: c for c in session["candidates"]}
        base = by_id.get(candidate_id)
        if candidate_id and (not base or base["view"] != view or not base.get("filename") or
                             (candidate_id not in board["slots"] and candidate_id != board["restored_source_id"])):
            raise QuickCharacterWizardError("Choose a current candidate to refine.")
        if base and view != "STYLE" and board["mode"] != "true_up":
            raise QuickCharacterWizardError("Select an aligned image and continue to true-ups first.")
        if not base and view != "STYLE" and not session["selected"].get("STYLE"):
            raise QuickCharacterWizardError("Select a style-alignment image before aligning views.")
        if base:
            report = (board.get("restored_findings") or {}).get("comparison") or base.get("comparison") or {"items": []}
            corrections = correction_items(report, item_ids or [], instructions)
            board["edit"] = {"candidate_id": candidate_id, "item_ids": item_ids or [], "instructions": instructions}
            board["undo"] = deepcopy({k: v for k, v in board.items() if k not in {"undo", "slots", "selected_id", "prior_selection_id"}})
            board["undo"]["restored_findings"] = deepcopy({k: base[k] for k in ("comparison", "review", "error") if k in base})
        else:
            board["undo"] = None
            board["edit"] = {"candidate_id": "", "item_ids": [], "instructions": ""}
        selected = board["selected_id"] if base else ""
        slots = [cid if cid == selected else None for cid in board["slots"]]
        target = next((n for n, cid in enumerate(slots) if cid is None), 0)
        cid = uuid4().hex
        kind = "true_up" if base else "alignment"
        # A view's style anchor and intent are frozen at alignment, not reread from the form.
        anchor = base.get("anchor_id") if base else session["selected"].get("STYLE") if view != "STYLE" else None
        source = base or by_id.get(anchor)
        inputs = deepcopy(source["inputs"]) if source else self._snapshot(session)
        candidate = {"candidate_id": cid, "view": view, "stage": view, "kind": kind,
                     "revision_id": session["revision_id"], "anchor_id": anchor,
                     "refinement_base_id": candidate_id or None, "request_id": "", "status": "QUEUING",
                     "error": "", "review": "", "refinements": [], "stale": False,
                     "instructions": instructions, "item_ids": item_ids or [], "created_at": self._now(), "inputs": inputs}
        previous_intent = (base or by_id.get(anchor) or {}).get("accepted_direction", [])
        candidate["accepted_direction"] = deepcopy(previous_intent)
        if base:
            candidate["corrections"] = [i["correction"] for i in corrections]
            candidate["accepted_direction"] += candidate["corrections"]
            if instructions:
                candidate["accepted_direction"].append(instructions)
        for key in ("reconstruction_id", "target_hash"):
            if key in inputs:
                candidate[key] = inputs[key]
        slots[target] = cid
        board.update(slots=slots, template_candidate_id=cid, prior_selection_id=selected,
                     restored_source_id="", mode="true_up" if base else "alignment", revision=board["revision"] + 1)
        if not selected:
            self._forget_selection(session, board)
        candidate.update(board_id=board["board_id"], board_revision=board["revision"])
        board["edit"] = {"candidate_id": cid, "item_ids": [], "instructions": ""}
        board.pop("restored_findings", None)
        session["candidates"].append(candidate)
        session.update(status="RENDERING", job={"kind": "render", "status": "COMPLETE", "error": ""})
        return candidate

    def render(self, sid, revision_id, view, instructions="", candidate_id="", item_ids=None, expected=None):
        sid = self._canonical(sid)["session_id"]
        with self._lock(sid):
            session = self._read(sid)
            self._board(session, view, expected)
            if self._busy(session):
                raise QuickCharacterWizardConflict("An image task is already running.")
            pending = dict(view=view, instructions=text(instructions, "Changes"), candidate_id=candidate_id,
                           item_ids=item_ids or [], expected=expected)
            if view == "STYLE" and not candidate_id and (session["needs_analysis"] or not session["description"]):
                return self._analyze(sid, pending=pending)
            candidate = self._new_candidate(session, **pending)
            self._write(session)
            self._submit(sid, self._render_job, candidate["candidate_id"], item_ids)
            return self._public(session)

    def _render_job(self, sid, candidate_id, item_ids):
        session = self._read(sid)
        candidate = next(c for c in session["candidates"] if c["candidate_id"] == candidate_id)
        frozen = {**session, **candidate["inputs"]}
        by_id = {c["candidate_id"]: c for c in session["candidates"]}
        view = candidate["view"]
        base = by_id.get(candidate["refinement_base_id"])
        anchor = by_id.get(candidate["anchor_id"])
        try:
            refs = []
            framing = "Full body, head to toe, feet visible." if frozen["framing"] == "full_body" else "Head-and-shoulders portrait."
            context = ("Create one character reference in the requested art style, preserving the character's identity, "
                       "costume, equipment, and anatomical asymmetry. Use a neutral pose and plain neutral background. "
                       "Choose a natural angle that shows the design clearly. " + framing
                       if view == "STYLE" else self.alignment_prompt(view) + " Keep the character in a neutral pose "
                       "against a plain neutral background. " + framing)
            if base:
                refs = [("Candidate to correct; preserve unaffected details", self._candidate_bytes(sid, base))]
                prompt = " ".join(filter(None, [
                    "Edit the image as the canvas. Apply only these corrections, with the operator's final instruction taking precedence. "
                    "Preserve the existing composition, framing, orientation, identity, costume, equipment, anatomical asymmetry, "
                    "colors, and art style wherever a correction does not explicitly change them.",
                    *candidate["corrections"], candidate["instructions"]]))
                payload = self._image_spec(prompt, refs)
            elif view != "STYLE":
                if not anchor:
                    raise QuickCharacterWizardError("The selected style image is unavailable.")
                payload = self._image_spec(context, [("Selected style image; change orientation only", self._candidate_bytes(sid, anchor))])
            elif candidate.get("reconstruction_id"):
                payload = self._reconstruction().render_spec(candidate["reconstruction_id"], context)
            else:
                prompt = "\n".join([context, frozen["description"], frozen["identity"], *frozen["proposals"], frozen.get("changes", "")])
                refs = [(r["caption"], path.read_bytes()) for r, path in
                        zip(self._ordered_references(frozen), map(Path, self._reference_paths(frozen)))]
                prompt = self._style_reference_prompt(refs) + "\n" + prompt
                payload = self._image_spec(prompt, refs)
            payload.update(count=1, width=832 if frozen["framing"] == "full_body" else 1024,
                           height=1216 if frozen["framing"] == "full_body" else 1024)
            candidate["view_context"] = context
            self._dispatch_candidate(sid, candidate, payload)
        except Exception as exc:
            with self._lock(sid):
                current = self._read(sid)
                target = next(c for c in current["candidates"] if c["candidate_id"] == candidate_id)
                target.update(status="FAILED", error=str(exc))
                self._write(current)

    def _candidate_bytes(self, sid, candidate):
        return (self._directory(sid) / candidate["filename"]).read_bytes()

    @staticmethod
    def _image_spec(prompt, references):
        return {"mode": "img2img", "prompt": prompt, "negative_prompt": "", "count": 1,
                "render_config": {"append_reference_labels": False},
                "reference_images": [{"label": label, "image": base64.b64encode(contents).decode("ascii")}
                                     for label, contents in references]}

    def _dispatch_candidate(self, sid, candidate, payload, seeds=None):
        with self._lock(sid):
            current = self._read(sid)
            if current.get("deleted_at") or candidate["candidate_id"] not in self._working_ids(current):
                return
            super()._dispatch_candidate(sid, candidate, payload, seeds)

    def _review_job(self, sid, candidate_id):
        session = self._read(sid)
        candidate = next(c for c in session["candidates"] if c["candidate_id"] == candidate_id)
        if candidate_id not in self._working_ids(session):
            return
        if session.get("deleted_at"):
            return
        self._review_harvest(sid, candidate)
        from zet.services.ai_workflow_service import current_workflow
        context_state = current_workflow.get()
        if context_state is not None:
            context_state["admission"] = lambda: self._review_admission(sid, candidate)
        frozen = {**session, **candidate.get("inputs", {})}
        anchor = next((c for c in session["candidates"] if c["candidate_id"] == candidate.get("anchor_id")), None)
        context = candidate.get("view_context", "")
        # Flattened accepted intent avoids traversing an unbounded refinement history.
        if anchor:
            context += "\nThe selected style image establishes intentional completed design; do not restore earlier source details that differ from it."
        if candidate.get("accepted_direction"):
            context += "\nAccepted operator direction, oldest to newest; latest takes precedence:\n" + "\n".join(candidate["accepted_direction"])
        if candidate.get("reconstruction_id"):
            comparison = self._reconstruction().compare(candidate["reconstruction_id"], self._candidate_bytes(sid, candidate),
                {"session_id": sid, "candidate_id": candidate_id}, context,
                self._candidate_bytes(sid, anchor) if anchor else None, anchor_role="Selected style image: completed identity, costume and style; orientation may change",
                review_role="character_review", review_model=frozen["model"] if frozen.get("model_explicit", True) else "")
        else:
            from zet.services.image_true_up_service import ImageTrueUpService
            paths = [str(self._directory(sid) / candidate["filename"]), *self._reference_paths(frozen)]
            roles = ["candidate", *[r["caption"] for r in self._ordered_references(frozen)]]
            if anchor:
                paths.append(str(self._directory(sid) / anchor["filename"]))
                roles.append("Selected style image: completed identity, costume and style")
            target = {"description": frozen["description"], "identity": frozen["identity"],
                      "preserve": frozen["preserve"], "change_text": frozen["changes"], "proposals": frozen["proposals"],
                      "style": {}, "notes": frozen["notes"], "observations": [], "sources": []}
            comparison = ImageTrueUpService(lambda model, prompt, schema, images: self._ask(prompt, schema, images, model if frozen.get("model_explicit", True) else None, role="character_review")).compare(
                frozen["model"], target, paths, {"roles": roles, "task": context})
        with self._lock(sid):
            current = self._read(sid)
            if current.get("deleted_at") or candidate_id not in self._working_ids(current):
                return
            target = next(c for c in current["candidates"] if c["candidate_id"] == candidate_id)
            target.update(status="READY", review=comparison["summary"], comparison=comparison,
                          refinements=[i["correction"] for i in comparison["items"] if i["correction"]], error="")
            self._write(current)

    def board_action(self, sid, view, action, expected=None, data=None):
        sid = self._canonical(sid)["session_id"]
        data = data or {}
        restart_style = False
        with self._lock(sid):
            session = self._read(sid)
            board = self._board(session, view, expected)
            if action == "edit":
                self._edit_board(board, data)
            elif action == "continue":
                if view == "STYLE" or board["mode"] != "alignment" or not board["selected_id"]:
                    raise QuickCharacterWizardError("Select a view-aligned image before continuing to true-ups.")
                board.update(mode="true_up", prior_selection_id=board["selected_id"])
                board["slots"] = [cid if cid == board["selected_id"] else None for cid in board["slots"]]
                board["edit"] = {"candidate_id": board["selected_id"], "item_ids": [], "instructions": ""}
            elif action == "undo":
                if not board["undo"]:
                    raise QuickCharacterWizardError("There is no previous true-up prompt.")
                restored = deepcopy(board["undo"])
                revision = board["revision"]
                self._forget_selection(session, board)
                board.clear()
                board.update(restored, slots=[None] * 4, selected_id="", prior_selection_id="", undo=None, revision=revision)
                board["restored_source_id"] = board["edit"]["candidate_id"]
            elif action == "restart":
                if self._busy(session):
                    raise QuickCharacterWizardConflict("Wait for the current image task to finish before restarting.")
                if view == "STYLE":
                    if not session["references"]:
                        raise QuickCharacterWizardError("Add at least one reference image before restarting Style alignment.")
                    views_started = any(
                        other["template_candidate_id"] or any(other["slots"]) or other["selected_id"]
                        or other["mode"] == "true_up" or other["undo"]
                        for target, other in session["boards"].items() if target != "STYLE")
                    if views_started and data.get("confirm_views_discarded") is not True:
                        raise QuickCharacterWizardConflict(
                            "Restarting Style alignment discards all view images and revisions. Confirm to continue.")
                    for target in self._views(session):
                        revision = session["boards"][target]["revision"] + 1
                        session["boards"][target] = self._empty_board(session, target)
                        session["boards"][target]["revision"] = revision
                    session.update(selected={}, notes="", changes="", description="", identity="",
                        observations=[], proposals=[], questions=[], answers=[], proposals_approved=False,
                        needs_analysis=True, revision_id=uuid4().hex, status="DRAFT_READY",
                        job={"kind": "draft", "status": "COMPLETE", "error": ""},
                        active_view="STYLE", preview_candidate_id="")
                    for key in ("reconstruction_id", "target_hash", "description_override", "analysis_inputs"):
                        session.pop(key, None)
                    self._write(session)
                    restart_style = True
                else:
                    if not session["selected"].get("STYLE"):
                        raise QuickCharacterWizardConflict("Select a style-alignment image before restarting this view.")
                    revision = board["revision"] + 1
                    board.clear()
                    board.update(self._empty_board(session, view))
                    board["revision"] = revision
                    session["selected"].pop(view, None)
                    session["preview_candidate_id"] = ""
                    session["active_view"] = view
                    candidate = self._new_candidate(session, view)
                    session.update(status="RENDERING", job={"kind": "render", "status": "COMPLETE", "error": ""})
                    self._write(session)
                    self._submit(sid, self._render_job, candidate["candidate_id"], [])
                    return self._public(session)
            else:
                raise QuickCharacterWizardError("Choose a board action.")
            if not restart_style:
                board["revision"] += 1
                self._write(session)
                return self._public(session)
        return self._analyze(sid)

    @staticmethod
    def _edit_board(board, data):
        cid = str(data.get("candidate_id", ""))
        if cid and cid not in board["slots"] and cid != board["restored_source_id"]:
            raise QuickCharacterWizardError("Choose a current candidate.")
        ids = data.get("item_ids", [])
        if not isinstance(ids, list) or any(not isinstance(i, str) for i in ids):
            raise QuickCharacterWizardError("Choose suggested changes.")
        board["edit"] = {"candidate_id": cid, "item_ids": ids, "instructions": text(data.get("instructions", ""), "Changes")}

    def board_slots(self, sid, board_id, action, slot=None, count=1, expected=None):
        sid = self._canonical(sid)["session_id"]
        with self._lock(sid):
            session = self._read(sid)
            board = next((b for b in session["boards"].values() if b["board_id"] == board_id), None)
            if not board:
                raise QuickCharacterWizardError("This board is no longer available.")
            self._board(session, board["view"], expected)
            if action not in {"add", "clear", "regenerate"}:
                raise QuickCharacterWizardError("Choose a slot action.")
            if action != "add" and (type(slot) is not int or not 0 <= slot < 4):
                raise QuickCharacterWizardError("Choose a slot from 1 to 4.")
            if action != "add":
                if board["edit"]["candidate_id"] == board["slots"][slot]:
                    board["edit"] = {"candidate_id": "", "item_ids": [], "instructions": ""}
                self._forget_selection(session, board, board["slots"][slot])
                board["slots"][slot] = None
            candidates = []
            if action != "clear":
                template = next((c for c in session["candidates"] if c["candidate_id"] == board["template_candidate_id"]), None)
                if not template or not template.get("render_payload"):
                    raise QuickCharacterWizardConflict("Generate an alignment or true-up prompt first.")
                empty = [n for n, cid in enumerate(board["slots"]) if not cid]
                if action == "add" and (type(count) is not int or not 1 <= count <= len(empty)):
                    raise QuickCharacterWizardError("Choose a render count within the empty slots.")
                for target in empty[:count] if action == "add" else [slot]:
                    candidate = deepcopy({k: v for k, v in template.items() if k in {
                        "view", "stage", "kind", "revision_id", "anchor_id", "refinement_base_id", "instructions",
                        "item_ids", "inputs", "reconstruction_id", "target_hash", "view_context", "accepted_direction", "corrections"}})
                    candidate.update(candidate_id=uuid4().hex, board_id=board["board_id"], request_id="",
                                     status="QUEUING", error="", review="", refinements=[], stale=False, created_at=self._now())
                    session["candidates"].append(candidate)
                    board["slots"][target] = candidate["candidate_id"]
                    candidates.append(candidate)
            board["revision"] += 1
            self._write(session)
            for candidate in candidates:
                self._dispatch_candidate(sid, candidate, deepcopy(template["render_payload"]))
            return self._public(self._read(sid))

    def select(self, sid, revision_id, candidate_id, expected=None):
        sid = self._canonical(sid)["session_id"]
        with self._lock(sid):
            session = self._read(sid)
            candidate = next((c for c in session["candidates"] if c["candidate_id"] == candidate_id and c.get("filename")), None)
            if not candidate or candidate_id not in self._working_ids(session):
                raise QuickCharacterWizardError("Choose a current rendered image.")
            board = self._board(session, candidate["view"], expected)
            board["selected_id"] = candidate_id
            session["selected"][candidate["view"]] = candidate_id
            board["revision"] += 1
            self._write(session)
            return self._public(session)

    def retry_render(self, sid, revision_id, candidate_id):
        session = self._read(self._canonical(sid)["session_id"])
        board = next((b for b in session["boards"].values() if candidate_id in b["slots"]), None)
        if not board:
            raise QuickCharacterWizardError("Choose a current failed slot.")
        return self.board_slots(sid, board["board_id"], "regenerate", board["slots"].index(candidate_id), expected=board["revision"])

    def view_slots(self, sid, view, data):
        sid = self._canonical(sid)["session_id"]
        with self._lock(sid):
            session = self._read(sid)
            board = self._board(session, view, data["revision"])
            return self.board_slots(sid, board["board_id"], data.get("action"), data.get("slot"),
                                        data.get("count", 1), expected=data["revision"])

    def image_path(self, sid, *, reference_index=None, candidate_id=""):
        if candidate_id:
            session = self._read(sid)
            if session.get("deleted_at") or candidate_id not in self._working_ids(session):
                raise QuickCharacterWizardError("This image is no longer in a working slot.")
        return super().image_path(sid, reference_index=reference_index, candidate_id=candidate_id)
