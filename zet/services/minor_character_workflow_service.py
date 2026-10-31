"""Current-board lifecycle and rendering for Minor Characters.

Private candidates remain immutable render dependencies. Only current slot membership
grants working-image access; undo restores a recipe, never candidate membership.
"""
from __future__ import annotations

import base64
import hashlib
from copy import deepcopy
from pathlib import Path
from uuid import uuid4, uuid5, NAMESPACE_URL

from zet.services.image_reconstruction_contract import correction_items, text
from zet.services.quick_character_wizard_service import QuickCharacterWizardError, QuickCharacterWizardConflict


class MinorCharacterWorkflow:
    @staticmethod
    def _views(session):
        return ["STYLE", "FRONT", "FRONT_LEFT_3_4", "FRONT_RIGHT_3_4", "LEFT_PROFILE", "RIGHT_PROFILE"]

    def _initialize_workflow(self, session):
        session.update(workflow_version=1, boards={view: self._empty_board(session, view) for view in self._views(session)},
                       final_boards={view: self._empty_board(session, view, "final") for view in self._views(session)},
                       final_selected={}, final_locked={})

    @staticmethod
    def _empty_board(session, view, render_mode="draft"):
        suffix = "" if render_mode == "draft" else f":{render_mode}"
        return {"board_id": uuid5(NAMESPACE_URL, f"minor-board:{session['session_id']}:{view}{suffix}").hex,
                "render_mode": render_mode,
                "view": view, "revision": 0, "mode": "alignment", "slots": [None] * 4,
                "selected_id": "", "prior_selection_id": "", "template_candidate_id": "",
                "restored_source_id": "",
                "edit": {"candidate_id": "", "item_ids": [], "instructions": ""}, "undo": None}

    def _board(self, session, view, expected=None, render_mode="draft"):
        if view not in self._views(session):
            raise QuickCharacterWizardError("Choose a character stage or view.")
        if render_mode not in ("draft", "final"):
            raise QuickCharacterWizardError("Render mode must be draft or final.")
        key = "final_boards" if render_mode == "final" else "boards"
        board = session.setdefault(key, {}).setdefault(view, self._empty_board(session, view, render_mode))
        if expected is not None and (type(expected) is not int or board["revision"] != expected):
            raise QuickCharacterWizardConflict("This board changed. Reload it before trying again.")
        return board

    @staticmethod
    def _working_ids(session):
        return {cid for key in ("boards", "final_boards") for board in session.get(key, {}).values() for cid in board["slots"] if cid}

    def _public(self, session):
        value = super()._public(session)
        working = self._working_ids(session)
        value["candidates"] = [c for c in value["candidates"] if c["candidate_id"] in working]
        by_id = {c["candidate_id"]: c for c in session["candidates"]}
        for key in ("boards", "final_boards"):
            for view, board in value.get(key, {}).items():
                board["can_undo"] = bool(board.pop("undo", None))
                template = by_id.get(board["template_candidate_id"], {})
                board["prompt"] = template.get("prompt", "")
                source = by_id.get(board["edit"]["candidate_id"], {})
                board["findings"] = board.get("restored_findings") or {k: deepcopy(source[k]) for k in ("comparison", "review", "error") if k in source}
                board["can_continue"] = bool(board["selected_id"] and board["mode"] == "alignment" and view != "STYLE")
        for candidate in value["candidates"]:
            candidate["can_lock"] = bool(candidate.get("image_url"))
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
        selected = session["final_selected" if board.get("render_mode", "draft") == "final" else "selected"]
        if candidate_id is None or board["selected_id"] == candidate_id:
            board["selected_id"] = ""
            selected.pop(board["view"], None)
        if candidate_id is None or board["prior_selection_id"] == candidate_id:
            board["prior_selection_id"] = ""

    @staticmethod
    def _assert_slots_unlocked(session, board, candidate_ids):
        key = "final_locked" if board.get("render_mode", "draft") == "final" else "locked"
        locked = (session.get(key) or {}).get(board["view"], {}).get("candidate_id")
        if locked and locked in candidate_ids:
            raise QuickCharacterWizardConflict("Unlock this mode's image before replacing its slot.")
        if any(candidate.get("candidate_id") in candidate_ids and candidate.get("status") in {"QUEUING", "QUEUED", "RUNNING"}
               for candidate in session.get("candidates") or []):
            raise QuickCharacterWizardConflict("Wait for the render to finish before replacing its slot.")

    @staticmethod
    def _other_mode_seed(session, view, render_mode, candidate_id):
        if not candidate_id:
            return None
        candidate = next((item for item in session.get("candidates", []) if item.get("candidate_id") == candidate_id), None)
        if (not candidate or candidate.get("view") != view or candidate.get("render_mode", "draft") == render_mode
                or type(candidate.get("seed")) is not int):
            raise QuickCharacterWizardError("Choose a same-view candidate from the other mode with a saved seed.")
        return candidate["seed"]

    def _new_candidate(self, session, view, instructions="", candidate_id="", item_ids=None, expected=None,
                       render_mode="draft", aspect_ratio=None, seed_candidate_id=""):
        board = self._board(session, view, expected, render_mode)
        requested_seed = self._other_mode_seed(session, view, render_mode, seed_candidate_id)
        selected = session["final_selected" if render_mode == "final" else "selected"]
        fallback = session["selected" if render_mode == "final" else "final_selected"]
        by_id = {c["candidate_id"]: c for c in session["candidates"]}
        base = by_id.get(candidate_id)
        if candidate_id and (not base or base["view"] != view or not base.get("filename") or
                             (candidate_id not in board["slots"] and candidate_id != board["restored_source_id"])):
            raise QuickCharacterWizardError("Choose a current candidate to refine.")
        if base and view != "STYLE" and board["mode"] != "true_up":
            raise QuickCharacterWizardError("Select an aligned image and continue to true-ups first.")
        anchor_id = next((cid for cid in (selected.get("STYLE"), fallback.get("STYLE"))
                          if cid and by_id.get(cid, {}).get("filename")
                          and self._candidate_source_path(session["session_id"], session, by_id[cid]).is_file()), None)
        if not base and view != "STYLE" and not anchor_id:
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
        self._assert_slots_unlocked(session, board, {cid for cid in board["slots"] if cid and cid != selected})
        slots = [cid if cid == selected else None for cid in board["slots"]]
        target = next((n for n, cid in enumerate(slots) if cid is None), 0)
        cid = uuid4().hex
        kind = "true_up" if base else "alignment"
        # A view's style anchor and intent are frozen at alignment, not reread from the form.
        anchor = base.get("anchor_id") if base else anchor_id if view != "STYLE" else None
        source = base or by_id.get(anchor)
        inputs = deepcopy(source["inputs"]) if source else self._snapshot(session)
        candidate = {"candidate_id": cid, "view": view, "stage": view, "kind": kind,
                     "revision_id": session["revision_id"], "anchor_id": anchor,
                     "refinement_base_id": candidate_id or None, "request_id": "", "status": "QUEUING",
                     "error": "", "review": "", "refinements": [], "stale": False,
                     "instructions": instructions, "item_ids": item_ids or [], "created_at": self._now(), "inputs": inputs,
                     "render_mode": render_mode}
        from zet.services.image_sizing_service import resolve_image_sizing
        ratio = aspect_ratio or ("2:3" if inputs.get("framing") == "full_body" else "1:1")
        candidate["render_sizing"] = resolve_image_sizing(self.app.config, render_mode, ratio)
        if requested_seed is not None:
            candidate.update(requested_seed=requested_seed, seed_source_candidate_id=seed_candidate_id)
        from zet.services.atomic_file_service import write_bytes_atomic
        for key, reference in (("base_snapshot", base), ("anchor_snapshot", by_id.get(anchor))):
            if reference:
                source_path = self._candidate_source_path(session["session_id"], session, reference)
                relative = f"renders/inputs/{cid}/{key}{source_path.suffix}"
                contents = source_path.read_bytes()
                write_bytes_atomic(self._directory(session["session_id"]) / relative, contents)
                candidate[key] = relative
                candidate[f"{key}_sha256"] = hashlib.sha256(contents).hexdigest()
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

    def render(self, sid, revision_id, view, instructions="", candidate_id="", item_ids=None, expected=None,
               render_mode="draft", aspect_ratio=None, seed_candidate_id=""):
        sid = self._canonical(sid)["session_id"]
        with self._lock(sid):
            session = self._read(sid)
            self._board(session, view, expected, render_mode)
            if self._busy(session):
                raise QuickCharacterWizardConflict("An image task is already running.")
            pending = dict(view=view, instructions=text(instructions, "Changes"), candidate_id=candidate_id,
                           item_ids=item_ids or [], expected=expected, render_mode=render_mode, aspect_ratio=aspect_ratio,
                           seed_candidate_id=seed_candidate_id)
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
                refs = [("Candidate to correct; preserve unaffected details", self._frozen_reference_path(sid, candidate, "base_snapshot", base).read_bytes())]
                prompt = " ".join(filter(None, [
                    "Edit the image as the canvas. Apply only these corrections, with the operator's final instruction taking precedence. "
                    "Preserve the existing composition, framing, orientation, identity, costume, equipment, anatomical asymmetry, "
                    "colors, and art style wherever a correction does not explicitly change them.",
                    *candidate["corrections"], candidate["instructions"]]))
                payload = self._image_spec(prompt, refs)
            elif view != "STYLE":
                if not anchor:
                    raise QuickCharacterWizardError("The selected style image is unavailable.")
                payload = self._image_spec(context, [("Selected style image; change orientation only", self._frozen_reference_path(sid, candidate, "anchor_snapshot", anchor).read_bytes())])
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
            self._dispatch_candidate(sid, candidate, payload,
                                     [candidate["requested_seed"]] if "requested_seed" in candidate else None)
        except Exception as exc:
            with self._lock(sid):
                current = self._read(sid)
                target = next(c for c in current["candidates"] if c["candidate_id"] == candidate_id)
                target.update(status="FAILED", error=str(exc))
                self._write(current)

    def _candidate_bytes(self, sid, candidate):
        return (self._directory(sid) / candidate["filename"]).read_bytes()

    def _candidate_source_path(self, sid, session, candidate):
        mode = candidate.get("render_mode", "draft")
        locks = session.get("final_locked" if mode == "final" else "locked") or {}
        if locks.get(candidate["view"], {}).get("candidate_id") == candidate["candidate_id"]:
            return self.locked_image_path(sid, candidate["view"], mode)
        return self._directory(sid) / candidate["filename"]

    def _frozen_reference_path(self, sid, candidate, key, fallback):
        relative = candidate.get(key)
        root = self._directory(sid).resolve()
        path = (root / relative).resolve() if relative else self._candidate_source_path(sid, self._read(sid), fallback).resolve()
        if relative and not path.is_relative_to(root):
            raise QuickCharacterWizardError("Saved render reference is outside this workspace.")
        if not path.is_file():
            raise QuickCharacterWizardError("Saved render reference is unavailable.")
        digest = candidate.get(f"{key}_sha256")
        if relative and digest and hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise QuickCharacterWizardError("Saved render reference has changed.")
        return path

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
        context += (f"\nCurrent board target view: {candidate['view']}. Evaluate composition and anatomical orientation "
                    "against this exact requested view; earlier orientation directions are superseded for this review.")
        if candidate.get("reconstruction_id"):
            comparison = self._reconstruction().compare(candidate["reconstruction_id"], self._candidate_bytes(sid, candidate),
                {"session_id": sid, "candidate_id": candidate_id}, context,
                self._frozen_reference_path(sid, candidate, "anchor_snapshot", anchor).read_bytes() if anchor else None, anchor_role="Selected style image: completed identity, costume and style; orientation may change",
                review_role="character_review", review_model=frozen["model"] if frozen.get("model_explicit", True) else "")
        else:
            from zet.services.image_true_up_service import ImageTrueUpService
            paths = [str(self._directory(sid) / candidate["filename"]), *self._reference_paths(frozen)]
            roles = ["candidate", *[r["caption"] for r in self._ordered_references(frozen)]]
            if anchor:
                paths.append(str(self._frozen_reference_path(sid, candidate, "anchor_snapshot", anchor)))
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
            render_mode = data.get("render_mode", "draft")
            board = self._board(session, view, expected, render_mode)
            board_key = "final_boards" if render_mode == "final" else "boards"
            selected_key = "final_selected" if render_mode == "final" else "selected"
            if action == "edit":
                self._edit_board(board, data)
            elif action == "continue":
                candidate_id = data.get("candidate_id") or board["selected_id"]
                candidate = next((c for c in session["candidates"] if c["candidate_id"] == candidate_id
                                  and c["view"] == view and c.get("filename")), None)
                if (view == "STYLE" or board["mode"] != "alignment" or not candidate
                        or candidate_id not in board["slots"]):
                    raise QuickCharacterWizardError("Select a view-aligned image before continuing to true-ups.")
                self._assert_slots_unlocked(session, board, {cid for cid in board["slots"] if cid and cid != candidate_id})
                board.update(mode="true_up", selected_id=candidate_id, prior_selection_id=candidate_id)
                session[selected_key][view] = candidate_id
                board["slots"] = [cid if cid == candidate_id else None for cid in board["slots"]]
                if board["edit"]["candidate_id"] != candidate_id:
                    board["edit"] = {"candidate_id": candidate_id, "item_ids": [], "instructions": ""}
            elif action == "undo":
                if not board["undo"]:
                    raise QuickCharacterWizardError("There is no previous true-up prompt.")
                self._assert_slots_unlocked(session, board, set(board["slots"]))
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
                        for target, other in session[board_key].items() if target != "STYLE")
                    if views_started and data.get("confirm_views_discarded") is not True:
                        raise QuickCharacterWizardConflict(
                            "Restarting Style alignment discards all view images and revisions. Confirm to continue.")
                    for target in self._views(session):
                        self._assert_slots_unlocked(session, session[board_key][target], set(session[board_key][target]["slots"]))
                    for target in self._views(session):
                        revision = session[board_key][target]["revision"] + 1
                        session[board_key][target] = self._empty_board(session, target, render_mode)
                        session[board_key][target]["revision"] = revision
                    session[selected_key] = {}
                    session.update(notes="", changes="", description="", identity="",
                        observations=[], proposals=[], questions=[], answers=[], proposals_approved=False,
                        needs_analysis=True, revision_id=uuid4().hex, status="DRAFT_READY",
                        job={"kind": "draft", "status": "COMPLETE", "error": ""},
                        active_view="STYLE", preview_candidate_id="")
                    for key in ("reconstruction_id", "target_hash", "description_override", "analysis_inputs"):
                        session.pop(key, None)
                    self._write(session)
                    restart_style = True
                else:
                    if not (session[selected_key].get("STYLE") or session["selected" if render_mode == "final" else "final_selected"].get("STYLE")):
                        raise QuickCharacterWizardConflict("Select a style-alignment image before restarting this view.")
                    self._assert_slots_unlocked(session, board, set(board["slots"]))
                    revision = board["revision"] + 1
                    board.clear()
                    board.update(self._empty_board(session, view, render_mode))
                    board["revision"] = revision
                    session[selected_key].pop(view, None)
                    session["preview_candidate_id"] = ""
                    session["active_view"] = view
                    candidate = self._new_candidate(session, view, render_mode=render_mode, aspect_ratio=data.get("aspect_ratio"))
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

    def board_slots(self, sid, board_id, action, slot=None, count=1, expected=None, aspect_ratio=None, seed_candidate_id=""):
        sid = self._canonical(sid)["session_id"]
        with self._lock(sid):
            session = self._read(sid)
            board = next((b for key in ("boards", "final_boards") for b in session[key].values() if b["board_id"] == board_id), None)
            if not board:
                raise QuickCharacterWizardError("This board is no longer available.")
            render_mode = board.get("render_mode", "draft")
            self._board(session, board["view"], expected, render_mode)
            if action not in {"add", "clear", "regenerate", "retry"}:
                raise QuickCharacterWizardError("Choose a slot action.")
            if action != "add" and (type(slot) is not int or not 0 <= slot < 4):
                raise QuickCharacterWizardError("Choose a slot from 1 to 4.")
            requested_seed = self._other_mode_seed(session, board["view"], render_mode, seed_candidate_id)
            if requested_seed is not None and action == "add" and count != 1:
                raise QuickCharacterWizardError("Reuse a seed for one render at a time.")
            previous_candidate = next((c for c in session["candidates"] if c["candidate_id"] == board["slots"][slot]), None) if action != "add" else None
            previous_job = None
            if action == "retry":
                if not previous_candidate or previous_candidate.get("status") != "FAILED" or not previous_candidate.get("render_payload"):
                    raise QuickCharacterWizardConflict("Choose a failed render with saved inputs.")
                previous_job = self._generation()._jobs.get(previous_candidate.get("render_request_id"))
                if not previous_job or not previous_job.get("children") or "seed" not in previous_job["children"][0]:
                    raise QuickCharacterWizardConflict("The original render seed is unavailable; regenerate instead.")
            if action != "add":
                self._assert_slots_unlocked(session, board, {board["slots"][slot]})
                if board["edit"]["candidate_id"] == board["slots"][slot]:
                    board["edit"] = {"candidate_id": "", "item_ids": [], "instructions": ""}
                self._forget_selection(session, board, board["slots"][slot])
                board["slots"][slot] = None
            candidates = []
            if action != "clear":
                template = previous_candidate if action == "retry" else next((c for c in session["candidates"] if c["candidate_id"] == board["template_candidate_id"]), None)
                if not template or not template.get("render_payload"):
                    raise QuickCharacterWizardConflict("Generate an alignment or true-up prompt first.")
                empty = [n for n, cid in enumerate(board["slots"]) if not cid]
                if action == "add" and (type(count) is not int or not 1 <= count <= len(empty)):
                    raise QuickCharacterWizardError("Choose a render count within the empty slots.")
                for target in empty[:count] if action == "add" else [slot]:
                    candidate = deepcopy({k: v for k, v in template.items() if k in {
                        "view", "stage", "kind", "revision_id", "anchor_id", "refinement_base_id", "instructions",
                        "item_ids", "inputs", "reconstruction_id", "target_hash", "view_context", "accepted_direction", "corrections", "render_mode", "base_snapshot", "base_snapshot_sha256", "anchor_snapshot", "anchor_snapshot_sha256"}})
                    candidate.update(candidate_id=uuid4().hex, board_id=board["board_id"], request_id="",
                                     status="QUEUING", error="", review="", refinements=[], stale=False, created_at=self._now())
                    if action == "retry":
                        sizing = template.get("render_sizing") or previous_job.get("render_sizing")
                        if sizing:
                            candidate["render_sizing"] = deepcopy(sizing)
                        candidate["retry_of"] = template["candidate_id"]
                    else:
                        from zet.services.image_sizing_service import resolve_image_sizing
                        ratio = aspect_ratio or ("2:3" if candidate.get("inputs", {}).get("framing") == "full_body" else "1:1")
                        candidate["render_sizing"] = resolve_image_sizing(self.app.config, render_mode, ratio)
                        candidate["render_mode"] = render_mode
                        if requested_seed is not None:
                            candidate.update(requested_seed=requested_seed, seed_source_candidate_id=seed_candidate_id)
                    session["candidates"].append(candidate)
                    board["slots"][target] = candidate["candidate_id"]
                    candidates.append(candidate)
            board["revision"] += 1
            self._write(session)
            for candidate in candidates:
                seeds = [previous_job["children"][0]["seed"]] if action == "retry" else [requested_seed] if requested_seed is not None else None
                self._dispatch_candidate(sid, candidate, deepcopy(template["render_payload"]), seeds)
            return self._public(self._read(sid))

    def select(self, sid, revision_id, candidate_id, expected=None):
        sid = self._canonical(sid)["session_id"]
        with self._lock(sid):
            session = self._read(sid)
            candidate = next((c for c in session["candidates"] if c["candidate_id"] == candidate_id and c.get("filename")), None)
            if not candidate or candidate_id not in self._working_ids(session):
                raise QuickCharacterWizardError("Choose a current rendered image.")
            render_mode = candidate.get("render_mode", "draft")
            board = self._board(session, candidate["view"], expected, render_mode)
            board["selected_id"] = candidate_id
            session["final_selected" if render_mode == "final" else "selected"][candidate["view"]] = candidate_id
            board["revision"] += 1
            self._write(session)
            return self._public(session)

    def retry_render(self, sid, revision_id, candidate_id):
        session = self._read(self._canonical(sid)["session_id"])
        board = next((b for key in ("boards", "final_boards") for b in session[key].values() if candidate_id in b["slots"]), None)
        if not board:
            raise QuickCharacterWizardError("Choose a current failed slot.")
        return self.board_slots(sid, board["board_id"], "retry", board["slots"].index(candidate_id), expected=board["revision"])

    def view_slots(self, sid, view, data):
        sid = self._canonical(sid)["session_id"]
        with self._lock(sid):
            session = self._read(sid)
            board = self._board(session, view, data["revision"], data.get("render_mode", "draft"))
            return self.board_slots(sid, board["board_id"], data.get("action"), data.get("slot"),
                                        data.get("count", 1), expected=data["revision"], aspect_ratio=data.get("aspect_ratio"),
                                        seed_candidate_id=data.get("seed_candidate_id", ""))

    def image_path(self, sid, *, reference_index=None, candidate_id=""):
        if candidate_id:
            session = self._read(sid)
            if session.get("deleted_at") or candidate_id not in self._working_ids(session):
                raise QuickCharacterWizardError("This image is no longer in a working slot.")
        return super().image_path(sid, reference_index=reference_index, candidate_id=candidate_id)
