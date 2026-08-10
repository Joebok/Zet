import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import zipfile

from PIL import Image, ImageDraw

from zet.services.prompt_evolution_service import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    DEFAULT_CHECKLIST_MODEL,
    DEFAULT_VISION_MODEL,
    PromptEvolutionError,
    PromptEvolutionPlaceholderResponse,
    PromptEvolutionService,
)
from zet.services.stable_matrix_api_compiler import compile_stable_matrix_api_call
from AI_Manager.local_image_proxy_worker import render_image_kwargs
from zet.services.view_service import ViewService


class PromptEvolutionServiceTests(unittest.TestCase):
    def test_create_run_requires_at_least_two_images_and_batches(self) -> None:
        service = object.__new__(PromptEvolutionService)
        service._source_asset = Mock(return_value=Mock())

        for payload in ({"batch_size": 1, "total_batches": 2}, {"batch_size": 2, "total_batches": 1}):
            with self.subTest(payload=payload), self.assertRaisesRegex(
                PromptEvolutionError, "Batch size must be 2–10 and total batches must be 2–20"
            ):
                service.create_run(payload)

    def test_ollama_json_response_uses_raw_transport_file_for_service_repair(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            class Proxy:
                def create_staging(self, ask_id):
                    path = root / f".{ask_id}.staging"
                    path.mkdir()
                    return path

                def publish(self, staging, ask_id, worker_type):
                    staging.rename(root / ask_id)

            image = root / "reference.png"
            image.write_bytes(b"image")
            output = root / "evaluation_1.json"
            service = object.__new__(PromptEvolutionService)
            service.proxy = Proxy()
            run = {"run_id": "run-1", "character": "Tsaeytte", "phase": "Adult", "model": "vision-model"}

            ask_id = service._queue_ollama(run, task="evaluate_1", prompt="prompt", output=output, images=[image])
            manifest = PromptEvolutionService._read_json(root / ask_id / "ask_manifest.json")

            self.assertEqual("evaluation_1.json.raw.txt", manifest["expected_output"])
            self.assertEqual("evaluation_1.json", manifest["target_output_file"])
            self.assertTrue(manifest["json_output"])

            schema_output = root / "refinement.json"
            schema = {"type": "object", "required": ["operations"]}
            ask_id = service._queue_ollama(
                run, task="refinement", prompt="prompt", output=schema_output, images=[image],
                response_schema=schema, temperature=0,
            )
            manifest = PromptEvolutionService._read_json(root / ask_id / "ask_manifest.json")
            self.assertEqual(schema, manifest["response_schema"])
            self.assertEqual(0, manifest["ollama_temperature"])

    def test_audit_bundle_contains_run_source_proxy_prompts_responses_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            run_root = root / "run"
            batch_root = run_root / "batches" / "000"
            batch_root.mkdir(parents=True)
            source = root / "locked.png"
            source.write_bytes(b"source")
            run = {
                "run_id": "run-1", "root": str(run_root), "source_image": str(source),
                "created_at": "2026-08-09T10:00:00", "status": "COMPLETE",
            }
            PromptEvolutionService._write_json(run_root / "run.json", run)
            PromptEvolutionService._write_json(batch_root / "batch.json", {"index": 0, "status": "REVIEWED"})
            queue_root = root / "queue"
            record = queue_root / "Zet_File_Proxy_State" / "Archive" / "Harvested" / "2026-08-09" / "Ask_Prompt_Evolution_run-1_00_test"
            record.mkdir(parents=True)
            (record / "OLLAMA_PROMPT.md").write_text("exact prompt", encoding="utf-8")
            (record / "response.json").write_text('{"answer":true}', encoding="utf-8")
            PromptEvolutionService._write_json(record / "ask_manifest.json", {
                "ask_id": record.name, "task_type": "prompt_evolution_test", "ollama_model": "model-1",
            })
            PromptEvolutionService._write_json(record / "job.json", {"created_at": "2026-08-09T10:01:00Z"})
            PromptEvolutionService._write_json(record / "answer_manifest.json", {
                "started_at": "2026-08-09T10:01:01", "completed_at": "2026-08-09T10:01:02", "status": "SUCCESS",
            })
            service = object.__new__(PromptEvolutionService)
            service.app = SimpleNamespace(config=SimpleNamespace(base_ai_queue_path=str(queue_root)))
            service._find_run = Mock(return_value=run)

            bundle = service.create_audit_bundle("run-1")
            try:
                with zipfile.ZipFile(bundle) as archive:
                    names = set(archive.namelist())
                    self.assertIn("run/run.json", names)
                    self.assertIn("inputs/locked_source.png", names)
                    prompt_path = f"proxy/harvested/{record.name}/OLLAMA_PROMPT.md"
                    self.assertEqual("exact prompt", archive.read(prompt_path).decode("utf-8"))
                    manifest = json.loads(archive.read("audit_manifest.json"))
                self.assertEqual("run-1", manifest["run_id"])
                self.assertEqual("model-1", manifest["proxy_records"][0]["model"])
                self.assertEqual(["ask_created", "ask_started", "ask_completed"], [event["event"] for event in manifest["events"] if event["event"].startswith("ask_")])
                self.assertEqual(0, manifest["batches"][0]["index"])
            finally:
                bundle.unlink(missing_ok=True)

    def test_replay_experiment_snapshots_source_and_queues_repeated_evaluations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            run_root = base / "Prompt_Evolution" / "run-1"
            batch_root = run_root / "batches" / "000"
            batch_root.mkdir(parents=True)
            reference = run_root / "reference.png"
            candidate = batch_root / "candidate.png"
            reference.write_bytes(b"reference")
            candidate.write_bytes(b"candidate")
            PromptEvolutionService._write_json(batch_root / "batch.json", {
                "positive_core": "black bob", "negative_core": "blonde hair",
                "positive_core_terms": [{"id": "p001", "text": "black bob"}],
                "negative_core_terms": [{"id": "n001", "text": "blonde hair"}],
                "candidates": [{"seed": 7, "file": str(candidate)}],
            })
            run = {
                "run_id": "run-1", "root": str(run_root), "reference_image": str(reference),
                "character": "Tsaeytte", "phase": "Adult", "model": "vision", "checkpoint": "checkpoint",
            }
            service = object.__new__(PromptEvolutionService)
            service._find_run = Mock(return_value=run)
            service.template = Mock(return_value="candidate {{SEED}}")
            service._queue_ollama = Mock(side_effect=lambda *args, **kwargs: f"ask-{kwargs['task']}")

            experiment = service.start_replay_experiment("run-1", 0, 7, 3)

            self.assertEqual("EVALUATING", experiment["status"])
            self.assertEqual(3, len(experiment["evaluations"]))
            self.assertEqual("candidate 7", experiment["evaluation_prompt"])
            self.assertTrue((Path(experiment["root"]) / "experiment.json").is_file())

    def test_scoped_checklists_use_adjacent_json_sidecars_and_merge_by_specificity(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            phase_path = root / "Characters" / "Tsaeytte" / "Adult"
            phase_path.mkdir(parents=True)
            character_template = phase_path / "Character.md"
            costume_template = phase_path / "Costume_Canonical_Adventure_Gear.md"
            character_template.write_text("# Character\n", encoding="utf-8")
            costume_template.write_text("# Costume\n", encoding="utf-8")
            templates_root = root / "Config" / "Prompt_Evolution"
            templates_root.mkdir(parents=True)
            PromptEvolutionService._write_json(templates_root / "checklist.json", {
                "items": [{"item": "Hair color is incorrect", "category": "hair", "max_rating": 4}],
            })
            service = object.__new__(PromptEvolutionService)
            service.templates_root = templates_root
            service.app = SimpleNamespace(path_service=SimpleNamespace(
                character_template_path=lambda character, phase: character_template,
                costume_template_path=lambda character, phase, costume: costume_template,
            ))

            service.save_scoped_checklist("character", "Tsaeytte", "Adult", "Canonical Adventure Gear", {
                "items": [{"item": "Hair color is incorrect", "category": "hair", "max_rating": 3}],
            })
            result = service.save_scoped_checklist("costume", "Tsaeytte", "Adult", "Canonical Adventure Gear", {
                "items": [{"item": "Boots are open toed", "category": "accessories_footwear", "max_rating": 6}],
            })

            self.assertTrue((phase_path / "Character.prompt_evolution_checklist.json").is_file())
            self.assertTrue((phase_path / "Costume_Canonical_Adventure_Gear.prompt_evolution_checklist.json").is_file())
            self.assertEqual(2, len(result["merged"]["items"]))
            hair = next(item for item in result["merged"]["items"] if item["category"] == "hair")
            self.assertEqual(3, hair["max_rating"])
            self.assertEqual("character", hair["scope"])
            self.assertEqual("costume", result["merged"]["items"][1]["scope"])

    def test_scoped_checklist_rejects_invalid_category_and_rating(self) -> None:
        with self.assertRaises(PromptEvolutionError):
            PromptEvolutionService._validated_checklist_items({
                "items": [{"item": "Bad rule", "category": "unknown", "max_rating": 11}],
            })

    def test_checklist_statements_become_direct_numbered_questions(self) -> None:
        questions = PromptEvolutionService._checklist_questions({"items": [
            {"item": "Hair color is incorrect"},
            {"item": "Hair is not black"},
            {"item": "Boots are open toed"},
        ]})
        self.assertEqual(
            "1 - Is the hair color incorrect?\n2 - Is the hair not black?\n3 - Are the boots open toed?",
            questions,
        )

    def test_checklist_uses_explicit_question_without_rewriting(self) -> None:
        questions = PromptEvolutionService._checklist_questions({"items": [{
            "item": "Hair is not black",
            "question": "Is the base hair color non-black after excluding reflected light?",
        }]})
        self.assertEqual("1 - Is the base hair color non-black after excluding reflected light?", questions)

    def test_reference_derivative_is_subject_aware_and_exact_size(self) -> None:
        service = object.__new__(PromptEvolutionService)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.png"
            output = root / "reference.png"
            image = Image.new("RGB", (1200, 900), "white")
            ImageDraw.Draw(image).rectangle((780, 80, 1060, 850), fill="black")
            image.save(source)

            crop = service._reference_derivative(source, output)

            with Image.open(output) as derivative:
                self.assertEqual((CANVAS_WIDTH, CANVAS_HEIGHT), derivative.size)
            self.assertEqual("turnaround_bbox_padded_contain", crop["crop_method"])
            self.assertGreater(crop["crop_box"][0], 0)
            self.assertGreater(crop["crop_box"][2] - crop["crop_box"][0], crop["subject_bounds"][2] - crop["subject_bounds"][0])
            self.assertEqual(50, crop["detection_tolerance"])
            self.assertEqual((1200, 900), Image.open(source).size)

    def test_reference_derivative_falls_back_for_blank_image(self) -> None:
        service = object.__new__(PromptEvolutionService)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.png"
            output = root / "reference.png"
            Image.new("RGB", (800, 800), "white").save(source)

            crop = service._reference_derivative(source, output)

            self.assertEqual("center_fallback", crop["crop_method"])
            self.assertEqual([100, 0, 700, 800], crop["crop_box"])

    def test_refinement_applies_all_valid_operations(self) -> None:
        service = object.__new__(PromptEvolutionService)
        positive, negative, applied = service._apply_operations(
            "red hair, green coat",
            "blue coat",
            {
                "positive_operations": [{"action": "edit", "old": "green coat", "new": "dark green coat"}],
                "negative_operations": [{"action": "add", "new": "blonde hair"}],
            },
        )
        self.assertEqual("red hair, dark green coat", positive)
        self.assertEqual("blue coat, blonde hair", negative)
        self.assertEqual(2, len(applied))
        positive, _, applied = service._apply_operations(
            "one", "two", {"positive_operations": [{"action": "add", "new": str(index)} for index in range(3)]},
        )
        self.assertEqual("one, 0, 1, 2", positive)
        self.assertEqual(3, len(applied))

    def test_refinement_unmatched_edit_becomes_addition(self) -> None:
        service = object.__new__(PromptEvolutionService)
        positive, _, applied = service._apply_operations(
            "red hair, green coat", "blue coat",
            {"positive_operations": [{"action": "edit", "old": "chin-length bob", "new": "chin-length bob curving inward under chin"}]},
        )
        self.assertEqual("red hair, green coat, chin-length bob curving inward under chin", positive)
        self.assertEqual("add", applied[0]["resolved_action"])

    def test_v2_refinement_uses_stable_term_ids_and_rejects_noops(self) -> None:
        positive, negative, applied = PromptEvolutionService._apply_term_operations(
            [{"id": "p001", "text": "solid black bob"}, {"id": "p002", "text": "teal crop top"}],
            [{"id": "n001", "text": "blonde hair"}],
            {"operations": [
                {"target": "positive", "action": "edit", "term_id": "p001", "new": "(solid black chin-length bob:1.25)", "category": "hair"},
                {"target": "negative", "action": "add", "term_id": "", "new": "purple hair", "category": "hair"},
            ]},
            {"hair"},
            [{"category": "hair", "correction": "Strengthen solid black hair and exclude purple hair."}],
        )
        self.assertEqual("(solid black chin-length bob:1.25)", positive[0]["text"])
        self.assertEqual("n002", negative[-1]["id"])
        self.assertEqual(2, len(applied))
        with self.assertRaisesRegex(PromptEvolutionError, "no-op"):
            PromptEvolutionService._apply_term_operations(
                [{"id": "p001", "text": "black hair"}], [],
                {"operations": [{"target": "positive", "action": "edit", "term_id": "p001", "new": "black hair", "category": "hair"}]},
                {"hair"},
            )

    def test_v2_refinement_strengthens_duplicate_terms_and_rejects_unknown_ids(self) -> None:
        base = [{"id": "p001", "text": "solid black hair"}]
        with self.assertRaisesRegex(PromptEvolutionError, "unknown term ID"):
            PromptEvolutionService._apply_term_operations(
                base, [], {"operations": [{"target": "positive", "action": "edit", "term_id": "p999", "new": "black bob", "category": "hair"}]}, {"hair"},
            )
        positive, _, applied = PromptEvolutionService._apply_term_operations(
            base, [], {"operations": [
                {"target": "positive", "action": "add", "term_id": "", "new": "solid black hair", "category": "hair"},
                {"target": "positive", "action": "add", "term_id": "", "new": "solid black hair", "category": "hair"},
            ]}, {"hair"},
        )
        self.assertEqual("(solid black hair:1.4)", positive[0]["text"])
        self.assertEqual(["strengthen", "strengthen"], [item["action"] for item in applied])
        semantic_variant, _, _ = PromptEvolutionService._apply_term_operations(
            base, [], {"operations": [{
                "target": "positive", "action": "edit", "term_id": "p001",
                "new": "black hair with natural brown undertones and subtle warm highlights", "category": "hair",
            }]}, {"hair"}, [{"category": "hair", "correction": "Preserve solid black hair."}],
        )
        self.assertEqual("black hair with natural brown undertones and subtle warm highlights", semantic_variant[0]["text"])
        with self.assertRaisesRegex(PromptEvolutionError, "visual traits"):
            PromptEvolutionService._apply_term_operations(
                base, [], {"operations": [{"target": "positive", "action": "edit", "term_id": "p001", "new": "brown hair removed", "category": "hair"}]}, {"hair"},
            )
        with self.assertRaisesRegex(PromptEvolutionError, "atomic"):
            PromptEvolutionService._apply_term_operations(
                base, [], {"operations": [{"target": "negative", "action": "add", "term_id": "", "new": "brown hair; purple hair", "category": "hair"}]}, {"hair"},
            )

    def test_refinement_analysis_preserves_guarded_preview_and_reports_every_error(self) -> None:
        positive = [{"id": "p001", "text": "blue eyes"}, {"id": "p002", "text": "ruffled top"}]
        negative = [{"id": "n001", "text": "glowing eyes"}]
        corrections = [
            {"category": "eyes", "correction": "use natural dark eyes"},
            {"category": "garment_pieces", "correction": "use a simple gathered top"},
        ]
        guarded = PromptEvolutionService._analyze_term_operations(
            positive, negative, {"operations": [
                {"target": "positive", "action": "edit", "term_id": "p001", "new": "natural dark eyes"},
                {"target": "negative", "action": "add", "term_id": "", "new": "heavy eyeliner", "category": "eyes"},
            ]}, {"eyes", "garment_pieces"}, corrections,
        )
        self.assertFalse(guarded["strict_valid"])
        self.assertTrue(guarded["guarded_override_allowed"])
        self.assertEqual("complete", guarded["preview_status"])
        self.assertIn("natural dark eyes", guarded["positive_core"])
        self.assertEqual(["missing_category"], [item["code"] for item in guarded["validation_errors"]])

        blocked = PromptEvolutionService._analyze_term_operations(
            positive, negative, {"operations": [
                {"target": "positive", "action": "edit", "term_id": "p999", "new": "natural dark eyes"},
                {"target": "negative", "action": "add", "term_id": "", "new": "eye glow, heavy eyeliner", "category": "eyes"},
            ]}, {"eyes", "garment_pieces"}, corrections,
        )
        self.assertFalse(blocked["guarded_override_allowed"])
        self.assertEqual("baseline", blocked["preview_status"])
        self.assertEqual({"missing_category", "unknown_term_id", "non_atomic_term"}, {item["code"] for item in blocked["validation_errors"]})

    def test_guarded_refinement_review_continues_without_changing_batch_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            batch_path = root / "batches" / "000"
            batch_path.mkdir(parents=True)
            response = {"operations": [
                {"target": "positive", "action": "edit", "term_id": "p001", "new": "natural dark eyes"},
            ]}
            batch = {"index": 0, "refinement_attempts": [{
                "attempt_id": "ollama-03", "response": response, "accepted": False,
            }]}
            PromptEvolutionService._write_json(batch_path / "batch.json", batch)
            incumbent = {
                "positive_core": "blue eyes", "negative_core": "glowing eyes",
                "positive_core_terms": [{"id": "p001", "text": "blue eyes"}],
                "negative_core_terms": [{"id": "n001", "text": "glowing eyes"}],
            }
            run = {
                "run_id": "run-1", "root": str(root), "status": "AWAITING_REFINEMENT_REVIEW",
                "current_batch": 0, "total_batches": 4, "incumbent": incumbent,
                "exploration_incumbent": incumbent,
                "pending_corrections": [{"category": "eyes", "correction": "use natural dark eyes"}],
            }
            service = object.__new__(PromptEvolutionService)
            service._find_run = Mock(return_value=run)
            service._start_batch = Mock()
            service.detail = Mock(side_effect=lambda _: run)

            result = service.accept_refinement_review("run-1", "ollama-03", None, True)

            self.assertEqual(1, result["current_batch"])
            self.assertEqual(4, result["total_batches"])
            service._start_batch.assert_called_once_with(run, "natural dark eyes", "glowing eyes")
            saved = PromptEvolutionService._read_json(batch_path / "batch.json")
            self.assertTrue(saved["refinement_human_override"])
            self.assertEqual("ollama-03", saved["selected_refinement_attempt_id"])

    def test_prompt_text_edit_is_backed_into_structured_operations(self) -> None:
        incumbent = {
            "positive_core_terms": [{"id": "p001", "text": "blue eyes"}, {"id": "p002", "text": "ruffled top"}],
            "negative_core_terms": [{"id": "n001", "text": "glowing eyes"}],
        }
        attempt = {"response": {"operations": [{
            "target": "positive", "action": "edit", "term_id": "p001", "new": "natural dark eyes", "category": "eyes",
        }]}}
        corrections = [{"category": "eyes", "correction": "Use natural dark eyes."}]

        operations = PromptEvolutionService._operations_from_prompt_text(
            incumbent, attempt, "natural dark eyes, ruffled top", "glowing eyes, blue eyes", corrections,
        )
        analysis = PromptEvolutionService._analyze_term_operations(
            incumbent["positive_core_terms"], incumbent["negative_core_terms"], {"operations": operations}, {"eyes"}, corrections,
        )

        self.assertTrue(analysis["strict_valid"])
        self.assertEqual("natural dark eyes, ruffled top", analysis["positive_core"])
        self.assertEqual("glowing eyes, blue eyes", analysis["negative_core"])
        self.assertEqual(["edit", "add"], [item["action"] for item in operations])

    def test_refinement_review_detail_revalidates_stored_attempts_with_current_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            batch_path = root / "batches" / "000"
            batch_path.mkdir(parents=True)
            response = {"operations": [{
                "target": "positive", "action": "edit", "term_id": "p001",
                "new": "black hair with natural brown undertones and subtle warm highlights", "category": "hair",
            }]}
            PromptEvolutionService._write_json(batch_path / "batch.json", {
                "index": 0, "refinement_attempts": [{
                    "attempt_id": "ollama-01", "response": response, "strict_valid": False,
                    "validation_errors": [{"code": "contradictory_term"}],
                }],
            })
            incumbent = {
                "positive_core_terms": [{"id": "p001", "text": "solid black hair"}],
                "negative_core_terms": [],
            }
            run = {
                "run_id": "run-1", "root": str(root), "status": "AWAITING_REFINEMENT_REVIEW",
                "current_batch": 0, "incumbent": incumbent, "exploration_incumbent": incumbent,
                "pending_corrections": [{"category": "hair", "correction": "Preserve solid black hair."}],
            }
            service = object.__new__(PromptEvolutionService)
            service._find_run = Mock(return_value=run)

            detail = service.detail("run-1")

            attempt = detail["batches"][0]["refinement_attempts"][0]
            self.assertTrue(attempt["strict_valid"])
            self.assertEqual([], attempt["validation_errors"])
            self.assertIn("natural brown undertones", attempt["positive_core"])

    def test_term_ids_never_leak_into_prompt_text(self) -> None:
        positive, negative, _ = PromptEvolutionService._apply_term_operations(
            [{"id": "p001", "text": "p001: black bob"}], [],
            {"operations": [{"target": "negative", "action": "add", "term_id": "", "new": "n010: long hair", "category": "hair"}]},
            {"hair"},
        )
        self.assertEqual("black bob", positive[0]["text"])
        self.assertEqual("long hair", negative[0]["text"])
        self.assertEqual(
            "corset bodice, long ruffled sleeves",
            PromptEvolutionService._clean_prompt_terms("n010: corset bodice, n011: long ruffled sleeves"),
        )

    def test_v2_prompt_core_and_evaluation_wrapper_remain_separate(self) -> None:
        core = PromptEvolutionService._term_records("black bob, teal crop top", "p")
        composed = PromptEvolutionService._compose_prompt(core, ("full body shot", "gray background", "sharp focus"))
        self.assertEqual("black bob, teal crop top", ", ".join(item["text"] for item in core))
        self.assertIn("full body shot", composed)
        self.assertIn("gray background", composed)
        self.assertNotIn("gray background", [item["text"] for item in core])

    def test_initial_prompt_injection_wraps_original_prompts_once(self) -> None:
        positive, negative = PromptEvolutionService._initial_prompts("red hair, custom coat", "green hair")
        self.assertTrue(positive.startswith("masterpiece, top quality, full body shot, standing pose, centered, visible from head to toe, red hair, custom coat"))
        self.assertTrue(positive.endswith("semi-realistic anime proportions, large expressive detailed eyes, soft shaded skin, textured brushstrokes, sharp focus"))
        self.assertTrue(negative.startswith("(worst quality, low quality:1.4), cropped, out of frame"))
        self.assertTrue(negative.endswith("jpeg artifacts, green hair"))
        reinjected_positive, reinjected_negative = PromptEvolutionService._initial_prompts(positive, negative)
        self.assertEqual(positive, reinjected_positive)
        self.assertEqual(negative, reinjected_negative)

    def test_initial_prompt_injection_does_not_duplicate_existing_term(self) -> None:
        positive, _ = PromptEvolutionService._initial_prompts("masterpiece, red hair, sharp focus", "")
        self.assertEqual(1, positive.casefold().count("masterpiece"))
        self.assertEqual(1, positive.casefold().count("sharp focus"))

    def test_gray_background_injection_replaces_legacy_term(self) -> None:
        positive = PromptEvolutionService._ensure_gray_background("red hair, plain smooth neutral gray studio background")
        self.assertEqual("red hair, gray background", positive)
        self.assertEqual("red hair, gray background", PromptEvolutionService._ensure_gray_background(positive))

    def test_rejected_batch_tells_refiner_which_change_was_ineffective(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "metadata_snapshot.json").write_text("{}", encoding="utf-8")
            service = object.__new__(PromptEvolutionService)
            service._format_template = Mock(return_value="regular refinement prompt")
            service._queue_ollama = Mock(return_value="ask-1")
            run = {
                "root": str(root), "run_id": "run-1", "current_batch": 1, "total_batches": 3, "batch_size": 2,
                "reference_image": str(root / "reference.png"), "incumbent": {"positive_prompt": "old prompt", "negative_prompt": "old negative"},
            }
            batch = {
                "index": 1, "accepted": False, "winner_seed": 7,
                "attempted_mutation": [{"action": "edit", "old": "red hair", "new": "dark red hair"}],
                "candidates": [{"seed": 7, "character_categories": {"hair": 4}, "costume_categories": {"colors": 7},
                                "checklist_effects": [{"item": "Hair color is incorrect", "category": "hair", "max_rating": 4}]}],
            }

            service._queue_next_or_finish(run, batch)

            values = service._format_template.call_args.args[2]
            self.assertIn("had no beneficial effect", values["REJECTION_CONTEXT"])
            self.assertIn("dark red hair", values["REJECTION_CONTEXT"])
            self.assertIn("Do not repeat", values["REJECTION_CONTEXT"])
            queued_prompt = service._queue_ollama.call_args.kwargs["prompt"]
            self.assertTrue(queued_prompt.startswith("Additionally you must address this defect directly: The hair color is incorrect."))

    def test_v2_refinement_receives_two_corrections_and_both_images(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            reference = root / "reference.png"
            candidate_image = root / "candidate.png"
            reference.write_bytes(b"reference")
            candidate_image.write_bytes(b"candidate")
            service = object.__new__(PromptEvolutionService)
            service._format_template = Mock(return_value="concise v2 prompt")
            service._queue_ollama = Mock(return_value="ask-1")
            service._save_run = Mock()
            feedback = {
                "hair": {"score": 2, "correction": "strengthen solid black hair"},
                "colors": {"score": 3, "correction": "restore dark teal clothing"},
                "eyes": {"score": 7, "correction": "reduce eye size"},
            }
            selected = {
                "seed": 7, "file": str(candidate_image), "evaluation": {"category_feedback": feedback},
                "checklist_effects": [{"category": "hair", "correction": "exclude purple hair"}],
            }
            incumbent = {
                "positive_core": "black bob, teal top", "negative_core": "blonde hair",
                "positive_core_terms": [{"id": "p001", "text": "black bob"}, {"id": "p002", "text": "teal top"}],
                "negative_core_terms": [{"id": "n001", "text": "blonde hair"}],
            }
            run = {
                "strategy_version": 2, "root": str(root), "run_id": "run-1", "current_batch": 0,
                "total_batches": 3, "batch_size": 2, "reference_image": str(reference),
                "exploration_incumbent": incumbent, "incumbent": incumbent, "rejected_mutations": [],
            }
            batch = {"winner_seed": 7, "candidates": [selected], "improved_exploration": True}

            service._queue_next_or_finish(run, batch)

            values = service._format_template.call_args.args[2]
            self.assertIn("hair", values["CORRECTIONS"])
            self.assertIn("colors", values["CORRECTIONS"])
            self.assertIn("exclude purple hair", values["CORRECTIONS"])
            self.assertEqual([reference, candidate_image], service._queue_ollama.call_args.kwargs["images"])
            self.assertEqual("REFINING", run["status"])

    def test_third_invalid_refinement_pauses_for_review_and_preserves_attempts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            batch_path = root / "batches" / "000"
            batch_path.mkdir(parents=True)
            output = batch_path / "refinement.attempt-03.json"
            output.write_text("{}", encoding="utf-8")
            PromptEvolutionService._write_json(batch_path / "batch.json", {"index": 0, "refinement_attempts": [
                {"attempt_id": "ollama-01"}, {"attempt_id": "ollama-02"},
            ]})
            incumbent = {
                "positive_core": "blue eyes", "negative_core": "glowing eyes",
                "positive_core_terms": [{"id": "p001", "text": "blue eyes"}],
                "negative_core_terms": [{"id": "n001", "text": "glowing eyes"}],
            }
            run = {
                "run_id": "run-1", "root": str(root), "status": "REFINING", "current_batch": 0,
                "total_batches": 5, "strategy_version": 2, "incumbent": incumbent, "exploration_incumbent": incumbent,
                "pending_corrections": [{"category": "eyes", "correction": "use natural dark eyes"}],
                "refinement_output": str(output), "refinement_attempt_number": 3,
                "refinement_ask_id": "ask-3",
            }
            service = object.__new__(PromptEvolutionService)
            service._find_run = Mock(return_value=run)
            service._llm_json = Mock(return_value={"operations": [
                {"target": "positive", "action": "edit", "term_id": "p999", "new": "natural dark eyes", "category": "eyes"},
            ]})
            service._save_run = Mock()
            service.detail = Mock(side_effect=lambda _: run)

            service._advance_run_unlocked("run-1")

            self.assertEqual("AWAITING_REFINEMENT_REVIEW", run["status"], run.get("error"))
            self.assertEqual(5, run["total_batches"])
            saved = PromptEvolutionService._read_json(batch_path / "batch.json")
            self.assertEqual(["ollama-01", "ollama-02", "ollama-03"], [item["attempt_id"] for item in saved["refinement_attempts"]])
            self.assertEqual("unknown_term_id", saved["refinement_attempts"][-1]["validation_errors"][0]["code"])

    def test_complete_prompt_refinement_advances_without_structured_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            batch_path = root / "batches" / "000"
            batch_path.mkdir(parents=True)
            output = batch_path / "refinement.attempt-01.json"
            output.write_text("{}", encoding="utf-8")
            PromptEvolutionService._write_json(batch_path / "batch.json", {"index": 0})
            incumbent = {
                "positive_core": "blue eyes", "negative_core": "glowing eyes",
                "positive_core_terms": [{"id": "p001", "text": "blue eyes"}],
                "negative_core_terms": [{"id": "n001", "text": "glowing eyes"}],
            }
            run = {
                "run_id": "run-1", "root": str(root), "status": "REFINING", "current_batch": 0,
                "strategy_version": 2, "incumbent": incumbent, "exploration_incumbent": incumbent,
                "pending_corrections": [{"category": "eyes", "correction": "use dark blue irises"}],
                "refinement_output": str(output), "refinement_attempt_number": 1,
            }
            service = object.__new__(PromptEvolutionService)
            service._find_run = Mock(return_value=run)
            service._llm_json = Mock(return_value={
                "positive_core": "dark blue irises, white sclera",
                "negative_core": "glowing eyes; colored sclera",
            })
            service._start_batch = Mock()

            service._advance_run_unlocked("run-1")

            service._start_batch.assert_called_once_with(
                run, "dark blue irises, white sclera", "glowing eyes; colored sclera",
            )
            self.assertEqual(1, run["current_batch"])
            saved = PromptEvolutionService._read_json(batch_path / "batch.json")
            self.assertTrue(saved["refinement_attempts"][0]["accepted"])

    def test_recover_missing_evaluations_requeues_only_absent_inactive_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            batch_path = root / "batches" / "001"
            batch_path.mkdir(parents=True)
            (root / "metadata_snapshot.json").write_text("{}", encoding="utf-8")
            (root / "checklist_snapshot.json").write_text('{"items":[]}', encoding="utf-8")
            completed = batch_path / "evaluation_1.json"
            completed.write_text("{}", encoding="utf-8")
            missing = batch_path / "evaluation_2.json"
            PromptEvolutionService._write_json(batch_path / "batch.json", {
                "evaluations": [
                    {"seed": 1, "file": str(batch_path / "one.png"), "output": str(completed), "ask_id": "done"},
                    {"seed": 2, "file": str(batch_path / "two.png"), "output": str(missing), "ask_id": "archived-error"},
                ],
            })
            run = {"run_id": "run-1", "root": str(root), "status": "EVALUATING", "current_batch": 1, "reference_image": str(root / "reference.png"), "error": ""}
            service = object.__new__(PromptEvolutionService)
            service.app = Mock()
            service.app.queue_snapshot.return_value = {"ask": [], "running": [], "answer": []}
            service._find_run = Mock(return_value=run)
            service._format_template = Mock(return_value="evaluation prompt")
            service._queue_ollama = Mock(return_value="recovery-ask")

            detail = service.recover_missing_evaluations("run-1")

            self.assertEqual("EVALUATING", detail["status"])
            service._queue_ollama.assert_called_once()
            saved = PromptEvolutionService._read_json(batch_path / "batch.json")
            self.assertEqual("recovery-ask", saved["evaluations"][1]["ask_id"])
            self.assertEqual(1, saved["evaluations"][1]["recovery_attempts"])

    def test_retry_failed_evaluation_requeues_invalid_structured_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            batch_path = root / "batches" / "000"
            batch_path.mkdir(parents=True)
            output = batch_path / "evaluation_1.json"
            output.write_text('{"category_feedback":{"hair":{"score":2}}}', encoding="utf-8")
            candidate = batch_path / "candidate.png"
            candidate.write_bytes(b"image")
            reference = root / "reference.png"
            reference.write_bytes(b"image")
            PromptEvolutionService._write_json(root / "checklist_snapshot.json", {"items": []})
            PromptEvolutionService._write_json(batch_path / "batch.json", {
                "evaluations": [{"seed": 1, "file": str(candidate), "output": str(output), "ask_id": "failed-ask"}],
            })
            run = {
                "run_id": "run-1", "root": str(root), "status": "FAILED", "failed_stage": "EVALUATING",
                "current_batch": 0, "reference_image": str(reference), "error": "Evaluation omitted structured category feedback.",
            }
            service = object.__new__(PromptEvolutionService)
            service._find_run = Mock(return_value=run)
            service._format_template = Mock(return_value="evaluation prompt")
            service._queue_ollama = Mock(return_value="retry-ask")
            service.detail = Mock(side_effect=lambda _: {**run, "batches": [PromptEvolutionService._read_json(batch_path / "batch.json")]})

            detail = service.retry("run-1")

            self.assertEqual("EVALUATING", detail["status"])
            saved = PromptEvolutionService._read_json(batch_path / "batch.json")
            self.assertEqual("retry-ask", saved["evaluations"][0]["ask_id"])
            self.assertIn("stage-retry-1", saved["evaluations"][0]["output"])
            self.assertEqual(1, saved["evaluations"][0]["stage_retry_attempts"])

    def test_recover_missing_evaluations_does_not_duplicate_active_ask(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            batch_path = root / "batches" / "000"
            batch_path.mkdir(parents=True)
            (root / "metadata_snapshot.json").write_text("{}", encoding="utf-8")
            PromptEvolutionService._write_json(batch_path / "batch.json", {
                "evaluations": [{"seed": 1, "file": "candidate.png", "output": str(batch_path / "missing.json"), "ask_id": "active-ask"}],
            })
            service = object.__new__(PromptEvolutionService)
            service.app = Mock()
            service.app.queue_snapshot.return_value = {"ask": [{"ask_id": "active-ask"}], "running": [], "answer": []}
            service._find_run = Mock(return_value={"run_id": "run-1", "root": str(root), "status": "EVALUATING", "current_batch": 0})

            with self.assertRaisesRegex(PromptEvolutionError, "still active"):
                service.recover_missing_evaluations("run-1")

    def test_category_asks_are_staged_before_checklist_asks_with_separate_model(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            batch_path = root / "batches" / "000"
            batch_path.mkdir(parents=True)
            reference = root / "reference.png"
            reference.write_bytes(b"image")
            renders = []
            for seed in (1, 2):
                candidate = batch_path / f"candidate_{seed}.png"
                candidate.write_bytes(b"image")
                renders.append({"seed": seed, "file": str(candidate)})
            PromptEvolutionService._write_json(batch_path / "batch.json", {"renders": renders, "status": "RENDERING"})
            PromptEvolutionService._write_json(root / "metadata_snapshot.json", {})
            PromptEvolutionService._write_json(root / "checklist_snapshot.json", {"items": [
                {"item": "Hair color is incorrect", "category": "hair", "max_rating": 4},
            ]})
            PromptEvolutionService._write_json(root / "template_snapshot.json", {"evaluation": "prompt", "checklist_evaluation": "prompt"})
            run = {
                "run_id": "run-1", "root": str(root), "status": "RENDERING", "current_batch": 0,
                "reference_image": str(reference), "model": "category-model", "checklist_model": "checklist-model",
            }
            service = object.__new__(PromptEvolutionService)
            service._find_run = Mock(return_value=run)
            service._format_template = Mock(return_value="prompt")
            queued = []
            service._queue_ollama = Mock(side_effect=lambda current, **kwargs: queued.append(kwargs) or f"ask-{len(queued)}")
            service._save_run = Mock()
            service.detail = Mock(return_value=run)

            service._advance_run_unlocked("run-1")

            self.assertEqual(["evaluate_1", "evaluate_2", "checklist_1", "checklist_2"], [item["task"] for item in queued])
            self.assertEqual([None, None, "checklist-model", "checklist-model"], [item.get("model") for item in queued])
            saved = PromptEvolutionService._read_json(batch_path / "batch.json")
            self.assertTrue(all(item.get("checklist_output") for item in saved["evaluations"]))
            values = [call.args[2] for call in service._format_template.call_args_list]
            self.assertTrue(all(value.get("METADATA", "") == "" for value in values))
            self.assertEqual("1 - Is the hair color incorrect?", values[-1]["CHECKLIST_QUESTIONS"])

    def test_missing_checklist_response_is_indeterminate(self) -> None:
        scores = {
            "character_categories": {"face_shape": 5, "eyes": 5, "hair": 5, "species_markers": 5, "body_proportions": 5},
            "costume_categories": {"silhouette_layering": 5, "garment_pieces": 5, "colors": 5, "accessories_footwear": 5},
        }
        _, _, _, character_categories, _, applied = PromptEvolutionService._score(
            scores,
            {"items": [{"item": "Hair color is incorrect", "category": "hair", "max_rating": 4}]},
            {"checklist": [{"number": 2, "result": False}]},
        )
        self.assertEqual(5, character_categories["hair"])
        self.assertEqual([], applied)

    def test_indeterminate_checklist_result_is_accepted_without_cap(self) -> None:
        scores = {
            "character_categories": {"face_shape": 5, "eyes": 5, "hair": 8, "species_markers": 5, "body_proportions": 5},
            "costume_categories": {"silhouette_layering": 5, "garment_pieces": 5, "colors": 5, "accessories_footwear": 5},
        }
        _, _, _, character_categories, _, applied = PromptEvolutionService._score(
            scores,
            {"items": [{"item": "Hair is not black", "category": "hair", "max_rating": 3}]},
            {"checklist": [{"number": 1, "result": None, "confidence": 0.2, "evidence": "occluded"}]},
        )
        self.assertEqual(8, character_categories["hair"])
        self.assertEqual([], applied)

    def test_numbered_checklist_response_applies_category_cap(self) -> None:
        _, _, _, character_categories, _, applied = PromptEvolutionService._score({
            "character_categories": {"face_shape": 5, "eyes": 5, "hair": 9, "species_markers": 5, "body_proportions": 5},
            "costume_categories": {"silhouette_layering": 5, "garment_pieces": 5, "colors": 5, "accessories_footwear": 5},
        }, {"items": [{"item": "Hair color is incorrect", "category": "hair", "max_rating": 4}]}, {
            "checklist": [{"number": 1, "result": True}],
        })
        self.assertEqual(4, character_categories["hair"])
        self.assertEqual("Hair color is incorrect", applied[0]["item"])

    def test_category_scores_are_backend_aggregated(self) -> None:
        character, costume, combined, character_categories, costume_categories, _ = PromptEvolutionService._score({
            "character_categories": {"face_shape": 9, "eyes": 8, "hair": 7, "species_markers": 6, "body_proportions": 4},
            "costume_categories": {"silhouette_layering": 9.5, "garment_pieces": 8.5, "colors": 7.5, "accessories_footwear": 4.5},
        })
        self.assertEqual(6.8, character)
        self.assertEqual(7.5, costume)
        self.assertEqual(7.2, combined)
        self.assertEqual(7, character_categories["hair"])
        self.assertEqual(8.5, costume_categories["garment_pieces"])

    def test_structured_category_feedback_is_scored_and_supplies_two_weakest_corrections(self) -> None:
        names = ("face_shape", "eyes", "hair", "species_markers", "body_proportions", "silhouette_layering", "garment_pieces", "colors", "accessories_footwear")
        feedback = {
            name: {"score": index + 1, "observation": f"visible {name} difference", "correction": f"correct {name}", "confidence": 0.9}
            for index, name in enumerate(names)
        }
        character, costume, _, character_categories, costume_categories, _ = PromptEvolutionService._score({
            "strategy_version": 2, "category_feedback": feedback,
        })
        self.assertEqual(1, character_categories["face_shape"])
        self.assertEqual(6, costume_categories["silhouette_layering"])
        self.assertEqual(3, character)
        self.assertEqual(7.5, costume)
        selected = PromptEvolutionService._selected_corrections({
            "evaluation": {"category_feedback": feedback},
            "checklist_effects": [{"category": "hair", "correction": "exclude purple hair"}],
        })
        self.assertEqual(["face_shape", "eyes", "hair"], [item["category"] for item in selected])
        self.assertEqual("exclude purple hair", selected[-1]["correction"])

    def test_structured_category_feedback_requires_every_category(self) -> None:
        with self.assertRaisesRegex(PromptEvolutionError, "structured category feedback"):
            PromptEvolutionService._score({"category_feedback": {"hair": {"score": 2}}})

    def test_legacy_nested_identity_scores_remain_supported(self) -> None:
        character, costume, combined, _, _, _ = PromptEvolutionService._score({
            "character_identity": {"score": 92}, "costume_identity": {"overall": 88},
        })
        self.assertEqual((9.2, 8.8, 9.0), (character, costume, combined))

    def test_true_checklist_result_caps_configured_category(self) -> None:
        character, costume, combined, character_categories, _, applied = PromptEvolutionService._score({
            "character_categories": {"face_shape": 9, "eyes": 8, "hair": 7, "species_markers": 6, "body_proportions": 4},
            "costume_categories": {"silhouette_layering": 9.5, "garment_pieces": 8.5, "colors": 7.5, "accessories_footwear": 4.5},
        }, {"items": [{"item": "Hair color is incorrect", "category": "Hair", "max_rating": 4}]}, {
            "checklist": [{"item": "Hair color is incorrect", "result": True}],
        })
        self.assertEqual(4, character_categories["hair"])
        self.assertEqual(6.2, character)
        self.assertEqual(7.5, costume)
        self.assertEqual(6.8, combined)
        self.assertEqual({"item": "Hair color is incorrect", "category": "hair", "max_rating": 4, "before": 7, "after": 4}, applied[0])

    def test_checklist_cap_does_not_raise_lower_score(self) -> None:
        _, _, _, character_categories, _, applied = PromptEvolutionService._score({
            "character_categories": {"face_shape": 5, "eyes": 5, "hair": 3, "species_markers": 5, "body_proportions": 5},
            "costume_categories": {"silhouette_layering": 5, "garment_pieces": 5, "colors": 5, "accessories_footwear": 5},
            "checklist": [{"item": "Hair color is incorrect", "result": True}],
        }, {"items": [{"item": "Hair color is incorrect", "category": "hair", "max_rating": 4}]})
        self.assertEqual(3, character_categories["hair"])
        self.assertEqual(3, applied[0]["after"])

    def test_prompt_evolution_default_vision_model(self) -> None:
        self.assertEqual("qwen3.5-prompt-evo", DEFAULT_VISION_MODEL)
        self.assertEqual("qwen3-VL-prompt-evo", DEFAULT_CHECKLIST_MODEL)

    def test_v2_templates_are_self_contained_and_omit_project_metadata(self) -> None:
        root = Path(__file__).resolve().parents[1] / "Config" / "Prompt_Evolution"
        bootstrap = (root / "bootstrap.md").read_text(encoding="utf-8")
        evaluation = (root / "evaluation.md").read_text(encoding="utf-8")
        refinement = (root / "refinement.md").read_text(encoding="utf-8")
        combined = "\n".join((bootstrap, evaluation, refinement))
        self.assertNotIn("Zet", combined)
        self.assertNotIn("METADATA_WORD_POOL", combined)
        self.assertIn("sole source of truth", bootstrap)
        self.assertIn("category_feedback", evaluation)
        self.assertIn("Automatic1111 txt2img API", refinement)
        self.assertIn("used by txt2img", evaluation)
        self.assertIn("positive_core", refinement)
        self.assertIn("self-contained description", evaluation)
        self.assertIn("iris color separately from sclera color", evaluation)
        self.assertIn("iris color and sclera color separately", refinement)

    def test_v2_refinement_accepts_complete_a1111_prompts_and_derives_nonblocking_diff(self) -> None:
        incumbent = {
            "positive_core": "blue eyes, ruffled top",
            "negative_core": "glowing eyes",
            "positive_core_terms": [{"id": "p001", "text": "blue eyes"}, {"id": "p002", "text": "ruffled top"}],
            "negative_core_terms": [{"id": "n001", "text": "glowing eyes"}],
        }
        analysis = PromptEvolutionService._analyze_refinement_response(incumbent, {
            "positive_core": "dark blue irises, white sclera, simple gathered top",
            "negative_core": "glowing eyes; colored sclera",
        }, [{"category": "eyes", "correction": "separate iris and sclera color"}])

        self.assertTrue(analysis["strict_valid"])
        self.assertEqual("dark blue irises, white sclera, simple gathered top", analysis["positive_core"])
        self.assertEqual("glowing eyes; colored sclera", analysis["negative_core"])
        self.assertTrue(analysis["operations"])

    def test_v2_refinement_schema_requests_complete_prompt_cores(self) -> None:
        values, schema = PromptEvolutionService._refinement_contract_values({
            "positive_core": "blue eyes", "negative_core": "glowing eyes",
            "positive_core_terms": [{"id": "p001", "text": "blue eyes"}],
            "negative_core_terms": [{"id": "n001", "text": "glowing eyes"}],
        }, [{"category": "eyes", "correction": "use dark blue irises"}], {
            "eyes": {"score": 4, "correction": "use dark blue irises"},
        })

        self.assertEqual(["positive_core", "negative_core"], schema["required"])
        self.assertNotIn("operations", schema["properties"])
        self.assertIn('"eyes"', values["EVALUATIONS"])

    def test_empty_placeholder_evaluation_is_rejected(self) -> None:
        with self.assertRaises(PromptEvolutionPlaceholderResponse):
            PromptEvolutionService._score({
                "character_categories": {name: 0 for name in ("face_shape", "eyes", "hair", "species_markers", "body_proportions")},
                "costume_categories": {name: 0 for name in ("silhouette_layering", "garment_pieces", "colors", "accessories_footwear")},
                "confidence": 0, "character_evidence": {}, "costume_evidence": {}, "evidence": "",
            })

    def test_category_ranking_orders_worst_category_last(self) -> None:
        ranking = PromptEvolutionService._category_ranking({
            "character_categories": {"hair": 35, "eyes": 80, "skin_markings": 0},
            "costume_categories": {"colors": 55, "garment_pieces": 90, "trim_patterns": 100},
        })
        self.assertEqual(["garment_pieces", "eyes", "colors", "hair"], [item["category"] for item in ranking])

    def test_checklist_violations_become_early_refinement_directives(self) -> None:
        directives = PromptEvolutionService._checklist_directives({
            "checklist_effects": [
                {"item": "Hair color is incorrect", "category": "hair", "max_rating": 4},
                {"item": "The costume hue is incorrect.", "category": "colors", "max_rating": 4},
            ],
        })
        self.assertEqual(
            "Additionally you must address these defects directly: The hair color is incorrect. The costume hue is incorrect.",
            directives,
        )

    def test_refinement_category_summary_lists_all_scores_worst_to_best(self) -> None:
        summary = PromptEvolutionService._category_evaluation_summary({
            "character_categories": {
                "face_shape": 9, "eyes": 6, "hair": 3, "species_markers": 10, "body_proportions": 8,
            },
            "costume_categories": {
                "silhouette_layering": 7, "garment_pieces": 4, "colors": 3, "accessories_footwear": 6,
            },
        })
        self.assertEqual([
            "Character Hair: Evaluation 3/10 - This category needs major improvement.",
            "Costume Colors: Evaluation 3/10 - This category needs major improvement.",
            "Costume Garments: Evaluation 4/10 - This category needs major improvement.",
            "Character Eyes: Evaluation 6/10 - This category needs improvement.",
            "Costume Accessories/footwear: Evaluation 6/10 - This category needs improvement.",
            "Costume Silhouette/layering: Evaluation 7/10 - This category needs refinement.",
            "Character Body proportions: Evaluation 8/10 - This category needs refinement.",
            "Character Face shape: Evaluation 9/10 - This category is excellent.",
            "Character Species markers: Evaluation 10/10 - This category is excellent.",
        ], summary.splitlines())

    def test_delete_removes_only_terminal_run_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pipeline_root = Path(temp_dir) / "Pipelines"
            run_root = pipeline_root / "Character" / "Adult" / "Costume" / "Prompt_Evolution" / "run-1"
            run_root.mkdir(parents=True)
            (run_root / "run.json").write_text('{"run_id":"run-1","status":"COMPLETE","root":"' + str(run_root).replace("\\", "\\\\") + '"}', encoding="utf-8")
            service = object.__new__(PromptEvolutionService)
            service.app = Mock(config=Mock(base_pipeline_path=pipeline_root))

            result = service.delete("run-1")

            self.assertEqual({"deleted": True, "run_id": "run-1"}, result)
            self.assertFalse(run_root.exists())

    def test_restart_uses_current_bootstrap_without_old_prompt(self) -> None:
        service = object.__new__(PromptEvolutionService)
        old = {
            "run_id": "old", "status": "ABORTED", "character": "Tsaeytte", "phase": "Elder",
            "costume": "Everyday", "view": "Front", "model": "vision", "checklist_model": "checklist",
            "checkpoint": "checkpoint", "profile": "profile", "cfg_scale": 7, "steps": 32,
            "batch_size": 5, "total_batches": 5, "metadata_mode": "curated", "mode": "auto",
            "positive_prompt": "obsolete prompt", "negative_prompt": "obsolete negative",
        }
        fresh = {"run_id": "new", "root": "root", "status": "BOOTSTRAPPING"}
        service._find_run = Mock(side_effect=[old, fresh, fresh])
        service.create_run = Mock(return_value=fresh)
        service._save_run = Mock()
        service.detail = Mock(return_value=fresh)

        service.restart("old")

        payload = service.create_run.call_args.args[0]
        self.assertNotIn("positive_prompt", payload)
        self.assertNotIn("negative_prompt", payload)
        self.assertEqual("Elder", payload["phase"])
        self.assertEqual("old", fresh["restarted_from_run_id"])

    def test_restart_raises_legacy_singleton_settings_to_current_minimums(self) -> None:
        service = object.__new__(PromptEvolutionService)
        old = {
            "run_id": "old", "status": "AWAITING_FINALIST", "character": "Tsaeytte", "phase": "Elder",
            "costume": "Everyday", "view": "Front", "batch_size": 1, "total_batches": 1,
        }
        fresh = {"run_id": "new", "root": "root", "status": "BOOTSTRAPPING"}
        service._find_run = Mock(side_effect=[old, fresh, fresh])
        service.create_run = Mock(return_value=fresh)
        service._save_run = Mock()
        service.detail = Mock(return_value=fresh)

        service.restart("old")

        payload = service.create_run.call_args.args[0]
        self.assertEqual(2, payload["batch_size"])
        self.assertEqual(2, payload["total_batches"])

    def test_finalist_selection_persists_reusable_core_and_wrapper(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            finalist = {
                "finalist_id": "batch-001", "positive_core": "black bob, teal top", "negative_core": "blonde hair",
                "positive_core_terms": [{"id": "p001", "text": "black bob"}],
                "negative_core_terms": [{"id": "n001", "text": "blonde hair"}],
                "positive_prompt": "black bob, teal top, full body shot", "negative_prompt": "blonde hair, cropped",
                "evaluation_wrapper": {"positive_terms": ["full body shot"], "negative_terms": ["cropped"]},
            }
            run = {
                "run_id": "run-1", "root": str(root), "status": "AWAITING_FINALIST", "strategy_version": 2,
                "checkpoint": "checkpoint", "finalists": [finalist],
            }
            service = object.__new__(PromptEvolutionService)
            service._find_run = Mock(return_value=run)
            service.detail = Mock(side_effect=lambda _: run)

            result = service.select_finalist("run-1", "batch-001")

            self.assertEqual("COMPLETE", result["status"])
            self.assertEqual("black bob, teal top", json.loads((root / "prompt_core.json").read_text())["positive_core"])
            self.assertEqual(["full body shot"], json.loads((root / "evaluation_wrapper.json").read_text())["positive_terms"])

    def test_selecting_parent_finalist_rejects_latest_batch_and_queues_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            reference = root / "reference.png"
            selected_image = root / "incumbent.png"
            reference.write_bytes(b"reference")
            selected_image.write_bytes(b"incumbent")
            (root / "batches" / "000").mkdir(parents=True)
            latest_path = root / "batches" / "001"
            latest_path.mkdir()
            mutation = [{"target": "positive", "action": "edit", "term_id": "p001", "new": "brown hair", "category": "hair"}]
            PromptEvolutionService._write_json(latest_path / "batch.json", {
                "index": 1, "batch_slot": 1, "retry_attempt": 0, "parent_finalist_id": "batch-000",
                "attempted_mutation": mutation, "status": "REVIEWED",
            })
            incumbent = {
                "finalist_id": "batch-000", "batch": 0, "seed": 7, "file": str(selected_image),
                "positive_core": "solid black hair", "negative_core": "brown hair",
                "positive_core_terms": [{"id": "p001", "text": "solid black hair"}],
                "negative_core_terms": [{"id": "n001", "text": "brown hair"}],
                "evaluation": {"category_feedback": {
                    "hair": {"score": 6, "correction": "preserve the solid black hair"},
                    "eyes": {"score": 7, "correction": "match the reference eye shape"},
                }},
            }
            latest = {**incumbent, "finalist_id": "batch-001", "batch": 1, "seed": 8, "combined_score": 9}
            run = {
                "run_id": "run-1", "root": str(root), "status": "AWAITING_FINALIST", "strategy_version": 2,
                "current_batch": 1, "total_batches": 2, "batch_size": 2, "reference_image": str(reference),
                "incumbent": incumbent, "exploration_incumbent": latest, "finalists": [incumbent, latest],
                "rejected_mutations": [],
            }
            service = object.__new__(PromptEvolutionService)
            service._find_run = Mock(return_value=run)
            service._format_template = Mock(return_value="base refinement prompt")
            service._queue_ollama = Mock(return_value="ask-1")
            service._save_run = Mock()
            service.detail = Mock(side_effect=lambda _: run)

            result = service.select_finalist(
                "run-1", "batch-000", "The hair in this image is a better match to the source.",
            )

            self.assertEqual("REFINING", result["status"])
            self.assertEqual(1, result["current_batch"])
            self.assertEqual(2, result["total_batches"])
            self.assertEqual(1, result["pending_batch_slot"])
            self.assertEqual(1, result["pending_batch_retry"])
            self.assertEqual("batch-000", result["exploration_incumbent"]["finalist_id"])
            self.assertIn("batch-001", result["rejected_finalist_ids"])
            self.assertEqual(mutation, result["rejected_mutations"])
            queued = service._queue_ollama.call_args.kwargs
            self.assertIn("Also take this into consideration: The hair in this image is a better match to the source.", queued["prompt"])
            self.assertEqual([reference, selected_image], queued["images"])
            saved = PromptEvolutionService._read_json(latest_path / "batch.json")
            self.assertFalse(saved["accepted"])
            self.assertTrue(saved["human_rejected"])
            self.assertEqual("REJECTED", saved["status"])

    def test_invalid_refinement_exposes_every_rendered_candidate(self) -> None:
        candidates = [{"seed": seed, "file": f"candidate-{seed}.png"} for seed in range(5)]
        incumbent = {**candidates[2], "finalist_id": "batch-000"}
        finalists, mode = PromptEvolutionService._finalist_choices({
            "run_id": "run-1", "status": "AWAITING_FINALIST", "incumbent": incumbent,
            "finalists": [incumbent], "exploration_warning": "No valid refinement alternative was produced.",
        }, [{
            "index": 0, "candidates": candidates, "positive_core": "black bob",
            "negative_core": "blonde hair", "positive_core_terms": [], "negative_core_terms": [],
            "evaluation_wrapper": {},
        }])

        self.assertEqual("candidate_fallback", mode)
        self.assertEqual(5, len(finalists))
        self.assertEqual(1, sum(item["is_incumbent"] for item in finalists))
        self.assertEqual({0, 1, 2, 3, 4}, {item["seed"] for item in finalists})

    def test_delete_rejects_active_run(self) -> None:
        service = object.__new__(PromptEvolutionService)
        service._find_run = Mock(return_value={"run_id": "run-1", "status": "RENDERING", "root": "unused"})
        with self.assertRaises(PromptEvolutionError):
            service.delete("run-1")

    def test_stable_matrix_overrides_canvas_cfg_and_steps(self) -> None:
        call = compile_stable_matrix_api_call(
            "Prompt: character\nNegative: mismatch",
            {"width": 512, "height": 768, "cfg": 5, "steps": 10, "enable_hr": False},
            preset_name="test",
            render_overrides={"width": 768, "height": 1024, "cfg_scale": 7.5, "steps": 31},
        )
        payload = call["payload"]
        self.assertEqual((768, 1024), (payload["width"], payload["height"]))
        self.assertEqual(7.5, payload["cfg_scale"])
        self.assertEqual(31, payload["steps"])

    def test_local_worker_forwards_render_overrides(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            kwargs = render_image_kwargs(
                {"render_overrides": {"width": 768, "height": 1024, "cfg_scale": 8, "steps": 30}},
                root / "Prompt.md", root, "body-reference-preview",
            )
        self.assertEqual(
            {"width": 768, "height": 1024, "cfg_scale": 8, "steps": 30},
            kwargs["render_overrides"],
        )

    def test_stored_front_view_normalizes_to_compiler_token(self) -> None:
        service = ViewService(Path(__file__).resolve().parents[1])
        self.assertEqual("FRONT", service.normalize_token("Front"))

    def test_curated_metadata_normalizes_asset_view_before_compile(self) -> None:
        source_service = Mock()
        source_service.views.normalize_token.return_value = "FRONT"
        source_service.options.return_value = {"costumes": [{"label": "Canonical Adventure Gear", "value": "canonical_adventure_gear"}]}
        source_service.compile.return_value = {"source_snapshot": {"selected_sections": {"IDENTITY_PRESERVATION_CORE": "identity"}}}
        service = object.__new__(PromptEvolutionService)
        service.app = Mock(character_source_service=source_service)

        metadata = service._metadata("Tsaeytte", "Adult", "Canonical Adventure Gear", "Front", "curated")

        self.assertEqual("Front", metadata["view"])
        self.assertEqual({"IDENTITY_PRESERVATION_CORE": "identity"}, metadata["selected_sections"])
        self.assertEqual("FRONT", source_service.compile.call_args.kwargs["view_token"])

    def test_ranking_accepts_object_and_scalar_seed_shapes(self) -> None:
        ordered = PromptEvolutionService._ordered_ranking_seeds({
            "ordered_seeds": [{"seed": "20", "rank": 1}, 10, {"unexpected": 5}, "invalid", {"seed": 20}],
        })
        self.assertEqual([20, 10], ordered)


if __name__ == "__main__":
    unittest.main()
