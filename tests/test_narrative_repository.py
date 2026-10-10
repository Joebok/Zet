from dataclasses import asdict

import pytest

from zet.models.narrative import NarrativeScene, NarrativeStory, NarrativeTarget
from zet.repositories.narrative_repository import NarrativeRepository


def test_independent_records_roundtrip(tmp_path):
    repo = NarrativeRepository(tmp_path)
    story, scene = NarrativeStory("Fresh"), NarrativeScene("Meeting")
    target = NarrativeTarget("Exchange", "subscene")
    with repo.lock():
        repo.write(story, story.id)
        repo.write(scene, story.id, scene.id)
        repo.write(target, story.id, scene.id, target.id)
    assert repo.read(story.id, scene.id, target.id) == asdict(target)
    assert repo.stories() == [asdict(story)]
    assert not (tmp_path / "Stories").exists()
    assert not (tmp_path / "Pipelines").exists()
    repo.delete(story.id, scene.id, target.id)
    with pytest.raises(KeyError):
        repo.read(story.id, scene.id, target.id)


def test_record_paths_reject_escape(tmp_path):
    repo = NarrativeRepository(tmp_path)
    for value in ("../other", "C:/other", "", "not-an-id"):
        if value:
            with pytest.raises(ValueError):
                repo.folder(value)
