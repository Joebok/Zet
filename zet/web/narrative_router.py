"""HTTP presentation for the independent narrative workflow."""
from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import FileResponse

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

    @router.get("/options")
    def options():
        app = app_provider()
        return {"model": app.config.ai_narrative_scene_model, "slot_count": 8, "renderer": "Qwen Image 2.1"}

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

    @router.post(target_path + "/candidates/{candidate}")
    def candidate_action(story: str, scene: str, target: str, candidate: str, data: dict = Body(...)):
        return call(generation().candidate_action, story, scene, target, candidate, data)

    @router.get(target_path + "/candidates/{candidate}/image")
    def candidate_image(story: str, scene: str, target: str, candidate: str, download: bool = Query(False)):
        path = call(generation().image, story, scene, target, candidate)
        return FileResponse(path, filename=path.name if download else None)

    return router
