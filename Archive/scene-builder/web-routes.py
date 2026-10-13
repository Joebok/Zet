    @app.post("/api/stories/git/status")
    def story_git_status() -> dict[str, Any]:
        """Fetch and return story git status."""
        zet_app = _app(app.state.config_path)
        try:
            return _story_git_payload(zet_app.story_git_status())
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/git/pull")
    def story_git_pull() -> dict[str, Any]:
        """Pull story library changes."""
        zet_app = _app(app.state.config_path)
        try:
            return _story_git_payload(zet_app.story_git_pull())
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/git/commit")
    def story_git_commit() -> dict[str, Any]:
        """Commit and push story changes."""
        zet_app = _app(app.state.config_path)
        try:
            return _story_git_payload(zet_app.story_git_commit())
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories")
    def story_create(title: str = Query(...)) -> dict[str, Any]:
        """Create a new story markdown file from the shared template."""
        zet_app = _app(app.state.config_path)
        try:
            document = zet_app.create_story(title)
            return {
                "stories": [_story_record_payload(item) for item in zet_app.list_stories()],
                "document": _story_document_payload(document),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": f"Created story {document.record.title}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/stories/order")
    def story_reorder(data: dict = Body(...)) -> dict[str, Any]:
        """Persist the complete story display order."""
        zet_app = _app(app.state.config_path)
        try:
            stories = zet_app.reorder_stories(data.get("slugs"))
            return {
                "stories": [_story_record_payload(item) for item in stories],
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": "Story order saved.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/stories/{story_slug}")
    def story_detail(story_slug: str) -> dict[str, Any]:
        """Load one story markdown document."""
        zet_app = _app(app.state.config_path)
        try:
            return {"document": _story_document_payload(zet_app.load_story(story_slug))}
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.patch("/api/stories/{story_slug}")
    def story_rename(story_slug: str, data: dict = Body(...)) -> dict[str, Any]:
        """Rename one story while preserving its slug."""
        zet_app = _app(app.state.config_path)
        try:
            document = zet_app.rename_story(story_slug, data.get("title"))
            return {
                "stories": [_story_record_payload(item) for item in zet_app.list_stories()],
                "document": _story_document_payload(document),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": f"Renamed story to {document.record.title}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/stories/{story_slug}")
    def story_delete(story_slug: str) -> dict[str, Any]:
        """Commit and delete one story folder."""
        zet_app = _app(app.state.config_path)
        try:
            result = zet_app.delete_story(story_slug)
            return {
                "stories": [_story_record_payload(item) for item in zet_app.list_stories()],
                "git": _story_git_payload(result),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": f"Deleted story {story_slug}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/stories/{story_slug}/settings")
    def story_settings_detail(story_slug: str) -> dict[str, Any]:
        """Load one story settings JSON document."""
        zet_app = _app(app.state.config_path)
        try:
            return {"data": _jsonable(zet_app.load_story_settings(story_slug))}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/stories/{story_slug}/settings")
    def story_settings_save(story_slug: str, data: dict = Body(...)) -> dict[str, Any]:
        """Save one story settings JSON document."""
        zet_app = _app(app.state.config_path)
        try:
            return {
                "data": _jsonable(zet_app.save_story_settings(story_slug, data)),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": "Saved story settings.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/{story_slug}/scenes")
    def scene_create(story_slug: str, scene_name: str = Query(...)) -> dict[str, Any]:
        """Create a new scene markdown file for one story."""
        zet_app = _app(app.state.config_path)
        try:
            document = zet_app.create_scene(story_slug, scene_name)
            return {
                "scenes": [_scene_record_payload(item) for item in zet_app.list_scenes(story_slug)],
                "document": _scene_document_payload(zet_app, document),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": f"Created scene {document.record.title}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/stories/{story_slug}/scenes/{scene_slug}")
    def scene_detail(story_slug: str, scene_slug: str) -> dict[str, Any]:
        """Load one story scene markdown document."""
        zet_app = _app(app.state.config_path)
        try:
            return {"document": _scene_document_payload(zet_app, zet_app.load_scene(story_slug, scene_slug))}
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/stories/{story_slug}/scenes/{scene_slug}/builder")
    def scene_builder_detail(story_slug: str, scene_slug: str, include_references: bool = Query(True)) -> dict[str, Any]:
        """Load Scene Builder JSON for one story scene."""
        zet_app = _app(app.state.config_path)
        try:
            return {
                "document": _scene_builder_document_payload(zet_app, zet_app.load_scene_builder(story_slug, scene_slug)),
                "options": zet_app.scene_builder_options(),
                "references": ([_image_reference_payload(item) for item in zet_app.scene_image_reference_rows()]
                               if include_references else []),
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/stories/{story_slug}/scenes/order")
    def scene_reorder(story_slug: str, data: dict = Body(...)) -> dict[str, Any]:
        """Persist the complete scene display order for one story."""
        zet_app = _app(app.state.config_path)
        try:
            scenes = zet_app.reorder_scenes(story_slug, data.get("slugs"))
            return {
                "scenes": [_scene_record_payload(item) for item in scenes],
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": "Scene order saved.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.patch("/api/stories/{story_slug}/scenes/{scene_slug}")
    def scene_rename(story_slug: str, scene_slug: str, data: dict = Body(...)) -> dict[str, Any]:
        """Rename one scene while preserving its slug."""
        zet_app = _app(app.state.config_path)
        try:
            document = zet_app.rename_scene(story_slug, scene_slug, data.get("title"))
            return {
                "scenes": [_scene_record_payload(item) for item in zet_app.list_scenes(story_slug)],
                "document": _scene_document_payload(zet_app, document),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": f"Renamed scene to {document.record.title}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/{story_slug}/scenes/{scene_slug}/move")
    def scene_move(story_slug: str, scene_slug: str, data: dict = Body(...)) -> dict[str, Any]:
        """Move one scene and its artifacts to another story."""
        zet_app = _app(app.state.config_path)
        try:
            target_story_slug = data.get("target_story_slug")
            document = zet_app.move_scene(story_slug, scene_slug, target_story_slug)
            return {
                "source_scenes": [_scene_record_payload(item) for item in zet_app.list_scenes(story_slug)],
                "target_scenes": [_scene_record_payload(item) for item in zet_app.list_scenes(target_story_slug)],
                "document": _scene_document_payload(zet_app, document),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": f"Moved scene {document.record.title} to {document.story.title}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/stories/{story_slug}/scenes/{scene_slug}/builder")
    def scene_builder_save(story_slug: str, scene_slug: str, data: dict = Body(...)) -> dict[str, Any]:
        """Save Scene Builder JSON for one story scene."""
        zet_app = _app(app.state.config_path)
        try:
            document = zet_app.save_scene_builder(story_slug, scene_slug, data)
            return {
                "document": _scene_builder_document_payload(zet_app, document),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": f"Saved Scene Builder data for {document.scene.title}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/{story_slug}/scenes/{scene_slug}/builder/3d-layout/draft")
    def scene_builder_layout_draft(story_slug: str, scene_slug: str, data: dict = Body(...), target_id: str = Query("main")) -> dict[str, Any]:
        """Create a 3D layout draft without saving scene data."""
        zet_app = _app(app.state.config_path)
        try:
            scene = zet_app.generate_scene_builder(story_slug, scene_slug, data)
            return {"layout_3d": zet_app.create_scene_layout_draft(scene, target_id)}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/{story_slug}/scenes/{scene_slug}/builder/3d-layout/preview")
    def scene_builder_layout_preview(story_slug: str, scene_slug: str, data: dict = Body(...), target_id: str = Query("main")) -> dict[str, Any]:
        """Preview unsaved 3D layout geometry and its Qwen guidance image."""
        zet_app = _app(app.state.config_path)
        try:
            scene = zet_app.generate_scene_builder(story_slug, scene_slug, data)
            scene.setdefault("scene", {})["_story_slug"] = story_slug
            return zet_app.preview_scene_layout(scene, target_id=target_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/stories/{story_slug}/scenes/{scene_slug}/builder/3d-layout")
    def scene_builder_layout_save(story_slug: str, scene_slug: str, data: dict = Body(...), target_id: str = Query("main")) -> dict[str, Any]:
        """Save one 3D layout workspace without replacing unrelated builder edits."""
        zet_app = _app(app.state.config_path)
        try:
            document = zet_app.save_scene_layout(story_slug, scene_slug, target_id, data.get("layout_3d") or {},
                                                  int(data.get("expected_revision", -1)))
            return {"document": _scene_builder_document_payload(zet_app, document),
                    "has_story_changes": zet_app.story_git_has_changes(),
                    "message": f"Saved 3D layout for {target_id}.", "target_id": target_id}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/{story_slug}/scenes/{scene_slug}/builder/continue-from")
    def scene_builder_continue_from(story_slug: str, scene_slug: str, source_scene_slug: str = Query(...)) -> dict[str, Any]:
        """Copy another scene's complete editable structure into this scene."""
        zet_app = _app(app.state.config_path)
        try:
            document = zet_app.continue_scene_builder_from(story_slug, scene_slug, source_scene_slug)
            return {
                "document": _scene_builder_document_payload(zet_app, document),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": f"Continued from {source_scene_slug}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/{story_slug}/scenes/{scene_slug}/builder/generate")
    def scene_builder_generate(story_slug: str, scene_slug: str, data: dict = Body(...)) -> dict[str, Any]:
        """Generate Scene Builder outputs without saving JSON."""
        zet_app = _app(app.state.config_path)
        try:
            return {"data": _jsonable(zet_app.generate_scene_builder(story_slug, scene_slug, data))}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/stories/{story_slug}/scenes/{scene_slug}/builder/subscenes/{target_id}")
    def scene_builder_subscene_save(
        story_slug: str, scene_slug: str, target_id: str, data: dict = Body(...)
    ) -> dict[str, Any]:
        """Save one subscene without replacing unrelated Scene Builder values."""
        zet_app = _app(app.state.config_path)
        try:
            document = zet_app.save_scene_builder_subscene(story_slug, scene_slug, target_id, data)
            return {
                "document": _scene_builder_document_payload(zet_app, document),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": f"Saved subscene {target_id}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/{story_slug}/scenes/{scene_slug}/subscenes/background/enable")
    def scene_background_subscene_enable(story_slug: str, scene_slug: str) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            document = zet_app.enable_background_subscene(story_slug, scene_slug)
            return {
                "document": _scene_builder_document_payload(zet_app, document),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": "Background sub-render enabled. Background-depth membership was seeded once.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/{story_slug}/scenes/{scene_slug}/subscenes")
    def scene_subscene_create(story_slug: str, scene_slug: str) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            document, target_id = zet_app.create_subscene(story_slug, scene_slug)
            return {
                "document": _scene_builder_document_payload(zet_app, document),
                "render_target_id": target_id,
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": "Sub-scene added. Assign elements from Full Scene using the Render in field.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/{story_slug}/scenes/{scene_slug}/subscenes/elements/{element_id}/enable")
    def scene_element_subscene_enable(story_slug: str, scene_slug: str, element_id: str) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            document = zet_app.enable_element_subscene(story_slug, scene_slug, element_id)
            target = next(
                (
                    item for item in document.data.get("subscenes") or []
                    if item.get("kind") == "element" and item.get("anchor_element_id") == element_id
                ),
                {},
            )
            return {
                "document": _scene_builder_document_payload(zet_app, document),
                "render_target_id": str(target.get("id") or ""),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": f"Element sub-render enabled for {target.get('name') or element_id}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/{story_slug}/scenes/{scene_slug}/subscenes/{target_id}/disable")
    def scene_subscene_disable(story_slug: str, scene_slug: str, target_id: str) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            document = zet_app.disable_scene_subscene(story_slug, scene_slug, target_id)
            return {
                "document": _scene_builder_document_payload(zet_app, document),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": f"{target_id} sub-render disabled; its setup and locked image were retained.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/scene-candidate-sources")
    def scene_candidate_sources() -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            return {"sources": [asdict(source) for source in zet_app.list_scene_candidate_sources()]}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/scene-candidates")
    def scene_candidates(
        source_key: str = Query(...), cursor: str = Query(""),
        limit: int = Query(50, ge=1, le=200),
    ) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            page = zet_app.indexed_list(
                "scene_candidate", source_key=source_key, cursor=cursor or None, limit=limit
            )
            return _indexed_page_payload(page)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/scene-candidates/{source_key}/{candidate_id}")
    def scene_candidate_detail(source_key: str, candidate_id: str) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            return {"candidate": asdict(zet_app.get_scene_candidate(source_key, candidate_id))}
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/scene-candidates/{source_key}/{candidate_id}/passed")
    def scene_candidate_passed(source_key: str, candidate_id: str, data: dict = Body(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            candidate = zet_app.set_scene_candidate_passed(source_key, candidate_id, bool(data.get("passed")))
            return {"candidate": asdict(candidate)}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/scene-candidates/{source_key}/{candidate_id}/image")
    def scene_candidate_image(source_key: str, candidate_id: str) -> FileResponse:
        zet_app = _app(app.state.config_path)
        try:
            return FileResponse(zet_app.scene_candidate_image_path(source_key, candidate_id))
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/scene-candidates/{source_key}/{candidate_id}/import")
    def scene_candidate_import(source_key: str, candidate_id: str, data: dict = Body(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            result = zet_app.import_scene_candidate(
                source_key,
                candidate_id,
                data.get("story_slug"),
                bool(data.get("confirm_update")),
            )
            return {
                "result": asdict(result),
                "document": _scene_builder_document_payload(
                    zet_app,
                    zet_app.load_scene_builder(result.story_slug, result.scene_slug),
                ),
                "scenes": [_scene_record_payload(item) for item in zet_app.list_scenes(result.story_slug)],
                "has_story_changes": zet_app.story_git_has_changes(),
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/{story_slug}/scenes/{scene_slug}/builder/interview")
    def scene_builder_interview_start(story_slug: str, scene_slug: str, data: dict = Body(...)) -> dict[str, Any]:
        """Start a focused local-LLM Scene Builder interview."""
        zet_app = _app(app.state.config_path)
        try:
            return _jsonable(zet_app.start_scene_builder_interview(
                data.get("narrative"),
                data.get("data"),
                data.get("phases"),
            ))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/stories/{story_slug}/scenes/{scene_slug}/builder/interview-seed")
    def scene_builder_interview_seed(story_slug: str, scene_slug: str) -> dict[str, Any]:
        """Rebuild the interview seed for a scene imported from a candidate."""
        zet_app = _app(app.state.config_path)
        try:
            return _jsonable(zet_app.scene_builder_interview_seed(story_slug, scene_slug))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/{story_slug}/scenes/{scene_slug}/builder/interview/step")
    def scene_builder_interview_step(story_slug: str, scene_slug: str, data: dict = Body(...)) -> dict[str, Any]:
        """Run one focused phase or clarification turn of a Scene Builder interview."""
        zet_app = _app(app.state.config_path)
        try:
            return _jsonable(zet_app.continue_scene_builder_interview(data.get("session"), data.get("answers")))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/stories/{story_slug}/scenes/{scene_slug}/prompt-analysis")
    def scene_prompt_analysis_status(
        story_slug: str, scene_slug: str, render_target_id: str = Query("main")
    ) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            return zet_app.scene_prompt_analysis_status(story_slug, scene_slug, render_target_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/stories/{story_slug}/scenes/{scene_slug}/prompt-analysis/view", response_class=HTMLResponse)
    def scene_prompt_analysis_view(
        story_slug: str, scene_slug: str, render_target_id: str = Query("main")
    ) -> HTMLResponse:
        zet_app = _app(app.state.config_path)
        try:
            status = zet_app.scene_prompt_analysis_status(story_slug, scene_slug, render_target_id)
            result_path = Path(status["result_path"])
            if not status["complete"] or not result_path.is_file():
                raise HTTPException(status_code=404, detail="Prompt analysis is not available.")
            content = markdown.markdown(result_path.read_text(encoding="utf-8"), extensions=["extra", "sane_lists"])
            return HTMLResponse(
                f"<!doctype html><html><head><meta charset=\"utf-8\"><title>Prompt Analysis</title>"
                "<style>body{max-width:900px;margin:40px auto;padding:0 24px;font:16px/1.55 system-ui,sans-serif}"
                "pre{padding:16px;overflow:auto;background:#f5f5f5}code{font-family:ui-monospace,monospace}"
                "table{border-collapse:collapse}th,td{padding:6px 10px;border:1px solid #ccc}</style></head>"
                f"<body>{content}</body></html>",
                headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"},
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/{story_slug}/scenes/{scene_slug}/prompt-analysis")
    def scene_prompt_analysis_queue(
        story_slug: str, scene_slug: str, render_target_id: str = Query("main")
    ) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            status = zet_app.queue_scene_prompt_analysis(story_slug, scene_slug, render_target_id)
            status["message"] = "AI prompt analysis queued."
            return status
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/{story_slug}/scenes/{scene_slug}/prompt-analysis/harvest")
    def scene_prompt_analysis_harvest(
        story_slug: str, scene_slug: str, render_target_id: str = Query("main")
    ) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            zet_app.harvest_ai_answers()
            status = zet_app.scene_prompt_analysis_status(story_slug, scene_slug, render_target_id)
            status["message"] = "AI answers harvested."
            return status
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/{story_slug}/scenes/{scene_slug}/builder/export-markdown")
    def scene_builder_export_markdown(story_slug: str, scene_slug: str, data: dict = Body(...)) -> dict[str, Any]:
        """Export Scene Builder-managed markdown into one story scene."""
        zet_app = _app(app.state.config_path)
        try:
            scene_document = zet_app.export_scene_builder_markdown(story_slug, scene_slug, data)
            builder_document = zet_app.load_scene_builder(story_slug, scene_slug)
            return {
                "document": _scene_document_payload(zet_app, scene_document),
                "builder": _scene_builder_document_payload(zet_app, builder_document),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": f"Exported Scene Builder sections for {scene_document.record.title}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/stories/{story_slug}/scenes/{scene_slug}")
    def scene_delete(story_slug: str, scene_slug: str) -> dict[str, Any]:
        """Commit and delete one story scene markdown file and image."""
        zet_app = _app(app.state.config_path)
        try:
            result = zet_app.delete_scene(story_slug, scene_slug)
            return {
                "scenes": [_scene_record_payload(item) for item in zet_app.list_scenes(story_slug)],
                "git": _story_git_payload(result),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": f"Deleted scene {scene_slug}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/{story_slug}/scenes/{scene_slug}/stage-render")
    def scene_stage_render(
        story_slug: str,
        scene_slug: str,
        allow_stale_dependencies: bool = Query(False),
    ) -> dict[str, Any]:
        """Compile and stage one story scene for the Render Console."""
        zet_app = _app(app.state.config_path)
        try:
            task = zet_app.stage_scene_render(
                story_slug, scene_slug, allow_stale_dependencies=allow_stale_dependencies
            )
            return {
                "task": _story_render_task_payload(task),
                "message": task.warning or f"Staged scene {task.scene_slug} for Render Console.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/{story_slug}/scenes/{scene_slug}/prompt-analysis/second-opinion")
    def scene_prompt_analysis_second_opinion(
        story_slug: str, scene_slug: str, render_target_id: str = Query("main")
    ) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            status = zet_app.queue_scene_prompt_analysis_second_opinion(
                story_slug, scene_slug, render_target_id
            )
            status["message"] = "AI prompt analysis second opinion queued."
            return status
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/{story_slug}/scenes/{scene_slug}/render-targets/{target_id}/stage-render")
    def scene_target_stage_render(
        story_slug: str,
        scene_slug: str,
        target_id: str,
        allow_stale_dependencies: bool = Query(False),
    ) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            task = zet_app.stage_scene_render(
                story_slug, scene_slug, target_id, allow_stale_dependencies
            )
            return {
                "task": _story_render_task_payload(task),
                "message": task.warning or f"Staged {target_id} render for {task.scene_slug}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/render-review/scenes/{story_slug}/{scene_slug}")
    def scene_render_review_detail(story_slug: str, scene_slug: str) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            return _scene_render_review_context_payload(zet_app, story_slug, scene_slug)
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/render-review/scenes/{story_slug}/{scene_slug}/promote-to-locked")
    def scene_render_review_promote(story_slug: str, scene_slug: str) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            status = zet_app.promote_scene_image(story_slug, scene_slug)
            return {
                "message": f"Scene image approved for {status.story_slug}/{status.scene_slug}.",
                "review": asdict(status),
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/render-review/scenes/{story_slug}/{scene_slug}/discard-candidate")
    def scene_render_review_discard(story_slug: str, scene_slug: str) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            status = zet_app.discard_scene_image_candidate(story_slug, scene_slug)
            return {
                "message": f"Scene candidate discarded for {status.story_slug}/{status.scene_slug}.",
                "review": asdict(status),
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/render-review/scenes/{story_slug}/{scene_slug}/targets/{target_id}")
    def scene_target_render_review_detail(story_slug: str, scene_slug: str, target_id: str) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            return _scene_render_review_context_payload(zet_app, story_slug, scene_slug, target_id)
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/render-review/scenes/{story_slug}/{scene_slug}/targets/{target_id}/promote-to-locked")
    def scene_target_render_review_promote(story_slug: str, scene_slug: str, target_id: str) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            status = zet_app.promote_scene_image(story_slug, scene_slug, target_id)
            return {"message": f"{status.render_target_label} image approved.", "review": asdict(status)}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/render-review/scenes/{story_slug}/{scene_slug}/targets/{target_id}/re-lock-current")
    def scene_target_render_review_relock(story_slug: str, scene_slug: str, target_id: str) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            status = zet_app.relock_current_scene_image(story_slug, scene_slug, target_id)
            return {"message": f"{status.render_target_label} image re-locked.", "review": asdict(status)}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/render-review/scenes/{story_slug}/{scene_slug}/targets/{target_id}/discard-candidate")
    def scene_target_render_review_discard(story_slug: str, scene_slug: str, target_id: str) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            status = zet_app.discard_scene_image_candidate(story_slug, scene_slug, target_id)
            return {"message": f"{status.render_target_label} candidate discarded.", "review": asdict(status)}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/stories/{story_slug}")
    async def story_save(story_slug: str, request: Request) -> dict[str, Any]:
        """Save one story markdown document."""
        zet_app = _app(app.state.config_path)
        try:
            text = (await request.body()).decode("utf-8")
            document = zet_app.save_story(story_slug, text)
            return {
                "stories": [_story_record_payload(item) for item in zet_app.list_stories()],
                "document": _story_document_payload(document),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": f"Saved story {document.record.title}.",
            }
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail="Story markdown must be UTF-8.") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/stories/{story_slug}/scenes/{scene_slug}")
    async def scene_save(story_slug: str, scene_slug: str, request: Request) -> dict[str, Any]:
        """Save one story scene markdown document."""
        zet_app = _app(app.state.config_path)
        try:
            text = (await request.body()).decode("utf-8")
            document = zet_app.save_scene(story_slug, scene_slug, text)
            return {
                "scenes": [_scene_record_payload(item) for item in zet_app.list_scenes(story_slug)],
                "document": _scene_document_payload(zet_app, document),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": f"Saved scene {document.record.title}.",
            }
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail="Scene markdown must be UTF-8.") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/render-review/scenes/{story_slug}/{scene_slug}/comment")
    async def scene_render_review_comment(story_slug: str, scene_slug: str, request: Request) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            payload = await request.json()
            comment = zet_app.save_scene_image_review_comment(story_slug, scene_slug, str(payload.get("comment") or ""))
            response = _scene_render_review_context_payload(zet_app, story_slug, scene_slug)
            response["message"] = "Image review comment saved." if comment else "Image review comment cleared."
            return response
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/render-review/scenes/{story_slug}/{scene_slug}/targets/{target_id}/comment")
    async def scene_target_render_review_comment(story_slug: str, scene_slug: str, target_id: str, request: Request) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            payload = await request.json()
            comment = zet_app.save_scene_image_review_comment(
                story_slug, scene_slug, str(payload.get("comment") or ""), target_id
            )
            response = _scene_render_review_context_payload(zet_app, story_slug, scene_slug, target_id)
            response["message"] = "Image review comment saved." if comment else "Image review comment cleared."
            return response
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

