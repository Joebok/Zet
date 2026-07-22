import dataclasses
import json
from dataclasses import fields
from pathlib import Path
from typing import Callable, TypeVar


ModelType = TypeVar("ModelType")


class MissingDataclassFieldsError(ValueError):
    """Report required dataclass fields absent from a stored record."""

    def __init__(self, missing_fields: list[str]):
        self.missing_fields = missing_fields
        super().__init__(", ".join(missing_fields))


def dataclass_from_record(model_type: type[ModelType], record: dict) -> ModelType:
    """Build a dataclass from its declared fields, applying field defaults."""
    model_fields = list(fields(model_type))
    required = [
        field.name
        for field in model_fields
        if field.default is dataclasses.MISSING and field.default_factory is dataclasses.MISSING
    ]
    missing = sorted(set(required) - set(record))
    if missing:
        raise MissingDataclassFieldsError(missing)
    values = {}
    for field in model_fields:
        if field.name in record:
            values[field.name] = record[field.name]
        elif field.default is not dataclasses.MISSING:
            values[field.name] = field.default
        elif field.default_factory is not dataclasses.MISSING:
            values[field.name] = field.default_factory()
    return model_type(**values)


def dataclass_to_record(model: object) -> dict:
    """Serialize the declared fields of a dataclass."""
    return {field.name: getattr(model, field.name) for field in fields(model)}


def write_json_atomic(
    path: Path,
    temp_path: Path,
    payload: dict,
    *,
    before_write: Callable[[], None] | None = None,
    cleanup_temp_on_error: bool = False,
) -> None:
    """Write and validate JSON before replacing its destination."""
    serialized = json.dumps(payload, indent=2)
    if not serialized.endswith("\n"):
        serialized += "\n"
    if before_write is not None:
        before_write()
    try:
        temp_path.write_text(serialized, encoding="utf-8")
        json.loads(temp_path.read_text(encoding="utf-8"))
        temp_path.replace(path)
    except Exception:
        if cleanup_temp_on_error and temp_path.exists():
            temp_path.unlink()
        raise
