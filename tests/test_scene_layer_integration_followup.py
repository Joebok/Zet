from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from zet.services.scene_layer_integration_followup import (
    FINAL_CRITERIA, PREP_CRITERIA, SceneLayerIntegrationFollowup,
    _grabcut_mask_full, _paper_mask_full, _parent_alpha_mask_full,
    _source_ground_removal, _source_restore_mask, _source_shadow_removal, _write_json,
)
from zet.services.scene_assembly_experiment_service import _hash


def _service(tmp_path: Path) -> SceneLayerIntegrationFollowup:
    service = SceneLayerIntegrationFollowup("test-followup")
    service.root = tmp_path
    service.root.mkdir(parents=True, exist_ok=True)
    service._test_parent_hash = _hash(service.parent_root / "manifest.json")
    return service


def _prep_manifest(service: SceneLayerIntegrationFollowup, *, has_luna: bool) -> str:
    slug = "Chapter-01-Standing-in-Wonder"
    image = service.root / "preview.png"
    Image.new("RGB", (16, 16), "white").save(image)
    digest = _hash(image)
    review = {"status": "LUNA_PROPOSED" if has_luna else "PENDING_LUNA", "luna": None, "human": None}
    if has_luna:
        review["luna"] = {"response": {"candidate_hash": digest}}
    manifest = {"parent_manifest_sha256": service._test_parent_hash, "status": "PREPARED_REVIEW_REQUIRED",
                "scenes": {slug: {"prepared_v2": {"preview": str(image), "candidate_hash": digest,
                                                        "raw_composite": str(image),
                                                        "edit_mask": str(image),
                                                        "luna_review_hashes": {"review-preview.png": digest}},
                                   "prep_review": review,
                                   "final_reviews": {}, "requirements": [], "sources": {}, "baseline_outputs": {}}}}
    _write_json(service.root / "manifest.json", manifest)
    return slug


def test_source_masks_stay_in_full_source_coordinates_and_keep_components():
    source = Image.new("RGB", (100, 80), "white")
    source.paste((40, 60, 90), (20, 10, 35, 70))
    source.paste((190, 40, 30), (72, 30, 82, 40))  # disconnected prop
    mask = _paper_mask_full(source)
    assert mask.shape == (80, 100)
    assert mask[40, 25]
    assert mask[34, 76]
    assert not mask[5, 5]


def test_grabcut_mask_uses_full_source_frame():
    source = Image.new("RGB", (120, 100), "white")
    source.paste("navy", (30, 10, 90, 98))
    mask = _grabcut_mask_full(source, (25, 5, 70, 90))
    assert mask.shape == (100, 120)
    assert mask[50, 55]
    assert not mask[50, 10]


def test_parent_alpha_is_mapped_to_source_frame_without_changing_pixels():
    cutout = Image.new("RGBA", (20, 15), (10, 20, 30, 255))
    cutout.putalpha(Image.new("L", cutout.size, 0))
    cutout.getchannel("A").putpixel((4, 5), 255)
    alpha = cutout.getchannel("A")
    assert alpha.getpixel((4, 5)) == 0  # getchannel returns a copy
    alpha.putpixel((4, 5), 255)
    cutout.putalpha(alpha)
    mask = _parent_alpha_mask_full((40, 30), cutout, (10, 8, 30, 23))
    assert mask.shape == (30, 40)
    assert mask[13, 14]
    assert not mask[0, 0]


def test_chapter_three_floor_trim_exempts_all_five_book_regions():
    remove = _source_ground_removal("Chapter-03-Collision", "pair", (928, 1152))
    assert remove[1090, 900]
    for x, y in [(90, 890), (80, 975), (80, 1080), (380, 1100), (820, 980)]:
        assert not remove[y, x]
    assert remove[1030, 850]  # keep the right-hand book, not its surrounding floor
    group_remove = _source_ground_removal("Chapter-03-Collision", "group", (928, 1152))
    assert group_remove[1050, 700]
    for x, y in [(60, 1035), (232, 1035), (354, 975), (500, 1090)]:
        assert not group_remove[y, x]


def test_chapter_two_restores_both_visible_boots_without_filling_the_ground():
    keep = _source_restore_mask("Chapter-02-At-the-Arch", "Tsaeytte", (1376, 768))
    assert keep[730, 1010]
    assert keep[730, 1090]
    assert not keep[730, 1180]


def test_chapter_two_shadow_trim_removes_light_floor_but_keeps_dark_shoe():
    source = Image.new("RGB", (100, 100), "white")
    draw = ImageDraw.Draw(source)
    draw.rectangle((10, 85, 35, 94), fill=(190, 190, 190))
    draw.rectangle((60, 85, 80, 94), fill=(55, 35, 25))
    remove = _source_shadow_removal("Chapter-02-At-the-Arch", "group", source)
    assert remove[90, 20]
    assert not remove[90, 70]


def test_human_confirmation_requires_successful_current_luna_hash(tmp_path):
    service = _service(tmp_path)
    slug = _prep_manifest(service, has_luna=False)
    values = {"criteria": {key: {"result": "fail", "reason": "needs source repair"} for key in PREP_CRITERIA}}
    with pytest.raises(ValueError, match="Luna proposal is required"):
        service.confirm_prep(slug, values, amended=False)


def test_confirmed_luna_review_is_effective_only_after_human_action(tmp_path):
    service = _service(tmp_path)
    slug = _prep_manifest(service, has_luna=True)
    before = service._manifest()["scenes"][slug]["prep_review"]
    assert before["human"] is None
    values = {"criteria": {key: {"result": "fail", "reason": "human confirms visible defect"} for key in PREP_CRITERIA},
              "summary": "Keep blocked pending repair."}
    service.confirm_prep(slug, values, amended=True)
    after = service._manifest()["scenes"][slug]["prep_review"]
    assert after["status"] == "HUMAN_CONFIRMED"
    assert after["human"]["action"] == "amended"
    assert after["human"]["summary"] == values["summary"]
    assert all(after["human"]["criteria"][k]["result"] == "fail" for k in PREP_CRITERIA)


def test_final_review_ratings_require_complete_rubric(tmp_path):
    service = _service(tmp_path)
    slug = "Chapter-03-Collision"
    image = tmp_path / "candidate.png"
    Image.new("RGB", (8, 8), "white").save(image)
    digest = _hash(image)
    review = {"status": "LUNA_PROPOSED", "input_hash": digest,
              "luna": {"response": {"candidate_hash": digest}}, "human": None}
    manifest = {"parent_manifest_sha256": service._test_parent_hash, "status": "PREPARED_REVIEW_REQUIRED",
                "scenes": {slug: {"final_reviews": {"1101": review}, "prep_review": {}}}}
    _write_json(tmp_path / "manifest.json", manifest)
    with pytest.raises(ValueError, match="All required criteria"):
        service.confirm_review(f"{slug}:1101", {"criteria": {}}, amended=True)


def test_confirmed_failed_prep_does_not_count_as_approved(tmp_path):
    service = _service(tmp_path)
    reviews = {}
    for slug in ("a", "b", "c"):
        reviews[slug] = {"prep_review": {"status": "HUMAN_CONFIRMED", "human": {
            "criteria": {key: {"result": "pass"} for key in PREP_CRITERIA}}}}
    reviews["b"]["prep_review"]["human"]["criteria"]["mask_correctness"]["result"] = "fail"
    assert service._effective_prep_status({"scenes": reviews}) == "PREPARATION_REPAIR_REQUIRED"


def test_manual_brush_writes_full_source_keep_remove_masks(tmp_path, monkeypatch):
    service = _service(tmp_path)
    slug = "Chapter-01-Standing-in-Wonder"
    annotation = tmp_path / "annotations" / "group"
    annotation.mkdir(parents=True)
    Image.new("L", (40, 30), 0).save(annotation / "manual-keep.png")
    Image.new("L", (40, 30), 0).save(annotation / "manual-remove.png")
    manifest = {"parent_manifest_sha256": service._test_parent_hash, "status": "PREPARED_REVIEW_REQUIRED",
                "scenes": {slug: {"prepared_v2": {"preview": str(tmp_path / "preview.png"), "candidate_hash": "hash",
                    "layers": [{"key": "group", "label": "Group",
                    "source_size": [40, 30], "manual_keep": str(annotation / "manual-keep.png")} ]},
                    "prep_review": {"status": "HUMAN_CONFIRMED", "human": {"criteria": {}}}}}}
    _write_json(tmp_path / "manifest.json", manifest)
    monkeypatch.setattr(service, "prepare", lambda: {})
    service.annotate_layer(slug, "group", "remove", 2, [[10, 10], [20, 10]], [40, 30])
    keep = Image.open(annotation / "manual-keep.png")
    remove = Image.open(annotation / "manual-remove.png")
    assert remove.getpixel((15, 10)) == 255
    assert keep.getpixel((15, 10)) == 0
    service.annotate_layer(slug, "group", "keep", 2, [[15, 10]], [40, 30])
    assert Image.open(annotation / "manual-keep.png").getpixel((15, 10)) == 255
    assert Image.open(annotation / "manual-remove.png").getpixel((15, 10)) == 0

