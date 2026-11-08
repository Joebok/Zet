"""Persistent character Asset Containers with one mixed-quality board per view."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4
import hashlib
import os
import copy
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor
import threading

_LUNA_REVIEW_WORKERS = ThreadPoolExecutor(max_workers=2, thread_name_prefix="zet-luna-review")
_LUNA_REVIEW_ACTIVE = set()
_LUNA_REVIEW_ACTIVE_LOCK = threading.Lock()

from zet.services.atomic_file_service import write_json_atomic
from zet.services.local_image_pipeline_policy import local_image_pipeline_config
from zet.services.workflow_storage import file_lock
from zet.services.image_candidate_board_service import select as select_candidate, lock as lock_candidate, unlock as unlock_candidate
from zet.services.image_candidate_board_service import allocate as allocate_candidates, cleanup, remove, retry_request
from zet.services.image_candidate_board_service import record_render_start, record_render_completion
from zet.services.image_production_service import ImageProductionService
from zet.services.image_render_request import draft_upscale_request, verify_upscale_output


class CharacterAssetContainerError(ValueError):
    pass


class CharacterAssetContainerService:
    PIPELINES = ("body-reference", "head-image", "head-image-edit",
                 "character-assembly", "costume-dressing")

    def __init__(self, app):
        self.app = app
        self.library_root = Path(app.config.base_library_path).resolve()
        self.character_root = Path(app.config.base_character_path).resolve()
        self._publishing_board = False
        self.image_production = ImageProductionService(app)

    def _scope(self, character: str, phase: str, pipeline: str, costume: str = "") -> dict:
        pipeline = str(pipeline).strip().lower()
        if pipeline not in self.PIPELINES:
            raise CharacterAssetContainerError("Choose a supported character pipeline.")
        try:
            local_image_pipeline_config(pipeline)
        except ValueError as exc:
            raise CharacterAssetContainerError(str(exc)) from exc
        character, phase = str(character).strip(), str(phase).strip()
        if not character or not phase:
            raise CharacterAssetContainerError("Choose a character and phase.")
        root = self.character_root
        character_path = (root / character).resolve()
        phase_path = (character_path / phase).resolve()
        if (character_path.parent != root or phase_path.parent != character_path
                or not phase_path.is_dir()):
            raise CharacterAssetContainerError("The selected character phase is unavailable.")
        costume = str(costume).strip()
        if pipeline == "costume-dressing":
            if not costume:
                raise CharacterAssetContainerError("Choose a costume for this Dressing container.")
            from zet.services.costume_service import CostumeService
            costumes = CostumeService(self.app.asset_repository, self.app.path_service)
            available = costumes.list_costumes(character, phase)
            match = next((item for item in available if costume in {item.slug, item.name}), None)
            if not match:
                raise CharacterAssetContainerError("The selected costume is unavailable in this phase.")
            costume = match.slug
        elif costume:
            raise CharacterAssetContainerError("Only Costume Dressing containers have a costume.")
        return {"universe_id": str(self.app.universe_id), "character": character,
                "phase": phase, "pipeline": pipeline, "costume": costume,
                "views": self._views(pipeline)}

    @staticmethod
    def _views(pipeline: str) -> list[str]:
        from zet.services.view_conditioning_service import VIEW_ORDER
        return list(VIEW_ORDER)

    def _path(self, scope: dict) -> Path:
        values = [scope["character"], scope["phase"], scope["pipeline"], scope["costume"] or "_"]
        safe = [quote(item, safe="-_.") for item in values]
        return self.library_root / "_state" / "CharacterAssetContainers" / safe[0] / safe[1] / safe[2] / safe[3] / "container.json"

    def detail(self, character: str, phase: str, pipeline: str, costume: str = "") -> dict:
        scope = self._scope(character, phase, pipeline, costume)
        path = self._path(scope)
        with file_lock(path.with_suffix(".lock")):
            if not self._publishing_board:
                self._recover_publications(path, scope)
            try:
                import json
                if path.is_file():
                    value = json.loads(path.read_text(encoding="utf-8"))
                else:
                    value = self._empty(scope)
                    write_json_atomic(path, value)
            except (OSError, ValueError) as exc:
                raise CharacterAssetContainerError("The Asset Container is unreadable.") from exc
            if value.get("scope") != scope:
                raise CharacterAssetContainerError("The Asset Container scope does not match its location.")
            pending = value.get("cleanup_pending")
            if pending:
                try:
                    cleanup(path.parent, pending)
                except OSError:
                    pass  # Keep the durable intent for the next read.
                else:
                    del value["cleanup_pending"]
                    write_json_atomic(path, value)
            return copy.deepcopy(value)

    def governing_template(self, character: str, phase: str, pipeline: str, costume: str = "") -> Path:
        scope = self._scope(character, phase, pipeline, costume)
        path = (self.character_root / scope["character"] / scope["phase"] / "Character.md").resolve()
        if not path.is_relative_to(self.character_root) or not path.is_file():
            raise CharacterAssetContainerError("The current character master template is unavailable.")
        return path

    def _recover_publications(self, container_path: Path, scope: dict) -> None:
        journal_root = container_path.parent / "publications"
        if not journal_root.is_dir():
            return
        for journal_path in sorted(journal_root.glob("*.json")):
            try:
                import json
                with file_lock(container_path.with_suffix(".lock")):
                    if not journal_path.is_file():
                        continue
                    journal = json.loads(journal_path.read_text(encoding="utf-8"))
                    operation_id = str(journal.get("operation_id") or journal_path.stem)
                    if (len(operation_id) != 32 or any(char not in "0123456789abcdef" for char in operation_id)
                            or journal.get("scope") != scope
                            or Path(str(journal.get("container_path") or "")).resolve() != container_path.resolve()):
                        raise ValueError("Publication journal identity does not match its Asset Container.")
                    committed = self.app.entity_library_service.publication_receipt(operation_id) is not None
                    current = json.loads(container_path.read_text(encoding="utf-8")) if container_path.is_file() else None
                    if committed:
                        recovered = journal.get("next")
                        if not isinstance(recovered, dict) or recovered.get("scope") != scope:
                            raise ValueError("Committed publication journal is missing its next container state.")
                        if current is not None and (not isinstance(current, dict) or current.get("scope") != scope):
                            raise ValueError("Current container scope does not match its committed publication.")
                        next_revision = int(recovered.get("revision", -1))
                        current_revision = int(current.get("revision", -1)) if isinstance(current, dict) else -1
                        same_committed_state = current == recovered
                        if (current is None or (current.get("_pending_publication_id") == operation_id
                                and current_revision <= next_revision)
                                or current_revision < next_revision):
                            write_json_atomic(container_path, recovered)
                        elif current_revision == next_revision and not same_committed_state:
                            # A later board write can share the publication's revision if it
                            # raced with recovery after the in-flight marker was cleared.
                            # Preserve that state instead of replaying an older snapshot.
                            pass
                    elif isinstance(current, dict) and current.get("_pending_publication_id") == operation_id:
                        recovered = journal.get("previous")
                        if not isinstance(recovered, dict) or recovered.get("scope") != scope:
                            raise ValueError("Uncommitted publication journal is missing its previous container state.")
                        write_json_atomic(container_path, recovered)
                    journal_path.unlink(missing_ok=True)
            except (OSError, ValueError, TypeError) as exc:
                raise CharacterAssetContainerError(f"Could not recover Inventory publication: {exc}") from exc

    def progress(self, character: str, phase: str, pipeline: str, costume: str,
                 view: str) -> dict:
        value = self.detail(character, phase, pipeline, costume)
        board = value["boards"].get(view)
        if board is None:
            raise CharacterAssetContainerError("Choose a view in this container.")
        active = {"SUBMITTING", "QUEUED", "RUNNING", "DISPATCHING"}
        slots = [{"candidate_id": candidate_id, "slot": index + 1,
                  "status": candidate["status"], "image": bool(candidate.get("image_path")),
                  "error": candidate.get("error", ""), "locked": bool(candidate.get("locked"))}
                 for index, candidate_id in enumerate(board["slots"]) if candidate_id
                 for candidate in (board["candidates"][candidate_id],)]
        return {"container_id": value["container_id"], "revision": value["revision"],
                "view": view, "slots": slots, "selected_id": board["selected_id"],
                "active": [slot for slot in slots if slot["status"] in active],
                "luna_review": board.get("luna_review", {})}

    def luna_review(self, character: str, phase: str, pipeline: str, costume: str, view: str,
                    *, _review_id: str = "") -> dict:
        """Rank the current completed mixed-quality board and retain full reviews."""
        import hashlib
        from datetime import datetime, timezone
        from zet.services.local_image_ranking_service import review_images_with_luna

        path = self._path(self._scope(character, phase, pipeline, costume))
        with file_lock(path.with_suffix(".lock")):
            value = self.detail(character, phase, pipeline, costume)
            board = value["boards"].get(view)
            if board is None:
                raise CharacterAssetContainerError("Choose a view in this container.")
            candidates = [board["candidates"][cid] for cid in board["slots"] if cid
                          and board["candidates"].get(cid, {}).get("status") == "COMPLETE"
                          and board["candidates"][cid].get("image_path")]
            if not candidates:
                raise CharacterAssetContainerError("Generate at least one image before running Luna Review.")
            review_id = _review_id or uuid4().hex
            images = [Path(item["image_path"]).resolve() for item in candidates]
            ids = [str(item["candidate_id"]) for item in candidates]
            hashes = [hashlib.sha256(image.read_bytes()).hexdigest() for image in images]
            previous = board.get("luna_review", {})
            if not _review_id:
                if previous.get("status") == "RUNNING":
                    with _LUNA_REVIEW_ACTIVE_LOCK:
                        if previous.get("active_id") in _LUNA_REVIEW_ACTIVE:
                            return previous
                    previous = {**previous, "status": "INTERRUPTED", "active_id": ""}
                board["luna_review"] = {**previous, "status": "RUNNING", "active_id": review_id,
                                        "started_at": datetime.now(timezone.utc).isoformat()}
                board["revision"] += 1
                self.save(character, phase, pipeline, costume, value, expected_revision=value["revision"])
            elif previous.get("active_id") != review_id:
                return previous

        if not _review_id:
            with _LUNA_REVIEW_ACTIVE_LOCK:
                _LUNA_REVIEW_ACTIVE.add(review_id)
            _LUNA_REVIEW_WORKERS.submit(self._run_luna_review_worker, character, phase, pipeline, costume,
                                        view, review_id)
            return {"status": "RUNNING", "active_id": review_id}

        criteria = (f"Compare all completed {pipeline.replace('-', ' ')} images for {view}. Rank Draft and Final images together. "
                    "Assess requested view accuracy, source preservation, identity, anatomy, visible detail, and usefulness as a reference. "
                    "Give each image a concise but informative full assessment, noting visible strengths and defects.")
        references = []
        reference_labels = []
        selected_id = board.get("selected_id")
        for candidate in candidates:
            for item in (candidate.get("render_request") or {}).get("inputs", []):
                if item.get("candidate_id") == selected_id and item.get("render_mode") == "draft":
                    continue
                reference = Path(str(item.get("path") or "")).resolve()
                if reference.is_file():
                    references.append(reference)
                    reference_labels.append(f"{candidate['candidate_id']}: image {len(references)} ({item.get('role') or item.get('label') or 'captured input'})")
        if pipeline == "character-assembly" and view != "FRONT":
            front_board = value["boards"].get("FRONT", {})
            front = front_board.get("candidates", {}).get(front_board.get("selected_id") or "")
            front_path = Path(str((front or {}).get("image_path") or "")).resolve()
            if front and front_path.is_file():
                references.append(front_path)
                reference_labels.append(f"Ranking comparison: selected FRONT image {len(references)}. Compare identity and head-to-body proportions while judging the requested {view} view.")
        prompt = criteria + "\nCandidate reference mapping:\n" + "\n".join(reference_labels) + "\nCandidate IDs in attachment order: " + ", ".join(ids)
        try:
            entries, model = review_images_with_luna(prompt=prompt, candidate_ids=ids, image_paths=images,
                reference_image_paths=references, paths=self.app.ai_proxy_service.ai_proxy_path_service,
                owner={"container_id": value["container_id"], "pipeline": pipeline, "view": view,
                       "luna_review_id": review_id})
            result = {"status": "COMPLETE", "active_id": "", "review_id": review_id,
                      "candidate_ids": ids, "image_hashes": dict(zip(ids, hashes)),
                      "entries": entries, "prompt": prompt, "model": model,
                      "recorded_at": datetime.now(timezone.utc).isoformat()}
        except Exception as exc:
            result = {**previous, "status": "FAILED", "active_id": "", "error": str(exc)}
        with file_lock(path.with_suffix(".lock")):
            latest = self.detail(character, phase, pipeline, costume)
            current = latest["boards"].get(view, {})
            if (current.get("luna_review", {}).get("active_id") == review_id
                    and current.get("luna_review", {}).get("status") == "RUNNING"):
                if result.get("status") == "COMPLETE":
                    current_ids = [cid for cid in current["slots"] if cid and current["candidates"].get(cid, {}).get("image_path")]
                    if set(current_ids) != set(ids) or any(cid not in current_ids or hashlib.sha256(Path(current["candidates"][cid]["image_path"]).read_bytes()).hexdigest() != result["image_hashes"].get(cid) for cid in ids):
                        result = {**previous, "status": "FAILED", "active_id": "", "error": "Board images changed while Luna Review was running."}
                current["luna_review"] = result
                current["revision"] += 1
                self.save(character, phase, pipeline, costume, latest, expected_revision=latest["revision"])
        return result

    def _run_luna_review_worker(self, character, phase, pipeline, costume, view, review_id):
        try:
            self.luna_review(character, phase, pipeline, costume, view, _review_id=review_id)
        finally:
            with _LUNA_REVIEW_ACTIVE_LOCK:
                _LUNA_REVIEW_ACTIVE.discard(review_id)

    def candidate_image(self, character: str, phase: str, pipeline: str, costume: str,
                        view: str, candidate_id: str) -> Path:
        value = self.detail(character, phase, pipeline, costume)
        board = value["boards"].get(view) or {}
        candidate = (board.get("candidates") or {}).get(candidate_id)
        if not candidate or candidate_id not in board.get("slots", []):
            raise CharacterAssetContainerError("Candidate is no longer in this view's board.")
        image = Path(str(candidate.get("image_path") or "")).resolve()
        if not image.is_relative_to(self.library_root) or not image.is_file():
            raise CharacterAssetContainerError("The candidate image is unavailable.")
        return image

    def _selected_reference(self, value: dict, view: str, role: str, *, published: bool) -> dict:
        board = value["boards"].get(view)
        candidate_id = (board or {}).get("selected_id")
        candidate = (board or {}).get("candidates", {}).get(candidate_id or "")
        if not candidate or not candidate.get("image_path"):
            raise CharacterAssetContainerError(f"Choose an available {view} image for {role} first.")
        if published and (not candidate.get("locked") or not candidate.get("inventory_asset_id")):
            raise CharacterAssetContainerError(f"Lock and publish the {role} {view} image first.")
        image = Path(candidate.get("locked_image_path") if published else candidate["image_path"]).resolve()
        if not image.is_relative_to(self.library_root) or not image.is_file():
            raise CharacterAssetContainerError(f"The selected {role} image is unavailable.")
        return {"role": role, "label": role.replace("_", " ").title(), "view": view, "path": str(image),
                "candidate_id": candidate_id, "render_mode": candidate.get("render_mode", "draft"),
                "sha256": hashlib.sha256(image.read_bytes()).hexdigest()}

    def resolve_references(self, character: str, phase: str, pipeline: str, costume: str,
                           view: str, *, render_mode: str = "draft",
                           costume_settings: dict | None = None) -> list[dict]:
        value = self.detail(character, phase, pipeline, costume)
        if view not in value["boards"]:
            raise CharacterAssetContainerError("Choose a view in this container.")
        if pipeline in {"body-reference", "head-image", "head-image-edit"}:
            if view == "FRONT":
                if pipeline in {"head-image", "head-image-edit"}:
                    sources = value["sources"]
                    if "phase_change" in sources:
                        source = sources.get("phase_change") or {}
                    else:
                        by_mode = sources.get("phase_change_by_mode") or {}
                        source = by_mode.get("final", by_mode.get("draft", {}))
                        if source is None:
                            source = by_mode.get("draft", {})
                    source_phase = str(source.get("phase") or "")
                    if source.get("kind") == "upload":
                        source_path = Path(str(source.get("path") or "")).resolve()
                        managed_root = self._path(value["scope"]).parent / "inputs" / "phase-change"
                        if (not source_path.is_relative_to(managed_root.resolve())
                                or not source_path.is_file()
                                or hashlib.sha256(source_path.read_bytes()).hexdigest() != source.get("sha256")):
                            raise CharacterAssetContainerError("The managed phase-change upload is unavailable. Upload it again.")
                        return [{"role": "head_image_source", "label": source.get("filename") or "Uploaded phase-change FRONT",
                            "path": str(source_path), "sha256": source["sha256"], "source_kind": "upload"}]
                    if source_phase and source_phase != phase:
                        source_pipeline = str(source.get("pipeline") or pipeline)
                        source_value = self.detail(character, source_phase, source_pipeline)
                        candidate_ref = self._selected_reference(source_value, "FRONT", "head_image_source", published=True)
                        return [candidate_ref]
                return []
            source_view = (value["sources"].get("views") or {}).get(view)
            if not source_view:
                if pipeline != "head-image-edit":
                    return []
                source_view = "FRONT"
            role = "body_reference_front_anchor" if pipeline == "body-reference" else "head_image_source"
            return [self._selected_reference(value, source_view, role, published=False)]
        if pipeline == "character-assembly":
            selected_head = str(value["sources"].get("head_pipeline") or "head-image")
            references = []
            for source_pipeline, role in (("body-reference", "body_reference"), (selected_head, "head_image")):
                source_value = self.detail(character, phase, source_pipeline)
                reference = self._selected_reference(source_value, view, role, published=True)
                reference.update(body_view=view, head_view=view)
                references.append(reference)
            return references
        if pipeline == "costume-dressing":
            assembly = self.detail(character, phase, "character-assembly")
            reference = self._selected_reference(assembly, view, "character_assembly", published=True)
            reference.update(body_view=view, head_view=view)
            if view == "FRONT":
                return [reference]
            from zet.services.costume_mode_conditioning_service import MODES
            saved = (value.get("sources", {}).get("dressing_settings") or {}).get(view) or {}
            settings = costume_settings or saved
            mode = settings.get("mode", "doll-dressing-no-ref")
            source_view = str(settings.get("costume_reference_view") or "").upper()
            if mode not in MODES:
                raise CharacterAssetContainerError("Choose a supported Costume Dressing mode.")
            if mode == "doll-dressing-no-ref":
                return [reference]
            if source_view not in value["boards"] or source_view == view:
                raise CharacterAssetContainerError("Choose a different view in this costume container as the costume reference.")
            dressed = self._selected_reference(value, source_view, "batch_view_reference", published=False)
            dressed.update(body_view=source_view, head_view=source_view,
                           prompt_role="edit_base" if mode == "rotate" else "subject_reference")
            if mode == "rotate":
                from zet.services.costume_rotation_service import rotation_instruction
                dressed.update(role="costume_rotation_source", source_view=source_view,
                               notes=rotation_instruction(source_view, view))
                reference.update(prompt_role="layout_reference", ignore=["fitment clothing", "bare feet", "rendering details"])
                return [dressed, reference]
            dressed.update(notes=f"Design reference from {source_view}; output must show {view}.")
            return [reference, dressed]
        raise CharacterAssetContainerError("This pipeline does not support image references.")

    def compile_prompt(self, character: str, phase: str, pipeline: str, costume: str,
                       view: str, *, apply_phase_change: bool = False,
                       assembly_style_mode: str = "", render_mode: str = "draft",
                       costume_settings: dict | None = None) -> dict:
        scope = self._scope(character, phase, pipeline, costume)
        references = self.resolve_references(character, phase, pipeline, scope["costume"], view,
                                             render_mode=render_mode, costume_settings=costume_settings)
        target = self._path(scope).parent / "prompt-previews" / quote(view, safe="-_.")
        from zet.services.character_container_prompt_service import CharacterContainerPromptService
        project_root = Path(__file__).resolve().parents[2]
        try:
            return CharacterContainerPromptService(self.app, project_root).compile(
                scope, view, target, references, apply_phase_change=apply_phase_change,
                assembly_style_mode=assembly_style_mode, render_mode=render_mode,
                costume_settings=costume_settings)
        except Exception as exc:
            raise CharacterAssetContainerError(f"Could not compile this view's prompt: {exc}") from exc

    def prepare_candidates(self, character: str, phase: str, pipeline: str, costume: str,
                           view: str, *, count: int, render_mode: str,
                           aspect_ratio: str, expected_revision: int,
                           apply_phase_change: bool = False,
                           assembly_style_mode: str = "", costume_settings: dict | None = None,
                           slot: int | None = None,
                           expected_candidate_id: str | None = None) -> dict:
        if type(count) is not int or not 1 <= count <= 8:
            raise CharacterAssetContainerError("Generate between one and eight images.")
        if render_mode not in {"draft", "final"}:
            raise CharacterAssetContainerError("Choose Draft or Final quality.")
        value = self.detail(character, phase, pipeline, costume)
        if value["revision"] != expected_revision:
            raise CharacterAssetContainerError("The container changed. Refresh before preparing renders.")
        board = value["boards"].get(view)
        if board is None:
            raise CharacterAssetContainerError("Choose a view in this container.")
        try:
            if slot is not None and (type(slot) is not int or not 1 <= slot <= 8
                    or board["slots"][slot - 1] != expected_candidate_id):
                raise ValueError("This slot changed. Refresh before replacing it.")
            positions = allocate_candidates(board["slots"], board["candidates"],
                board["selected_id"], count, slot, active={"SUBMITTING", "QUEUED", "RUNNING", "DISPATCHING"})
            compiled = self.compile_prompt(character, phase, pipeline, costume, view,
                apply_phase_change=apply_phase_change,
                assembly_style_mode=assembly_style_mode, render_mode=render_mode,
                costume_settings=costume_settings)
            preset_name = self._preset(pipeline, bool(compiled["reference_inputs"]),
                                       view, assembly_style_mode)
            preset_path = self.app.config.state_file(Path(__file__).resolve().parents[2], "Local_Render_Presets.json")
            from zet.services.local_render_backend_service import LocalRenderBackendService
            profile = LocalRenderBackendService(preset_path, config=self.app.config).preset(preset_name)
            if not profile:
                raise ValueError(f"Render profile is unavailable: {preset_name}")
            from zet.services.image_sizing_service import resolve_image_sizing
            sizing = resolve_image_sizing(self.app.config, render_mode, aspect_ratio)
            from zet.services.render_slot_service import frozen_input
            from zet.services.image_render_request import ImageRenderRequest
            from datetime import datetime, timezone
            import random
            candidates = []
            for slot in positions:
                candidate_id = uuid4().hex
                seed = random.SystemRandom().randrange(0, 2**63 - 1)
                candidate_root = self._path(value["scope"]).parent / "renders" / candidate_id
                frozen = frozen_input(candidate_root / "inputs", compiled["prompt"],
                    compiled["reference_inputs"], preset_name, render_sizing=sizing)
                settings = {key: profile[key] for key in (
                    "diffusion_model", "text_encoder", "vae", "steps", "cfg", "sampler_name",
                    "scheduler", "denoise", "disable_prompt_globals", "reference_max_pixels",
                    "reference_total_max_pixels") if key in profile}
                settings.update(sizing)
                settings.update(profile=preset_name, profile_snapshot=profile,
                    checkpoint=str(profile.get("diffusion_model") or self.app.config.comfyui_checkpoint or ""))
                request = ImageRenderRequest(self.app.universe_id,
                    f"{value['container_id']}:{view}", candidate_id, frozen["prompt"],
                    tuple(frozen["references"]), settings, seed,
                    {"pipeline": pipeline, "character": character, "phase": phase,
                     "costume": value["scope"]["costume"], "view": view,
                     "template_revision_id": compiled.get("template_revision_id", ""),
                     "apply_phase_change": bool(apply_phase_change),
                     "costume_settings": costume_settings or {},
                     "assembly_style_mode": assembly_style_mode}).to_dict()
                candidate = {"id": candidate_id, "candidate_id": candidate_id,
                    "slot": slot + 1, "render_mode": render_mode, "status": "PREPARED",
                    "prompt": frozen["prompt"], "render_request": request,
                    "image_path": "", "locked": False, "seed": seed,
                    "prepared_at": datetime.now(timezone.utc).isoformat(),
                    "template_revision_id": compiled.get("template_revision_id", "")}
                previous = board["slots"][slot]
                if previous:
                    self._remove_candidate(value, board, previous)
                board["slots"][slot] = candidate_id
                board["candidates"][candidate_id] = candidate
                candidates.append(candidate)
            board["revision"] += 1
            return {"container": self.save(character, phase, pipeline, costume, value,
                expected_revision=expected_revision), "candidates": candidates}
        except CharacterAssetContainerError:
            raise
        except Exception as exc:
            raise CharacterAssetContainerError(f"Could not prepare candidate renders: {exc}") from exc

    def _remove_candidate(self, value: dict, board: dict, candidate_id: str) -> None:
        candidate = remove(board, candidate_id)
        root = self._path(value["scope"]).parent
        pending = value.setdefault("cleanup_pending", [])
        pending.append(f"renders/{candidate_id}")
        image = Path(candidate.get("image_path") or "").resolve()
        if image.parent == root / "images" and image.stem == candidate_id:
            pending.append(str(image.relative_to(root)))

    def generate(self, character: str, phase: str, pipeline: str, costume: str, view: str, **options) -> dict:
        path = self._path(self._scope(character, phase, pipeline, costume))
        with file_lock(path.with_suffix(".lock")):
            prepared = self.prepare_candidates(character, phase, pipeline, costume, view, **options)
            current = prepared["container"]
            for candidate in prepared["candidates"]:
                try:
                    current = self._dispatch_candidate(character, phase, pipeline, costume, view,
                        candidate["candidate_id"], expected_revision=current["revision"])
                except CharacterAssetContainerError:
                    current = self.detail(character, phase, pipeline, costume)
            return current

    def candidate_input(self, character: str, phase: str, pipeline: str, costume: str,
                        view: str, candidate_id: str, index: int) -> Path:
        value = self.detail(character, phase, pipeline, costume)
        board = value["boards"].get(view, {})
        inputs = (board.get("candidates", {}).get(candidate_id, {}).get("render_request") or {}).get("inputs", [])
        if candidate_id not in board.get("slots", []) or not 1 <= index <= len(inputs):
            raise CharacterAssetContainerError("Captured input is unavailable.")
        root = (self._path(value["scope"]).parent / "renders" / candidate_id / "inputs").resolve()
        path = Path(inputs[index - 1]["path"]).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise CharacterAssetContainerError("Captured input is unavailable.")
        return path

    def dispatch_candidate(self, character: str, phase: str, pipeline: str, costume: str,
                           view: str, candidate_id: str, *, expected_revision: int) -> dict:
        path = self._path(self._scope(character, phase, pipeline, costume))
        with file_lock(path.with_suffix(".lock")):
            return self._dispatch_candidate(character, phase, pipeline, costume, view, candidate_id,
                                            expected_revision=expected_revision)

    def _dispatch_candidate(self, character: str, phase: str, pipeline: str, costume: str,
                           view: str, candidate_id: str, *, expected_revision: int,
                           upscale_request: dict | None = None) -> dict:
        value = self.detail(character, phase, pipeline, costume)
        board = value["boards"].get(view)
        candidate = (board or {}).get("candidates", {}).get(candidate_id)
        if value["revision"] != expected_revision:
            raise CharacterAssetContainerError("The container changed. Refresh before submitting this render.")
        if not candidate or candidate_id not in board["slots"]:
            raise CharacterAssetContainerError("Candidate is no longer in this view's board.")
        if candidate.get("status") != ("COMPLETE" if upscale_request else "PREPARED"):
            raise CharacterAssetContainerError("Only a prepared candidate can be submitted.")
        request = upscale_request or candidate.get("render_request") or {}
        if (request.get("universe_id") != value["scope"]["universe_id"]
                or request.get("target_id") != f"{value['container_id']}:{view}"
                or request.get("candidate_id") != candidate_id):
            raise CharacterAssetContainerError("The frozen render request does not belong to this candidate.")
        from zet.services.render_slot_service import verify_input
        frozen = {"references": request.get("inputs", [])}
        try:
            verify_input(frozen)
        except (ValueError, OSError) as exc:
            raise CharacterAssetContainerError(str(exc)) from exc
        attempt_id = uuid4().hex
        if upscale_request:
            candidate["upscale_request"] = upscale_request
            candidate.update(ask_id="", output_path="", error="")
        if not upscale_request:
            record_render_start(candidate)
        candidate.update(status="SUBMITTING", attempt_id=attempt_id, reserved_ask_id=attempt_id,
                         attempt_number=int(candidate.get("attempt_number") or 0) + 1)
        board["revision"] += 1
        self.save(character, phase, pipeline, costume, value, expected_revision=expected_revision)
        candidate_root = self._path(value["scope"]).parent / "renders" / candidate_id / "attempts" / attempt_id
        prompt_path = candidate_root / "prompt.md"
        owner = self._render_owner(value, candidate_id, view, attempt_id)
        owner["slot"] = candidate["slot"]
        settings = request["settings"]
        sizing = {key: settings[key] for key in
            ("render_mode", "aspect_ratio", "target_pixels", "width", "height") if key in settings}
        manifest = {"ask_id": f"container_{value['container_id']}_{candidate_id}_{attempt_id}",
                    "character": character, "phase": phase, "pipeline": pipeline,
                    "transport_job_id": attempt_id, "pipeline_stage": "ASSET_CONTAINER_RENDER", "render_sizing": sizing,
                    "image_production": owner,
                    "ai_owner": {"candidate_id": candidate_id, "view": view,
                                 "character": character, "phase": phase,
                                 "costume": value["scope"]["costume"]}}
        try:
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            saved_prompt = candidate.get("prompt", "") if upscale_request else request["prompt"]
            prompt_path.write_text(saved_prompt, encoding="utf-8", newline="")
            staged = self.image_production.submit(request, manifest=manifest,
                prompt_path=prompt_path, output_directory=candidate_root,
                consumer="zet-character-containers")
            current = self.detail(character, phase, pipeline, costume)
            live = current["boards"][view]["candidates"].get(candidate_id)
            if not live or live.get("attempt_id") != attempt_id:
                raise CharacterAssetContainerError("This render attempt was superseded before dispatch completed.")
            live.update(status="QUEUED", ask_id=staged["ask_id"], output_path=staged["output_path"], error="")
            current["boards"][view]["revision"] += 1
            return self.save(character, phase, pipeline, costume, current,
                             expected_revision=current["revision"])
        except Exception as exc:
            current = self.detail(character, phase, pipeline, costume)
            live = current["boards"][view]["candidates"].get(candidate_id)
            if (live and live.get("attempt_id") == attempt_id
                    and not self.image_production.find_attempt(manifest["ask_id"], owner, attempt_id)):
                updates = {"status": "FAILED", "error": str(exc)}
                self._settle_upscale(current, live, updates)
                live.update(updates)
                current["boards"][view]["revision"] += 1
                self.save(character, phase, pipeline, costume, current,
                          expected_revision=current["revision"])
            if isinstance(exc, CharacterAssetContainerError):
                raise
            raise CharacterAssetContainerError(f"Could not submit candidate render: {exc}") from exc

    def retry_candidate(self, character: str, phase: str, pipeline: str, costume: str,
                        view: str, candidate_id: str, *, expected_revision: int) -> dict:
        value = self.detail(character, phase, pipeline, costume)
        board = value["boards"].get(view)
        candidate = (board or {}).get("candidates", {}).get(candidate_id)
        if value["revision"] != expected_revision:
            raise CharacterAssetContainerError("The container changed. Refresh before retrying this render.")
        if not candidate or candidate_id not in board["slots"]:
            raise CharacterAssetContainerError("Candidate is no longer in this view's board.")
        try:
            retry_request(board, candidate_id)
        except ValueError as exc:
            raise CharacterAssetContainerError(str(exc)) from exc
        candidate.update(status="PREPARED", error="", ask_id="", output_path="")
        board["revision"] += 1
        saved = self.save(character, phase, pipeline, costume, value,
                          expected_revision=expected_revision)
        return self.dispatch_candidate(character, phase, pipeline, costume, view,
            candidate_id, expected_revision=saved["revision"])

    def refresh_view(self, character: str, phase: str, pipeline: str, costume: str, view: str) -> dict:
        path = self._path(self._scope(character, phase, pipeline, costume))
        with file_lock(path.with_suffix(".lock")):
            return self._refresh_view(character, phase, pipeline, costume, view)

    def _refresh_view(self, character: str, phase: str, pipeline: str, costume: str,
                     view: str) -> dict:
        value = self.detail(character, phase, pipeline, costume)
        if view not in value["boards"]:
            raise CharacterAssetContainerError("Choose a view in this container.")
        board = value["boards"][view]
        changed = False
        for candidate_id in board["slots"]:
            if not candidate_id:
                continue
            candidate = board["candidates"][candidate_id]
            if candidate["status"] not in {"SUBMITTING", "QUEUED", "RUNNING"}:
                continue
            attempt_id = candidate.get("attempt_id")
            owner = self._render_owner(value, candidate_id, view, attempt_id)
            if candidate.get("reserved_ask_id"):
                owner["slot"] = candidate["slot"]
            root = self._path(value["scope"]).parent / "renders" / candidate_id / "attempts" / str(attempt_id)
            updates = self.image_production.reconcile(candidate, owner, root,
                f"container_{value['container_id']}_{candidate_id}_{attempt_id}")
            previous_image_path = candidate.get("image_path")
            if (self._settle_upscale(value, candidate, updates)
                    or any(candidate.get(key) != item for key, item in updates.items())):
                candidate.update(updates)
                if candidate.get("status") == "COMPLETE":
                    record_render_completion(candidate)
                    if candidate.get("image_path") != previous_image_path and board.get("luna_review", {}).get("status") in {"COMPLETE", "RUNNING"}:
                        board["luna_review"]["status"] = "OBSOLETE"
                        board["luna_review"]["active_id"] = ""
                changed = True
        if changed:
            board["revision"] += 1
            self.save(character, phase, pipeline, costume, value, expected_revision=value["revision"])
        return self.progress(character, phase, pipeline, costume, view)

    def _settle_upscale(self, value: dict, candidate: dict, updates: dict) -> bool:
        request = candidate.get("upscale_request")
        if not request or updates["status"] not in {"COMPLETE", "FAILED"}:
            return False
        from PIL import Image

        root = self._path(value["scope"]).parent.resolve()
        pending = value.setdefault("cleanup_pending", [])
        if updates["status"] == "COMPLETE":
            try:
                with Image.open(updates["image_path"]) as image:
                    verify_upscale_output(image, request)
            except (OSError, ValueError) as exc:
                updates.update(status="FAILED", error=str(exc))
                rejected = Path(updates.pop("image_path")).resolve()
                if rejected.is_relative_to(root):
                    pending.append(str(rejected.relative_to(root)))
            else:
                updates["render_mode"] = "final"
                for key in ("locked_image_path", "inventory_asset_id", "image_sha256"):
                    candidate.pop(key, None)
                old_image = Path(candidate["image_path"]).resolve()
                candidate_id = request["candidate_id"]
                if (old_image.is_relative_to(root / "renders" / candidate_id / "attempts")
                        or (old_image.parent == root / "images" and old_image.stem == candidate_id)):
                    pending.append(str(old_image.relative_to(root)))
        pending.append(str(Path(request["inputs"][0]["path"]).parent.relative_to(root)))
        candidate.pop("upscale_request")
        if updates["status"] == "FAILED":
            updates.update(status="COMPLETE", error=f"Upscale failed. {updates['error']}")
        return True

    @staticmethod
    def _render_owner(value: dict, candidate_id: str, view: str, attempt_id: str) -> dict:
        scope = value["scope"]
        return {"consumer": "zet-character-containers", "universe_id": scope["universe_id"],
                "target_id": f"{value['container_id']}:{view}", "candidate_id": candidate_id,
                "attempt_id": attempt_id, "character": scope["character"], "phase": scope["phase"],
                "pipeline": scope["pipeline"], "costume": scope["costume"], "view": view}

    @staticmethod
    def _preset(pipeline: str, has_references: bool, view: str, assembly_style_mode: str) -> str:
        if pipeline == "body-reference":
            return "comfyui-qwen-body-reference-edit" if has_references else "comfyui-qwen-body-reference-text"
        if pipeline == "head-image":
            return "comfyui-qwen-head-image-edit" if has_references else "comfyui-qwen-head-image-text"
        if pipeline == "head-image-edit":
            return ("comfyui-qwen-head-image-edit-v1" if has_references
                    else "comfyui-qwen-head-image-edit-front-v1") if view == "FRONT" else "comfyui-qwen-head-image-edit-v1"
        return "comfyui-qwen-local-character-edit"

    @staticmethod
    def _empty(scope: dict) -> dict:
        return {"schema_version": 1, "container_id": str(uuid4()), "scope": scope,
                "revision": 0, "sources": {}, "boards": {
                    view: {"slots": [None] * 8, "candidates": {}, "selected_id": None,
                           "revision": 0}
                    for view in scope["views"]}}

    def save(self, character: str, phase: str, pipeline: str, costume: str, value: dict,
             *, expected_revision: int) -> dict:
        scope = self._scope(character, phase, pipeline, costume)
        path = self._path(scope)
        with file_lock(path.with_suffix(".lock")):
            current = self.detail(character, phase, pipeline, costume)
            if current["revision"] != expected_revision:
                raise CharacterAssetContainerError("The container changed. Refresh before saving.")
            if value.get("container_id") != current["container_id"] or value.get("scope") != scope:
                raise CharacterAssetContainerError("The container identity cannot be changed.")
            value["revision"] = expected_revision + 1
            write_json_atomic(path, value)
            return copy.deepcopy(value)

    def save_source(self, character: str, phase: str, pipeline: str, costume: str,
                    source_name: str, source: dict, *, expected_revision: int,
                    render_mode: str = "") -> dict:
        if source_name not in {"phase_change", "phase_change_by_mode", "head_pipeline", "views", "dressing_settings"}:
            raise CharacterAssetContainerError("Choose a supported container source setting.")
        value = self.detail(character, phase, pipeline, costume)
        if source_name == "phase_change_by_mode":
            raise CharacterAssetContainerError("Phase-change sources are shared across qualities. Refresh the container and choose one source.")
        if source_name == "head_pipeline":
            if pipeline != "character-assembly" or source not in {"head-image", "head-image-edit"}:
                raise CharacterAssetContainerError("Choose Head Image Construct or Head Image Edit for Assembly.")
        elif not isinstance(source, dict):
            raise CharacterAssetContainerError("Reference settings must be an object.")
        if isinstance(source, dict):
            source = copy.deepcopy(source)
        if source_name in {"phase_change", "phase_change_by_mode"} and source:
            if pipeline not in {"head-image", "head-image-edit"}:
                raise CharacterAssetContainerError("Phase-change sources belong to a Head container.")
            if source.get("kind") == "upload":
                source_path = Path(str(source.get("path") or "")).resolve()
                managed_root = self._path(value["scope"]).parent / "inputs" / "phase-change"
                if not source_path.is_relative_to(managed_root.resolve()) or not source_path.is_file():
                    raise CharacterAssetContainerError("The phase-change upload must be a verified image managed by this container.")
                digest = hashlib.sha256(source_path.read_bytes()).hexdigest()
                if digest != str(source.get("sha256") or ""):
                    raise CharacterAssetContainerError("The phase-change upload must be a verified image managed by this container.")
            else:
                source_phase = str(source.get("phase") or "").strip()
                source_pipeline = str(source.get("pipeline") or "")
                if not source_phase or source_phase == phase or source_pipeline not in {"head-image", "head-image-edit"}:
                    raise CharacterAssetContainerError("Choose a Head FRONT from another phase of this character.")
                source = {"phase": source_phase, "pipeline": source_pipeline}
        if source_name == "dressing_settings":
            if pipeline != "costume-dressing" or not isinstance(source, dict):
                raise CharacterAssetContainerError("Dressing settings belong to a Costume Dressing container.")
            view = str(source.get("view") or "").upper()
            mode = source.get("mode")
            source_view = str(source.get("costume_reference_view") or "").upper()
            from zet.services.costume_mode_conditioning_service import MODES
            if view == "FRONT" or view not in value["boards"] or mode not in MODES:
                raise CharacterAssetContainerError("Choose a supported Costume Dressing view and mode.")
            if mode != "doll-dressing-no-ref" and (source_view not in value["boards"] or source_view == view):
                raise CharacterAssetContainerError("Choose a different view in this costume container as the costume reference.")
            value["sources"].setdefault("dressing_settings", {})[view] = {
                "mode": mode,
                "costume_reference_view": source_view if mode != "doll-dressing-no-ref" else "",
            }
            return self.save(character, phase, pipeline, costume, value,
                             expected_revision=expected_revision)
        if source_name == "views":
            allowed = set(value["boards"])
            if not isinstance(source, dict) or any(view not in allowed or source_view not in (allowed | {""}) or view == source_view
                                                   for view, source_view in source.items()):
                raise CharacterAssetContainerError("Choose a different view in this container for each reference.")
        value["sources"][source_name] = copy.deepcopy(source)
        if source_name == "phase_change":
            value["sources"].pop("phase_change_by_mode", None)
        return self.save(character, phase, pipeline, costume, value,
                         expected_revision=expected_revision)

    def upload_phase_source(self, character: str, phase: str, pipeline: str, costume: str,
                            filename: str, contents: bytes,
                            *, expected_revision: int) -> dict:
        if pipeline not in {"head-image", "head-image-edit"}:
            raise CharacterAssetContainerError("Managed phase-change uploads belong to a Head container.")
        if not contents or len(contents) > 32 * 1024 * 1024:
            raise CharacterAssetContainerError("The source must be a nonempty image under 32 MB.")
        suffix = Path(filename or "").suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg", ".webp"}:
            raise CharacterAssetContainerError("The source must be a PNG, JPEG, or WebP image.")
        value = self.detail(character, phase, pipeline, costume)
        if value["revision"] != expected_revision:
            raise CharacterAssetContainerError("The container changed. Refresh before uploading a source.")
        from PIL import Image
        try:
            import io
            with Image.open(io.BytesIO(contents)) as image:
                image.verify()
        except Exception as exc:
            raise CharacterAssetContainerError("The uploaded phase-change source is not a valid image.") from exc
        digest = hashlib.sha256(contents).hexdigest()
        input_root = self._path(value["scope"]).parent / "inputs" / "phase-change"
        input_root.mkdir(parents=True, exist_ok=True)
        destination = input_root / f"{digest}{suffix}"
        if destination.exists():
            if hashlib.sha256(destination.read_bytes()).hexdigest() != digest:
                raise CharacterAssetContainerError("A managed phase-change file conflicts with this upload.")
        else:
            temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
            try:
                temporary.write_bytes(contents)
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)
        clean_name = Path(filename or "phase-change-source").name
        return self.save_source(character, phase, pipeline, costume, "phase_change",
            {"kind": "upload", "path": str(destination), "sha256": digest, "filename": clean_name},
            expected_revision=expected_revision)

    def board_action(self, character: str, phase: str, pipeline: str, costume: str,
                     view: str, candidate_id: str, action: str, **options) -> dict:
        path = self._path(self._scope(character, phase, pipeline, costume))
        with file_lock(path.with_suffix(".lock")):
            return self._board_action(character, phase, pipeline, costume, view, candidate_id, action, **options)

    @staticmethod
    def _bulk_clear_preview(value: dict, view: str, mode: str) -> dict:
        import json
        board = value["boards"].get(view)
        if board is None:
            raise CharacterAssetContainerError("Choose a view in this container.")
        keep = set() if mode == "drafts" else ({board.get("selected_id")} |
            {cid for cid, item in board["candidates"].items() if item.get("locked")})
        candidates = [{"candidate_id": cid, "slot": index + 1}
                      for index, cid in enumerate(board["slots"]) if cid and cid not in keep
                      and (mode != "drafts" or board["candidates"][cid].get("render_mode", "draft") == "draft")]
        active = {"SUBMITTING", "QUEUED", "RUNNING", "DISPATCHING"}
        if any(board["candidates"][item["candidate_id"]].get("status") in active for item in candidates):
            raise CharacterAssetContainerError("Wait for active renders to finish before deleting these candidates.")
        effects = []
        for item in candidates:
            candidate_id = item["candidate_id"]
            if board.get("selected_id") == candidate_id:
                effects.append({"id": f"select:{candidate_id}", "candidate_id": candidate_id,
                                "label": f"Clear selected candidate in slot {item['slot']}"})
            if board["candidates"][candidate_id].get("locked"):
                effects.append({"id": f"lock:{candidate_id}", "candidate_id": candidate_id,
                                "label": f"Clear locked candidate in slot {item['slot']}"})
        token = hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()
        return {"candidates": candidates, "protected_effects": effects, "confirmation_token": token,
                "revision": value["revision"]}

    def preview_delete_non_selected(self, character: str, phase: str, pipeline: str,
                                    costume: str, view: str) -> dict:
        value = self.detail(character, phase, pipeline, costume)
        return self._bulk_clear_preview(value, view, "non-selected")

    def preview_delete_drafts(self, character: str, phase: str, pipeline: str,
                              costume: str, view: str) -> dict:
        value = self.detail(character, phase, pipeline, costume)
        return self._bulk_clear_preview(value, view, "drafts")

    def delete_candidates(self, character: str, phase: str, pipeline: str,
                          costume: str, view: str, mode: str, data: dict) -> dict:
        path = self._path(self._scope(character, phase, pipeline, costume))
        with file_lock(path.with_suffix(".lock")):
            value = self.detail(character, phase, pipeline, costume)
            preview = self._bulk_clear_preview(value, view, mode)
            if (data.get("confirmation_token") != preview["confirmation_token"] or
                    data.get("expected_revision") != preview["revision"]):
                raise CharacterAssetContainerError("The board changed. Refresh and review the deletion before confirming.")
            approved = data.get("approved_effects")
            if not isinstance(approved, list) or set(approved) != {effect["id"] for effect in preview["protected_effects"]}:
                raise CharacterAssetContainerError("Approve each selected or locked candidate affected by deletion.")
            board = value["boards"][view]
            for item in preview["candidates"]:
                self._remove_candidate(value, board, item["candidate_id"])
            if preview["candidates"]:
                board["revision"] += 1
                value = self.save(character, phase, pipeline, costume, value,
                                  expected_revision=preview["revision"])
            return self.detail(character, phase, pipeline, costume)

    def delete_non_selected(self, character: str, phase: str, pipeline: str,
                            costume: str, view: str, data: dict) -> dict:
        return self.delete_candidates(character, phase, pipeline, costume, view, "non-selected", data)

    def delete_drafts(self, character: str, phase: str, pipeline: str,
                      costume: str, view: str, data: dict) -> dict:
        return self.delete_candidates(character, phase, pipeline, costume, view, "drafts", data)

    def _board_action(self, character: str, phase: str, pipeline: str, costume: str,
                     view: str, candidate_id: str, action: str, *, expected_revision: int,
                     expected_candidate_id: str = "", confirm_selected: bool = False,
                     confirm_locked: bool = False) -> dict:
        value = self.detail(character, phase, pipeline, costume)
        if value["revision"] != expected_revision:
            raise CharacterAssetContainerError("The container changed. Refresh before acting.")
        board = value["boards"].get(view)
        if board is None:
            raise CharacterAssetContainerError("Choose a view in this container.")
        candidate = board["candidates"].get(candidate_id)
        if candidate is None or candidate_id not in board["slots"]:
            raise CharacterAssetContainerError("Candidate is no longer in this view's board.")
        if action == "upscale":
            try:
                source = self.candidate_image(character, phase, pipeline, costume, view, candidate_id)
                root = self._path(value["scope"]).parent.resolve()
                directory = root / "renders" / candidate_id / f"upscale-{uuid4().hex}"
                request = draft_upscale_request(self.app.config, f"{value['container_id']}:{view}",
                                                candidate_id, candidate, source, directory)
            except (ValueError, OSError) as exc:
                raise CharacterAssetContainerError(str(exc)) from exc
            return self._dispatch_candidate(character, phase, pipeline, costume, view, candidate_id,
                expected_revision=expected_revision, upscale_request=request)
        if candidate.get("upscale_request") and action in {"select", "lock"}:
            raise CharacterAssetContainerError("Wait for the upscale to finish.")
        if action == "clear":
            if expected_candidate_id != candidate_id:
                raise CharacterAssetContainerError("This slot changed. Refresh and review it before clearing.")
            if candidate.get("status") in {"SUBMITTING", "QUEUED", "RUNNING", "DISPATCHING"}:
                raise CharacterAssetContainerError("Wait for this candidate's render to settle before clearing it.")
            if board.get("selected_id") == candidate_id and not confirm_selected:
                raise CharacterAssetContainerError("Confirm clearing the selected candidate.")
            if candidate.get("locked") and not confirm_locked:
                raise CharacterAssetContainerError("Confirm clearing the locked candidate.")
            if candidate.get("locked"):
                raise CharacterAssetContainerError("Unlock the candidate before clearing its slot.")
            self._remove_candidate(value, board, candidate_id)
            board["revision"] += 1
            self.save(character, phase, pipeline, costume, value, expected_revision=expected_revision)
            return self.detail(character, phase, pipeline, costume)
        if action == "select":
            if not candidate.get("image_path") or not Path(candidate["image_path"]).is_file():
                raise CharacterAssetContainerError("The candidate image is unavailable.")
            try:
                select_candidate(board, candidate_id)
            except ValueError as exc:
                raise CharacterAssetContainerError(str(exc)) from exc
        elif action == "lock":
            if not candidate.get("image_path") or not Path(candidate["image_path"]).is_file():
                raise CharacterAssetContainerError("The candidate image is unavailable.")
            previous = copy.deepcopy(value)
            try:
                lock_candidate(board, candidate_id)
            except ValueError as exc:
                raise CharacterAssetContainerError(str(exc)) from exc
            image = Path(candidate["image_path"]).resolve()
            if not image.is_relative_to(self.library_root):
                raise CharacterAssetContainerError("Candidate image is outside this universe's library.")
            digest = hashlib.sha256(image.read_bytes()).hexdigest()
            operation_id = uuid4().hex
            board["revision"] += 1
            journal_path = self._path(value["scope"]).parent / "publications" / f"{operation_id}.json"

            def commit_board(published):
                asset = published[0]
                candidate.update(locked_image_path=asset["image_path"],
                                inventory_asset_id=asset["asset_id"],
                                image_sha256=digest)
                next_value = copy.deepcopy(value)
                next_value["revision"] = expected_revision + 1
                pending_value = copy.deepcopy(next_value)
                pending_value["_pending_publication_id"] = operation_id
                write_json_atomic(journal_path, {"operation_id": operation_id,
                    "container_path": str(self._path(value["scope"])), "scope": value["scope"],
                    "previous": previous, "next": next_value})
                self._publishing_board = True
                try:
                    self.save(character, phase, pipeline, costume, pending_value,
                              expected_revision=expected_revision)
                finally:
                    self._publishing_board = False

            try:
                self.app.entity_library_service.register_locked_pipeline_images([{
                    "source": str(image), "checksum": digest, "pipeline": pipeline,
                    "character": character, "phase": phase, "costume": value["scope"]["costume"],
                    "view": view, "candidate_id": candidate_id,
                    "prompt": candidate.get("prompt", ""),
                    "label": " · ".join(part for part in
                        (character, phase, costume, pipeline.replace("-", " ").title(), view.replace("_", " ").title()) if part),
                }], operation_id=operation_id, before_commit=commit_board)
                self._recover_publications(self._path(value["scope"]), value["scope"])
            except Exception as exc:
                raise CharacterAssetContainerError(f"Could not publish the locked candidate: {exc}") from exc
            return self.detail(character, phase, pipeline, costume)
        elif action == "unlock":
            locked_id = next((item for item in board["slots"] if item and board["candidates"][item].get("locked")), None)
            if locked_id != candidate_id or board.get("selected_id") != candidate_id:
                raise CharacterAssetContainerError("Unlock the current locked candidate on this board.")
            unlock_candidate(board, candidate_id)
        else:
            raise CharacterAssetContainerError("Choose select, lock, or unlock.")
        board["revision"] += 1
        return self.save(character, phase, pipeline, costume, value,
                         expected_revision=expected_revision)
