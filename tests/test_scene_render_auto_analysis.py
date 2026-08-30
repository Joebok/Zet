from types import SimpleNamespace
from unittest.mock import Mock

from zet.app import ZetApp


def test_stage_scene_render_auto_queues_analysis_for_selected_target():
    app = ZetApp.__new__(ZetApp)
    app.config = SimpleNamespace(ai_prompt_analysis_auto_queue_on_render=True)
    app.story_service = Mock()
    app.scene_prompt_analysis_service = Mock()
    task = object()
    app.story_service.stage_scene_render.return_value = task

    result = app.stage_scene_render("Story", "Scene", "background")

    assert result is task
    app.story_service.stage_scene_render.assert_called_once_with("Story", "Scene", "background", False)
    app.scene_prompt_analysis_service.queue.assert_called_once_with("Story", "Scene", "background")


def test_stage_scene_render_does_not_auto_queue_analysis_when_disabled():
    app = ZetApp.__new__(ZetApp)
    app.config = SimpleNamespace(ai_prompt_analysis_auto_queue_on_render=False)
    app.story_service = Mock()
    app.scene_prompt_analysis_service = Mock()
    app.story_service.stage_scene_render.return_value = object()

    app.stage_scene_render("Story", "Scene")

    app.scene_prompt_analysis_service.queue.assert_not_called()
