"""Records for the independent narrative scene workflow."""
from dataclasses import dataclass, field
from uuid import uuid4


def new_id() -> str:
    return uuid4().hex


@dataclass
class NarrativeStory:
    title: str
    id: str = field(default_factory=new_id)
    brief: str = ""
    scene_ids: list[str] = field(default_factory=list)
    scene_text_style_override: dict = field(default_factory=dict)
    source_provenance: dict = field(default_factory=dict)


@dataclass
class NarrativeElement:
    name: str
    id: str = field(default_factory=new_id)
    kind: str = "subject"
    asset_id: str = ""
    reference_key: str = ""
    appearance: str = ""
    reference_role: str = "appearance"


@dataclass
class NarrativeScene:
    title: str
    id: str = field(default_factory=new_id)
    intent: str = ""
    setting: str = ""
    camera: str = "Eye level"
    perspective: str = "Natural perspective"
    lighting: str = "Soft daylight from the upper left"
    style: str = ""
    use_universe_style: bool = True
    universe_style_variant: str = "canonical"
    canvas: str = "16:9"
    elements: list[dict] = field(default_factory=list)
    target_ids: list[str] = field(default_factory=list)
    legacy_image: dict = field(default_factory=dict)
    source_provenance: dict = field(default_factory=dict)
    migration: dict = field(default_factory=dict)


@dataclass
class NarrativeTarget:
    title: str
    kind: str
    id: str = field(default_factory=new_id)
    narrative: str = ""
    staging: str = ""
    physical_context: str = ""
    use_transparent_background: bool = True
    framing: str = "Full body, complete silhouettes"
    width: int = 1216
    height: int = 832
    element_ids: list[str] = field(default_factory=list)
    visual_overrides: dict = field(default_factory=dict)
    universe_style_variant: str = ""
    prompt: str = ""
    interview: list[dict] = field(default_factory=list)
    jobs: dict = field(default_factory=dict)
    candidates: dict = field(default_factory=dict)
    slots: list[str | None] = field(default_factory=lambda: [None] * 8)
    selected_id: str | None = None
    active_llm_job: str | None = None
    interview_model: str = ""
    prompt_model: str = ""
    prompt_provenance: dict = field(default_factory=dict)
    scene_text: list[dict] = field(default_factory=list)
    scene_text_revision: int = 0
    layers: list[dict] = field(default_factory=list)
    assembly_mode: str = "finish_composite"
    source_snapshot: dict = field(default_factory=dict)
    backdrop_link_mode: str = "reference"
    backdrop_adaptation: dict = field(default_factory=dict)


@dataclass
class NarrativeCandidate:
    target_id: str
    slot: int
    seed: int
    id: str = field(default_factory=new_id)
    job_id: str | None = None
    status: str = "SUBMITTING"
    image: str = ""
    error: str = ""
    locked: bool = False

