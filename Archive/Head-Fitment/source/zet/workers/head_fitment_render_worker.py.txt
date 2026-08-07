from dataclasses import replace

from zet.models.worker import WorkerResult


def run(asset, context) -> WorkerResult:
    if asset.pipeline != "Head-Fitment":
        return WorkerResult(False, "Masked-local worker only supports Head-Fitment.", advance_stage=False, error_code="WRONG_PIPELINE")
    config = context.config
    if config is None or str(config.head_fitment_render_mode) != "masked_local":
        return WorkerResult(False, "Head-Fitment masked-local render mode is not enabled.", advance_stage=False, error_code="MASKED_LOCAL_DISABLED")
    if context.ai_proxy_service is None:
        return WorkerResult(False, "AI Proxy service is unavailable.", advance_stage=False, error_code="AI_PROXY_UNAVAILABLE")
    queued_asset = replace(asset)
    queued_asset.actor = "AI_AGENT"
    queued_asset.ai_state = None
    context.asset_repository.save_asset(queued_asset)
    try:
        ask_path = context.ai_proxy_service.stage_current_ai_ask(asset.character, asset.phase, asset.asset_id)
    except Exception as exc:
        return WorkerResult(False, str(exc), advance_stage=False, error_code="HEAD_FITMENT_AI_PROXY_STAGING_FAILED", error_message=str(exc))
    return WorkerResult(
        True,
        f"Staged masked-local Head-Fitment inpaint ask for Asset {asset.asset_id}.",
        output_files=[str(ask_path)],
        advance_stage=False,
    )
