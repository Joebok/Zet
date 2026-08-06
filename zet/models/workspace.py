from dataclasses import dataclass, field


@dataclass(frozen=True)
class WorkspaceStep:
    """Describe one visible workspace progression step."""

    key: str
    label: str
    complete: bool
    current: int
    total: int
    destination: str


@dataclass(frozen=True)
class CharacterWorkspaceSummary:
    """Summarize character-phase readiness for the dashboard overview."""

    character: str
    phase: str
    ready: bool
    steps: list[WorkspaceStep] = field(default_factory=list)
    base_reference_locked: int = 0
    base_reference_total: int = 0
    head_image_locked: int = 0
    head_image_total: int = 0
    assembly_locked: int = 0
    assembly_total: int = 0
    identity_count: int = 0
    turnaround_count: int = 0
    costume_count: int = 0
    expression_count: int = 0
    recommended_destination: str = "onboarding"
    recommended_action: str = "Edit character setup"


@dataclass(frozen=True)
class StorySceneSummary:
    """Summarize one story scene and its current image state."""

    slug: str
    title: str
    image_state: str
    image_path: str
    candidate_pending: bool


@dataclass(frozen=True)
class StoryWorkspaceSummary:
    """Summarize scene progress for one story."""

    story_slug: str
    title: str
    scene_count: int
    locked_count: int
    candidate_count: int
    unrendered_count: int
    scenes: list[StorySceneSummary] = field(default_factory=list)
    recommended_scene_slug: str = ""
    recommended_destination: str = "stories"
    recommended_action: str = "Create a story"
