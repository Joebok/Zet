"""Canonical auxiliary-resource tag parsing and inventory matching."""

import re
from collections.abc import Iterable


_PART = r"[a-z0-9][a-z0-9-]*"
AUXILIARY_RESOURCE_TAG_RE = re.compile(
    rf"\{{\{{AUX:(person|place|thing):({_PART}):({_PART})\}}\}}"
)


def auxiliary_resource_tag(category: str, resource_id: str, image_id: str) -> str:
    """Return the only valid auxiliary-resource tag form."""
    tag = f"{{{{AUX:{category}:{resource_id}:{image_id}}}}}"
    if not AUXILIARY_RESOURCE_TAG_RE.fullmatch(tag):
        raise ValueError(f"Invalid auxiliary resource tag: {tag}")
    return tag


def parse_auxiliary_resource_tag(tag: str) -> tuple[str, str, str]:
    """Parse one complete auxiliary-resource tag."""
    match = AUXILIARY_RESOURCE_TAG_RE.fullmatch(str(tag or ""))
    if not match:
        raise ValueError(f"Invalid auxiliary resource tag: {tag}")
    return match.group(1), match.group(2), match.group(3)


def auxiliary_resource_tags_in_text(text: str) -> list[tuple[str, str, str, str]]:
    """Return unique valid auxiliary-resource tags from text."""
    tags = []
    seen = set()
    for match in AUXILIARY_RESOURCE_TAG_RE.finditer(text or ""):
        tag = match.group(0)
        if tag not in seen:
            seen.add(tag)
            tags.append((tag, match.group(1), match.group(2), match.group(3)))
    return tags


def auxiliary_resource_image_for_tag(resources: Iterable[object], tag: str) -> tuple[object, dict]:
    """Find the stored resource and image identified by a canonical tag."""
    category, resource_id, image_id = parse_auxiliary_resource_tag(tag)
    for resource in resources:
        if _field(resource, "category").strip().lower() != category or _field(resource, "resource_id").strip() != resource_id:
            continue
        for image in _field(resource, "images", []):
            if isinstance(image, dict) and str(image.get("image_id") or "").strip() == image_id:
                return resource, image
        raise LookupError(f"Auxiliary image not found for {tag}.")
    raise LookupError(f"Auxiliary resource not found for {tag}.")


def _field(record: object, name: str, default: object = "") -> object:
    if isinstance(record, dict):
        return record.get(name, default)
    return getattr(record, name, default)
