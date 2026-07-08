from pathlib import Path

from zet.models.asset import Asset
from zet.services.config_service import Config


class PathService:
    def __init__(self, config: Config):
        """Create a path service from loaded configuration."""
        self.config = config

    def character_path(self, character: str, phase: str) -> Path:
        """Return the character phase folder."""
        return Path(self.config.base_character_path) / character / phase

    def shared_character_path(self) -> Path:
        """Return the shared character template folder."""
        return Path(self.config.base_character_path) / "_Shared"

    def shared_costume_template_path(self) -> Path:
        """Return the shared costume markdown template path."""
        return self.shared_character_path() / "Costume_Template.md"

    def shared_expression_template_path(self) -> Path:
        """Return the shared expression markdown template path."""
        return self.shared_character_path() / "Expression_Template.md"

    def library_path(self, *parts: str) -> Path:
        """Return a path inside the configured library root."""
        return Path(self.config.base_library_path).joinpath(*parts)

    def resolve_path(self, path: str | Path) -> Path:
        """Resolve absolute, project-relative, and legacy _Lib paths."""
        raw_path = Path(path)
        if raw_path.is_absolute():
            return raw_path
        parts = raw_path.parts
        if parts and parts[0] == "_Lib":
            return self.library_path(*parts[1:])
        if parts and parts[0] in {"Characters", "Assets", "Pipelines", "AuxiliaryResources", "Stories"}:
            return self.library_path(*parts)
        return raw_path

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

    def auxiliary_resource_image_path(self, category: str, resource_id: str, extension: str = ".png") -> Path:
        """Return the image path for a global auxiliary resource."""
        return self.auxiliary_resource_root() / "Images" / category / f"{resource_id}{extension}"

    def costume_template_path(self, character: str, phase: str, costume_name: str) -> Path:
        """Return the markdown template path for a costume name."""
        safe = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in str(costume_name).strip())
        safe = "_".join(part for part in safe.replace("-", "_").split("_") if part)
        return self.character_path(character, phase) / f"Costume_{safe or 'Costume'}.md"

    def expressions_path(self, character: str, phase: str) -> Path:
        """Return the expression definition folder for a character phase."""
        return self.character_path(character, phase) / "Expressions"

    def gpt_helper_prompt_path(self, character: str, phase: str) -> Path:
        """Return the GPT helper prompt config path for a character phase."""
        return self.character_path(character, phase) / "GPT_Helper_Prompts.json"

    def stories_path(self) -> Path:
        """Return the stories library root."""
        return self.library_path("Stories")

    def shared_story_template_path(self) -> Path:
        """Return the shared story markdown template path."""
        return self.stories_path() / "_Story_Template.md"

    def shared_scene_template_path(self) -> Path:
        """Return the shared scene markdown template path."""
        return self.stories_path() / "_Scene_Template.md"

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
