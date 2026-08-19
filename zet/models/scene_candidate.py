from dataclasses import dataclass, field


@dataclass(frozen=True)
class SceneCandidateSource:
    key: str
    label: str
    path: str
    default_story_slug: str
    read_only: bool
    exists: bool
    modified_at: str = ""
    error: str = ""


@dataclass(frozen=True)
class SceneCandidate:
    source_key: str
    candidate_id: str
    session: str
    title: str
    status: str
    fields: dict[str, object]
    content_hash: str
    warnings: list[str] = field(default_factory=list)
    imported_story_slug: str = ""
    imported_scene_slug: str = ""
    import_state: str = "available"
    readiness: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class SceneCandidateImportResult:
    candidate: SceneCandidate
    story_slug: str
    scene_slug: str
    created: bool
    data: dict
    interview_narrative: str
    interview_phases: list[str]
    readiness: dict[str, object]
