import json
from pathlib import Path
import socket
from unittest.mock import patch

from zet.services.file_proxy_client import FileProxyClient


def test_atomic_publication_writes_generic_job_manifest(tmp_path: Path) -> None:
    client = FileProxyClient(tmp_path)
    staging = client.create_staging("job-1")
    (staging / "ask_manifest.json").write_text(
        json.dumps(
            {
                "ask_id": "job-1",
                "worker_type": "ollama_generate",
                "ollama_model": "vision-analysis:latest",
                "prompt_file": "prompt.md",
                "target_output_dir": str((tmp_path / "outputs").resolve()),
            }
        ),
        encoding="utf-8",
    )
    (staging / "prompt.md").write_text("hello", encoding="utf-8")

    ready = client.publish(staging, "job-1", "ollama_generate")

    assert ready == tmp_path / "File_Proxy" / "Ask" / "zet" / "job-1"
    assert not staging.exists()
    job = json.loads((ready / "job.json").read_text(encoding="utf-8"))
    assert job["subscriber_id"] == "zet"
    assert job["worker"] == "ollama"
    assert job["producer_id"] == socket.gethostname()
    assert job["resource_key"] == "ollama:vision-analysis:latest"
    assert {item["path"] for item in job["files"]} == {"ask_manifest.json", "prompt.md"}
    assert job["route_required"] is True
    ask = json.loads((ready / "ask_manifest.json").read_text(encoding="utf-8"))
    assert "target_output_dir" not in ask
    assert client.load_route("job-1")["target_output_dir"] == str((tmp_path / "outputs").resolve())


def test_reference_inputs_are_copied_inside_job(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    source.write_bytes(b"image")
    client = FileProxyClient(tmp_path / "queue")
    staging = client.create_staging("image-1")
    (staging / "ask_manifest.json").write_text(
        json.dumps(
            {
                "ask_id": "image-1",
                "worker_type": "local_image_render",
                "image_generation": "comfyui",
                "checkpoint": "portrait.safetensors",
                "reference_files": [{"path": str(source.resolve())}],
            }
        ),
        encoding="utf-8",
    )

    ready = client.publish(staging, "image-1", "local_image_render")

    job = json.loads((ready / "job.json").read_text(encoding="utf-8"))
    assert job["resource_key"] == "image:comfyui:portrait.safetensors"
    manifest = json.loads((ready / "ask_manifest.json").read_text(encoding="utf-8"))
    assert manifest["reference_files"][0]["path"] == "references/source.png"
    assert (ready / "references" / "source.png").read_bytes() == b"image"






def test_nested_scene_ir_paths_are_localized(tmp_path: Path) -> None:
    scene = tmp_path / "scene.json"
    settings = tmp_path / "story.json"
    nested = tmp_path / "nested.json"
    reference = tmp_path / "reference.png"
    nested.write_text("{}", encoding="utf-8")
    scene.write_text(json.dumps({"nested_path": str(nested.resolve())}), encoding="utf-8")
    settings.write_text("{}", encoding="utf-8")
    reference.write_bytes(b"image")
    client = FileProxyClient(tmp_path / "queue")
    staging = client.create_staging("scene-1")
    (staging / "ask_manifest.json").write_text(
        json.dumps(
            {
                "ask_id": "scene-1",
                "worker_type": "local_image_render",
                "reference_files": [{"tag": "hero", "path": str(reference.resolve())}],
            }
        ),
        encoding="utf-8",
    )
    (staging / "Scene_Render_IR.json").write_text(
        json.dumps(
            {
                "source": {
                    "scene_json_path": str(scene.resolve()),
                    "story_settings_path": str(settings.resolve()),
                },
                "resolved_sources": {
                    "references": [{"tag": "hero", "path": str(reference.resolve())}]
                },
            }
        ),
        encoding="utf-8",
    )

    ready = client.publish(staging, "scene-1", "local_image_render")

    ir = json.loads((ready / "Scene_Render_IR.json").read_text(encoding="utf-8"))
    assert ir["source"]["scene_json_path"] == "inputs/scene.json"
    assert ir["source"]["story_settings_path"] == "inputs/story.json"
    assert ir["resolved_sources"]["references"][0]["path"] == "references/reference.png"
    assert (ready / "inputs" / "scene.json").is_file()
    assert (ready / "inputs" / "story.json").is_file()
    localized_scene = json.loads((ready / "inputs" / "scene.json").read_text(encoding="utf-8"))
    assert localized_scene["nested_path"] == "inputs/nested.json"
    assert (ready / "inputs" / "nested.json").is_file()












def test_answer_is_only_harvested_on_its_producer_machine(tmp_path: Path) -> None:
    client = FileProxyClient(tmp_path)
    answer = client.answer_root / "job-1"
    answer.mkdir(parents=True)
    (answer / "job.json").write_text(
        json.dumps({"job_id": "job-1", "producer_id": f"other-than-{socket.gethostname()}"}),
        encoding="utf-8",
    )
    (answer / "proxy_result.json").write_text(
        json.dumps({"output_files": client._file_inventory(answer)}),
        encoding="utf-8",
    )

    assert client.answer_is_ready(answer) is False
