import json
from pathlib import Path

import pytest

from Scripts.Retire_Head_Fitment import retire_phase
from zet.models.asset import Asset
from zet.repositories.asset_repository import AssetRepository, AssetRepositoryError
from zet.services.config_service import Config
from zet.services.path_service import PathService


def _paths(root: Path) -> PathService:
    return PathService(Config(
        base_library_path=str(root),
        base_character_path=str(root / "Characters"),
        base_asset_path=str(root / "Assets"),
        base_pipeline_path=str(root / "Pipelines"),
        base_ai_queue_path=str(root / "Queue"),
    ))


def test_retirement_archives_fitment_and_reserves_ids_idempotently(tmp_path: Path) -> None:
    paths = _paths(tmp_path)
    phase = paths.character_path("Test", "Adult")
    assets = paths.character_asset_path("Test", "Adult")
    old_pipeline = paths.pipeline_base_path("Test", "Adult") / "Head-Fitment" / "Front"
    phase.mkdir(parents=True)
    assets.mkdir(parents=True)
    old_pipeline.mkdir(parents=True)
    (old_pipeline / "diagnostic.json").write_text("{}", encoding="utf-8")
    (assets / "fitment.png").write_bytes(b"fitment")
    records = [
        Asset(1, "Test", "Adult", "Body-Reference", "Front", asset_state="LOCKED", pipeline_stage="LOCKED").__dict__,
        Asset(2, "Test", "Adult", "Head-Fitment", "Front", head_view="Front", asset_state="LOCKED", pipeline_stage="LOCKED", final_image_output="fitment.png").__dict__,
        Asset(3, "Test", "Adult", "Character-Assembly", "Front", head_view="Front", asset_state="LOCKED", pipeline_stage="LOCKED", reference_files=[{"role": "head_fitment", "source_asset_id": 2, "path": str(assets / "fitment.png")}]).__dict__,
    ]
    (phase / "Assets.json").write_text(json.dumps({"schema_version": 1, "next_asset_id": 4, "assets": records}), encoding="utf-8")
    (phase / "Pipelines.json").write_text(json.dumps({"pipelines": {"Head-Fitment": {}, "Character-Assembly": {}}}), encoding="utf-8")

    first = retire_phase(paths, "Test", "Adult", "stamp")
    second = retire_phase(paths, "Test", "Adult", "later")

    assert first["changed"] is True
    assert second["changed"] is False
    payload = json.loads((phase / "Assets.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == 2
    assert payload["reserved_asset_ids"] == [2]
    assert [record["asset_id"] for record in payload["assets"]] == [1, 3]
    historical = payload["assets"][1]["reference_files"][0]
    assert historical["historical_only"] is True
    assert historical["archived"] is True
    assert (phase / "_archive" / "Head-Fitment" / "Assets" / "fitment.png").read_bytes() == b"fitment"
    assert (phase / "_archive" / "Head-Fitment" / "Pipeline" / "Front" / "diagnostic.json").exists()
    assert (phase / "_backup" / "HeadFitmentRetirement" / "stamp" / "Assets.json").exists()
    pipelines = json.loads((phase / "Pipelines.json").read_text(encoding="utf-8"))["pipelines"]
    assert "Head-Fitment" not in pipelines

    repository = AssetRepository(paths)
    with pytest.raises(AssetRepositoryError, match="not found"):
        repository.get_asset("Test", "Adult", 2)
    with pytest.raises(AssetRepositoryError, match="reserved"):
        repository.create_asset(Asset(2, "Test", "Adult", "Head-Image", "Front"))
    created = repository.create_asset(Asset(0, "Test", "Adult", "Head-Image", "Front"))
    assert created.asset_id == 4
