"""Read-only Adventure Log Markdown parsing, independent of scene authoring."""
from dataclasses import replace
from datetime import datetime
import hashlib
from pathlib import Path
import re

from zet.models.scene_candidate import SceneCandidate, SceneCandidateSource


class SceneCandidateSourceService:
    FIELD_RE = re.compile(r"^\*\*(?P<label>[^*]+):\*\*\s*(?P<value>.*)$")
    HEADING_RE = re.compile(r"^###\s+Scene\s+(.+?)\s+[—-]\s+(.+?)\s*$")

    def __init__(self, config):
        self.config = config

    @staticmethod
    def _normalize(value: str) -> str:
        return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())

    @staticmethod
    def _known(value: str) -> str:
        text = str(value or "").strip()
        return "" if text.casefold().startswith("unknown") else text

    def list_sources(self) -> list[SceneCandidateSource]:
        sources = []
        for configured in self.config.scene_candidate_sources:
            path = Path(configured.path).expanduser()
            exists = path.is_file()
            modified = datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds") if exists else ""
            error = "" if exists else f"Scene candidate index not found: {path}"
            sources.append(SceneCandidateSource(
                key=configured.key,
                label=configured.label,
                path=str(path),
                default_story_slug=configured.default_story_slug,
                read_only=configured.read_only,
                exists=exists,
                modified_at=modified,
                error=error,
            ))
        return sources

    def _source(self, source_key: str) -> SceneCandidateSource:
        for source in self.list_sources():
            if source.key == str(source_key or "").strip():
                if not source.read_only:
                    raise ValueError(f"Scene candidate source must be read-only: {source.key}")
                if not source.exists:
                    raise ValueError(source.error)
                return source
        raise ValueError(f"Unknown scene candidate source: {source_key}")

    @staticmethod
    def _field_value(lines: list[str]) -> object:
        cleaned = [line.rstrip() for line in lines]
        while cleaned and not cleaned[0].strip():
            cleaned.pop(0)
        while cleaned and not cleaned[-1].strip():
            cleaned.pop()
        bullets = [re.sub(r"^\s*[-*]\s+", "", line).strip() for line in cleaned if re.match(r"^\s*[-*]\s+", line)]
        nonblank = [line.strip() for line in cleaned if line.strip()]
        if bullets and len(bullets) == len(nonblank):
            return bullets
        return "\n".join(nonblank).strip()

    def _parse_block(self, source_key: str, heading_id: str, title: str, lines: list[str]) -> SceneCandidate:
        fields: dict[str, object] = {}
        current = ""
        buffer: list[str] = []
        for line in lines:
            match = self.FIELD_RE.match(line.strip())
            if match:
                if current:
                    fields[current] = self._field_value(buffer)
                current = match.group("label").strip()
                buffer = [match.group("value")] if match.group("value").strip() else []
            elif current:
                buffer.append(line)
        if current:
            fields[current] = self._field_value(buffer)
        candidate_id = str(fields.get("Candidate ID") or heading_id).strip()
        session = str(fields.get("Source Session") or "").strip()
        raw = "\n".join([f"### Scene {heading_id} — {title}", *lines]).strip()
        warnings = []
        if not fields.get("Candidate ID"):
            warnings.append("Candidate ID is inherited from the heading; add an explicit stable Candidate ID.")
        if "TBD" in candidate_id.upper():
            warnings.append("Candidate ID is not stable because it contains TBD.")
        for required in ("Story Beat", "Location"):
            if not fields.get(required):
                warnings.append(f"Missing required field: {required}.")
        return SceneCandidate(
            source_key=source_key,
            candidate_id=candidate_id,
            session=session,
            title=title.strip(),
            status=str(fields.get("Status") or "Candidate").strip(),
            fields=fields,
            content_hash=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            warnings=warnings,
        )

    def _parse(self, source: SceneCandidateSource) -> list[SceneCandidate]:
        text = Path(source.path).read_text(encoding="utf-8")
        lines = text.splitlines()
        candidates = []
        current: tuple[str, str] | None = None
        buffer: list[str] = []
        for line in lines:
            match = self.HEADING_RE.match(line.strip())
            if match and "[Scene Title]" not in match.group(2):
                if current:
                    candidates.append(self._parse_block(source.key, current[0], current[1], buffer))
                current = (match.group(1).strip(), match.group(2).strip())
                buffer = []
            elif current:
                buffer.append(line)
        if current:
            candidates.append(self._parse_block(source.key, current[0], current[1], buffer))
        counts: dict[str, int] = {}
        for candidate in candidates:
            counts[candidate.candidate_id] = counts.get(candidate.candidate_id, 0) + 1
        return [
            replace(candidate, warnings=[*candidate.warnings, "Duplicate Candidate ID."])
            if counts[candidate.candidate_id] > 1 else candidate
            for candidate in candidates
        ]

