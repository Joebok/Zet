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

    def test_comfyui_render_controls_validate_and_recreate_recipe(self) -> None:
        controls = PromptEvolutionService._render_controls({
            "denoise": 0.6,
            "control_preprocessor": "depth",
            "controlnet_model": "depth.safetensors",
            "control_strength": 0.75,
            "control_start": 0.1,
            "control_end": 0.9,
        }, {}, 6.5, 30)
        self.assertEqual("depth", controls["control_preprocessor"])
        self.assertEqual(6.5, controls["cfg"])
        settings = PromptEvolutionService._recipe_creation_settings({
            "backend": "comfyui",
            "render_recipe": {
                "controls": controls,
                "inputs": [{"role": "prompt_evolution_pose", "path": "pose.png"}],
            },
        })
        self.assertEqual("comfyui", settings["backend"])
        self.assertEqual("pose.png", settings["pose_source_path"])
        with self.assertRaises(PromptEvolutionError):
            PromptEvolutionService._render_controls({
                "control_start": 0.9, "control_end": 0.5,
            }, {}, 7, 25)
        with self.assertRaisesRegex(PromptEvolutionError, "sdxl_depth.safetensors"):
            PromptEvolutionService._render_controls({
                "control_preprocessor": "dwpose", "controlnet_model": "sdxl_depth.safetensors",
            }, {}, 7, 25)

    def test_regression_check_contract_is_breaking_and_unambiguous(self) -> None:
        items = PromptEvolutionService._validated_checklist_items({"items": [{
            "id": "hair-black", "requirement": "Base hair is black",
            "question": "Is the base hair black?", "correction": "Use black base hair",
        }]})
        self.assertEqual("hair-black", items[0]["id"])
        self.assertNotIn("category", items[0])
        with self.assertRaises(PromptEvolutionError):
            PromptEvolutionService._validated_checklist_items({"items": [{"item": "legacy", "category": "hair"}]})
        questions = PromptEvolutionService._checklist_questions({"items": items})
        self.assertIn('"id": "hair-black"', questions)
        self.assertNotIn("1 [hair-black]", questions)
        schema = PromptEvolutionService._regression_check_schema(["hair-black"])
        self.assertEqual(["hair-black"], schema["properties"]["checks"]["items"]["properties"]["id"]["enum"])

    def test_regression_check_accepts_numbered_bracket_id_from_existing_run(self) -> None:
        checks = PromptEvolutionService._validate_checks({"checks": [{
            "id": "1 [hair-black]", "pass": True, "confidence": 0.9, "evidence": "visible black hair",
        }]}, {"hair-black"})
        self.assertEqual("hair-black", checks[0]["id"])

    def test_visual_report_has_no_scores_and_requires_paired_descriptions(self) -> None:
        report = PromptEvolutionService._validate_visual_report({
            "major_differences": [{"reference": "open overskirt", "candidate": "closed skirt"}],
            "secondary_differences": [], "stable_matches": ["black bob"],
        })
        self.assertNotIn("score", report)
        with self.assertRaises(PromptEvolutionError):
            PromptEvolutionService._validate_visual_report({
                "major_differences": [{"reference": "open overskirt"}],
                "secondary_differences": [], "stable_matches": [],
            })

    def test_synthesis_and_diagnosis_limit_work_to_three_items(self) -> None:
        synthesis = {name: [] for name in (
            "recurrent_deviations", "intermittent_deviations", "isolated_deviations",
            "stable_successes", "cross_feature_patterns", "next_round_priorities",
        )}
        PromptEvolutionService._validate_synthesis(synthesis)
        synthesis["next_round_priorities"] = [1, 2, 3, 4]
        with self.assertRaises(PromptEvolutionError):
            PromptEvolutionService._validate_synthesis(synthesis)

    def test_synthesis_promotes_recurring_findings_when_model_omits_priorities(self) -> None:
        synthesis = {
            "recurrent_deviations": [{
                "finding": "coat color drift", "seeds": [1, 2], "observer_agreement": "dual",
            }],
            "intermittent_deviations": [], "isolated_deviations": [],
            "stable_successes": [], "cross_feature_patterns": [], "next_round_priorities": [],
        }
        validated = PromptEvolutionService._validate_synthesis(synthesis)
        self.assertEqual("coat color drift", validated["next_round_priorities"][0]["problem"])

    def test_diagnosis_retry_uses_safe_defaults_and_warnings(self) -> None:
        response = {"interventions": [{
            "id": "i1", "observed_pattern": "hair mismatch", "prompt": "positive", "action": "replace",
            "relevant_wording": "", "proposed_wording": "short black bob", "diagnosis": "default drift",
            "rationale": "more explicit", "confidence": "High", "regression_risk": "",
        }]}
        with self.assertRaises(PromptEvolutionError):
            PromptEvolutionService._validate_diagnosis(response)
        warnings = []
        normalized = PromptEvolutionService._validate_diagnosis(response, lenient=True, warnings=warnings)
        self.assertEqual("add", normalized["interventions"][0]["action"])
        self.assertEqual("Not supplied.", normalized["interventions"][0]["regression_risk"])
        self.assertTrue(any("treated replace as add" in warning for warning in warnings))

    def test_editor_accepts_only_eligible_high_confidence_changes(self) -> None:
        edited = PromptEvolutionService._validate_edit({
            "positive_core": "black bob, open overskirt", "negative_core": "blonde hair",
            "changes": [{"intervention_id": "i1", "old": "closed skirt", "new": "open overskirt", "reason": "recurrent"}],
        }, "black bob, closed skirt", "blonde hair", {"i1"})
        self.assertEqual("black bob, open overskirt", edited["positive_core"])
        with self.assertRaises(PromptEvolutionError):
            PromptEvolutionService._validate_edit({
                "positive_core": "black bob, open overskirt", "negative_core": "blonde hair",
                "changes": [{"intervention_id": "medium", "old": "", "new": "x", "reason": ""}],
            }, "black bob", "blonde hair", {"i1"})

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

    def test_comfyui_worker_error_is_condensed_for_dashboard(self) -> None:
        message = "ComfyUI execution failed: " + __import__("json").dumps({
            "messages": [["execution_error", {"exception_message": "shape mismatch\nuse an SDXL ControlNet"}]],
        })
        self.assertEqual(
            "shape mismatch\nuse an SDXL ControlNet",
            PromptEvolutionService._concise_render_error(message),
        )
        shape_message = "ComfyUI execution failed: " + __import__("json").dumps({
            "messages": [["execution_error", {"exception_message": "mat1 and mat2 shapes cannot be multiplied (1x2 and 3x4)"}]],
        })
        self.assertIn("incompatible model families", PromptEvolutionService._concise_render_error(shape_message))

    def test_fixed_seeds_are_reused_and_fresh_seeds_are_replaced(self) -> None:
        run = {"fixed_seeds": [1, 2, 3], "batch_size": 6, "fixed_seed_count": 3}
        fresh = PromptEvolutionService._new_fresh_seeds(run)
        self.assertEqual(3, len(fresh))
        self.assertFalse(set(fresh) & {1, 2, 3})

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

    def test_observing_requeues_archived_worker_failures(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            batch_path = root / "batches" / "000"
            batch_path.mkdir(parents=True)
            PromptEvolutionService._write_json(batch_path / "batch.json", {
                "observations": [{
                    "seed": 11, "file": str(batch_path / "candidate.png"),
                    "critics": {"a": {"ask_id": "failed-critic", "output": str(batch_path / "critic.json")}},
                }],
            })
            run = {"run_id": "run-1", "root": str(root), "current_batch": 0, "status": "OBSERVING"}
            service = object.__new__(PromptEvolutionService)
            service._find_run = Mock(return_value=run)
            service._proxy_failures = Mock(return_value={"failed-critic": "worker interrupted"})
            service._retry_observation_output = Mock(return_value=True)
            service.detail = Mock(return_value=run)

            service._advance_v3_unlocked("run-1")

            service._retry_observation_output.assert_called_once()

    def test_detail_exposes_partial_critic_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            batch_path = root / "batches" / "000"
            batch_path.mkdir(parents=True)
            critic = batch_path / "critic.json"
            critic.write_text('{"stable_matches":["black hair"]}', encoding="utf-8")
            PromptEvolutionService._write_json(batch_path / "batch.json", {
                "prompt_version_id": "prompt-000", "renders": [],
                "observations": [{
                    "seed": 11, "seed_role": "fixed", "file": "candidate.png",
                    "critics": {
                        "a": {"output": str(critic)},
                        "b": {"output": str(batch_path / "pending.json")},
                    },
                }],
            })
            service = object.__new__(PromptEvolutionService)
            service._find_run = Mock(return_value={"run_id": "run-1", "root": str(root)})

            result = service.detail("run-1")["batches"][0]["observation_results"][0]

            self.assertEqual(["black hair"], result["critics"]["a"]["stable_matches"])
            self.assertEqual(["critic_b"], result["pending"])

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

    def test_manual_resume_does_not_queue_a_third_llm_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run = {
                "root": str(root), "current_batch": 1, "status": "FAILED", "failed_stage": "DIAGNOSING",
                "error": "missing relevant wording", "validation_retries": {"1:DIAGNOSING": 1},
            }
            service = object.__new__(PromptEvolutionService)
            service._find_run = Mock(return_value=run)
            service._save_run = Mock()
            service.advance_run = Mock(return_value={"status": "EDITING"})
            service._retry_v3_validation = Mock()

            result = service.retry("run-1")

            self.assertEqual("EDITING", result["status"])
            self.assertEqual(1, run["validation_retries"]["1:DIAGNOSING"])
            service._retry_v3_validation.assert_not_called()

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

    def test_list_runs_excludes_legacy_schema(self) -> None:
        service = object.__new__(PromptEvolutionService)
        service._run_paths = Mock(return_value=[])
        self.assertEqual([], service.list_runs())

    def test_templates_are_score_free_and_critics_do_not_receive_prompts(self) -> None:
        root = Path(__file__).resolve().parents[1] / "Config" / "Prompt_Evolution"
        critic = (root / "visual_critic.md").read_text(encoding="utf-8")
        synthesis = (root / "batch_synthesis.md").read_text(encoding="utf-8")
        self.assertNotIn("{{POSITIVE", critic)
        self.assertNotIn("{{NEGATIVE", critic)
        self.assertNotIn('"score"', critic.casefold())
        self.assertIn("{{BATCH_EVIDENCE}}", synthesis)
