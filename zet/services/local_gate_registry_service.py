from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Callable
from uuid import uuid4

from PIL import Image

from zet.services.atomic_file_service import write_json_atomic
from zet.services.candidate_review_contract import ReviewGate


GATE_STATUSES = {"Active", "Warning", "Disabled"}


@dataclass(frozen=True)
class LocalGatePipeline:
    key: str
    label: str
    views: tuple[str, ...]
    service_factory: Callable[[Any, str | Path], Any]
    gates_for_view: Callable[[Any, str], list[ReviewGate]]
    interpret: Callable[[str, str], dict[str, str]]
    default_disabled: frozenset[str] = frozenset()


class LocalGateRegistryService:
    """Shared catalog and persisted policy for local image pipeline gates."""

    _registered_pipelines: dict[str, LocalGatePipeline] | None = None

    def __init__(self, app: Any, project_root: str | Path):
        self.app = app
        self.project_root = Path(project_root).resolve()
        self.root = Path(app.config.base_library_path).resolve() / "Experiments" / "Gate-Test-Rig"
        self.settings_path = self.root / "pipeline-settings.json"
        self.case_root = self.root / "cases"
        self.saved_test_root = self.root / "saved-tests"
        self.pipelines = type(self)._pipelines()

    @classmethod
    def _pipelines(cls) -> dict[str, LocalGatePipeline]:
        if cls._registered_pipelines is not None:
            return cls._registered_pipelines
        from zet.services.local_body_reference_service import (
            DEFAULT_VIEWS, LocalBodyReferenceService, _parse_orientation_gate_verdict,
            _parse_passing_gate_verdict,
        )
        from zet.services.local_head_image_service import LocalHeadImageService, VIEWS

        def body_factory(app: Any, root: str | Path) -> Any:
            return LocalBodyReferenceService(app, root)

        def head_factory(app: Any, root: str | Path) -> Any:
            return LocalHeadImageService(app, root)

        def body_gates(_service: Any, view: str) -> list[ReviewGate]:
            return LocalBodyReferenceService.review_gates(view)

        def head_gates(_service: Any, view: str) -> list[ReviewGate]:
            return LocalHeadImageService.review_gates(view, has_front_source=True)

        def body_interpret(gate: str, response: str) -> dict[str, str]:
            if gate == "orientation":
                rejected, reason = _parse_orientation_gate_verdict(response)
            elif gate in {"proportion", "framing", "body_identity"}:
                rejected, reason = _parse_passing_gate_verdict(response)
            else:
                from zet.services.candidate_review_contract import parse_rejection_verdict
                rejected, reason = parse_rejection_verdict(response), ""
            return {"result": "FAIL" if rejected == "TRUE" else "PASS", "reason": reason}

        def head_interpret(gate: str, response: str) -> dict[str, str]:
            from zet.services.candidate_review_contract import parse_rejection_verdict
            rejected = parse_rejection_verdict(response)
            return {"result": "FAIL" if rejected == "TRUE" else "PASS", "reason": ""}

        cls._registered_pipelines = {
            "body-reference": LocalGatePipeline(
                "body-reference", "Local Body-Reference", tuple(DEFAULT_VIEWS), body_factory,
                body_gates, body_interpret, frozenset({"orientation"}),
            ),
            "head-image": LocalGatePipeline(
                "head-image", "Local Head-Image", tuple(VIEWS), head_factory,
                head_gates, head_interpret,
            ),
        }
        return cls._registered_pipelines

    @classmethod
    def register_pipeline(cls, pipeline: LocalGatePipeline) -> None:
        """Register a future local pipeline adapter before building the rig catalog."""
        pipelines = cls._pipelines()
        if pipeline.key in pipelines:
            raise ValueError(f"Local pipeline is already registered: {pipeline.key}")
        cls._registered_pipelines[pipeline.key] = pipeline

    def pipeline(self, pipeline: str) -> LocalGatePipeline:
        key = str(pipeline or "").strip()
        if key not in self.pipelines:
            raise ValueError(f"Unknown local pipeline: {key}")
        return self.pipelines[key]

    def _gate_keys(self, pipeline: LocalGatePipeline) -> set[str]:
        return {gate.key for view in pipeline.views for gate in pipeline.gates_for_view(None, view)}

    def _settings(self) -> dict[str, Any]:
        try:
            value = json.loads(self.settings_path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                return value
        except (OSError, json.JSONDecodeError):
            pass
        return {}

    def catalog(self, pipeline: str = "") -> dict[str, Any]:
        if not pipeline:
            return {"pipelines": [{"key": item.key, "label": item.label, "views": list(item.views)}
                                   for item in self.pipelines.values()]}
        definition = self.pipeline(pipeline)
        gates_by_view = {}
        all_gates: dict[str, dict[str, Any]] = {}
        for view in definition.views:
            values = []
            for gate in definition.gates_for_view(None, view):
                roles = list(gate.input_roles)
                if gate.crop_head and "candidate_head" not in roles:
                    roles.append("candidate_head")
                elif "candidate" not in roles:
                    roles.append("candidate")
                if gate.uses_anchor and "front_anchor" not in roles:
                    roles.append("front_anchor")
                if gate.uses_source and "front_source" not in roles:
                    roles.append("front_source")
                item = {"key": gate.key, "prompt": gate.prompt, "uses_anchor": gate.uses_anchor,
                        "crop_head": gate.crop_head, "uses_source": gate.uses_source,
                        "image_roles": roles}
                values.append(item)
                all_gates.setdefault(gate.key, item)
            gates_by_view[view] = values
        settings = self._settings().get(definition.key, {})
        statuses = {}
        for key in all_gates:
            default = "Disabled" if key in definition.default_disabled else "Active"
            status = str((settings.get(key) or {}).get("status") or default)
            statuses[key] = status if status in GATE_STATUSES else default
        return {"pipeline": definition.key, "label": definition.label, "views": list(definition.views),
                "gates": all_gates, "gates_by_view": gates_by_view, "statuses": statuses}

    def status(self, pipeline: str, gate: str) -> str:
        definition = self.pipeline(pipeline)
        catalog = self.catalog(pipeline)
        if gate not in catalog["gates"]:
            raise ValueError(f"Unknown {definition.label} gate: {gate}")
        return catalog["statuses"][gate]

    def set_status(self, pipeline: str, gate: str, status: str) -> dict[str, Any]:
        definition = self.pipeline(pipeline)
        if gate not in self.catalog(pipeline)["gates"]:
            raise ValueError(f"Unknown {definition.label} gate: {gate}")
        if status not in GATE_STATUSES:
            raise ValueError("Gate status must be Active, Warning, or Disabled.")
        value = self._settings()
        value.setdefault(definition.key, {}).setdefault(gate, {})["status"] = status
        write_json_atomic(self.settings_path, value)
        return self.catalog(pipeline)

    def definitions_for_view(self, pipeline: str, view: str) -> list[dict[str, Any]]:
        catalog = self.catalog(pipeline)
        view = str(view or "").strip().upper()
        if view not in catalog["gates_by_view"]:
            raise ValueError(f"Unknown {catalog['label']} view: {view}")
        return [{**gate, "status": catalog["statuses"][gate["key"]]}
                for gate in catalog["gates_by_view"][view]]

    def list_cases(self, pipeline: str = "", gate: str = "") -> list[dict[str, Any]]:
        if pipeline:
            self.pipeline(pipeline)
        paths = [self.case_root / pipeline / gate / "*.json"] if pipeline and gate else []
        if pipeline and not gate:
            paths = [self.case_root / pipeline / "*" / "*.json"]
        elif not pipeline:
            paths = [self.case_root / "*" / "*" / "*.json"]
        values = []
        for pattern in paths:
            for path in pattern.parent.glob(pattern.name):
                try:
                    value = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    continue
                if value.get("case_id") == path.stem:
                    values.append(value)
        return sorted(values, key=lambda item: (item.get("pipeline", ""), item.get("gate", ""), item.get("view", ""), item.get("case_id", "")))

    def _case_path(self, pipeline: str, gate: str, case_id: str) -> Path:
        if not all(part and Path(part).name == part for part in (pipeline, gate, case_id)):
            raise ValueError("Invalid curated case identifier.")
        return self.case_root / pipeline / gate / f"{case_id}.json"

    @staticmethod
    def _image(contents: Any, label: str) -> bytes:
        if not isinstance(contents, str) or not contents:
            raise ValueError(f"{label} image is required.")
        if contents.startswith("data:"):
            import base64
            try:
                contents = contents.split(",", 1)[1]
                data = base64.b64decode(contents, validate=True)
            except Exception as exc:
                raise ValueError(f"{label} image data is invalid.") from exc
        elif isinstance(contents, str):
            import base64
            try:
                data = base64.b64decode(contents, validate=True)
            except Exception as exc:
                raise ValueError(f"{label} image data is invalid.") from exc
        else:
            data = contents
        try:
            from io import BytesIO
            image = Image.open(BytesIO(data)).convert("RGBA")
            output = BytesIO()
            image.save(output, format="PNG")
            data = output.getvalue()
        except Exception as exc:
            raise ValueError(f"{label} must be a valid image.") from exc
        return data

    def save_case(self, payload: dict[str, Any], case_id: str = "") -> dict[str, Any]:
        pipeline = self.pipeline(str(payload.get("pipeline") or ""))
        gate = str(payload.get("gate") or "").strip()
        view = str(payload.get("view") or "").strip().upper()
        if view not in pipeline.views:
            raise ValueError(f"Unknown {pipeline.label} view: {view}")
        gate_def = next((item for item in self.definitions_for_view(pipeline.key, view) if item["key"] == gate), None)
        if gate_def is None:
            raise ValueError(f"Gate {gate} does not apply to {view}.")
        expected = str(payload.get("expected") or "").upper()
        if expected not in {"PASS", "FAIL"}:
            raise ValueError("Expected answer must be PASS or FAIL.")
        path = self._case_path(pipeline.key, gate, case_id or uuid4().hex)
        existing = {}
        if case_id:
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise ValueError(f"Curated case not found: {case_id}") from exc
        candidate = self._image(payload.get("image_data"), "Candidate") if payload.get("image_data") else None
        refs = {}
        reference_data = payload.get("reference_data") or {}
        if not isinstance(reference_data, dict):
            raise ValueError("Reference images must be an object keyed by image role.")
        required_roles = [role for role in gate_def["image_roles"]
                          if role not in {"candidate", "candidate_head"}]
        previous_refs = existing.get("references", {})
        for role in required_roles:
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", role):
                raise ValueError(f"Unsupported gate image role: {role}")
            raw = reference_data.get(role) or payload.get(f"{role}_data")
            previous = previous_refs.get(role)
            if raw:
                refs[role] = hashlib.sha256(self._image(raw, role.replace("_", " ").title())).hexdigest()
            elif previous:
                refs[role] = previous
            else:
                raise ValueError(f"{role.replace('_', ' ').title()} image is required for this gate.")
        image_hash = hashlib.sha256(candidate).hexdigest() if candidate else existing.get("image_sha256", "")
        if not image_hash:
            raise ValueError("Candidate image is required.")
        value = {"case_id": path.stem, "pipeline": pipeline.key, "gate": gate, "view": view,
                 "expected": expected, "image_sha256": image_hash, "references": refs,
                 "updated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds")}
        path.parent.mkdir(parents=True, exist_ok=True)
        if candidate:
            (path.parent / f"{path.stem}.candidate.png").write_bytes(candidate)
        for role in required_roles:
            raw = reference_data.get(role) or payload.get(f"{role}_data")
            if raw:
                (path.parent / f"{path.stem}.{role}.png").write_bytes(self._image(raw, role))
        write_json_atomic(path, value)
        return value

    def case_image_path(self, pipeline: str, gate: str, case_id: str, role: str = "candidate") -> Path:
        path = self._case_path(pipeline, gate, case_id)
        if not path.is_file():
            raise ValueError(f"Curated case not found: {case_id}")
        suffix = "candidate" if role == "candidate" else role
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", suffix):
            raise ValueError("Unknown case image role.")
        image_path = path.with_name(f"{case_id}.{suffix}.png")
        if not image_path.is_file():
            raise ValueError(f"Curated case image not found: {role}")
        return image_path

    def delete_case(self, pipeline: str, gate: str, case_id: str) -> None:
        path = self._case_path(pipeline, gate, case_id)
        if not path.is_file():
            raise ValueError(f"Curated case not found: {case_id}")
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            record = {}
        path.unlink()
        for role in ("candidate", *list((record.get("references") or {}).keys())):
            path.with_name(f"{case_id}.{role}.png").unlink(missing_ok=True)
