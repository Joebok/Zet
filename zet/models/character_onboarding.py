from dataclasses import dataclass, field


@dataclass
class CharacterOnboardingOptions:
    """Represent selectable values for character onboarding fields."""
    species_ancestry: list[str] = field(default_factory=list)
    gender_presentation: list[str] = field(default_factory=list)


@dataclass
class CharacterOnboardingStatus:
    """Represent onboarding progress for one character phase."""
    character: str
    phase: str
    exists: bool
    complete: bool
    template_exists: bool
    assets_exists: bool
    pipelines_exists: bool
    messages: list[str] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    template_path: str = ""
    character_name: str = ""
    species_ancestry: str = ""
    gender_presentation: str = ""
    canonical_art_style: str = ""
    standing_barefoot_height: str = ""
    eye_height: str = ""
    shoulder_width: str = ""
    body_depth: str = ""
    template_ready: bool = False


@dataclass
class CharacterOnboardingDraft:
    """Represent a saved draft phase before template validation completes."""
    character: str
    phase: str
    template_path: str
    status: CharacterOnboardingStatus
