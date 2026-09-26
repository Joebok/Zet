import json
from pathlib import Path
import shutil
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


    def test_unsupported_manifest_version_is_rejected(self) -> None:
        with self.assertRaisesRegex(UnsupportedAIProxyProtocolVersion, "Unsupported ask_manifest.json version 2"):
            AIProxyAskManifest.from_dict({"version": 2, "ask_id": "Ask_1"})
        with self.assertRaisesRegex(UnsupportedAIProxyProtocolVersion, "version '1'"):
            AIProxyAskManifest.from_dict({"version": "1", "ask_id": "Ask_1"})


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

    def test_harvested_archive_root_uses_configured_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = self._config(root)
            external_archive = root / "ExternalArchive" / "Harvested"
            config = Config(**{**config.__dict__, "ai_harvest_archive_path": str(external_archive)})
            service = AIProxyPathService(config)

            self.assertEqual(external_archive, service.harvested_archive_root())

    def test_archive_move_retries_after_drive_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Queue" / "Answer" / "Ask_1"
            source.mkdir(parents=True)
            (source / "answer.txt").write_text("answer", encoding="utf-8")
            archive = root / "ExternalArchive"
            config = Config(**{**self._config(root).__dict__, "ai_harvest_archive_path": str(archive)})
            service = AIProxyPathService(config)
            real_move = shutil.move
            move_attempts = 0

            def fail_once_then_move(source_path, destination_path):
                nonlocal move_attempts
                move_attempts += 1
                if move_attempts == 1:
                    raise OSError("drive is waking")
                return real_move(source_path, destination_path)

            with patch(
                "zet.services.ai_proxy_path_service.shutil.move",
                side_effect=fail_once_then_move,
            ) as move, patch("zet.services.ai_proxy_path_service.time.sleep") as sleep:
                archived = service.archive_harvested_answer(source)

            self.assertTrue((archived / "answer.txt").is_file())
            self.assertFalse(source.exists())
            self.assertEqual(2, move.call_count)
            sleep.assert_called_once_with(2)

    def test_archive_move_reports_error_after_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "Answer" / "Ask_1"
            source.mkdir(parents=True)
            config = Config(**{**self._config(root).__dict__, "ai_harvest_archive_path": str(root / "Archive")})
            service = AIProxyPathService(config)

            with patch(
                "zet.services.ai_proxy_path_service.shutil.move",
                side_effect=OSError("drive is unavailable"),
            ) as move, patch("zet.services.ai_proxy_path_service.time.sleep") as sleep:
                with self.assertRaisesRegex(OSError, "drive is unavailable"):
                    service.archive_harvested_answer(source)

            self.assertEqual(2, move.call_count)
            sleep.assert_called_once_with(2)


    def test_proxy_workers_reject_unsupported_ask_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "ask_manifest.json"
            path.write_text(json.dumps({"version": 2}), encoding="utf-8")

            for reader in (ollama_proxy_worker.read_ask_manifest, local_image_proxy_worker.read_ask_manifest):
                with self.subTest(reader=reader.__module__):
                    with self.assertRaisesRegex(UnsupportedAIProxyProtocolVersion, "version 2"):
                        reader(path)



if __name__ == "__main__":
    unittest.main()
