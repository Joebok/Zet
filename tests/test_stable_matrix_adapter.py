from pathlib import Path
from unittest.mock import patch

import pytest

from Scripts.Local_Render_Adapters.stable_matrix_adapter import render_preview
from zet.services.local_render_types import LocalRenderError


@pytest.mark.parametrize("profile", ["body-reference-preview", "scene-preview-sd15"])
def test_retired_stability_matrix_adapter_never_submits(tmp_path, profile):
    with patch("Scripts.Local_Render_Adapters.stable_matrix_adapter._post_json") as submit:
        with pytest.raises(LocalRenderError, match="retired"):
            render_preview(project_root=tmp_path, final_prompt_path=Path("unused.md"),
                           job_output_dir=tmp_path, preset_name=profile)
        submit.assert_not_called()
