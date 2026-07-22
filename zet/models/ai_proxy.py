from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Optional

from zet.models.reference import ReferenceFile


AI_PROXY_PROTOCOL_VERSION = 1


class UnsupportedAIProxyProtocolVersion(ValueError):
    """Raised when persisted queue data requires an unsupported protocol."""


@dataclass(frozen=True)
class AIProxyManifest:
    """Typed, lossless view of a persisted AI proxy manifest.

    Versionless manifests predate explicit protocol versioning and are read as
    version 1. Unknown fields are retained so older readers remain tolerant of
    compatible additions.
    """

    version: int
    values: dict[str, Any]

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any], *, manifest_name: str) -> "AIProxyManifest":
        if not isinstance(payload, Mapping):
            raise ValueError(f"{manifest_name} must contain a JSON object.")
        raw_version = payload.get("version", AI_PROXY_PROTOCOL_VERSION)
        if isinstance(raw_version, bool) or not isinstance(raw_version, int):
            raise UnsupportedAIProxyProtocolVersion(
                f"Unsupported {manifest_name} version {raw_version!r}; supported version is {AI_PROXY_PROTOCOL_VERSION}."
            )
        version = raw_version
        if version != AI_PROXY_PROTOCOL_VERSION:
            raise UnsupportedAIProxyProtocolVersion(
                f"Unsupported {manifest_name} version {version}; supported version is {AI_PROXY_PROTOCOL_VERSION}."
            )
        values = dict(payload)
        reference_files = values.get("reference_files")
        if reference_files is not None:
            if not isinstance(reference_files, list):
                raise ValueError("ask_manifest.json reference_files must be a JSON array.")
            for reference in reference_files:
                ReferenceFile.from_dict(reference)
        return cls(version=version, values=values)

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def to_dict(self) -> dict[str, Any]:
        return dict(self.values)


class AIProxyAskManifest(AIProxyManifest):
    @classmethod
    def from_dict(cls, payload: Mapping[str, Any], *, manifest_name: str = "ask_manifest.json") -> "AIProxyAskManifest":
        manifest = super().from_dict(payload, manifest_name=manifest_name)
        return cls(version=manifest.version, values=manifest.values)


class AIProxyAnswerManifest(AIProxyManifest):
    @classmethod
    def from_dict(cls, payload: Mapping[str, Any], *, manifest_name: str = "answer_manifest.json") -> "AIProxyAnswerManifest":
        manifest = super().from_dict(payload, manifest_name=manifest_name)
        return cls(version=manifest.version, values=manifest.values)


@dataclass
class AIProxyAsk:
    ask_id: str
    asset_id: int
    character: str
    phase: str
    pipeline: str
    pipeline_stage: str
    ollama_attempt_id: str
    worker_type: str
    ollama_model: str
    prompt_file: str
    expected_output: str
    candidate_output_file: Optional[str] = None
    task_type: Optional[str] = None
    auxiliary: bool = False
    manual: bool = False
    target_output_file: Optional[str] = None
    render_preset: Optional[str] = None
    reference_files: list[dict | ReferenceFile] = field(default_factory=list)


@dataclass
class AIProxyPaths:
    proxy_root: Path
    ask_root: Path
    claims_root: Path
    claimed_root: Path
    answer_root: Path
    failed_root: Path
    archive_root: Path
    control_root: Path
    monitor_root: Path
    monitor_requests_root: Path
    monitor_responses_root: Path


@dataclass
class AIProxyAnswer:
    ask_id: str
    asset_id: Optional[int]
    ollama_attempt_id: str
    worker_id: str
    status: str
    expected_output: str
    error_type: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class MonitorTestResult:
    test_id: str
    worker_id: str
    host: str
    status: str
    ollama_ok: bool
    models: list[str]
    message: Optional[str] = None
    responded_at: Optional[str] = None


@dataclass
class HarvestResult:
    answer_path: Path
    ask_id: str
    asset_id: Optional[int]
    status: str
    message: str
