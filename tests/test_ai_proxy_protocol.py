import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from AI_Manager import local_image_proxy_worker, ollama_proxy_worker
from zet.models.ai_proxy import AIProxyAskManifest, UnsupportedAIProxyProtocolVersion
from zet.models.reference import ReferenceFile, UnsupportedReferenceFileProtocolVersion, reference_files_payload
from zet.render_console.queue import RenderConsoleQueue
from zet.services.ai_proxy_path_service import AIProxyPathService
from zet.services.config_service import Config


class AIProxyProtocolTests(unittest.TestCase):
    def _config(self, root: Path) -> Config:
        return Config(
            base_library_path=str(root),
            base_character_path=str(root / "Characters"),
            base_asset_path=str(root / "Assets"),
            base_pipeline_path=str(root / "Pipelines"),
            base_ai_queue_path=str(root / "Queue"),
        )

    def test_versionless_manifest_is_legacy_v1_and_preserves_unknown_fields(self) -> None:
        manifest = AIProxyAskManifest.from_dict({"ask_id": "Ask_1", "future_optional": {"value": 1}})

        self.assertEqual(1, manifest.version)
        self.assertEqual({"value": 1}, manifest.get("future_optional"))
        self.assertNotIn("version", manifest.to_dict())

    def test_unsupported_manifest_version_is_rejected(self) -> None:
        with self.assertRaisesRegex(UnsupportedAIProxyProtocolVersion, "Unsupported ask_manifest.json version 2"):
            AIProxyAskManifest.from_dict({"version": 2, "ask_id": "Ask_1"})
        with self.assertRaisesRegex(UnsupportedAIProxyProtocolVersion, "version '1'"):
            AIProxyAskManifest.from_dict({"version": "1", "ask_id": "Ask_1"})

    def test_reference_record_reader_accepts_legacy_and_writer_emits_protocol_fields(self) -> None:
        payload = {"role": "body_reference", "path": "ref.png", "future_optional": True}

        reference = ReferenceFile.from_dict(payload)

        self.assertEqual(1, reference.version)
        self.assertEqual("reference_file", reference.record_type)
        self.assertEqual(
            {**payload, "version": 1, "type": "reference_file"},
            reference.to_dict(),
        )
        self.assertEqual([reference.to_dict()], reference_files_payload([payload]))

    def test_ask_manifest_rejects_unsupported_nested_reference_version(self) -> None:
        with self.assertRaisesRegex(UnsupportedReferenceFileProtocolVersion, "reference file version 2"):
            AIProxyAskManifest.from_dict(
                {"version": 1, "reference_files": [{"version": 2, "type": "reference_file", "path": "ref.png"}]}
            )

    def test_task_paths_use_flat_subscriber_states(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = AIProxyPathService(self._config(root))
            ask = service.ask_root() / "Ask_1"
            running = service.running_root() / "Ask_2"
            for path in (ask, running):
                path.mkdir(parents=True)

            self.assertEqual(
                {ask, running},
                set(service.task_paths("ask", "running")),
            )

    def test_render_console_rejects_unsupported_ask_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            queue = RenderConsoleQueue(self._config(root))
            ask = queue.ask_root / "Ask_1"
            ask.mkdir(parents=True)
            (ask / "ask_manifest.json").write_text(
                json.dumps({"version": 2, "worker_type": "manual_chatgpt_render"}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(UnsupportedAIProxyProtocolVersion, "version 2"):
                queue.list_tasks()

    def test_proxy_workers_reject_unsupported_ask_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "ask_manifest.json"
            path.write_text(json.dumps({"version": 2}), encoding="utf-8")

            for reader in (ollama_proxy_worker.read_ask_manifest, local_image_proxy_worker.read_ask_manifest):
                with self.subTest(reader=reader.__module__):
                    with self.assertRaisesRegex(UnsupportedAIProxyProtocolVersion, "version 2"):
                        reader(path)

    def test_proxy_workers_retry_dropbox_write_locks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            real_replace = __import__("os").replace

            for worker in (ollama_proxy_worker, local_image_proxy_worker):
                with self.subTest(worker=worker.__name__):
                    path = root / worker.__name__ / "answer_manifest.json"
                    attempts = 0

                    def flaky_replace(source, destination):
                        nonlocal attempts
                        attempts += 1
                        if attempts < 3:
                            raise PermissionError(13, "Dropbox sharing violation")
                        real_replace(source, destination)

                    with patch("zet.services.atomic_file_service.os.replace", side_effect=flaky_replace):
                        worker.write_json(path, {"status": "SUCCESS"})

                    self.assertEqual(3, attempts)
                    self.assertEqual({"status": "SUCCESS"}, json.loads(path.read_text(encoding="utf-8")))
                    self.assertEqual([], list(path.parent.glob(".*.tmp.*")))


if __name__ == "__main__":
    unittest.main()
