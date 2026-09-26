from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from zet.services.local_asset_store_service import LocalAssetStoreError, LocalAssetStoreService


def test_locked_dependent_remains_locked_when_upstream_selection_changes(tmp_path: Path) -> None:
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

    store.record_selection("Tsaeytte", "Adult", "Head-Image", "FRONT", candidate_id="c003",
                           image_path=front, batch_id="run-2")
    child = store.detail("Tsaeytte", "Adult")["assets"][store.key("Head-Image", "LEFT_PROFILE")]
    assert child["locked"] is True
    store.unlock("Tsaeytte", "Adult", "Head-Image", "LEFT_PROFILE")


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


def test_batch_selection_does_not_replace_existing_lock(tmp_path: Path) -> None:
    store = LocalAssetStoreService(tmp_path)
    old_image, new_image = tmp_path / "old.png", tmp_path / "new.png"
    Image.new("RGB", (32, 32), "white").save(old_image)
    Image.new("RGB", (32, 32), "black").save(new_image)
    store.record_selection("Test", "Adult", "Body-Reference", "FRONT",
                           candidate_id="old", image_path=old_image, batch_id="earlier")
    store.lock("Test", "Adult", "Body-Reference", "FRONT")

    assert store.record_batch_selection("Test", "Adult", "Body-Reference", "FRONT",
                                        candidate_id="new", image_path=new_image, batch_id="new-run") is None
    locked = store.lock_batch_selection("Test", "Adult", "Body-Reference", "FRONT",
                                        candidate_id="new", image_path=new_image, batch_id="new-run")
    assert locked["locked"] and locked["batch_id"] == "new-run"
    assert store.detail("Test", "Adult")["assets"]["body-reference:FRONT"]["batch_id"] == "new-run"


def test_lock_allows_selected_image_when_upstream_has_changed(tmp_path: Path) -> None:
    store = LocalAssetStoreService(tmp_path)
    old_front, selected_front, back = (tmp_path / name for name in ("old-front.png", "selected-front.png", "back.png"))
    Image.new("RGB", (32, 32), "white").save(old_front)
    Image.new("RGB", (32, 32), "gray").save(selected_front)
    Image.new("RGB", (32, 32), "black").save(back)
    store.record_selection("Test", "Adult", "Head-Image", "FRONT", candidate_id="old-front",
                           image_path=old_front, batch_id="old-run")
    store.lock("Test", "Adult", "Head-Image", "FRONT")
    store.unlock("Test", "Adult", "Head-Image", "FRONT")
    store.record_selection("Test", "Adult", "Head-Image", "FRONT", candidate_id="selected-front",
                           image_path=selected_front, batch_id="new-run")
    store.record_selection("Test", "Adult", "Head-Image", "BACK", candidate_id="back",
                           image_path=back, batch_id="new-run", dependencies=[{
                               "key": store.key("Head-Image", "FRONT"),
                               "image_sha256": store._image_hash(old_front),
                           }])

    locked = store.lock("Test", "Adult", "Head-Image", "BACK")
    assert locked["locked"] is True


def test_promote_chain_leaves_index_unchanged_when_copy_fails(tmp_path: Path) -> None:
    store = LocalAssetStoreService(tmp_path)
    first, second = tmp_path / "first.png", tmp_path / "second.png"
    Image.new("RGB", (32, 32), "white").save(first)
    Image.new("RGB", (32, 32), "black").save(second)
    records = [
        {"pipeline": "Head-Image", "view": "FRONT", "candidate_id": "front", "batch_id": "run",
         "image_path": str(first), "image_sha256": store._image_hash(first)},
        {"pipeline": "Character-Assembly", "view": "FRONT", "candidate_id": "assembly", "batch_id": "run",
         "image_path": str(second), "image_sha256": store._image_hash(second)},
    ]
    original_copy = __import__("shutil").copy2
    calls = 0

    def fail_second_copy(source, destination):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated copy failure")
        return original_copy(source, destination)

    with patch("zet.services.local_asset_store_service.shutil.copy2", side_effect=fail_second_copy):
        with pytest.raises(OSError, match="simulated copy failure"):
            store.promote_chain("Test", "Adult", records)
    assert store.detail("Test", "Adult")["assets"] == {}
