from dataclasses import dataclass


@dataclass(frozen=True)
class ZineRecord:
    """Describe one saved zine."""

    name: str
    slug: str
    image_path: str
    json_path: str
    image_exists: bool


@dataclass(frozen=True)
class ZineDocument:
    """Describe one saved zine and its metadata."""

    record: ZineRecord
    metadata: dict


@dataclass(frozen=True)
class ZineSceneSource:
    """Describe one story scene image available to the Zine Maker."""

    story_slug: str
    scene_slug: str
    title: str
    tag: str
    image_path: str
    width: int
    height: int

