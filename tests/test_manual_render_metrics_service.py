import json
import tempfile
import unittest
from pathlib import Path

from zet.services.config_service import Config
from zet.services.manual_render_metrics_service import ManualRenderMetricsService


class ManualRenderMetricsServiceTests(unittest.TestCase):
    @staticmethod
    def _config(root: Path) -> Config:
        return Config(
            base_library_path=str(root),
            base_character_path=str(root / "Characters"),
            base_asset_path=str(root / "Assets"),
            base_pipeline_path=str(root / "Pipelines"),
            base_ai_queue_path=str(root / "Queue"),
        )

    @staticmethod
    def _answer(
        folder: Path,
        ask_id: str,
        *,
        refinement: dict | None,
        engine_profile: str = "chatgpt_images_2_5_v1",
        pipeline: str = "Body-Reference",
        status: str = "SUCCESS",
    ) -> None:
        folder.mkdir(parents=True)
        (folder / "ask_manifest.json").write_text(json.dumps({
            "ask_id": ask_id,
            "worker_type": "manual_chatgpt_render",
            "engine_profile": engine_profile,
            "pipeline": pipeline,
        }), encoding="utf-8")
        answer = {"ask_id": ask_id, "status": status}
        if refinement is not None:
            answer["chatgpt_refinement"] = refinement
        (folder / "answer_manifest.json").write_text(json.dumps(answer), encoding="utf-8")

    def test_summarizes_explicit_telemetry_and_separates_legacy_unknowns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            live = root / "Queue" / "Manual_Render_Queue" / "Answer"
            archive = root / "Queue" / "Zet_File_Proxy_State" / "Archive" / "Harvested" / "2026-09-09"
            self._answer(live / "first", "first", refinement={
                "schema_version": 1, "required": False, "additional_image_generations": 0, "note": "",
            })
            self._answer(archive / "refined", "refined", refinement={
                "schema_version": 1, "required": True, "additional_image_generations": 2, "note": "orientation",
            }, pipeline="Scene-Appearance")
            self._answer(archive / "legacy", "legacy", refinement=None, engine_profile="chatgpt_images_2_0_v1")
            self._answer(archive / "failed", "failed", refinement=None, status="ERROR")
            self._answer(archive / "first-copy", "first", refinement={
                "schema_version": 1, "required": False, "additional_image_generations": 0, "note": "",
            })

            summary = ManualRenderMetricsService(self._config(root)).summary()

            self.assertEqual("2026-09-09", summary["telemetry_start_date"])
            self.assertEqual(2, summary["classified_count"])
            self.assertEqual(1, summary["unknown_count"])
            self.assertEqual(1, summary["first_pass_count"])
            self.assertEqual(1, summary["refined_count"])
            self.assertEqual(0.5, summary["first_pass_rate"])
            self.assertEqual(1.0, summary["average_additional_image_generations"])
            self.assertEqual(2.0, summary["average_when_refined"])
            self.assertEqual(
                ["Body-Reference", "Scene-Appearance"],
                [group["value"] for group in summary["by_pipeline"]],
            )
