import json
import shutil
from dataclasses import replace
from datetime import datetime
from pathlib import Path

from zet.models.ai_proxy import (
    AI_PROXY_PROTOCOL_VERSION,
    AIProxyAnswerManifest,
    AIProxyAsk,
    AIProxyAskManifest,
)
from zet.repositories.asset_repository import AssetRepository
from zet.repositories.pipeline_repository import PipelineRepository
from zet.models.reference import reference_files_payload
from zet.services.ai_proxy_path_service import AIProxyPathService
from zet.services.atomic_file_service import write_text_atomic
from zet.services.housekeeping_service import HousekeepingService
from zet.services.path_service import PathService
from zet.services.prompt_artifact_service import PromptArtifactService


class AIProxyServiceError(Exception):
    pass


class AIProxyService:
    def __init__(
        self,
        asset_repository: AssetRepository,
        pipeline_repository: PipelineRepository,
        path_service: PathService,
        prompt_artifact_service: PromptArtifactService,
        ai_proxy_path_service: AIProxyPathService,
        housekeeping_service: HousekeepingService,
    ):
        self.asset_repository = asset_repository
        self.pipeline_repository = pipeline_repository
        self.path_service = path_service
        self.prompt_artifact_service = prompt_artifact_service
        self.ai_proxy_path_service = ai_proxy_path_service
        self.housekeeping_service = housekeeping_service

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
        if not isinstance(data, dict):
            return {}
        if path.name == "ask_manifest.json":
            return AIProxyAskManifest.from_dict(data).to_dict()
        if path.name == "answer_manifest.json":
            return AIProxyAnswerManifest.from_dict(data).to_dict()
        return data

    def _write_text_atomic(self, path: Path, contents: str) -> None:
        write_text_atomic(path, contents)

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

        for item in self.ai_proxy_path_service.task_paths("ask", "answer"):
            manifest = self._read_json_if_exists(item / "ask_manifest.json")
            if manifest.get("asset_id") == asset.asset_id or item.name.startswith(asset_prefix):
                remove_path(item)
                self.ai_proxy_path_service.file_proxy_client.remove_route(item.name)

        return removed

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
            body_view=asset.body_view,
            candidate_output_file=asset.final_image_output,
            task_type="render",
            render_preset="chatgpt-manual",
            manual=True,
            reference_files=asset.reference_files or [],
        )

    def _build_ask(self, asset) -> AIProxyAsk:
        """Build the queue ask appropriate for an asset's current pipeline stage."""
        stamp = self._timestamp_compact()
        ask_id = f"Ask_Asset_{asset.asset_id}_{asset.pipeline_stage}_{stamp}"
        attempt_id = f"{stamp}_{asset.asset_id}_{asset.pipeline_stage}"
        if asset.pipeline == "Body-Reference" and asset.pipeline_stage == "RENDER":
            render_backend = self._render_backend()
            if render_backend == "manual_chatgpt":
                return self._build_manual_render_ask(asset, ask_id, attempt_id)
            prompt_file = "Final_Image_Prompt.md"
            context = self.prompt_artifact_service.get_context(asset.character, asset.phase, asset.asset_id)
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
        if asset.pipeline == "Head-Image" and asset.pipeline_stage == "RENDER":
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
            ollama_model=str(getattr(self.path_service.config, "ai_asset_workflow_model", "general-purpose:latest")),
            prompt_file="OLLAMA_PROMPT.md",
            expected_output="OLLAMA_RESPONSE.md",
            candidate_output_file=asset.final_image_output,
            task_type="generate",
        )

    def _ensure_queue_dirs(self) -> None:
        self.ai_proxy_path_service.file_proxy_client.ensure_layout()
        for path in (
            self.ai_proxy_path_service.manual_ask_root(),
            self.ai_proxy_path_service.manual_answer_root(),
        ):
            path.mkdir(parents=True, exist_ok=True)

    def _create_ask_folder(self, ask_id: str, worker_type: str) -> Path:
        if worker_type == "manual_chatgpt_render":
            path = self.ai_proxy_path_service.manual_ask_path(ask_id)
            path.mkdir(parents=True, exist_ok=False)
            return path
        return self.ai_proxy_path_service.file_proxy_client.create_staging(ask_id)

    def _publish_ask_folder(self, path: Path, ask_id: str, worker_type: str) -> Path:
        if worker_type == "manual_chatgpt_render":
            return path
        return self.ai_proxy_path_service.file_proxy_client.publish(path, ask_id, worker_type)

    def _manifest_payload(self, ask: AIProxyAsk) -> dict:
        payload = {
            "version": AI_PROXY_PROTOCOL_VERSION,
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
            "reference_files": reference_files_payload(ask.reference_files),
            "ollama_temperature": ask.ollama_temperature,
            "ollama_num_ctx": ask.ollama_num_ctx,
            "consumer": ask.consumer,
        }
        if ask.body_view is not None:
            payload["body_view"] = ask.body_view
        workflow_kind = self._local_render_workflow_kind()
        if ask.worker_type == "local_image_render" and workflow_kind:
            payload["workflow_kind"] = workflow_kind
        return payload

    def asset_job_status(self, asset_id: int) -> dict:
        """Return outstanding AI proxy work for one asset."""
        jobs = []
        for state in ("ask", "running", "answer"):
            for path in self.ai_proxy_path_service.task_paths(state):
                manifest = self._read_json_if_exists(path / "ask_manifest.json")
                if int(manifest.get("asset_id") or 0) != asset_id:
                    continue
                if state == "answer" and (path / "harvest_manifest.json").exists():
                    continue
                jobs.append({
                    "ask_id": manifest.get("ask_id") or path.name,
                    "state": state,
                    "task_type": manifest.get("task_type"),
                    "worker_type": manifest.get("worker_type"),
                })
        return {"pending": bool(jobs), "count": len(jobs), "jobs": jobs}

    def _prompt_contents(self, asset) -> str:
        """Read the prompt text that should be copied into a queued ask."""
        if asset.pipeline == "Body-Reference" and asset.pipeline_stage == "RENDER":
            context = self.prompt_artifact_service.get_context(asset.character, asset.phase, asset.asset_id)
            if self._render_backend() == "manual_chatgpt":
                if not context.prompt_text:
                    raise AIProxyServiceError(f"No Final_Image_Prompt.md found for Asset {asset.asset_id}.")
                return context.prompt_text
            if not context.render_prompt_text:
                raise AIProxyServiceError(f"No render prompt found for Asset {asset.asset_id}.")
            return context.render_prompt_text

        if asset.pipeline == "Head-Image" and asset.pipeline_stage == "RENDER":
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

    def stage_current_ai_ask(self, character: str, phase: str, asset_id: int) -> Path:
        """Write an AI queue ask for the asset's current AI_AGENT stage."""
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        if asset.actor != "AI_AGENT":
            raise AIProxyServiceError("AI ask staging is only available when Actor is AI_AGENT.")
        if not asset.final_image_output:
            raise AIProxyServiceError(f"Asset {asset.asset_id} is missing final_image_output.")

        self.pipeline_repository.get_pipeline(character, phase, asset.pipeline)
        ask = self._build_ask(asset)
        self._ensure_queue_dirs()

        ask_path = self._create_ask_folder(ask.ask_id, ask.worker_type)

        manifest_path = ask_path / "ask_manifest.json"
        self._write_json_atomic(manifest_path, self._manifest_payload(ask))
        json.loads(manifest_path.read_text(encoding="utf-8"))

        prompt_path = ask_path / ask.prompt_file
        self._write_text_atomic(prompt_path, self._prompt_contents(asset))
        updated_asset = replace(asset)
        updated_asset.ai_state = "ASKED"
        updated_asset.last_ai_update = f"AI ask staged: {ask.ask_id} ({ask.ollama_attempt_id})"
        updated_asset.updated_at = self._timestamp()

        self.asset_repository.save_asset(updated_asset)
        self.housekeeping_service.prepare_stage(updated_asset)
        return self._publish_ask_folder(ask_path, ask.ask_id, ask.worker_type)

    def _prompt_condense_enabled(self) -> bool:
        return bool(getattr(self.path_service.config, "prompt_condense_enabled", False))

    def _local_render_auto_queue_after_condense_enabled(self) -> bool:
        return bool(getattr(self.path_service.config, "local_render_auto_queue_after_condense", False))

    def _local_render_preset(self) -> str:
        if str(getattr(self.path_service.config, "local_render_backend", "stable_matrix")).strip().lower() == "comfyui":
            return str(getattr(self.path_service.config, "comfyui_profile", "comfyui-core-preview"))
        return str(getattr(self.path_service.config, "local_render_preset", "body-reference-preview"))

    def _local_render_workflow_kind(self) -> str:
        if str(getattr(self.path_service.config, "local_render_backend", "stable_matrix")).strip().lower() != "comfyui":
            return ""
        profile_name = self._local_render_preset()
        profiles = self._read_json_if_exists(
            self.path_service.project_root / "Config" / "Local_Render_Presets.json"
        )
        profile = profiles.get(profile_name) if isinstance(profiles, dict) else None
        if isinstance(profile, dict) and str(profile.get("workflow_kind") or "").strip():
            return str(profile["workflow_kind"])
        return "core_txt2img_scene_preview"

    def _workflow_kind_for_preset(self, profile_name: str) -> str:
        profiles = self._read_json_if_exists(
            self.path_service.project_root / "Config" / "Local_Render_Presets.json"
        )
        profile = profiles.get(profile_name) if isinstance(profiles, dict) else None
        if not isinstance(profile, dict):
            return ""
        return str(profile.get("prompt_workflow_kind") or profile.get("workflow_kind") or "").strip()

    def _prompt_condense_model(self) -> str:
        return str(getattr(self.path_service.config, "prompt_condense_model", "structured-reasoning:latest"))

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
        for ask_path in self.ai_proxy_path_service.task_paths("ask", "answer"):
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
        for ask_path in self.ai_proxy_path_service.task_paths("ask", "running", "answer"):
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
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        if asset.pipeline_stage != "RENDER":
            return None
        context = self.prompt_artifact_service.get_context(character, phase, asset_id)
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
        ask_path = self._create_ask_folder(ask.ask_id, ask.worker_type)
        manifest = self._manifest_payload(ask)
        manifest["source_prompt_file"] = "Final_Image_Prompt.md"
        manifest["target_output_dir"] = str(context.prompt_path.parent.resolve())
        manifest["prompt_condense_template"] = str(self._prompt_condense_file())
        self._write_json_atomic(ask_path / "ask_manifest.json", manifest)
        self._write_text_atomic(ask_path / ask.prompt_file, self._prompt_condense_contents(asset, context.prompt_text))
        return self._publish_ask_folder(ask_path, ask.ask_id, ask.worker_type)

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
            for path in self.ai_proxy_path_service.task_paths("ask", "answer"):
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
            for path in self.ai_proxy_path_service.task_paths("ask", "answer"):
                queued = self._read_json_if_exists(path / "ask_manifest.json")
                if queued.get("task_type") == "prompt_condense" and queued.get("source_ask_id") == manifest.get("ask_id"):
                    return None

        stamp = self._timestamp_compact()
        ask_id = f"Ask_{ask_id_base}_PROMPT_CONDENSE_{stamp}"
        ask_path = self._create_ask_folder(ask_id, "ollama_generate")
        ask_manifest = {
            "version": AI_PROXY_PROTOCOL_VERSION,
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
        return self._publish_ask_folder(ask_path, ask_id, "ollama_generate")

    def render_task_local_render_api_params(
        self,
        manifest: dict,
        prompt_path: Path,
        target_output_dir: Path,
        render_layout: dict | None = None,
        scene_render_ir_path: Path | None = None,
        seed: int | None = None,
        checkpoint: str | None = None,
        render_overrides: dict | None = None,
        render_preset: str | None = None,
        image_generation: str | None = None,
        reference_files: list[dict] | None = None,
    ) -> dict:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        target_output_file = f"test_{stamp}.png"
        ask_id = f"Ask_Render_Task_{manifest.get('ask_id') or 'LOCAL'}_LOCAL_RENDER_{stamp}"
        ask_manifest = {
            "version": AI_PROXY_PROTOCOL_VERSION,
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
            "artifact_output_dir": str(target_output_dir.resolve()),
            "target_output_file": target_output_file,
            "render_preset": render_preset or self._local_render_preset(),
            "image_generation": str(
                image_generation or getattr(self.path_service.config, "local_render_backend", "stable_matrix")
            ).strip().lower(),
            "reference_files": reference_files_payload(
                reference_files if reference_files is not None else manifest.get("reference_files") or []
            ),
        }
        ask_manifest["checkpoint"] = checkpoint if checkpoint is not None else str(
            getattr(
                self.path_service.config,
                "comfyui_checkpoint"
                if ask_manifest["image_generation"] == "comfyui"
                else "local_render_checkpoint",
                "",
            )
        )
        workflow_kind = self._workflow_kind_for_preset(str(ask_manifest["render_preset"]))
        if not workflow_kind and ask_manifest["image_generation"] == "comfyui":
            workflow_kind = self._local_render_workflow_kind()
        if workflow_kind:
            ask_manifest["workflow_kind"] = workflow_kind
        if seed is not None:
            ask_manifest["seed"] = int(seed)
        if render_overrides:
            ask_manifest["render_overrides"] = dict(render_overrides)
        if manifest.get("aspect_ratio"):
            ask_manifest["aspect_ratio"] = manifest.get("aspect_ratio")
        if render_layout:
            ask_manifest["render_layout"] = render_layout
        if scene_render_ir_path is not None:
            ask_manifest["scene_render_ir_file"] = scene_render_ir_path.name
        return ask_manifest

    def stage_render_task_local_render_ask(
        self,
        manifest: dict,
        prompt_path: Path,
        target_output_dir: Path,
        render_layout: dict | None = None,
        scene_render_ir_path: Path | None = None,
        *,
        allow_parallel: bool = False,
        seed: int | None = None,
        checkpoint: str | None = None,
        render_overrides: dict | None = None,
        render_preset: str | None = None,
        image_generation: str | None = None,
        reference_files: list[dict] | None = None,
    ) -> Path:
        self._ensure_queue_dirs()
        if not allow_parallel:
            for path in self.ai_proxy_path_service.task_paths("ask", "answer"):
                queued = self._read_json_if_exists(path / "ask_manifest.json")
                if queued.get("task_type") == "local_test_render" and queued.get("source_ask_id") == manifest.get("ask_id"):
                    if not (path / "harvest_manifest.json").exists():
                        return path

        ask_manifest = self.render_task_local_render_api_params(
            manifest,
            prompt_path,
            target_output_dir,
            render_layout,
            scene_render_ir_path,
            seed,
            checkpoint,
            render_overrides,
            render_preset,
            image_generation,
            reference_files,
        )
        ask_path = self._create_ask_folder(ask_manifest["ask_id"], "local_image_render")
        self._write_json_atomic(ask_path / "ask_manifest.json", ask_manifest)
        self._write_text_atomic(ask_path / prompt_path.name, prompt_path.read_text(encoding="utf-8"))
        if scene_render_ir_path is not None:
            self._write_text_atomic(
                ask_path / scene_render_ir_path.name,
                scene_render_ir_path.read_text(encoding="utf-8"),
            )
        return self._publish_ask_folder(ask_path, ask_manifest["ask_id"], "local_image_render")

    def stage_scene_local_render_ask(
        self,
        manifest: dict,
        workspace: Path,
        *,
        allow_parallel: bool = False,
        seed: int | None = None,
        checkpoint: str | None = None,
    ) -> Path:
        prompt_path = workspace / "Local_Render_Prompt.md"
        if not prompt_path.exists():
            raise FileNotFoundError(f"No local render prompt was found: {prompt_path}")

        selected_backend = str(getattr(self.path_service.config, "local_render_backend", "stable_matrix")).strip().lower()
        layout_backend = str(getattr(self.path_service.config, "local_render_layout_backend", "forge_couple_basic"))
        brief_path = workspace / "Local_Render_Brief.json"
        brief = self._read_json_if_exists(brief_path)
        if selected_backend == "stable_matrix" and layout_backend == "forge_couple_basic" and not brief:
            raise FileNotFoundError(f"No valid local render brief was found: {brief_path}")
        canvas = brief.get("canvas") if isinstance(brief.get("canvas"), dict) else {}
        staged_manifest = dict(manifest)
        if str(canvas.get("aspect_ratio") or "").strip():
            staged_manifest["aspect_ratio"] = str(canvas["aspect_ratio"])

        subject_count = int(brief.get("subject_count") or 0)
        render_layout = None
        if selected_backend == "stable_matrix" and layout_backend == "forge_couple_basic" and subject_count >= 2:
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
        elif selected_backend == "stable_matrix" and layout_backend not in {"forge_couple_basic", "plain_txt2img"}:
            raise AIProxyServiceError(f"Unsupported local render layout backend: {layout_backend}")

        ir_path = workspace / "Scene_Render_IR.json"
        if selected_backend == "comfyui" and not ir_path.exists():
            raise FileNotFoundError(f"No canonical scene render IR was found: {ir_path}")
        return self.stage_render_task_local_render_ask(
            staged_manifest,
            prompt_path,
            workspace,
            render_layout,
            ir_path if selected_backend == "comfyui" else None,
            allow_parallel=allow_parallel,
            seed=seed,
            checkpoint=checkpoint,
        )

    def stage_prompt_inspection_render_ask_if_enabled(self, character: str, phase: str, asset_id: int) -> Path | None:
        if not self._local_render_auto_queue_after_condense_enabled():
            return None
        asset = self.asset_repository.get_asset(character, phase, asset_id)
        if asset.pipeline_stage != "RENDER":
            return None

        context = self.prompt_artifact_service.get_context(character, phase, asset_id)
        if context.condensed_prompt_path is None or not context.condensed_prompt_text:
            return None
        if self._has_pending_auxiliary_task(asset, "prompt_inspection_render"):
            return None

        self._ensure_queue_dirs()
        stamp = self._timestamp_compact()
        target_output_file = f"test_{stamp}.png"
        ask = AIProxyAsk(
            ask_id=f"Ask_Asset_{asset.asset_id}_PROMPT_INSPECTION_RENDER_{stamp}",
            asset_id=asset.asset_id,
            character=asset.character,
            phase=asset.phase,
            pipeline=asset.pipeline,
            pipeline_stage=asset.pipeline_stage,
            ollama_attempt_id=f"{stamp}_{asset.asset_id}_PROMPT_INSPECTION_RENDER",
            worker_type="local_image_render",
            ollama_model="",
            prompt_file="Condensed_Image_Prompt.md",
            expected_output=target_output_file,
            candidate_output_file=None,
            task_type="prompt_inspection_render",
            auxiliary=True,
            target_output_file=target_output_file,
            render_preset=self._local_render_preset(),
        )
        ask_path = self._create_ask_folder(ask.ask_id, ask.worker_type)
        manifest = self._manifest_payload(ask)
        manifest["source_prompt_file"] = "Condensed_Image_Prompt.md"
        manifest["target_output_dir"] = str((context.condensed_prompt_path.parent / "Local_Test_Renders").resolve())
        self._write_json_atomic(ask_path / "ask_manifest.json", manifest)
        self._write_text_atomic(ask_path / ask.prompt_file, context.condensed_prompt_text)
        return self._publish_ask_folder(ask_path, ask.ask_id, ask.worker_type)

    def archive_harvested_answers(self) -> dict:
        """Move harvested answer folders into a dated archive folder."""
        self._ensure_queue_dirs()
        archive_root = self.ai_proxy_path_service.harvested_archive_root() / datetime.now().strftime("%Y-%m-%d")
        archive_root.mkdir(parents=True, exist_ok=True)

        moved: list[dict] = []
        skipped: list[dict] = []
        for answer_path in self.ai_proxy_path_service.task_paths("answer"):
            harvest_manifest = answer_path / "harvest_manifest.json"
            if not harvest_manifest.exists():
                skipped.append({"name": answer_path.name, "reason": "not harvested"})
                continue

            dest_path = archive_root / answer_path.name
            if dest_path.exists():
                suffix = datetime.now().strftime("%H%M%S_%f")
                dest_path = archive_root / f"{answer_path.name}.{suffix}"
            shutil.move(str(answer_path), str(dest_path))
            self.ai_proxy_path_service.file_proxy_client.remove_route(answer_path.name)
            moved.append({"name": answer_path.name, "archived_to": str(dest_path)})

        return {
            "archive_root": str(archive_root),
            "moved_count": len(moved),
            "skipped_count": len(skipped),
            "moved": moved,
            "skipped": skipped,
        }

    def harvested_answer_count(self) -> int:
        self._ensure_queue_dirs()
        return sum(
            1
            for answer_path in self.ai_proxy_path_service.task_paths("answer")
            if (answer_path / "harvest_manifest.json").exists()
        )

    def queue_snapshot(self) -> dict:
        self._ensure_queue_dirs()
        snapshot: dict[str, list[dict]] = {
            "ask": [],
            "running": [],
            "answer": [],
        }

        for ask_path in self.ai_proxy_path_service.task_paths("ask"):
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

        for running_path in self.ai_proxy_path_service.task_paths("running"):
            payload = self._read_json_if_exists(running_path / "ask_manifest.json")
            snapshot["running"].append(
                {
                    "ask_id": payload.get("ask_id") or running_path.name,
                    "asset_id": payload.get("asset_id"),
                    "pipeline_stage": payload.get("pipeline_stage"),
                    "worker_type": payload.get("worker_type"),
                    "task_type": payload.get("task_type"),
                    "source_ask_id": payload.get("source_ask_id"),
                    "ollama_attempt_id": payload.get("ollama_attempt_id"),
                }
            )

        for answer_path in self.ai_proxy_path_service.task_paths("answer"):
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

        return snapshot
