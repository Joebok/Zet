from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re

from zet.models.worker import WorkerResult
from zet.services.config_service import ConfigService


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RESULT_FILE = "AI_Prompt_Review_Result.txt"
RAW_RESULT_FILE = "AI_Prompt_Review_Raw_Response.txt"
PROMPT_FILE = "OLLAMA_PROMPT.md"
TASK_TYPE = "ai_prompt_review"


@dataclass(frozen=True)
class AIReviewResult:
    """Represent a parsed AI prompt review response."""

    result: str
    category: str
    summary: str


def run(asset, context) -> WorkerResult:
    """Queue or apply an AI prompt review for a PROMPT_REVIEW asset."""
    prompt_path = _resolve_prompt_path(context.pipeline_path)
    if prompt_path is None:
        return WorkerResult(
            success=False,
            message="No Final_Image_Prompt.md found for AI prompt review.",
            advance_stage=False,
            error_code="AI_PROMPT_REVIEW_MISSING_PROMPT",
            error_message="No Final_Image_Prompt.md found for AI prompt review.",
        )

    result_path = prompt_path.parent / RESULT_FILE
    if result_path.exists() and result_path.stat().st_mtime >= prompt_path.stat().st_mtime:
        raw_text = result_path.read_text(encoding="utf-8")
        raw_path = prompt_path.parent / RAW_RESULT_FILE
        raw_path.write_text(raw_text, encoding="utf-8")
        parsed = _parse_review_response(raw_text)
        if parsed is None:
            return WorkerResult(
                success=False,
                message="AI prompt review response could not be parsed.",
                advance_stage=False,
                output_files=[str(result_path), str(raw_path)],
                error_code="AI_PROMPT_REVIEW_UNPARSABLE",
                error_message=f"AI prompt review response could not be parsed. Raw response saved at {raw_path}.",
            )
        if parsed.result == "PASS":
            return WorkerResult(
                success=True,
                message=f"AI prompt review passed: {parsed.summary}",
                output_files=[str(result_path), str(raw_path)],
                advance_stage=True,
            )
        return WorkerResult(
            success=False,
            message=f"AI prompt review failed: {parsed.summary}",
            output_files=[str(result_path), str(raw_path)],
            advance_stage=False,
            error_code="PROMPT_REVIEW_NEEDS_HUMAN",
            error_message=f"AI prompt review {parsed.category}: {parsed.summary}",
        )

    config = ConfigService.load(PROJECT_ROOT / "config.toml")
    if _has_pending_review(config.base_ai_queue_path, asset.asset_id):
        return WorkerResult(
            success=True,
            message="AI prompt review is already queued; waiting for proxy answer harvest.",
            advance_stage=False,
        )

    ask_path = _queue_review_ask(config, asset, prompt_path)
    return WorkerResult(
        success=True,
        message=f"Queued AI prompt review at {ask_path}.",
        output_files=[str(ask_path)],
        advance_stage=False,
    )


def _resolve_prompt_path(pipeline_path: Path) -> Path | None:
    """Find the prompt file to validate."""
    for name in ("Final_Image_Prompt.md", "OLLAMA_PROMPT.md"):
        path = pipeline_path / name
        if path.exists() and path.is_file():
            return path
    return None


def _parse_review_response(text: str) -> AIReviewResult | None:
    """Parse the exact AI prompt review response fields."""
    fields: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^\s*(RESULT|CATEGORY|SUMMARY)\s*:\s*(.*?)\s*$", line, re.IGNORECASE)
        if match:
            fields[match.group(1).upper()] = match.group(2).strip()
    result = fields.get("RESULT", "").upper()
    category = fields.get("CATEGORY", "").upper()
    summary = fields.get("SUMMARY", "").strip()
    valid_categories = {"NONE", "TEMPLATE", "CONTRADICTION", "AMBIGUITY", "STALE_TEXT", "MISSING_INFORMATION", "OTHER"}
    if result not in {"PASS", "FAIL"} or category not in valid_categories or not summary:
        return None
    if result == "PASS" and category != "NONE":
        return None
    if result == "FAIL" and category == "NONE":
        return None
    return AIReviewResult(result=result, category=category, summary=summary)


def _queue_review_ask(config, asset, prompt_path: Path) -> Path:
    """Write an Ollama proxy ask for AI prompt validation."""
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    ask_id = f"Ask_Asset_{asset.asset_id}_AI_PROMPT_REVIEW_{stamp}"
    attempt_id = f"{stamp}_{asset.asset_id}_AI_PROMPT_REVIEW"
    ask_root = Path(config.base_ai_queue_path) / "Ollama_Proxy" / "Ask"
    ask_path = ask_root / ask_id
    ask_path.mkdir(parents=True, exist_ok=False)
    manifest = {
        "version": 1,
        "ask_id": ask_id,
        "asset_id": asset.asset_id,
        "character": asset.character,
        "phase": asset.phase,
        "pipeline": asset.pipeline,
        "pipeline_stage": asset.pipeline_stage,
        "ollama_attempt_id": attempt_id,
        "worker_type": "ollama_generate",
        "ollama_model": config.ai_prompt_review_model,
        "prompt_file": PROMPT_FILE,
        "expected_output": RESULT_FILE,
        "candidate_output_file": None,
        "task_type": TASK_TYPE,
        "auxiliary": True,
        "manual": False,
        "target_output_file": RESULT_FILE,
        "target_output_dir": str(prompt_path.parent.resolve()),
        "ai_prompt_review_instructions_file": config.ai_prompt_review_instructions_file,
    }
    (ask_path / "ask_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    (ask_path / PROMPT_FILE).write_text(_review_prompt(config, prompt_path), encoding="utf-8")
    return ask_path


def _review_prompt(config, prompt_path: Path) -> str:
    """Render the configured AI review instructions with the final prompt text."""
    instructions_path = PROJECT_ROOT / config.ai_prompt_review_instructions_file
    instructions = instructions_path.read_text(encoding="utf-8")
    return instructions.replace("{{FINAL_IMAGE_PROMPT}}", prompt_path.read_text(encoding="utf-8"))


def _has_pending_review(base_ai_queue_path: str, asset_id: int) -> bool:
    """Return true when this asset already has an unharvested AI prompt review task."""
    proxy_root = Path(base_ai_queue_path) / "Ollama_Proxy"
    roots = [proxy_root / "Ask", proxy_root / "Answer"]
    claimed_root = proxy_root / "Claimed"
    if claimed_root.exists():
        roots.extend(path for path in claimed_root.iterdir() if path.is_dir())
    for root in roots:
        if not root.exists():
            continue
        for ask_path in root.iterdir():
            if not ask_path.is_dir():
                continue
            if (ask_path / "harvest_manifest.json").exists():
                continue
            manifest_path = ask_path / "ask_manifest.json"
            if not manifest_path.exists():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if manifest.get("asset_id") == asset_id and manifest.get("task_type") == TASK_TYPE:
                return True
    return False
