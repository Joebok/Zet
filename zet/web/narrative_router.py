"""HTTP presentation for the independent narrative workflow."""
from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import FileResponse, Response

from zet.services.narrative_scene_service import ProtectedNarrativeImages


def create_narrative_router(app_provider):
    router = APIRouter(prefix="/api/narrative", tags=["narrative"])

    def call(method, *args):
        try:
            return method(*args)
        except ProtectedNarrativeImages as exc:
            raise HTTPException(409, detail={"message": str(exc), "protected_images": exc.images}) from exc
        except KeyError as exc:
            raise HTTPException(404, detail=str(exc).strip("'")) from exc
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(400, detail=str(exc)) from exc

    def author():
        return app_provider().narrative_scene_service

    def generation():
        return app_provider().narrative_generation_service

    def candidates():
        return app_provider().narrative_candidate_import_service

    @router.get("/candidate-sources")
    def candidate_sources():
        return call(candidates().list_sources)

    @router.get("/candidates")
    def candidate_list(source_key: str):
        return call(candidates().list_candidates, source_key)

    @router.post("/candidates/{source_key}/{candidate_id}/import")
    def candidate_import(source_key: str, candidate_id: str, data: dict = Body(...)):
        return call(candidates().import_candidate, source_key, candidate_id, data.get("story_id", ""))

    @router.post("/candidates/{source_key}/{candidate_id}/passed")
    def candidate_passed(source_key: str, candidate_id: str, data: dict = Body(...)):
        return call(candidates().set_passed, source_key, candidate_id, bool(data.get("passed")))

    @router.post("/candidates/{source_key}/{candidate_id}/review")
    def candidate_review(source_key: str, candidate_id: str, data: dict = Body(...)):
        return call(candidates().review, source_key, candidate_id, data.get("story_id", ""), data.get("scene_id", ""), bool(data.get("acknowledge")))

    def references():
        return app_provider().narrative_reference_service

    @router.get("/sources")
    def source_options(kind: str = Query("backdrop")):
        return call(references().sources, kind)

    @router.post("/sources/preview")
    def source_preview(data: dict = Body(...)):
        return call(references().preview, data)

    @router.get("/options")
    def options():
        app = app_provider()
        from zet.services.ai_model_catalog_service import AIModelCatalogService
        return {"model": app.config.ai_narrative_scene_model, "slot_count": 8, "renderer": "Qwen Image 2.1",
                "codex_models": [item["id"] for item in AIModelCatalogService(app.config.base_ai_queue_path, config=app.config).models(providers=["codex"])]}

    @router.get("/scene-text-style")
    def text_style(story: str = ""):
        from zet.services.scene_text_style_service import effective_style, DEFAULTS, available_fonts
        app = app_provider()
        parent = author().repository.read(story) if story else {}
        return {"fonts": available_fonts(), "effective": effective_style(app.config.base_library_path, parent), "defaults": DEFAULTS,
                "overrides": parent.get("scene_text_style_override", {})}

    @router.post("/scene-text-style/preview")
    def text_style_preview(data: dict = Body(...)):
        from zet.services.scene_text_style_service import validate_style
        from zet.services.scene_text_render_service import render
        from io import BytesIO
        from base64 import b64encode
        style = call(validate_style, data)
        image, errors = call(render, (1216, 420), [{"id":"sample", "text":"Scene text with <b>bold</b> and <i>italic</i>.", "tail":"straight"}], {"sample":{"box":[.1,.1,.8,.65],"tip":[.7,.95]}}, style)
        output=BytesIO();image.save(output,format="PNG")
        return {"overlay":"data:image/png;base64,"+b64encode(output.getvalue()).decode(), "errors":errors}

    @router.get("/library")
    def library(q: str = Query("")):
        return call(author().library_options, q)

    @router.get("/library/{asset_id}/image")
    def reference_image(asset_id: str):
        asset = call(author().library_asset, asset_id)
        return FileResponse(asset["image_path"])

    @router.get("/stories")
    def stories():
        return call(author().stories)

    @router.get("/legacy-location")
    def legacy_location(story_slug: str, scene_slug: str = "", optional: bool = False):
        return call(author().legacy_location, story_slug, scene_slug, not optional)

    @router.post("/stories")
    def create_story(data: dict = Body(...)):
        return call(author().create_story, data)

    @router.get("/stories/{story}")
    def story_detail(story: str):
        return call(author().story, story)

    @router.patch("/stories/{story}")
    def update_story(story: str, data: dict = Body(...)):
        return call(author().update_story, story, data)

    @router.delete("/stories/{story}")
    def delete_story(story: str, data: dict = Body(default={})):
        call(author().delete, story, "", "", data.get("confirm_ids", []))
        return {"deleted": True}

    @router.post("/stories/{story}/scenes")
    def create_scene(story: str, data: dict = Body(...)):
        return call(author().create_scene, story, data)

    @router.get("/stories/{story}/scenes/{scene}")
    def scene_detail(story: str, scene: str):
        return call(author().scene, story, scene)

    @router.patch("/stories/{story}/scenes/{scene}")
    def update_scene(story: str, scene: str, data: dict = Body(...)):
        return call(author().update_scene, story, scene, data)

    @router.get("/stories/{story}/scenes/{scene}/legacy-image")
    def legacy_image(story: str, scene: str):
        return FileResponse(call(author().legacy_image, story, scene)["image_path"])

    @router.delete("/stories/{story}/scenes/{scene}")
    def delete_scene(story: str, scene: str, data: dict = Body(default={})):
        call(author().delete, story, scene, "", data.get("confirm_ids", []))
        return {"deleted": True}

    @router.post("/stories/{story}/scenes/{scene}/elements")
    def create_element(story: str, scene: str, data: dict = Body(...)):
        return call(author().save_element, story, scene, data)

    @router.patch("/stories/{story}/scenes/{scene}/elements/{element}")
    def update_element(story: str, scene: str, element: str, data: dict = Body(...)):
        return call(author().save_element, story, scene, data, element)

    @router.delete("/stories/{story}/scenes/{scene}/elements/{element}")
    def delete_element(story: str, scene: str, element: str):
        call(author().delete_element, story, scene, element)
        return {"deleted": True}

    @router.get("/stories/{story}/scenes/{scene}/targets")
    def list_targets(story: str, scene: str):
        return call(author().list_targets, story, scene)

    @router.post("/stories/{story}/scenes/{scene}/targets")
    def create_target(story: str, scene: str, data: dict = Body(...)):
        return call(author().create_target, story, scene, data)

    target_path = "/stories/{story}/scenes/{scene}/targets/{target}"

    @router.post("/stories/{story}/scenes/{scene}/references")
    def import_reference(story: str, scene: str, data: dict = Body(...)):
        return call(references().create, story, scene, data)

    @router.post(target_path + "/backdrop-source")
    def backdrop_source_action(story: str, scene: str, target: str, data: dict = Body(...)):
        return call(references().backdrop_action, story, scene, target, data)

    @router.get(target_path + "/source-image")
    def pinned_source_image(story: str, scene: str, target: str):
        return FileResponse(call(references().image, story, scene, target))

    @router.get(target_path + "/crop-preview")
    def crop_preview(story: str, scene: str, target: str):
        return Response(call(references().crop, story, scene, target), media_type="image/png")

    def assembly():
        return app_provider().narrative_assembly_service

    def animation():
        return app_provider().story_animation_service

    @router.get("/stories/{story}/animations")
    def animations(story: str):
        return call(animation().list, story)

    @router.get("/stories/{story}/animation-sources")
    def animation_sources(story: str):
        return call(animation().sources, story)

    @router.post("/stories/{story}/animations")
    def create_animation(story: str, data: dict = Body(...)):
        return call(animation().create, story, data)

    @router.get("/stories/{story}/animations/{animation_id}")
    def get_animation(story: str, animation_id: str):
        return call(animation().read, story, animation_id)

    @router.put("/stories/{story}/animations/{animation_id}")
    def save_animation(story: str, animation_id: str, data: dict = Body(...)):
        return call(animation().save, story, animation_id, data)

    @router.post("/stories/{story}/animations/{animation_id}/sources")
    def bind_animation_source(story: str, animation_id: str, data: dict = Body(...)):
        return call(animation().bind, story, animation_id, data)

    @router.get("/stories/{story}/animations/{animation_id}/html")
    def animation_html(story: str, animation_id: str, preview: bool = Query(False)):
        from zet.services.story_animation_service import resolve_animation
        from zet.services.story_animation_html_compiler import compile_html
        doc = call(animation().read, story, animation_id)
        data = doc["assets"]
        resolved = call(resolve_animation, doc["spec"], data)
        return Response(compile_html(resolved), media_type="text/html; charset=utf-8",
                        headers={} if preview else {"Content-Disposition": 'attachment; filename="story-animation.html"'})

    @router.get(target_path + "/composite")
    def composite(story: str, scene: str, target: str, download: bool = Query(False)):
        return Response(call(assembly().preview, story, scene, target), media_type="image/png",
                        headers={"Content-Disposition": 'attachment; filename="composite.png"'} if download else {},
                        )

    @router.get(target_path + "/layers/{layer}/image")
    def layer_image(story: str, scene: str, target: str, layer: str, kind: str = Query("cutout")):
        return Response(call(assembly().layer_image, story, scene, target, layer, kind), media_type="image/png")

    @router.get(target_path + "/candidates/{candidate}/composite")
    def candidate_composite(story: str, scene: str, target: str, candidate: str):
        return FileResponse(call(assembly().candidate_composite, story, scene, target, candidate))

    @router.get(target_path)
    def target_detail(story: str, scene: str, target: str):
        return call(generation().detail, story, scene, target)

    @router.patch(target_path)
    def update_target(story: str, scene: str, target: str, data: dict = Body(...)):
        call(author().update_target, story, scene, target, data)
        return call(author().target, story, scene, target)

    @router.delete(target_path)
    def delete_target(story: str, scene: str, target: str, data: dict = Body(default={})):
        call(author().delete, story, scene, target, data.get("confirm_ids", []))
        return {"deleted": True}

    @router.post(target_path + "/jobs")
    def start_job(story: str, scene: str, target: str, data: dict = Body(...)):
        return call(generation().start, story, scene, target, data)

    @router.post(target_path + "/interview-review")
    def apply_interview_review(story: str, scene: str, target: str, data: dict = Body(...)):
        return call(author().apply_interview, story, scene, target, data)

    @router.post(target_path + "/candidates/{candidate}")
    def candidate_action(story: str, scene: str, target: str, candidate: str, data: dict = Body(...)):
        return call(generation().candidate_action, story, scene, target, candidate, data)

    @router.post(target_path + "/candidates/{candidate}/inventory")
    def save_subscene_image(story: str, scene: str, target: str, candidate: str, data: dict = Body(...)):
        return call(author().save_subscene_image_to_inventory, story, scene, target, candidate, data)

    @router.get(target_path + "/candidates/{candidate}/image")
    def candidate_image(story: str, scene: str, target: str, candidate: str, download: bool = Query(False)):
        path = call(generation().image, story, scene, target, candidate)
        return FileResponse(path, filename=path.name if download else None)

    @router.get(target_path + "/scene-text")
    def text_state(story: str, scene: str, target: str, candidate: str = ""):
        return call(app_provider().narrative_scene_text_service.state, story, scene, target, candidate or None)

    @router.post(target_path + "/scene-text/{operation}")
    def text_action(story: str, scene: str, target: str, operation: str, data: dict = Body(...), candidate: str = ""):
        service = app_provider().narrative_scene_text_service
        if operation == "save": return call(service.save, story, scene, target, data, candidate or None)
        if operation == "preview": return call(service.preview, story, scene, target, data, candidate or None)
        if operation == "confirm" and candidate: return call(service.confirm, story, scene, target, candidate, data)
        raise HTTPException(400, detail="Unknown scene text action.")

    @router.get(target_path + "/candidates/{candidate}/finished-image")
    def finished_image(story: str, scene: str, target: str, candidate: str):
        from zet.services.narrative_scene_text_service import finished_path
        return FileResponse(call(finished_path, author().repository, story, scene, target, candidate))

    return router
