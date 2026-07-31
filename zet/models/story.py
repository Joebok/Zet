from dataclasses import dataclass


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
class SceneBuilderDocument:
    """Describe one editable Scene Builder JSON document."""
    story: StoryRecord
    scene: SceneRecord
    data: dict
    json_path: str
    md_path: str
    png_path: str
    json_exists: bool
    png_exists: bool
    validation_warnings: list[str]
    blocked: bool = False
    error: str = ""


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
    costume: str = ""
    view: str = ""
    available: bool = True
    disabled_reason: str = ""


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
