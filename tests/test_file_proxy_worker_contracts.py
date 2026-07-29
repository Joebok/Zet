import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from AI_Manager import local_image_proxy_worker


@pytest.mark.parametrize(
    ("backend", "artifact_name", "artifact_payload"),
    [
        (
            "stable_matrix",
            "Stable_Matrix_API_Call.json",
            {"api_path": "/sdapi/v1/txt2img"},
        ),
        (
            "comfyui",
            "ComfyUI_Compilation_Debug.json",
            {"workflow_kind": "ipadapter_scene_preview"},
        ),
    ],
)
def test_local_image_worker_outputs_remain_proxy_safe(
    tmp_path: Path,
    backend: str,
    artifact_name: str,
    artifact_payload: dict,
) -> None:
    job = tmp_path / "Running" / "zet" / f"{backend}-job"
    job.mkdir(parents=True)
    prompt = job / "prompt.md"
    prompt.write_text("prompt: test\nnegative: bad\n", encoding="utf-8")
    reference = job / "references" / "reference.png"
    reference.parent.mkdir()
    reference.write_bytes(b"reference")
    ask = {
        "version": 1,
        "ask_id": job.name,
        "worker_type": "local_image_render",
        "prompt_file": prompt.name,
        "expected_output": "result.png",
        "render_preset": "test",
        "image_generation": backend,
        "reference_files": [{"path": "references/reference.png"}],
    }
    (job / "ask_manifest.json").write_text(json.dumps(ask), encoding="utf-8")

    generated = job / "backend" / "generated.png"
    generated.parent.mkdir()
    generated.write_bytes(b"image")
    metadata = generated.parent / "metadata.json"
    metadata.write_text(
        json.dumps({"backend": backend, "final_prompt": str(prompt.resolve())}),
        encoding="utf-8",
    )
    artifact = generated.parent / artifact_name
    artifact_payload = dict(artifact_payload)
    artifact_payload["reference_path"] = str(reference.resolve())
    artifact.write_text(json.dumps(artifact_payload), encoding="utf-8")
    result = SimpleNamespace(
        image_path=generated,
        metadata_path=metadata,
        artifact_paths=[artifact],
        prompt_id="test-prompt",
    )

    with patch.object(local_image_proxy_worker, "render_image", return_value=result):
        status = local_image_proxy_worker.process_claimed(
            job,
            {"answer": job.parent, "ask": job.parent, "failed": job.parent},
            "test-worker",
            return_transient_to_ask=False,
            move_answer=False,
        )

    assert status == "SUCCESS"
    assert (job / "result.png").read_bytes() == b"image"
    assert json.loads((job / "answer_manifest.json").read_text())["status"] == "SUCCESS"
    localized_artifact = json.loads((job / artifact_name).read_text())
    assert localized_artifact["reference_path"] == "references/reference.png"
    if backend == "stable_matrix":
        assert localized_artifact["api_path"] == "/sdapi/v1/txt2img"


def test_ollama_and_local_image_are_the_only_registered_proxy_workers(tmp_path: Path) -> None:
    from zet.services.file_proxy_client import FileProxyClient

    client = FileProxyClient(tmp_path)

    assert client.worker_names == {
        "ollama_generate": "ollama",
        "local_image_render": "local_image",
    }
