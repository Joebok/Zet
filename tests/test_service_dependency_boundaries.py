import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from zet.models.asset import Asset
from zet.models.worker import WorkerResult
from zet.services.prompt_artifact_service import PromptArtifactContext
from zet.services.prompt_review_service import PromptReviewService
from zet.services.worker_service import WorkerService


class WorkerServiceBoundaryTests(unittest.TestCase):
    def test_run_named_worker_builds_context_and_invokes_worker(self):
        asset = Asset(1, "Test", "Adult", "Body-Reference", "Front")
        context = object()
        run = Mock(return_value=WorkerResult(success=True, message="done"))
        service = WorkerService(Mock(), Mock(), Mock())

        with (
            patch.object(service, "_build_context", return_value=context),
            patch("zet.services.worker_service.importlib.import_module", return_value=SimpleNamespace(run=run)),
        ):
            result = service.run_named_worker(asset, "example.worker")

        run.assert_called_once_with(asset, context)
        self.assertTrue(result.success)
        self.assertEqual(service.last_worker_module_name, "example.worker")

    def test_prompt_recompile_uses_public_named_worker_api(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            prompt_path = Path(temp_dir) / "Final_Image_Prompt.md"
            prompt_path.write_text("prompt\n", encoding="utf-8")
            asset = Asset(
                1,
                "Test",
                "Adult",
                "Body-Reference",
                "Front",
                pipeline_stage="RENDER",
            )
            artifacts = PromptArtifactContext(
                asset=asset,
                prompt_path=prompt_path,
                prompt_text="prompt\n",
                condensed_prompt_path=None,
                condensed_prompt_text=None,
                render_prompt_path=prompt_path,
                render_prompt_text="prompt\n",
                prompt_candidates=[prompt_path],
            )
            artifact_service = Mock()
            artifact_service.get_context.return_value = artifacts
            artifact_service.resolve_prompt_file.return_value = prompt_path
            artifact_service.prompt_file_candidates.return_value = [prompt_path]
            worker_service = Mock()
            pipeline_repository = Mock()
            pipeline_repository.get_pipeline.return_value = SimpleNamespace(
                worker_by_stage={"PROMPT": "example.prompt_worker"}
            )
            worker_service.run_named_worker.return_value = WorkerResult(success=True, message="done")
            path_service = Mock()
            path_service.config = SimpleNamespace(
                prompt_condense_enabled=False,
                prompt_condense_model="",
                base_ai_queue_path=temp_dir,
            )
            asset_repository = Mock()
            asset_repository.get_asset.return_value = asset
            service = PromptReviewService(
                asset_repository,
                pipeline_repository,
                artifact_service,
                worker_service,
                path_service,
            )

            context = service.recompile("Test", "Adult", 1)

            worker_service.run_named_worker.assert_called_once_with(asset, "example.prompt_worker")
            self.assertEqual(context.prompt_text, "prompt\n")


if __name__ == "__main__":
    unittest.main()
