from types import SimpleNamespace

import pytest

from zet.services.narrative_scene_service import NarrativeSceneService


@pytest.fixture
def author(tmp_path):
    return NarrativeSceneService(SimpleNamespace(config=SimpleNamespace(base_library_path=str(tmp_path))))


def test_target_isolation_and_context(author):
    story = author.create_story({"title": "Fresh story"})["id"]
    scene = author.create_scene(story, {"title": "Meeting", "camera": "High camera"})["id"]
    a = author.save_element(story, scene, {"name": "A"})
    b = author.save_element(story, scene, {"name": "B"})
    first = author.create_target(story, scene, {"title": "First", "element_ids": [a["id"]]})
    second = author.create_target(story, scene, {"title": "Second", "element_ids": [b["id"]], "visual_overrides": {"camera": "Low camera"}})
    detail = author.target(story, scene, first["id"])
    assert [item["name"] for item in detail["elements"]] == ["A"]
    assert detail["context"]["camera"] == "High camera"
    assert author.target(story, scene, second["id"])["context"]["camera"] == "Low camera"
    author.delete_element(story, scene, a["id"])
    assert author.target(story, scene, first["id"])["elements"] == []


def test_new_backdrop_and_crud(author):
    story = author.create_story({"title": "Story"})["id"]
    scene = author.create_scene(story, {"title": "Scene"})["id"]
    backdrop = author.create_target(story, scene, {"title": "Forest", "kind": "backdrop"})
    assert (backdrop["width"], backdrop["height"]) == (1344, 768)
    assert backdrop["element_ids"] == []
    author.update_target(story, scene, backdrop["id"], {"narrative": "Tall trees"})
    assert author.target(story, scene, backdrop["id"])["narrative"] == "Tall trees"
    author.delete(story, scene, backdrop["id"])
    assert author.scene(story, scene)["targets"] == []
    author.delete(story, scene)
    assert author.story(story)["scenes"] == []
    author.delete(story)
    assert author.stories() == []


def test_invalid_new_target_does_not_create_partial_records(author):
    story = author.create_story({"title": "Story"})["id"]
    scene = author.create_scene(story, {"title": "Scene"})["id"]
    with pytest.raises(ValueError):
        author.create_target(story, scene, {"title": "Invalid", "width": 777})
    assert author.scene(story, scene)["targets"] == []
    assert list(author.repository.folder(story, scene).glob("*/target.json")) == []


def test_target_summaries_put_backdrops_first_without_changing_saved_order(author):
    story = author.create_story({"title": "Story"})["id"]
    scene = author.create_scene(story, {"title": "Scene"})["id"]
    created = [author.create_target(story, scene, {"title": name, "kind": kind})["id"]
               for name, kind in (("First", "subscene"), ("Sky", "backdrop"), ("Second", "subscene"), ("Courtyard", "backdrop"))]
    summaries = author.list_targets(story, scene)
    assert [item["id"] for item in summaries] == [created[1], created[3], created[0], created[2]]
    assert author.scene(story, scene)["targets"] == summaries
    assert author.repository.read(story, scene)["target_ids"] == created
    assert all(set(item) == {"id", "title", "kind", "selected_id"} for item in summaries)
