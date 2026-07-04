from __future__ import annotations

import argparse
from datetime import datetime
import difflib
import json
import re
from dataclasses import asdict
from pathlib import Path
import sys
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from zet.app import ZetApp
from zet.render_console.queue import RenderConsoleQueue
from zet.services.config_service import ConfigService
from zet.services.pipeline_control_service import AutomationSettings
PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parents[1]
SCRIPTS_PATH = PROJECT_ROOT / "Scripts"
if str(SCRIPTS_PATH) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_PATH))

from zet.services.prompt_review_service import LocalRenderUnavailable

from Compile_Character_Template import MARKER_RE
from Template_Section_Editor import save_template_sections


def _app(config_path: str | Path) -> ZetApp:
    return ZetApp.from_config(config_path)


def _render_console_queue(config_path: str | Path) -> RenderConsoleQueue:
    return RenderConsoleQueue(ConfigService.load(config_path))


def _view_key(value: Any) -> str:
    """Normalize an asset view value to a config lookup key."""
    return re.sub(r"[^A-Z0-9]+", "_", str(value or "").upper()).strip("_")


def _gpt_helper_prompt_path(config_path: str | Path) -> Path:
    """Resolve the GPT helper prompt config path for this app instance."""
    local_path = Path(config_path).resolve().parent / "Config" / "GPT_Helper_Prompts.json"
    if local_path.exists():
        return local_path
    return PROJECT_ROOT / "Config" / "GPT_Helper_Prompts.json"


def _read_json_file(path: Path) -> dict[str, Any]:
    """Read a JSON object file, returning an empty object on failure."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return data


def _read_gpt_helper_prompt_config(path: Path) -> dict[str, Any]:
    """Read a phase-local GPT helper prompt config, returning a valid empty shape if missing."""
    data = _read_json_file(path)
    data.setdefault("schema_version", 1)
    data.setdefault("pipelines", {})
    return data


def _write_gpt_helper_prompt_config(path: Path, data: dict[str, Any]) -> Path:
    """Write the GPT helper prompt config atomically."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temp_path.replace(path)
    return path


def _render_console_asset_for_task(zet_app: ZetApp, task):
    """Look up the asset associated with a render-console task."""
    if task.asset_id is None:
        return None
    try:
        return zet_app.asset(task.character, task.phase, int(task.asset_id)).get()
    except Exception:
        return None


def _view_keys() -> list[str]:
    """Return all configured normalized view keys."""
    view_text_path = PROJECT_ROOT / "Config" / "Prompt_View_Text.json"
    data = _read_json_file(view_text_path)
    views = data.get("views", {})
    if not isinstance(views, dict):
        return []
    return [str(key) for key in views.keys()]


def _phase_gpt_helper_prompt_path(zet_app: ZetApp, task) -> Path | None:
    """Resolve the per-character-phase GPT helper prompt config path for a render task."""
    asset = _render_console_asset_for_task(zet_app, task)
    if asset is None:
        return None
    return zet_app.path_service.gpt_helper_prompt_path(asset.character, asset.phase)


def _seed_phase_gpt_helper_prompt_config(zet_app: ZetApp, path: Path, task) -> Path:
    """Create a per-phase GPT helper prompt config from the legacy global config."""
    asset = _render_console_asset_for_task(zet_app, task)
    if asset is None:
        raise ValueError("Cannot seed helper prompts because the render task is not tied to an asset.")
    legacy = _read_json_file(_gpt_helper_prompt_path(zet_app.config_path))
    legacy_defaults = legacy.get("defaults", {}) if isinstance(legacy.get("defaults"), dict) else {}
    legacy_pipelines = legacy.get("pipelines", {}) if isinstance(legacy.get("pipelines"), dict) else {}
    phase_pipelines: dict[str, dict[str, str]] = {}
    view_keys = _view_keys()
    for pipeline in zet_app.pipeline_repository.list_pipelines(asset.character, asset.phase):
        legacy_pipeline = legacy_pipelines.get(pipeline.name, {}) if isinstance(legacy_pipelines.get(pipeline.name), dict) else {}
        prompts: dict[str, str] = {}
        for view in view_keys:
            text = str(legacy_pipeline.get(view) or legacy_pipeline.get("__default") or legacy_defaults.get(view) or "").strip()
            prompts[view] = text
        phase_pipelines[pipeline.name] = prompts
    return _write_gpt_helper_prompt_config(path, {"schema_version": 1, "pipelines": phase_pipelines})


def _ensure_phase_gpt_helper_prompt_config(zet_app: ZetApp, task) -> Path:
    """Return a ready per-phase GPT helper prompt config path, seeding it if needed."""
    path = _phase_gpt_helper_prompt_path(zet_app, task)
    if path is None:
        raise ValueError("Cannot load helper prompts because the render task is not tied to an asset.")
    if not path.exists():
        _seed_phase_gpt_helper_prompt_config(zet_app, path, task)
    return path


def _gpt_helper_prompt(zet_app: ZetApp, config_path: str | Path, task) -> dict[str, str]:
    """Return the short manual ChatGPT helper prompt for a render-console task."""
    asset = _render_console_asset_for_task(zet_app, task)
    if asset is None:
        return {"text": "", "view": "", "source": ""}

    view = _view_key(asset.body_view)
    path = _ensure_phase_gpt_helper_prompt_config(zet_app, task)
    data = _read_gpt_helper_prompt_config(path)
    pipelines = data.get("pipelines", {}) if isinstance(data, dict) else {}
    pipeline_prompts = pipelines.get(asset.pipeline, {}) if isinstance(pipelines, dict) else {}
    text = ""
    source = ""
    if isinstance(pipeline_prompts, dict):
        text = str(pipeline_prompts.get(view) or "").strip()
        source = f"pipeline:{asset.pipeline}" if text else ""
    return {"text": text, "view": view, "source": source, "pipeline": asset.pipeline, "config_path": str(path)}


def _save_gpt_helper_prompt(zet_app: ZetApp, config_path: str | Path, task, text: str) -> dict[str, str]:
    """Save a pipeline/view GPT helper prompt override for a render-console task."""
    asset = _render_console_asset_for_task(zet_app, task)
    if asset is None:
        raise ValueError("Cannot save helper prompt because the render task is not tied to an asset.")
    view = _view_key(asset.body_view)
    if not view:
        raise ValueError("Cannot save helper prompt because the asset has no view.")

    path = _ensure_phase_gpt_helper_prompt_config(zet_app, task)
    data = _read_gpt_helper_prompt_config(path)
    pipelines = data.setdefault("pipelines", {})
    if not isinstance(pipelines, dict):
        pipelines = {}
        data["pipelines"] = pipelines
    pipeline_prompts = pipelines.setdefault(asset.pipeline, {})
    if not isinstance(pipeline_prompts, dict):
        pipeline_prompts = {}
        pipelines[asset.pipeline] = pipeline_prompts

    cleaned = str(text or "").strip()
    if cleaned:
        pipeline_prompts[view] = cleaned
    else:
        pipeline_prompts[view] = ""

    path = _write_gpt_helper_prompt_config(path, data)
    prompt = _gpt_helper_prompt(zet_app, config_path, task)
    prompt["config_path"] = str(path)
    return prompt


def _format_value(value: Any) -> str:
    return "None" if value is None else str(value)


def _format_timestamp_with_age(value: Any) -> str:
    return _format_value(value)


def _discover_characters(base_character_path: str) -> list[str]:
    root = Path(base_character_path)
    if not root.exists() or not root.is_dir():
        return []
    return sorted(path.name for path in root.iterdir() if path.is_dir())


def _discover_phases(base_character_path: str, character: str) -> list[str]:
    root = Path(base_character_path) / character
    if not root.exists() or not root.is_dir():
        return []
    return sorted(path.name for path in root.iterdir() if path.is_dir())


def _review_image_ready(zet_app: ZetApp, asset) -> bool:
    if asset.pipeline_stage == "PROMPT_REVIEW":
        if asset.pipeline != "Body-Reference":
            return False
        try:
            context = zet_app.prompt_review_service.get_context(asset.character, asset.phase, asset.asset_id)
            return context.latest_local_test_render is not None
        except Exception:
            return False
    if asset.pipeline_stage == "RENDER_REVIEW":
        try:
            return zet_app.path_service.candidate_image_path(asset).exists()
        except Exception:
            return False
    return False


def _is_prompt_review_asset(asset) -> bool:
    return asset.pipeline_stage == "PROMPT_REVIEW" and asset.actor == "HUMAN_AGENT"


def _is_render_review_asset(asset) -> bool:
    return asset.pipeline_stage == "RENDER_REVIEW" and asset.actor == "HUMAN_AGENT"


def _is_head_fitment_manifest_asset(asset) -> bool:
    return asset.pipeline == "Head-Fitment" and asset.pipeline_stage in {"MANIFEST", "ADD_REF"} and asset.actor == "PYTHON"


def _asset_payload(zet_app: ZetApp, asset) -> dict[str, Any]:
    """Serialize an asset for dashboard tables and detail panels."""
    data = asdict(asset)
    data["head_view"] = _format_value(asset.head_view)
    data["costume"] = _format_value(asset.costume)
    data["expression"] = _format_value(asset.expression)
    data["ai_state"] = _format_value(asset.ai_state)
    data["final_image_output"] = _format_value(asset.final_image_output)
    data["updated_at_display"] = _format_timestamp_with_age(asset.updated_at)
    render_comment = zet_app.render_review_comment(asset.character, asset.phase, asset.asset_id)
    data["render_review_comment"] = render_comment
    data["has_render_review_comment"] = bool(render_comment)
    data["review_image_ready"] = _review_image_ready(zet_app, asset)
    if asset.pipeline_stage == "ADD_REF" and asset.error_code:
        data["pipeline_stage_display"] = f"ADD_REF ({asset.error_code})"
    elif data["review_image_ready"]:
        data["pipeline_stage_display"] = f"CAMERA {asset.pipeline_stage}"
    else:
        data["pipeline_stage_display"] = asset.pipeline_stage
    return data


def _identity_key_payload(identity_key) -> dict[str, Any]:
    """Serialize an identity key for dashboard views."""
    return asdict(identity_key)


def _identity_key_preview_payload(preview) -> dict[str, Any]:
    """Serialize an identity key preview crop."""
    return asdict(preview)


def _costume_payload(costume) -> dict[str, Any]:
    """Serialize a costume template for dashboard views."""
    data = asdict(costume)
    data["source"] = {
        "source_kind": "costume_template",
        "source_label": costume.name,
        "source_path": costume.path,
        "editable": True,
    }
    return data


def _expression_definition_payload(expression) -> dict[str, Any]:
    """Serialize an expression definition for dashboard views."""
    data = asdict(expression)
    data["source"] = {
        "source_kind": "expression_definition",
        "source_label": expression.label,
        "source_path": expression.path,
        "editable": True,
    }
    return data


def _onboarding_status_payload(status) -> dict[str, Any]:
    """Serialize a character onboarding status for dashboard views."""
    return asdict(status)


def _onboarding_options_payload(options) -> dict[str, Any]:
    """Serialize character onboarding dropdown options."""
    return asdict(options)


def _prompt_review_task_payload(zet_app: ZetApp, asset) -> dict[str, Any]:
    payload = _asset_payload(zet_app, asset)
    try:
        context = zet_app.prompt_review_service.get_context(asset.character, asset.phase, asset.asset_id)
        payload["prompt_path"] = str(context.prompt_path) if context.prompt_path else None
        payload["condense_state"] = context.condense_status.get("state")
        payload["latest_local_test_render"] = str(context.latest_local_test_render) if context.latest_local_test_render else None
    except Exception:
        payload["prompt_path"] = None
        payload["condense_state"] = None
        payload["latest_local_test_render"] = None
    return payload


def _prompt_review_context_payload(zet_app: ZetApp, character: str, phase: str, asset_id: int) -> dict[str, Any]:
    context = zet_app.prompt_review_service.get_context(character, phase, asset_id)
    asset = context.asset
    return {
        "asset": _asset_payload(zet_app, asset),
        "is_reviewable": _is_prompt_review_asset(asset),
        "supports_local_test_render": asset.pipeline == "Body-Reference",
        "prompt_path": str(context.prompt_path) if context.prompt_path else None,
        "prompt_text": context.prompt_text or "",
        "condensed_prompt_path": str(context.condensed_prompt_path) if context.condensed_prompt_path else None,
        "condensed_prompt_text": context.condensed_prompt_text or "",
        "render_prompt_path": str(context.render_prompt_path) if context.render_prompt_path else None,
        "source_map_path": str(context.source_map_path) if context.source_map_path else None,
        "source_map": _jsonable(context.source_map),
        "prompt_review_path": str(context.prompt_review_path) if context.prompt_review_path else None,
        "latest_local_test_render": str(context.latest_local_test_render) if context.latest_local_test_render else None,
        "prompt_candidates": [str(path) for path in context.prompt_candidates],
        "condense_status": _jsonable(context.condense_status),
    }


def _render_review_task_payload(zet_app: ZetApp, asset) -> dict[str, Any]:
    payload = _asset_payload(zet_app, asset)
    try:
        candidate_image_path = zet_app.path_service.candidate_image_path(asset)
        locked_image_path = zet_app.path_service.locked_image_path(asset)
        payload["candidate_image_path"] = str(candidate_image_path)
        payload["candidate_image_exists"] = candidate_image_path.exists()
        payload["locked_image_path"] = str(locked_image_path)
        payload["locked_image_exists"] = locked_image_path.exists()
    except Exception:
        payload["candidate_image_path"] = None
        payload["candidate_image_exists"] = False
        payload["locked_image_path"] = None
        payload["locked_image_exists"] = False
    return payload


def _render_review_context_payload(zet_app: ZetApp, character: str, phase: str, asset_id: int) -> dict[str, Any]:
    detail = _asset_detail_payload(zet_app, character, phase, asset_id)
    asset = detail["asset"]
    return {
        "asset": asset,
        "is_reviewable": _is_render_review_asset(zet_app.asset(character, phase, asset_id).get()),
        "paths": detail["paths"],
        "exists": detail["exists"],
        "stage_text": detail["stage_text"],
        "history_text": detail["history_text"],
        "candidate_image_path": detail["paths"]["candidate_image_path"],
        "locked_image_path": detail["paths"]["locked_image_path"],
        "render_review_comment": zet_app.render_review_comment(character, phase, asset_id),
    }


def _head_fitment_manifest_task_payload(zet_app: ZetApp, asset) -> dict[str, Any]:
    payload = _asset_payload(zet_app, asset)
    payload["reference_count"] = len(asset.reference_files or [])
    payload["has_body_reference"] = any(ref.get("role") == "body_reference" for ref in asset.reference_files or [])
    payload["has_headshot"] = any(ref.get("role") == "headshot" for ref in asset.reference_files or [])
    return payload


def _head_fitment_manifest_context_payload(zet_app: ZetApp, character: str, phase: str, asset_id: int) -> dict[str, Any]:
    context = zet_app.head_fitment_reference_context(character, phase, asset_id)
    return {
        "asset": _asset_payload(zet_app, context["asset"]),
        "is_manifest_editable": context["is_manifest_editable"],
        "body_reference_options": _jsonable(context["body_reference_options"]),
        "headshot_options": _jsonable(context["headshot_options"]),
        "selected_body_reference": _jsonable(context["selected_body_reference"]),
        "selected_headshot": _jsonable(context["selected_headshot"]),
        "reference_files": _jsonable(context["reference_files"]),
    }


def _monitor_request_payloads(zet_app: ZetApp) -> list[dict[str, Any]]:
    root = zet_app.ai_proxy_service.ai_proxy_path_service.monitor_requests_root()
    if not root.exists():
        return []
    rows = []
    for request_path in sorted((path for path in root.iterdir() if path.is_dir()), reverse=True):
        manifest_path = request_path / "request.json"
        payload: dict[str, Any] = {}
        if manifest_path.exists():
            try:
                import json

                payload = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                payload = {}
        rows.append(
            {
                "test_id": payload.get("test_id") or request_path.name,
                "instruction": payload.get("instruction") or "",
                "created_at": payload.get("created_at") or "",
                "path": str(request_path),
            }
        )
    return rows


def _ai_controls_payload(zet_app: ZetApp) -> dict[str, Any]:
    queue_snapshot = zet_app.queue_snapshot()
    manual_render_asks = [
        item for item in queue_snapshot["ask"]
        if item.get("worker_type") == "manual_chatgpt_render"
    ]
    return {
        "stop_state": _jsonable(zet_app.proxy_stop_state()),
        "queue": _jsonable(queue_snapshot),
        "queue_counts": {key: len(value) for key, value in queue_snapshot.items()},
        "manual_render_asks": _jsonable(manual_render_asks),
        "monitor_requests": _monitor_request_payloads(zet_app),
        "monitor_responses": _jsonable(zet_app.list_monitor_responses()),
        "processes": [status.to_dict() for status in zet_app.process_statuses()],
    }


def _automation_settings_from_payload(payload: dict[str, Any]) -> AutomationSettings:
    return AutomationSettings(
        prompt_condense_enabled=bool(payload.get("prompt_condense_enabled", False)),
        prompt_condense_model=str(payload.get("prompt_condense_model", "")),
        prompt_condense_file=str(payload.get("prompt_condense_file", "")),
        local_render_auto_queue_after_condense=bool(payload.get("local_render_auto_queue_after_condense", False)),
        local_render_preset=str(payload.get("local_render_preset", "")),
        ai_harvest_auto_enabled=bool(payload.get("ai_harvest_auto_enabled", False)),
        ai_harvest_interval_seconds=int(payload.get("ai_harvest_interval_seconds", 0)),
        render_backend=str(payload.get("render_backend", "")),
    )


def _pipeline_controls_payload(zet_app: ZetApp, character: str, phase: str) -> dict[str, Any]:
    snapshot = zet_app.pipeline_control_snapshot(character, phase)
    pipeline_names = sorted({row.pipeline for row in snapshot.pipeline_rows})
    prompt_review_enabled = {
        name: any(row.pipeline == name and row.stage == "PROMPT_REVIEW" for row in snapshot.pipeline_rows)
        for name in pipeline_names
    }
    return {
        "config_path": str(snapshot.config_path),
        "pipelines_path": str(snapshot.pipelines_path),
        "automation": _jsonable(snapshot.automation),
        "pipeline_rows": _jsonable(snapshot.pipeline_rows),
        "project_config_rows": _jsonable(snapshot.project_config_rows),
        "pipeline_names": pipeline_names,
        "prompt_review_enabled": prompt_review_enabled,
    }


def _turnaround_row_payload(row) -> dict[str, Any]:
    """Serialize a turnaround dashboard row for the browser."""
    return _jsonable(row)


def _auxiliary_resource_payload(resource) -> dict[str, Any]:
    """Serialize an auxiliary resource for the browser."""
    return _jsonable(resource)


def _jsonable(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return _jsonable(asdict(value))
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value


def _source_for_line(source_map: dict[str, Any], line_number: int) -> dict[str, Any]:
    fragments = source_map.get("fragments") if isinstance(source_map, dict) else []
    if not isinstance(fragments, list):
        return {}
    for fragment in fragments:
        if not isinstance(fragment, dict):
            continue
        start = int(fragment.get("prompt_start_line") or 0)
        end = int(fragment.get("prompt_end_line") or start)
        if start <= line_number <= end:
            return fragment
    return {}


def _prompt_diff_payload(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    old_text = str(before.get("prompt_text") or "")
    new_text = str(after.get("prompt_text") or "")
    old_lines = old_text.splitlines()
    new_lines = new_text.splitlines()
    old_map = before.get("source_map") if isinstance(before.get("source_map"), dict) else {}
    new_map = after.get("source_map") if isinstance(after.get("source_map"), dict) else {}
    old_rows: list[dict[str, Any]] = []
    new_rows: list[dict[str, Any]] = []

    def row(line_no: int, text: str, status: str, source_map: dict[str, Any]) -> dict[str, Any]:
        source = _source_for_line(source_map, line_no)
        return {
            "line_no": line_no,
            "text": text,
            "status": status,
            "source_kind": source.get("source_kind") or "",
            "source_label": source.get("source_label") or "",
        }

    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines)
    for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
        old_status = "unchanged" if tag == "equal" else "changed"
        new_status = "unchanged" if tag == "equal" else "changed"
        if tag == "delete":
            old_status = "removed"
        elif tag == "insert":
            new_status = "added"

        for index in range(old_start, old_end):
            old_rows.append(row(index + 1, old_lines[index], old_status, old_map))
        for index in range(new_start, new_end):
            new_rows.append(row(index + 1, new_lines[index], new_status, new_map))

    return {
        "changed": old_text != new_text,
        "old_prompt_path": before.get("prompt_path"),
        "new_prompt_path": after.get("prompt_path"),
        "old_rows": old_rows,
        "new_rows": new_rows,
    }


def _record_source_edit(payload: dict[str, Any], result: dict[str, Any]) -> None:
    log_dir = PROJECT_ROOT / "Logs"
    log_dir.mkdir(exist_ok=True)
    entry = {
        "saved_at": datetime.now().isoformat(timespec="seconds"),
        "path": result.get("path"),
        "editor_type": result.get("editor_type"),
        "section_name": payload.get("section_name"),
        "json_pointer": payload.get("json_pointer"),
        "text_length": len(str(payload.get("text") or "")),
    }
    with (log_dir / "Source_Edits.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _resolve_editable_source_path(path: str) -> Path:
    requested = Path(path)
    if not requested.is_absolute():
        requested = PROJECT_ROOT / requested
    resolved = requested.resolve()
    project_root = PROJECT_ROOT.resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Source path must be inside the Zet project.") from exc
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail=f"Source file not found: {path}")
    return resolved


def _json_pointer_parts(pointer: str) -> list[str]:
    raw = str(pointer or "").strip()
    if not raw.startswith("/"):
        raise HTTPException(status_code=400, detail="JSON pointer must start with '/'.")
    return [part.replace("~1", "/").replace("~0", "~") for part in raw.split("/")[1:]]


def _get_json_pointer(data: Any, pointer: str) -> Any:
    item = data
    for part in _json_pointer_parts(pointer):
        if isinstance(item, dict):
            item = item[part]
        elif isinstance(item, list):
            item = item[int(part)]
        else:
            raise KeyError(part)
    return item


def _set_json_pointer(data: Any, pointer: str, value: Any) -> None:
    parts = _json_pointer_parts(pointer)
    if not parts:
        raise HTTPException(status_code=400, detail="Cannot replace the whole JSON document here.")
    item = data
    for part in parts[:-1]:
        item = item[int(part)] if isinstance(item, list) else item[part]
    last = parts[-1]
    if isinstance(item, list):
        item[int(last)] = value
    elif isinstance(item, dict):
        item[last] = value
    else:
        raise HTTPException(status_code=400, detail="JSON pointer does not reference an editable field.")


def _extract_markdown_section(path: Path, section_name: str) -> tuple[str, int | None, int | None]:
    text = path.read_text(encoding="utf-8")
    open_name = None
    content_start = 0
    start_line = None
    for marker in MARKER_RE.finditer(text):
        kind, name = marker.group(1), marker.group(2)
        if kind == "BEGIN":
            open_name = name
            content_start = marker.end()
            start_line = text.count("\n", 0, content_start) + 1
            continue
        if open_name == section_name and kind == "END" and name == section_name:
            end_line = text.count("\n", 0, marker.start()) + 1
            return text[content_start:marker.start()].strip("\n"), start_line, end_line
        open_name = None
    raise HTTPException(status_code=404, detail=f"Section not found: {section_name}")


def _edit_source_payload(source: dict[str, Any]) -> dict[str, Any]:
    kind = str(source.get("source_kind") or "")
    path = _resolve_editable_source_path(str(source.get("source_path") or ""))
    section = str(source.get("section_name") or "")
    json_pointer = str(source.get("json_pointer") or "")
    warning = ""
    if kind == "shared_template_section":
        warning = "Shared template edits can affect multiple characters and phases."
    if section:
        text, start_line, end_line = _extract_markdown_section(path, section)
        editor_type = "markdown_section"
    elif json_pointer:
        data = json.loads(path.read_text(encoding="utf-8"))
        text = _get_json_pointer(data, json_pointer)
        if isinstance(text, (list, dict)):
            text = json.dumps(text, indent=2, ensure_ascii=False)
        editor_type = "json_field"
        start_line = end_line = None
    else:
        text = path.read_text(encoding="utf-8")
        editor_type = "markdown_file"
        start_line = end_line = None
    return {
        "source": source,
        "editor_type": editor_type,
        "path": str(path),
        "section_name": section or None,
        "json_pointer": json_pointer or None,
        "text": str(text),
        "start_line": start_line,
        "end_line": end_line,
        "warning": warning,
    }


def _save_edit_source(payload: dict[str, Any]) -> dict[str, Any]:
    path = _resolve_editable_source_path(str(payload.get("path") or ""))
    editor_type = str(payload.get("editor_type") or "")
    text = str(payload.get("text") or "")
    if editor_type == "markdown_section":
        section = str(payload.get("section_name") or "")
        if not section:
            raise HTTPException(status_code=400, detail="Missing section name.")
        save_template_sections(path, {section: text}, [section])
    elif editor_type == "json_field":
        pointer = str(payload.get("json_pointer") or "")
        data = json.loads(path.read_text(encoding="utf-8"))
        current = _get_json_pointer(data, pointer)
        value: Any = text
        if isinstance(current, list):
            value = [line.strip() for line in text.splitlines() if line.strip()]
        elif isinstance(current, (int, float, bool, dict)):
            value = json.loads(text)
        _set_json_pointer(data, pointer, value)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    elif editor_type == "markdown_file":
        path.write_text(text, encoding="utf-8")
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported editor type: {editor_type}")
    result = {"status": "SAVED", "path": str(path), "editor_type": editor_type}
    _record_source_edit(payload, result)
    return result


def _asset_detail_payload(zet_app: ZetApp, character: str, phase: str, asset_id: int) -> dict[str, Any]:
    asset_ref = zet_app.asset(character, phase, asset_id)
    asset = asset_ref.get()
    pipeline_path = asset_ref.pipeline_path()
    candidate_image_path = asset_ref.candidate_image_path()
    locked_image_path = asset_ref.locked_image_path()
    stage_path = pipeline_path / "_stage.txt"
    history_path = pipeline_path / "_history.log"
    return {
        "asset": _asset_payload(zet_app, asset),
        "paths": {
            "character_path": str(zet_app.path_service.character_path(character, phase)),
            "character_asset_path": str(zet_app.path_service.character_asset_path(character, phase)),
            "pipeline_path": str(pipeline_path),
            "candidate_image_path": str(candidate_image_path),
            "locked_image_path": str(locked_image_path),
        },
        "exists": {
            "candidate_image": candidate_image_path.exists(),
            "locked_image": locked_image_path.exists(),
            "stage": stage_path.exists(),
            "history": history_path.exists(),
        },
        "stage_text": stage_path.read_text(encoding="utf-8") if stage_path.exists() else "",
        "history_text": history_path.read_text(encoding="utf-8") if history_path.exists() else "",
    }


def _action_response(zet_app: ZetApp, character: str, phase: str, asset_id: int, message: str) -> dict[str, Any]:
    return {
        "message": message,
        "detail": _asset_detail_payload(zet_app, character, phase, asset_id),
        "assets": [_asset_payload(zet_app, asset) for asset in zet_app.list_assets(character, phase)],
    }


def create_app(config_path: str | Path = "config.toml") -> FastAPI:
    config_path = Path(config_path)
    config = ConfigService.load(config_path)
    app = FastAPI(title="Zet Web")
    app.state.config_path = str(config_path)

    app.mount("/static", StaticFiles(directory=PACKAGE_ROOT / "static"), name="zet_web_static")
    app.mount("/img", StaticFiles(directory=PROJECT_ROOT / "img"), name="zet_img")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (PACKAGE_ROOT / "templates" / "index.html").read_text(encoding="utf-8")

    @app.get("/api/context")
    def context() -> dict[str, Any]:
        current_config = ConfigService.load(app.state.config_path)
        zet_app = _app(app.state.config_path)
        characters = _discover_characters(current_config.base_character_path)
        phases_by_character = {
            character: _discover_phases(current_config.base_character_path, character)
            for character in characters
        }
        onboarding_statuses = {
            character: {
                phase: _onboarding_status_payload(zet_app.character_onboarding_status(character, phase))
                for phase in phases_by_character.get(character, [])
            }
            for character in characters
        }
        return {
            "characters": characters,
            "phases_by_character": phases_by_character,
            "onboarding_statuses": onboarding_statuses,
            "onboarding_options": _onboarding_options_payload(zet_app.character_onboarding_options()),
            "default_character": characters[0] if characters else None,
            "default_phase": phases_by_character.get(characters[0], [None])[0] if characters else None,
        }

    @app.get("/api/onboarding/prefill")
    def onboarding_prefill(character: str = Query(""), source_phase: str = Query("")) -> dict[str, Any]:
        """Return metadata defaults for a new character or phase draft."""
        zet_app = _app(app.state.config_path)
        try:
            return {"prefill": zet_app.character_onboarding_prefill(character, source_phase)}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/onboarding/draft")
    def onboarding_draft(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        """Create or update a draft character phase template."""
        zet_app = _app(app.state.config_path)
        try:
            draft = zet_app.save_character_onboarding_draft(payload)
            return {
                "draft": {
                    "character": draft.character,
                    "phase": draft.phase,
                    "template_path": draft.template_path,
                    "status": _onboarding_status_payload(draft.status),
                },
                "message": "Draft Character_Image_Template.md saved.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/onboarding/template")
    async def onboarding_template_upload(
        request: Request,
        character: str = Query(...),
        phase: str = Query(...),
    ) -> dict[str, Any]:
        """Upload, validate, and initialize a character image template."""
        zet_app = _app(app.state.config_path)
        try:
            contents = (await request.body()).decode("utf-8")
            status = zet_app.upload_character_template(character, phase, contents)
            message = "Template validated and foundation assets initialized." if status.complete else "Template saved; validation still has issues."
            return {"status": _onboarding_status_payload(status), "message": message}
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail="Character template must be UTF-8 markdown.") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/assets")
    def assets(character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            items = zet_app.list_assets(character, phase)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"assets": [_asset_payload(zet_app, asset) for asset in items]}

    @app.post("/api/assets/advance-displayed")
    def advance_displayed_assets(
        payload: dict[str, Any] = Body(...),
        character: str = Query(...),
        phase: str = Query(...),
    ) -> dict[str, Any]:
        """Advance the displayed non-locked assets through their current worker stage."""
        zet_app = _app(app.state.config_path)
        try:
            asset_ids = [int(value) for value in payload.get("asset_ids", [])]
            results = zet_app.advance_assets(character, phase, asset_ids)
            advanced = len([item for item in results if item.get("status") == "ADVANCED"])
            errors = len([item for item in results if item.get("status") == "ERROR"])
            skipped = len([item for item in results if item.get("status") == "SKIPPED"])
            return {
                "results": results,
                "assets": [_asset_payload(zet_app, asset) for asset in zet_app.list_assets(character, phase)],
                "message": f"Advanced {advanced} asset(s); skipped {skipped}; errors {errors}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/assets/{asset_id}")
    def asset_detail(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            return _asset_detail_payload(zet_app, character, phase, asset_id)
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/auxiliary-resources")
    def auxiliary_resources(category: str = Query("person")) -> dict[str, Any]:
        """List global auxiliary resources for one category."""
        zet_app = _app(app.state.config_path)
        try:
            return {"resources": [_auxiliary_resource_payload(item) for item in zet_app.list_auxiliary_resources(category)]}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/auxiliary-resources")
    async def auxiliary_resource_create(
        request: Request,
        category: str = Query(...),
        label: str = Query(...),
    ) -> dict[str, Any]:
        """Create a global auxiliary resource from uploaded image bytes."""
        zet_app = _app(app.state.config_path)
        try:
            resource = zet_app.create_auxiliary_resource(
                category,
                label,
                await request.body(),
                request.headers.get("content-type", ""),
            )
            return {
                "resource": _auxiliary_resource_payload(resource),
                "resources": [_auxiliary_resource_payload(item) for item in zet_app.list_auxiliary_resources(category)],
                "message": f"Created auxiliary resource {resource.label}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/auxiliary-resources/{resource_id}")
    async def auxiliary_resource_update(
        resource_id: str,
        request: Request,
        category: str = Query(...),
        label: str = Query(...),
        replace_image: bool = Query(False),
    ) -> dict[str, Any]:
        """Update a global auxiliary resource and optionally replace its image."""
        zet_app = _app(app.state.config_path)
        try:
            image_bytes = await request.body() if replace_image else None
            resource = zet_app.update_auxiliary_resource(
                resource_id,
                label,
                image_bytes,
                request.headers.get("content-type", ""),
            )
            return {
                "resource": _auxiliary_resource_payload(resource),
                "resources": [_auxiliary_resource_payload(item) for item in zet_app.list_auxiliary_resources(category)],
                "message": f"Updated auxiliary resource {resource.label}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/identity-keys")
    def identity_keys(character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        """List saved identity keys."""
        zet_app = _app(app.state.config_path)
        try:
            return {"identity_keys": [_identity_key_payload(item) for item in zet_app.list_identity_keys(character, phase)]}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/identity-keys/{identity_key_id}")
    def identity_key_detail(identity_key_id: str, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        """Return one saved identity key."""
        zet_app = _app(app.state.config_path)
        try:
            return {"identity_key": _identity_key_payload(zet_app.identity_key(character, phase, identity_key_id))}
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/identity-keys/preview")
    def identity_key_preview(payload: dict[str, Any] = Body(...), character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        """Generate a preview crop for an identity key."""
        zet_app = _app(app.state.config_path)
        try:
            preview = zet_app.preview_identity_key(
                character,
                phase,
                int(payload.get("source_asset_id") or 0),
                str(payload.get("label") or ""),
                float(payload.get("crop_percent") or 0),
                str(payload.get("identity_key_id") or "") or None,
            )
            return {"preview": _identity_key_preview_payload(preview)}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/identity-keys")
    def identity_key_save(payload: dict[str, Any] = Body(...), character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        """Save a new or existing identity key."""
        zet_app = _app(app.state.config_path)
        try:
            identity_key = zet_app.save_identity_key(
                character,
                phase,
                int(payload.get("source_asset_id") or 0),
                str(payload.get("label") or ""),
                float(payload.get("crop_percent") or 0),
                str(payload.get("identity_key_id") or "") or None,
            )
            return {
                "identity_key": _identity_key_payload(identity_key),
                "identity_keys": [_identity_key_payload(item) for item in zet_app.list_identity_keys(character, phase)],
                "message": "Identity Key saved.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/identity-keys/{identity_key_id}")
    def identity_key_delete(identity_key_id: str, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        """Delete an identity key."""
        zet_app = _app(app.state.config_path)
        try:
            zet_app.delete_identity_key(character, phase, identity_key_id)
            return {
                "identity_keys": [_identity_key_payload(item) for item in zet_app.list_identity_keys(character, phase)],
                "message": "Identity Key deleted.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/costumes")
    def costumes(character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        """List costume templates."""
        zet_app = _app(app.state.config_path)
        try:
            return {"costumes": [_costume_payload(item) for item in zet_app.list_costumes(character, phase)]}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/costumes")
    async def costume_create(
        request: Request,
        character: str = Query(...),
        phase: str = Query(...),
        costume_name: str = Query(...),
    ) -> dict[str, Any]:
        """Create a costume template and its Costume-Dressing assets."""
        zet_app = _app(app.state.config_path)
        try:
            contents = (await request.body()).decode("utf-8")
            result = zet_app.create_costume(character, phase, costume_name, contents)
            return {
                "costume": _costume_payload(result.costume),
                "costumes": [_costume_payload(item) for item in zet_app.list_costumes(character, phase)],
                "assets": [_asset_payload(zet_app, asset) for asset in zet_app.list_assets(character, phase)],
                "message": f"Created {len(result.assets)} Costume-Dressing assets for {result.costume.name}.",
            }
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail="Costume template must be UTF-8 markdown.") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/expressions")
    def expressions(character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        """List expression assets, definitions, and Identity Key choices."""
        zet_app = _app(app.state.config_path)
        try:
            return {
                "expression_assets": [
                    _asset_payload(zet_app, asset)
                    for asset in zet_app.list_expression_assets(character, phase)
                ],
                "expression_definitions": [
                    _expression_definition_payload(item)
                    for item in zet_app.list_expression_definitions(character, phase)
                ],
                "identity_keys": [
                    _identity_key_payload(item)
                    for item in zet_app.list_identity_keys(character, phase)
                ],
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/expressions")
    async def expression_create(
        request: Request,
        character: str = Query(...),
        phase: str = Query(...),
        label: str = Query(...),
        identity_key_id: str = Query(...),
    ) -> dict[str, Any]:
        """Create an expression definition and its Expression asset."""
        zet_app = _app(app.state.config_path)
        try:
            contents = (await request.body()).decode("utf-8")
            result = zet_app.create_expression(character, phase, label, identity_key_id, contents)
            return {
                "expression": _expression_definition_payload(result.expression),
                "asset": _asset_payload(zet_app, result.asset),
                "expression_assets": [
                    _asset_payload(zet_app, asset)
                    for asset in zet_app.list_expression_assets(character, phase)
                ],
                "expression_definitions": [
                    _expression_definition_payload(item)
                    for item in zet_app.list_expression_definitions(character, phase)
                ],
                "identity_keys": [
                    _identity_key_payload(item)
                    for item in zet_app.list_identity_keys(character, phase)
                ],
                "assets": [_asset_payload(zet_app, asset) for asset in zet_app.list_assets(character, phase)],
                "message": f"Created Expression asset for {result.expression.label}.",
            }
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail="Expression definition must be UTF-8 markdown.") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/file")
    def local_file(path: str = Query(...), download: bool = Query(False)):
        """Serve a local file inline or as a browser download."""
        requested = Path(path)
        if not requested.exists() or not requested.is_file():
            raise HTTPException(status_code=404, detail=f"File not found: {path}")
        if download:
            return FileResponse(requested, filename=requested.name)
        return FileResponse(requested)

    @app.post("/api/edit-source/load")
    def edit_source_load(source: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            if source.get("editable") is False:
                raise HTTPException(status_code=400, detail="This source is not editable.")
            return _edit_source_payload(source)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/edit-source/save")
    def edit_source_save(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            return _save_edit_source(payload)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/prompt-review/tasks")
    def prompt_review_tasks(character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            assets = [asset for asset in zet_app.list_assets(character, phase) if _is_prompt_review_asset(asset)]
            return {"tasks": [_prompt_review_task_payload(zet_app, asset) for asset in assets]}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/prompt-review/{asset_id}")
    def prompt_review_detail(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            return _prompt_review_context_payload(zet_app, character, phase, asset_id)
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/prompt-review/{asset_id}/local-test-render")
    def prompt_review_local_test_render(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            result = zet_app.generate_local_test_render(character, phase, asset_id)
            payload = _prompt_review_context_payload(zet_app, character, phase, asset_id)
            payload["message"] = f"Local test image generated: {result.image_path}"
            return payload
        except LocalRenderUnavailable as exc:
            raise HTTPException(status_code=503, detail="Local render backend unavailable.") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/prompt-review/{asset_id}/recompile")
    def prompt_review_recompile(
        asset_id: int,
        character: str = Query(...),
        phase: str = Query(...),
        invalidate_review_artifacts: bool = Query(False),
    ) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            before = _prompt_review_context_payload(zet_app, character, phase, asset_id)
            zet_app.recompile_prompt_review(
                character,
                phase,
                asset_id,
                invalidate_review_artifacts=invalidate_review_artifacts,
            )
            payload = _prompt_review_context_payload(zet_app, character, phase, asset_id)
            payload["prompt_diff"] = _prompt_diff_payload(before, payload)
            suffix = " Review aids were cleared." if invalidate_review_artifacts else ""
            payload["message"] = f"Prompt recompiled for Asset {asset_id}.{suffix}"
            return payload
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/prompt-review/{asset_id}/approve")
    def prompt_review_approve(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            updated = zet_app.approve_prompt_review(character, phase, asset_id)
            return {
                "message": f"Prompt approved. Asset {updated.asset_id} moved to {updated.pipeline_stage}.",
                "asset": _asset_payload(zet_app, updated),
                "tasks": [
                    _prompt_review_task_payload(zet_app, asset)
                    for asset in zet_app.list_assets(character, phase)
                    if _is_prompt_review_asset(asset)
                ],
            }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/prompt-review/{asset_id}/fail")
    def prompt_review_fail(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            updated = zet_app.fail_prompt_review(character, phase, asset_id)
            return {
                "message": f"Prompt failed. Asset {updated.asset_id} moved to {updated.pipeline_stage}.",
                "asset": _asset_payload(zet_app, updated),
                "tasks": [
                    _prompt_review_task_payload(zet_app, asset)
                    for asset in zet_app.list_assets(character, phase)
                    if _is_prompt_review_asset(asset)
                ],
            }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/render-review/tasks")
    def render_review_tasks(character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            assets = [asset for asset in zet_app.list_assets(character, phase) if _is_render_review_asset(asset)]
            return {"tasks": [_render_review_task_payload(zet_app, asset) for asset in assets]}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/render-review/{asset_id}")
    def render_review_detail(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            return _render_review_context_payload(zet_app, character, phase, asset_id)
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/render-review/{asset_id}/promote-to-locked")
    def render_review_promote_to_locked(
        asset_id: int,
        character: str = Query(...),
        phase: str = Query(...),
        replace_existing: bool = Query(False),
    ) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            asset_ref = zet_app.asset(character, phase, asset_id)
            asset = asset_ref.get()
            locked_image_path = zet_app.path_service.locked_image_path(asset)
            if locked_image_path.exists() and not replace_existing:
                raise HTTPException(
                    status_code=409,
                    detail="A locked image already exists. Confirm replacement before promoting.",
                )
            updated = asset_ref.promote_to_locked()
            return {
                "message": f"Render approved. Asset {updated.asset_id} moved to LOCKED.",
                "asset": _asset_payload(zet_app, updated),
                "tasks": [
                    _render_review_task_payload(zet_app, asset)
                    for asset in zet_app.list_assets(character, phase)
                    if _is_render_review_asset(asset)
                ],
            }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/render-review/{asset_id}/fail-to-render")
    def render_review_fail_to_render(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            updated = zet_app.fail_render_review_to_render(character, phase, asset_id)
            return {
                "message": f"Render rejected. Asset {updated.asset_id} moved back to RENDER.",
                "asset": _asset_payload(zet_app, updated),
                "tasks": [
                    _render_review_task_payload(zet_app, asset)
                    for asset in zet_app.list_assets(character, phase)
                    if _is_render_review_asset(asset)
                ],
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/render-review/{asset_id}/fail-to-regenerate")
    def render_review_fail_to_regenerate(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            updated = zet_app.asset(character, phase, asset_id).regenerate()
            return {
                "message": f"Render rejected. Asset {updated.asset_id} reset to {updated.pipeline_stage}.",
                "asset": _asset_payload(zet_app, updated),
                "tasks": [
                    _render_review_task_payload(zet_app, asset)
                    for asset in zet_app.list_assets(character, phase)
                    if _is_render_review_asset(asset)
                ],
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/render-review/{asset_id}/comment")
    async def render_review_save_comment(asset_id: int, request: Request, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        """Save the render-review comment for an asset."""
        zet_app = _app(app.state.config_path)
        try:
            payload = await request.json()
            comment = zet_app.save_render_review_comment(character, phase, asset_id, str(payload.get("comment") or ""))
            response = _render_review_context_payload(zet_app, character, phase, asset_id)
            response["message"] = "Image review comment saved." if comment else "Image review comment cleared."
            response["assets"] = [_asset_payload(zet_app, asset) for asset in zet_app.list_assets(character, phase)]
            return response
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/turnarounds")
    def turnaround_rows(character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        """List turnaround sheet rows for the selected character phase."""
        zet_app = _app(app.state.config_path)
        try:
            return {"rows": [_turnaround_row_payload(row) for row in zet_app.list_turnaround_rows(character, phase)]}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/turnarounds/{turnaround_id}")
    def turnaround_detail(turnaround_id: str, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        """Return detail for one turnaround sheet row."""
        zet_app = _app(app.state.config_path)
        try:
            return {"row": _turnaround_row_payload(zet_app.turnaround_row(character, phase, turnaround_id))}
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/turnarounds/{turnaround_id}/generate")
    def turnaround_generate(
        turnaround_id: str,
        payload: dict[str, Any] | None = Body(None),
        character: str = Query(...),
        phase: str = Query(...),
    ) -> dict[str, Any]:
        """Generate a candidate turnaround sheet for review."""
        zet_app = _app(app.state.config_path)
        try:
            row = zet_app.generate_turnaround(
                character,
                phase,
                turnaround_id,
                float(payload.get("detection_tolerance")) if isinstance(payload, dict) and payload.get("detection_tolerance") is not None else None,
            )
            return {
                "message": f"Generated turnaround candidate for {row.label}.",
                "row": _turnaround_row_payload(row),
                "rows": [_turnaround_row_payload(item) for item in zet_app.list_turnaround_rows(character, phase)],
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/turnarounds/{turnaround_id}/promote")
    def turnaround_promote(
        turnaround_id: str,
        character: str = Query(...),
        phase: str = Query(...),
        replace_existing: bool = Query(False),
    ) -> dict[str, Any]:
        """Promote a turnaround candidate to the locked reference image."""
        zet_app = _app(app.state.config_path)
        try:
            row = zet_app.promote_turnaround_to_locked(character, phase, turnaround_id, replace_existing)
            return {
                "message": f"Turnaround locked for {row.label}.",
                "row": _turnaround_row_payload(row),
                "rows": [_turnaround_row_payload(item) for item in zet_app.list_turnaround_rows(character, phase)],
            }
        except Exception as exc:
            if "Confirm replacement" in str(exc):
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/turnarounds/{turnaround_id}/partials")
    def turnaround_save_partial(
        turnaround_id: str,
        payload: dict[str, Any] = Body(...),
        character: str = Query(...),
        phase: str = Query(...),
    ) -> dict[str, Any]:
        """Create or update an auxiliary partial turnaround sheet."""
        zet_app = _app(app.state.config_path)
        try:
            row = zet_app.save_partial_turnaround(
                character,
                phase,
                turnaround_id,
                str(payload.get("label") or ""),
                float(payload.get("crop_percent") or 0),
                float(payload.get("detection_tolerance")) if payload.get("detection_tolerance") is not None else None,
            )
            return {
                "message": "Partial turnaround saved.",
                "row": _turnaround_row_payload(row),
                "rows": [_turnaround_row_payload(item) for item in zet_app.list_turnaround_rows(character, phase)],
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/turnarounds/partials/{partial_turnaround_id}")
    def turnaround_update_partial(
        partial_turnaround_id: str,
        payload: dict[str, Any] = Body(...),
        character: str = Query(...),
        phase: str = Query(...),
    ) -> dict[str, Any]:
        """Update and regenerate an existing auxiliary partial turnaround sheet."""
        zet_app = _app(app.state.config_path)
        try:
            row = zet_app.update_partial_turnaround(
                character,
                phase,
                partial_turnaround_id,
                str(payload.get("label") or ""),
                float(payload.get("crop_percent") or 0),
                float(payload.get("detection_tolerance")) if payload.get("detection_tolerance") is not None else None,
            )
            return {
                "message": "Partial turnaround updated.",
                "row": _turnaround_row_payload(row),
                "rows": [_turnaround_row_payload(item) for item in zet_app.list_turnaround_rows(character, phase)],
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/turnarounds/partials/{partial_turnaround_id}")
    def turnaround_delete_partial(partial_turnaround_id: str, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        """Delete an auxiliary partial turnaround sheet."""
        zet_app = _app(app.state.config_path)
        try:
            row = zet_app.delete_partial_turnaround(character, phase, partial_turnaround_id)
            return {
                "message": "Partial turnaround deleted.",
                "row": _turnaround_row_payload(row),
                "rows": [_turnaround_row_payload(item) for item in zet_app.list_turnaround_rows(character, phase)],
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/head-fitment-manifest/tasks")
    def head_fitment_manifest_tasks(character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            assets = [
                asset for asset in zet_app.list_assets(character, phase)
                if _is_head_fitment_manifest_asset(asset)
            ]
            return {"tasks": [_head_fitment_manifest_task_payload(zet_app, asset) for asset in assets]}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/head-fitment-manifest/{asset_id}")
    def head_fitment_manifest_detail(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            return _head_fitment_manifest_context_payload(zet_app, character, phase, asset_id)
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/head-fitment-manifest/{asset_id}/references")
    def head_fitment_manifest_save_references(
        asset_id: int,
        payload: dict[str, Any] = Body(...),
        character: str = Query(...),
        phase: str = Query(...),
    ) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            updated = zet_app.save_head_fitment_references(
                character,
                phase,
                asset_id,
                str(payload.get("body_reference_path") or ""),
                str(payload.get("headshot_path") or ""),
            )
            response = _head_fitment_manifest_context_payload(zet_app, character, phase, updated.asset_id)
            response["message"] = "Head-fitment reference slots saved."
            return response
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/head-fitment-manifest/headshots")
    async def head_fitment_manifest_upload_headshot(
        request: Request,
        filename: str = Query(...),
        character: str = Query(...),
        phase: str = Query(...),
    ) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            path = zet_app.upload_headshot_reference(character, phase, filename, await request.body())
            return {"path": str(path), "name": path.name}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/ai-controls")
    def ai_controls() -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            return _ai_controls_payload(zet_app)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/ai-controls/harvest")
    def ai_controls_harvest() -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            results = zet_app.harvest_ai_answers()
            payload = _ai_controls_payload(zet_app)
            payload["message"] = f"Harvested {len(results)} AI answer folder(s)." if results else "No AI answer folders found."
            payload["harvest_results"] = _jsonable(results)
            return payload
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/ai-controls/archive-harvested")
    def ai_controls_archive_harvested() -> dict[str, Any]:
        """Archive harvested AI answer folders."""
        zet_app = _app(app.state.config_path)
        try:
            result = zet_app.archive_harvested_answers()
            payload = _ai_controls_payload(zet_app)
            payload["message"] = (
                f"Archived {result['moved_count']} harvested answer folder(s); "
                f"skipped {result['skipped_count']} unharvested folder(s)."
            )
            payload["archive_result"] = result
            return payload
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/ai-controls/monitor-test")
    def ai_controls_monitor_test(instruction: str = Query("", max_length=1000)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            request_path = zet_app.issue_monitor_test(instruction)
            payload = _ai_controls_payload(zet_app)
            payload["message"] = f"Monitor test sent: {request_path.name}"
            return payload
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/ai-controls/stop")
    def ai_controls_stop() -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            stop_state = zet_app.activate_proxy_stop()
            payload = _ai_controls_payload(zet_app)
            payload["message"] = f"Proxy stop activated. Cleared {stop_state['cleared_asks']} ask folder(s)."
            return payload
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/ai-controls/resume")
    def ai_controls_resume() -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            zet_app.resume_proxy_stop()
            payload = _ai_controls_payload(zet_app)
            payload["message"] = "Proxy stop cleared. New asks may be processed."
            return payload
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/ai-controls/processes/{process_id}/{action}")
    def ai_controls_process_action(process_id: str, action: str) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            if action == "start":
                zet_app.start_process(process_id)
                message = f"Started {process_id}."
            elif action == "stop":
                count = zet_app.stop_process(process_id)
                message = f"Stopped {count} process(es) for {process_id}."
            elif action == "restart":
                count = zet_app.restart_process(process_id)
                message = f"Restarted {process_id}; stopped {count} old process(es)."
            else:
                raise ValueError(f"Unsupported process action: {action}")
            payload = _ai_controls_payload(zet_app)
            payload["message"] = message
            return payload
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/pipeline-controls")
    def pipeline_controls(character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            return _pipeline_controls_payload(zet_app, character, phase)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/pipeline-controls/automation")
    def pipeline_controls_save_automation(
        payload: dict[str, Any] = Body(...),
        character: str = Query(...),
        phase: str = Query(...),
    ) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            zet_app.save_automation_settings(_automation_settings_from_payload(payload))
            refreshed = _app(app.state.config_path)
            response = _pipeline_controls_payload(refreshed, character, phase)
            response["message"] = "Project automation settings saved."
            return response
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/pipeline-controls/prompt-review")
    def pipeline_controls_prompt_review(
        payload: dict[str, Any] = Body(...),
        character: str = Query(...),
        phase: str = Query(...),
    ) -> dict[str, Any]:
        """Enable or disable PROMPT_REVIEW for one pipeline."""
        zet_app = _app(app.state.config_path)
        try:
            pipeline_name = str(payload.get("pipeline_name") or "").strip()
            enabled = bool(payload.get("enabled"))
            zet_app.set_pipeline_prompt_review_enabled(character, phase, pipeline_name, enabled)
            response = _pipeline_controls_payload(zet_app, character, phase)
            response["message"] = f"PROMPT_REVIEW {'enabled' if enabled else 'disabled'} for {pipeline_name}."
            return response
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/pipeline-controls/batch-render-reset")
    def pipeline_controls_batch_render_reset(
        pipeline_name: str = Query(...),
        include_locked: bool = Query(False),
        character: str = Query(...),
        phase: str = Query(...),
    ) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            results = zet_app.reset_pipeline_assets_to_render(character, phase, pipeline_name, include_locked)
            response = _pipeline_controls_payload(zet_app, character, phase)
            reset_count = sum(1 for result in results if result.status == "RESET")
            skipped_count = sum(1 for result in results if result.status == "SKIPPED")
            error_count = sum(1 for result in results if result.status == "ERROR")
            response["message"] = (
                f"Batch render reset complete for {pipeline_name}: "
                f"{reset_count} reset, {skipped_count} skipped, {error_count} error."
            )
            response["batch_results"] = _jsonable(results)
            return response
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/render-console/tasks")
    def render_console_tasks() -> dict[str, Any]:
        queue = _render_console_queue(app.state.config_path)
        try:
            return {"tasks": [task.to_dict() for task in queue.list_tasks()]}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/render-console/tasks/{ask_id}")
    def render_console_task_detail(ask_id: str) -> dict[str, Any]:
        queue = _render_console_queue(app.state.config_path)
        task = queue.get_task(ask_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Manual render task not found: {ask_id}")
        zet_app = _app(app.state.config_path)
        return {
            "task": task.to_dict(),
            "manifest": _jsonable(task.manifest),
            "prompt": queue.read_prompt(task),
            "gpt_helper_prompt": _gpt_helper_prompt(zet_app, app.state.config_path, task),
        }

    @app.post("/api/render-console/tasks/{ask_id}/gpt-helper-prompt")
    async def render_console_save_gpt_helper_prompt(ask_id: str, request: Request) -> dict[str, Any]:
        """Save the editable GPT helper prompt for a render-console task."""
        queue = _render_console_queue(app.state.config_path)
        task = queue.get_task(ask_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Manual render task not found: {ask_id}")
        try:
            payload = await request.json()
            zet_app = _app(app.state.config_path)
            prompt = _save_gpt_helper_prompt(zet_app, app.state.config_path, task, str(payload.get("text") or ""))
            return {
                "message": f"Saved GPT helper prompt for {prompt.get('pipeline')} / {prompt.get('view')}.",
                "gpt_helper_prompt": prompt,
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/render-console/tasks/{ask_id}/answer-image")
    async def render_console_answer_image(ask_id: str, request: Request, render_comment: str = Query("", max_length=10000)) -> dict[str, Any]:
        queue = _render_console_queue(app.state.config_path)
        task = queue.get_task(ask_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Manual render task not found: {ask_id}")
        image_bytes = await request.body()
        content_type = request.headers.get("content-type", "")
        try:
            answer_path = queue.write_answer_image(task, image_bytes, content_type, render_comment)
            tasks = queue.list_tasks()
            return {
                "status": "SUCCESS",
                "answer_path": str(answer_path),
                "remaining_tasks": [item.to_dict() for item in tasks],
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/render-console/tasks/{ask_id}/fail")
    async def render_console_fail_task(ask_id: str, request: Request) -> dict[str, Any]:
        queue = _render_console_queue(app.state.config_path)
        task = queue.get_task(ask_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Manual render task not found: {ask_id}")
        payload = await request.json()
        reason = str(payload.get("reason") or "")
        try:
            answer_path = queue.write_failed_answer(task, reason)
            tasks = queue.list_tasks()
            return {
                "status": "ERROR",
                "answer_path": str(answer_path),
                "remaining_tasks": [item.to_dict() for item in tasks],
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/assets/{asset_id}/stage-ai-ask")
    def stage_ai_ask(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            ask_path = zet_app.asset(character, phase, asset_id).stage_ai_ask()
            return _action_response(zet_app, character, phase, asset_id, f"AI ask staged at {ask_path}.")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/assets/{asset_id}/run-current-worker")
    def run_current_worker(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            result = zet_app.asset(character, phase, asset_id).run_current_worker_chain()
            message = f"Ran {result.worker_count} worker(s). Finished at {result.asset.pipeline_stage}."
            if result.messages:
                message = f"{message} " + " | ".join(result.messages)
            return _action_response(zet_app, character, phase, result.asset.asset_id, message)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/assets/{asset_id}/run-housekeeping")
    def run_housekeeping(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            path = zet_app.asset(character, phase, asset_id).run_housekeeping()
            return _action_response(zet_app, character, phase, asset_id, f"Housekeeping complete at {path}.")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/assets/{asset_id}/retry-ai")
    def retry_ai(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            updated = zet_app.asset(character, phase, asset_id).retry_ai()
            return _action_response(zet_app, character, phase, updated.asset_id, "AI retry requested.")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/assets/{asset_id}/regenerate")
    def regenerate(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            updated = zet_app.asset(character, phase, asset_id).regenerate()
            return _action_response(zet_app, character, phase, updated.asset_id, f"Asset reset to {updated.pipeline_stage}.")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/assets/{asset_id}/retouch")
    def retouch(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        """Stage a selected asset for manual retouch rendering."""
        zet_app = _app(app.state.config_path)
        try:
            updated = zet_app.asset(character, phase, asset_id).start_retouch_render()
            return _action_response(
                zet_app,
                character,
                phase,
                updated.asset_id,
                "Retouch render staged. Open Render Console to paste the edited image.",
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/assets/{asset_id}/promote-to-locked")
    def promote_to_locked(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            updated = zet_app.asset(character, phase, asset_id).promote_to_locked()
            return _action_response(zet_app, character, phase, updated.asset_id, "Asset promoted to LOCKED.")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


app = create_app()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Zet FastAPI web dashboard.")
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    import uvicorn

    uvicorn.run(create_app(args.config), host=args.host, port=args.port, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
