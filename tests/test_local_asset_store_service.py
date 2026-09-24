from pathlib import Path

import pytest
from PIL import Image

from zet.services.local_asset_store_service import LocalAssetStoreError, LocalAssetStoreService


def test_locked_dependent_blocks_upstream_change_until_unlocked(tmp_path: Path) -> None:
    store = LocalAssetStoreService(tmp_path)
    front = tmp_path / "front.png"
    profile = tmp_path / "profile.png"
    Image.new("RGB", (32, 32), "white").save(front)
    Image.new("RGB", (32, 32), "black").save(profile)
    front_hash = store._image_hash(front)
    store.record_selection("Tsaeytte", "Adult", "Head-Image", "FRONT", candidate_id="c001",
                           image_path=front, batch_id="run-1")
    store.record_selection("Tsaeytte", "Adult", "Head-Image", "LEFT_PROFILE", candidate_id="c002",
                           image_path=profile, batch_id="run-1", dependencies=[{
                               "key": store.key("Head-Image", "FRONT"), "image_sha256": front_hash,
                           }])
    store.lock("Tsaeytte", "Adult", "Head-Image", "LEFT_PROFILE")

    with pytest.raises(LocalAssetStoreError, match="unlock downstream local assets first"):
        store.record_selection("Tsaeytte", "Adult", "Head-Image", "FRONT", candidate_id="c003",
                               image_path=front, batch_id="run-2")

    store.unlock("Tsaeytte", "Adult", "Head-Image", "LEFT_PROFILE")
    store.record_selection("Tsaeytte", "Adult", "Head-Image", "FRONT", candidate_id="c003",
                           image_path=front, batch_id="run-2")
    child = store.detail("Tsaeytte", "Adult")["assets"][store.key("Head-Image", "LEFT_PROFILE")]
    assert child["stale"] is True


def test_locked_lookup_returns_verified_immutable_copy(tmp_path: Path) -> None:
    store = LocalAssetStoreService(tmp_path)
    source = tmp_path / "source.png"
    Image.new("RGB", (32, 32), "white").save(source)
    store.record_selection("Valindia", "Adult", "Body-Reference", "FRONT", candidate_id="c010",
                           image_path=source, batch_id="run-3")
    record = store.lock("Valindia", "Adult", "Body-Reference", "FRONT")

    assets = store.locked_assets("Valindia", "Adult")
    assert len(assets) == 1
    assert assets[0]["key"] == "body-reference:FRONT"
    assert Path(assets[0]["image_path"]) == Path(record["locked_image_path"])
    assert assets[0]["image_sha256"] == store._image_hash(Path(record["locked_image_path"]))
