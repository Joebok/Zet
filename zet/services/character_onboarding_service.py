from __future__ import annotations

from dataclasses import asdict
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from zet.models.asset import Asset
from zet.models.character_onboarding import (
    CharacterOnboardingDraft,
    CharacterOnboardingOptions,
    CharacterOnboardingStatus,
)
from zet.services.path_service import PathService

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_PATH = PROJECT_ROOT / "Scripts"

from Scripts.Compile_Character_Template import TemplateCompileError, load_template_sections
from zet.services.pipeline_compiler_support import extract_template_field


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

class CharacterOnboardingError(Exception):
    """Report invalid character onboarding actions."""
    pass


class CharacterOnboardingService:
    """Create and validate character phases before dashboard workflows unlock."""

    def __init__(self, path_service: PathService, project_root: Path = PROJECT_ROOT):
        """Create the onboarding service for a project root."""
        self.path_service = path_service
        self.project_root = project_root

    def options_path(self) -> Path:
        """Return the onboarding dropdown options path."""
        return self.project_root / "Config" / "Character_Onboarding_Options.json"

    def options(self) -> CharacterOnboardingOptions:
        """Load data-backed onboarding dropdown options."""
        path = self.options_path()
        if not path.exists():
            return CharacterOnboardingOptions()
        data = json.loads(path.read_text(encoding="utf-8"))
        return CharacterOnboardingOptions(
            species_ancestry=list(data.get("species_ancestry") or []),
            gender_presentation=list(data.get("gender_presentation") or []),
        )

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
        }
        exists = phase_path.exists()
        if not exists:
            messages.append("Phase folder has not been created.")
        if exists and not template_path.exists():
            messages.append("Character.md is waiting to be saved or uploaded.")
        if exists and template_path.exists():
            metadata = self._template_metadata(template_path)
            errors = self.validate_template(template_path)
        if exists and template_path.exists() and not errors and not assets_path.exists():
            messages.append("Template is valid. Foundation assets have not been initialized yet.")
        complete = exists and template_path.exists() and assets_path.exists() and pipelines_path.exists() and not errors
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
        )

    def prefill(self, character: str, source_phase: str = "") -> dict[str, str]:
        """Return metadata defaults for a new character or phase."""
        if source_phase:
            template = self.path_service.character_template_path(character, source_phase)
            if template.exists():
                return {
                    "character": extract_template_field(template, ["Character Name"]) or character,
                    "species_ancestry": extract_template_field(template, ["Species / Ancestry", "Species", "Ancestry"]),
                    "gender_presentation": extract_template_field(template, ["Gender Presentation", "Gender"]),
                    "canonical_art_style": extract_template_field(template, ["Canonical Art Style"]),
                }
        return {
            "character": character,
            "species_ancestry": "",
            "gender_presentation": "",
            "canonical_art_style": "",
        }

    def save_draft(self, payload: dict[str, Any]) -> CharacterOnboardingDraft:
        """Create or update a draft Character.md for onboarding."""
        character = self._clean_folder_name(payload.get("character"), "Character")
        phase = self._clean_folder_name(payload.get("phase"), "Phase")
        if not character or not phase:
            raise CharacterOnboardingError("Character and phase are required.")
        phase_path = self.path_service.character_path(character, phase)
        phase_path.mkdir(parents=True, exist_ok=True)
        self._ensure_phase_scaffold(character, phase, payload.get("source_phase") or "")
        template_path = self.path_service.character_template_path(character, phase)
        template_path.write_text(self._render_template(payload, character, phase), encoding="utf-8")
        return CharacterOnboardingDraft(character, phase, str(template_path), self.status(character, phase))

    def upload_template(self, character: str, phase: str, contents: str, create_only: bool = False) -> CharacterOnboardingStatus:
        """Validate and install an uploaded character image template."""
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
        template_path.write_text(contents, encoding="utf-8")
        errors = self.validate_template(template_path)
        if errors:
            return self.status(character, phase)
        self.initialize_foundation(character, phase)
        return self.status(character, phase)

    def initialize_foundation(self, character: str, phase: str) -> None:
        """Create foundation Assets.json and support folders for an onboarded phase."""
        phase_path = self.path_service.character_path(character, phase)
        template_path = self.path_service.character_template_path(character, phase)
        if not template_path.exists():
            raise CharacterOnboardingError("Character.md must exist before initialization.")
        errors = self.validate_template(template_path)
        if errors:
            raise CharacterOnboardingError("; ".join(errors))
        self._ensure_phase_scaffold(character, phase, "")
        assets_path = phase_path / "Assets.json"
        if assets_path.exists():
            payload = json.loads(assets_path.read_text(encoding="utf-8"))
            if payload.get("assets"):
                return
        assets = self._foundation_assets(character, phase)
        reserved_asset_ids = list(range(17, 25))
        assets_path.write_text(
            json.dumps(
                {
                    "schema_version": 2,
                    "next_asset_id": max(item["asset_id"] for item in assets) + 1,
                    "reserved_asset_ids": reserved_asset_ids,
                    "assets": assets,
                },
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )

    def validate_template(self, template_path: Path) -> list[str]:
        """Validate Character.md against active compiler requirements."""
        if not template_path.exists():
            return [f"Template file not found: {template_path}"]
        errors: list[str] = []
        for label in ["Character Name", "Character Phase", "Species / Ancestry", "Gender Presentation", "Canonical Art Style"]:
            value = extract_template_field(template_path, [label])
            if not value or self._looks_placeholder(value):
                errors.append(f"{label} must be filled in.")
        try:
            template_sections = load_template_sections(template_path)
            shared_sections = load_template_sections(self.path_service.shared_character_path() / "Character_Template.md")
            missing = sorted(set(shared_sections) - set(template_sections))
            extra = sorted(set(template_sections) - set(shared_sections))
            if missing:
                errors.append(f"Missing canonical sections: {', '.join(missing)}")
            if extra:
                errors.append(f"Unsupported sections: {', '.join(extra)}")
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
                if not value:
                    errors.append(f"{name} must be filled in.")
                elif value == str(shared_sections.get(name) or "").strip():
                    errors.append(f"{name} still contains shared template placeholder text.")
        except TemplateCompileError as exc:
            errors.append(str(exc))
        except Exception as exc:
            errors.append(f"Template validation failed: {exc}")
        return list(dict.fromkeys(errors))

    def _ensure_phase_scaffold(self, character: str, phase: str, source_phase: str) -> None:
        """Create non-asset support files and folders for a character phase."""
        phase_path = self.path_service.character_path(character, phase)
        phase_path.mkdir(parents=True, exist_ok=True)
        for folder in [
            phase_path / "Reference_Images" / "Head_Image_Sources",
            phase_path / "Body_Reference",
            self.path_service.character_asset_path(character, phase),
            self.path_service.pipeline_base_path(character, phase),
        ]:
            folder.mkdir(parents=True, exist_ok=True)
        pipelines_path = phase_path / "Pipelines.json"
        if not pipelines_path.exists():
            source = self.path_service.character_path(character, source_phase) / "Pipelines.json" if source_phase else None
            if source is None or not source.exists():
                source = self.path_service.character_path("Tsaeytte", "Adult") / "Pipelines.json"
            if source.exists():
                shutil.copy2(source, pipelines_path)
        if pipelines_path.exists():
            self._normalize_foundation_pipelines(pipelines_path)
        identity_keys_path = phase_path / "IdentityKeys.json"
        if not identity_keys_path.exists():
            identity_keys_path.write_text('{\n  "schema_version": 1,\n  "identity_keys": []\n}\n', encoding="utf-8")
        turnaround_path = phase_path / "TurnaroundSheets.json"
        if not turnaround_path.exists():
            turnaround_path.write_text('{\n  "schema_version": 1,\n  "turnarounds": []\n}\n', encoding="utf-8")

    def _foundation_assets(self, character: str, phase: str) -> list[dict[str, Any]]:
        """Build initial Body-Reference, Head-Image, and Character-Assembly assets."""
        assets: list[Asset] = []
        stamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        asset_id = 1
        for view in FOUNDATION_VIEWS:
            assets.append(Asset(asset_id, character, phase, "Body-Reference", view, final_image_output=f"Body-Reference_{view}.png", updated_at=stamp))
            asset_id += 1
        for view in FOUNDATION_VIEWS:
            assets.append(
                Asset(
                    asset_id,
                    character,
                    phase,
                    "Head-Image",
                    view,
                    head_view=view,
                    final_image_output=f"Head-Image_{view}.png",
                    updated_at=stamp,
                )
            )
            asset_id += 1
        # Preserve the retired Head-Fitment foundation slot without creating active assets.
        asset_id += len(FOUNDATION_VIEWS)
        for view in FOUNDATION_VIEWS:
            assets.append(
                Asset(
                    asset_id,
                    character,
                    phase,
                    "Character-Assembly",
                    view,
                    head_view=view,
                    final_image_output=f"Character-Assembly_{view}_{view}_Assembled.png",
                    updated_at=stamp,
                )
            )
            asset_id += 1
        return [asdict(asset) for asset in assets]

    def _template_metadata(self, template_path: Path) -> dict[str, str]:
        """Read top-level onboarding metadata from a character template."""
        return {
            "character_name": extract_template_field(template_path, ["Character Name"]),
            "species_ancestry": extract_template_field(template_path, ["Species / Ancestry", "Species", "Ancestry"]),
            "gender_presentation": extract_template_field(template_path, ["Gender Presentation", "Gender"]),
            "canonical_art_style": extract_template_field(template_path, ["Canonical Art Style"]),
        }

    def _normalize_foundation_pipelines(self, pipelines_path: Path) -> None:
        """Remove the retired prompt-review stage from phase pipelines."""
        data = json.loads(pipelines_path.read_text(encoding="utf-8"))
        pipelines = data.get("pipelines")
        if not isinstance(pipelines, dict):
            raise CharacterOnboardingError(f"Pipelines.json must contain a pipelines object: {pipelines_path}")
        if "Head-Image" not in pipelines:
            ordered: dict[str, Any] = {}
            for name, pipeline in pipelines.items():
                ordered[name] = pipeline
                if name == "Body-Reference":
                    ordered["Head-Image"] = {
                        "stages": ["MANIFEST", "PROMPT", "RENDER", "RENDER_REVIEW"],
                        "actor_by_stage": {
                            "MANIFEST": "PYTHON",
                            "PROMPT": "PYTHON",
                            "RENDER": "AI_AGENT",
                            "RENDER_REVIEW": "HUMAN_AGENT",
                        },
                        "worker_by_stage": {
                            "MANIFEST": "zet.workers.head_image_manifest_worker",
                            "PROMPT": "zet.workers.head_image_prompt_worker",
                            "RENDER": "zet.workers.noop_worker",
                            "RENDER_REVIEW": "zet.workers.noop_worker",
                        },
                    }
            pipelines.clear()
            pipelines.update(ordered)
        for pipeline in pipelines.values():
            if not isinstance(pipeline, dict):
                continue
            pipeline["stages"] = [stage for stage in list(pipeline.get("stages") or []) if stage != "PROMPT_REVIEW"]
            actor_by_stage = pipeline.get("actor_by_stage", {})
            if isinstance(actor_by_stage, dict):
                actor_by_stage.pop("PROMPT_REVIEW", None)
            worker_by_stage = pipeline.get("worker_by_stage", {})
            if isinstance(worker_by_stage, dict):
                worker_by_stage.pop("PROMPT_REVIEW", None)
        pipelines.pop("Head-Fitment", None)
        pipelines_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    def add_missing_head_image_foundation(self, character: str, phase: str) -> list[Asset]:
        """Append missing Head-Image views without changing existing assets."""
        self._ensure_phase_scaffold(character, phase, "")
        assets_path = self.path_service.character_path(character, phase) / "Assets.json"
        if not assets_path.exists():
            raise CharacterOnboardingError("Assets.json must exist before adding Head-Image assets.")
        payload = json.loads(assets_path.read_text(encoding="utf-8"))
        records = payload.get("assets")
        if not isinstance(records, list):
            raise CharacterOnboardingError("Assets.json must contain an assets list.")
        existing = {str(record.get("body_view") or "") for record in records if record.get("pipeline") == "Head-Image"}
        next_id = int(payload.get("next_asset_id") or 1)
        reserved_ids = {int(asset_id) for asset_id in payload.get("reserved_asset_ids", [])}
        stamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        added: list[Asset] = []
        for view in FOUNDATION_VIEWS:
            if view in existing:
                continue
            while next_id in reserved_ids:
                next_id += 1
            asset = Asset(next_id, character, phase, "Head-Image", view, head_view=view, final_image_output=f"Head-Image_{view}.png", updated_at=stamp)
            records.append(asdict(asset))
            added.append(asset)
            next_id += 1
        if added:
            backup_dir = self.path_service.character_backup_path(character, phase)
            backup_dir.mkdir(parents=True, exist_ok=True)
            stamp_name = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            shutil.copy2(assets_path, backup_dir / f"Assets.backup.{stamp_name}.json")
            payload["next_asset_id"] = next_id
            assets_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return added

    def _render_template(self, payload: dict[str, Any], character: str, phase: str) -> str:
        """Render a draft template from the shared character template and interview answers."""
        shared_path = self.path_service.shared_character_path() / "Character_Template.md"
        if not shared_path.exists():
            raise CharacterOnboardingError(f"Shared character template not found: {shared_path}")
        text = shared_path.read_text(encoding="utf-8")
        replacements = {
            "Character Name": character,
            "Character Phase": phase,
            "Species / Ancestry": str(payload.get("species_ancestry") or "").strip(),
            "Gender Presentation": str(payload.get("gender_presentation") or "").strip(),
            "Canonical Art Style": str(payload.get("canonical_art_style") or "").strip(),
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
