"""HTTP presentation for story-scoped local scene batches."""
from fastapi import APIRouter, Body, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from starlette.background import BackgroundTask


def create_local_scene_batch_router(app_factory):
    router = APIRouter(prefix="/api/stories/{story_slug}/scenes/{scene_slug}/local-batches")

    def service():
        return app_factory().local_scene_batch_service

    def call(function):
        try:
            return function()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @router.post("/preview")
    def preview(story_slug: str, scene_slug: str, payload: dict = Body(...)):
        return call(lambda: service().preview(story_slug, scene_slug, payload))

    @router.post("")
    def create(story_slug: str, scene_slug: str, payload: dict = Body(...)):
        return call(lambda: service().create(story_slug, scene_slug, payload))

    @router.get("")
    def list_batches(story_slug: str, scene_slug: str, target_id: str = "main", ask_id: str = ""):
        return call(lambda: {"batches": service().list_runs(story_slug, scene_slug),
                             "linked_batch_id": service().linked_batch(story_slug, scene_slug, target_id, ask_id)})

    @router.get("/{run_id}")
    def detail(story_slug: str, scene_slug: str, run_id: str):
        return call(lambda: service().improvement(story_slug, scene_slug).detail(run_id))

    @router.delete("/{run_id}")
    def delete(story_slug: str, scene_slug: str, run_id: str):
        return call(lambda: service().delete(story_slug, scene_slug, run_id) or {"deleted": True})

    @router.post("/{run_id}/actions/{action}")
    def action(story_slug: str, scene_slug: str, run_id: str, action: str, payload: dict = Body(default={})):
        def perform():
            batches = service()
            target = str(payload.get("target_id") or "main")
            if action in {"analyze-prompt", "second-opinion"}:
                return batches.analyze_prompt(story_slug, scene_slug, run_id, target, action == "second-opinion")
            improvement = batches.improvement(story_slug, scene_slug)
            if action == "save-observations":
                return improvement.save_observations(run_id, target, str(payload.get("observations") or ""))
            if action == "analyze-images":
                return improvement.start(run_id, target)
            return batches.action(story_slug, scene_slug, run_id, action, payload)
        return call(perform)

    @router.get("/{run_id}/targets/{target_id}/prompt", response_class=PlainTextResponse)
    def prompt(story_slug: str, scene_slug: str, run_id: str, target_id: str, attempt_id: str = ""):
        return call(lambda: service().artifact(story_slug, scene_slug, run_id, target_id, "prompt", attempt_id=attempt_id).read_text(encoding="utf-8"))

    @router.get("/{run_id}/targets/{target_id}/analysis", response_class=PlainTextResponse)
    def analysis(story_slug: str, scene_slug: str, run_id: str, target_id: str, attempt_id: str = ""):
        return call(lambda: service().artifact(story_slug, scene_slug, run_id, target_id, "analysis", attempt_id=attempt_id).read_text(encoding="utf-8"))

    @router.get("/{run_id}/targets/{target_id}/images/{candidate_id}")
    def image(story_slug: str, scene_slug: str, run_id: str, target_id: str, candidate_id: str, attempt_id: str = ""):
        return call(lambda: FileResponse(service().artifact(story_slug, scene_slug, run_id, target_id, "image", candidate_id, attempt_id)))

    @router.get("/{run_id}/targets/{target_id}/references/{index}")
    def reference(story_slug: str, scene_slug: str, run_id: str, target_id: str, index: int, attempt_id: str = ""):
        return call(lambda: FileResponse(service().artifact(story_slug, scene_slug, run_id, target_id, "reference", str(index), attempt_id)))

    @router.get("/{run_id}/prompt-improvement-package")
    def package(story_slug: str, scene_slug: str, run_id: str):
        def download():
            path = service().improvement(story_slug, scene_slug).create_package(run_id)
            return FileResponse(path, media_type="application/zip", filename=f"Scene_{run_id}_Prompt_Review.zip",
                                background=BackgroundTask(path.unlink, missing_ok=True))
        return call(download)

    return router
