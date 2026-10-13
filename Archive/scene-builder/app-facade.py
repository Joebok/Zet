    def list_scene_candidate_sources(self):
        return self.scene_candidate_import_service.list_sources()

    def list_scene_candidates(self, source_key: str):
        return self.scene_candidate_import_service.list_candidates(source_key)

    def get_scene_candidate(self, source_key: str, candidate_id: str):
        return self.scene_candidate_import_service.get_candidate(source_key, candidate_id)

    def set_scene_candidate_passed(self, source_key: str, candidate_id: str, passed: bool):
        return self._indexed_write(
            lambda: self.scene_candidate_import_service.set_passed(source_key, candidate_id, passed)
        )

    def scene_candidate_image_path(self, source_key: str, candidate_id: str) -> Path:
        return self.scene_candidate_import_service.candidate_image_path(source_key, candidate_id)

    def import_scene_candidate(self, source_key: str, candidate_id: str, story_slug: str, confirm_update: bool = False):
        return self._indexed_write(lambda: self.scene_candidate_import_service.import_candidate(
            source_key,
            candidate_id,
            story_slug,
            confirm_update,
        ))

    def scene_readiness(self, data: dict) -> dict:
        readiness = self.scene_candidate_import_service.readiness(data)
        catalog_by_tag = {
            item.tag: item for item in self.image_catalog_service.list_items(include_base=True)
        }
        blockers = list(readiness.get("blockers") or [])
        for element in data.get("scene_elements") or []:
            references = [item for item in element.get("reference_images") or [] if isinstance(item, dict)]
            if not references:
                continue
            catalog_item = catalog_by_tag.get(str(references[0].get("tag") or ""))
            if catalog_item is None:
                continue
            label = element.get("display_name") or element.get("id") or "Scene element"
            if catalog_item.identity_status == "missing":
                blockers.append(f"{label}'s selected image needs identity description text.")
            if catalog_item.costume_status == "missing":
                blockers.append(f"{label}'s selected image needs costume description text.")
        readiness["blockers"] = list(dict.fromkeys(blockers))
        if readiness["blockers"] and readiness.get("status") == "ready":
            readiness["status"] = "needs_attention"
        return readiness

    def scene_image_review_status(self, story_slug: str, scene_slug: str, render_target_id: str = "main"):
        return self.scene_image_review_service.status(story_slug, scene_slug, render_target_id)

    def list_pending_scene_image_reviews(
        self,
        story_slug: str = "",
        scene_slug: str = "",
        *,
        discovery_context: DiscoveryContext | None = None,
    ):
        return self.scene_image_review_service.list_pending(
            story_slug,
            scene_slug,
            discovery_context=discovery_context,
        )

    def promote_scene_image(self, story_slug: str, scene_slug: str, render_target_id: str = "main"):
        return self._indexed_write(
            lambda: self.scene_image_review_service.promote(story_slug, scene_slug, render_target_id)
        )

    def relock_current_scene_image(self, story_slug: str, scene_slug: str, render_target_id: str = "main"):
        return self._indexed_write(
            lambda: self.scene_image_review_service.relock_current(story_slug, scene_slug, render_target_id)
        )

    def discard_scene_image_candidate(self, story_slug: str, scene_slug: str, render_target_id: str = "main"):
        return self.scene_image_review_service.discard(story_slug, scene_slug, render_target_id)

    def save_scene_image_review_comment(self, story_slug: str, scene_slug: str, comment: str, render_target_id: str = "main"):
        return self.scene_image_review_service.save_comment(story_slug, scene_slug, comment, render_target_id)

    def load_scene_builder(self, story_slug: str, scene_slug: str) -> SceneBuilderDocument:
        """Load Scene Builder JSON for one story scene."""
        return self.story_service.load_scene_builder_data(story_slug, scene_slug)

    def save_scene_builder(self, story_slug: str, scene_slug: str, data: dict) -> SceneBuilderDocument:
        """Save Scene Builder JSON for one story scene."""
        return self._indexed_write(
            lambda: self.story_service.save_scene_builder_data(story_slug, scene_slug, data)
        )

    def save_scene_builder_subscene(
        self, story_slug: str, scene_slug: str, target_id: str, subscene: dict
    ) -> SceneBuilderDocument:
        """Save one Scene Builder subscene without replacing the full scene."""
        return self._indexed_write(
            lambda: self.story_service.save_scene_builder_subscene_data(
                story_slug, scene_slug, target_id, subscene
            )
        )

    def continue_scene_builder_from(self, story_slug: str, scene_slug: str, source_scene_slug: str) -> SceneBuilderDocument:
        """Copy another scene's complete editable structure into this scene."""
        return self._indexed_write(
            lambda: self.story_service.continue_scene_builder_from(story_slug, scene_slug, source_scene_slug)
        )

    def generate_scene_builder(self, story_slug: str, scene_slug: str, data: dict) -> dict:
        """Generate Scene Builder outputs without saving."""
        return self.story_service.generate_scene_builder_outputs(story_slug, scene_slug, data)

    def preview_scene_layout(self, data: dict, *, width: int = 1024, height: int = 576, target_id: str = "main") -> dict:
        """Project an unsaved scene layout and return its clean guidance image."""
        data = __import__("copy").deepcopy(data)
        if target_id == "main":
            data["layout_3d"] = data.get("layout_3d") or {}
        else:
            definition = next((item for item in data.get("subscenes") or [] if item.get("id") == target_id), None)
            if definition is None:
                raise ValueError(f"Scene subscene not found: {target_id}")
            definition["layout_3d"] = data.get("layout_3d") or definition.get("layout_3d") or {}
        elements = data.get("scene_elements") or []
        service = self.story_service.scene_layout_service
        targets = service.normalize_targets(data)
        if target_id not in targets["targets"]:
            raise ValueError(f"Scene subscene not found: {target_id}")
        layout = targets["targets"][target_id]
        if target_id == "main":
            composition = service.compose_targets(data, target_id)
            visible_ids = {item["element_id"] for item in composition["pawns"]}
            layout = {**layout, "pawns": [item for item in layout["pawns"] if item["element_id"] in visible_ids]}
        else:
            composition = service.compose_targets(data, target_id)
        if width == 1024 and height == 576:
            canvas = (data.get("setup") or {}).get("canvas") or {}
            try:
                presets = __import__("json").loads(self.story_service._project_config_path("Local_Render_Presets.json").read_text(encoding="utf-8"))
                budget = int(presets.get("comfyui-qwen-image-2-1-scene", {}).get("pixel_budget", 1_048_576))
            except (OSError, ValueError, TypeError):
                budget = 1_048_576
            width, height = service.output_size(str(canvas.get("aspect_ratio") or "16:9"), budget)
        from zet.services.scene_background_service import SceneBackgroundService
        backgrounds = SceneBackgroundService(self.story_service.story_reference_service, self.story_service.scene_render_target_service)
        background = None
        background_warning = ""
        try:
            background = backgrounds.resolve(data, layout, width=width, height=height)
        except ValueError as exc:
            background_warning = str(exc)
        if target_id == "main":
            composition_ids = {item["element_id"] for item in composition["pawns"]}
            main_elements = [item for item in elements if item.get("id") in composition_ids]
            camera_layout = {**layout, "pawns": [item for item in composition["pawns"]]}
        else:
            main_elements = [item for item in elements if item.get("id") in {pawn["element_id"] for pawn in composition["pawns"]}]
            camera_layout = {**layout, "pawns": composition["pawns"]}
        projection = service.project(camera_layout, width=width, height=height, aspect=backgrounds.aspect(data))
        composition["groups_workspace"] = target_id
        service.aggregate_group_projection(projection, composition, main_elements)
        projection["warnings"].extend(service.empty_group_warnings(composition, data.get("subscenes") or []))
        if background:
            projection["background"] = background["projection"]
        if background_warning:
            projection["warnings"].append(background_warning)
        import base64
        png = service.render_guidance(camera_layout, projection, main_elements, background_png=background["png_bytes"] if background else None)
        return {"projection": projection, "guidance_png_base64": base64.b64encode(png).decode("ascii"),
                "layout_3d": layout, "background_options": backgrounds.options(data),
                "composition": composition,
                "background_source_png_base64": base64.b64encode(background["source_png_bytes"]).decode("ascii") if background else "",
                "sha256": __import__("hashlib").sha256(png).hexdigest(),
                "warnings": projection["warnings"], "migration_review_required": layout.get("migration_review_required", False),
                "provisional_elements": [item["element_id"] for item in camera_layout["pawns"] if item["provisional_height"]]}

    def create_scene_layout_draft(self, data: dict, target_id: str = "main") -> dict:
        """Create an unsaved 3D layout draft from scene elements and legacy positions."""
        service = self.story_service.scene_layout_service
        targets = service.normalize_targets(data)
        if target_id not in targets["targets"]:
            raise ValueError(f"Scene subscene not found: {target_id}")
        return targets["targets"][target_id]

    def save_scene_layout(self, story_slug: str, scene_slug: str, target_id: str, layout: dict,
                          expected_revision: int):
        """Save a single 3D layout workspace without replacing other scene edits."""
        return self._indexed_write(lambda: self.story_service.save_scene_layout_data(
            story_slug, scene_slug, target_id, layout, expected_revision
        ))

    def scene_builder_options(self) -> dict:
        """Return Scene Builder option lists."""
        return self.story_service.scene_builder_options()

    def start_scene_builder_interview(self, narrative: str, data: dict, phases: list[str] | None = None) -> dict:
        """Start a narrative-to-Scene-Builder interview."""
        return self.scene_builder_interview_service.start(narrative, data, phases)

    def continue_scene_builder_interview(self, session: dict, answers: dict | None = None) -> dict:
        """Run one focused phase of a Scene Builder interview."""
        return self.scene_builder_interview_service.step(session, answers)

    def scene_builder_interview_seed(self, story_slug: str, scene_slug: str) -> dict[str, object]:
        """Rebuild an imported candidate's Scene Builder interview seed."""
        data = self.load_scene_builder(story_slug, scene_slug).data
        return self.scene_candidate_import_service.interview_seed(data)

    def stage_scene_render(
        self,
        story_slug: str,
        scene_slug: str,
        render_target_id: str = "main",
        allow_stale_dependencies: bool = False,
    ) -> StoryRenderTask:
        """Compile and stage one story scene for the Render Console."""
        task = self.story_service.stage_scene_render(
            story_slug, scene_slug, render_target_id, allow_stale_dependencies
        )
        if self.config.ai_prompt_analysis_auto_queue_on_render:
            try:
                self.scene_prompt_analysis_service.queue(story_slug, scene_slug, render_target_id,
                                                         Path(task.ask_path) / "Final_Image_Prompt.md")
            except Exception as exc:
                from dataclasses import replace
                from zet.services.atomic_file_service import write_json_atomic
                warning = f"Render is staged, but prompt analysis could not be queued: {exc}. Retry analysis from Scene Builder."
                task = replace(task, warning=warning)
                try:
                    write_json_atomic(Path(task.ask_path) / "analysis_queue_error.json", {"error": str(exc), "recovery": warning})
                except OSError:
                    pass  # The returned task still carries the recovery message.
        self.refresh_library_index()
        return task

    def enable_background_subscene(self, story_slug: str, scene_slug: str) -> SceneBuilderDocument:
        return self._indexed_write(
            lambda: self.story_service.enable_background_subscene(story_slug, scene_slug)
        )

    def create_subscene(self, story_slug: str, scene_slug: str) -> tuple[SceneBuilderDocument, str]:
        return self._indexed_write(lambda: self.story_service.create_subscene(story_slug, scene_slug))

    def enable_element_subscene(self, story_slug: str, scene_slug: str, element_id: str) -> SceneBuilderDocument:
        return self._indexed_write(
            lambda: self.story_service.enable_element_subscene(story_slug, scene_slug, element_id)
        )

    def disable_scene_subscene(self, story_slug: str, scene_slug: str, target_id: str) -> SceneBuilderDocument:
        return self._indexed_write(
            lambda: self.story_service.disable_scene_subscene(story_slug, scene_slug, target_id)
        )

    def queue_scene_prompt_analysis(self, story_slug: str, scene_slug: str, render_target_id: str = "main") -> dict:
        return self._indexed_write(
            lambda: self.scene_prompt_analysis_service.queue(story_slug, scene_slug, render_target_id)
        )

    def queue_scene_prompt_analysis_second_opinion(
        self, story_slug: str, scene_slug: str, render_target_id: str = "main"
    ) -> dict:
        return self._indexed_write(
            lambda: self.scene_prompt_analysis_service.queue(
                story_slug, scene_slug, render_target_id, second_opinion=True
            )
        )

    def scene_prompt_analysis_status(
        self,
        story_slug: str,
        scene_slug: str,
        render_target_id: str = "main",
        *,
        current_prompt_text: str | None = None,
    ) -> dict:
        return self.scene_prompt_analysis_service.status(
            story_slug,
            scene_slug,
            render_target_id,
            current_prompt_text=current_prompt_text,
        )

    def list_scene_prompt_analyses(self, story_slug: str = "", scene_slug: str = "") -> list[dict]:
        return self.scene_prompt_analysis_service.list_statuses(story_slug, scene_slug)

    def create_story(self, title: str) -> StoryDocument:
        """Create a story folder and main story markdown file."""
        return self._indexed_write(lambda: self.story_service.create_story(title))

    def load_story(self, story_slug: str) -> StoryDocument:
        """Load one story markdown document."""
        return self.story_service.load_story(story_slug)

    def save_story(self, story_slug: str, text: str) -> StoryDocument:
        """Save one story markdown document."""
        return self._indexed_write(lambda: self.story_service.save_story(story_slug, text))

    def rename_story(self, story_slug: str, title: str) -> StoryDocument:
        """Rename one story without changing its stable slug."""
        return self._indexed_write(lambda: self.story_service.rename_story(story_slug, title))

    def reorder_stories(self, story_slugs: list[str]) -> list[StoryRecord]:
        """Persist the display order for all stories."""
        return self._indexed_write(lambda: self.story_service.reorder_stories(story_slugs))

    def load_story_settings(self, story_slug: str) -> dict:
        """Load one story settings JSON document."""
        path = self.story_service.get_story_settings_path_from_story_md(self.story_service.path_service.story_file_path(self.story_service.safe_slug(story_slug)))
        if not path.exists():
            self.story_service.save_story_settings(path, self.story_service.create_default_story_settings(self.story_service.path_service.story_file_path(self.story_service.safe_slug(story_slug))))
        return self.story_service.load_story_settings(path)

    def save_story_settings(self, story_slug: str, data: dict) -> dict:
        """Save one story settings JSON document."""
        path = self.story_service.get_story_settings_path_from_story_md(self.story_service.path_service.story_file_path(self.story_service.safe_slug(story_slug)))
        self.story_service.save_story_settings(path, data)
        self.refresh_library_index()
        return self.story_service.load_story_settings(path)

    def delete_story(self, story_slug: str) -> StoryGitResult:
        """Commit and delete one story folder."""
        result = self.story_service.delete_story(story_slug)
        self.image_catalog_service.rebind_source_prefix(f"scene:{story_slug}:")
        self.refresh_library_index()
        return result

    def story_git_status(self) -> StoryGitResult:
        """Fetch and return story git status."""
        return self.story_service.story_git_status()

    def story_git_pull(self) -> StoryGitResult:
        """Pull library changes and return story git output."""
        return self.story_service.story_git_pull()

    def story_git_commit(self) -> StoryGitResult:
        """Commit and push story changes."""
        return self.story_service.story_git_commit()

    def create_scene(self, story_slug: str, scene_name: str) -> SceneDocument:
        """Create a new scene markdown file from template."""
        return self._indexed_write(lambda: self.story_service.create_scene(story_slug, scene_name))

    def load_scene(self, story_slug: str, scene_slug: str) -> SceneDocument:
        """Load one scene markdown document."""
        return self.story_service.load_scene(story_slug, scene_slug)

    def save_scene(self, story_slug: str, scene_slug: str, text: str) -> SceneDocument:
        """Save one scene markdown document."""
        return self._indexed_write(lambda: self.story_service.save_scene(story_slug, scene_slug, text))

    def rename_scene(self, story_slug: str, scene_slug: str, title: str) -> SceneDocument:
        """Rename one scene without changing its stable slug."""
        return self._indexed_write(lambda: self.story_service.rename_scene(story_slug, scene_slug, title))

    def reorder_scenes(self, story_slug: str, scene_slugs: list[str]) -> list[SceneRecord]:
        """Persist the display order for one story's scenes."""
        return self._indexed_write(lambda: self.story_service.reorder_scenes(story_slug, scene_slugs))

    def move_scene(self, story_slug: str, scene_slug: str, target_story_slug: str) -> SceneDocument:
        """Move one scene and its artifacts to another story."""
        document = self.story_service.move_scene(story_slug, scene_slug, target_story_slug)
        self.image_catalog_service.rebind_source_prefix(
            f"scene:{story_slug}:{scene_slug}:",
            f"scene:{target_story_slug}:{scene_slug}:",
        )
        self.refresh_library_index()
        return document

    def delete_scene(self, story_slug: str, scene_slug: str) -> StoryGitResult:
        """Commit and delete one scene markdown and image."""
        result = self.story_service.delete_scene(story_slug, scene_slug)
        self.image_catalog_service.rebind_source_prefix(f"scene:{story_slug}:{scene_slug}:")
        self.refresh_library_index()
        return result

    def export_scene_builder_markdown(self, story_slug: str, scene_slug: str, data: dict) -> SceneDocument:
        """Export Scene Builder-managed markdown into the scene file."""
        return self._indexed_write(
            lambda: self.story_service.export_scene_markdown(story_slug, scene_slug, data)
        )

    def stage_scene_local_render_ask(
        self,
        manifest: dict,
        workspace: Path,
        *,
        allow_parallel: bool = False,
        seed: int | None = None,
        checkpoint: str | None = None,
        qwen_prompt_override: str | None = None,
        render_profile: str | None = None,
    ):
        return self.ai_proxy_service.stage_scene_local_render_ask(
            manifest,
            workspace,
            allow_parallel=allow_parallel,
            seed=seed,
            checkpoint=checkpoint,
            qwen_prompt_override=qwen_prompt_override,
            render_profile=render_profile,
        )

