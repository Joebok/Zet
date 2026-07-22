from __future__ import annotations

import copy
from datetime import datetime
import json
import re
import shutil
import subprocess
from pathlib import Path

from zet.models.asset import Asset
from zet.models.auxiliary_resource import AuxiliaryResource
from zet.models.identity_key import IdentityKey
from zet.models.story import (
    ImageReferenceRow,
    SceneBuilderDocument,
    SceneDocument,
    SceneRecord,
    StoryDocument,
    StoryGitResult,
    StoryRecord,
    StoryRenderTask,
)
from zet.repositories.asset_repository import AssetRepository
from zet.repositories.auxiliary_resource_repository import AuxiliaryResourceRepository
from zet.repositories.identity_key_repository import IdentityKeyRepository
from zet.services.auxiliary_resource_service import AUXILIARY_RESOURCE_CATEGORIES
from zet.services.path_service import PathService
from zet.services.scene_document_service import SceneDocumentService
from zet.services.story_reference_service import StoryReferenceService
from zet.services.story_render_service import StoryRenderService


class StoryServiceError(Exception):
    """Report story and scene workflow failures."""


class StoryService:
    """Manage story folders, scene markdown files, and scene image references."""

    def __init__(
        self,
        path_service: PathService,
        asset_repository: AssetRepository,
        auxiliary_resource_repository: AuxiliaryResourceRepository,
        identity_key_repository: IdentityKeyRepository | None = None,
    ):
        """Create a story service with filesystem and repository access."""
        self.path_service = path_service
        self.asset_repository = asset_repository
        self.auxiliary_resource_repository = auxiliary_resource_repository
        self.identity_key_repository = identity_key_repository
        self.scene_document_service = SceneDocumentService(self, StoryServiceError)
        self.story_reference_service = StoryReferenceService(
            path_service,
            asset_repository,
            auxiliary_resource_repository,
            identity_key_repository,
            StoryServiceError,
        )
        self.story_render_service = StoryRenderService(
            self,
            self.story_reference_service,
            StoryRenderTask,
            StoryServiceError,
        )

    def safe_slug(self, value: str) -> str:
        """Return a filename-safe slug for stories and scenes."""
        text = str(value or "").strip()
        safe = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-")
        return safe or "Untitled"

    def _story_title_from_slug(self, slug: str) -> str:
        """Return a readable title from a story slug."""
        return str(slug or "").replace("-", " ").strip() or "Untitled"

    def _scene_title_from_slug(self, slug: str) -> str:
        """Return a readable scene title from a scene slug."""
        return self._story_title_from_slug(slug)

    def _extract_first_metadata_field(self, text: str, label: str) -> str:
        """Return the first matching markdown metadata field value."""
        match = re.search(rf"(?im)^\s*{re.escape(label)}\s*:\s*(.+?)\s*$", text or "")
        if not match:
            return ""
        return str(match.group(1)).strip().strip("`").strip().strip("[]").strip()

    def _extract_bounded_section(self, text: str, section_name: str) -> str:
        """Return the contents of one bounded compiler section."""
        pattern = re.compile(
            rf"<!-- ZET:BEGIN {re.escape(section_name)} -->\s*(.*?)\s*<!-- ZET:END {re.escape(section_name)} -->",
            re.DOTALL,
        )
        match = pattern.search(text or "")
        return str(match.group(1)).strip() if match else ""

    def _source_section(self, path: Path, section_name: str) -> str:
        """Read one compiler section from a markdown source."""
        if not path.is_file():
            return ""
        return self._extract_bounded_section(path.read_text(encoding="utf-8"), section_name)

    def _element_source_sections(self, element: dict) -> dict:
        resource_type = str(element.get("resource_type") or "").strip()
        if resource_type == "Character":
            character = str(element.get("character") or element.get("display_name") or "").strip()
            phase = str(element.get("phase") or "").strip()
            costume = str(element.get("costume") or "").strip()
            if not character or not phase:
                return {}
            character_template = self.path_service.character_path(character, phase) / "Character_Image_Template.md"
            costume_template = self.path_service.costume_template_path(character, phase, costume) if costume else Path()
            return {
                "identity_preservation_core": self._source_section(character_template, "IDENTITY_PRESERVATION_SCENE"),
                "identity_preservation_costume": self._source_section(costume_template, "IDENTITY_PRESERVATION_COSTUME_SCENE"),
                "identity_source": self._library_relative_path(character_template),
                "costume_source": self._library_relative_path(costume_template) if costume else "",
            }
        if resource_type in {"Person", "Place", "Object"}:
            resource_id = str(element.get("aux_resource_id") or "").strip()
            if not resource_id:
                return {}
            resource = self.auxiliary_resource_repository.get_resource(resource_id)
            template = self.path_service.resolve_path(resource.template_path)
            sections = {
                "identity_preservation_core": self._source_section(template, "IDENTITY_PRESERVATION_SCENE"),
                "identity_source": self._library_relative_path(template),
            }
            if resource_type == "Person":
                sections["identity_preservation_costume"] = self._source_section(template, "IDENTITY_PRESERVATION_COSTUME_SCENE")
                sections["costume_source"] = self._library_relative_path(template)
            return sections
        return {}

    def _resolve_scene_element_sources(self, data: dict) -> dict:
        resolved = {}
        for element in data.get("scene_elements") or []:
            if not isinstance(element, dict):
                continue
            sections = self._element_source_sections(element)
            if sections:
                element["resolved_source_sections"] = sections
                resolved[str(element.get("id") or "")] = sections
        return resolved

    def _git_repo_path(self) -> Path:
        """Return the library git repository path."""
        return Path(self.path_service.config.base_library_path)

    def _run_git(self, args: list[str]) -> subprocess.CompletedProcess:
        """Run one git command in the library repository."""
        return subprocess.run(
            ["git", "-C", str(self._git_repo_path()), *args],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            text=True,
            timeout=120,
        )

    def _git_output(self, label: str, result: subprocess.CompletedProcess) -> str:
        """Format one git command result for dashboard display."""
        output = "\n".join(part for part in [result.stdout.strip(), result.stderr.strip()] if part)
        if not output:
            output = "(no output)"
        return f"$ git {label}\n{output}"

    def _story_git_conflict(self, output: str) -> bool:
        """Return whether git output appears to report conflicts."""
        text = str(output or "").lower()
        return any(term in text for term in ("conflict", "unmerged", "merge failed", "fix conflicts"))

    def story_git_has_changes(self) -> bool:
        """Return whether the Stories folder has uncommitted changes."""
        result = self._run_git(["status", "--porcelain", "--", "Stories"])
        return bool(result.stdout.strip())

    def story_git_status(self) -> StoryGitResult:
        """Fetch and return story git status."""
        fetch = self._run_git(["fetch"])
        status = self._run_git(["status", "--short", "--", "Stories"])
        output = "\n\n".join([self._git_output("fetch", fetch), self._git_output("status --short -- Stories", status)])
        conflict = self._story_git_conflict(output)
        return StoryGitResult(output=output, has_story_changes=bool(status.stdout.strip()), conflict=conflict)

    def story_git_pull(self) -> StoryGitResult:
        """Pull library changes and return git output."""
        pull = self._run_git(["pull"])
        output = self._git_output("pull", pull)
        return StoryGitResult(output=output, has_story_changes=self.story_git_has_changes(), conflict=self._story_git_conflict(output))

    def story_git_commit(self) -> StoryGitResult:
        """Commit and push all Stories folder changes."""
        add = self._run_git(["add", "Stories"])
        staged = self._run_git(["diff", "--cached", "--quiet", "--", "Stories"])
        outputs = [self._git_output("add Stories", add)]
        if staged.returncode == 0:
            outputs.append("No story changes to commit.")
            output = "\n\n".join(outputs)
            return StoryGitResult(output=output, has_story_changes=self.story_git_has_changes(), conflict=False)
        message = f"Zet Story Edits {datetime.now().strftime('%m/%d/%Y %H:%M')}"
        commit = self._run_git(["commit", "-m", message])
        push = self._run_git(["push"]) if commit.returncode == 0 else None
        outputs.append(self._git_output(f'commit -m "{message}"', commit))
        if push:
            outputs.append(self._git_output("push", push))
        output = "\n\n".join(outputs)
        return StoryGitResult(output=output, has_story_changes=self.story_git_has_changes(), conflict=self._story_git_conflict(output))

    def _replace_metadata_field(self, text: str, label: str, value: str) -> str:
        """Replace or insert one markdown metadata field."""
        replacement = f"{label}: `[{value}]`"
        pattern = re.compile(rf"(?im)^\s*{re.escape(label)}\s*:\s*.+?\s*$")
        if pattern.search(text):
            return pattern.sub(replacement, text, count=1)
        lines = text.splitlines()
        lines.insert(0, replacement)
        return "\n".join(lines)

    def _replace_bounded_section(self, text: str, section_name: str, value: str) -> str:
        """Replace the contents of one bounded compiler section."""
        pattern = re.compile(
            rf"(<!-- ZET:BEGIN {re.escape(section_name)} -->\s*)(.*?)(\s*<!-- ZET:END {re.escape(section_name)} -->)",
            re.DOTALL,
        )
        if not pattern.search(text):
            raise StoryServiceError(f"Missing compiler section: {section_name}")
        return pattern.sub(rf"\1{value}\3", text, count=1)

    def _require_template(self, path: Path, label: str) -> str:
        """Return template text or raise when the template file is missing."""
        if not path.exists() or not path.is_file():
            raise StoryServiceError(f"{label} template not found: {path}")
        return path.read_text(encoding="utf-8")

    def _story_record(self, story_slug: str) -> StoryRecord:
        """Build a story record from one story folder slug."""
        folder_path = self.path_service.story_folder_path(story_slug)
        story_file_path = self.path_service.story_file_path(story_slug)
        title = self._story_title_from_slug(story_slug)
        if story_file_path.exists():
            title_text = self._extract_first_metadata_field(story_file_path.read_text(encoding="utf-8"), "Title")
            if title_text:
                title = title_text
        return StoryRecord(
            slug=story_slug,
            title=title,
            folder_path=str(folder_path),
            story_file_path=str(story_file_path),
            story_file_exists=story_file_path.exists(),
        )

    def _scene_record(self, story_slug: str, path: Path) -> SceneRecord:
        """Build a scene record from one scene markdown path."""
        text = path.read_text(encoding="utf-8")
        title = self._extract_scene_line(text) or self._scene_title_from_slug(path.stem)
        return SceneRecord(
            story_slug=story_slug,
            slug=path.stem,
            title=title,
            path=str(path),
        )

    def _scene_json_record(self, story_slug: str, path: Path) -> SceneRecord:
        """Build a scene record from one Scene Builder V3 JSON path."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
        scene = data.get("scene", {}) if isinstance(data, dict) else {}
        slug = str(scene.get("slug") or path.name.removesuffix(".scene.json"))
        return SceneRecord(
            story_slug=story_slug,
            slug=slug,
            title=str(scene.get("name") or self._scene_title_from_slug(slug)),
            path=str(path),
        )

    def _extract_scene_line(self, text: str) -> str:
        """Return the scene line value from a scene template."""
        return self._extract_first_metadata_field(text, "Scene")

    def list_stories(self) -> list[StoryRecord]:
        """List all user story folders in the library."""
        root = self.path_service.stories_path()
        if not root.exists():
            root.mkdir(parents=True, exist_ok=True)
        records = []
        for folder in sorted(item for item in root.iterdir() if item.is_dir() and not item.name.startswith("_")):
            records.append(self._story_record(folder.name))
        return records

    def create_story(self, title: str) -> StoryDocument:
        """Create a new story folder and main markdown file from template."""
        cleaned_title = str(title or "").strip()
        if not cleaned_title:
            raise StoryServiceError("Story title is required.")
        story_slug = self.safe_slug(cleaned_title)
        folder_path = self.path_service.story_folder_path(story_slug)
        story_file_path = self.path_service.story_file_path(story_slug)
        if folder_path.exists() and not folder_path.is_dir():
            raise StoryServiceError(f"Story path exists and is not a folder: {folder_path}")
        folder_path.mkdir(parents=True, exist_ok=True)
        if not story_file_path.exists():
            template = self._require_template(self.path_service.shared_story_template_path(), "Story")
            template = self._replace_metadata_field(template, "Title", cleaned_title)
            if self._extract_bounded_section(template, "STORY_TITLE"):
                template = self._replace_bounded_section(template, "STORY_TITLE", cleaned_title)
            story_file_path.write_text(template.rstrip() + "\n", encoding="utf-8")
        story_settings_path = self.get_story_settings_path_from_story_md(story_file_path)
        if not story_settings_path.exists():
            self.save_story_settings(story_settings_path, self.create_default_story_settings(story_file_path))
        return self.load_story(story_slug)

    def load_story(self, story_slug: str) -> StoryDocument:
        """Load one story document, creating it from template if missing."""
        safe_slug = self.safe_slug(story_slug)
        story_file_path = self.path_service.story_file_path(safe_slug)
        if not story_file_path.exists():
            return self.create_story(self._story_title_from_slug(safe_slug))
        text = story_file_path.read_text(encoding="utf-8")
        record = self._story_record(safe_slug)
        return StoryDocument(record=record, text=text, validation_errors=self.validate_story_text(text))

    def validate_story_text(self, text: str) -> list[str]:
        """Validate human story markdown."""
        errors: list[str] = []
        title = self._extract_first_metadata_field(text, "Title")
        if not title or title.lower() == "story title":
            errors.append("Title must be filled in.")
        return errors

    def save_story(self, story_slug: str, text: str) -> StoryDocument:
        """Save one story markdown file and return validation warnings."""
        safe_slug = self.safe_slug(story_slug)
        story_file_path = self.path_service.story_file_path(safe_slug)
        story_file_path.parent.mkdir(parents=True, exist_ok=True)
        story_file_path.write_text(str(text or "").rstrip() + "\n", encoding="utf-8")
        return self.load_story(safe_slug)

    def delete_story(self, story_slug: str) -> StoryGitResult:
        """Commit the current story state, then delete one story folder."""
        safe_slug = self.safe_slug(story_slug)
        folder_path = self.path_service.story_folder_path(safe_slug)
        if not folder_path.exists() or not folder_path.is_dir():
            raise StoryServiceError(f"Story folder not found: {folder_path}")
        commit = self.story_git_commit()
        if commit.conflict or commit.has_story_changes:
            raise StoryServiceError(f"Story delete aborted; commit current story changes first.\n\n{commit.output}")
        shutil.rmtree(folder_path)
        return commit

    def list_scenes(self, story_slug: str) -> list[SceneRecord]:
        """List all scene markdown files for one story."""
        safe_slug = self.safe_slug(story_slug)
        folder_path = self.path_service.story_folder_path(safe_slug)
        if not folder_path.exists():
            return []
        story_file_name = f"{safe_slug}.md"
        records = []
        seen_slugs = set()
        for path in sorted(item for item in folder_path.iterdir() if item.is_file() and item.suffix.lower() == ".md"):
            if path.name.startswith("_") or path.name == story_file_name:
                continue
            record = self._scene_record(safe_slug, path)
            records.append(record)
            seen_slugs.add(record.slug)
        for path in sorted(folder_path.glob("*.scene.json")):
            record = self._scene_json_record(safe_slug, path)
            if record.slug not in seen_slugs:
                records.append(record)
        return records

    def create_scene(self, story_slug: str, scene_name: str) -> SceneDocument:
        """Create a new scene markdown file from template."""
        safe_story_slug = self.safe_slug(story_slug)
        cleaned_name = str(scene_name or "").strip()
        if not cleaned_name:
            raise StoryServiceError("Scene name is required.")
        scene_slug = self.safe_slug(cleaned_name)
        story_folder = self.path_service.story_folder_path(safe_story_slug)
        if not story_folder.exists():
            raise StoryServiceError(f"Story folder does not exist: {story_folder}")
        scene_path = self.path_service.scene_file_path(safe_story_slug, scene_slug)
        if not scene_path.exists():
            template = self._require_template(self.path_service.shared_scene_template_path(), "Scene")
            template = re.sub(r"(?im)^Scene:\s*.+?$", f"Scene: `[{cleaned_name}]`", template, count=1)
            scene_path.write_text(template.rstrip() + "\n", encoding="utf-8")
        scene_json_path = self.scene_builder_json_path(safe_story_slug, scene_slug)
        if not scene_json_path.exists():
            self.save_scene_v3(scene_json_path, self.create_default_scene_builder_data(safe_story_slug, scene_slug))
        return self.load_scene(safe_story_slug, scene_slug)

    def load_scene(self, story_slug: str, scene_slug: str) -> SceneDocument:
        """Load one scene markdown file."""
        safe_story_slug = self.safe_slug(story_slug)
        safe_scene_slug = self.safe_slug(scene_slug)
        path = self.path_service.scene_file_path(safe_story_slug, safe_scene_slug)
        if not path.exists():
            json_path = self.scene_builder_json_path(safe_story_slug, safe_scene_slug)
            if json_path.exists():
                story = self._story_record(safe_story_slug)
                return SceneDocument(story=story, record=self._scene_json_record(safe_story_slug, json_path), text="", validation_errors=[])
            return self.create_scene(safe_story_slug, self._scene_title_from_slug(safe_scene_slug))
        text = path.read_text(encoding="utf-8")
        record = self._scene_record(safe_story_slug, path)
        story = self._story_record(safe_story_slug)
        return SceneDocument(story=story, record=record, text=text, validation_errors=self.validate_scene_text(text))

    def validate_scene_text(self, text: str) -> list[str]:
        """Return scene markdown validation warnings."""
        return []

    def save_scene(self, story_slug: str, scene_slug: str, text: str) -> SceneDocument:
        """Save one scene markdown file after validation."""
        safe_story_slug = self.safe_slug(story_slug)
        safe_scene_slug = self.safe_slug(scene_slug)
        errors = self.validate_scene_text(text)
        if errors:
            record = SceneRecord(
                story_slug=safe_story_slug,
                slug=safe_scene_slug,
                title=self._scene_title_from_slug(safe_scene_slug),
                path=str(self.path_service.scene_file_path(safe_story_slug, safe_scene_slug)),
            )
            return SceneDocument(story=self._story_record(safe_story_slug), record=record, text=str(text or ""), validation_errors=errors)
        path = self.path_service.scene_file_path(safe_story_slug, safe_scene_slug)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(text or "").rstrip() + "\n", encoding="utf-8")
        return self.load_scene(safe_story_slug, safe_scene_slug)

    def delete_scene(self, story_slug: str, scene_slug: str) -> StoryGitResult:
        """Commit the current story state, then delete one scene markdown and image."""
        safe_story_slug = self.safe_slug(story_slug)
        safe_scene_slug = self.safe_slug(scene_slug)
        scene_path = self.path_service.scene_file_path(safe_story_slug, safe_scene_slug)
        image_path = self.scene_image_path(safe_story_slug, safe_scene_slug)
        builder_path = self.scene_builder_json_path(safe_story_slug, safe_scene_slug)
        legacy_builder_path = self.path_service.scene_file_path(safe_story_slug, safe_scene_slug).with_suffix(".json")
        if not scene_path.exists():
            raise StoryServiceError(f"Scene file not found: {scene_path}")
        commit = self.story_git_commit()
        if commit.conflict or commit.has_story_changes:
            raise StoryServiceError(f"Scene delete aborted; commit current story changes first.\n\n{commit.output}")
        scene_path.unlink()
        if image_path.exists():
            image_path.unlink()
        if builder_path.exists():
            builder_path.unlink()
        if legacy_builder_path.exists():
            legacy_builder_path.unlink()
        return commit

    def scene_image_path(self, story_slug: str, scene_slug: str) -> Path:
        """Return the expected rendered scene image path."""
        safe_story_slug = self.safe_slug(story_slug)
        safe_scene_slug = self.safe_slug(scene_slug)
        return self.path_service.story_folder_path(safe_story_slug) / f"{safe_scene_slug}.png"

    def scene_builder_json_path(self, story_slug: str, scene_slug: str) -> Path:
        """Return the canonical Scene Builder V3 JSON path for one story scene."""
        safe_story_slug = self.safe_slug(story_slug)
        safe_scene_slug = self.safe_slug(scene_slug)
        return self.get_scene_json_path_from_scene_slug(self.path_service.story_folder_path(safe_story_slug), safe_scene_slug)

    def scene_pipeline_path(self, story_slug: str, scene_slug: str) -> Path:
        return self.path_service.story_pipeline_path(self.safe_slug(story_slug), self.safe_slug(scene_slug))

    def _scene_prompt_source_map(
        self,
        ir: dict,
        prompt: str,
        final_prompt_path: Path,
        scene_builder_path: Path,
        story_settings_path: Path,
        artifacts: list[str],
    ) -> dict:
        """Build line-level provenance for a compiled scene prompt."""
        fragments: list[dict] = []
        elements_by_name = {
            str(element.get("display_name") or element.get("id") or ""): element
            for element in ir.get("elements") or []
            if isinstance(element, dict)
        }
        current_element = None
        continuity_rules = {
            str(rule).strip(): index
            for index, rule in enumerate((ir.get("style") or {}).get("visual_continuity", {}).get("rules") or [])
            if str(rule).strip()
        }
        for line_number, line in enumerate(prompt.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("## "):
                current_element = elements_by_name.get(stripped[3:].strip())
                continue
            source = None
            if stripped.startswith("- Art style:"):
                source = {
                    "source_kind": "story_settings",
                    "source_path": str(story_settings_path),
                    "source_label": "Canonical art style",
                    "json_pointer": "/style_defaults/canonical_art_style/full_prompt_text",
                    "editable": True,
                }
            elif stripped.startswith("- ") and stripped[2:].rstrip(".") in continuity_rules:
                index = continuity_rules[stripped[2:].rstrip(".")]
                source = {
                    "source_kind": "story_settings",
                    "source_path": str(story_settings_path),
                    "source_label": "Visual continuity rule",
                    "json_pointer": f"/style_defaults/visual_continuity/rules/{index}",
                    "editable": True,
                }
            elif current_element and stripped.startswith(("**Identity:**", "**Location design:**")):
                sections = current_element.get("resolved_source_sections") or {}
                source_path = str(sections.get("identity_source") or "")
                if source_path:
                    source = {
                        "source_kind": "auxiliary_template_section" if current_element.get("resource_type") in {"Person", "Place", "Object"} else "character_template_section",
                        "source_path": source_path,
                        "source_label": f"{current_element.get('display_name') or current_element.get('id')} identity",
                        "section_name": "IDENTITY_PRESERVATION_SCENE",
                        "editable": True,
                    }
            elif current_element and stripped.startswith("**Costume"):
                sections = current_element.get("resolved_source_sections") or {}
                source_path = str(sections.get("costume_source") or "")
                if source_path:
                    source = {
                        "source_kind": "auxiliary_template_section" if current_element.get("resource_type") == "Person" else "costume_template_section",
                        "source_path": source_path,
                        "source_label": f"{current_element.get('display_name') or current_element.get('id')} costume",
                        "section_name": "IDENTITY_PRESERVATION_COSTUME_SCENE",
                        "editable": True,
                    }
            if source:
                source["prompt_start_line"] = line_number
                source["prompt_end_line"] = line_number
                fragments.append(source)
        return {
            "story_settings_file": str(story_settings_path),
            "scene_builder_file": str(scene_builder_path),
            "final_prompt": str(final_prompt_path),
            "compiler": "scene_render_v3",
            "artifacts": artifacts,
            "fragments": fragments,
        }

    def scene_prompt_source_map(self, pipeline_path: Path, prompt: str) -> dict:
        """Return current scene provenance, including for render asks staged before line maps existed."""
        ir_path = Path(pipeline_path) / "Scene_Render_IR.json"
        if not ir_path.exists():
            return {}
        ir = json.loads(ir_path.read_text(encoding="utf-8"))
        source = ir.get("source") or {}
        final_prompt_path = Path(pipeline_path) / "Final_Image_Prompt.md"
        scene_builder_path = Path(str(source.get("scene_json_path") or ""))
        story_settings_path = Path(str(source.get("story_settings_path") or ""))
        return self._scene_prompt_source_map(
            ir,
            prompt,
            final_prompt_path,
            scene_builder_path,
            story_settings_path,
            [path.name for path in Path(pipeline_path).iterdir() if path.is_file()],
        )

    def compile_scene_prompt(self, story_slug: str, scene_slug: str) -> Path:
        """Compile the final image prompt used by Scene Builder automation."""
        return self.story_render_service.compile_scene_prompt(story_slug, scene_slug)

    def get_scene_builder_json_path(self, scene_path: Path) -> Path:
        """Return the Scene Builder JSON path matching a scene markdown or image path."""
        path = Path(scene_path)
        return path.with_name(f"{path.stem}.scene.json")

    def get_story_settings_path_from_story_md(self, story_md_path: Path) -> Path:
        return Path(story_md_path).with_suffix(".story.json")

    def get_scene_json_path_from_scene_slug(self, scene_dir: Path, scene_slug: str) -> Path:
        return Path(scene_dir) / f"{self.safe_slug(scene_slug)}.scene.json"

    def create_default_story_settings(self, story_md_path: Path | None = None) -> dict:
        stamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        slug = story_md_path.stem if story_md_path else ""
        title = self._story_title_from_slug(slug)
        return {
            "schema_version": 1,
            "file_kind": "story_settings",
            "story": {
                "id": self.normalize_scene_element_id(slug).lower(),
                "title": title,
                "slug": slug,
                "human_markdown_path": self._library_relative_path(story_md_path) if story_md_path else "",
                "premise": "",
                "notes": "",
            },
            "style_defaults": {
                "canonical_art_style": {
                    "id": "default_story_style",
                    "short_label": "Painterly semi-realistic fantasy illustration",
                    "full_prompt_text": "Painterly semi-realistic fantasy illustration with anime-influenced facial proportions, large expressive eyes, refined linework, and warm storybook-fantasy color handling.",
                    "negative_style_notes": "",
                },
                "visual_continuity": {
                    "rules": [
                        "Preserve the story's canonical art style across all scene images.",
                        "Preserve recurring characters, costumes, props, and locations when referenced by scene tags.",
                    ],
                    "notes": "",
                },
                "default_avoid": ["inconsistent character identity", "wrong costume", "modern objects", "unreadable faces", "merged characters", "extra limbs", "malformed hands"],
            },
            "dialogue_styles": [
                {
                    "id": "compact_parchment",
                    "display_name": "Compact parchment dialogue panel",
                    "enabled_by_default": True,
                    "panel_prompt": "Compact rectangular parchment dialogue panel with softly rounded corners, minimal padding, warm ivory parchment background, subtle paper texture, and a thin dark bronze border.",
                    "pointer_prompt": "Short unobtrusive triangular pointer aimed toward the speaker's mouth.",
                    "lettering_prompt": "Clean modern comic-style sans-serif lettering, medium weight, crisp edges, high legibility.",
                    "layout_rules": ["Panel should be only slightly larger than the text.", "Do not obscure important faces, hands, props, or focal areas."],
                    "avoid": ["oversized speech panel", "hard-to-read text", "panel covering faces"],
                    "notes": "",
                }
            ],
            "compiler_profiles": {
                "final_image_prompt": {
                    "include_story_premise": False,
                    "include_visual_continuity": True,
                    "include_dialogue_when_scene_has_dialogue": True,
                    "include_reference_assignments": True,
                    "include_final_verification": True,
                    "notes": "",
                },
                "local_render": {
                    "purpose": "composition preview only",
                    "include_dialogue": False,
                    "include_reference_tags": False,
                    "negative_text_terms": ["text", "letters", "caption", "speech bubble", "watermark"],
                    "notes": "",
                },
            },
            "scene_index": [],
            "metadata": {"created_at": stamp, "updated_at": stamp, "created_by": "Zet Story Settings"},
        }

    def load_story_settings(self, path: Path) -> dict:
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def save_story_settings(self, path: Path, data: dict) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def save_scene_v3(self, path: Path, data: dict) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def _project_config_path(self, *parts: str) -> Path:
        return Path(__file__).resolve().parents[2] / "Config" / Path(*parts)

    def scene_builder_options(self) -> dict:
        """Return Scene Builder dropdown and validation option lists."""
        path = self._project_config_path("Scene_Builder_Options.json")
        if not path.exists():
            raise StoryServiceError(f"Scene Builder options not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        data["auxiliary_resource_categories"] = AUXILIARY_RESOURCE_CATEGORIES
        data["resource_type"] = [
            {"value": "Character", "label": "Character"},
            *[{"value": item["resource_type"], "label": item["label"], "category": item["value"]} for item in AUXILIARY_RESOURCE_CATEGORIES],
            {"value": "Scene-Only", "label": "Scene-Only"},
        ]
        return data

    def _library_relative_path(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(Path(self.path_service.config.base_library_path).resolve())).replace("\\", "/")
        except ValueError:
            return str(path)

    def _library_absolute_path(self, path_text: str) -> Path:
        path = Path(path_text)
        if path.is_absolute():
            return path
        return Path(self.path_service.config.base_library_path) / path

    def _scene_builder_paths(self, story_slug: str, scene_slug: str) -> tuple[Path, Path, Path]:
        safe_story_slug = self.safe_slug(story_slug)
        safe_scene_slug = self.safe_slug(scene_slug)
        return (
            self.path_service.scene_file_path(safe_story_slug, safe_scene_slug),
            self.scene_image_path(safe_story_slug, safe_scene_slug),
            self.scene_builder_json_path(safe_story_slug, safe_scene_slug),
        )

    def create_default_scene_builder_data(self, story_slug: str, scene_slug: str) -> dict:
        """Create default Scene Builder V3 data for one existing scene."""
        safe_story_slug = self.safe_slug(story_slug)
        safe_scene_slug = self.safe_slug(scene_slug)
        scene_doc = self.load_scene(safe_story_slug, safe_scene_slug)
        scene_path, image_path, _ = self._scene_builder_paths(safe_story_slug, safe_scene_slug)
        story_settings_path = self.get_story_settings_path_from_story_md(self.path_service.story_file_path(safe_story_slug))
        build_dir = self.path_service.story_pipeline_path(safe_story_slug, safe_scene_slug)
        stamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        return {
            "schema_version": 3,
            "file_kind": "scene",
            "scene": {
                "id": self.normalize_scene_element_id(safe_scene_slug).lower(),
                "name": scene_doc.record.title,
                "slug": safe_scene_slug,
                "sequence": None,
                "story_settings_path": self._library_relative_path(story_settings_path),
                "associated_png_path": self._library_relative_path(image_path),
                "story_beat": "",
                "author_notes": "",
            },
            "setup": {
                "canvas": {
                    "orientation": "landscape",
                    "aspect_ratio": "16:9",
                    "width": None,
                    "height": None,
                },
                "composition": {"focal_point": "", "left_to_right": [], "composition_notes": ""},
                "environment": {
                    "location": "",
                    "lighting": "",
                    "mood": "",
                    "weather_or_atmosphere": "",
                    "important_exclusions": [],
                    "general_background_notes": "",
                    "general_foreground_notes": "",
                },
            },
            "scene_elements": [],
            "placements": [],
            "props_and_states": [],
            "interactions": [],
            "custom_interactions": "",
            "dialogue": [],
            "reference_assignments": [],
            "avoid": {"scene_specific": [], "notes": ""},
            "render_settings": {
                "final_image_prompt": {"enabled": True, "output_path": self._library_relative_path(build_dir / "Final_Image_Prompt.md")},
                "local_render_brief": {"enabled": True, "output_path": self._library_relative_path(build_dir / "Local_Render_Brief.json")},
                "local_render_prompt": {"enabled": True, "output_path": self._library_relative_path(build_dir / "Local_Render_Prompt.md")},
                "scene_render_ir": {"enabled": True, "output_path": self._library_relative_path(build_dir / "Scene_Render_IR.json")},
            },
            "metadata": {
                "created_at": stamp,
                "updated_at": stamp,
                "created_by": "Zet Scene Builder",
            },
        }

    def _merge_scene_builder_defaults(self, default: dict, current: dict) -> dict:
        """Merge loaded Scene Builder data over defaults while preserving unknown fields."""
        merged = copy.deepcopy(default)
        for key, value in (current or {}).items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = self._merge_scene_builder_defaults(merged[key], value)
            else:
                merged[key] = value
        return merged

    def _normalize_scene_builder_data(self, story_slug: str, scene_slug: str, data: dict) -> dict:
        """Apply defaults and derived scene paths to Scene Builder data."""
        return self.scene_document_service.normalize(story_slug, scene_slug, data)

    def load_scene_builder_data(self, story_slug: str, scene_slug: str) -> SceneBuilderDocument:
        """Load Scene Builder data or return defaults when JSON does not exist."""
        safe_story_slug = self.safe_slug(story_slug)
        safe_scene_slug = self.safe_slug(scene_slug)
        scene_path, image_path, json_path = self._scene_builder_paths(safe_story_slug, safe_scene_slug)
        story_record = self._story_record(safe_story_slug)
        scene_record = self._scene_record(safe_story_slug, scene_path) if scene_path.exists() else self._scene_json_record(safe_story_slug, json_path)
        try:
            if json_path.exists():
                raw = json.loads(json_path.read_text(encoding="utf-8"))
                data = self._normalize_scene_builder_data(safe_story_slug, safe_scene_slug, raw)
            else:
                data = self.create_default_scene_builder_data(safe_story_slug, safe_scene_slug)
        except json.JSONDecodeError as exc:
            return SceneBuilderDocument(
                story=story_record,
                scene=scene_record,
                data={},
                json_path=str(json_path),
                md_path=str(scene_path),
                png_path=str(image_path),
                json_exists=json_path.exists(),
                png_exists=image_path.exists(),
                validation_warnings=[],
                blocked=True,
                error=f"Malformed Scene Builder JSON: {exc}",
            )
        warnings = self.validate_scene_builder_data(data)
        data["_validation_warnings"] = warnings
        return SceneBuilderDocument(
            story=story_record,
            scene=scene_record,
            data=data,
            json_path=str(json_path),
            md_path=str(scene_path),
            png_path=str(image_path),
            json_exists=json_path.exists(),
            png_exists=image_path.exists(),
            validation_warnings=warnings,
        )

    def save_scene_builder_data(self, story_slug: str, scene_slug: str, data: dict) -> SceneBuilderDocument:
        """Save Scene Builder JSON atomically."""
        safe_story_slug = self.safe_slug(story_slug)
        safe_scene_slug = self.safe_slug(scene_slug)
        _, _, json_path = self._scene_builder_paths(safe_story_slug, safe_scene_slug)
        normalized = self._normalize_scene_builder_data(safe_story_slug, safe_scene_slug, data)
        now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        normalized.setdefault("metadata", {})
        normalized["metadata"].setdefault("created_at", now)
        normalized["metadata"]["updated_at"] = now
        json_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = json_path.with_name(f".{json_path.name}.tmp")
        temp_path.write_text(json.dumps(normalized, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temp_path.replace(json_path)
        return self.load_scene_builder_data(safe_story_slug, safe_scene_slug)

    def continue_scene_builder_from(self, story_slug: str, scene_slug: str, source_scene_slug: str) -> SceneBuilderDocument:
        """Copy the reusable visual setup from another scene in the same story."""
        safe_story_slug = self.safe_slug(story_slug)
        safe_scene_slug = self.safe_slug(scene_slug)
        safe_source_scene_slug = self.safe_slug(source_scene_slug)
        if safe_source_scene_slug == safe_scene_slug:
            raise StoryServiceError("Choose a different scene to continue from.")
        source = self.load_scene_builder_data(safe_story_slug, safe_source_scene_slug)
        if source.blocked:
            raise StoryServiceError(source.error or "Source Scene Builder JSON is blocked.")
        target = self.load_scene_builder_data(safe_story_slug, safe_scene_slug)
        if target.blocked:
            raise StoryServiceError(target.error or "Current Scene Builder JSON is blocked.")
        data = copy.deepcopy(target.data)
        data.setdefault("setup", {})["canvas"] = copy.deepcopy(source.data.get("setup", {}).get("canvas", {}))
        data["setup"]["composition"] = copy.deepcopy(source.data.get("setup", {}).get("composition", {}))
        data["setup"]["environment"] = copy.deepcopy(source.data.get("setup", {}).get("environment", {}))
        data["scene_elements"] = copy.deepcopy(source.data.get("scene_elements", []))
        data["placements"] = copy.deepcopy(source.data.get("placements", []))
        return self.save_scene_builder_data(safe_story_slug, safe_scene_slug, data)

    def generate_scene_builder_outputs(self, story_slug: str, scene_slug: str, data: dict) -> dict:
        """Return Scene Builder data with validation only; prompt text is written as artifacts."""
        normalized = self._normalize_scene_builder_data(story_slug, scene_slug, data)
        normalized["_validation_warnings"] = self.validate_scene_builder_data(normalized)
        return normalized

    def _setup(self, data: dict, key: str) -> dict:
        return data.get("setup", {}).get(key, {})

    def normalize_scene_element_id(self, display_name: str) -> str:
        """Create a stable ID for scene elements when missing."""
        value = re.sub(r"[^A-Za-z0-9]+", "_", str(display_name or "").strip()).strip("_")
        return value or "scene_element"

    def _normalized_scene_elements(self, data: dict) -> list[dict]:
        elements = []
        for index, element in enumerate(data.get("scene_elements") or [], start=1):
            if not isinstance(element, dict):
                continue
            item = copy.deepcopy(element)
            item.setdefault("id", self.normalize_scene_element_id(item.get("display_name") or f"scene element {index}"))
            item.setdefault("display_name", item["id"])
            item.setdefault("resource_type", item.get("element_type") if item.get("element_type") in {"Character", "Person", "Place", "Object", "Scene-Only"} else "Character")
            item.setdefault("element_type", "Character")
            item.pop("asset_tag", None)
            item.pop("source_refs", None)
            item.setdefault("reference_images", [])
            if item.get("image_tag") and not item["reference_images"]:
                item["reference_images"].append({"tag": item.pop("image_tag"), "roles": ["visual reference"], "ignore": ["source pose", "source background", "source framing"], "notes": ""})
            item.pop("identity_prompt", None)
            if item.get("default_visual_description") and not item.get("fallback_visual_description"):
                item["fallback_visual_description"] = item.pop("default_visual_description")
            item.setdefault("element_visual_override", "")
            item.setdefault("fallback_visual_description", "")
            item.pop("role", None)
            item.pop("importance", None)
            item.setdefault("notes", "")
            elements.append(item)
        return elements

    def _normalized_placements(self, data: dict) -> list[dict]:
        placements = []
        element_types = {
            str(element.get("id") or ""): str(element.get("element_type") or "")
            for element in data.get("scene_elements") or []
        }
        for index, placement in enumerate(data.get("placements") or [], start=1):
            if not isinstance(placement, dict):
                continue
            item = copy.deepcopy(placement)
            item.setdefault("id", f"placement_{index:03d}")
            item.setdefault("scene_element_id", item.get("character_id") or "")
            item.pop("screen_cell", None)
            default_position = "None" if element_types.get(str(item.get("scene_element_id") or "")) == "Prop" else "center"
            item.setdefault("position_within_cell", default_position)
            item.setdefault("depth", "midground")
            raw_world_position = item.get("world_position")
            world_position = raw_world_position.strip() if isinstance(raw_world_position, str) else ""
            if world_position:
                item["world_position"] = world_position
            else:
                item.pop("world_position", None)
            item.pop("z_order", None)
            item.setdefault("frame_coverage", "")
            item.setdefault("distance_from_camera", "")
            item.setdefault("visual_scale", "")
            item.pop("must_be_visible", None)
            item.pop("visible_body_requirements", None)
            if not isinstance(item.get("pose"), dict):
                item["pose"] = {
                    "summary": item.pop("pose", ""),
                    "temporary_condition": "",
                    "gaze_target_element_id": item.pop("gaze_target_element_id", ""),
                    "expression": item.pop("expression", ""),
                    "left_arm_action": "",
                    "right_arm_action": "",
                    "leg_foot_detail": "",
                    "balance_weight_detail": "",
                }
            if isinstance(item.get("pose"), dict):
                item["pose"].pop("action_direction_screen", None)
                for key in ("body_view", "head_view", "left_hand_detail", "right_hand_detail", "gaze_description"):
                    item["pose"].pop(key, None)
            motion = item.get("motion") if isinstance(item.get("motion"), dict) else {}
            item["motion"] = {
                "state": str(motion.get("state") or "stationary").strip() or "stationary",
                "direction_screen": str(motion.get("direction_screen") or "").strip(),
                "cue": str(motion.get("cue") or "").strip(),
            }
            item.pop("occlusion", None)
            item.setdefault("placement_notes", "")
            placements.append(item)
        return self._paired_scene_element_placements(data, placements)

    def _default_scene_element_placement(self, element: dict, index: int) -> dict:
        element_id = str(element.get("id") or "")
        element_type = element.get("element_type") or "Character"
        return {
            "id": f"placement_{self.normalize_scene_element_id(element_id) or index}",
            "scene_element_id": element_id,
            "position_within_cell": "" if element_type == "Backdrop" else "None" if element_type == "Prop" else "center",
            "depth": "background" if element_type == "Backdrop" else "midground",
            "frame_coverage": "",
            "distance_from_camera": "",
            "visual_scale": "",
            "pose": {"summary": "", "temporary_condition": "", "gaze_target_element_id": "", "expression": "", "left_arm_action": "", "right_arm_action": "", "leg_foot_detail": "", "balance_weight_detail": ""},
            "motion": {"state": "stationary", "direction_screen": "", "cue": ""},
            "placement_notes": "",
        }

    def _paired_scene_element_placements(self, data: dict, placements: list[dict]) -> list[dict]:
        paired: list[dict] = []
        seen: set[str] = set()
        by_element: dict[str, dict] = {}
        for placement in placements:
            element_id = str(placement.get("scene_element_id") or "")
            if element_id and element_id not in by_element:
                by_element[element_id] = placement
        for index, element in enumerate(data.get("scene_elements") or [], start=1):
            element_id = str(element.get("id") or "")
            if not element_id or element_id in seen:
                continue
            item = by_element.get(element_id) or self._default_scene_element_placement(element, index)
            item["scene_element_id"] = element_id
            if element.get("element_type") == "Backdrop":
                item["position_within_cell"] = ""
                item["depth"] = "background"
            paired.append(item)
            seen.add(element_id)
        return paired

    def rebuild_depth_lanes_from_placements(self, data: dict) -> dict:
        """Rebuild depth lanes from placements."""
        lanes = {"foreground": [], "midground": [], "background": []}
        for placement in data.get("placements") or []:
            if str(placement.get("position_within_cell") or "").strip().lower() == "none":
                continue
            depth = str(placement.get("depth") or "midground")
            key = "background" if "background" in depth else depth if depth in lanes else "midground"
            element_id = placement.get("scene_element_id")
            if element_id and element_id not in lanes[key]:
                lanes[key].append(element_id)
        return lanes

    def _scene_element_lookup(self, data: dict) -> dict[str, dict]:
        return {
            str(element.get("id") or ""): element
            for element in data.get("scene_elements") or []
            if isinstance(element, dict) and str(element.get("id") or "")
        }

    def validate_scene_builder_data(self, data: dict) -> list[str]:
        """Return non-blocking Scene Builder validation warnings."""
        warnings: list[str] = []
        scene = data.get("scene", {})
        environment = self._setup(data, "environment")
        composition = self._setup(data, "composition")
        elements = self._scene_element_lookup(data)
        if data.get("schema_version") != 3:
            warnings.append("Invalid schema_version; Scene Builder V3 requires 3.")
        if data.get("file_kind") != "scene":
            warnings.append("Invalid file_kind; Scene Builder V3 requires scene.")
        if not str(scene.get("id") or "").strip():
            warnings.append("No scene id specified.")
        if not str(scene.get("name") or "").strip():
            warnings.append("No scene name specified.")
        if not str(scene.get("story_beat") or "").strip():
            warnings.append("No Story Beat specified.")
        if not str(scene.get("story_settings_path") or "").strip():
            warnings.append("No story settings path.")
        else:
            settings_path = Path(self.path_service.config.base_library_path) / str(scene.get("story_settings_path"))
            if not settings_path.exists():
                warnings.append(f"Story settings path does not exist: {scene.get('story_settings_path')}.")
        if not elements:
            warnings.append("No scene elements defined.")
        if not data.get("placements"):
            warnings.append("No placements defined.")
        backdrop_count = sum(element.get("element_type") == "Backdrop" for element in data.get("scene_elements") or [])
        if backdrop_count > 1:
            warnings.append("More than one Backdrop is defined; the first will be used as the primary Backdrop.")
        for element_id in composition.get("left_to_right") or []:
            if element_id not in elements:
                warnings.append(f"Left-to-right visual read references missing scene element {element_id}.")
        seen: set[str] = set()
        for element in data.get("scene_elements") or []:
            element_id = str(element.get("id") or "")
            element_type = element.get("element_type")
            if not element_id:
                warnings.append("Scene element has missing id.")
            if element_id in seen:
                warnings.append(f"Duplicate scene element id {element_id}.")
            seen.add(element_id)
            if element_type not in {"Character", "Monster", "Prop", "Backdrop"}:
                warnings.append(f"Scene element {element_id or element.get('display_name')} has invalid element_type {element_type}.")
            has_source = element.get("resource_type") in {"Character", "Person", "Place", "Object"}
            has_reference = any(str(item.get("tag") or "").strip() for item in element.get("reference_images") or [] if isinstance(item, dict))
            if not has_reference and not str(element.get("fallback_visual_description") or "").strip():
                warnings.append(f"Scene element {element_id or element.get('display_name')} has no image reference tag or fallback visual description.")
        for placement in data.get("placements") or []:
            element_id = str(placement.get("scene_element_id") or "")
            element = elements.get(element_id)
            placement_label = (element or {}).get("display_name") or element_id or placement.get("id")
            if element_id and element_id not in elements:
                warnings.append(f"Placement {placement_label} references missing scene element {element_id}.")
            pose = placement.get("pose") if isinstance(placement.get("pose"), dict) else {}
            if element and element.get("element_type") in {"Prop", "Backdrop"} and str(pose.get("expression") or "").strip():
                warnings.append(f"{element.get('element_type')} {element_id} has an expression; this is allowed but unusual.")
            if pose.get("gaze_target_element_id") and pose.get("gaze_target_element_id") not in elements:
                warnings.append(f"Placement {placement_label} gaze target references missing element {pose.get('gaze_target_element_id')}.")
            motion = placement.get("motion") if isinstance(placement.get("motion"), dict) else {}
            if motion.get("state") not in {"stationary", "moving"}:
                warnings.append(f"Placement {placement_label} has invalid motion state {motion.get('state')}.")
        for interaction in data.get("interactions") or []:
            subject = str(interaction.get("subject_element_id") or "")
            prop = str(interaction.get("prop_id") or "")
            target = str(interaction.get("target_element_id") or "")
            if subject and subject not in elements:
                warnings.append(f"Interaction references missing subject {subject}.")
            if target and target not in elements:
                warnings.append(f"Interaction references missing target {target}.")
            if prop and prop not in {item.get("id") for item in data.get("props_and_states") or []} and prop not in elements:
                warnings.append(f"Interaction references missing prop {prop}.")
        for item in data.get("dialogue") or []:
            speaker = str(item.get("speaker_element_id") or "")
            if speaker and speaker not in elements:
                warnings.append(f"Dialogue references missing speaker {speaker}.")
            if not str(item.get("text") or "").strip():
                warnings.append(f"Dialogue {item.get('id') or ''} has blank text.")
            if not str(item.get("pointer_target") or "").strip():
                warnings.append(f"Dialogue {item.get('id') or ''} has no pointer target.")
        for item in data.get("reference_assignments") or []:
            applies_to = str(item.get("applies_to_element_id") or "")
            if applies_to and applies_to not in elements:
                warnings.append(f"Reference assignment applies to missing element {applies_to}.")
            if not item.get("roles"):
                warnings.append(f"Reference assignment {item.get('id') or item.get('tag') or ''} has no roles.")
            if not item.get("ignore"):
                warnings.append(f"Reference assignment {item.get('id') or item.get('tag') or ''} has no ignore list.")
        if not str(environment.get("lighting") or "").strip():
            warnings.append("No lighting specified.")
        if not str(environment.get("location") or "").strip():
            warnings.append("No environment/location specified.")
        return warnings

    def _placement_phrase(self, placement: dict, element: dict | None = None) -> str:
        element = element or {}
        label = element.get("display_name") or placement.get("scene_element_id") or "item"
        element_type = element.get("element_type") or "Character"
        intro = f"In the {placement.get('position_within_cell') or 'scene'} {placement.get('depth') or 'midground'}, "
        description = element.get("default_visual_description") or ""
        if element_type == "Prop":
            return f"{intro}{label} lies {placement.get('position_within_cell') or 'center'}{(' near ' + placement.get('interaction_target_element_id')) if placement.get('interaction_target_element_id') else ''}.".replace(" ,", ",")
        if element_type == "Backdrop":
            return f"{intro}{label} anchors the scene{(', ' + description) if description else ''}."
        details = []
        if placement.get("pose"):
            details.append(str(placement.get("pose")))
        if placement.get("body_facing"):
            details.append(f"body angled {placement.get('body_facing')}")
        gaze = placement.get("gaze_target_description") or placement.get("gaze_target_element_id")
        if gaze:
            details.append(str(gaze))
        if placement.get("expression"):
            details.append(f"with a {placement.get('expression')} expression")
        verb = "looms" if element_type == "Monster" and not placement.get("pose") else ""
        return f"{intro}{label} {verb} {', '.join(details) if details else 'is placed ' + (placement.get('position_within_cell') or 'center')}.".replace("  ", " ").strip()

    def generate_scene_brief(self, data: dict) -> str:
        """Generate a concise human-readable scene brief."""
        canvas = self._setup(data, "canvas")
        environment = self._setup(data, "environment")
        elements = self._scene_element_lookup(data)
        parts = [
            f"{str(canvas.get('orientation') or 'landscape').capitalize()} scene of {environment.get('location') or 'the scene'}."
        ]
        for depth in ("foreground", "midground", "background", "distant background"):
            for placement in data.get("placements") or []:
                if placement.get("depth") == depth and str(placement.get("position_within_cell") or "").strip().lower() != "none":
                    parts.append(self._placement_phrase(placement, elements.get(str(placement.get("scene_element_id") or ""))))
        if environment.get("lighting") or environment.get("mood"):
            parts.append(" ".join(str(value) for value in [environment.get("lighting"), environment.get("mood")] if value).strip() + ".")
        return " ".join(part for part in parts if part).strip()

    def _markdown_list(self, items: list[str]) -> str:
        return "\n".join(f"- {item}" for item in items if str(item).strip()) or "- None"

    def _markdown_table(self, headers: list[str], rows: list[list[str]]) -> str:
        table = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
        table.extend("| " + " | ".join(str(cell).replace("|", "\\|") for cell in row) + " |" for row in rows)
        return "\n".join(table)

    def _scene_builder_markdown(self, data: dict) -> str:
        scene = data.get("scene", {})
        canvas = self._setup(data, "canvas")
        environment = self._setup(data, "environment")
        elements = self._scene_element_lookup(data)
        element_rows = [[
            element.get("id", ""),
            element.get("display_name", ""),
            element.get("element_type", ""),
            element.get("image_tag") or "",
        ] for element in data.get("scene_elements") or []]
        placement_rows = []
        for placement in data.get("placements") or []:
            if str(placement.get("position_within_cell") or "").strip().lower() == "none":
                continue
            element = elements.get(str(placement.get("scene_element_id") or ""), {})
            pose = placement.get("pose") if isinstance(placement.get("pose"), dict) else {}
            placement_rows.append([
                element.get("display_name") or placement.get("scene_element_id") or "",
                placement.get("depth") or "",
                placement.get("position_within_cell") or "",
                placement.get("visual_scale") or "",
                pose.get("summary") or "",
                pose.get("gaze_target_element_id") or "",
                pose.get("expression") or "",
            ])
        return "\n\n".join([
            f"# Scene: {scene.get('name') or scene.get('slug') or 'Untitled'}",
            "## Scene Brief\n\n" + (data.get("generation_outputs", {}).get("scene_brief") or self.generate_scene_brief(data)),
            "## Positive Image Prompt\n\n" + (data.get("generation_outputs", {}).get("positive_prompt") or ""),
            "## Negative Prompt\n\n" + (data.get("generation_outputs", {}).get("negative_prompt") or ""),
            "## Structured Layout Summary",
            "### Setup\n\n#### Canvas\n" + self._markdown_list([f"Orientation: {canvas.get('orientation') or ''}", f"Aspect ratio: {canvas.get('aspect_ratio') or ''}"]),
            "#### Environment\n" + self._markdown_list([f"Location: {environment.get('location') or ''}", f"Lighting: {environment.get('lighting') or ''}", f"Mood: {environment.get('mood') or ''}", f"Weather/atmosphere: {environment.get('weather_or_atmosphere') or ''}", f"Important exclusions: {', '.join(map(str, environment.get('important_exclusions') or []))}"]),
            "### Scene Elements\n\n" + self._markdown_table(["ID", "Display Name", "Type", "Image Tag"], element_rows),
            "### Placements\n\n" + self._markdown_table(["Element", "Depth", "Position", "Scale", "Pose", "Gaze", "Expression"], placement_rows),
            "### Interactions\n\n" + self._markdown_list([" ".join(str(value) for value in [elements.get(str(interaction.get("subject_element_id") or ""), {}).get("display_name") or interaction.get("subject_description"), interaction.get("relationship"), elements.get(str(interaction.get("target_element_id") or ""), {}).get("display_name") or interaction.get("target_description"), interaction.get("note")] if value) for interaction in data.get("interactions") or []]),
            "## Validation Warnings\n\n" + self._markdown_list(data.get("generation_outputs", {}).get("validation_warnings") or []),
        ]).rstrip()

    def export_scene_markdown(self, story_slug: str, scene_slug: str, data: dict) -> SceneDocument:
        """Update only the Scene Builder-managed section in the scene markdown file."""
        safe_story_slug = self.safe_slug(story_slug)
        safe_scene_slug = self.safe_slug(scene_slug)
        saved = self.save_scene_builder_data(safe_story_slug, safe_scene_slug, data)
        scene_path, _, _ = self._scene_builder_paths(safe_story_slug, safe_scene_slug)
        text = scene_path.read_text(encoding="utf-8")
        block = self._scene_builder_markdown(saved.data)
        managed = f"<!-- ZET:BEGIN SCENE_BUILDER -->\n{block}\n<!-- ZET:END SCENE_BUILDER -->"
        pattern = re.compile(r"<!-- ZET:BEGIN SCENE_BUILDER -->.*?<!-- ZET:END SCENE_BUILDER -->", re.DOTALL)
        if pattern.search(text):
            text = pattern.sub(managed, text, count=1)
        else:
            text = text.rstrip() + "\n\n" + managed
        scene_path.write_text(text.rstrip() + "\n", encoding="utf-8")
        return self.load_scene(safe_story_slug, safe_scene_slug)

    def _resolve_aux_reference(self, tag: str) -> dict:
        """Resolve one auxiliary image reference tag."""
        return self.story_reference_service.resolve_aux_reference(tag)

    def _resolve_asset_reference(self, tag: str, character: str, phase: str, asset_id: str) -> dict:
        """Resolve one locked asset image reference tag."""
        return self.story_reference_service.resolve_asset_reference(tag, character, phase, asset_id)

    def _resolve_identity_reference(self, tag: str, character: str, phase: str, identity_key_id: str) -> dict:
        """Resolve one identity key image reference tag."""
        return self.story_reference_service.resolve_identity_reference(tag, character, phase, identity_key_id)

    def _resolve_scene_references(self, scene_text: str) -> list[dict]:
        """Resolve image reference tags used by a scene."""
        return self.story_reference_service.resolve_scene_references(scene_text)

    def _write_json(self, path: Path, payload: dict) -> None:
        """Write JSON with stable formatting."""
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _clear_scene_render_queue_items(self, story_slug: str, scene_slug: str) -> None:
        """Remove stale queued render work for one story scene."""
        proxy_root = Path(self.path_service.config.base_ai_queue_path) / "Ollama_Proxy"
        ask_prefix = f"Ask_Story_{story_slug}_{scene_slug}_RENDER_"

        def matches(path: Path) -> bool:
            if path.name.startswith(ask_prefix):
                return True
            manifest_path = path / "ask_manifest.json"
            if not manifest_path.exists():
                return False
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                return False
            return manifest.get("story_slug") == story_slug and manifest.get("scene_slug") == scene_slug

        for root in (proxy_root / "Ask", proxy_root / "Answer"):
            if root.exists():
                for path in root.iterdir():
                    if path.is_dir() and matches(path):
                        shutil.rmtree(path, ignore_errors=True)

        for root in (proxy_root / "Claimed", proxy_root / "Failed"):
            if root.exists():
                for worker_dir in root.iterdir():
                    if worker_dir.is_dir():
                        for path in worker_dir.iterdir():
                            if path.is_dir() and matches(path):
                                shutil.rmtree(path, ignore_errors=True)

        claims_root = proxy_root / "Claims"
        if claims_root.exists():
            for path in claims_root.glob(f"{ask_prefix}*.claim.json"):
                path.unlink(missing_ok=True)

    def stage_scene_render(self, story_slug: str, scene_slug: str) -> StoryRenderTask:
        """Compile one story scene prompt and stage it for the Render Console."""
        return self.story_render_service.stage_scene_render(story_slug, scene_slug)

    def image_reference_rows(self, character_filter: str = "", text_filter: str = "") -> list[ImageReferenceRow]:
        """List copyable image reference rows for scenes."""
        rows: list[ImageReferenceRow] = []
        normalized_character = str(character_filter or "").strip().lower()
        normalized_filter = str(text_filter or "").strip().lower()
        for resource in self.auxiliary_resource_repository.list_resources():
            rows.extend(self._aux_resource_rows(resource))
        base_character_root = Path(self.path_service.config.base_character_path)
        if not base_character_root.exists():
            base_character_root.mkdir(parents=True, exist_ok=True)
        for character in sorted(item.name for item in base_character_root.iterdir() if item.is_dir() and not item.name.startswith("_")):
            if normalized_character and character.lower() != normalized_character:
                continue
            for phase_dir in sorted(item for item in (base_character_root / character).iterdir() if item.is_dir() and not item.name.startswith("_")):
                for asset in self._locked_assets(character, phase_dir.name):
                    rows.append(self._asset_reference_row(asset))
                for identity_key in self._identity_keys(character, phase_dir.name):
                    rows.append(self._identity_reference_row(identity_key))
        rows = [row for row in rows if self._matches_filter(row, normalized_filter)]
        return sorted(rows, key=lambda row: (row.character.lower(), row.phase.lower(), row.kind.lower(), row.label.lower()))

    def _matches_filter(self, row: ImageReferenceRow, normalized_filter: str) -> bool:
        """Return whether one image reference row matches a text filter."""
        if not normalized_filter:
            return True
        haystack = " ".join([row.tag, row.label, row.character, row.phase, row.kind, row.pipeline]).lower()
        return normalized_filter in haystack

    def _aux_resource_rows(self, resource: AuxiliaryResource) -> list[ImageReferenceRow]:
        """Return picker rows for auxiliary resource images."""
        rows = []
        for image in resource.images:
            image_path = self.path_service.resolve_path(str(image.get("image_path") or ""))
            rows.append(ImageReferenceRow(
                tag=str(image.get("tag") or ""),
                label=f"{resource.label} - {image.get('label') or image.get('image_id')}",
                character="",
                phase="",
                kind=f"aux:{resource.category}",
                pipeline="Auxiliary Resource",
                image_path=str(image_path),
                thumbnail_path=str(image_path),
            ))
        return rows

    def _locked_assets(self, character: str, phase: str) -> list[Asset]:
        """List locked assets for one character phase."""
        try:
            assets = self.asset_repository.list_assets(character, phase)
        except Exception:
            return []
        return [asset for asset in assets if asset.asset_state == "LOCKED" and asset.pipeline_stage == "LOCKED"]

    def _identity_keys(self, character: str, phase: str) -> list[IdentityKey]:
        """List identity keys for one character phase."""
        if self.identity_key_repository is None:
            return []
        try:
            return self.identity_key_repository.list_identity_keys(character, phase)
        except Exception:
            return []

    def _asset_reference_row(self, asset: Asset) -> ImageReferenceRow:
        """Return one picker row for a locked asset."""
        label_parts = [asset.pipeline, asset.body_view]
        if asset.head_view and asset.head_view != asset.body_view:
            label_parts.append(asset.head_view)
        if asset.costume:
            label_parts.append(asset.costume)
        if asset.expression:
            label_parts.append(asset.expression)
        image_path = self.path_service.locked_image_path(asset)
        tag_parts = [self._asset_reference_pipeline_code(asset.pipeline), asset.body_view]
        if asset.pipeline == "Costume-Dressing" and asset.costume:
            tag_parts.append(asset.costume)
        if asset.pipeline == "Expression" and asset.expression:
            tag_parts.append(asset.expression)
        return ImageReferenceRow(
            tag=f"{{{{ASSET:{asset.character}:{asset.phase}:{asset.asset_id}:{' | '.join(part for part in tag_parts if part)}}}}}",
            label=" | ".join(part for part in label_parts if part),
            character=asset.character,
            phase=asset.phase,
            kind="locked-asset",
            pipeline=asset.pipeline,
            image_path=str(image_path),
            thumbnail_path=str(image_path),
        )

    def _asset_reference_pipeline_code(self, pipeline: str) -> str:
        """Return the short pipeline label used in scene reference tags."""
        return {
            "Body-Reference": "Body",
            "Head-Fitment": "Head",
            "Character-Assembly": "Character",
            "Costume-Dressing": "Costume",
            "Expression": "Expression",
        }.get(pipeline, pipeline)

    def _identity_reference_row(self, identity_key: IdentityKey) -> ImageReferenceRow:
        """Return one picker row for an identity key."""
        image_path = self.path_service.resolve_path(identity_key.image_path)
        return ImageReferenceRow(
            tag=f"{{{{IDENTITY:{identity_key.character}:{identity_key.phase}:{identity_key.identity_key_id}}}}}",
            label=identity_key.label,
            character=identity_key.character,
            phase=identity_key.phase,
            kind="identity-key",
            pipeline="Identity Key",
            image_path=str(image_path),
            thumbnail_path=str(image_path),
        )
