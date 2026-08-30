from dataclasses import dataclass, field


@dataclass(frozen=True)
class ImageSourceBinding:
    source_key: str
    source_type: str
    tag: str


@dataclass(frozen=True)
class CatalogCollection:
    collection_id: str
    label: str
    usage_count: int = 0


@dataclass(frozen=True)
class CatalogKeyword:
    keyword_id: str
    label: str
    usage_count: int = 0


@dataclass(frozen=True)
class CompilerSectionMetadata:
    mode: str = "inherit"
    approved_text: str = ""
    provenance: str = ""


@dataclass(frozen=True)
class EffectiveImageDescription:
    identity_text: str
    costume_text: str
    identity_status: str
    costume_status: str


@dataclass(frozen=True)
class ImageCatalogItem:
    """Describe one selectable image plus its logical catalog metadata."""

    catalog_id: str
    source_key: str
    source_type: str
    tag: str
    label: str
    image_path: str
    thumbnail_path: str
    semantic_category: str
    collections: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    character: str = ""
    phase: str = ""
    costume: str = ""
    pipeline: str = ""
    view: str = ""
    story_slug: str = ""
    scene_slug: str = ""
    subscene_id: str = ""
    is_base_pipeline: bool = False
    identity_text: str = ""
    costume_text: str = ""
    identity_status: str = "missing"
    costume_status: str = "not_applicable"
    description_status: str = "missing"
    identity_mode: str = "inherit"
    costume_mode: str = "inherit"
    ai_draft_identity: str = ""
    ai_draft_costume: str = ""
    available: bool = True
    candidate_pending: bool = False
    image_review_key: str = ""
