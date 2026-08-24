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



if __name__ == "__main__":
    unittest.main()
