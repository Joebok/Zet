"""Versioned public contracts for local prompt-authoring pilot sessions."""
from __future__ import annotations

from dataclasses import MISSING, asdict, dataclass
from typing import Any


PROMPT_PACKET_VERSION = 1
PROMPT_SESSION_VERSION = 2
SEED_COUNT = 4


@dataclass(frozen=True)
class PromptPacket:
    """Immutable compiler output and the image bindings used to author a prompt."""

    universe_id: str
    pipeline: str
    run_id: str
    costume: str
    view: str
    operation: str
    packet_id: str
    packet_hash: str
    prompt: str
    baseline_prompt: str
    baseline_input: dict[str, Any]
    sources: dict[str, str]
    facts: dict[str, Any] | None = None
    references: tuple[dict[str, Any], ...] = ()
    analysis_references: tuple[dict[str, Any], ...] = ()
    criteria: tuple[str, ...] = ()
    required_constraints: tuple[str, ...] = ()
    render_preset: str = ""
    render_settings: dict[str, Any] | None = None
    instruction_modules: dict[str, Any] | None = None
    direction: str = ""
    prior_attempts: dict[str, Any] | None = None
    edit_base_attempt_id: str = ""
    rendering_mode: str = ""
    revision: int = 1
    version: int = PROMPT_PACKET_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "PromptPacket":
        if value.get("version") != PROMPT_PACKET_VERSION:
            raise ValueError("Unsupported prompt packet version.")
        fields = {}
        for key, field in cls.__dataclass_fields__.items():
            if key == "version":
                continue
            if key in value:
                fields[key] = value[key]
            elif field.default is not MISSING:
                fields[key] = field.default
            elif field.default_factory is not MISSING:
                fields[key] = field.default_factory()
            else:
                raise ValueError(f"Prompt packet is missing required field: {key}")
        return cls(**fields,
                   version=value["version"])


@dataclass(frozen=True)
class PromptDraft:
    packet_id: str
    packet_hash: str
    prompt: str
    reference_ids: tuple[str, ...] = ()
    proposals: tuple[str, ...] = ()
    approved_hash: str = ""
    approved: bool = False


@dataclass(frozen=True)
class PromptAttempt:
    attempt_id: str
    request_id: str
    seed: int
    status: str
    input: dict[str, Any]
    image_sha256: str = ""
    error: str = ""


@dataclass(frozen=True)
class PromptRound:
    round_id: str
    kind: str
    packet_hash: str
    prompt: str
    attempts: tuple[PromptAttempt, ...]


@dataclass(frozen=True)
class PromptDecision:
    destination: str
    text: str
    packet_hash: str
    status: str = "READY_FOR_REVIEW"


@dataclass(frozen=True)
class PromptSeedSet:
    seeds: tuple[int, ...]
    version: int = 1


@dataclass(frozen=True)
class PromptGeneratorSession:
    session_id: str
    universe_id: str
    pipeline: str
    run_id: str
    view: str
    packet: PromptPacket
    seeds: PromptSeedSet
    status: str = "SETUP"
    revision: int = 0
    version: int = PROMPT_SESSION_VERSION
