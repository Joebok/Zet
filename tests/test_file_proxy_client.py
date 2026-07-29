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
                "reference_files": [{"path": str(source.resolve())}],
            }
        ),
        encoding="utf-8",
    )

    ready = client.publish(staging, "image-1", "local_image_render")

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


def test_manual_render_queue_is_outside_file_proxy(tmp_path: Path) -> None:
    from zet.services.ai_proxy_path_service import AIProxyPathService
    from zet.services.config_service import Config

    service = AIProxyPathService(
        Config(
            base_library_path=str(tmp_path),
            base_character_path=str(tmp_path / "Characters"),
            base_asset_path=str(tmp_path / "Assets"),
            base_pipeline_path=str(tmp_path / "Pipelines"),
            base_ai_queue_path=str(tmp_path / "Queue"),
        )
    )

    assert service.manual_ask_root() == tmp_path / "Queue" / "Manual_Render_Queue" / "Ask"
    assert service.ask_root() == tmp_path / "Queue" / "File_Proxy" / "Ask" / "zet"


def test_manual_render_console_stays_independent(tmp_path: Path) -> None:
    from zet.render_console.queue import RenderConsoleQueue
    from zet.services.config_service import Config

    config = Config(
        base_library_path=str(tmp_path),
        base_character_path=str(tmp_path / "Characters"),
        base_asset_path=str(tmp_path / "Assets"),
        base_pipeline_path=str(tmp_path / "Pipelines"),
        base_ai_queue_path=str(tmp_path / "Queue"),
    )
    ask = tmp_path / "Queue" / "Manual_Render_Queue" / "Ask" / "manual-1"
    ask.mkdir(parents=True)
    (ask / "ask_manifest.json").write_text(
        json.dumps(
            {
                "ask_id": "manual-1",
                "worker_type": "manual_chatgpt_render",
                "prompt_file": "prompt.md",
                "expected_output": "image.png",
            }
        ),
        encoding="utf-8",
    )
    (ask / "prompt.md").write_text("prompt", encoding="utf-8")

    queue = RenderConsoleQueue(config)
    task = queue.get_task("manual-1")
    answer = queue.write_answer_image(task, b"image")

    assert answer == tmp_path / "Queue" / "Manual_Render_Queue" / "Answer" / "manual-1"
    assert not (tmp_path / "Queue" / "File_Proxy").exists()


def test_publication_retries_dropbox_sharing_violation(tmp_path: Path) -> None:
    source = tmp_path / "staging"
    destination = tmp_path / "ready"
    source.mkdir()
    real_replace = __import__("os").replace
    attempts = 0

    def flaky_replace(src, dest):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise PermissionError(13, "sharing violation")
        real_replace(src, dest)

    with patch("zet.services.file_proxy_client.os.replace", side_effect=flaky_replace):
        FileProxyClient._replace_with_retry(source, destination, timeout_seconds=1)

    assert attempts == 3
    assert destination.is_dir()


def test_worker_localizes_generated_metadata_paths(tmp_path: Path) -> None:
    from AI_Manager.local_image_proxy_worker import localize_output_json_paths

    job = tmp_path / "Running" / "zet" / "job-1"
    reference = job / "references" / "reference.png"
    reference.parent.mkdir(parents=True)
    reference.write_bytes(b"image")
    metadata = job / "ComfyUI_Compilation_Debug.json"
    metadata.write_text(
        json.dumps({"references_used": [{"path": str(reference.resolve())}]}),
        encoding="utf-8",
    )

    localize_output_json_paths(job)

    payload = json.loads(metadata.read_text(encoding="utf-8"))
    assert payload["references_used"][0]["path"] == "references/reference.png"


def test_answer_waits_for_proxy_inventory_and_route_sync(tmp_path: Path) -> None:
    client = FileProxyClient(tmp_path)
    answer = client.answer_root / "job-1"
    answer.mkdir(parents=True)
    (answer / "job.json").write_text(
        json.dumps({"job_id": "job-1", "route_required": True}),
        encoding="utf-8",
    )
    (answer / "answer_manifest.json").write_text("{}", encoding="utf-8")
    route = client.route_root / "job-1.json"

    assert client.answer_is_ready(answer) is False

    output = answer / "output.png"
    output.write_bytes(b"image")
    (answer / "proxy_result.json").write_text(
        json.dumps({"output_files": client._file_inventory(answer)}),
        encoding="utf-8",
    )
    assert client.answer_is_ready(answer) is False

    route.parent.mkdir(parents=True)
    route.write_text("{}", encoding="utf-8")
    assert client.answer_is_ready(answer) is True

    output.write_bytes(b"partial")
    assert client.answer_is_ready(answer) is False


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
