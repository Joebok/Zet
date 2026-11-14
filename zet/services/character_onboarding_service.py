from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from zet.models.character_onboarding import (
    CharacterOnboardingDraft,
    CharacterOnboardingOptions,
    CharacterOnboardingStatus,
)
from zet.services.path_service import PathService
from zet.services.species_service import SpeciesCatalog, SpeciesError, set_species, species_value

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_PATH = PROJECT_ROOT / "Scripts"

from Scripts.Compile_Character_Template import TemplateCompileError, load_template_sections
from zet.services.pipeline_compiler_support import extract_template_field
from zet.services.view_conditioning_service import ViewConditioningError, validate_view_controls


FOUNDATION_VIEWS = [
    "Front",
    "Front-Left-3-4",
    "Front-Right-3-4",
    "Left-Profile",
    "Right-Profile",
    "Back-Left-3-4",
    "Back-Right-3-4",
    "Back",
]

# Older character files may still carry this scene-specific section.  The story
# compiler continues to consume it, so it is compatible even though new files no
# longer receive it from Character_Template.md.
COMPATIBLE_CHARACTER_SECTIONS = {"SCENE_CHARACTER_ANCHORS"}

class CharacterOnboardingError(Exception):
    """Report invalid character onboarding actions."""
    pass


class CharacterOnboardingService:
    """Create and validate character phases before dashboard workflows unlock."""

    def __init__(self, path_service: PathService, project_root: Path = PROJECT_ROOT):
        """Create the onboarding service for a project root."""
        self.path_service = path_service
        self.project_root = project_root
        self.species = SpeciesCatalog(project_root, path_service.config.base_library_path)

    def options_path(self) -> Path:
        """Return the onboarding dropdown options path."""
        return self.project_root / "Config" / "Character_Onboarding_Options.json"

    def options(self) -> CharacterOnboardingOptions:
        """Load data-backed onboarding dropdown options."""
        path = self.options_path()
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
        catalog = self.species.load()[0]["species"]
        return CharacterOnboardingOptions(
            species_ancestry=sorted((entry["label"] for entry in catalog.values()), key=str.casefold),
            gender_presentation=list(data.get("gender_presentation") or []),
        )

    def _species_label(self, template):
        value = species_value(template.read_text(encoding="utf-8"))
        try:
            return self.species.resolve(value)[1]["label"]
        except SpeciesError:
            return value

    def status(self, character: str, phase: str) -> CharacterOnboardingStatus:
        """Return onboarding status for one character phase."""
        phase_path = self.path_service.character_path(character, phase)
        template_path = self.path_service.character_template_path(character, phase)
        assets_path = phase_path / "Assets.json"
        pipelines_path = phase_path / "Pipelines.json"
        messages: list[str] = []
        errors: list[str] = []
        metadata = {
            "character_name": "",
            "species_ancestry": "",
            "gender_presentation": "",
            "canonical_art_style": "",
            "standing_barefoot_height": "",
            "eye_height": "",
            "shoulder_width": "",
            "body_depth": "",
        }
        exists = phase_path.exists()
        if not exists:
            messages.append("Phase folder has not been created.")
        if exists and not template_path.exists():
            messages.append("Character.md is waiting to be saved or uploaded.")
        if exists and template_path.exists():
            metadata = self._template_metadata(template_path)
            errors = self.validate_template(template_path)
        template_ready = exists and template_path.exists() and not errors
        if template_ready and not assets_path.exists():
            messages.append("Character template is valid. Local assets can now be created.")
        complete = template_ready
        return CharacterOnboardingStatus(
            character=character,
            phase=phase,
            exists=exists,
            complete=complete,
            template_exists=template_path.exists(),
            assets_exists=assets_path.exists(),
            pipelines_exists=pipelines_path.exists(),
            messages=messages,
            validation_errors=errors,
            template_path=str(template_path) if template_path.exists() else "",
            character_name=metadata["character_name"],
            species_ancestry=metadata["species_ancestry"],
            gender_presentation=metadata["gender_presentation"],
            canonical_art_style=metadata["canonical_art_style"],
            standing_barefoot_height=metadata["standing_barefoot_height"],
            eye_height=metadata["eye_height"],
            shoulder_width=metadata["shoulder_width"],
            body_depth=metadata["body_depth"],
            template_ready=template_ready,
        )

    def prefill(self, character: str, source_phase: str = "") -> dict[str, str]:
        """Return metadata defaults for a new character or phase."""
        if source_phase:
            template = self.path_service.character_template_path(character, source_phase)
            if template.exists():
                return {
                    "character": extract_template_field(template, ["Character Name"]) or character,
                    "species_ancestry": self._species_label(template),
                    "gender_presentation": extract_template_field(template, ["Gender Presentation", "Gender"]),
                    "canonical_art_style": extract_template_field(template, ["Canonical Art Style"]),
                    "standing_barefoot_height": extract_template_field(template, ["Standing Barefoot Height"]),
                    "eye_height": extract_template_field(template, ["Eye Height"]),
                    "shoulder_width": extract_template_field(template, ["Shoulder Width"]),
                    "body_depth": extract_template_field(template, ["Body Depth"]),
                }
        return {
            "character": character,
            "species_ancestry": "",
            "gender_presentation": "",
            "canonical_art_style": "",
            "standing_barefoot_height": "",
            "eye_height": "",
            "shoulder_width": "",
            "body_depth": "",
        }

    def save_draft(self, payload: dict[str, Any]) -> CharacterOnboardingDraft:
        """Create or update a draft Character.md for onboarding."""
        with self.character_creation_lock():
            return self._save_draft(payload)

    def character_creation_lock(self):
        from zet.services.workflow_storage import file_lock
        return file_lock(self.path_service.state_path("CharacterWizard", "create.lock"))

    def _save_draft(self, payload: dict[str, Any]) -> CharacterOnboardingDraft:
        character = self._clean_folder_name(payload.get("character"), "Character")
        phase = self._clean_folder_name(payload.get("phase"), "Phase")
        if not character or not phase:
            raise CharacterOnboardingError("Character and phase are required.")
        markdown = self._render_template(payload, character, phase)
        phase_path = self.path_service.character_path(character, phase)
        phase_path.mkdir(parents=True, exist_ok=True)
        self._ensure_phase_scaffold(character, phase, payload.get("source_phase") or "")
        template_path = self.path_service.character_template_path(character, phase)
        from zet.services.image_usage_service import usage_mutation
        with usage_mutation(self.path_service, template_path):
            template_path.write_text(markdown, encoding="utf-8")
        return CharacterOnboardingDraft(character, phase, str(template_path), self.status(character, phase))

    def upload_template(self, character: str, phase: str, contents: str, create_only: bool = False) -> CharacterOnboardingStatus:
        """Validate and install an uploaded character image template."""
        with self.character_creation_lock():
            return self._upload_template(character, phase, contents, create_only)

    def _upload_template(self, character: str, phase: str, contents: str, create_only: bool) -> CharacterOnboardingStatus:
        # Uploads can arrive with CRLF already present. Normalize before text-mode
        # writing so Windows does not expand each existing CR into CRCRLF.
        contents = contents.replace("\r\r\n", "\n").replace("\r\n", "\n").replace("\r", "\n")
        if not contents.strip():
            raise CharacterOnboardingError("Uploaded template is empty.")
        character = self._clean_folder_name(character, "Character")
        phase = self._clean_folder_name(phase, "Phase")
        if not character or not phase:
            raise CharacterOnboardingError("Character and phase are required.")
        phase_path = self.path_service.character_path(character, phase)
        if create_only and phase_path.exists() and any(path.is_file() for path in phase_path.rglob("*")):
            raise CharacterOnboardingError(f"{character} / {phase} already exists. Select it before replacing its template.")
        phase_path.mkdir(parents=True, exist_ok=True)
        self._ensure_phase_scaffold(character, phase, "")
        template_path = self.path_service.character_template_path(character, phase)
        if template_path.exists():
            backup_dir = self.path_service.character_backup_path(character, phase)
            backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            shutil.copy2(template_path, backup_dir / f"Character.backup.{stamp}.md")
        from zet.services.image_usage_service import usage_mutation
        with usage_mutation(self.path_service, template_path):
            template_path.write_text(contents, encoding="utf-8")
        errors = self.validate_template(template_path)
        if errors:
            return self.status(character, phase)
        self.initialize_foundation(character, phase)
        return self.status(character, phase)

    def initialize_foundation(self, character: str, phase: str) -> None:
        """Prepare local workflow folders without creating traditional pipeline rows."""
        phase_path = self.path_service.character_path(character, phase)
        template_path = self.path_service.character_template_path(character, phase)
        if not template_path.exists():
            raise CharacterOnboardingError("Character.md must exist before initialization.")
        errors = self.validate_template(template_path)
        if errors:
            raise CharacterOnboardingError("; ".join(errors))
        self._ensure_phase_scaffold(character, phase, "")

    def validate_template(self, template_path: Path) -> list[str]:
        """Validate Character.md against active compiler requirements."""
        if not template_path.exists():
            return [f"Template file not found: {template_path}"]
        errors: list[str] = []
        if self._looks_placeholder(species_value(template_path.read_text(encoding="utf-8"))):
            errors.append("Species must be filled in.")
        for label in ["Character Name", "Character Phase", "Gender Presentation"]:
            value = extract_template_field(template_path, [label])
            if not value or self._looks_placeholder(value):
                errors.append(f"{label} must be filled in.")
        try:
            template_sections = load_template_sections(template_path)
            validate_view_controls(str(template_path))
            shared_sections = load_template_sections(self.path_service.shared_character_path() / "Character_Template.md")
            metadata = json.loads((self.project_root / "Config" / "Prompt_Section_Metadata.json").read_text(encoding="utf-8")).get("sections", {})
            optional = {name for name, spec in metadata.items() if spec.get("optional_section")}
            missing = sorted(set(shared_sections) - set(template_sections) - optional)
            extra = sorted(set(template_sections) - set(shared_sections) - COMPATIBLE_CHARACTER_SECTIONS)
            if missing:
                errors.append(f"Missing canonical sections: {', '.join(missing)}")
            if extra:
                errors.append(f"Unsupported sections: {', '.join(extra)}")
            legacy_views = sorted(name for name in extra if re.match(
                r"^(?:BODY|HEAD|HAIR|COSTUME|EQUIPMENT_JEWELRY_PROPS)_.+_VIEW_(?:FRONT|BACK|LEFT_PROFILE|RIGHT_PROFILE|.*_3_4)$", name
            ))
            if legacy_views:
                errors.append("Legacy per-view sections are unsupported; move their content into tagged VIEW_OVERRIDES: " + ", ".join(legacy_views))
            metadata_path = self.project_root / "Config" / "Prompt_Section_Metadata.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8")).get("sections", {})
            required_sections: list[str] = []
            for name, record in metadata.items():
                if not isinstance(record, dict) or not record.get("required_content"):
                    continue
                if name in shared_sections:
                    required_sections.append(name)
                elif "{VIEW}" in name:
                    required_sections.extend(name.replace("{VIEW}", view) for view in self._view_tokens())
            for name in required_sections:
                if name not in shared_sections:
                    continue
                value = str(template_sections.get(name) or "").strip()
                if not re.sub(r"<!--.*?-->", "", value, flags=re.S).strip():
                    errors.append(f"{name} must be filled in.")
                elif value == str(shared_sections.get(name) or "").strip():
                    errors.append(f"{name} still contains shared template placeholder text.")
        except TemplateCompileError as exc:
            errors.append(str(exc))
        except ViewConditioningError as exc:
            errors.append(str(exc))
        except Exception as exc:
            errors.append(f"Template validation failed: {exc}")
        return list(dict.fromkeys(errors))

    def _ensure_phase_scaffold(self, character: str, phase: str, source_phase: str) -> None:
        """Create non-asset support files and folders for a character phase."""
        self.scaffold_phase_files(self.path_service.character_path(character, phase))
        self.ensure_support_folders(character, phase)

    def ensure_support_folders(self, character: str, phase: str) -> None:
        for folder in [
            self.path_service.character_asset_path(character, phase),
            self.path_service.pipeline_base_path(character, phase),
        ]:
            folder.mkdir(parents=True, exist_ok=True)
    @staticmethod
    def scaffold_phase_files(phase_path: Path) -> None:
        phase_path.mkdir(parents=True, exist_ok=True)
        identity_keys_path = phase_path / "IdentityKeys.json"
        if not identity_keys_path.exists():
            identity_keys_path.write_text('{\n  "schema_version": 1,\n  "identity_keys": []\n}\n', encoding="utf-8")
        turnaround_path = phase_path / "TurnaroundSheets.json"
        if not turnaround_path.exists():
            turnaround_path.write_text('{\n  "schema_version": 1,\n  "turnarounds": []\n}\n', encoding="utf-8")

    def _template_metadata(self, template_path: Path) -> dict[str, str]:
        """Read top-level onboarding metadata from a character template."""
        return {
            "character_name": extract_template_field(template_path, ["Character Name"]),
            "species_ancestry": self._species_label(template_path),
            "gender_presentation": extract_template_field(template_path, ["Gender Presentation", "Gender"]),
            "canonical_art_style": extract_template_field(template_path, ["Canonical Art Style"]),
            "standing_barefoot_height": extract_template_field(template_path, ["Standing Barefoot Height"]),
            "eye_height": extract_template_field(template_path, ["Eye Height"]),
            "shoulder_width": extract_template_field(template_path, ["Shoulder Width"]),
            "body_depth": extract_template_field(template_path, ["Body Depth"]),
        }

    def _render_template(self, payload: dict[str, Any], character: str, phase: str) -> str:
        """Render a draft template from the shared character template and interview answers."""
        shared_path = self.path_service.shared_character_path() / "Character_Template.md"
        if not shared_path.exists():
            raise CharacterOnboardingError(f"Shared character template not found: {shared_path}")
        text = shared_path.read_text(encoding="utf-8")
        try:
            sid, _, _ = self.species.resolve(str(payload.get("species_ancestry") or ""))
        except SpeciesError as exc:
            raise CharacterOnboardingError(str(exc)) from exc
        text = set_species(text, sid)
        replacements = {
            "Character Name": character,
            "Character Phase": phase,
            "Gender Presentation": str(payload.get("gender_presentation") or "").strip(),
            "Canonical Art Style": str(payload.get("canonical_art_style") or "").strip(),
            "Standing Barefoot Height": str(payload.get("standing_barefoot_height") or "").strip() or "optional",
            "Eye Height": str(payload.get("eye_height") or "").strip() or "optional",
            "Shoulder Width": str(payload.get("shoulder_width") or "").strip() or "optional",
            "Body Depth": str(payload.get("body_depth") or "").strip() or "optional",
        }
        for label, value in replacements.items():
            text = self._replace_metadata_line(text, label, value)
        has_footwear_metadata = bool(self._extract_metadata_line(text, "Footwear"))
        if not has_footwear_metadata:
            text = re.sub(
                r"(?im)^(\s*Canonical\s+Art\s+Style\s*:\s*.+?\s*)$",
                "\\1\n"
                "Footwear: `[feet]`\n"
                "Footwear Contact: `[Both bare feet are flat on the floor. Both heels are fully planted. Both forefeet and toes touch the ground.]`\n"
                "Footwear Grounding: `[Both bare feet remain flat on the ground.]`\n",
                text,
                count=1,
            )
        return text

    def _replace_metadata_line(self, text: str, label: str, value: str) -> str:
        """Replace one top-level metadata line in a template."""
        escaped = re.escape(label).replace(r"\ ", r"\s+")
        return re.sub(rf"(?im)^\s*{escaped}\s*:\s*.+?$", f"{label}: `[{value}]`", text, count=1)

    def _extract_metadata_line(self, text: str, label: str) -> str:
        """Extract one unbulleted top-level metadata line from template text."""
        escaped = re.escape(label).replace(r"\ ", r"\s+")
        match = re.search(rf"(?im)^\s*{escaped}\s*:\s*(.+?)\s*$", text)
        if not match:
            return ""
        return str(match.group(1) or "").strip().strip("`").strip().strip("[]").strip()

    def _view_tokens(self) -> list[str]:
        """Return compiler view tokens for foundation views."""
        return [re.sub(r"[^A-Z0-9]+", "_", view.upper()).strip("_") for view in FOUNDATION_VIEWS]

    def _looks_placeholder(self, value: str) -> bool:
        """Return whether a metadata value still looks like template placeholder text."""
        cleaned = str(value or "").strip().lower()
        return not cleaned or "character name" in cleaned or "adult / youth" in cleaned or cleaned in {"species", "optional"}

    def _clean_folder_name(self, value: Any, label: str) -> str:
        """Return a safe folder name from user input."""
        cleaned = str(value or "").strip()
        if not cleaned:
            return ""
        if not re.match(r"^[A-Za-z0-9 _-]+$", cleaned):
            raise CharacterOnboardingError(f"{label} may only contain letters, numbers, spaces, underscores, and hyphens.")
        return cleaned
