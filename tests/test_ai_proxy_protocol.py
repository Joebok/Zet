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
