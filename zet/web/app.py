from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
import markdown
from starlette.background import BackgroundTask

from zet.app import ZetApp
from zet.render_console.queue import RenderConsoleQueue
from zet.services.config_service import ConfigService
from zet.services.auxiliary_resource_service import AUXILIARY_RESOURCE_CATEGORIES
from zet.services.character_phase_discovery_service import CharacterPhaseDiscoveryService
from zet.services.local_render_backend_service import LocalRenderBackendService
from zet.services.local_image_review_service import LocalImageReviewService
from zet.services.manual_render_submission_service import ManualRenderSubmissionService
from zet.services.ollama_model_service import OllamaModelService
from zet.services.pipeline_control_service import AutomationSettings
from zet.services.prompt_evolution_service import PromptEvolutionError
from zet.services.source_editor_service import SourceEditorService
from zet.web.pipeline_controls_router import create_pipeline_controls_router
from zet.web.pipeline_inspection_router import create_pipeline_inspection_router
PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parents[1]

from zet.services.prompt_review_service import LocalRenderUnavailable


def _app(config_path: str | Path) -> ZetApp:
    return ZetApp.from_config(config_path)


def _render_console_queue(config_path: str | Path) -> RenderConsoleQueue:
    return RenderConsoleQueue(ConfigService.load(config_path))


def _read_json_file(path: Path) -> dict[str, Any]:
    """Read a JSON object file, returning an empty object on failure."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return data


def _render_console_asset_for_task(zet_app: ZetApp, task):
    """Look up the asset associated with a render-console task."""
    if task.asset_id is None:
        return None
    try:
        return zet_app.asset(task.character, task.phase, int(task.asset_id)).get()
    except Exception:
        return None


def _render_console_reference_files(zet_app: ZetApp, task) -> list[dict]:
    """Return the current asset references for a render task when available."""
    asset = _render_console_asset_for_task(zet_app, task)
    if asset is not None and asset.reference_files:
        return asset.reference_files
    return task.manifest.get("reference_files") or []


def _format_value(value: Any) -> str:
    return "None" if value is None else str(value)


def _format_timestamp_with_age(value: Any) -> str:
    return _format_value(value)


def _review_image_ready(zet_app: ZetApp, asset) -> bool:
    if asset.pipeline_stage == "RENDER_REVIEW":
        try:
            return zet_app.path_service.candidate_image_path(asset).exists()
        except Exception:
            return False
    return False


def _is_render_review_asset(asset) -> bool:
    return asset.pipeline_stage == "RENDER_REVIEW" and asset.actor == "HUMAN_AGENT"


def _is_head_image_manifest_asset(asset) -> bool:
    return asset.pipeline == "Head-Image" and asset.pipeline_stage == "MANIFEST" and asset.actor == "PYTHON"


def _is_character_assembly_manifest_asset(asset) -> bool:
    return asset.pipeline == "Character-Assembly" and asset.pipeline_stage == "MANIFEST" and asset.actor == "PYTHON"


def _header_preview_payload(zet_app: ZetApp, character: str, phase: str) -> dict[str, Any] | None:
    """Return the locked front-left three-quarter Head-Image preview for a character phase."""
    try:
        assets = zet_app.list_assets(character, phase)
    except Exception:
        return None
    for asset in assets:
        if asset.pipeline != "Head-Image":
            continue
        if str(asset.body_view) != "Front-Left-3-4" or str(asset.head_view) != "Front-Left-3-4":
            continue
        if asset.asset_state != "LOCKED":
            continue
        locked_path = zet_app.path_service.locked_image_path(asset)
        if locked_path.exists():
            return {
                "asset_id": asset.asset_id,
                "image_path": str(locked_path),
                "updated_at": asset.updated_at,
            }
    return None


def _asset_payload(zet_app: ZetApp, asset) -> dict[str, Any]:
    """Serialize an asset for dashboard tables and detail panels."""
    data = asdict(asset)
    data["costume_or_expression"] = asset.expression if asset.expression else asset.costume
    character_template = zet_app.path_service.character_template_path(asset.character, asset.phase)
    data["character_template_source"] = {
        "source_kind": "character_image_template",
        "source_label": "Character Image Template",
        "source_path": str(character_template),
        "editable": True,
    }
    governing_source = data["character_template_source"]
    if asset.pipeline == "Costume-Dressing":
        costume_path = zet_app.path_service.resolve_path(asset.costume_path) if asset.costume_path else zet_app.path_service.costume_template_path(
            asset.character,
            asset.phase,
            asset.costume or "Costume",
        )
        governing_source = {
            "source_kind": "costume_template",
            "source_label": asset.costume or "Costume Template",
            "source_path": str(costume_path),
            "editable": True,
        }
    elif asset.pipeline == "Expression" and asset.expression_definition_path:
        governing_source = {
            "source_kind": "expression_definition",
            "source_label": asset.expression or "Expression Definition",
            "source_path": str(zet_app.path_service.resolve_path(asset.expression_definition_path)),
            "editable": True,
        }
    data["governing_template_source"] = governing_source
    data["head_view"] = _format_value(asset.head_view)
    data["costume"] = _format_value(asset.costume)
    data["expression"] = _format_value(asset.expression)
    data["ai_state"] = _format_value(asset.ai_state)
    data["final_image_output"] = _format_value(asset.final_image_output)
    if asset.costume_path:
        data["costume_path"] = str(zet_app.path_service.resolve_path(asset.costume_path))
    if asset.expression_definition_path:
        data["expression_definition_path"] = str(zet_app.path_service.resolve_path(asset.expression_definition_path))
    data["updated_at_display"] = _format_timestamp_with_age(asset.updated_at)
    render_comment = zet_app.render_review_comment(asset.character, asset.phase, asset.asset_id)
    data["render_review_comment"] = render_comment
    data["has_render_review_comment"] = bool(render_comment)
    data["review_image_ready"] = _review_image_ready(zet_app, asset)
    ai_proxy_status = {"pending": False, "count": 0, "jobs": []}
    data["ai_proxy_status"] = ai_proxy_status
    data["actor_display"] = f"{asset.actor} → AI PROXY" if ai_proxy_status["pending"] else asset.actor
    try:
        locked_image_path = zet_app.path_service.locked_image_path(asset)
        data["locked_image_path"] = str(locked_image_path)
        data["locked_image_exists"] = locked_image_path.exists()
    except Exception:
        data["locked_image_path"] = None
        data["locked_image_exists"] = False
    if asset.pipeline_stage == "ADD_REF" and asset.error_code:
        data["pipeline_stage_display"] = f"ADD_REF ({asset.error_code})"
    elif data["review_image_ready"]:
        data["pipeline_stage_display"] = f"CAMERA {asset.pipeline_stage}"
    else:
        data["pipeline_stage_display"] = asset.pipeline_stage
    if ai_proxy_status["pending"]:
        data["pipeline_stage_display"] += " (AI PROXY PENDING)"
    return data


def _identity_key_payload(zet_app: ZetApp, identity_key) -> dict[str, Any]:
    """Serialize an identity key for dashboard views."""
    data = asdict(identity_key)
    for key in ("image_path", "source_image_path", "analysis_path"):
        if data.get(key):
            data[key] = str(zet_app.path_service.resolve_path(data[key]))
    return data


def _identity_key_preview_payload(preview) -> dict[str, Any]:
    """Serialize an identity key preview crop."""
    return asdict(preview)


def _costume_payload(zet_app: ZetApp, character: str, phase: str, costume) -> dict[str, Any]:
    """Serialize a costume template for dashboard views."""
    data = asdict(costume)
    locked_preview = None
    try:
        for row in zet_app.list_turnaround_rows(character, phase):
            if row.source_pipeline == "Costume-Dressing" and row.costume == costume.name and row.locked_image_exists:
                locked_preview = row
                break
    except Exception:
        locked_preview = None
    data["locked_preview_path"] = locked_preview.locked_image_path if locked_preview else None
    data["locked_preview_exists"] = bool(locked_preview)
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


def _story_record_payload(record) -> dict[str, Any]:
    """Serialize one story record for dashboard views."""
    return asdict(record)


def _story_document_payload(document) -> dict[str, Any]:
    """Serialize one story document for dashboard editing."""
    return {
        "story": _story_record_payload(document.record),
        "text": document.text,
        "validation_errors": list(document.validation_errors),
    }


def _scene_record_payload(record) -> dict[str, Any]:
    """Serialize one scene record for dashboard views."""
    return asdict(record)


def _scene_document_payload(zet_app: ZetApp, document) -> dict[str, Any]:
    """Serialize one scene document for dashboard editing."""
    review = zet_app.scene_image_review_status(document.story.slug, document.record.slug)
    return {
        "story": _story_record_payload(document.story),
        "scene": _scene_record_payload(document.record),
        "text": document.text,
        "validation_errors": list(document.validation_errors),
        "image_path": review.locked_image_path,
        "image_exists": review.locked_exists,
        "candidate_pending": review.candidate_exists,
        "image_review_key": review.review_key,
    }


def _scene_builder_document_payload(zet_app: ZetApp, document) -> dict[str, Any]:
    """Serialize one Scene Builder document for dashboard editing."""
    review = zet_app.scene_image_review_status(document.story.slug, document.scene.slug)
    return {
        "story": _story_record_payload(document.story),
        "scene": _scene_record_payload(document.scene),
        "data": _jsonable(document.data),
        "json_path": document.json_path,
        "md_path": document.md_path,
        "png_path": document.png_path,
        "json_exists": document.json_exists,
        "png_exists": document.png_exists,
        "candidate_pending": review.candidate_exists,
        "image_review_key": review.review_key,
        "validation_warnings": list(document.validation_warnings),
        "blocked": document.blocked,
        "error": document.error,
    }


def _image_reference_payload(row) -> dict[str, Any]:
    """Serialize one copyable scene image reference row."""
    return asdict(row)


def _zine_record_payload(record) -> dict[str, Any]:
    """Serialize one saved zine."""
    return asdict(record)


def _zine_document_payload(document) -> dict[str, Any]:
    """Serialize one saved zine and its metadata."""
    return {
        "zine": _zine_record_payload(document.record),
        "metadata": _jsonable(document.metadata),
    }


def _story_render_task_payload(task) -> dict[str, Any]:
    """Serialize one staged story render task."""
    return {
        "story_slug": task.story_slug,
        "scene_slug": task.scene_slug,
        "ask_id": task.ask_id,
        "ask_path": task.ask_path,
        "pipeline_path": task.pipeline_path,
        "final_prompt_path": task.final_prompt_path,
        "expected_output": task.expected_output,
        "reference_files": _jsonable(task.reference_files),
    }


def _story_git_payload(result) -> dict[str, Any]:
    """Serialize one story git operation result."""
    return {
        "output": result.output,
        "has_story_changes": result.has_story_changes,
        "conflict": result.conflict,
    }


def _onboarding_status_payload(status) -> dict[str, Any]:
    """Serialize a character onboarding status for dashboard views."""
    return asdict(status)


def _onboarding_options_payload(options) -> dict[str, Any]:
    """Serialize character onboarding dropdown options."""
    return asdict(options)


def _render_console_local_prompt_payload(zet_app: ZetApp, task) -> dict[str, Any]:
    if task.asset_id is not None:
        try:
            context = zet_app.prompt_review_service.get_context(task.character, task.phase, task.asset_id)
        except Exception:
            context = None
        if context is not None:
            return {
                "supports_local_test_render": bool(context.condense_status.get("enabled")),
                "condensed_prompt_text": context.condensed_prompt_text or "",
                "latest_local_test_render": str(context.latest_local_test_render) if context.latest_local_test_render else None,
                "local_api_call_exists": _render_console_local_api_call_path(context.condensed_prompt_path.parent).exists()
                if context.condensed_prompt_path
                else False,
                "local_render_status": _render_console_local_render_status(zet_app, task),
                "condense_status": _jsonable(context.condense_status),
            }

    workspace = _render_console_task_workspace(task)
    prompt_path = workspace / "Final_Image_Prompt.md"
    local_prompt_path = _render_console_scene_local_prompt_path(workspace)
    condensed_path = workspace / "Condensed_Image_Prompt.md"
    latest_render = _latest_render_console_local_test_render(workspace)
    enabled = local_prompt_path.exists()
    condensed_current = condensed_path.exists() and prompt_path.exists() and condensed_path.stat().st_mtime >= prompt_path.stat().st_mtime
    return {
        "supports_local_test_render": enabled,
        "condensed_prompt_text": local_prompt_path.read_text(encoding="utf-8") if local_prompt_path.exists() else "",
        "latest_local_test_render": str(latest_render) if latest_render else None,
        "local_api_call_exists": _render_console_local_api_call_path(workspace).exists(),
        "local_render_status": _render_console_local_render_status(zet_app, task),
        "condense_status": {
            "enabled": enabled,
            "state": "READY" if enabled else "DISABLED",
            "condensed_exists": local_prompt_path.exists(),
            "condensed_current": condensed_current,
            "condensed_prompt_path": str(local_prompt_path) if local_prompt_path.exists() else None,
        },
    }


def _render_console_detail_payload(zet_app: ZetApp, queue: RenderConsoleQueue, task) -> dict[str, Any]:
    """Return render-task prompt review data for assets and story scenes."""
    prompt = queue.read_prompt(task)
    source_map_path = None
    source_map: dict[str, Any] = {}
    if task.asset_id is not None:
        try:
            context = zet_app.prompt_review_service.get_context(task.character, task.phase, task.asset_id)
            source_map_path = context.source_map_path
            source_map = context.source_map
        except Exception:
            pass
    manifest = task.manifest
    prompt_analysis: dict[str, Any] = {}
    story_slug = str(manifest.get("story_slug") or "")
    scene_slug = str(manifest.get("scene_slug") or "")
    if story_slug and scene_slug:
        try:
            pipeline_value = str(manifest.get("pipeline_path") or "")
            if pipeline_value:
                pipeline_path = Path(pipeline_value)
                source_map_path = pipeline_path / "Prompt_Source_Map.json"
                source_map = zet_app.story_service.scene_prompt_source_map(pipeline_path, prompt)
            prompt_analysis = zet_app.scene_prompt_analysis_status(story_slug, scene_slug)
        except Exception:
            pass
    return {
        "task": task.to_dict(),
        "manifest": _jsonable(manifest),
        "reference_files": _jsonable(_render_console_reference_files(zet_app, task)),
        "prompt_path": str(task.ask_path / task.prompt_file),
        "prompt": prompt,
        "source_map_path": str(source_map_path) if source_map_path else None,
        "source_map": _jsonable(source_map),
        "prompt_analysis": _jsonable(prompt_analysis),
        "local_prompt": _render_console_local_prompt_payload(zet_app, task),
    }


def _local_image_review_payload(zet_app: ZetApp, task) -> dict[str, Any]:
    service = LocalImageReviewService(zet_app)
    local_prompt = _render_console_local_prompt_payload(zet_app, task)
    return {
        "task": task.to_dict(),
        "manifest": _jsonable(task.manifest),
        "workspace": str(service.workspace(task)),
        "images": service.list_images(task),
        "supports_local_test_render": bool(local_prompt.get("supports_local_test_render")),
        "local_render_status": local_prompt.get("local_render_status") or {"state": ""},
    }


def _render_console_local_render_status(zet_app: ZetApp, task) -> dict[str, Any]:
    source_ask_id = task.manifest.get("ask_id")
    items = []
    for state, entries in zet_app.queue_snapshot().items():
        for entry in entries:
            if entry.get("task_type") == "local_test_render" and entry.get("source_ask_id") == source_ask_id:
                item = dict(entry)
                item["state"] = state.upper()
                items.append(item)
    return {"state": items[0]["state"], "latest_queue_item": items[0], "queue_items": items} if items else {"state": ""}


def _render_console_task_workspace(task) -> Path:
    pipeline_path = str(task.manifest.get("pipeline_path") or "").strip()
    if pipeline_path:
        return Path(pipeline_path)
    return task.ask_path


def _render_console_scene_local_prompt_path(workspace: Path) -> Path:
    forge_path = workspace / "Local_Render_Forge_Couple_Prompt.md"
    if forge_path.exists():
        return forge_path
    return workspace / "Local_Render_Prompt.md"


def _latest_render_console_local_test_render(workspace: Path) -> Path | None:
    render_dir = workspace / "Local_Test_Renders"
    if not render_dir.exists():
        return None
    images = sorted(render_dir.glob("test_*.png"), key=lambda path: path.stat().st_mtime, reverse=True)
    return images[0] if images else None


def _render_console_local_api_call_path(workspace: Path) -> Path:
    comfyui_path = workspace / "ComfyUI_Workflow_API.json"
    if comfyui_path.exists():
        return comfyui_path
    return workspace / "Local_Test_Renders" / "Stable_Matrix_API_Call.json"


def _render_review_task_payload(zet_app: ZetApp, asset) -> dict[str, Any]:
    payload = _asset_payload(zet_app, asset)
    payload["review_kind"] = "asset"
    payload["review_key"] = f"asset:{asset.character}:{asset.phase}:{asset.asset_id}"
    payload["title"] = f"{asset.pipeline} #{asset.asset_id}"
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
        "review_kind": "asset",
        "review_key": f"asset:{character}:{phase}:{asset_id}",
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


def _scene_render_review_task_payload(status) -> dict[str, Any]:
    return asdict(status)


def _scene_render_review_context_payload(zet_app: ZetApp, story_slug: str, scene_slug: str) -> dict[str, Any]:
    status = zet_app.scene_image_review_status(story_slug, scene_slug)
    return {
        **asdict(status),
        "is_reviewable": status.candidate_exists,
        "render_review_comment": status.comment,
        "stage_text": "",
        "history_text": "",
    }


def _head_image_manifest_context_payload(zet_app: ZetApp, character: str, phase: str, asset_id: int) -> dict[str, Any]:
    context = zet_app.head_image_reference_context(character, phase, asset_id)
    return {
        "asset": _asset_payload(zet_app, context["asset"]),
        "is_manifest_editable": context["is_manifest_editable"],
        "source_options": _jsonable(context["source_options"]),
        "selected_source": _jsonable(context["selected_source"]),
        "reference_files": _jsonable(context["reference_files"]),
    }


def _character_assembly_manifest_context_payload(zet_app: ZetApp, character: str, phase: str, asset_id: int) -> dict[str, Any]:
    context = zet_app.character_assembly_reference_context(character, phase, asset_id)
    return {
        "asset": _asset_payload(zet_app, context["asset"]),
        "is_manifest_editable": context["is_manifest_editable"],
        "body_reference_options": _jsonable(context["body_reference_options"]),
        "head_image_options": _jsonable(context["head_image_options"]),
        "selected_body_reference": _jsonable(context["selected_body_reference"]),
        "selected_head_image": _jsonable(context["selected_head_image"]),
        "reference_files": _jsonable(context["reference_files"]),
    }


def _ai_controls_payload(zet_app: ZetApp) -> dict[str, Any]:
    queue_snapshot = zet_app.queue_snapshot()
    manual_render_asks = [
        item for item in queue_snapshot["ask"]
        if item.get("worker_type") == "manual_chatgpt_render"
    ]
    return {
        "harvested_answer_count": zet_app.harvested_answer_count(),
        "queue": _jsonable(queue_snapshot),
        "queue_counts": {key: len(value) for key, value in queue_snapshot.items()},
        "manual_render_asks": _jsonable(manual_render_asks),
        "processes": [status.to_dict() for status in zet_app.process_statuses()],
    }


def _automation_settings_from_payload(payload: dict[str, Any], defaults: AutomationSettings | None = None) -> AutomationSettings:
    """Build automation settings, preserving current values for omitted fields."""
    defaults = defaults or AutomationSettings(
        local_render_preset="body-reference-preview",
        local_render_positive_prompt_globals="",
        local_render_negative_prompt_globals="",
        local_render_use_forge_couple=True,
        local_render_checkpoint="",
        ai_harvest_auto_enabled=False,
        ai_harvest_interval_seconds=0,
        render_backend="",
    )
    stable_profile = str(
        payload.get("stable_matrix_profile", payload.get("local_render_preset", defaults.stable_matrix_profile or defaults.local_render_preset))
    )
    stable_positive = str(
        payload.get(
            "stable_matrix_positive_prompt_globals",
            payload.get(
                "local_render_positive_prompt_globals",
                defaults.stable_matrix_positive_prompt_globals or defaults.local_render_positive_prompt_globals,
            ),
        )
    )
    stable_negative = str(
        payload.get(
            "stable_matrix_negative_prompt_globals",
            payload.get(
                "local_render_negative_prompt_globals",
                defaults.stable_matrix_negative_prompt_globals or defaults.local_render_negative_prompt_globals,
            ),
        )
    )
    stable_forge = bool(
        payload.get(
            "stable_matrix_use_forge_couple",
            payload.get(
                "local_render_use_forge_couple",
                defaults.stable_matrix_use_forge_couple
                if defaults.stable_matrix_use_forge_couple is not None
                else defaults.local_render_use_forge_couple,
            ),
        )
    )
    stable_checkpoint = str(
        payload.get(
            "stable_matrix_checkpoint",
            payload.get("local_render_checkpoint", defaults.stable_matrix_checkpoint or defaults.local_render_checkpoint),
        )
    )
    return AutomationSettings(
        local_render_preset=stable_profile,
        local_render_positive_prompt_globals=stable_positive,
        local_render_negative_prompt_globals=stable_negative,
        local_render_use_forge_couple=stable_forge,
        local_render_checkpoint=stable_checkpoint,
        ai_harvest_auto_enabled=bool(payload.get("ai_harvest_auto_enabled", defaults.ai_harvest_auto_enabled)),
        ai_harvest_interval_seconds=int(payload.get("ai_harvest_interval_seconds", defaults.ai_harvest_interval_seconds)),
        render_backend=str(payload.get("render_backend", defaults.render_backend)),
        local_render_backend=str(payload.get("local_render_backend", defaults.local_render_backend)),
        stable_matrix_profile=stable_profile,
        stable_matrix_positive_prompt_globals=stable_positive,
        stable_matrix_negative_prompt_globals=stable_negative,
        stable_matrix_use_forge_couple=stable_forge,
        stable_matrix_checkpoint=stable_checkpoint,
        comfyui_profile=str(payload.get("comfyui_profile", defaults.comfyui_profile)),
        comfyui_server_url=str(payload.get("comfyui_server_url", defaults.comfyui_server_url)),
        comfyui_checkpoint=str(payload.get("comfyui_checkpoint", defaults.comfyui_checkpoint)),
        comfyui_positive_prompt_globals=str(
            payload.get("comfyui_positive_prompt_globals", defaults.comfyui_positive_prompt_globals)
        ),
        comfyui_negative_prompt_globals=str(
            payload.get("comfyui_negative_prompt_globals", defaults.comfyui_negative_prompt_globals)
        ),
        comfyui_poll_seconds=float(payload.get("comfyui_poll_seconds", defaults.comfyui_poll_seconds)),
        comfyui_timeout_seconds=float(payload.get("comfyui_timeout_seconds", defaults.comfyui_timeout_seconds)),
        ai_prompt_analysis_model=str(payload.get("ai_prompt_analysis_model", defaults.ai_prompt_analysis_model)),
        ai_prompt_analysis_instructions_file=str(
            payload.get("ai_prompt_analysis_instructions_file", defaults.ai_prompt_analysis_instructions_file)
        ),
        zine_print_scale=float(payload.get("zine_print_scale", defaults.zine_print_scale)),
        zine_page_margin=int(payload.get("zine_page_margin", defaults.zine_page_margin)),
        zine_width=int(payload.get("zine_width", defaults.zine_width)),
        turnaround_width=int(payload.get("turnaround_width", defaults.turnaround_width)),
    )


def _pipeline_controls_payload(zet_app: ZetApp, character: str, phase: str) -> dict[str, Any]:
    snapshot = zet_app.pipeline_control_snapshot(character, phase)
    pipeline_names = sorted({row.pipeline for row in snapshot.pipeline_rows})
    return {
        "config_path": str(snapshot.config_path),
        "pipelines_path": str(snapshot.pipelines_path),
        "automation": _jsonable(snapshot.automation),
        "render_profiles": snapshot.render_profiles,
        "pipeline_rows": _jsonable(snapshot.pipeline_rows),
        "project_config_rows": _jsonable(snapshot.project_config_rows),
        "pipeline_names": pipeline_names,
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
    app.state.zet_app = ZetApp.from_config(config_path)

    def _app(_config_path: str | Path) -> ZetApp:
        return app.state.zet_app

    def _reload_app() -> ZetApp:
        app.state.zet_app = ZetApp.from_config(app.state.config_path)
        return app.state.zet_app

    app.include_router(
        create_pipeline_controls_router(
            lambda: _app(app.state.config_path),
            _reload_app,
            _pipeline_controls_payload,
            _automation_settings_from_payload,
            _jsonable,
        )
    )
    app.include_router(create_pipeline_inspection_router(lambda: _app(app.state.config_path)))

    app.mount("/static", StaticFiles(directory=PACKAGE_ROOT / "static"), name="zet_web_static")
    app.mount("/img", StaticFiles(directory=PROJECT_ROOT / "img"), name="zet_img")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (PACKAGE_ROOT / "templates" / "index.html").read_text(encoding="utf-8")

    @app.get("/api/context")
    def context() -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        discovery = CharacterPhaseDiscoveryService(zet_app.config.base_character_path)
        characters = discovery.list_characters()
        phases_by_character = {
            character: discovery.list_phases(character)
            for character in characters
        }
        onboarding_statuses = {
            character: {
                phase: _onboarding_status_payload(zet_app.character_onboarding_status(character, phase))
                for phase in phases_by_character.get(character, [])
            }
            for character in characters
        }
        header_previews = {
            character: {
                phase: _header_preview_payload(zet_app, character, phase)
                for phase in phases_by_character.get(character, [])
            }
            for character in characters
        }
        return {
            "characters": characters,
            "phases_by_character": phases_by_character,
            "onboarding_statuses": onboarding_statuses,
            "header_previews": header_previews,
            "onboarding_options": _onboarding_options_payload(zet_app.character_onboarding_options()),
            "auxiliary_resource_categories": AUXILIARY_RESOURCE_CATEGORIES,
            "default_character": characters[0] if characters else None,
            "default_phase": phases_by_character.get(characters[0], [None])[0] if characters else None,
        }

    @app.get("/api/todo")
    def todo() -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            return {"text": zet_app.todo_text()}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/workspace-summary")
    def workspace_summary(
        character: str = Query(""),
        phase: str = Query(""),
        story_slug: str = Query(""),
    ) -> dict[str, Any]:
        """Return overview data for the active dashboard workspaces."""
        zet_app = _app(app.state.config_path)
        try:
            return {
                "character": asdict(zet_app.character_workspace_summary(character, phase))
                if character and phase
                else None,
                "story": asdict(zet_app.story_workspace_summary(story_slug)),
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/todo")
    def save_todo(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            zet_app.save_todo_text(str(payload.get("text") or ""))
            return {"message": "To Do saved."}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

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
                "message": "Draft Character.md saved.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/onboarding/template")
    async def onboarding_template_upload(
        request: Request,
        character: str = Query(...),
        phase: str = Query(...),
        create_only: bool = Query(False),
    ) -> dict[str, Any]:
        """Upload, validate, and initialize a character image template."""
        zet_app = _app(app.state.config_path)
        try:
            contents = (await request.body()).decode("utf-8")
            status = zet_app.upload_character_template(character, phase, contents, create_only=create_only)
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

    @app.post("/api/assets/advance-all")
    def advance_all_assets(
        payload: dict[str, Any] = Body(...),
        character: str = Query(...),
        phase: str = Query(...),
    ) -> dict[str, Any]:
        """Advance the requested non-locked assets through their current worker stage."""
        zet_app = _app(app.state.config_path)
        try:
            asset_ids = [int(value) for value in payload.get("asset_ids", [])]
            results = zet_app.advance_assets(character, phase, asset_ids)
            advanced = len([item for item in results if item.get("status") == "ADVANCED"])
            waiting = len([item for item in results if item.get("status") == "WAITING"])
            errors = len([item for item in results if item.get("status") == "ERROR"])
            skipped = len([item for item in results if item.get("status") == "SKIPPED"])
            return {
                "results": results,
                "assets": [_asset_payload(zet_app, asset) for asset in zet_app.list_assets(character, phase)],
                "message": f"Advanced {advanced} asset(s); waiting for action {waiting}; skipped {skipped}; errors {errors}.",
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
        category: str = Query(...),
        label: str = Query(...),
    ) -> dict[str, Any]:
        """Create a global auxiliary resource folder."""
        zet_app = _app(app.state.config_path)
        try:
            resource = zet_app.create_auxiliary_resource(
                category,
                label,
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
        category: str = Query(...),
        label: str = Query(...),
    ) -> dict[str, Any]:
        """Update a global auxiliary resource folder metadata."""
        zet_app = _app(app.state.config_path)
        try:
            resource = zet_app.update_auxiliary_resource(
                resource_id,
                label,
            )
            return {
                "resource": _auxiliary_resource_payload(resource),
                "resources": [_auxiliary_resource_payload(item) for item in zet_app.list_auxiliary_resources(category)],
                "message": f"Updated auxiliary resource {resource.label}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/auxiliary-resources/{resource_id}")
    def auxiliary_resource_delete(
        resource_id: str,
        category: str = Query(...),
    ) -> dict[str, Any]:
        """Delete a global auxiliary resource folder and its contents."""
        zet_app = _app(app.state.config_path)
        try:
            resource = zet_app.delete_auxiliary_resource(resource_id)
            return {
                "resources": [_auxiliary_resource_payload(item) for item in zet_app.list_auxiliary_resources(category)],
                "message": f"Deleted auxiliary resource {resource.label}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/stories")
    def stories() -> dict[str, Any]:
        """List all stories in the shared stories library."""
        zet_app = _app(app.state.config_path)
        try:
            return {
                "stories": [_story_record_payload(item) for item in zet_app.list_stories()],
                "has_story_changes": zet_app.story_git_has_changes(),
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/git/status")
    def story_git_status() -> dict[str, Any]:
        """Fetch and return story git status."""
        zet_app = _app(app.state.config_path)
        try:
            return _story_git_payload(zet_app.story_git_status())
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/git/pull")
    def story_git_pull() -> dict[str, Any]:
        """Pull story library changes."""
        zet_app = _app(app.state.config_path)
        try:
            return _story_git_payload(zet_app.story_git_pull())
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/git/commit")
    def story_git_commit() -> dict[str, Any]:
        """Commit and push story changes."""
        zet_app = _app(app.state.config_path)
        try:
            return _story_git_payload(zet_app.story_git_commit())
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories")
    def story_create(title: str = Query(...)) -> dict[str, Any]:
        """Create a new story markdown file from the shared template."""
        zet_app = _app(app.state.config_path)
        try:
            document = zet_app.create_story(title)
            return {
                "stories": [_story_record_payload(item) for item in zet_app.list_stories()],
                "document": _story_document_payload(document),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": f"Created story {document.record.title}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/stories/order")
    def story_reorder(data: dict = Body(...)) -> dict[str, Any]:
        """Persist the complete story display order."""
        zet_app = _app(app.state.config_path)
        try:
            stories = zet_app.reorder_stories(data.get("slugs"))
            return {
                "stories": [_story_record_payload(item) for item in stories],
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": "Story order saved.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/stories/{story_slug}")
    def story_detail(story_slug: str) -> dict[str, Any]:
        """Load one story markdown document."""
        zet_app = _app(app.state.config_path)
        try:
            return {"document": _story_document_payload(zet_app.load_story(story_slug))}
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.put("/api/stories/{story_slug}")
    async def story_save(story_slug: str, request: Request) -> dict[str, Any]:
        """Save one story markdown document."""
        zet_app = _app(app.state.config_path)
        try:
            text = (await request.body()).decode("utf-8")
            document = zet_app.save_story(story_slug, text)
            return {
                "stories": [_story_record_payload(item) for item in zet_app.list_stories()],
                "document": _story_document_payload(document),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": f"Saved story {document.record.title}.",
            }
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail="Story markdown must be UTF-8.") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.patch("/api/stories/{story_slug}")
    def story_rename(story_slug: str, data: dict = Body(...)) -> dict[str, Any]:
        """Rename one story while preserving its slug."""
        zet_app = _app(app.state.config_path)
        try:
            document = zet_app.rename_story(story_slug, data.get("title"))
            return {
                "stories": [_story_record_payload(item) for item in zet_app.list_stories()],
                "document": _story_document_payload(document),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": f"Renamed story to {document.record.title}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/auxiliary-resources/{resource_id}/images")
    async def auxiliary_resource_image_save(
        resource_id: str,
        request: Request,
        category: str = Query(...),
        image_label: str = Query(...),
        original_image_id: str = Query(""),
    ) -> dict[str, Any]:
        """Save or update one auxiliary resource image."""
        zet_app = _app(app.state.config_path)
        try:
            resource = zet_app.save_auxiliary_resource_image(
                resource_id,
                image_label,
                await request.body(),
                request.headers.get("content-type", ""),
                original_image_id,
            )
            return {
                "resource": _auxiliary_resource_payload(resource),
                "resources": [_auxiliary_resource_payload(item) for item in zet_app.list_auxiliary_resources(category)],
                "message": f"Saved auxiliary image {image_label}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/stories/{story_slug}")
    def story_delete(story_slug: str) -> dict[str, Any]:
        """Commit and delete one story folder."""
        zet_app = _app(app.state.config_path)
        try:
            result = zet_app.delete_story(story_slug)
            return {
                "stories": [_story_record_payload(item) for item in zet_app.list_stories()],
                "git": _story_git_payload(result),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": f"Deleted story {story_slug}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/stories/{story_slug}/scenes")
    def story_scenes(story_slug: str) -> dict[str, Any]:
        """List scenes for one story folder."""
        zet_app = _app(app.state.config_path)
        try:
            return {"scenes": [_scene_record_payload(item) for item in zet_app.list_scenes(story_slug)]}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/zines")
    def zine_list() -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            return {"zines": [_zine_record_payload(item) for item in zet_app.list_zines()]}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/zines")
    def zine_create(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            document = zet_app.create_zine(payload)
            return {
                "document": _zine_document_payload(document),
                "zines": [_zine_record_payload(item) for item in zet_app.list_zines()],
                "message": f"Created zine {document.record.name}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/zines/story-scenes/{story_slug}")
    def zine_story_scenes(story_slug: str) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            return {"scenes": [asdict(item) for item in zet_app.zine_story_scene_sources(story_slug)]}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/zines/{slug}")
    def zine_detail(slug: str) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            return {"document": _zine_document_payload(zet_app.load_zine(slug))}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/zines/{slug}")
    def zine_update(slug: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            document = zet_app.update_zine(slug, payload)
            return {
                "document": _zine_document_payload(document),
                "zines": [_zine_record_payload(item) for item in zet_app.list_zines()],
                "message": f"Saved zine {document.record.name}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/zines/{slug}/regenerate")
    def zine_regenerate(slug: str) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            document = zet_app.regenerate_zine(slug)
            return {
                "document": _zine_document_payload(document),
                "message": f"Regenerated zine {document.record.name}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/zines/{slug}")
    def zine_delete(slug: str) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            zet_app.delete_zine(slug)
            return {
                "zines": [_zine_record_payload(item) for item in zet_app.list_zines()],
                "message": f"Deleted zine {slug}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/stories/{story_slug}/settings")
    def story_settings_detail(story_slug: str) -> dict[str, Any]:
        """Load one story settings JSON document."""
        zet_app = _app(app.state.config_path)
        try:
            return {"data": _jsonable(zet_app.load_story_settings(story_slug))}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/stories/{story_slug}/settings")
    def story_settings_save(story_slug: str, data: dict = Body(...)) -> dict[str, Any]:
        """Save one story settings JSON document."""
        zet_app = _app(app.state.config_path)
        try:
            return {
                "data": _jsonable(zet_app.save_story_settings(story_slug, data)),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": "Saved story settings.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/{story_slug}/scenes")
    def scene_create(story_slug: str, scene_name: str = Query(...)) -> dict[str, Any]:
        """Create a new scene markdown file for one story."""
        zet_app = _app(app.state.config_path)
        try:
            document = zet_app.create_scene(story_slug, scene_name)
            return {
                "scenes": [_scene_record_payload(item) for item in zet_app.list_scenes(story_slug)],
                "document": _scene_document_payload(zet_app, document),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": f"Created scene {document.record.title}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/stories/{story_slug}/scenes/{scene_slug}")
    def scene_detail(story_slug: str, scene_slug: str) -> dict[str, Any]:
        """Load one story scene markdown document."""
        zet_app = _app(app.state.config_path)
        try:
            return {"document": _scene_document_payload(zet_app, zet_app.load_scene(story_slug, scene_slug))}
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.get("/api/stories/{story_slug}/scenes/{scene_slug}/builder")
    def scene_builder_detail(story_slug: str, scene_slug: str) -> dict[str, Any]:
        """Load Scene Builder JSON for one story scene."""
        zet_app = _app(app.state.config_path)
        try:
            return {
                "document": _scene_builder_document_payload(zet_app, zet_app.load_scene_builder(story_slug, scene_slug)),
                "options": zet_app.scene_builder_options(),
                "references": [_image_reference_payload(item) for item in zet_app.scene_image_reference_rows()],
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/stories/{story_slug}/scenes/order")
    def scene_reorder(story_slug: str, data: dict = Body(...)) -> dict[str, Any]:
        """Persist the complete scene display order for one story."""
        zet_app = _app(app.state.config_path)
        try:
            scenes = zet_app.reorder_scenes(story_slug, data.get("slugs"))
            return {
                "scenes": [_scene_record_payload(item) for item in scenes],
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": "Scene order saved.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.patch("/api/stories/{story_slug}/scenes/{scene_slug}")
    def scene_rename(story_slug: str, scene_slug: str, data: dict = Body(...)) -> dict[str, Any]:
        """Rename one scene while preserving its slug."""
        zet_app = _app(app.state.config_path)
        try:
            document = zet_app.rename_scene(story_slug, scene_slug, data.get("title"))
            return {
                "scenes": [_scene_record_payload(item) for item in zet_app.list_scenes(story_slug)],
                "document": _scene_document_payload(zet_app, document),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": f"Renamed scene to {document.record.title}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/{story_slug}/scenes/{scene_slug}/move")
    def scene_move(story_slug: str, scene_slug: str, data: dict = Body(...)) -> dict[str, Any]:
        """Move one scene and its artifacts to another story."""
        zet_app = _app(app.state.config_path)
        try:
            target_story_slug = data.get("target_story_slug")
            document = zet_app.move_scene(story_slug, scene_slug, target_story_slug)
            return {
                "source_scenes": [_scene_record_payload(item) for item in zet_app.list_scenes(story_slug)],
                "target_scenes": [_scene_record_payload(item) for item in zet_app.list_scenes(target_story_slug)],
                "document": _scene_document_payload(zet_app, document),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": f"Moved scene {document.record.title} to {document.story.title}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/stories/{story_slug}/scenes/{scene_slug}/builder")
    def scene_builder_save(story_slug: str, scene_slug: str, data: dict = Body(...)) -> dict[str, Any]:
        """Save Scene Builder JSON for one story scene."""
        zet_app = _app(app.state.config_path)
        try:
            document = zet_app.save_scene_builder(story_slug, scene_slug, data)
            return {
                "document": _scene_builder_document_payload(zet_app, document),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": f"Saved Scene Builder data for {document.scene.title}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/{story_slug}/scenes/{scene_slug}/builder/continue-from")
    def scene_builder_continue_from(story_slug: str, scene_slug: str, source_scene_slug: str = Query(...)) -> dict[str, Any]:
        """Copy reusable visual setup from another scene in the same story."""
        zet_app = _app(app.state.config_path)
        try:
            document = zet_app.continue_scene_builder_from(story_slug, scene_slug, source_scene_slug)
            return {
                "document": _scene_builder_document_payload(zet_app, document),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": f"Continued from {source_scene_slug}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/{story_slug}/scenes/{scene_slug}/builder/generate")
    def scene_builder_generate(story_slug: str, scene_slug: str, data: dict = Body(...)) -> dict[str, Any]:
        """Generate Scene Builder outputs without saving JSON."""
        zet_app = _app(app.state.config_path)
        try:
            return {"data": _jsonable(zet_app.generate_scene_builder(story_slug, scene_slug, data))}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/stories/{story_slug}/scenes/{scene_slug}/prompt-analysis")
    def scene_prompt_analysis_status(story_slug: str, scene_slug: str) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            return zet_app.scene_prompt_analysis_status(story_slug, scene_slug)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/stories/{story_slug}/scenes/{scene_slug}/prompt-analysis/view", response_class=HTMLResponse)
    def scene_prompt_analysis_view(story_slug: str, scene_slug: str) -> HTMLResponse:
        zet_app = _app(app.state.config_path)
        try:
            status = zet_app.scene_prompt_analysis_status(story_slug, scene_slug)
            result_path = Path(status["result_path"])
            if not status["complete"] or not result_path.is_file():
                raise HTTPException(status_code=404, detail="Prompt analysis is not available.")
            content = markdown.markdown(result_path.read_text(encoding="utf-8"), extensions=["extra", "sane_lists"])
            return HTMLResponse(
                f"<!doctype html><html><head><meta charset=\"utf-8\"><title>Prompt Analysis</title>"
                "<style>body{max-width:900px;margin:40px auto;padding:0 24px;font:16px/1.55 system-ui,sans-serif}"
                "pre{padding:16px;overflow:auto;background:#f5f5f5}code{font-family:ui-monospace,monospace}"
                "table{border-collapse:collapse}th,td{padding:6px 10px;border:1px solid #ccc}</style></head>"
                f"<body>{content}</body></html>",
                headers={"Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'"},
            )
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/{story_slug}/scenes/{scene_slug}/prompt-analysis")
    def scene_prompt_analysis_queue(story_slug: str, scene_slug: str) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            status = zet_app.queue_scene_prompt_analysis(story_slug, scene_slug)
            status["message"] = "AI prompt analysis queued."
            return status
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/{story_slug}/scenes/{scene_slug}/prompt-analysis/harvest")
    def scene_prompt_analysis_harvest(story_slug: str, scene_slug: str) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            zet_app.harvest_ai_answers()
            status = zet_app.scene_prompt_analysis_status(story_slug, scene_slug)
            status["message"] = "AI answers harvested."
            return status
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/{story_slug}/scenes/{scene_slug}/builder/export-markdown")
    def scene_builder_export_markdown(story_slug: str, scene_slug: str, data: dict = Body(...)) -> dict[str, Any]:
        """Export Scene Builder-managed markdown into one story scene."""
        zet_app = _app(app.state.config_path)
        try:
            scene_document = zet_app.export_scene_builder_markdown(story_slug, scene_slug, data)
            builder_document = zet_app.load_scene_builder(story_slug, scene_slug)
            return {
                "document": _scene_document_payload(zet_app, scene_document),
                "builder": _scene_builder_document_payload(zet_app, builder_document),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": f"Exported Scene Builder sections for {scene_document.record.title}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/stories/{story_slug}/scenes/{scene_slug}")
    async def scene_save(story_slug: str, scene_slug: str, request: Request) -> dict[str, Any]:
        """Save one story scene markdown document."""
        zet_app = _app(app.state.config_path)
        try:
            text = (await request.body()).decode("utf-8")
            document = zet_app.save_scene(story_slug, scene_slug, text)
            return {
                "scenes": [_scene_record_payload(item) for item in zet_app.list_scenes(story_slug)],
                "document": _scene_document_payload(zet_app, document),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": f"Saved scene {document.record.title}.",
            }
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail="Scene markdown must be UTF-8.") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/stories/{story_slug}/scenes/{scene_slug}")
    def scene_delete(story_slug: str, scene_slug: str) -> dict[str, Any]:
        """Commit and delete one story scene markdown file and image."""
        zet_app = _app(app.state.config_path)
        try:
            result = zet_app.delete_scene(story_slug, scene_slug)
            return {
                "scenes": [_scene_record_payload(item) for item in zet_app.list_scenes(story_slug)],
                "git": _story_git_payload(result),
                "has_story_changes": zet_app.story_git_has_changes(),
                "message": f"Deleted scene {scene_slug}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/stories/{story_slug}/scenes/{scene_slug}/stage-render")
    def scene_stage_render(story_slug: str, scene_slug: str) -> dict[str, Any]:
        """Compile and stage one story scene for the Render Console."""
        zet_app = _app(app.state.config_path)
        try:
            task = zet_app.stage_scene_render(story_slug, scene_slug)
            return {
                "task": _story_render_task_payload(task),
                "message": f"Staged scene {task.scene_slug} for Render Console.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/scene-image-picker")
    def scene_image_picker(character: str = Query(""), text_filter: str = Query("")) -> dict[str, Any]:
        """List copyable auxiliary and locked-asset image references for scene editing."""
        zet_app = _app(app.state.config_path)
        try:
            return {
                "rows": [_image_reference_payload(item) for item in zet_app.scene_image_reference_rows(character, text_filter)]
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/identity-keys")
    def identity_keys(character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        """List saved identity keys."""
        zet_app = _app(app.state.config_path)
        try:
            return {
                "identity_keys": [
                    _identity_key_payload(zet_app, item)
                    for item in zet_app.list_identity_keys(character, phase)
                ]
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/identity-keys/{identity_key_id}")
    def identity_key_detail(identity_key_id: str, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        """Return one saved identity key."""
        zet_app = _app(app.state.config_path)
        try:
            return {
                "identity_key": _identity_key_payload(
                    zet_app,
                    zet_app.identity_key(character, phase, identity_key_id),
                )
            }
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
                "identity_key": _identity_key_payload(zet_app, identity_key),
                "identity_keys": [
                    _identity_key_payload(zet_app, item)
                    for item in zet_app.list_identity_keys(character, phase)
                ],
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
                "identity_keys": [
                    _identity_key_payload(zet_app, item)
                    for item in zet_app.list_identity_keys(character, phase)
                ],
                "message": "Identity Key deleted.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/costumes")
    def costumes(character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        """List costume templates."""
        zet_app = _app(app.state.config_path)
        try:
            return {"costumes": [_costume_payload(zet_app, character, phase, item) for item in zet_app.list_costumes(character, phase)]}
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
                "costume": _costume_payload(zet_app, character, phase, result.costume),
                "costumes": [_costume_payload(zet_app, character, phase, item) for item in zet_app.list_costumes(character, phase)],
                "assets": [_asset_payload(zet_app, asset) for asset in zet_app.list_assets(character, phase)],
                "message": f"Created {len(result.assets)} Costume-Dressing assets for {result.costume.name}.",
            }
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail="Costume template must be UTF-8 markdown.") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/costumes/{costume_slug}")
    def costume_update(
        costume_slug: str,
        character: str = Query(...),
        phase: str = Query(...),
        payload: dict[str, Any] = Body(...),
    ) -> dict[str, Any]:
        """Update a costume template name and related Costume-Dressing assets."""
        zet_app = _app(app.state.config_path)
        try:
            result = zet_app.update_costume(character, phase, costume_slug, str(payload.get("name") or ""))
            return {
                "costume": _costume_payload(zet_app, character, phase, result.costume),
                "costumes": [_costume_payload(zet_app, character, phase, item) for item in zet_app.list_costumes(character, phase)],
                "assets": [_asset_payload(zet_app, asset) for asset in zet_app.list_assets(character, phase)],
                "message": f"Updated costume {result.costume.name}.",
            }
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
                    _identity_key_payload(zet_app, item)
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
                    _identity_key_payload(zet_app, item)
                    for item in zet_app.list_identity_keys(character, phase)
                ],
                "assets": [_asset_payload(zet_app, asset) for asset in zet_app.list_assets(character, phase)],
                "message": f"Created Expression asset for {result.expression.label}.",
            }
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=400, detail="Expression definition must be UTF-8 markdown.") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/expressions/{asset_id}")
    def expression_update(
        asset_id: int,
        character: str = Query(...),
        phase: str = Query(...),
        payload: dict[str, Any] = Body(...),
    ) -> dict[str, Any]:
        """Update an expression definition and optional regeneration state."""
        zet_app = _app(app.state.config_path)
        try:
            result = zet_app.update_expression(
                character,
                phase,
                asset_id,
                str(payload.get("label") or ""),
                str(payload.get("identity_key_id") or ""),
                bool(payload.get("regenerate")),
            )
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
                    _identity_key_payload(zet_app, item)
                    for item in zet_app.list_identity_keys(character, phase)
                ],
                "assets": [_asset_payload(zet_app, asset) for asset in zet_app.list_assets(character, phase)],
                "message": f"Updated Expression asset for {result.expression.label}.",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/file")
    def local_file(path: str = Query(...), download: bool = Query(False)):
        """Serve a local file inline or as a browser download."""
        zet_app = _app(app.state.config_path)
        requested = zet_app.path_service.resolve_path(path)
        if not requested.exists() or not requested.is_file():
            raise HTTPException(status_code=404, detail=f"File not found: {path}")
        if download:
            return FileResponse(requested, filename=requested.name)
        return FileResponse(requested)

    @app.get("/api/prompt-evolution/options")
    def prompt_evolution_options(character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        try:
            return _app(app.state.config_path).prompt_evolution_options(character, phase)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/help/template-manuals")
    def template_manuals() -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        manuals = []
        for item in zet_app.template_manual_service.list():
            manuals.append({
                **item,
                "html": markdown.markdown(item["markdown"], extensions=["extra", "sane_lists"]),
                "download_url": f"/api/help/template-manuals/{item['id']}/download",
            })
        return {"manuals": manuals}

    @app.get("/api/help/template-manuals/{manual_id}/download")
    def template_manual_download(manual_id: str) -> FileResponse:
        zet_app = _app(app.state.config_path)
        try:
            item = zet_app.template_manual_service.get(manual_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Template manual not found.") from exc
        return FileResponse(item["path"], filename=item["filename"], media_type="text/markdown")

    @app.get("/api/prompt-evolution/runs")
    def prompt_evolution_runs() -> dict[str, Any]:
        return {"runs": _app(app.state.config_path).list_prompt_evolution_runs()}

    @app.get("/api/prompt-evolution/reference-preview")
    def prompt_evolution_reference_preview(
        character: str = Query(...), phase: str = Query(...), costume: str = Query(...), view: str = Query(...),
    ) -> Response:
        try:
            content = _app(app.state.config_path).prompt_evolution_service.reference_preview(character, phase, costume, view)
            return Response(content=content, media_type="image/png")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/prompt-evolution/runs")
    def prompt_evolution_create(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            return _app(app.state.config_path).create_prompt_evolution_run(payload)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/prompt-evolution/runs/{run_id}")
    def prompt_evolution_detail(run_id: str) -> dict[str, Any]:
        try:
            zet_app = _app(app.state.config_path)
            return zet_app.prompt_evolution_service.advance_run(run_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/prompt-evolution/runs/{run_id}/final-selection/{prompt_version_id}")
    def prompt_evolution_final_selection(
        run_id: str, prompt_version_id: str, payload: dict[str, Any] | None = Body(default=None),
    ) -> dict[str, Any]:
        try:
            return _app(app.state.config_path).prompt_evolution_service.select_prompt_version(
                run_id, prompt_version_id, str((payload or {}).get("selection_reason") or ""),
            )
        except (PromptEvolutionError, FileNotFoundError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/prompt-evolution/runs/{run_id}/prompt-review")
    def prompt_evolution_prompt_review(run_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            return _app(app.state.config_path).accept_prompt_evolution_review(
                run_id, str(payload.get("positive_core") or ""), str(payload.get("negative_core") or ""),
            )
        except (PromptEvolutionError, FileNotFoundError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/prompt-evolution/runs/{run_id}/abort")
    def prompt_evolution_abort(run_id: str) -> dict[str, Any]:
        try:
            return _app(app.state.config_path).prompt_evolution_service.abort(run_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/prompt-evolution/runs/{run_id}/name")
    def prompt_evolution_rename(run_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            return _app(app.state.config_path).prompt_evolution_service.rename(run_id, str(payload.get("name") or ""))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/prompt-evolution/runs/{run_id}/directed-refinement")
    def prompt_evolution_directed_refinement(run_id: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            return _app(app.state.config_path).prompt_evolution_service.start_directed_refinement(run_id, str(payload.get("instructions") or ""))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/prompt-evolution/runs/{run_id}")
    def prompt_evolution_delete(run_id: str) -> dict[str, Any]:
        try:
            return _app(app.state.config_path).prompt_evolution_service.delete(run_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/prompt-evolution/runs/{run_id}/audit-bundle")
    def prompt_evolution_audit_bundle(run_id: str) -> FileResponse:
        try:
            bundle = _app(app.state.config_path).prompt_evolution_service.create_audit_bundle(run_id)
            return FileResponse(
                bundle, media_type="application/zip", filename=f"prompt-evolution-{run_id}-audit.zip",
                background=BackgroundTask(bundle.unlink, missing_ok=True),
            )
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/prompt-evolution/runs/{run_id}/retry")
    def prompt_evolution_retry(run_id: str) -> dict[str, Any]:
        try:
            return _app(app.state.config_path).prompt_evolution_service.retry(run_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/prompt-evolution/runs/{run_id}/restart")
    def prompt_evolution_restart(run_id: str) -> dict[str, Any]:
        try:
            return _app(app.state.config_path).prompt_evolution_service.restart(run_id)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/prompt-evolution/runs/{run_id}/clone/{batch_index}")
    def prompt_evolution_clone(run_id: str, batch_index: int) -> dict[str, Any]:
        try:
            return _app(app.state.config_path).prompt_evolution_service.clone_from_batch(run_id, batch_index)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/prompt-evolution/templates")
    def prompt_evolution_templates() -> dict[str, Any]:
        service = _app(app.state.config_path).prompt_evolution_service
        return {"templates": {name: service.template(name) for name in service.template_names}}

    @app.get("/api/prompt-evolution/checklists")
    def prompt_evolution_checklists(
        character: str = Query(...), phase: str = Query(...), costume: str = Query(...),
    ) -> dict[str, Any]:
        try:
            return _app(app.state.config_path).prompt_evolution_service.scoped_checklists(character, phase, costume)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/prompt-evolution/checklists/{scope}")
    def prompt_evolution_checklist_save(scope: str, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            return _app(app.state.config_path).prompt_evolution_service.save_scoped_checklist(
                scope, str(payload.get("character") or ""), str(payload.get("phase") or ""),
                str(payload.get("costume") or ""), payload,
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.put("/api/prompt-evolution/templates/{name}")
    def prompt_evolution_template_save(name: str, payload: dict[str, Any] = Body(...)) -> dict[str, str]:
        try:
            return _app(app.state.config_path).prompt_evolution_service.save_template(name, str(payload.get("text") or ""))
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/edit-source/load")
    def edit_source_load(source: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            zet_app = _app(app.state.config_path)
            if source.get("editable") is False:
                raise HTTPException(status_code=400, detail="This source is not editable.")
            return SourceEditorService(zet_app, PROJECT_ROOT).load(source)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/edit-source/save")
    def edit_source_save(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        try:
            zet_app = _app(app.state.config_path)
            return SourceEditorService(zet_app, PROJECT_ROOT).save(payload)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/render-review/tasks")
    def render_review_tasks(
        character: str = Query(""),
        phase: str = Query(""),
        story_slug: str = Query(""),
        scene_slug: str = Query(""),
    ) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            tasks = []
            if character and phase:
                assets = [asset for asset in zet_app.list_assets(character, phase) if _is_render_review_asset(asset)]
                tasks.extend(_render_review_task_payload(zet_app, asset) for asset in assets)
            tasks.extend(
                _scene_render_review_task_payload(status)
                for status in zet_app.list_pending_scene_image_reviews(story_slug, scene_slug)
            )
            return {"tasks": tasks}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/render-review/scenes/{story_slug}/{scene_slug}")
    def scene_render_review_detail(story_slug: str, scene_slug: str) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            return _scene_render_review_context_payload(zet_app, story_slug, scene_slug)
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/render-review/scenes/{story_slug}/{scene_slug}/promote-to-locked")
    def scene_render_review_promote(story_slug: str, scene_slug: str) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            status = zet_app.promote_scene_image(story_slug, scene_slug)
            return {
                "message": f"Scene image approved for {status.story_slug}/{status.scene_slug}.",
                "review": asdict(status),
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/render-review/scenes/{story_slug}/{scene_slug}/discard-candidate")
    def scene_render_review_discard(story_slug: str, scene_slug: str) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            status = zet_app.discard_scene_image_candidate(story_slug, scene_slug)
            return {
                "message": f"Scene candidate discarded for {status.story_slug}/{status.scene_slug}.",
                "review": asdict(status),
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/render-review/scenes/{story_slug}/{scene_slug}/comment")
    async def scene_render_review_comment(story_slug: str, scene_slug: str, request: Request) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            payload = await request.json()
            comment = zet_app.save_scene_image_review_comment(story_slug, scene_slug, str(payload.get("comment") or ""))
            response = _scene_render_review_context_payload(zet_app, story_slug, scene_slug)
            response["message"] = "Image review comment saved." if comment else "Image review comment cleared."
            return response
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

    @app.post("/api/render-review/{asset_id}/discard-candidate")
    def render_review_discard_candidate(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            updated = zet_app.asset(character, phase, asset_id).discard_candidate()
            return {
                "message": f"Candidate discarded. Asset {updated.asset_id} moved to LOCKED.",
                "asset": _asset_payload(zet_app, updated),
                "tasks": [
                    _render_review_task_payload(zet_app, asset)
                    for asset in zet_app.list_assets(character, phase)
                    if _is_render_review_asset(asset)
                ],
            }
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

    @app.get("/api/phase-comparison")
    def phase_comparison(
        character: str = Query(...),
        left_phase: str = Query(...),
        right_phase: str = Query(...),
        pipeline: str = Query(""),
        selected_index: int = Query(0),
        selected_slot_key: str = Query(""),
        left_costume: str = Query(""),
        right_costume: str = Query(""),
    ) -> dict[str, Any]:
        """Return read-only locked asset comparison rows for two phases."""
        zet_app = _app(app.state.config_path)
        try:
            result = zet_app.phase_comparison(
                character,
                left_phase,
                right_phase,
                pipeline,
                selected_index,
                selected_slot_key,
                left_costume,
                right_costume,
            )
            return _jsonable(result)
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

    @app.get("/api/head-image-manifest/tasks")
    def head_image_manifest_tasks(character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            assets = [asset for asset in zet_app.list_assets(character, phase) if _is_head_image_manifest_asset(asset)]
            return {"tasks": [_asset_payload(zet_app, asset) for asset in assets]}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/character-assembly-manifest/tasks")
    def character_assembly_manifest_tasks(character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            assets = [asset for asset in zet_app.list_assets(character, phase) if _is_character_assembly_manifest_asset(asset)]
            return {"tasks": [_asset_payload(zet_app, asset) for asset in assets]}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/character-assembly-manifest/{asset_id}")
    def character_assembly_manifest_detail(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            return _character_assembly_manifest_context_payload(zet_app, character, phase, asset_id)
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/character-assembly-manifest/{asset_id}/references")
    def character_assembly_manifest_save_references(
        asset_id: int,
        payload: dict[str, Any] = Body(...),
        character: str = Query(...),
        phase: str = Query(...),
    ) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            updated = zet_app.save_character_assembly_references(
                character,
                phase,
                asset_id,
                str(payload.get("body_reference_path") or ""),
                str(payload.get("head_image_path") or ""),
            )
            response = _character_assembly_manifest_context_payload(zet_app, character, phase, updated.asset_id)
            response["message"] = "Character-assembly reference slots saved."
            return response
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/head-image-manifest/{asset_id}")
    def head_image_manifest_detail(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            return _head_image_manifest_context_payload(zet_app, character, phase, asset_id)
        except Exception as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/api/head-image-manifest/{asset_id}/source")
    def head_image_manifest_save_source(asset_id: int, payload: dict[str, Any] = Body(...), character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            zet_app.save_head_image_source(character, phase, asset_id, str(payload.get("source_path") or ""))
            response = _head_image_manifest_context_payload(zet_app, character, phase, asset_id)
            response["message"] = "Head-Image source saved."
            return response
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/head-image-sources")
    async def head_image_manifest_upload_source(request: Request, filename: str = Query(...), character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            path = zet_app.upload_head_image_source(character, phase, filename, await request.body())
            return {"path": str(path), "name": path.name}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/onboarding/head-images")
    def add_missing_head_images(character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            added = zet_app.add_missing_head_image_foundation(character, phase)
            return {"added": len(added), "message": f"Added {len(added)} missing Head-Image asset(s)."}
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

    @app.get("/api/local-image/checkpoints")
    def local_image_checkpoints(
        preset: str = Query("body-reference-preview"),
        backend: str = Query("stable_matrix"),
    ) -> dict[str, Any]:
        try:
            zet_app = _app(app.state.config_path)
            profiles_path = Path(app.state.config_path).resolve().parent / "Config" / "Local_Render_Presets.json"
            service = LocalRenderBackendService(profiles_path)
            server_url = zet_app.config.comfyui_server_url if backend == "comfyui" else ""
            return {"checkpoints": service.list_checkpoints(preset, backend=backend, server_url=server_url)}
        except Exception as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.get("/api/ai-controls/ollama-models")
    def ai_controls_ollama_models() -> dict[str, Any]:
        try:
            return OllamaModelService().list_models()
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"Unable to load Ollama models: {exc}") from exc

    @app.get("/api/render-console/tasks")
    def render_console_tasks(
        character: str = Query(""),
        phase: str = Query(""),
        story_slug: str = Query(""),
        scene_slug: str = Query(""),
    ) -> dict[str, Any]:
        """List manual render tasks for the selected workspace context."""
        queue = _render_console_queue(app.state.config_path)
        service = ManualRenderSubmissionService(queue)
        try:
            return {
                "tasks": [
                    task.to_dict()
                    for task in service.list_tasks(character, phase, story_slug, scene_slug)
                ]
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/render-console/tasks/{ask_id}")
    def render_console_task_detail(ask_id: str, character: str = Query(""), phase: str = Query("")) -> dict[str, Any]:
        """Return one manual render task for the selected character phase."""
        queue = _render_console_queue(app.state.config_path)
        task = ManualRenderSubmissionService(queue).get_task(ask_id, character, phase)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Manual render task not found: {ask_id}")
        zet_app = _app(app.state.config_path)
        return _render_console_detail_payload(zet_app, queue, task)

    @app.get("/api/local-image-review/tasks/{ask_id}")
    def local_image_review_task(ask_id: str, character: str = Query(""), phase: str = Query("")) -> dict[str, Any]:
        queue = _render_console_queue(app.state.config_path)
        task = ManualRenderSubmissionService(queue).get_task(ask_id, character, phase)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Manual render task not found: {ask_id}")
        try:
            return _local_image_review_payload(_app(app.state.config_path), task)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/local-image-review/tasks/{ask_id}/images")
    def local_image_review_generate(
        ask_id: str,
        count: int = Query(1, ge=1, le=10),
        character: str = Query(""),
        phase: str = Query(""),
    ) -> dict[str, Any]:
        queue = _render_console_queue(app.state.config_path)
        task = ManualRenderSubmissionService(queue).get_task(ask_id, character, phase)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Manual render task not found: {ask_id}")
        try:
            zet_app = _app(app.state.config_path)
            queued = LocalImageReviewService(zet_app).queue_images(task, count)
            payload = _local_image_review_payload(zet_app, task)
            payload["queued"] = queued
            payload["message"] = f"Queued {len(queued)} local image render(s) with distinct seeds."
            return payload
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/local-image-review/tasks/{ask_id}/images/all-checkpoints")
    def local_image_review_generate_all_checkpoints(
        ask_id: str,
        count: int = Query(1, ge=1, le=10),
        character: str = Query(""),
        phase: str = Query(""),
    ) -> dict[str, Any]:
        queue = _render_console_queue(app.state.config_path)
        task = ManualRenderSubmissionService(queue).get_task(ask_id, character, phase)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Manual render task not found: {ask_id}")
        try:
            zet_app = _app(app.state.config_path)
            queued, checkpoint_count = LocalImageReviewService(zet_app).queue_images_for_all_checkpoints(task, count)
            payload = _local_image_review_payload(zet_app, task)
            payload["queued"] = queued
            payload["message"] = (
                f"Queued {len(queued)} local image render(s) across {checkpoint_count} checkpoint(s)."
            )
            return payload
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/local-image-review/tasks/{ask_id}/images")
    def local_image_review_clear(
        ask_id: str,
        character: str = Query(""),
        phase: str = Query(""),
    ) -> dict[str, Any]:
        queue = _render_console_queue(app.state.config_path)
        task = ManualRenderSubmissionService(queue).get_task(ask_id, character, phase)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Manual render task not found: {ask_id}")
        try:
            zet_app = _app(app.state.config_path)
            removed = LocalImageReviewService(zet_app).clear_images(task)
            payload = _local_image_review_payload(zet_app, task)
            payload["removed_count"] = removed
            payload["message"] = f"Cleared {removed} local image(s)."
            return payload
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/render-console/tasks/{ask_id}/recompile")
    def render_console_recompile_prompt(
        ask_id: str,
        character: str = Query(""),
        phase: str = Query(""),
        invalidate_review_artifacts: bool = Query(False),
    ) -> dict[str, Any]:
        """Recompile an asset prompt and refresh the queued render prompt."""
        queue = _render_console_queue(app.state.config_path)
        service = ManualRenderSubmissionService(queue)
        task = service.get_task(ask_id, character, phase)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Manual render task not found: {ask_id}")
        if task.asset_id is None:
            raise HTTPException(status_code=400, detail="Scene prompts must be edited in Scene Builder.")
        zet_app = _app(app.state.config_path)
        try:
            context = zet_app.recompile_prompt_review(
                task.character,
                task.phase,
                task.asset_id,
                invalidate_review_artifacts=invalidate_review_artifacts,
            )
            if context.prompt_text is None:
                raise ValueError(f"No Final_Image_Prompt.md found for Asset {task.asset_id}.")
            service.replace_prompt(task, context.prompt_text)
            payload = _render_console_detail_payload(zet_app, queue, task)
            payload["message"] = f"Prompt recompiled for Asset {task.asset_id}."
            return payload
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/render-console/tasks/{ask_id}/local-test-render")
    def render_console_local_test_render(ask_id: str, character: str = Query(""), phase: str = Query("")) -> dict[str, Any]:
        """Generate a local test render for a render-console task."""
        queue = _render_console_queue(app.state.config_path)
        task = ManualRenderSubmissionService(queue).get_task(ask_id, character, phase)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Manual render task not found: {ask_id}")
        try:
            zet_app = _app(app.state.config_path)
            if task.asset_id is not None:
                context = zet_app.prompt_review_service.get_context(task.character, task.phase, task.asset_id)
                if context.condensed_prompt_path is None:
                    raise FileNotFoundError(f"No condensed prompt was found for task {ask_id}.")
                ask_path = zet_app.stage_render_task_local_render_ask(task.manifest, context.condensed_prompt_path, context.condensed_prompt_path.parent)
            else:
                workspace = _render_console_task_workspace(task)
                manifest = dict(task.manifest)
                ask_path = zet_app.stage_scene_local_render_ask(manifest, workspace)
            payload = {
                "task": task.to_dict(),
                "manifest": _jsonable(task.manifest),
                "prompt": queue.read_prompt(task),
                "local_prompt": _render_console_local_prompt_payload(zet_app, task),
            }
            payload["message"] = f"Local test render queued: {ask_path}" if ask_path else "Local test render already queued."
            return payload
        except LocalRenderUnavailable as exc:
            raise HTTPException(status_code=503, detail="Local render backend unavailable.") from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/api/render-console/tasks/{ask_id}/local-test-render/api-params")
    def render_console_local_test_render_api_params(ask_id: str, character: str = Query(""), phase: str = Query("")) -> dict[str, Any]:
        """Return harvested local test render API parameters for a render-console task."""
        queue = _render_console_queue(app.state.config_path)
        task = ManualRenderSubmissionService(queue).get_task(ask_id, character, phase)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Manual render task not found: {ask_id}")
        try:
            if task.asset_id is not None:
                zet_app = _app(app.state.config_path)
                context = zet_app.prompt_review_service.get_context(task.character, task.phase, task.asset_id)
                if context.condensed_prompt_path is None:
                    raise FileNotFoundError(f"No condensed prompt was found for task {ask_id}.")
                workspace = context.condensed_prompt_path.parent
            else:
                workspace = _render_console_task_workspace(task)
            api_call_path = _render_console_local_api_call_path(workspace)
            if not api_call_path.exists():
                raise FileNotFoundError(f"No harvested local render API artifact was found for task {ask_id}.")
            return {"path": str(api_call_path), "text": api_call_path.read_text(encoding="utf-8")}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.delete("/api/render-console/tasks/{ask_id}/local-test-render")
    def render_console_clear_local_test_render(ask_id: str, character: str = Query(""), phase: str = Query("")) -> dict[str, Any]:
        """Delete all local test renders for a render-console task."""
        queue = _render_console_queue(app.state.config_path)
        task = ManualRenderSubmissionService(queue).get_task(ask_id, character, phase)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Manual render task not found: {ask_id}")
        try:
            zet_app = _app(app.state.config_path)
            removed = LocalImageReviewService(zet_app).clear_images(task)
            return {
                "task": task.to_dict(),
                "manifest": _jsonable(task.manifest),
                "prompt": queue.read_prompt(task),
                "local_prompt": _render_console_local_prompt_payload(zet_app, task),
                "message": f"Cleared {removed} local image(s).",
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/render-console/tasks/{ask_id}/answer-image")
    async def render_console_answer_image(
        ask_id: str,
        request: Request,
        render_comment: str = Query("", max_length=10000),
        character: str = Query(""),
        phase: str = Query(""),
    ) -> dict[str, Any]:
        """Write a successful render answer for a task in the selected character phase."""
        queue = _render_console_queue(app.state.config_path)
        service = ManualRenderSubmissionService(queue)
        task = service.get_task(ask_id, character, phase)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Manual render task not found: {ask_id}")
        image_bytes = await request.body()
        content_type = request.headers.get("content-type", "")
        try:
            answer_path = service.submit_image(task, image_bytes, content_type, render_comment)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        review = None
        harvest_warning = ""
        if task.manifest.get("story_slug") and task.manifest.get("scene_slug"):
            try:
                zet_app = _app(app.state.config_path)
                zet_app.asset_service.ai_answer_harvester.apply_answer_folder(answer_path)
                review = asdict(zet_app.scene_image_review_status(
                    str(task.manifest["story_slug"]),
                    str(task.manifest["scene_slug"]),
                ))
            except Exception as exc:
                harvest_warning = f"Image answer was saved and is pending harvest: {exc}"
        try:
            tasks = service.list_tasks(character, phase)
        except Exception:
            tasks = []
        return {
            "status": "ACCEPTED" if harvest_warning else "SUCCESS",
            "answer_path": str(answer_path),
            "remaining_tasks": [item.to_dict() for item in tasks],
            "scene_image_review": review,
            "harvest_warning": harvest_warning,
        }

    @app.post("/api/render-console/tasks/{ask_id}/fail")
    async def render_console_fail_task(
        ask_id: str,
        request: Request,
        character: str = Query(""),
        phase: str = Query(""),
    ) -> dict[str, Any]:
        """Write a failed render answer for a task in the selected character phase."""
        queue = _render_console_queue(app.state.config_path)
        service = ManualRenderSubmissionService(queue)
        task = service.get_task(ask_id, character, phase)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Manual render task not found: {ask_id}")
        payload = await request.json()
        reason = str(payload.get("reason") or "")
        try:
            answer_path = service.submit_failure(task, reason)
            tasks = service.list_tasks(character, phase)
            return {
                "status": "ERROR",
                "answer_path": str(answer_path),
                "remaining_tasks": [item.to_dict() for item in tasks],
            }
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

    @app.post("/api/assets/{asset_id}/regenerate")
    def regenerate(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            result = zet_app.asset(character, phase, asset_id).regenerate_and_advance()
            message = f"Asset regenerated and advanced to {result.asset.pipeline_stage}."
            if result.messages:
                message = f"{message} " + " | ".join(result.messages)
            return _action_response(zet_app, character, phase, result.asset.asset_id, message)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/assets/{asset_id}/regenerate-and-clear-references")
    def regenerate_and_clear_references(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            updated = zet_app.asset(character, phase, asset_id).regenerate_and_clear_references()
            return _action_response(zet_app, character, phase, updated.asset_id, "Asset regenerated at MANIFEST with references cleared.")
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

    @app.post("/api/assets/{asset_id}/keep-locked")
    def keep_locked(asset_id: int, character: str = Query(...), phase: str = Query(...)) -> dict[str, Any]:
        zet_app = _app(app.state.config_path)
        try:
            updated = zet_app.asset(character, phase, asset_id).keep_locked()
            return _action_response(zet_app, character, phase, updated.asset_id, "Keeping existing locked image.")
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


app = create_app()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Zet FastAPI web dashboard.")
    parser.add_argument("--config", default="config.toml")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    import uvicorn

    uvicorn.run(create_app(args.config), host=args.host, port=args.port, reload=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
