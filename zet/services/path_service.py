from pathlib import Path, PureWindowsPath

from zet.models.asset import Asset
from zet.services.config_service import Config


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class PathService:
    def __init__(self, config: Config, project_root: str | Path = PROJECT_ROOT):
        """Create a path service from loaded configuration."""
        self.config = config
        self.project_root = Path(project_root)

    def character_path(self, character: str, phase: str) -> Path:
        """Return the character phase folder."""
        return Path(self.config.base_character_path) / character / phase

    def character_template_path(self, character: str, phase: str) -> Path:
        """Return the canonical character markdown path for a phase."""
        return self.character_path(character, phase) / "Character.md"

    def shared_library_path(self, *parts: str) -> Path:
        """Return a path inside the source-controlled shared library."""
        return self.project_root.joinpath("Shared_Library", *parts)

    def shared_character_path(self) -> Path:
        """Return the shared character template folder."""
        return self.shared_library_path("Characters", "_Shared")

    def shared_costume_template_path(self) -> Path:
        """Return the shared costume markdown template path."""
        return self.shared_character_path() / "Costume_Template.md"

    def shared_expression_template_path(self) -> Path:
        """Return the shared expression markdown template path."""
        return self.shared_character_path() / "Expression_Template.md"

    def library_path(self, *parts: str) -> Path:
        """Return a path inside the configured library root."""
        return Path(self.config.base_library_path).joinpath(*parts)

    def _path_parts(self, path: str | Path) -> tuple[str, ...]:
        """Return path parts while accepting stored POSIX or Windows separators."""
        text = str(path)
        if "\\" in text:
            return PureWindowsPath(text).parts
        return Path(text).parts

    def resolve_path(self, path: str | Path) -> Path:
        """Resolve absolute, project-relative, and legacy _Lib paths."""
        parts = self._path_parts(path)
        if parts and parts[0].endswith(":\\"):
            library_name = Path(self.config.base_library_path).name
            for index, part in enumerate(parts):
                if part == library_name:
                    return self.library_path(*parts[index + 1:])
            return Path(*parts)
        raw_path = Path(path)
        if raw_path.is_absolute():
            return raw_path
        if parts and parts[0] == "_Lib":
            return self.library_path(*parts[1:])
        if parts and parts[0] in {"Characters", "Assets", "Pipelines", "AuxiliaryResources", "Stories"}:
            return self.library_path(*parts)
        return self.project_root.joinpath(*parts)

    def character_asset_path(self, character: str, phase: str) -> Path:
        """Return the character phase asset folder."""
        return Path(self.config.base_asset_path) / character / phase

    def character_backup_path(self, character: str, phase: str) -> Path:
        """Return the character phase backup folder."""
        return self.character_path(character, phase) / "_backup"

    def pipeline_base_path(self, character: str, phase: str) -> Path:
        """Return the character phase pipeline folder."""
        return Path(self.config.base_pipeline_path) / character / phase

    def pipeline_path(self, asset: Asset) -> Path:
        """Return the pipeline work folder for an asset."""
        head_view = asset.head_view if asset.head_view and asset.head_view.strip() else "_"
        return (
            self.pipeline_base_path(asset.character, asset.phase)
            / asset.pipeline
            / asset.body_view
            / head_view
            / f"Asset_{asset.asset_id}"
        )

    def candidate_image_path(self, asset: Asset) -> Path:
        """Return the expected candidate image path for an asset."""
        if not asset.final_image_output:
            raise ValueError(f"Asset {asset.asset_id} has no final_image_output")
        return self.pipeline_path(asset) / asset.final_image_output

    def locked_image_path(self, asset: Asset) -> Path:
        """Return the locked image path for an asset."""
        if not asset.final_image_output:
            raise ValueError(f"Asset {asset.asset_id} has no final_image_output")
        return self.character_asset_path(asset.character, asset.phase) / asset.final_image_output

    def turnaround_work_path(self, character: str, phase: str, turnaround_id: str) -> Path:
        """Return the pipeline work folder for a turnaround sheet."""
        return self.pipeline_base_path(character, phase) / "Turnaround" / turnaround_id

    def turnaround_locked_image_path(self, character: str, phase: str, turnaround_id: str) -> Path:
        """Return the locked reference image path for a turnaround sheet."""
        return self.character_asset_path(character, phase) / "Turnarounds" / f"{turnaround_id}.png"

    def identity_key_image_path(self, character: str, phase: str, identity_key_id: str) -> Path:
        """Return the locked image path for an identity key."""
        return self.character_asset_path(character, phase) / "IdentityKeys" / f"{identity_key_id}.png"

    def auxiliary_resource_root(self) -> Path:
        """Return the global auxiliary resource folder."""
        return Path(self.config.base_character_path).parent / "AuxiliaryResources"

    def auxiliary_resource_inventory_path(self) -> Path:
        """Return the global auxiliary resource inventory path."""
        return self.auxiliary_resource_root() / "AuxiliaryResources.json"

    def auxiliary_resource_inventory_default_path(self) -> Path:
        """Return the source-controlled default auxiliary resource inventory."""
        return self.shared_library_path("AuxiliaryResources", "AuxiliaryResources.json")

    def auxiliary_resource_image_path(self, category: str, resource_id: str, extension: str = ".png") -> Path:
        """Return the image path for a global auxiliary resource."""
        return self.auxiliary_resource_root() / "Images" / category / f"{resource_id}{extension}"

    def auxiliary_resource_folder_path(self, resource_id: str) -> Path:
        """Return one auxiliary resource folder path."""
        return self.auxiliary_resource_root() / "Images" / str(resource_id or "").strip()

    def auxiliary_resource_template_source_path(self) -> Path:
        """Return the shared auxiliary resource template path."""
        return self.shared_library_path("AuxiliaryResources", "_Shared", "AuxResource_Template.md")

    def auxiliary_resource_folder_image_path(self, resource_id: str, image_label: str, extension: str = ".png") -> Path:
        """Return an image path inside one auxiliary resource folder."""
        safe = str(image_label or "").strip()
        return self.auxiliary_resource_folder_path(resource_id) / f"{safe}{extension}"

    def image_catalog_root(self) -> Path:
        """Return the logical image-catalog metadata folder."""
        return Path(self.config.base_library_path) / "ImageCatalog"

    def image_catalog_inventory_path(self) -> Path:
        """Return the logical image-catalog overlay path."""
        return self.image_catalog_root() / "ImageCatalog.json"

    def image_catalog_drafts_path(self) -> Path:
        """Return the folder containing harvested AI description drafts."""
        return self.image_catalog_root() / "Drafts"

    def image_catalog_images_path(self) -> Path:
        """Return the folder owned by user-imported catalog images."""
        return self.image_catalog_root() / "Images"

    def image_catalog_trash_path(self) -> Path:
        """Return recoverable storage for replaced and deleted catalog images."""
        return self.image_catalog_root() / "_trash"

    def costume_template_path(self, character: str, phase: str, costume_name: str) -> Path:
        """Return the markdown template path for a costume name."""
        safe = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in str(costume_name).strip())
        safe = "_".join(part for part in safe.replace("-", "_").split("_") if part)
        return self.character_path(character, phase) / f"Costume_{safe or 'Costume'}.md"

    def expressions_path(self, character: str, phase: str) -> Path:
        """Return the expression definition folder for a character phase."""
        return self.character_path(character, phase) / "Expressions"

    def scene_appearances_path(self, character: str, phase: str) -> Path:
        """Return the Scene Appearance definition folder for a character phase."""
        return self.character_path(character, phase) / "SceneAppearances"

    def scene_appearance_definition_path(self, character: str, phase: str, appearance_id: str) -> Path:
        """Return one structured Scene Appearance definition path."""
        return self.scene_appearances_path(character, phase) / f"{appearance_id}.json"

    def stories_path(self) -> Path:
        """Return the stories library root."""
        return self.library_path("Stories")

    def shared_story_template_path(self) -> Path:
        """Return the shared story markdown template path."""
        return self.shared_library_path("Stories", "_Story_Template.md")

    def shared_scene_template_path(self) -> Path:
        """Return the shared scene markdown template path."""
        return self.shared_library_path("Stories", "_Scene_Template.md")

    def shared_story_index_path(self) -> Path:
        """Return the source-controlled default story ordering index."""
        return self.shared_library_path("Stories", "_Story_Index.json")

    def story_index_path(self) -> Path:
        """Return the persisted story ordering index path."""
        return self.stories_path() / "_Story_Index.json"

    def story_folder_path(self, story_slug: str) -> Path:
        """Return the folder path for one story slug."""
        return self.stories_path() / str(story_slug or "").strip()

    def story_file_path(self, story_slug: str) -> Path:
        """Return the main markdown file path for one story slug."""
        safe_slug = str(story_slug or "").strip()
        return self.story_folder_path(safe_slug) / f"{safe_slug}.md"

    def scene_file_path(self, story_slug: str, scene_slug: str) -> Path:
        """Return one scene markdown path within a story folder."""
        return self.story_folder_path(story_slug) / f"{str(scene_slug or '').strip()}.md"

    def story_pipeline_path(self, story_slug: str, scene_slug: str) -> Path:
        """Return the pipeline work folder for one story scene."""
        return self.library_path("Pipelines", "Stories", story_slug, scene_slug)

    def scene_locked_image_path(self, story_slug: str, scene_slug: str) -> Path:
        """Return the published image path for one story scene."""
        return self.story_folder_path(story_slug) / f"{str(scene_slug or '').strip()}.png"

    def scene_candidate_image_path(self, story_slug: str, scene_slug: str) -> Path:
        """Return the pending review image path for one story scene."""
        return self.story_pipeline_path(story_slug, scene_slug) / "Candidate" / f"{str(scene_slug or '').strip()}.png"

    def scene_locked_backups_path(self, story_slug: str, scene_slug: str) -> Path:
        """Return the locked-image backup folder for one story scene."""
        return self.story_pipeline_path(story_slug, scene_slug) / "Locked_Backups"

    def scene_render_review_comment_path(self, story_slug: str, scene_slug: str) -> Path:
        """Return the review comment path for one scene candidate."""
        return self.story_pipeline_path(story_slug, scene_slug) / "Candidate" / "Render_Review_Comment.md"

    def scene_subscene_pipeline_path(self, story_slug: str, scene_slug: str, target_id: str) -> Path:
        """Return the pipeline folder for one scene subscene target."""
        return self.story_pipeline_path(story_slug, scene_slug) / "Subscenes" / str(target_id or "").strip()

    def scene_subscene_locked_path(self, story_slug: str, scene_slug: str, target_id: str) -> Path:
        """Return the stable locked image path for one scene subscene."""
        return self.story_folder_path(story_slug) / "_Subscene_Renders" / scene_slug / f"{target_id}.png"

    def scene_subscene_locked_metadata_path(self, story_slug: str, scene_slug: str, target_id: str) -> Path:
        """Return locked-render provenance for one scene subscene."""
        return self.scene_subscene_locked_path(story_slug, scene_slug, target_id).with_suffix(".render.json")

    def scene_subscene_candidate_path(self, story_slug: str, scene_slug: str, target_id: str) -> Path:
        """Return the pending image path for one scene subscene."""
        return self.scene_subscene_pipeline_path(story_slug, scene_slug, target_id) / "Candidate" / f"{target_id}.png"

    def scene_subscene_comment_path(self, story_slug: str, scene_slug: str, target_id: str) -> Path:
        """Return the review comment path for one scene subscene."""
        return self.scene_subscene_pipeline_path(story_slug, scene_slug, target_id) / "Candidate" / "Render_Review_Comment.md"

    def scene_subscene_locked_backups_path(self, story_slug: str, scene_slug: str, target_id: str) -> Path:
        """Return locked-image backups for one scene subscene."""
        return self.scene_subscene_pipeline_path(story_slug, scene_slug, target_id) / "Locked_Backups"

    def zines_path(self) -> Path:
        """Return the generated zine asset folder."""
        return Path(self.config.base_asset_path) / "Zines"
