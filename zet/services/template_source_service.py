"""Context-local template versions for compiler trials; canonical source paths stay stable."""
from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import hashlib
from pathlib import Path

from zet.services.library_reference_service import pipeline_library_root_for_path, read_library_json


_SOURCES = ContextVar("zet_template_sources", default=None)


def read_template_text(path: str | Path) -> str:
    path = Path(path)
    sources = _SOURCES.get()
    key = str(path.resolve())
    return sources[key] if sources is not None and key in sources else path.read_text(encoding="utf-8")


def template_source_hash(path: Path) -> str:
    sources = _SOURCES.get() or {}
    text = sources.get(str(path.resolve()))
    raw = path.read_bytes()
    if text is not None and text != path.read_text(encoding="utf-8"):
        raw = text.encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@contextmanager
def template_sources(sources: list[dict]):
    token = _SOURCES.set({str(Path(item["source_path"]).resolve()): item["text"] for item in sources})
    try:
        yield
    finally:
        _SOURCES.reset(token)


def active_revision(root: Path) -> dict:
    directory = Path(root) / "template_improvement"
    pointer = directory / "active.json"
    if not pointer.is_file():
        return {}
    library = pipeline_library_root_for_path(root)
    revision_id = read_library_json(pointer, library).get("revision_id", "")
    if not revision_id:
        return {}
    if not isinstance(revision_id, str) or len(revision_id) != 32 or any(c not in "0123456789abcdef" for c in revision_id):
        raise ValueError("Invalid active template revision.")
    record = read_library_json(directory / "revisions" / f"{revision_id}.json", library)
    if record.get("status") != "READY":
        raise ValueError("Active template revision has not passed compilation.")
    return bind_revision_sources(record, library)


def bind_revision_sources(record: dict, library_root: Path, project_root: Path | None = None) -> dict:
    """Bind stable source IDs to this checkout and universe after moves/deploys."""
    project_root = (project_root or Path(__file__).resolve().parents[2]).resolve()
    record = deepcopy(record)
    for source in record["sources"]:
        sid = source["source_id"]
        if sid.startswith("project/"):
            owner, relative = project_root, sid.removeprefix("project/")
        elif sid.startswith("library/"):
            owner, relative = Path(library_root).resolve(), sid.removeprefix("library/")
        else:
            raise ValueError("Unknown template source owner.")
        target = (owner / relative).resolve()
        if not target.is_relative_to(owner) or ".." in Path(relative).parts:
            raise ValueError("Template source escapes its owning root.")
        source["source_path"] = str(target)
    return record


def compile_with_revision(root: Path, compile_function, *args, **kwargs):
    # Explicit trial contexts also cover analysis compilation and nested readers.
    if _SOURCES.get() is not None:
        return compile_function(*args, **kwargs)
    revision = active_revision(root)
    with template_sources(revision.get("sources", [])):
        result = compile_function(*args, **kwargs)
        from zet.services.local_prompt_improvement_service import record_compiler_sources
        record_compiler_sources(Path(result["final_prompt"]).parent)
    from zet.services.atomic_file_service import write_json_atomic
    write_json_atomic(Path(result["final_prompt"]).parent / "Template_Revision.json",
                      {"revision_id": revision.get("revision_id", "")})
    return {**result, "template_revision_id": revision.get("revision_id", "")}
