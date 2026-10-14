"""Portable serialization for explicitly typed library-owned path fields."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path, PureWindowsPath
from typing import Any

from zet.services.path_service import LIBRARY_PATH_FORMAT_VERSION, PathService


_PATH_FIELDS = frozenset({
    "path", "paths", "image_path", "image_paths", "thumbnail_path", "locked_image_path",
    "candidate_image_path", "source_path", "source_paths", "source_image", "source_image_path", "front_source",
    "prompt_path", "front_prompt_path", "analysis_path", "analysis_prompt_path", "diagnostics_path",
    "costume_path", "ir_path", "snapshot_path", "result_path", "accepted_path", "output_path",
    "target_output_dir", "target_output_file", "artifact_output_dir", "pipeline_path",
    "resource_path", "template_path", "prompt_condense_template", "dependency_manifest", "original_path", "workspace",
})
_LIBRARY_ROOTS = frozenset({
    "Assets", "AuxiliaryResources", "Characters", "ImageCatalog", "NarrativeStories",
    "PipelineCandidates", "Pipelines", "Stories", "_state", "images",
})
_FORMAT_FIELD = "library_path_format_version"


class LibraryReferenceError(ValueError):
    """A stored library reference uses an unsupported or unsafe path format."""


class LibraryReferenceService:
    """Translate typed, library-owned JSON path values at persistence boundaries."""

    def __init__(self, paths: PathService):
        self.paths = paths

    @staticmethod
    def _portable(value: str) -> bool:
        normalized = value.replace("\\", "/")
        parts = tuple(part for part in normalized.split("/") if part not in {"", "."})
        if parts and parts[0] in _LIBRARY_ROOTS and ".." in parts:
            raise LibraryReferenceError("A portable library path cannot traverse outside its owning universe.")
        return bool(parts and parts[0] in _LIBRARY_ROOTS and ".." not in parts)

    def encode(self, document: dict[str, Any]) -> dict[str, Any]:
        """Copy a record and make absolute, in-library typed paths portable."""
        result = deepcopy(document)
        self._walk(result, encode=True)
        result[_FORMAT_FIELD] = LIBRARY_PATH_FORMAT_VERSION
        return result

    def decode(self, document: dict[str, Any]) -> dict[str, Any]:
        """Copy a record and resolve its versioned portable paths for runtime use."""
        version = document.get(_FORMAT_FIELD)
        if version is None:
            return deepcopy(document)
        if isinstance(version, bool) or not isinstance(version, int) or version != LIBRARY_PATH_FORMAT_VERSION:
            raise LibraryReferenceError(f"Unsupported library path format version: {version!r}")
        bound_universe = str(getattr(self.paths.config, "universe_id", "") or "")
        if not bound_universe:
            descriptor = self.paths.entity_library_root() / "universe.json"
            if descriptor.is_file():
                try:
                    bound_universe = str(json.loads(descriptor.read_text(encoding="utf-8")).get("universe_id") or "")
                except (OSError, UnicodeError, json.JSONDecodeError, AttributeError) as exc:
                    raise LibraryReferenceError(f"Cannot verify the owning universe for this record: {exc}") from exc
        owner_universe = str(document.get("universe_id") or "")
        if bound_universe and owner_universe and owner_universe != bound_universe:
            raise LibraryReferenceError(
                f"Record belongs to universe {owner_universe!r}, not bound universe {bound_universe!r}."
            )
        result = deepcopy(document)
        result.pop(_FORMAT_FIELD, None)
        self._walk(result, encode=False)
        return result

    def _walk(self, value: Any, *, encode: bool) -> None:
        if isinstance(value, dict):
            for key, child in tuple(value.items()):
                if key in _PATH_FIELDS:
                    if isinstance(child, str):
                        value[key] = self._convert(child, encode=encode)
                    elif key in {"paths", "image_paths", "source_paths"} and isinstance(child, list):
                        value[key] = [self._convert(item, encode=encode) if isinstance(item, str) else item for item in child]
                        for item in value[key]:
                            if isinstance(item, (dict, list)):
                                self._walk(item, encode=encode)
                    elif isinstance(child, (dict, list)):
                        self._walk(child, encode=encode)
                elif isinstance(child, (dict, list)):
                    self._walk(child, encode=encode)
        elif isinstance(value, list):
            for child in value:
                if isinstance(child, (dict, list)):
                    self._walk(child, encode=encode)

    def _convert(self, value: str, *, encode: bool) -> str:
        raw = value.strip()
        if not raw:
            return value
        if encode:
            if Path(raw).is_absolute() or PureWindowsPath(raw).is_absolute():
                return self.paths.serialize_library_path(raw)
            return value
        if self._portable(raw):
            return str(self.paths.resolve_library_path(raw))
        return value


def migrate_library_document(
    document: dict[str, Any], library_root: str | Path, old_roots: tuple[str | Path, ...] = (),
) -> tuple[dict[str, Any], int, list[str]]:
    """Convert only registered path fields rooted in an explicit current/old library."""
    current = Path(library_root).expanduser().resolve()
    roots = tuple(Path(root).expanduser().resolve() for root in (*old_roots, current))
    result = deepcopy(document)
    converted = 0
    unresolved: list[str] = []
    found_library_reference = False

    def convert(value: str, field: str) -> str:
        nonlocal converted, found_library_reference
        if not value.strip():
            return value
        native = Path(value).expanduser()
        windows = PureWindowsPath(value)
        for old_root in roots:
            try:
                if native.is_absolute():
                    relative = native.resolve().relative_to(old_root)
                elif windows.is_absolute() and old_root.drive:
                    # PureWindowsPath is needed when migration is inspected on another OS.
                    win_root = PureWindowsPath(str(old_root))
                    relative = Path(*windows.relative_to(win_root).parts)
                else:
                    continue
            except (ValueError, OSError):
                continue
            if old_root != current:
                target = current.joinpath(*relative.parts)
                if field not in {"target_output_file", "output_path", "artifact_output_dir"} and not target.exists():
                    unresolved.append(f"{field}: {value}")
                    return value
            else:
                target = native if native.is_absolute() else current.joinpath(*relative.parts)
                if field not in {"target_output_file", "output_path", "artifact_output_dir"} and not target.exists():
                    unresolved.append(f"{field}: {value}")
                    return value
            try:
                portable = target.resolve().relative_to(current).as_posix()
            except (ValueError, OSError):
                unresolved.append(f"{field}: {value}")
                return value
            found_library_reference = True
            converted += int(portable != value)
            return portable
        if LibraryReferenceService._portable(value):
            found_library_reference = True
            converted += int(value.replace("\\", "/") != value)
            try:
                resolved = current.joinpath(*value.replace("\\", "/").split("/")).resolve()
                if (not resolved.is_relative_to(current)
                        or field not in {"target_output_file", "output_path", "artifact_output_dir"} and not resolved.exists()):
                    unresolved.append(f"{field}: {value}")
            except OSError:
                unresolved.append(f"{field}: {value}")
        else:
            normalized = value.replace("\\", "/")
            parts = tuple(part for part in normalized.split("/") if part not in {"", "."})
            if parts and parts[0] in _LIBRARY_ROOTS and ".." in parts:
                unresolved.append(f"{field}: {value} (path traversal)")
        return value

    def walk(value: Any, key: str = "") -> None:
        if isinstance(value, dict):
            for name, child in tuple(value.items()):
                if name in _PATH_FIELDS:
                    if isinstance(child, str):
                        value[name] = convert(child, name)
                    elif name in {"paths", "image_paths", "source_paths"} and isinstance(child, list):
                        value[name] = [convert(item, name) if isinstance(item, str) else item for item in child]
                        for item in value[name]:
                            if isinstance(item, (dict, list)):
                                walk(item)
                    elif isinstance(child, (dict, list)):
                        walk(child)
                elif isinstance(child, (dict, list)):
                    walk(child)
        elif isinstance(value, list):
            for child in value:
                if isinstance(child, (dict, list)):
                    walk(child)

    walk(result)
    image_fields = {"image_path", "locked_image_path", "candidate_image_path", "source_image_path"}

    def verify_image_hashes(value: Any) -> None:
        if isinstance(value, dict):
            for name in image_fields:
                reference = value.get(name)
                expected = str(value.get("image_sha256") or value.get("sha256") or value.get("checksum") or "").strip().lower()
                if not isinstance(reference, str) or not expected or not LibraryReferenceService._portable(reference):
                    continue
                target = current.joinpath(*reference.replace("\\", "/").split("/")).resolve()
                try:
                    digest = hashlib.sha256()
                    with target.open("rb") as handle:
                        for block in iter(lambda: handle.read(1024 * 1024), b""):
                            digest.update(block)
                    if digest.hexdigest() != expected:
                        unresolved.append(f"{name}: {reference} (saved image hash mismatch)")
                except OSError:
                    unresolved.append(f"{name}: {reference} (image hash could not be verified)")
            for child in value.values():
                if isinstance(child, (dict, list)):
                    verify_image_hashes(child)
        elif isinstance(value, list):
            for child in value:
                if isinstance(child, (dict, list)):
                    verify_image_hashes(child)

    verify_image_hashes(result)
    version = result.get(_FORMAT_FIELD)
    if (version is not None and
            (isinstance(version, bool) or not isinstance(version, int) or version != LIBRARY_PATH_FORMAT_VERSION)):
        raise LibraryReferenceError(f"Unsupported library path format version: {version!r}")
    if found_library_reference or version == LIBRARY_PATH_FORMAT_VERSION:
        result[_FORMAT_FIELD] = LIBRARY_PATH_FORMAT_VERSION
    else:
        result.pop(_FORMAT_FIELD, None)
    return result, converted, unresolved


def count_untyped_library_occurrences(document: Any, roots: tuple[str | Path, ...]) -> int:
    """Count old/current-root text outside the explicitly typed path fields."""
    needles = tuple(str(root).replace("\\", "/").rstrip("/").casefold() for root in roots if str(root).strip())
    total = 0

    def walk(value: Any, *, typed_path: bool = False) -> None:
        nonlocal total
        if isinstance(value, dict):
            for key, child in value.items():
                is_typed = typed_path or key in _PATH_FIELDS
                if isinstance(child, (dict, list)):
                    walk(child, typed_path=is_typed)
                elif isinstance(child, str) and not is_typed:
                    text = child.replace("\\", "/").casefold()
                    total += sum(text.count(needle) for needle in needles)
        elif isinstance(value, list):
            for child in value:
                walk(child, typed_path=typed_path)
        elif isinstance(value, str) and not typed_path:
            text = value.replace("\\", "/").casefold()
            total += sum(text.count(needle) for needle in needles)

    walk(document)
    return total


def serialize_library_document(document: dict[str, Any], library_root: str | Path) -> dict[str, Any]:
    """Convenience storage-boundary helper for services that own only a library root."""
    from types import SimpleNamespace

    paths = PathService(SimpleNamespace(base_library_path=str(library_root)), Path(library_root))
    return LibraryReferenceService(paths).encode(document)


def resolve_library_document(document: dict[str, Any], library_root: str | Path) -> dict[str, Any]:
    """Convenience read-boundary helper for services that own only a library root."""
    from types import SimpleNamespace

    paths = PathService(SimpleNamespace(base_library_path=str(library_root)), Path(library_root))
    return LibraryReferenceService(paths).decode(document)


def read_library_json(path: str | Path, library_root: str | Path) -> dict[str, Any]:
    import json

    value = json.loads(Path(path).read_text(encoding="utf-8"))
    return resolve_library_document(value, library_root) if isinstance(value, dict) else value


def write_library_json(path: str | Path, value: dict[str, Any], library_root: str | Path) -> None:
    from zet.services.atomic_file_service import write_json_atomic

    write_json_atomic(path, serialize_library_document(value, library_root))


def pipeline_library_root_for_path(path: str | Path) -> Path:
    """Find the owning universe root for a path beneath its PipelineCandidates tree."""
    candidate = Path(path).resolve()
    for parent in (candidate, *candidate.parents):
        if parent.name == "PipelineCandidates":
            return parent.parent
    raise ValueError(f"Expected a path beneath PipelineCandidates: {path}")
