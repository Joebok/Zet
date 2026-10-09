import json
from pathlib import Path

import pytest

from zet.services.comfyui_render_service import compile_prompt_to_comfyui_workflow
from zet.services.local_render_types import LocalRenderError


NODES = {"UNETLoader", "CLIPLoader", "VAELoader", "TextEncodeQwenImage21", "EmptyLatentImage",
         "KSampler", "VAEDecode", "SaveImage", "LoadImage"}
PROFILE = json.loads((Path(__file__).resolve().parents[1] / "Config/Local_Render_Presets.json").read_text())["comfyui-qwen-narrative"]


@pytest.mark.parametrize("count", [0, 1, 3, 10])
def test_narrative_graph_exact_prompt_and_reference_order(tmp_path, count):
    refs = []
    for i in range(count):
        path = tmp_path / f"reference_{i}.png"
        path.write_bytes(b"input")
        refs.append({"path": str(path), "label": f"Subject {i}"})
    compiled = compile_prompt_to_comfyui_workflow("Literal narrative", "", PROFILE,
        checkpoint=PROFILE["diffusion_model"], seed=42, reference_files=refs, available_node_types=NODES,
        positive_prompt_globals="MUST NOT APPEAR", negative_prompt_globals="MUST NOT APPEAR")
    encode = compiled.workflow["4"]["inputs"]
    assert encode["prompt"] == "Literal narrative"
    assert encode["negative_prompt"] == ""
    assert compiled.width == 1216 and compiled.height == 832
    assert [item["image_index"] for item in compiled.debug["references_used"]] == list(range(1, count + 1))
    assert len([node for node in compiled.workflow.values() if node["class_type"] == "LoadImage"]) == count


def test_narrative_graph_rejects_unsupported_reference_count():
    with pytest.raises(LocalRenderError, match="ten"):
        compile_prompt_to_comfyui_workflow("Prompt", "", PROFILE, checkpoint=PROFILE["diffusion_model"],
                                         reference_files=[{}] * 11, available_node_types=NODES)
