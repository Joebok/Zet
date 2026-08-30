import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from zet.models.auxiliary_resource import AuxiliaryResource
from zet.repositories.auxiliary_resource_repository import AuxiliaryResourceRepository
from zet.repositories.image_catalog_repository import ImageCatalogRepository
from zet.services.config_service import Config
from zet.services.image_catalog_service import ImageCatalogService, ImageCatalogServiceError
from zet.services.path_service import PathService
from zet.services.story_service import StoryService, StoryServiceError


class EmptyRepository:
    def list_assets(self, character, phase):
        return []

    def list_identity_keys(self, character, phase):
        return []

    def list_sheets(self, character, phase):
        return []


class EmptyStoryService:
    def list_stories(self):
        return []

    def _asset_reference_pipeline_code(self, pipeline):
        return pipeline


class ImageCatalogServiceTests(unittest.TestCase):
    def make_service(self, root: Path):
        config = Config(
            base_library_path=str(root),
            base_character_path=str(root / "Characters"),
            base_asset_path=str(root / "Assets"),
            base_pipeline_path=str(root / "Pipelines"),
            base_ai_queue_path=str(root / "Queue"),
        )
        paths = PathService(config, root)
        aux_repository = AuxiliaryResourceRepository(paths)
        image_folder = paths.auxiliary_resource_folder_path("hell")
        image_folder.mkdir(parents=True)
        template = image_folder / "hell_Template.md"
        template.write_text(
            "<!-- ZET:BEGIN IDENTITY_PRESERVATION_SCENE -->\nshared hell\n<!-- ZET:END IDENTITY_PRESERVATION_SCENE -->\n"
            "<!-- ZET:BEGIN IDENTITY_PRESERVATION_COSTUME_SCENE -->\n<!-- ZET:END IDENTITY_PRESERVATION_COSTUME_SCENE -->\n",
            encoding="utf-8",
        )
        images = []
        for image_id in ("arena", "stairs"):
            image_path = image_folder / f"{image_id}.png"
            image_path.write_bytes(b"image")
            images.append({
                "image_id": image_id,
                "label": image_id.title(),
                "tag": f"{{{{AUX:place:hell:{image_id}}}}}",
                "image_path": str(image_path),
            })
        aux_repository.save_resource(AuxiliaryResource(
            resource_id="hell",
            category="place",
            label="Hell",
            resource_path=str(image_folder),
            template_path=str(template),
            updated_at="now",
            created_at="now",
            images=images,
        ))
        empty = EmptyRepository()
        service = ImageCatalogService(
            config,
            paths,
            ImageCatalogRepository(paths),
            empty,
            aux_repository,
            empty,
            empty,
            EmptyStoryService(),
        )
        return service, paths

    def test_aux_images_share_inheritance_but_support_independent_overrides(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service, _ = self.make_service(Path(temp_dir))
            items = service.list_items(include_base=True)
            self.assertEqual(2, len(items))
            self.assertEqual({"inherited"}, {item.identity_status for item in items})
            arena = next(item for item in items if item.tag.endswith(":arena}}"))

            service.update_item(arena.catalog_id, {
                "identity": {"mode": "override", "approved_text": "iron arena", "provenance": "manual"},
            })

            refreshed = {item.tag: item for item in service.list_items(include_base=True)}
            self.assertEqual("iron arena", refreshed[arena.tag].identity_text)
            self.assertEqual("shared hell", refreshed["{{AUX:place:hell:stairs}}"].identity_text)
            self.assertEqual("approved", refreshed[arena.tag].identity_status)

    def test_collections_keywords_filters_and_deletion_do_not_touch_images(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service, _ = self.make_service(Path(temp_dir))
            arena = next(item for item in service.list_items(include_base=True) if item.tag.endswith(":arena}}"))
            service.save_vocabulary("collections", "Hell")
            service.save_vocabulary("keywords", "lava")
            service.update_item(arena.catalog_id, {
                "semantic_category": "Place",
                "collection_ids": ["hell"],
                "keyword_ids": ["lava"],
            })

            self.assertEqual([arena.catalog_id], [item.catalog_id for item in service.list_items(collection="Hell")])
            self.assertEqual([arena.catalog_id], [item.catalog_id for item in service.list_items(keyword="lava")])
            image_path = Path(arena.image_path)
            service.delete_vocabulary("keywords", "lava")
            self.assertTrue(image_path.is_file())
            self.assertEqual([], service.get_item(arena.catalog_id).keywords)

    def test_ai_job_uses_structured_vision_output_and_stays_in_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service, paths = self.make_service(Path(temp_dir))
            item = service.list_items(include_base=True)[0]
            item = service.update_item(item.catalog_id, {"semantic_category": "Person"})

            queued = service.queue_description(item.catalog_id)

            self.assertEqual("ai_queued", queued.description_status)
            asks = list(service.ai_paths.file_proxy_client.task_paths("ask"))
            self.assertEqual(1, len(asks))
            manifest = json.loads((asks[0] / "ask_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("image_catalog_description", manifest["task_type"])
            self.assertEqual(item.catalog_id, manifest["catalog_id"])
            self.assertIn("response_schema", manifest)
            self.assertEqual(1, manifest["response_schema"]["properties"]["identity_preservation_scene"]["minLength"])
            self.assertEqual(1, manifest["response_schema"]["properties"]["identity_preservation_costume_scene"]["minLength"])
            self.assertEqual(1, len(manifest["image_files"]))
            prompt = (asks[0] / service.PROMPT_FILE).read_text(encoding="utf-8")
            self.assertIn("must not be blank", prompt)
            self.assertIn("Exclude clothing, armor, jewelry", prompt)
            self.assertIn("Exclude face, body, build", prompt)
            self.assertIn("For a Person this field is required and must not be blank", prompt)

            draft_path = paths.image_catalog_drafts_path() / f"{item.catalog_id}.json"
            draft_path.parent.mkdir(parents=True)
            draft_path.write_text(json.dumps({
                "identity_preservation_scene": "AI identity",
                "identity_preservation_costume_scene": "AI costume",
            }), encoding="utf-8")
            (asks[0] / "harvest_manifest.json").write_text("{}", encoding="utf-8")
            review = service.get_item(item.catalog_id)
            self.assertEqual("ai_review_required", review.description_status)
            self.assertEqual("shared hell", review.identity_text)
            with self.assertRaisesRegex(ImageCatalogServiceError, "Identity description is required"):
                service.approve_draft(item.catalog_id, "", "AI costume")
            self.assertTrue(draft_path.exists())
            with self.assertRaisesRegex(ImageCatalogServiceError, "Costume description is required"):
                service.approve_draft(item.catalog_id, "AI identity", "")
            self.assertTrue(draft_path.exists())

            approved = service.approve_draft(item.catalog_id, "edited identity", "", True)
            self.assertEqual("edited identity", approved.identity_text)
            self.assertEqual("approved", approved.description_status)
            self.assertFalse(draft_path.exists())

    def test_ai_job_for_identity_only_image_does_not_request_or_show_costume(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service, paths = self.make_service(Path(temp_dir))
            item = service.list_items(include_base=True)[0]

            queued = service.queue_description(item.catalog_id)

            self.assertEqual("ai_queued", queued.description_status)
            asks = list(service.ai_paths.file_proxy_client.task_paths("ask"))
            manifest = json.loads((asks[0] / "ask_manifest.json").read_text(encoding="utf-8"))
            schema = manifest["response_schema"]
            self.assertEqual(["identity_preservation_scene"], schema["required"])
            self.assertEqual(["identity_preservation_scene"], list(schema["properties"]))
            prompt = (asks[0] / service.PROMPT_FILE).read_text(encoding="utf-8")
            self.assertNotIn("costume", prompt.lower())

            draft_path = paths.image_catalog_drafts_path() / f"{item.catalog_id}.json"
            draft_path.parent.mkdir(parents=True)
            draft_path.write_text(json.dumps({
                "identity_preservation_scene": "AI place identity",
                "identity_preservation_costume_scene": "Should not be shown",
            }), encoding="utf-8")
            (asks[0] / "harvest_manifest.json").write_text("{}", encoding="utf-8")

            review = service.get_item(item.catalog_id)
            self.assertEqual("ai_review_required", review.description_status)
            self.assertEqual("AI place identity", review.ai_draft_identity)
            self.assertEqual("", review.ai_draft_costume)

    def test_story_compiler_sources_use_the_selected_images_approved_text(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service, paths = self.make_service(Path(temp_dir))
            story = StoryService(
                paths,
                service.asset_repository,
                service.auxiliary_resource_repository,
                service.identity_key_repository,
                service.turnaround_repository,
            )
            service.story_service = story
            story.image_catalog_service = service
            arena = next(item for item in service.list_items(include_base=True) if item.tag.endswith(":arena}}"))
            service.update_item(arena.catalog_id, {
                "identity": {"mode": "override", "approved_text": "arena-specific identity"},
            })
            data = {"scene_elements": [{
                "id": "hell",
                "display_name": "Hell",
                "resource_type": "Place",
                "aux_resource_id": "hell",
                "reference_images": [{"tag": arena.tag}],
            }]}

            sources = story._resolve_scene_element_sources(data)

            self.assertEqual("arena-specific identity", sources["hell"]["identity_preservation_core"])
            self.assertEqual(arena.catalog_id, sources["hell"]["catalog_id"])

            service.update_item(arena.catalog_id, {
                "identity": {"mode": "override", "approved_text": ""},
            })
            with self.assertRaisesRegex(StoryServiceError, "needs identity description text"):
                story._resolve_scene_element_sources(data)

    def test_subscene_inherits_identity_from_composition_notes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            service, paths = self.make_service(Path(temp_dir))
            target_id = "travelers_subscene"
            locked_path = paths.scene_subscene_locked_path("Demo", "Opening", target_id)
            locked_path.parent.mkdir(parents=True)
            locked_path.write_bytes(b"image")
            document = SimpleNamespace(data={
                "scene_elements": [{
                    "id": "travelers",
                    "resource_type": "Person",
                    "aux_resource_id": "",
                }],
                "subscenes": [{
                    "id": target_id,
                    "name": "Travelers",
                    "kind": "element",
                    "anchor_element_id": "travelers",
                    "setup": {"composition": {"composition_notes": "A coherent roped group of travelers."}},
                }],
            })
            service.story_service = SimpleNamespace(
                list_stories=lambda: [SimpleNamespace(slug="Demo", title="Demo")],
                list_scenes=lambda story_slug: [SimpleNamespace(slug="Opening", title="Opening")],
                scene_image_path=lambda story_slug, scene_slug: paths.scene_locked_image_path(story_slug, scene_slug),
                load_scene_builder_data=lambda story_slug, scene_slug: document,
                _canonical_element_source_sections=lambda element: {},
                scene_render_target_service=SimpleNamespace(
                    image_tag=lambda story_slug, scene_slug, render_target_id: (
                        f"{{{{SCENE_RENDER:{story_slug}:{scene_slug}:{render_target_id}}}}}"
                    )
                ),
            )

            item = next(item for item in service.list_items() if item.subscene_id == target_id)

            self.assertEqual("A coherent roped group of travelers.", item.identity_text)
            self.assertEqual("inherited", item.identity_status)
            self.assertEqual("Composite/Scene", item.semantic_category)
            self.assertEqual("not_applicable", item.costume_status)

            item = service.update_item(item.catalog_id, {"costume": {"mode": "inherit", "approved_text": ""}})

            self.assertEqual("not_applicable", item.costume_status)


if __name__ == "__main__":
    unittest.main()
