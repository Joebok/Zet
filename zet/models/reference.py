from dataclasses import dataclass
from typing import Any, Iterable, Mapping


REFERENCE_FILE_PROTOCOL_VERSION = 1
REFERENCE_FILE_TYPE = "reference_file"


class UnsupportedReferenceFileProtocolVersion(ValueError):
    """Raised when a persisted reference record requires a newer protocol."""


@dataclass(frozen=True)
class ReferenceFile:
    """Typed, lossless view of a persisted reference-file record."""

    version: int
    record_type: str
    values: dict[str, Any]

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "ReferenceFile":
        if not isinstance(payload, Mapping):
            raise ValueError("reference_files entries must be JSON objects.")
        raw_version = payload.get("version", REFERENCE_FILE_PROTOCOL_VERSION)
        if isinstance(raw_version, bool) or not isinstance(raw_version, int):
            raise UnsupportedReferenceFileProtocolVersion(
                f"Unsupported reference file version {raw_version!r}; supported version is {REFERENCE_FILE_PROTOCOL_VERSION}."
            )
        if raw_version != REFERENCE_FILE_PROTOCOL_VERSION:
            raise UnsupportedReferenceFileProtocolVersion(
                f"Unsupported reference file version {raw_version}; supported version is {REFERENCE_FILE_PROTOCOL_VERSION}."
            )
        return cls(
            version=raw_version,
            record_type=str(payload.get("type") or REFERENCE_FILE_TYPE),
            values=dict(payload),
        )

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def to_dict(self) -> dict[str, Any]:
        payload = dict(self.values)
        payload["version"] = self.version
        payload["type"] = self.record_type
        return payload


def reference_files_payload(references: Iterable[Mapping[str, Any] | ReferenceFile]) -> list[dict[str, Any]]:
    """Serialize reference records with explicit protocol identifiers."""
    return [
        reference.to_dict() if isinstance(reference, ReferenceFile) else ReferenceFile.from_dict(reference).to_dict()
        for reference in references
    ]
