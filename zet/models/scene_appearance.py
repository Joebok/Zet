from dataclasses import dataclass, field


@dataclass(frozen=True)
class SceneAppearanceReference:
    """Identify one ordered supporting image used by a Scene Appearance."""

    role: str
    label: str
    tag: str


@dataclass(frozen=True)
class SceneAppearanceDefinition:
    """Describe one reusable costume, equipment, and companion arrangement."""

    schema_version: int
    appearance_id: str
    name: str
    character: str
    phase: str
    costume: str
    instructions: str
    supporting_references: list[SceneAppearanceReference] = field(default_factory=list)
    path: str = ""
    asset_count: int = 0
