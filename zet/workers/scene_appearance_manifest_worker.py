from Scripts.Auxiliary_Resource_Tags import auxiliary_references_for_texts
from zet.models.worker import WorkerResult
from zet.services.scene_appearance_service import SceneAppearanceService
from zet.workers.character_assembly_manifest_worker import _assets_payload, _matching_asset


def run(asset, context) -> WorkerResult:
    """Resolve one same-view costume source and the ordered configured references."""
    if asset.pipeline != "Scene-Appearance":
        return WorkerResult(
            success=False,
            message=f"Scene-Appearance manifest worker cannot run for pipeline {asset.pipeline}.",
            advance_stage=False,
            error_code="WRONG_PIPELINE",
            error_message=f"Expected Scene-Appearance, got {asset.pipeline}.",
        )
    try:
        definition = SceneAppearanceService(context.asset_repository, context.path_service).get_definition(
            asset.character, asset.phase, asset.scene_appearance_id or ""
        )
        _, payload = _assets_payload(context)
        source_record, source_path = _matching_asset(
            context,
            payload,
            pipeline="Costume-Dressing",
            body_view=asset.body_view,
            head_view=asset.head_view or asset.body_view,
            costume=definition.costume,
        )
        if source_record is None or source_path is None:
            return WorkerResult(
                success=False,
                message=f"No locked {definition.costume} costume image found for {asset.body_view}.",
                advance_stage=False,
                error_code="MISSING_COSTUME_DRESSING",
                error_message=f"No locked Costume-Dressing source found for {definition.costume} / {asset.body_view}.",
            )
        references = [{
            "role": "scene_appearance_source",
            "label": f"Locked {definition.costume} costume image",
            "path": str(source_path),
            "source_asset_id": source_record.get("asset_id"),
            "body_view": source_record.get("body_view"),
            "head_view": source_record.get("head_view"),
            "costume": source_record.get("costume"),
        }]
        resolved = auxiliary_references_for_texts(
            context.path_service.project_root,
            ["\n".join(item.tag for item in definition.supporting_references)],
            [],
        )
        by_tag = {str(item.get("tag") or ""): item for item in resolved}
        for configured in definition.supporting_references:
            reference = by_tag.get(configured.tag)
            if reference is None:
                raise ValueError(f"Supporting reference did not resolve: {configured.tag}")
            references.append({
                **reference,
                "role": configured.role,
                "label": configured.label,
            })
        return WorkerResult(
            success=True,
            message=f"Resolved {len(references)} Scene Appearance references for Asset {asset.asset_id}.",
            output_files=[str(item.get("path") or "") for item in references],
            reference_files=references,
            advance_stage=True,
        )
    except Exception as exc:
        return WorkerResult(
            success=False,
            message=str(exc),
            advance_stage=False,
            error_code="MISSING_REFERENCE",
            error_message=str(exc),
        )
