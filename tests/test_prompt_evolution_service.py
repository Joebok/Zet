from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock
import tempfile

from zet.services.prompt_evolution_service import PromptEvolutionError, PromptEvolutionService, RUN_VERSION


class PromptEvolutionServiceV3Tests(TestCase):
    def test_prompt_evolution_models_come_from_global_config(self) -> None:
        service = object.__new__(PromptEvolutionService)
        service.app = SimpleNamespace(config=SimpleNamespace(
            ai_prompt_evolution_critic_model_a="critic-a",
            ai_prompt_evolution_critic_model_b="critic-b",
            ai_prompt_evolution_analysis_model="analysis",
            ai_prompt_evolution_check_model="check",
        ))

        self.assertEqual({
            "critic_model_a": "critic-a",
            "critic_model_b": "critic-b",
            "analysis_model": "analysis",
            "check_model": "check",
        }, service._configured_models())









    def test_render_completion_queues_two_isolated_critics_and_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            batch_path = root / "batches" / "000"
            batch_path.mkdir(parents=True)
            reference = root / "reference.png"
            reference.write_bytes(b"image")
            renders = []
            for seed, role in ((11, "fixed"), (22, "fresh")):
                image = batch_path / f"{seed}.png"
                image.write_bytes(b"image")
                renders.append({"seed": seed, "seed_role": role, "file": str(image)})
            PromptEvolutionService._write_json(batch_path / "batch.json", {
                "version": 3, "index": 0, "prompt_version_id": "prompt-000",
                "positive_core": "secret positive", "negative_core": "secret negative",
                "renders": renders, "status": "RENDERING",
            })
            PromptEvolutionService._write_json(root / "checklist_snapshot.json", {"items": [{
                "id": "hair", "requirement": "black hair", "question": "Is hair black?", "correction": "use black hair",
            }]})
            run = {
                "version": 3, "run_id": "run-1", "root": str(root), "status": "RENDERING", "current_batch": 0,
                "reference_image": str(reference), "critic_model_a": "a", "critic_model_b": "b",
                "analysis_model": "analysis", "check_model": "check",
            }
            service = object.__new__(PromptEvolutionService)
            service._find_run = Mock(return_value=run)
            service._format_template = Mock(side_effect=lambda current, name, values: f"{name}:{values}")
            queued = []
            service._queue_ollama = Mock(side_effect=lambda current, **kwargs: queued.append(kwargs) or f"ask-{len(queued)}")
            service._save_run = Mock()
            service.detail = Mock(return_value=run)

            service._advance_v3_unlocked("run-1")

            self.assertEqual(6, len(queued))
            self.assertEqual(4, sum(item["task"].startswith("critic_") for item in queued))
            for item in queued:
                self.assertNotIn("secret positive", item["prompt"])
                self.assertNotIn("secret negative", item["prompt"])
            self.assertTrue(all(len(item["images"]) == 2 for item in queued))

    def test_render_worker_error_fails_run_instead_of_stalling(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            batch_path = root / "batches" / "000"
            batch_path.mkdir(parents=True)
            PromptEvolutionService._write_json(batch_path / "batch.json", {
                "renders": [{"ask_id": "render-1", "seed": 11, "file": str(batch_path / "missing.png")}],
                "status": "RENDERING",
            })
            run = {"run_id": "run-1", "root": str(root), "status": "RENDERING", "current_batch": 0}
            service = object.__new__(PromptEvolutionService)
            service._find_run = Mock(return_value=run)
            service._render_failure = Mock(return_value={
                "ask_id": "render-1", "error_message": "model families do not match",
            })
            service._save_run = Mock()
            service.detail = Mock(return_value=run)

            service._advance_v3_unlocked("run-1")

            self.assertEqual("FAILED", run["status"])
            self.assertEqual("RENDERING", run["failed_stage"])
            self.assertIn("model families do not match", run["error"])



    def test_invalid_check_retries_only_that_check_without_requeueing_critics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            batch_path = root / "batches" / "000"
            batch_path.mkdir(parents=True)
            reference = root / "reference.png"
            candidate = batch_path / "candidate.png"
            reference.write_bytes(b"image")
            candidate.write_bytes(b"image")
            valid_report = '{"major_differences":[],"secondary_differences":[],"stable_matches":["hair"]}'
            critic_a, critic_b, check = (batch_path / "a.json", batch_path / "b.json", batch_path / "check.json")
            critic_a.write_text(valid_report, encoding="utf-8")
            critic_b.write_text(valid_report, encoding="utf-8")
            check.write_text('{"checks":[]}', encoding="utf-8")
            PromptEvolutionService._write_json(batch_path / "batch.json", {
                "observations": [{
                    "seed": 11, "seed_role": "fixed", "file": str(candidate),
                    "critics": {"a": {"output": str(critic_a)}, "b": {"output": str(critic_b)}},
                    "check": {"output": str(check)},
                }],
            })
            PromptEvolutionService._write_json(root / "checklist_snapshot.json", {"items": [{
                "id": "hair", "question": "Is the hair black?",
            }]})
            run = {
                "run_id": "run-1", "root": str(root), "current_batch": 0, "status": "OBSERVING",
                "validation_retries": {}, "reference_image": str(reference), "critic_model_a": "a",
                "critic_model_b": "b", "check_model": "check", "analysis_model": "analysis",
            }
            service = object.__new__(PromptEvolutionService)
            service._find_run = Mock(return_value=run)
            service._format_template = Mock(return_value="retry prompt")
            service._queue_ollama = Mock(return_value="retry-check")
            service._save_run = Mock()
            service.detail = Mock(return_value=run)

            service._advance_v3_unlocked("run-1")

            self.assertTrue(critic_a.exists())
            self.assertTrue(critic_b.exists())
            self.assertFalse(check.exists())
            self.assertEqual("check_11", service._queue_ollama.call_args.kwargs["task"])
            self.assertEqual("OBSERVING", run["status"])
            self.assertTrue(any("rejected regression check" in event["message"] for event in run["activity_log"]))



    def test_synthesis_retry_includes_prior_failure_and_is_queued_only_once(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            batch_path = root / "batches" / "000"
            batch_path.mkdir(parents=True)
            rejected = batch_path / "batch_synthesis.json"
            rejected.write_text("{}", encoding="utf-8")
            PromptEvolutionService._write_json(batch_path / "batch.json", {
                "candidates": [{"seed": 11}], "synthesis": {"output": str(rejected)},
            })
            run = {
                "root": str(root), "current_batch": 0, "status": "SYNTHESIZING",
                "validation_retries": {}, "analysis_model": "analysis",
            }
            service = object.__new__(PromptEvolutionService)
            service._format_template = Mock(return_value="original synthesis prompt")
            service._queue_ollama = Mock(return_value="retry-synthesis")
            service._save_run = Mock()

            self.assertTrue(service._retry_v3_validation(run, "SYNTHESIZING", "missing priorities"))
            retry_prompt = service._queue_ollama.call_args.kwargs["prompt"]
            self.assertIn("The prior response was rejected: missing priorities", retry_prompt)
            self.assertFalse(service._retry_v3_validation(run, "SYNTHESIZING", "still invalid"))
            self.assertEqual(1, service._queue_ollama.call_count)


    def test_final_selection_persists_selected_prompt_version(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            batch_path = root / "batches" / "001"
            batch_path.mkdir(parents=True)
            PromptEvolutionService._write_json(batch_path / "batch.json", {
                "prompt_version_id": "prompt-001", "positive_core": "black bob",
                "negative_core": "blonde hair", "evaluation_wrapper": {"positive_terms": ["full body"]},
            })
            run = {"version": RUN_VERSION, "run_id": "run-1", "root": str(root), "status": "AWAITING_FINAL_REVIEW", "checkpoint": "model"}
            service = object.__new__(PromptEvolutionService)
            service._find_run = Mock(return_value=run)
            service._save_run = Mock(side_effect=lambda value: PromptEvolutionService._write_json(root / "run.json", value))
            service.detail = Mock(side_effect=lambda _: run)

            service.select_prompt_version("run-1", "prompt-001", "best across seeds")

            core = PromptEvolutionService._read_json(root / "prompt_core.json")
            self.assertEqual("prompt-001", core["prompt_version_id"])
            self.assertEqual("COMPLETE", run["status"])

    def test_prompt_review_persists_manual_edit_and_starts_next_batch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            batch_path = root / "batches" / "000"
            batch_path.mkdir(parents=True)
            PromptEvolutionService._write_json(batch_path / "batch.json", {
                "index": 0, "status": "AWAITING_PROMPT_REVIEW",
                "edit": {"positive_core": "proposed coat", "negative_core": "blue coat"},
            })
            run = {
                "root": str(root), "current_batch": 0, "status": "AWAITING_PROMPT_REVIEW",
                "fixed_seeds": [11], "fresh_seeds": [22], "seeds": [11, 22],
            }
            service = object.__new__(PromptEvolutionService)
            service._find_run = Mock(return_value=run)
            service._save_run = Mock()
            service._log = Mock()
            service._new_fresh_seeds = Mock(return_value=[33])
            service._start_batch = Mock()
            service.detail = Mock(return_value={"status": "RENDERING"})

            result = service.accept_prompt_review("run-1", "edited red coat", "blue coat")

            review = PromptEvolutionService._read_json(batch_path / "batch.json")["prompt_review"]
            self.assertTrue(review["manually_edited"])
            self.assertEqual("edited red coat", review["accepted_positive_core"])
            self.assertEqual(1, run["current_batch"])
            service._start_batch.assert_called_once_with(run, "edited red coat", "blue coat")
            self.assertEqual("RENDERING", result["status"])
