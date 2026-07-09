from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import re
import shutil
import subprocess
from pathlib import Path

from zet.models.asset import Asset
from zet.models.auxiliary_resource import AuxiliaryResource
from zet.repositories.asset_repository import AssetRepository
from zet.repositories.auxiliary_resource_repository import AuxiliaryResourceRepository
from zet.services.path_service import PathService


@dataclass(frozen=True)
class StoryRecord:
    """Describe one story folder and its main markdown file."""
    slug: str
    title: str
    folder_path: str
    story_file_path: str
    story_file_exists: bool


@dataclass(frozen=True)
class SceneRecord:
    """Describe one scene markdown file inside a story folder."""
    story_slug: str
    slug: str
    title: str
    path: str


@dataclass(frozen=True)
class StoryDocument:
    """Describe one editable story markdown document."""
    record: StoryRecord
    text: str
    validation_errors: list[str]


@dataclass(frozen=True)
class SceneDocument:
    """Describe one editable scene markdown document."""
    story: StoryRecord
    record: SceneRecord
    text: str
    validation_errors: list[str]


@dataclass(frozen=True)
class ImageReferenceRow:
    """Describe one copyable image reference for scene editing."""
    tag: str
    label: str
    character: str
    phase: str
    kind: str
    pipeline: str
    image_path: str
    thumbnail_path: str


@dataclass(frozen=True)
class StoryRenderTask:
    """Describe a staged story scene render task."""
    story_slug: str
    scene_slug: str
    ask_id: str
    ask_path: str
    pipeline_path: str
    final_prompt_path: str
    expected_output: str
    reference_files: list[dict]


@dataclass(frozen=True)
class StoryGitResult:
    """Describe one story git operation result."""
    output: str
    has_story_changes: bool
    conflict: bool = False


class StoryServiceError(Exception):
    """Report story and scene workflow failures."""


class StoryService:
    """Manage story folders, scene markdown files, and scene image references."""

    STORY_SCENE_TEMPLATE_NAME = "story_scene_v1.md"

    def __init__(
        self,
        path_service: PathService,
        asset_repository: AssetRepository,
        auxiliary_resource_repository: AuxiliaryResourceRepository,
    ):
        """Create a story service with filesystem and repository access."""
        self.path_service = path_service
        self.asset_repository = asset_repository
        self.auxiliary_resource_repository = auxiliary_resource_repository

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

    def _render_prompt_block(self, text: str) -> str:
        """Return the scene Render Prompt block."""
        match = re.search(r"(?ims)^##\s+Render Prompt\s*(.*)$", text or "")
        return str(match.group(1)).strip() if match else ""

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

    def _placeholder_section_value(self, value: str) -> bool:
        """Return whether a compiler section still contains template placeholder text."""
        cleaned = str(value or "").strip().strip("`").strip()
        if not cleaned:
            return True
        normalized = cleaned.strip("[]").strip().lower()
        return normalized in {
            "story title",
            "painterly semi-realistic, anime-influenced facial proportions, etc.",
            "short premise, central conflict, emotional arc, or visual theme.",
        }

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
        title = self._extract_bounded_section(text, "SCENE_NAME") or self._extract_scene_line(text) or self._scene_title_from_slug(path.stem)
        return SceneRecord(
            story_slug=story_slug,
            slug=path.stem,
            title=title,
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
            template = self._replace_bounded_section(template, "STORY_TITLE", cleaned_title)
            story_file_path.write_text(template.rstrip() + "\n", encoding="utf-8")
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
        """Validate required story metadata and compiler sections."""
        errors: list[str] = []
        title = self._extract_first_metadata_field(text, "Title")
        art_style = self._extract_first_metadata_field(text, "Canonical Art Style")
        placeholder_art_styles = {
            "canonical art style",
            "painterly semi-realistic, anime-influenced facial proportions, etc.",
        }
        if not title or title.lower() == "story title":
            errors.append("Title must be filled in.")
        if not art_style or art_style.lower() in placeholder_art_styles:
            errors.append("Canonical Art Style must be filled in.")
        for section_name in ("STORY_TITLE", "CANONICAL_ART_STYLE"):
            if not self._extract_bounded_section(text, section_name):
                errors.append(f"Compiler section {section_name} must be present and filled in.")
        return errors

    def save_story(self, story_slug: str, text: str) -> StoryDocument:
        """Save one story markdown file and return validation warnings."""
        safe_slug = self.safe_slug(story_slug)
        story_file_path = self.path_service.story_file_path(safe_slug)
        story_file_path.parent.mkdir(parents=True, exist_ok=True)
        story_file_path.write_text(str(text or "").rstrip() + "\n", encoding="utf-8")
        return self.load_story(safe_slug)

    def list_scenes(self, story_slug: str) -> list[SceneRecord]:
        """List all scene markdown files for one story."""
        safe_slug = self.safe_slug(story_slug)
        folder_path = self.path_service.story_folder_path(safe_slug)
        if not folder_path.exists():
            return []
        story_file_name = f"{safe_slug}.md"
        records = []
        for path in sorted(item for item in folder_path.iterdir() if item.is_file() and item.suffix.lower() == ".md"):
            if path.name.startswith("_") or path.name == story_file_name:
                continue
            records.append(self._scene_record(safe_slug, path))
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
            template = self._replace_bounded_section(template, "SCENE_NAME", cleaned_name)
            template = re.sub(r"(?im)^Scene:\s*.+?$", f"Scene: `[{cleaned_name}]`", template, count=1)
            scene_path.write_text(template.rstrip() + "\n", encoding="utf-8")
        return self.load_scene(safe_story_slug, scene_slug)

    def load_scene(self, story_slug: str, scene_slug: str) -> SceneDocument:
        """Load one scene markdown file."""
        safe_story_slug = self.safe_slug(story_slug)
        safe_scene_slug = self.safe_slug(scene_slug)
        path = self.path_service.scene_file_path(safe_story_slug, safe_scene_slug)
        if not path.exists():
            return self.create_scene(safe_story_slug, self._scene_title_from_slug(safe_scene_slug))
        text = path.read_text(encoding="utf-8")
        record = self._scene_record(safe_story_slug, path)
        story = self._story_record(safe_story_slug)
        return SceneDocument(story=story, record=record, text=text, validation_errors=self.validate_scene_text(text))

    def validate_scene_text(self, text: str) -> list[str]:
        """Validate required scene compiler sections."""
        errors: list[str] = []
        scene_name = self._extract_bounded_section(text, "SCENE_NAME") or self._extract_scene_line(text)
        if not scene_name or scene_name.lower() == "scene name":
            errors.append("Scene name must be specified.")
        if not self._extract_bounded_section(text, "SCENE_NAME"):
            errors.append("Compiler section SCENE_NAME must be present and filled in.")
        return errors

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
        scene_name = self._extract_bounded_section(text, "SCENE_NAME") or self._extract_scene_line(text)
        saved_scene_slug = self.safe_slug(scene_name)
        path = self.path_service.scene_file_path(safe_story_slug, safe_scene_slug)
        saved_path = self.path_service.scene_file_path(safe_story_slug, saved_scene_slug)
        if saved_scene_slug != safe_scene_slug and saved_path.exists():
            raise StoryServiceError(f"Scene file already exists: {saved_path.name}")
        path.parent.mkdir(parents=True, exist_ok=True)
        if saved_scene_slug != safe_scene_slug and path.exists():
            path.rename(saved_path)
            image_path = self.scene_image_path(safe_story_slug, safe_scene_slug)
            saved_image_path = self.scene_image_path(safe_story_slug, saved_scene_slug)
            if image_path.exists() and not saved_image_path.exists():
                image_path.rename(saved_image_path)
        saved_path.write_text(str(text or "").rstrip() + "\n", encoding="utf-8")
        return self.load_scene(safe_story_slug, saved_scene_slug)

    def scene_image_path(self, story_slug: str, scene_slug: str) -> Path:
        """Return the expected rendered scene image path."""
        safe_story_slug = self.safe_slug(story_slug)
        safe_scene_slug = self.safe_slug(scene_slug)
        return self.path_service.story_folder_path(safe_story_slug) / f"{safe_scene_slug}.png"

    def _story_scene_sections(self, story_text: str, scene_text: str) -> dict[str, str]:
        """Return story and scene compiler sections for prompt rendering."""
        sections = {}
        for section_name in ("STORY_TITLE", "CANONICAL_ART_STYLE", "STORY_PREMISE", "STORY_VISUAL_CONTINUITY"):
            value = self._extract_bounded_section(story_text, section_name)
            if section_name == "STORY_TITLE" and self._placeholder_section_value(value):
                value = self._extract_first_metadata_field(story_text, "Title")
            if section_name == "CANONICAL_ART_STYLE" and self._placeholder_section_value(value):
                value = self._extract_first_metadata_field(story_text, "Canonical Art Style")
            if section_name == "STORY_PREMISE" and self._placeholder_section_value(value):
                value = ""
            sections[section_name] = value
        for section_name in ("SCENE_NAME", "SCENE_DESCRIPTION", "SCENE_IMAGE_REFERENCES", "SCENE_RENDERING_NOTES"):
            sections[section_name] = self._extract_bounded_section(scene_text, section_name)
        return sections

    def _render_story_scene_prompt(self, story_text: str, scene_text: str) -> str:
        """Render a story scene final image prompt."""
        prompt = self._story_scene_template_path().read_text(encoding="utf-8")
        sections = self._story_scene_sections(story_text, scene_text)

        def replace(match: re.Match) -> str:
            section_name = match.group(1)
            if section_name not in sections:
                raise StoryServiceError(f"Unknown compiler section: {section_name}")
            return sections.get(section_name, "")

        rendered = re.sub(r"\{\{SECTION:([A-Z0-9_]+)\}\}", replace, prompt).strip()
        if "{{SECTION:" in rendered:
            raise StoryServiceError("Final prompt still contains unresolved section tokens.")
        return rendered + "\n"

    def _story_scene_template_path(self) -> Path:
        """Return the configured story scene prompt template path."""
        path = Path(__file__).resolve().parents[2] / "Config" / "Prompt_Templates" / self.STORY_SCENE_TEMPLATE_NAME
        if not path.exists():
            raise StoryServiceError(f"Story scene prompt template not found: {path}")
        return path

    def _resolve_aux_reference(self, tag: str, category: str, resource_id: str) -> dict:
        """Resolve one auxiliary image reference tag."""
        resource = self.auxiliary_resource_repository.get_resource(resource_id)
        if resource.category != category:
            raise StoryServiceError(f"Auxiliary resource category mismatch for {tag}.")
        path = self.path_service.resolve_path(resource.image_path)
        if not path.exists():
            raise StoryServiceError(f"Auxiliary image not found: {path}")
        return {
            "role": "story_reference",
            "label": resource.label,
            "tag": tag,
            "path": str(path),
            "kind": f"aux:{category}",
        }

    def _resolve_asset_reference(self, tag: str, character: str, phase: str, asset_id: str) -> dict:
        """Resolve one locked asset image reference tag."""
        asset = self.asset_repository.get_asset(character, phase, int(asset_id))
        if asset.asset_state != "LOCKED" or asset.pipeline_stage != "LOCKED":
            raise StoryServiceError(f"Asset reference is not locked: {tag}")
        if not asset.final_image_output:
            raise StoryServiceError(f"Asset reference has no final image output: {tag}")
        path = self.path_service.character_asset_path(character, phase) / asset.final_image_output
        if not path.exists():
            raise StoryServiceError(f"Asset reference image not found: {path}")
        return {
            "role": "story_reference",
            "label": f"{character} {phase} {asset.pipeline} {asset.body_view}",
            "tag": tag,
            "path": str(path),
            "kind": "asset",
            "source_asset_id": asset.asset_id,
        }

    def _resolve_scene_references(self, scene_text: str) -> list[dict]:
        """Resolve image reference tags used by a scene."""
        references = []
        seen = set()
        pattern = r"\{\{AUX:([a-z]+):([a-z0-9-]+)\}\}|\{\{ASSET:([^:}]+):([^:}]+):(\d+)\}\}"
        for match in re.finditer(pattern, scene_text or ""):
            tag = match.group(0)
            if tag in seen:
                continue
            seen.add(tag)
            if match.group(1):
                references.append(self._resolve_aux_reference(tag, match.group(1), match.group(2)))
            else:
                references.append(self._resolve_asset_reference(tag, match.group(3), match.group(4), match.group(5)))
        return references

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
        safe_story_slug = self.safe_slug(story_slug)
        safe_scene_slug = self.safe_slug(scene_slug)
        story_path = self.path_service.story_file_path(safe_story_slug)
        scene_path = self.path_service.scene_file_path(safe_story_slug, safe_scene_slug)
        if not story_path.exists():
            raise StoryServiceError(f"Story file not found: {story_path}")
        if not scene_path.exists():
            raise StoryServiceError(f"Scene file not found: {scene_path}")
        story_text = story_path.read_text(encoding="utf-8")
        scene_text = scene_path.read_text(encoding="utf-8")
        story_errors = self.validate_story_text(story_text)
        scene_errors = self.validate_scene_text(scene_text)
        if story_errors or scene_errors:
            raise StoryServiceError("; ".join(story_errors + scene_errors))

        prompt = self._render_story_scene_prompt(story_text, scene_text)
        references = self._resolve_scene_references(scene_text)
        pipeline_path = self.path_service.story_pipeline_path(safe_story_slug, safe_scene_slug)
        pipeline_path.mkdir(parents=True, exist_ok=True)
        final_prompt_path = pipeline_path / "Final_Image_Prompt.md"
        final_prompt_path.write_text(prompt, encoding="utf-8")
        template_path = self._story_scene_template_path()
        self._write_json(
            pipeline_path / "Prompt_Source_Map.json",
            {
                "story_file": str(story_path),
                "scene_file": str(scene_path),
                "template_file": str(template_path),
                "final_prompt": str(final_prompt_path),
                "sections": sorted(self._story_scene_sections(story_text, scene_text)),
            },
        )
        self._write_json(
            pipeline_path / "dependency_manifest.json",
            {
                "story_slug": safe_story_slug,
                "scene_slug": safe_scene_slug,
                "reference_files": references,
            },
        )

        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        self._clear_scene_render_queue_items(safe_story_slug, safe_scene_slug)
        ask_id = f"Ask_Story_{safe_story_slug}_{safe_scene_slug}_RENDER_{stamp}"
        ask_path = Path(self.path_service.config.base_ai_queue_path) / "Ollama_Proxy" / "Ask" / ask_id
        ask_path.mkdir(parents=True, exist_ok=False)
        expected_output = f"{safe_scene_slug}.png"
        manifest = {
            "version": 1,
            "ask_id": ask_id,
            "asset_id": None,
            "character": "",
            "phase": "",
            "pipeline": "Story",
            "pipeline_stage": "RENDER",
            "story_slug": safe_story_slug,
            "scene_slug": safe_scene_slug,
            "ollama_attempt_id": f"{stamp}_{safe_story_slug}_{safe_scene_slug}_RENDER",
            "worker_type": "manual_chatgpt_render",
            "ollama_model": "",
            "prompt_file": "Final_Image_Prompt.md",
            "expected_output": expected_output,
            "candidate_output_file": expected_output,
            "task_type": "render",
            "render_preset": "chatgpt-manual",
            "manual": True,
            "target_output_file": str(self.path_service.story_folder_path(safe_story_slug) / expected_output),
            "pipeline_path": str(pipeline_path),
            "reference_files": references,
        }
        self._write_json(ask_path / "ask_manifest.json", manifest)
        (ask_path / "Final_Image_Prompt.md").write_text(prompt, encoding="utf-8")
        return StoryRenderTask(
            story_slug=safe_story_slug,
            scene_slug=safe_scene_slug,
            ask_id=ask_id,
            ask_path=str(ask_path),
            pipeline_path=str(pipeline_path),
            final_prompt_path=str(final_prompt_path),
            expected_output=expected_output,
            reference_files=references,
        )

    def image_reference_rows(self, character_filter: str = "", text_filter: str = "") -> list[ImageReferenceRow]:
        """List copyable image reference rows for scenes."""
        rows: list[ImageReferenceRow] = []
        normalized_character = str(character_filter or "").strip().lower()
        normalized_filter = str(text_filter or "").strip().lower()
        for resource in self.auxiliary_resource_repository.list_resources():
            rows.append(self._aux_resource_row(resource))
        base_character_root = Path(self.path_service.config.base_character_path)
        if not base_character_root.exists():
            base_character_root.mkdir(parents=True, exist_ok=True)
        for character in sorted(item.name for item in base_character_root.iterdir() if item.is_dir() and not item.name.startswith("_")):
            if normalized_character and character.lower() != normalized_character:
                continue
            for phase_dir in sorted(item for item in (base_character_root / character).iterdir() if item.is_dir() and not item.name.startswith("_")):
                for asset in self._locked_assets(character, phase_dir.name):
                    rows.append(self._asset_reference_row(asset))
        rows = [row for row in rows if self._matches_filter(row, normalized_filter)]
        return sorted(rows, key=lambda row: (row.character.lower(), row.phase.lower(), row.kind.lower(), row.label.lower()))

    def _matches_filter(self, row: ImageReferenceRow, normalized_filter: str) -> bool:
        """Return whether one image reference row matches a text filter."""
        if not normalized_filter:
            return True
        haystack = " ".join([row.tag, row.label, row.character, row.phase, row.kind, row.pipeline]).lower()
        return normalized_filter in haystack

    def _aux_resource_row(self, resource: AuxiliaryResource) -> ImageReferenceRow:
        """Return one picker row for an auxiliary resource."""
        image_path = self.path_service.resolve_path(resource.image_path)
        return ImageReferenceRow(
            tag=resource.tag,
            label=resource.label,
            character="",
            phase="",
            kind=f"aux:{resource.category}",
            pipeline="Auxiliary Resource",
            image_path=str(image_path),
            thumbnail_path=str(image_path),
        )

    def _locked_assets(self, character: str, phase: str) -> list[Asset]:
        """List locked assets for one character phase."""
        try:
            assets = self.asset_repository.list_assets(character, phase)
        except Exception:
            return []
        return [asset for asset in assets if asset.asset_state == "LOCKED" and asset.pipeline_stage == "LOCKED"]

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
        return ImageReferenceRow(
            tag=f"{{{{ASSET:{asset.character}:{asset.phase}:{asset.asset_id}}}}}",
            label=" | ".join(part for part in label_parts if part),
            character=asset.character,
            phase=asset.phase,
            kind="locked-asset",
            pipeline=asset.pipeline,
            image_path=str(image_path),
            thumbnail_path=str(image_path),
        )
