import importlib

from zet.models.worker import WorkerContext, WorkerResult
from zet.repositories.asset_repository import AssetRepository
from zet.repositories.pipeline_repository import PipelineRepository
from zet.services.path_service import PathService


class WorkerServiceError(Exception):
    pass


class WorkerService:
    def __init__(
        self,
        asset_repository: AssetRepository,
        pipeline_repository: PipelineRepository,
        path_service: PathService,
    ):
        self.asset_repository = asset_repository
        self.pipeline_repository = pipeline_repository
        self.path_service = path_service
        self.last_worker_module_name: str | None = None
        self.last_worker_result: WorkerResult | None = None

    def _normalize_worker_name(self, worker_name: str) -> str:
        if worker_name == "workers.noop_worker":
            return "zet.workers.noop_worker"
        return worker_name

    def _build_context(self, asset) -> WorkerContext:
        return WorkerContext(
            pipeline_path=self.path_service.pipeline_path(asset),
            candidate_image_path=self.path_service.candidate_image_path(asset),
            locked_image_path=self.path_service.locked_image_path(asset),
            character_path=self.path_service.character_path(asset.character, asset.phase),
            character_asset_path=self.path_service.character_asset_path(asset.character, asset.phase),
        )

    def run_current_worker(self, character: str, phase: str, asset_id: int) -> WorkerResult:
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        pipeline = self.pipeline_repository.get_pipeline(character, phase, asset.pipeline)
        worker_name = pipeline.worker_by_stage.get(asset.pipeline_stage)
        if not worker_name:
            raise WorkerServiceError(
                f"Pipeline {pipeline.name} has no worker configured for stage {asset.pipeline_stage}"
            )

        module_name = self._normalize_worker_name(worker_name)
        context = self._build_context(asset)

        try:
            module = importlib.import_module(module_name)
        except Exception as exc:
            raise WorkerServiceError(f"Unable to import worker module {module_name}: {exc}") from exc

        run_func = getattr(module, "run", None)
        if not callable(run_func):
            raise WorkerServiceError(f"Worker module {module_name} has no callable run function")

        try:
            result = run_func(asset, context)
        except Exception as exc:
            result = WorkerResult(
                success=False,
                message=f"Worker execution failed: {exc}",
                advance_stage=False,
                error_code="WORKER_EXCEPTION",
                error_message=str(exc),
            )

        self.last_worker_module_name = module_name
        self.last_worker_result = result
        return result
