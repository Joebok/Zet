"""Character Asset Container reads and revision-checked source settings."""
from pathlib import Path
from fastapi import APIRouter, Body, HTTPException, Query, Request
from fastapi.responses import FileResponse
from zet.web.captured_image_response import captured_image_response

from zet.services.character_asset_container_service import (
    CharacterAssetContainerError, CharacterAssetContainerService,
)
from zet.services.character_container_template_service import (
    CharacterContainerTemplateError, CharacterContainerTemplateService,
)


def create_character_asset_container_router(resolve_app, image_generation_provider):
    router = APIRouter()

    def service(universe_id: str):
        app = resolve_app()
        if universe_id and universe_id != app.universe_id:
            raise HTTPException(status_code=404, detail="The requested universe is not active.")
        return CharacterAssetContainerService(app)

    def template_service(universe_id: str):
        app = resolve_app()
        if universe_id and universe_id != app.universe_id:
            raise HTTPException(status_code=404, detail="The requested universe is not active.")
        return CharacterContainerTemplateService(app, Path(__file__).resolve().parents[2])

    @router.get("/api/character-containers/{pipeline}")
    def detail(pipeline: str, character: str = Query(...), phase: str = Query(...),
               costume: str = Query(""), universe_id: str = Query("")):
        try:
            return service(universe_id).detail(character, phase, pipeline, costume)
        except CharacterAssetContainerError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/api/character-containers/{pipeline}/template")
    def governing_template(pipeline: str, character: str = Query(...), phase: str = Query(...),
                          costume: str = Query(""), universe_id: str = Query("")):
        try:
            path = service(universe_id).governing_template(character, phase, pipeline, costume)
            return {"source_path": str(path), "character": character, "phase": phase}
        except CharacterAssetContainerError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/api/character-containers/{pipeline}/template-sources")
    def template_sources(pipeline: str, character: str = Query(...), phase: str = Query(...),
                         costume: str = Query(""), universe_id: str = Query("")):
        try:
            instance = template_service(universe_id)
            scope = instance.containers._scope(character, phase, pipeline, costume)
            return {"sources": [{key: value for key, value in source.items() if key not in {"text", "sha256"}}
                                for source in instance._sources(scope)]}
        except (CharacterContainerTemplateError, CharacterAssetContainerError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/api/character-containers/{pipeline}/template-reviews")
    def start_template_review(pipeline: str, payload: dict = Body(...), character: str = Query(...),
                              phase: str = Query(...), costume: str = Query(""), universe_id: str = Query("")):
        try:
            return template_service(universe_id).start_review(character, phase, pipeline, costume, payload)
        except (CharacterContainerTemplateError, CharacterAssetContainerError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.put("/api/character-containers/{pipeline}/template-proposals/{proposal_id}/decisions")
    def decide_template_review(pipeline: str, proposal_id: str, payload: dict = Body(...),
                               character: str = Query(...), phase: str = Query(...),
                               costume: str = Query(""), universe_id: str = Query("")):
        try:
            return template_service(universe_id).decide(character, phase, pipeline, costume,
                proposal_id, payload.get("selected_ids"))
        except (CharacterContainerTemplateError, CharacterAssetContainerError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/api/character-containers/{pipeline}/template-proposals")
    def propose_template(pipeline: str, payload: dict = Body(...),
                         character: str = Query(...), phase: str = Query(...),
                         costume: str = Query(""), universe_id: str = Query("")):
        try:
            return template_service(universe_id).propose(character, phase, pipeline, costume,
                str(payload.get("view") or ""), str(payload.get("candidate_id") or ""),
                direction=str(payload.get("direction") or ""), model=str(payload.get("model") or ""),
                expected_revision=payload.get("expected_revision", -1))
        except (CharacterContainerTemplateError, CharacterAssetContainerError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get("/api/character-containers/{pipeline}/template-proposals")
    def latest_template_proposal(pipeline: str, character: str = Query(...),
                         phase: str = Query(...), costume: str = Query(""),
                         universe_id: str = Query("")):
        try:
            return template_service(universe_id).latest(character, phase, pipeline, costume)
        except (CharacterContainerTemplateError, CharacterAssetContainerError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.get("/api/character-containers/{pipeline}/template-proposals/{proposal_id}")
    def template_proposal(pipeline: str, proposal_id: str, character: str = Query(...),
                          phase: str = Query(...), costume: str = Query(""),
                          universe_id: str = Query("")):
        try:
            return template_service(universe_id).detail(character, phase, pipeline, costume, proposal_id)
        except (CharacterContainerTemplateError, CharacterAssetContainerError) as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/api/character-containers/{pipeline}/template-proposals/{proposal_id}/accept")
    def accept_template_proposal(pipeline: str, proposal_id: str, payload: dict = Body(...),
                          character: str = Query(...), phase: str = Query(...),
                          costume: str = Query(""), universe_id: str = Query("")):
        try:
            instance = template_service(universe_id)
            record = instance.detail(character, phase, pipeline, costume, proposal_id)
            if record.get("schema_version") == 2:
                return instance.accept_review(character, phase, pipeline, costume,
                    proposal_id, confirm=payload.get("confirm") is True)
            return instance.accept(character, phase, pipeline, costume, proposal_id,
                confirm=payload.get("confirm") is True)
        except (CharacterContainerTemplateError, CharacterAssetContainerError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get("/api/character-containers/{pipeline}/views/{view}/progress")
    def progress(pipeline: str, view: str, character: str = Query(...),
                 phase: str = Query(...), costume: str = Query(""),
                 universe_id: str = Query("")):
        try:
            return service(universe_id).refresh_view(character, phase, pipeline, costume, view)
        except CharacterAssetContainerError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/api/character-containers/{pipeline}/views/{view}/luna-review")
    def luna_review(pipeline: str, view: str, character: str = Query(...), phase: str = Query(...),
                    costume: str = Query(""), universe_id: str = Query("")):
        try:
            return service(universe_id).luna_review(character, phase, pipeline, costume, view)
        except (CharacterAssetContainerError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/api/character-containers/{pipeline}/views/{view}/prompt")
    def compile_prompt(pipeline: str, view: str, payload: dict = Body(default={}),
                       character: str = Query(...), phase: str = Query(...),
                       costume: str = Query(""), universe_id: str = Query("")):
        try:
            return service(universe_id).compile_prompt(character, phase, pipeline, costume,
                view, apply_phase_change=payload.get("apply_phase_change") is True,
                assembly_style_mode=str(payload.get("assembly_style_mode") or ""),
                render_mode=str(payload.get("render_mode") or "draft"),
                costume_settings=payload.get("costume_settings"))
        except CharacterAssetContainerError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/api/character-containers/{pipeline}/views/{view}/image-generation-stage")
    def stage_image_generation(pipeline: str, view: str, payload: dict = Body(...),
                               character: str = Query(...), phase: str = Query(...),
                               costume: str = Query(""), universe_id: str = Query("")):
        from zet.services.image_generator_staging_service import ImageGeneratorStagingService

        try:
            return ImageGeneratorStagingService(service(universe_id), image_generation_provider()).stage_container(
                character, phase, pipeline, costume, view, payload)
        except (CharacterAssetContainerError, ValueError, OSError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/api/character-containers/{pipeline}/views/{view}/candidates")
    def prepare_candidates(pipeline: str, view: str, payload: dict = Body(...),
                          character: str = Query(...), phase: str = Query(...),
                          costume: str = Query(""), universe_id: str = Query("")):
        try:
            return service(universe_id).prepare_candidates(character, phase, pipeline, costume,
                view, count=payload.get("count", 1),
                render_mode=str(payload.get("render_mode") or "draft"),
                aspect_ratio=str(payload.get("aspect_ratio") or "2:3"),
                expected_revision=payload.get("expected_revision", -1),
                apply_phase_change=payload.get("apply_phase_change") is True,
                costume_settings=payload.get("costume_settings"),
                assembly_style_mode=str(payload.get("assembly_style_mode") or ""))
        except CharacterAssetContainerError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/api/character-containers/{pipeline}/views/{view}/generate")
    def generate(pipeline: str, view: str, payload: dict = Body(...),
                 character: str = Query(...), phase: str = Query(...),
                 costume: str = Query(""), universe_id: str = Query("")):
        try:
            return service(universe_id).generate(character, phase, pipeline, costume, view,
                count=payload.get("count", 1), render_mode=payload.get("render_mode", "draft"),
                aspect_ratio=payload.get("aspect_ratio", "2:3"),
                expected_revision=payload.get("expected_revision", -1),
                apply_phase_change=payload.get("apply_phase_change") is True,
                costume_settings=payload.get("costume_settings"),
                slot=payload.get("slot"), expected_candidate_id=payload.get("expected_candidate_id"))
        except CharacterAssetContainerError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get("/api/character-containers/{pipeline}/views/{view}/candidates/{candidate_id}/inputs/{index}")
    def candidate_input(pipeline: str, view: str, candidate_id: str, index: int,
                        character: str = Query(...), phase: str = Query(...),
                        costume: str = Query(""), universe_id: str = Query("")):
        try:
            path = service(universe_id).candidate_input(
                character, phase, pipeline, costume, view, candidate_id, index)
        except CharacterAssetContainerError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return captured_image_response(path)

    @router.post("/api/character-containers/{pipeline}/views/{view}/candidates/{candidate_id}/submit")
    def dispatch_candidate(pipeline: str, view: str, candidate_id: str,
                           payload: dict = Body(...), character: str = Query(...),
                           phase: str = Query(...), costume: str = Query(""),
                           universe_id: str = Query("")):
        try:
            return service(universe_id).dispatch_candidate(character, phase, pipeline, costume,
                view, candidate_id, expected_revision=payload.get("expected_revision", -1))
        except CharacterAssetContainerError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/api/character-containers/{pipeline}/views/{view}/candidates/{candidate_id}/retry")
    def retry_candidate(pipeline: str, view: str, candidate_id: str,
                       payload: dict = Body(...), character: str = Query(...),
                       phase: str = Query(...), costume: str = Query(""),
                       universe_id: str = Query("")):
        try:
            return service(universe_id).retry_candidate(character, phase, pipeline, costume,
                view, candidate_id, expected_revision=payload.get("expected_revision", -1))
        except CharacterAssetContainerError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.put("/api/character-containers/{pipeline}/sources/phase-change-upload")
    async def upload_phase_source(pipeline: str, request: Request,
                    character: str = Query(...), phase: str = Query(...),
                    costume: str = Query(""), universe_id: str = Query(""),
                    filename: str = Query(...),
                    expected_revision: int = Query(...)):
        try:
            if "render_mode" in request.query_params:
                raise HTTPException(status_code=409, detail="Phase-change uploads are shared across qualities. Refresh the container.")
            chunks = bytearray()
            async for chunk in request.stream():
                if len(chunks) + len(chunk) > 32 * 1024 * 1024:
                    raise HTTPException(status_code=413, detail="The source must be under 32 MB.")
                chunks.extend(chunk)
            return service(universe_id).upload_phase_source(character, phase, pipeline,
                costume, filename, bytes(chunks), expected_revision=expected_revision)
        except CharacterAssetContainerError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.put("/api/character-containers/{pipeline}/sources/{source_name}")
    def save_source(pipeline: str, source_name: str, payload: dict = Body(...),
                    character: str = Query(...), phase: str = Query(...),
                    costume: str = Query(""), universe_id: str = Query("")):
        try:
            return service(universe_id).save_source(character, phase, pipeline, costume,
                source_name, payload.get("source", {}),
                expected_revision=payload.get("expected_revision", -1),
                render_mode=str(payload.get("render_mode") or ""))
        except CharacterAssetContainerError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/api/character-containers/{pipeline}/views/{view}/candidates/{candidate_id}/{action}")
    def board_action(pipeline: str, view: str, candidate_id: str, action: str,
                     payload: dict = Body(...), character: str = Query(...),
                     phase: str = Query(...), costume: str = Query(""),
                     universe_id: str = Query("")):
        try:
            return service(universe_id).board_action(character, phase, pipeline, costume,
                view, candidate_id, action,
                expected_revision=payload.get("expected_revision", -1),
                expected_candidate_id=payload.get("expected_candidate_id", ""),
                confirm_selected=payload.get("confirm_selected") is True,
                confirm_locked=payload.get("confirm_locked") is True)
        except CharacterAssetContainerError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/api/character-containers/{pipeline}/views/{view}/delete-non-selected/preview")
    def preview_delete_non_selected(pipeline: str, view: str, character: str = Query(...),
                                    phase: str = Query(...), costume: str = Query(""),
                                    universe_id: str = Query("")):
        try:
            return service(universe_id).preview_delete_non_selected(
                character, phase, pipeline, costume, view)
        except CharacterAssetContainerError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/api/character-containers/{pipeline}/views/{view}/delete-drafts/preview")
    def preview_delete_drafts(pipeline: str, view: str, character: str = Query(...),
                              phase: str = Query(...), costume: str = Query(""),
                              universe_id: str = Query("")):
        try:
            return service(universe_id).preview_delete_drafts(
                character, phase, pipeline, costume, view)
        except CharacterAssetContainerError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/api/character-containers/{pipeline}/views/{view}/delete-non-selected")
    def delete_non_selected(pipeline: str, view: str, data: dict = Body(...),
                            character: str = Query(...), phase: str = Query(...),
                            costume: str = Query(""), universe_id: str = Query("")):
        try:
            return service(universe_id).delete_non_selected(
                character, phase, pipeline, costume, view, data)
        except CharacterAssetContainerError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.post("/api/character-containers/{pipeline}/views/{view}/delete-drafts")
    def delete_drafts(pipeline: str, view: str, data: dict = Body(...),
                      character: str = Query(...), phase: str = Query(...),
                      costume: str = Query(""), universe_id: str = Query("")):
        try:
            return service(universe_id).delete_drafts(
                character, phase, pipeline, costume, view, data)
        except CharacterAssetContainerError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @router.get("/api/character-containers/{pipeline}/views/{view}/candidates/{candidate_id}/image")
    def candidate_image(pipeline: str, view: str, candidate_id: str,
                        character: str = Query(...), phase: str = Query(...),
                        costume: str = Query(""), universe_id: str = Query("")):
        try:
            image = service(universe_id).candidate_image(character, phase, pipeline,
                                                         costume, view, candidate_id)
            return FileResponse(image)
        except CharacterAssetContainerError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    return router
