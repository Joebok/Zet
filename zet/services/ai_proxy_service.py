import json
import shutil
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from zet.models.ai_proxy import AIProxyAsk, MonitorTestResult
from zet.repositories.asset_repository import AssetRepository
from zet.repositories.pipeline_repository import PipelineRepository
from zet.services.ai_proxy_path_service import AIProxyPathService
from zet.services.housekeeping_service import HousekeepingService
from zet.services.path_service import PathService


class AIProxyServiceError(Exception):
    pass


class AIProxyService:
    def __init__(
        self,
        asset_repository: AssetRepository,
        pipeline_repository: PipelineRepository,
        path_service: PathService,
        ai_proxy_path_service: AIProxyPathService,
        housekeeping_service: HousekeepingService,
    ):
        self.asset_repository = asset_repository
        self.pipeline_repository = pipeline_repository
        self.path_service = path_service
        self.ai_proxy_path_service = ai_proxy_path_service
        self.housekeeping_service = housekeeping_service
        self.prompt_review_service = None

    def _timestamp(self) -> str:
        return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    def _timestamp_compact(self) -> str:
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def _safe_head_view(self, head_view: str | None) -> str:
        return head_view if head_view and head_view.strip() else "_"

    def _render_backend(self) -> str:
        return str(getattr(self.path_service.config, "render_backend", "local_image")).strip().lower()

    def _read_json_if_exists(self, path: Path) -> dict:
        if not path.exists() or not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def _write_text_atomic(self, path: Path, contents: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_name(f"{path.name}.tmp")
        try:
            temp_path.write_text(contents, encoding="utf-8")
            temp_path.replace(path)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    def _write_json_atomic(self, path: Path, payload: dict) -> None:
        contents = json.dumps(payload, indent=2) + "\n"
        self._write_text_atomic(path, contents)

    def clear_asset_queue_items(self, asset) -> int:
        self._ensure_queue_dirs()
        removed = 0
        asset_prefix = f"Ask_Asset_{asset.asset_id}_"

        def remove_path(path: Path) -> None:
            nonlocal removed
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
                removed += 1
            elif path.exists():
                path.unlink(missing_ok=True)
                removed += 1

        roots = [
            self.ai_proxy_path_service.ask_root(),
            self.ai_proxy_path_service.answer_root(),
        ]

        for root in roots:
            if not root.exists():
                continue
            for item in root.iterdir():
                if not item.is_dir():
                    continue
                manifest = self._read_json_if_exists(item / "ask_manifest.json")
                if manifest.get("asset_id") == asset.asset_id or item.name.startswith(asset_prefix):
                    remove_path(item)

        for parent in (self.ai_proxy_path_service.claimed_root(), self.ai_proxy_path_service.failed_root()):
            if not parent.exists():
                continue
            for worker_dir in parent.iterdir():
                if not worker_dir.is_dir():
                    continue
                for item in worker_dir.iterdir():
                    manifest = self._read_json_if_exists(item / "ask_manifest.json") if item.is_dir() else {}
                    if manifest.get("asset_id") == asset.asset_id or item.name.startswith(asset_prefix):
                        remove_path(item)

        claims_root = self.ai_proxy_path_service.claims_root()
        if claims_root.exists():
            for claim_path in claims_root.glob(f"{asset_prefix}*.claim.json"):
                remove_path(claim_path)

        return removed

    def _clear_monitor_state(self) -> None:
        request_root = self.ai_proxy_path_service.monitor_requests_root()
        if request_root.exists():
            for path in request_root.iterdir():
                if path.is_dir():
                    shutil.rmtree(path, ignore_errors=True)
                else:
                    path.unlink(missing_ok=True)

        response_root = self.ai_proxy_path_service.monitor_responses_root()
        if not response_root.exists():
            return
        for worker_dir in response_root.iterdir():
            if worker_dir.is_dir():
                for response_path in worker_dir.iterdir():
                    if response_path.is_dir():
                        shutil.rmtree(response_path, ignore_errors=True)
                    else:
                        response_path.unlink(missing_ok=True)
            else:
                worker_dir.unlink(missing_ok=True)

    def _build_manual_render_ask(self, asset, ask_id: str, attempt_id: str) -> AIProxyAsk:
        """Build a manual ChatGPT render ask for the render console."""
        return AIProxyAsk(
            ask_id=ask_id,
            asset_id=asset.asset_id,
            character=asset.character,
            phase=asset.phase,
            pipeline=asset.pipeline,
            pipeline_stage=asset.pipeline_stage,
            ollama_attempt_id=attempt_id,
            worker_type="manual_chatgpt_render",
            ollama_model="",
            prompt_file="Final_Image_Prompt.md",
            expected_output=asset.final_image_output,
            candidate_output_file=asset.final_image_output,
            task_type="render",
            render_preset="chatgpt-manual",
            manual=True,
            reference_files=asset.reference_files or [],
        )

    def _build_ask(self, asset, force_manual_render: bool = False) -> AIProxyAsk:
        """Build the queue ask appropriate for an asset's current pipeline stage."""
        stamp = self._timestamp_compact()
        ask_id = f"Ask_Asset_{asset.asset_id}_{asset.pipeline_stage}_{stamp}"
        attempt_id = f"{stamp}_{asset.asset_id}_{asset.pipeline_stage}"
        if force_manual_render and asset.pipeline_stage == "RENDER":
            return self._build_manual_render_ask(asset, ask_id, attempt_id)
        if asset.pipeline == "Body-Reference" and asset.pipeline_stage == "RENDER":
            render_backend = self._render_backend()
            if render_backend == "manual_chatgpt":
                return self._build_manual_render_ask(asset, ask_id, attempt_id)
            prompt_file = "Final_Image_Prompt.md"
            if self.prompt_review_service is not None:
                context = self.prompt_review_service.get_context(asset.character, asset.phase, asset.asset_id)
                if context.condensed_prompt_path is not None:
                    prompt_file = "Condensed_Image_Prompt.md"
            return AIProxyAsk(
                ask_id=ask_id,
                asset_id=asset.asset_id,
                character=asset.character,
                phase=asset.phase,
                pipeline=asset.pipeline,
                pipeline_stage=asset.pipeline_stage,
                ollama_attempt_id=attempt_id,
                worker_type="local_image_render",
                ollama_model="",
                prompt_file=prompt_file,
                expected_output=asset.final_image_output,
                candidate_output_file=asset.final_image_output,
                task_type="render",
                render_preset=self._local_render_preset(),
            )
        if asset.pipeline == "Head-Fitment" and asset.pipeline_stage == "RENDER":
            return self._build_manual_render_ask(asset, ask_id, attempt_id)
        if asset.pipeline == "Character-Assembly" and asset.pipeline_stage == "RENDER":
            return self._build_manual_render_ask(asset, ask_id, attempt_id)
        if asset.pipeline == "Costume-Dressing" and asset.pipeline_stage == "RENDER":
            return self._build_manual_render_ask(asset, ask_id, attempt_id)
        if asset.pipeline == "Expression" and asset.pipeline_stage == "RENDER":
            return self._build_manual_render_ask(asset, ask_id, attempt_id)
        return AIProxyAsk(
            ask_id=ask_id,
            asset_id=asset.asset_id,
            character=asset.character,
            phase=asset.phase,
            pipeline=asset.pipeline,
            pipeline_stage=asset.pipeline_stage,
            ollama_attempt_id=attempt_id,
            worker_type="ollama_generate",
            ollama_model="llama3.2:3b",
            prompt_file="OLLAMA_PROMPT.md",
            expected_output="OLLAMA_RESPONSE.md",
            candidate_output_file=asset.final_image_output,
            task_type="generate",
        )

    def _ensure_queue_dirs(self) -> None:
        paths = self.ai_proxy_path_service.all_paths()
        for path in (
            paths.proxy_root,
            paths.ask_root,
            paths.claims_root,
            paths.claimed_root,
            paths.answer_root,
            paths.failed_root,
            paths.control_root,
            paths.monitor_root,
            paths.monitor_requests_root,
            paths.monitor_responses_root,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def _manifest_payload(self, ask: AIProxyAsk) -> dict:
        return {
            "version": 1,
            "ask_id": ask.ask_id,
            "asset_id": ask.asset_id,
            "character": ask.character,
            "phase": ask.phase,
            "pipeline": ask.pipeline,
            "pipeline_stage": ask.pipeline_stage,
            "ollama_attempt_id": ask.ollama_attempt_id,
            "worker_type": ask.worker_type,
            "ollama_model": ask.ollama_model,
            "prompt_file": ask.prompt_file,
            "expected_output": ask.expected_output,
            "candidate_output_file": ask.candidate_output_file,
            "task_type": ask.task_type,
            "auxiliary": ask.auxiliary,
            "manual": ask.manual,
            "target_output_file": ask.target_output_file,
            "render_preset": ask.render_preset,
            "reference_files": ask.reference_files,
        }

    def _prompt_contents(self, asset, force_manual_render: bool = False) -> str:
        """Read the prompt text that should be copied into a queued ask."""
        if asset.pipeline == "Body-Reference" and asset.pipeline_stage == "RENDER":
            if self.prompt_review_service is None:
                raise AIProxyServiceError("Prompt review service is required to stage body-reference render asks.")
            context = self.prompt_review_service.get_context(asset.character, asset.phase, asset.asset_id)
            if force_manual_render or self._render_backend() == "manual_chatgpt":
                if not context.prompt_text:
                    raise AIProxyServiceError(f"No Final_Image_Prompt.md found for Asset {asset.asset_id}.")
                return context.prompt_text
            if not context.render_prompt_text:
                raise AIProxyServiceError(f"No render prompt found for Asset {asset.asset_id}.")
            return context.render_prompt_text

        if asset.pipeline == "Head-Fitment" and asset.pipeline_stage == "RENDER":
            prompt_path = self.path_service.pipeline_path(asset) / "Final_Image_Prompt.md"
            if not prompt_path.exists():
                raise AIProxyServiceError(f"No Final_Image_Prompt.md found for Asset {asset.asset_id}.")
            return prompt_path.read_text(encoding="utf-8")

        if asset.pipeline == "Character-Assembly" and asset.pipeline_stage == "RENDER":
            prompt_path = self.path_service.pipeline_path(asset) / "Final_Image_Prompt.md"
            if not prompt_path.exists():
                raise AIProxyServiceError(f"No Final_Image_Prompt.md found for Asset {asset.asset_id}.")
            return prompt_path.read_text(encoding="utf-8")

        if asset.pipeline == "Costume-Dressing" and asset.pipeline_stage == "RENDER":
            prompt_path = self.path_service.pipeline_path(asset) / "Final_Image_Prompt.md"
            if not prompt_path.exists():
                raise AIProxyServiceError(f"No Final_Image_Prompt.md found for Asset {asset.asset_id}.")
            return prompt_path.read_text(encoding="utf-8")

        if asset.pipeline == "Expression" and asset.pipeline_stage == "RENDER":
            prompt_path = self.path_service.pipeline_path(asset) / "Final_Image_Prompt.md"
            if not prompt_path.exists():
                raise AIProxyServiceError(f"No Final_Image_Prompt.md found for Asset {asset.asset_id}.")
            return prompt_path.read_text(encoding="utf-8")

        head_view = self._safe_head_view(asset.head_view)
        return (
            "# Zet Ollama Prompt\n\n"
            f"AssetID: {asset.asset_id}\n"
            f"Character: {asset.character}\n"
            f"Phase: {asset.phase}\n"
            f"Pipeline: {asset.pipeline}\n"
            f"PipelineStage: {asset.pipeline_stage}\n"
            f"BodyView: {asset.body_view}\n"
            f"HeadView: {head_view}\n"
            f"FinalImageOutput: {asset.final_image_output}\n\n"
            "This is a staged placeholder prompt for Zet AI proxy testing.\n"
        )

    def stage_current_ai_ask(self, character: str, phase: str, asset_id: int, force_manual_render: bool = False) -> Path:
        """Write an AI queue ask for the asset's current AI_AGENT stage."""
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        if asset.actor != "AI_AGENT":
            raise AIProxyServiceError("AI ask staging is only available when Actor is AI_AGENT.")
        if not asset.final_image_output:
            raise AIProxyServiceError(f"Asset {asset.asset_id} is missing final_image_output.")

        self.pipeline_repository.get_pipeline(character, phase, asset.pipeline)
        ask = self._build_ask(asset, force_manual_render=force_manual_render)
        self._ensure_queue_dirs()

        ask_path = self.ai_proxy_path_service.ask_path(ask.ask_id)
        ask_path.mkdir(parents=True, exist_ok=False)

        manifest_path = ask_path / "ask_manifest.json"
        self._write_json_atomic(manifest_path, self._manifest_payload(ask))
        json.loads(manifest_path.read_text(encoding="utf-8"))

        prompt_path = ask_path / ask.prompt_file
        self._write_text_atomic(prompt_path, self._prompt_contents(asset, force_manual_render=force_manual_render))

        updated_asset = replace(asset)
        updated_asset.ai_state = "ASKED"
        updated_asset.last_ai_update = f"AI ask staged: {ask.ask_id} ({ask.ollama_attempt_id})"
        updated_asset.updated_at = self._timestamp()

        self.asset_repository.save_asset(updated_asset)
        self.housekeeping_service.prepare_stage(updated_asset)
        return ask_path

    def _prompt_condense_enabled(self) -> bool:
        return bool(getattr(self.path_service.config, "prompt_condense_enabled", False))

    def _local_render_auto_queue_after_condense_enabled(self) -> bool:
        return bool(getattr(self.path_service.config, "local_render_auto_queue_after_condense", False))

    def _local_render_preset(self) -> str:
        return str(getattr(self.path_service.config, "local_render_preset", "body-reference-preview"))

    def _prompt_condense_model(self) -> str:
        return str(getattr(self.path_service.config, "prompt_condense_model", "llama3.2-vision:11b"))

    def _prompt_condense_file(self) -> Path:
        configured_path = Path(str(getattr(
            self.path_service.config,
            "prompt_condense_file",
            "Config/Prompt_Condense_Tasks/body_reference_condense.md",
        )))
        if configured_path.is_absolute():
            return configured_path
        return Path(__file__).resolve().parents[2] / configured_path

    def _prompt_condense_contents(self, asset, final_prompt: str) -> str:
        return self._prompt_condense_contents_from_values(
            final_prompt=final_prompt,
            values={
                "ASSET_ID": str(asset.asset_id),
                "CHARACTER": str(asset.character),
                "PHASE": str(asset.phase),
                "PIPELINE": str(asset.pipeline),
                "BODY_VIEW": str(asset.body_view),
                "HEAD_VIEW": self._safe_head_view(asset.head_view),
                "FINAL_IMAGE_OUTPUT": str(asset.final_image_output or ""),
            },
        )

    def _prompt_condense_contents_from_values(self, final_prompt: str, values: dict[str, str]) -> str:
        prompt_template_path = self._prompt_condense_file()
        if not prompt_template_path.exists():
            raise AIProxyServiceError(f"Prompt condense template not found: {prompt_template_path}")
        contents = prompt_template_path.read_text(encoding="utf-8")
        replacements = {
            "ASSET_ID": "",
            "CHARACTER": "",
            "PHASE": "",
            "PIPELINE": "",
            "BODY_VIEW": "",
            "HEAD_VIEW": "",
            "FINAL_IMAGE_OUTPUT": "",
            "FINAL_IMAGE_PROMPT": final_prompt.strip(),
        }
        replacements.update(values)
        for key, value in replacements.items():
            contents = contents.replace("{{" + key + "}}", value)
        return contents.strip() + "\n"

    def _has_pending_prompt_condense_ask(self, asset) -> bool:
        return self._has_pending_auxiliary_task(asset, "prompt_condense")

    def _clear_pending_prompt_condense_ask(self, asset) -> None:
        self._clear_pending_auxiliary_task(asset, "prompt_condense")

    def _clear_pending_auxiliary_task(self, asset, task_type: str) -> None:
        for root in [self.ai_proxy_path_service.ask_root(), self.ai_proxy_path_service.answer_root()]:
            if not root.exists():
                continue
            for ask_path in root.iterdir():
                if not ask_path.is_dir():
                    continue
                manifest = self._read_json_if_exists(ask_path / "ask_manifest.json")
                if (ask_path / "harvest_manifest.json").exists():
                    continue
                if (
                    manifest.get("asset_id") == asset.asset_id
                    and manifest.get("task_type") == task_type
                    and manifest.get("auxiliary") is True
                ):
                    shutil.rmtree(ask_path, ignore_errors=True)

    def _has_pending_auxiliary_task(self, asset, task_type: str) -> bool:
        roots = [self.ai_proxy_path_service.ask_root()]
        claimed_root = self.ai_proxy_path_service.claimed_root()
        if claimed_root.exists():
            roots.extend(path for path in claimed_root.iterdir() if path.is_dir())
        answer_root = self.ai_proxy_path_service.answer_root()
        if answer_root.exists():
            roots.append(answer_root)
        for root in roots:
            if not root.exists():
                continue
            for ask_path in root.iterdir():
                if not ask_path.is_dir():
                    continue
                manifest = self._read_json_if_exists(ask_path / "ask_manifest.json")
                if (ask_path / "harvest_manifest.json").exists():
                    continue
                if (
                    manifest.get("asset_id") == asset.asset_id
                    and manifest.get("task_type") == task_type
                    and manifest.get("auxiliary") is True
                ):
                    return True
        return False

    def stage_prompt_condense_ask_if_enabled(self, character: str, phase: str, asset_id: int, force: bool = False) -> Path | None:
        if not self._prompt_condense_enabled():
            return None
        if self.prompt_review_service is None:
            raise AIProxyServiceError("Prompt review service is required to stage prompt condense asks.")

        asset = self.asset_repository.get_asset(character, phase, asset_id)
        if asset.pipeline_stage not in {"PROMPT_REVIEW", "RENDER"}:
            return None
        context = self.prompt_review_service.get_context(character, phase, asset_id)
        if context.prompt_path is None or not context.prompt_text:
            return None

        condensed_path = context.prompt_path.parent / "Condensed_Image_Prompt.md"
        if force:
            condensed_path.unlink(missing_ok=True)
            self._clear_pending_prompt_condense_ask(asset)
        if not force and condensed_path.exists() and condensed_path.stat().st_mtime >= context.prompt_path.stat().st_mtime:
            return None
        self._ensure_queue_dirs()
        if not force and self._has_pending_prompt_condense_ask(asset):
            return None

        stamp = self._timestamp_compact()
        ask = AIProxyAsk(
            ask_id=f"Ask_Asset_{asset.asset_id}_PROMPT_CONDENSE_{stamp}",
            asset_id=asset.asset_id,
            character=asset.character,
            phase=asset.phase,
            pipeline=asset.pipeline,
            pipeline_stage=asset.pipeline_stage,
            ollama_attempt_id=f"{stamp}_{asset.asset_id}_PROMPT_CONDENSE",
            worker_type="ollama_generate",
            ollama_model=self._prompt_condense_model(),
            prompt_file="OLLAMA_PROMPT.md",
            expected_output="Condensed_Image_Prompt.md",
            candidate_output_file=None,
            task_type="prompt_condense",
            auxiliary=True,
            target_output_file="Condensed_Image_Prompt.md",
        )
        ask_path = self.ai_proxy_path_service.ask_path(ask.ask_id)
        ask_path.mkdir(parents=True, exist_ok=False)
        manifest = self._manifest_payload(ask)
        manifest["source_prompt_file"] = "Final_Image_Prompt.md"
        manifest["target_output_dir"] = str(context.prompt_path.parent.resolve())
        manifest["prompt_condense_template"] = str(self._prompt_condense_file())
        self._write_json_atomic(ask_path / "ask_manifest.json", manifest)
        self._write_text_atomic(ask_path / ask.prompt_file, self._prompt_condense_contents(asset, context.prompt_text))
        return ask_path

    def stage_render_task_prompt_condense_ask_if_enabled(
        self,
        manifest: dict,
        prompt_path: Path,
        target_output_dir: Path,
        force: bool = False,
    ) -> Path | None:
        if not self._prompt_condense_enabled():
            return None
        if not prompt_path.exists() or not prompt_path.is_file():
            return None
        condensed_path = target_output_dir / "Condensed_Image_Prompt.md"
        if force:
            condensed_path.unlink(missing_ok=True)
            for root in [self.ai_proxy_path_service.ask_root(), self.ai_proxy_path_service.answer_root()]:
                if not root.exists():
                    continue
                for path in root.iterdir():
                    if not path.is_dir():
                        continue
                    queued = self._read_json_if_exists(path / "ask_manifest.json")
                    if (path / "harvest_manifest.json").exists():
                        continue
                    if queued.get("task_type") == "prompt_condense" and queued.get("source_ask_id") == manifest.get("ask_id"):
                        shutil.rmtree(path, ignore_errors=True)
        if not force and condensed_path.exists() and condensed_path.stat().st_mtime >= prompt_path.stat().st_mtime:
            return None
        self._ensure_queue_dirs()
        ask_id_base = str(manifest.get("ask_id") or "RenderTask").replace("Ask_", "", 1)
        if not force:
            for root in [self.ai_proxy_path_service.ask_root(), self.ai_proxy_path_service.answer_root()]:
                if not root.exists():
                    continue
                for path in root.iterdir():
                    if not path.is_dir():
                        continue
                    queued = self._read_json_if_exists(path / "ask_manifest.json")
                    if queued.get("task_type") == "prompt_condense" and queued.get("source_ask_id") == manifest.get("ask_id"):
                        return None

        stamp = self._timestamp_compact()
        ask_id = f"Ask_{ask_id_base}_PROMPT_CONDENSE_{stamp}"
        ask_path = self.ai_proxy_path_service.ask_path(ask_id)
        ask_path.mkdir(parents=True, exist_ok=False)
        ask_manifest = {
            "version": 1,
            "ask_id": ask_id,
            "asset_id": manifest.get("asset_id"),
            "character": str(manifest.get("character") or ""),
            "phase": str(manifest.get("phase") or ""),
            "pipeline": str(manifest.get("pipeline") or ""),
            "pipeline_stage": str(manifest.get("pipeline_stage") or ""),
            "story_slug": manifest.get("story_slug"),
            "scene_slug": manifest.get("scene_slug"),
            "source_ask_id": manifest.get("ask_id"),
            "ollama_attempt_id": f"{stamp}_{ask_id_base}_PROMPT_CONDENSE",
            "worker_type": "ollama_generate",
            "ollama_model": self._prompt_condense_model(),
            "prompt_file": "OLLAMA_PROMPT.md",
            "expected_output": "Condensed_Image_Prompt.md",
            "candidate_output_file": None,
            "task_type": "prompt_condense",
            "auxiliary": True,
            "target_output_file": "Condensed_Image_Prompt.md",
            "target_output_dir": str(target_output_dir.resolve()),
            "source_prompt_file": prompt_path.name,
            "prompt_condense_template": str(self._prompt_condense_file()),
        }
        self._write_json_atomic(ask_path / "ask_manifest.json", ask_manifest)
        self._write_text_atomic(
            ask_path / "OLLAMA_PROMPT.md",
            self._prompt_condense_contents_from_values(
                prompt_path.read_text(encoding="utf-8"),
                {
                    "ASSET_ID": str(manifest.get("asset_id") or ""),
                    "CHARACTER": str(manifest.get("character") or manifest.get("story_slug") or ""),
                    "PHASE": str(manifest.get("phase") or ""),
                    "PIPELINE": str(manifest.get("pipeline") or ""),
                    "BODY_VIEW": str(manifest.get("body_view") or manifest.get("scene_slug") or ""),
                    "HEAD_VIEW": str(manifest.get("head_view") or ""),
                    "FINAL_IMAGE_OUTPUT": str(manifest.get("expected_output") or ""),
                },
            ),
        )
        return ask_path

    def render_task_local_render_api_params(
        self,
        manifest: dict,
        prompt_path: Path,
        target_output_dir: Path,
        render_layout: dict | None = None,
    ) -> dict:
        stamp = self._timestamp_compact()
        target_output_file = f"test_{stamp}.png"
        ask_id = f"Ask_Render_Task_{manifest.get('ask_id') or 'LOCAL'}_LOCAL_RENDER_{stamp}"
        ask_manifest = {
            "version": 1,
            "ask_id": ask_id,
            "asset_id": manifest.get("asset_id"),
            "character": manifest.get("character") or "",
            "phase": manifest.get("phase") or "",
            "pipeline": manifest.get("pipeline") or "",
            "pipeline_stage": manifest.get("pipeline_stage") or "",
            "ollama_attempt_id": f"{stamp}_{manifest.get('asset_id') or 'render_task'}_LOCAL_RENDER",
            "worker_type": "local_image_render",
            "ollama_model": "",
            "prompt_file": prompt_path.name,
            "expected_output": target_output_file,
            "candidate_output_file": None,
            "task_type": "local_test_render",
            "auxiliary": True,
            "source_ask_id": manifest.get("ask_id"),
            "source_prompt_file": prompt_path.name,
            "target_output_dir": str((target_output_dir / "Local_Test_Renders").resolve()),
            "target_output_file": target_output_file,
            "render_preset": self._local_render_preset(),
            "reference_files": manifest.get("reference_files") or [],
        }
        if manifest.get("aspect_ratio"):
            ask_manifest["aspect_ratio"] = manifest.get("aspect_ratio")
        if render_layout:
            ask_manifest["render_layout"] = render_layout
        return ask_manifest

    def stage_render_task_local_render_ask(
        self,
        manifest: dict,
        prompt_path: Path,
        target_output_dir: Path,
        render_layout: dict | None = None,
    ) -> Path:
        self._ensure_queue_dirs()
        for root in [self.ai_proxy_path_service.ask_root(), self.ai_proxy_path_service.answer_root()]:
            if not root.exists():
                continue
            for path in root.iterdir():
                if not path.is_dir():
                    continue
                queued = self._read_json_if_exists(path / "ask_manifest.json")
                if queued.get("task_type") == "local_test_render" and queued.get("source_ask_id") == manifest.get("ask_id"):
                    if not (path / "harvest_manifest.json").exists():
                        return path

        ask_manifest = self.render_task_local_render_api_params(manifest, prompt_path, target_output_dir, render_layout)
        ask_path = self.ai_proxy_path_service.ask_path(ask_manifest["ask_id"])
        ask_path.mkdir(parents=True, exist_ok=False)
        self._write_json_atomic(ask_path / "ask_manifest.json", ask_manifest)
        self._write_text_atomic(ask_path / prompt_path.name, prompt_path.read_text(encoding="utf-8"))
        return ask_path

    def stage_scene_local_render_ask(self, manifest: dict, workspace: Path) -> Path:
        prompt_path = workspace / "Local_Render_Prompt.md"
        if not prompt_path.exists():
            raise FileNotFoundError(f"No local render prompt was found: {prompt_path}")

        layout_backend = str(getattr(self.path_service.config, "local_render_layout_backend", "forge_couple_basic"))
        brief_path = workspace / "Local_Render_Brief.json"
        brief = self._read_json_if_exists(brief_path)
        if layout_backend == "forge_couple_basic" and not brief:
            raise FileNotFoundError(f"No valid local render brief was found: {brief_path}")
        canvas = brief.get("canvas") if isinstance(brief.get("canvas"), dict) else {}
        staged_manifest = dict(manifest)
        if str(canvas.get("aspect_ratio") or "").strip():
            staged_manifest["aspect_ratio"] = str(canvas["aspect_ratio"])

        subject_count = int(brief.get("subject_count") or 0)
        render_layout = None
        if layout_backend == "forge_couple_basic" and subject_count >= 2:
            forge = brief.get("forge_couple_basic") if isinstance(brief.get("forge_couple_basic"), dict) else {}
            plan = brief.get("forge_couple_plan") if isinstance(brief.get("forge_couple_plan"), dict) else {}
            prompt_lines = [str(line).strip() for line in forge.get("prompt_lines", []) if str(line).strip()]
            if len(prompt_lines) != subject_count + 1:
                raise AIProxyServiceError("Forge Couple scene layout must contain one global line and one line per visible subject.")
            mode = str(plan.get("mode") or "Basic")
            mappings = [
                plan.get("global_region", {}).get("mapping"),
                *[region.get("mapping") for region in plan.get("character_regions", [])],
            ] if plan else []
            if mode == "Advanced" and (len(mappings) != len(prompt_lines) or not all(isinstance(item, list) and len(item) == 5 for item in mappings)):
                mode = "Basic"
                mappings = []
            render_layout = {
                "backend": "forge_couple_basic",
                "subject_count": subject_count,
                "prompt_lines": prompt_lines,
                "mode": mode,
                "disable_hr": bool(plan.get("forge_couple_debug_base_pass", True)),
                "mappings": mappings,
                "separator": "",
                "direction": str(forge.get("direction") or "Horizontal"),
                "background": str(forge.get("background") or "First Line"),
                "background_weight": float(forge.get("background_weight", 0.5)),
                "common_parser": "{ }",
                "common_debug": False,
                "def_in_prompt": True,
            }
        elif layout_backend not in {"forge_couple_basic", "plain_txt2img"}:
            raise AIProxyServiceError(f"Unsupported local render layout backend: {layout_backend}")

        return self.stage_render_task_local_render_ask(staged_manifest, prompt_path, workspace, render_layout)

    def stage_prompt_review_render_ask_if_enabled(self, character: str, phase: str, asset_id: int) -> Path | None:
        if not self._local_render_auto_queue_after_condense_enabled():
            return None
        if self.prompt_review_service is None:
            raise AIProxyServiceError("Prompt review service is required to stage prompt review render asks.")

        asset = self.asset_repository.get_asset(character, phase, asset_id)
        if asset.pipeline_stage not in {"PROMPT_REVIEW", "RENDER"}:
            return None

        context = self.prompt_review_service.get_context(character, phase, asset_id)
        if context.condensed_prompt_path is None or not context.condensed_prompt_text:
            return None
        if self._has_pending_auxiliary_task(asset, "prompt_review_render"):
            return None

        self._ensure_queue_dirs()
        stamp = self._timestamp_compact()
        target_output_file = f"test_{stamp}.png"
        ask = AIProxyAsk(
            ask_id=f"Ask_Asset_{asset.asset_id}_PROMPT_REVIEW_RENDER_{stamp}",
            asset_id=asset.asset_id,
            character=asset.character,
            phase=asset.phase,
            pipeline=asset.pipeline,
            pipeline_stage=asset.pipeline_stage,
            ollama_attempt_id=f"{stamp}_{asset.asset_id}_PROMPT_REVIEW_RENDER",
            worker_type="local_image_render",
            ollama_model="",
            prompt_file="Condensed_Image_Prompt.md",
            expected_output=target_output_file,
            candidate_output_file=None,
            task_type="prompt_review_render",
            auxiliary=True,
            target_output_file=target_output_file,
            render_preset=self._local_render_preset(),
        )
        ask_path = self.ai_proxy_path_service.ask_path(ask.ask_id)
        ask_path.mkdir(parents=True, exist_ok=False)
        manifest = self._manifest_payload(ask)
        manifest["source_prompt_file"] = "Condensed_Image_Prompt.md"
        manifest["target_output_dir"] = str((context.condensed_prompt_path.parent / "Local_Test_Renders").resolve())
        self._write_json_atomic(ask_path / "ask_manifest.json", manifest)
        self._write_text_atomic(ask_path / ask.prompt_file, context.condensed_prompt_text)
        return ask_path

    def issue_monitor_test(self, instruction: str = "") -> Path:
        self._ensure_queue_dirs()
        self._clear_monitor_state()
        test_id = f"Test_{self._timestamp_compact()}"
        request_path = self.ai_proxy_path_service.monitor_request_path(test_id)
        request_path.mkdir(parents=True, exist_ok=False)
        payload = {
            "version": 1,
            "test_id": test_id,
            "instruction": instruction.strip(),
            "created_at": self._timestamp(),
        }
        manifest_path = request_path / "request.json"
        self._write_json_atomic(manifest_path, payload)
        json.loads(manifest_path.read_text(encoding="utf-8"))
        return request_path

    def stop_state(self) -> dict:
        self._ensure_queue_dirs()
        payload = self._read_json_if_exists(self.ai_proxy_path_service.stop_manifest_path())
        return {
            "active": bool(payload.get("active", False)),
            "stop_id": payload.get("stop_id"),
            "reject_before_compact": payload.get("reject_before_compact"),
            "activated_at": payload.get("activated_at"),
            "cleared_at": payload.get("cleared_at"),
            "cleared_asks": int(payload.get("cleared_asks", 0) or 0),
        }

    def activate_stop(self) -> dict:
        self._ensure_queue_dirs()
        stop_id = f"Stop_{self._timestamp_compact()}"
        reject_before_compact = self._timestamp_compact().replace("_", "")
        cleared_asks = 0

        for ask_path in sorted(path for path in self.ai_proxy_path_service.ask_root().iterdir() if path.is_dir()):
            ask_manifest = self._read_json_if_exists(ask_path / "ask_manifest.json")
            answer_manifest = {
                "version": 1,
                "ask_id": ask_manifest.get("ask_id") or ask_path.name,
                "asset_id": ask_manifest.get("asset_id"),
                "ollama_attempt_id": ask_manifest.get("ollama_attempt_id") or "",
                "worker_id": "SYSTEM_STOP",
                "status": "REJECTED",
                "expected_output": ask_manifest.get("expected_output") or "OLLAMA_RESPONSE.md",
                "started_at": self._timestamp(),
                "completed_at": self._timestamp(),
                "elapsed_seconds": 0,
                "error_type": "STOPPED",
                "error_message": "Ask rejected because AI proxy stop was activated.",
            }
            self._write_json_atomic(ask_path / "answer_manifest.json", answer_manifest)
            dest = self.ai_proxy_path_service.answer_root() / ask_path.name
            if dest.exists():
                shutil.rmtree(dest, ignore_errors=True)
            shutil.move(str(ask_path), str(dest))
            cleared_asks += 1

        payload = {
            "version": 1,
            "active": True,
            "stop_id": stop_id,
            "reject_before_compact": reject_before_compact,
            "activated_at": self._timestamp(),
            "cleared_at": None,
            "cleared_asks": cleared_asks,
        }
        self._write_json_atomic(self.ai_proxy_path_service.stop_manifest_path(), payload)
        return payload

    def resume_stop(self) -> dict:
        self._ensure_queue_dirs()
        current = self._read_json_if_exists(self.ai_proxy_path_service.stop_manifest_path())
        payload = {
            "version": 1,
            "active": False,
            "stop_id": current.get("stop_id"),
            "reject_before_compact": current.get("reject_before_compact"),
            "activated_at": current.get("activated_at"),
            "cleared_at": self._timestamp(),
            "cleared_asks": int(current.get("cleared_asks", 0) or 0),
        }
        self._write_json_atomic(self.ai_proxy_path_service.stop_manifest_path(), payload)
        return payload

    def dump_pending_queue(self) -> dict:
        """Delete pending ask and claimed task folders without touching answers."""
        self._ensure_queue_dirs()
        removed: list[dict] = []

        def remove_path(path: Path, queue_area: str, worker_id: str = "") -> None:
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            elif path.exists():
                path.unlink(missing_ok=True)
            removed.append({"queue_area": queue_area, "worker_id": worker_id, "name": path.name})

        for ask_path in sorted(path for path in self.ai_proxy_path_service.ask_root().iterdir() if path.is_dir()):
            remove_path(ask_path, "Ask")

        claimed_root = self.ai_proxy_path_service.claimed_root()
        if claimed_root.exists():
            for worker_dir in sorted(path for path in claimed_root.iterdir() if path.is_dir()):
                for task_path in sorted(path for path in worker_dir.iterdir() if path.is_dir()):
                    remove_path(task_path, "Claimed", worker_dir.name)

        claims_root = self.ai_proxy_path_service.claims_root()
        if claims_root.exists():
            for claim_path in sorted(path for path in claims_root.iterdir() if path.is_file()):
                remove_path(claim_path, "Claims")

        return {
            "removed_count": len(removed),
            "removed": removed,
        }

    def archive_harvested_answers(self) -> dict:
        """Move harvested answer folders into a dated archive folder."""
        self._ensure_queue_dirs()
        answer_root = self.ai_proxy_path_service.answer_root()
        archive_root = self.ai_proxy_path_service.harvested_archive_root() / datetime.now().strftime("%Y-%m-%d")
        archive_root.mkdir(parents=True, exist_ok=True)

        moved: list[dict] = []
        skipped: list[dict] = []
        for answer_path in sorted(path for path in answer_root.iterdir() if path.is_dir()):
            harvest_manifest = answer_path / "harvest_manifest.json"
            if not harvest_manifest.exists():
                skipped.append({"name": answer_path.name, "reason": "not harvested"})
                continue

            dest_path = archive_root / answer_path.name
            if dest_path.exists():
                suffix = datetime.now().strftime("%H%M%S_%f")
                dest_path = archive_root / f"{answer_path.name}.{suffix}"
            shutil.move(str(answer_path), str(dest_path))
            moved.append({"name": answer_path.name, "archived_to": str(dest_path)})

        return {
            "archive_root": str(archive_root),
            "moved_count": len(moved),
            "skipped_count": len(skipped),
            "moved": moved,
            "skipped": skipped,
        }

    def list_monitor_responses(self) -> list[MonitorTestResult]:
        self._ensure_queue_dirs()
        results: list[MonitorTestResult] = []
        root = self.ai_proxy_path_service.monitor_responses_root()
        for worker_dir in sorted(path for path in root.iterdir() if path.is_dir()):
            for response_path in sorted(path for path in worker_dir.iterdir() if path.is_file() and path.suffix == ".json"):
                payload = self._read_json_if_exists(response_path)
                results.append(
                    MonitorTestResult(
                        test_id=str(payload.get("test_id") or response_path.stem),
                        worker_id=str(payload.get("worker_id") or worker_dir.name),
                        host=str(payload.get("host") or worker_dir.name),
                        status=str(payload.get("status") or "UNKNOWN"),
                        ollama_ok=bool(payload.get("ollama_ok", False)),
                        models=[str(model) for model in payload.get("models", []) if str(model).strip()],
                        message=str(payload.get("message")) if payload.get("message") is not None else None,
                        responded_at=str(payload.get("responded_at")) if payload.get("responded_at") is not None else None,
                    )
                )
        results.sort(key=lambda item: (item.test_id, item.worker_id), reverse=True)
        return results

    def queue_snapshot(self) -> dict:
        self._ensure_queue_dirs()
        snapshot: dict[str, list[dict]] = {
            "ask": [],
            "claimed": [],
            "answer": [],
            "failed": [],
        }

        for ask_path in sorted(path for path in self.ai_proxy_path_service.ask_root().iterdir() if path.is_dir()):
            payload = self._read_json_if_exists(ask_path / "ask_manifest.json")
            snapshot["ask"].append(
                {
                    "ask_id": payload.get("ask_id") or ask_path.name,
                    "asset_id": payload.get("asset_id"),
                    "pipeline_stage": payload.get("pipeline_stage"),
                    "worker_type": payload.get("worker_type"),
                    "task_type": payload.get("task_type"),
                    "source_ask_id": payload.get("source_ask_id"),
                    "ollama_attempt_id": payload.get("ollama_attempt_id"),
                }
            )

        claimed_root = self.ai_proxy_path_service.claimed_root()
        for worker_dir in sorted(path for path in claimed_root.iterdir() if path.is_dir()):
            for claim_path in sorted(path for path in worker_dir.iterdir() if path.is_dir()):
                payload = self._read_json_if_exists(claim_path / "ask_manifest.json")
                snapshot["claimed"].append(
                    {
                        "worker_id": worker_dir.name,
                        "ask_id": payload.get("ask_id") or claim_path.name,
                        "asset_id": payload.get("asset_id"),
                        "pipeline_stage": payload.get("pipeline_stage"),
                        "worker_type": payload.get("worker_type"),
                        "task_type": payload.get("task_type"),
                        "source_ask_id": payload.get("source_ask_id"),
                        "ollama_attempt_id": payload.get("ollama_attempt_id"),
                    }
                )

        for answer_path in sorted(path for path in self.ai_proxy_path_service.answer_root().iterdir() if path.is_dir()):
            payload = self._read_json_if_exists(answer_path / "answer_manifest.json")
            ask_payload = self._read_json_if_exists(answer_path / "ask_manifest.json")
            harvest_payload = self._read_json_if_exists(answer_path / "harvest_manifest.json")
            if harvest_payload:
                continue
            snapshot["answer"].append(
                {
                    "ask_id": payload.get("ask_id") or answer_path.name,
                    "asset_id": payload.get("asset_id"),
                    "status": payload.get("status"),
                    "worker_id": payload.get("worker_id"),
                    "task_type": ask_payload.get("task_type"),
                    "source_ask_id": ask_payload.get("source_ask_id"),
                    "ollama_attempt_id": payload.get("ollama_attempt_id"),
                }
            )

        failed_root = self.ai_proxy_path_service.failed_root()
        for worker_dir in sorted(path for path in failed_root.iterdir() if path.is_dir()):
            for failed_path in sorted(path for path in worker_dir.iterdir()):
                snapshot["failed"].append(
                    {
                        "worker_id": worker_dir.name,
                        "name": failed_path.name,
                    }
                )

        return snapshot
