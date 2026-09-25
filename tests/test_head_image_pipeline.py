import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from Scripts.Run_Head_Image_Jobs import compile_head_image_job
from zet.models.asset import Asset
from zet.models.worker import WorkerContext
from zet.repositories.asset_repository import AssetRepository
from zet.services.character_onboarding_service import CharacterOnboardingService, FOUNDATION_VIEWS
from zet.services.config_service import Config
from zet.services.local_head_image_service import LocalHeadImageService, VIEWS
from zet.services import atomic_file_service
from zet.services.path_service import PathService
from zet.services.reference_service import ReferenceService
from zet.workers import character_assembly_manifest_worker
from zet.web.app import create_app


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def config_for(root: Path) -> Config:
    return Config(
        base_library_path=str(root),
        base_character_path=str(root / "Characters"),
        base_asset_path=str(root / "Assets"),
        base_pipeline_path=str(root / "Pipelines"),
        base_ai_queue_path=str(root / "Queue"),
    )


class HeadImageCompilerTests(unittest.TestCase):
    def test_local_head_review_includes_background_gate_for_every_view(self) -> None:
        for view in VIEWS:
            with self.subTest(view=view):
                gates = LocalHeadImageService.review_gates(view)
                self.assertEqual("background", gates[0].key)
                self.assertIn("transparent background passes", gates[0].prompt)
                self.assertIn("Return TRUE when the background similar in color or tone", gates[0].prompt)

    def test_local_gaze_gate_applies_only_to_views_with_visible_eyes(self) -> None:
        for view in ("FRONT", "FRONT_LEFT_3_4", "FRONT_RIGHT_3_4", "LEFT_PROFILE", "RIGHT_PROFILE"):
            with self.subTest(view=view):
                gates = LocalHeadImageService.review_gates(view)
                keys = [gate.key for gate in gates]
                self.assertEqual("gaze", keys[keys.index("orientation") + 1])
                self.assertIn("exactly TRUE or FALSE", gates[keys.index("gaze")].prompt)
                self.assertIn("ambiguous", gates[keys.index("gaze")].prompt)
                self.assertEqual(view != "FRONT", gates[keys.index("gaze")].uses_anchor)
        for view in ("BACK_LEFT_3_4", "BACK_RIGHT_3_4", "BACK"):
            with self.subTest(view=view):
                self.assertNotIn("gaze", [gate.key for gate in LocalHeadImageService.review_gates(view)])

    def test_local_front_compiles_with_optional_source_and_keeps_traditional_rule(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            template = PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Character_Template.md"
            base = {"Job": "local-front", "Task": "head-image", "Character": "Test", "Phase": "Adult",
                    "Head View": "Front", "Template Path": str(template), "Reference Files": []}
            generated = compile_head_image_job({**base, "Output Directory": str(root / "text")}, PROJECT_ROOT,
                                               pipeline_mode="local")
            prompt = Path(generated["final_prompt"]).read_text(encoding="utf-8")
            manifest = json.loads(Path(generated["dependency_manifest"]).read_text(encoding="utf-8"))
            self.assertNotIn("source image", prompt.lower())
            self.assertNotIn("source-image", prompt.lower())
            self.assertNotIn("reference image", prompt.lower())
            self.assertNotIn("camera-facing gaze", prompt)
            self.assertNotIn("# Render Task", prompt)
            self.assertEqual("generate", manifest["render_mode"])
            self.assertEqual([], manifest["resources"])
            self.assertEqual([], manifest["required_reference_roles"])

            source = root / "source.png"
            source.write_bytes(b"source")
            edited = compile_head_image_job({**base, "Output Directory": str(root / "guided"),
                                             "Reference Files": [{"role": "head_image_source", "path": str(source)}]},
                                            PROJECT_ROOT, pipeline_mode="local")
            edited_prompt = Path(edited["final_prompt"]).read_text(encoding="utf-8")
            edited_manifest = json.loads(Path(edited["dependency_manifest"]).read_text(encoding="utf-8"))
            self.assertIn("Use Image 1 as the identity and appearance reference", edited_prompt)
            self.assertNotIn("optional identity reference", edited_prompt.lower())
            self.assertNotIn("camera-facing gaze", edited_prompt)
            self.assertEqual("edit", edited_manifest["render_mode"])
            self.assertEqual([str(source)], [item["path"] for item in edited_manifest["resources"]])

            side = compile_head_image_job({**base, "Job": "local-side", "Head View": "Front Left 3/4",
                                           "Output Directory": str(root / "side"),
                                           "Reference Files": [{"role": "head_image_source", "path": str(source)}]},
                                          PROJECT_ROOT, pipeline_mode="local")
            side_prompt = Path(side["final_prompt"]).read_text(encoding="utf-8")
            self.assertIn("nose points image-left", side_prompt)
            self.assertIn("Both eyes look image-left along the turned face", side_prompt)
            self.assertIn("Use Image 1, the selected FRONT render, as the identity and appearance anchor", side_prompt)

    def test_local_source_contract_is_present_only_with_a_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            shared = PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Character_Template.md"
            template = root / "Character.md"
            template.write_text(shared.read_text(encoding="utf-8").replace(
                "Source-image contract:", "Optional source-image contract:").replace(
                "* Source identity authority: `[What likeness or design information should be taken from a supplied source image.]`",
                "* When a source image is supplied, use it as the visual authority for identity.\n"
                "* Without a source image, construct the character from authored facts."), encoding="utf-8")
            base = {"Job": "local-contract", "Task": "head-image", "Character": "Test", "Phase": "Adult",
                    "Head View": "Front", "Template Path": str(template)}
            no_source = compile_head_image_job({**base, "Output Directory": str(root / "text"),
                                                "Reference Files": []}, PROJECT_ROOT, pipeline_mode="local")
            no_source_prompt = Path(no_source["final_prompt"]).read_text(encoding="utf-8")
            self.assertNotIn("source image", no_source_prompt.lower())
            self.assertNotIn("source-image", no_source_prompt.lower())

            source = root / "source.png"
            source.write_bytes(b"source")
            with_source = compile_head_image_job({**base, "Output Directory": str(root / "guided"),
                                                  "Reference Files": [{"role": "head_image_source", "path": str(source)}]},
                                                 PROJECT_ROOT, pipeline_mode="local")
            with_source_prompt = Path(with_source["final_prompt"]).read_text(encoding="utf-8")
            self.assertIn("Use Image 1 as the identity and appearance reference.", with_source_prompt)
            self.assertNotIn("Without a source image", with_source_prompt)

    def test_local_non_front_gaze_rule_precedes_subject_details_for_every_view(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.png"
            source.write_bytes(b"source")
            template = PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Character_Template.md"
            gaze_by_view = {
                "FRONT_LEFT_3_4": "Both eyes look image-left along the turned face.",
                "FRONT_RIGHT_3_4": "Both eyes look image-right along the turned face.",
                "LEFT_PROFILE": "The visible eye looks image-left along the nose.",
                "RIGHT_PROFILE": "The visible eye looks image-right along the nose.",
                "BACK_LEFT_3_4": "Keep the face turned away; no eye or expression is visible.",
                "BACK_RIGHT_3_4": "Keep the face turned away; no eye or expression is visible.",
                "BACK": "No eyes or facial features are visible.",
            }
            for view in VIEWS:
                if view == "FRONT":
                    continue
                with self.subTest(view=view):
                    result = compile_head_image_job({
                        "Job": f"local-{view}", "Task": "head-image", "Character": "Test", "Phase": "Adult",
                        "Head View": view, "Template Path": str(template), "Output Directory": str(root / view),
                        "Reference Files": [{"role": "head_image_source", "path": str(source)}],
                    }, PROJECT_ROOT, pipeline_mode="local")
                    prompt = Path(result["final_prompt"]).read_text(encoding="utf-8")
                    self.assertIn(gaze_by_view[view], prompt)
                    self.assertNotIn("If the requested view", prompt)

    def test_local_prompt_instructions_are_compiled_for_all_eight_views(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "source.png"
            source.write_bytes(b"source")
            template = PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Character_Template.md"
            expected = {
                "FRONT": ("camera is directly in front", "Both eyes look straight ahead"),
                "FRONT_LEFT_3_4": ("camera is in front of the character's anatomical left", "Both eyes look image-left"),
                "FRONT_RIGHT_3_4": ("camera is in front of the character's anatomical right", "Both eyes look image-right"),
                "LEFT_PROFILE": ("camera is directly beside the character's anatomical left", "visible eye looks image-left"),
                "RIGHT_PROFILE": ("camera is directly beside the character's anatomical right", "visible eye looks image-right"),
                "BACK_LEFT_3_4": ("camera is behind the character's anatomical left", "no eye or expression is visible"),
                "BACK_RIGHT_3_4": ("camera is behind the character's anatomical right", "no eye or expression is visible"),
                "BACK": ("camera is directly behind the character", "No eyes or facial features are visible"),
            }
            for view, (view_text, gaze_text) in expected.items():
                with self.subTest(view=view):
                    result = compile_head_image_job({
                        "Job": f"local-{view}", "Task": "head-image", "Character": "Test", "Phase": "Adult",
                        "Head View": view, "Template Path": str(template), "Output Directory": str(root / view),
                        "Reference Files": [{"role": "head_image_source", "path": str(source)}],
                    }, PROJECT_ROOT, pipeline_mode="local")
                    prompt = Path(result["final_prompt"]).read_text(encoding="utf-8")
                    self.assertIn(view_text, prompt)
                    self.assertIn(gaze_text, prompt)
                    self.assertNotIn("if the requested view", prompt.lower())
                    self.assertNotIn("{{", prompt)
                    if view in {"BACK_LEFT_3_4", "BACK_RIGHT_3_4", "BACK"}:
                        self.assertNotIn("Eye shape:", prompt)
                        self.assertNotIn("large expressive eyes", prompt)

    def test_local_phase_changes_are_compact_and_traditional_transform_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            template = Path(r"C:\Users\Joe\Projects\Zet_Library\Characters\Tsaeytte\Elder\Character.md")
            source = root / "source.png"
            source.write_bytes(b"source")
            reference = [{"role": "head_image_source", "path": str(source)}]
            job = {"Job": "elder-phase", "Task": "head-image", "Character": "Tsaeytte", "Phase": "Elder",
                   "Head View": "Front", "Template Path": str(template), "Reference Files": reference}
            local = compile_head_image_job({**job, "Output Directory": str(root / "local")}, PROJECT_ROOT,
                                           pipeline_mode="local")
            local_prompt = Path(local["final_prompt"]).read_text(encoding="utf-8")
            self.assertIn("Show Tsaeytte as the same person in her Elder phase", local_prompt)
            self.assertIn("luminous silver", local_prompt)
            self.assertNotIn("primary goal of this task is successful age transformation", local_prompt)

            rear = compile_head_image_job({**job, "Head View": "BACK_RIGHT_3_4",
                                           "Output Directory": str(root / "rear")}, PROJECT_ROOT,
                                          pipeline_mode="local")
            rear_prompt = Path(rear["final_prompt"]).read_text(encoding="utf-8")
            self.assertNotIn("large expressive eyes", rear_prompt)
            self.assertIn("Painterly semi-realistic fantasy illustration", rear_prompt)

            traditional = compile_head_image_job({**job, "Output Directory": str(root / "traditional")}, PROJECT_ROOT)
            traditional_prompt = Path(traditional["final_prompt"]).read_text(encoding="utf-8")
            self.assertIn("primary goal of this task is successful age transformation", traditional_prompt)
            self.assertIn("The final face must read as Elder Tsaeytte", traditional_prompt)

    def test_local_non_front_requires_selected_front_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with self.assertRaisesRegex(Exception, "require the selected FRONT anchor"):
                compile_head_image_job({
                    "Job": "local-profile", "Task": "head-image", "Character": "Test", "Phase": "Adult",
                    "Head View": "Left Profile",
                    "Template Path": str(PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Character_Template.md"),
                    "Output Directory": str(root / "output"), "Reference Files": [],
                }, PROJECT_ROOT, pipeline_mode="local")

    def test_local_head_workspace_starts_with_front_candidates_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            characters = root / "Characters" / "Test" / "Adult"
            characters.mkdir(parents=True)
            shared_template = PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Character_Template.md"
            (characters / "Character.md").write_text(shared_template.read_text(encoding="utf-8"), encoding="utf-8")
            app = SimpleNamespace(config=SimpleNamespace(base_library_path=str(root / "Library"),
                                                         base_character_path=str(root / "Characters")))
            service = LocalHeadImageService(app, PROJECT_ROOT)
            run = service.create_run({"character": "Test", "phase": "Adult", "front_count": 1,
                                      "other_count": 1, "seeds": list(range(8))})

            self.assertEqual(8, len(run["views"]))
            self.assertEqual(8, run["candidate_count"])
            self.assertEqual("QUEUED", run["status"])
            self.assertEqual("", run["front_source"])
            prompt = Path(run["front_prompt_path"]).read_text(encoding="utf-8")
            self.assertNotIn("source image", prompt.lower())
            self.assertEqual(1, len([item for item in run["candidates"] if item["view"] == "FRONT"]))

    def test_saved_render_survives_transient_state_replace_access_denied(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            characters = root / "Characters" / "Test" / "Adult"
            characters.mkdir(parents=True)
            shared_template = PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Character_Template.md"
            (characters / "Character.md").write_text(shared_template.read_text(encoding="utf-8"), encoding="utf-8")
            app = SimpleNamespace(config=SimpleNamespace(base_library_path=str(root / "Library"),
                                                         base_character_path=str(root / "Characters"),
                                                         comfyui_poll_seconds=0.01))
            service = LocalHeadImageService(app, PROJECT_ROOT)
            run = service.create_run({"character": "Test", "phase": "Adult", "front_count": 1,
                                      "other_count": 1, "seeds": list(range(8))})
            candidate = next(item for item in run["candidates"] if item["view"] == "FRONT")
            target = root / "rendered.png"
            service._update(run["run_id"], candidate["candidate_id"], status="RUNNING", image_path=str(target))

            def harvest(_run_id, _candidate):
                target.write_bytes(b"saved render")

            real_replace = atomic_file_service.os.replace
            attempts = 0

            def fail_once(source, destination):
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    error = OSError(5, "Access is denied")
                    error.winerror = 5
                    raise error
                return real_replace(source, destination)

            with patch.object(service, "_harvest", side_effect=harvest), \
                    patch.object(atomic_file_service.os, "replace", side_effect=fail_once):
                self.assertTrue(service._wait_render(run["run_id"], candidate["candidate_id"]))

            current = next(item for item in service.detail(run["run_id"])["candidates"]
                           if item["candidate_id"] == candidate["candidate_id"])
            self.assertEqual("WAITING_FOR_GATES", current["status"])
            self.assertTrue(target.is_file())
            self.assertGreaterEqual(attempts, 2)

    def test_old_ranking_is_stale_and_cannot_select_without_new_gaze_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            characters = root / "Characters" / "Test" / "Adult"
            characters.mkdir(parents=True)
            shared_template = PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Character_Template.md"
            (characters / "Character.md").write_text(shared_template.read_text(encoding="utf-8"), encoding="utf-8")
            app = SimpleNamespace(config=SimpleNamespace(base_library_path=str(root / "Library"),
                                                         base_character_path=str(root / "Characters")))
            service = LocalHeadImageService(app, PROJECT_ROOT)
            run = service.create_run({"character": "Test", "phase": "Adult", "front_count": 1,
                                      "other_count": 1, "seeds": list(range(8))})
            candidate = next(item for item in run["candidates"] if item["view"] == "FRONT")
            image = root / "old-front.png"
            image.write_bytes(b"old candidate image")
            service._update(run["run_id"], candidate["candidate_id"], status="WAITING_FOR_HUMAN_REVIEW",
                            image_path=str(image), human_review={"decision": "keep", "notes": "Keep these notes."})
            state_path = Path(run["root"]) / "state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["rankings"] = {"FRONT": {"status": "COMPLETE", "ordered_candidate_ids": [candidate["candidate_id"]],
                                             "entries": [], "input_hashes": {candidate["candidate_id"]: service._hash(image)}}}
            state_path.write_text(json.dumps(state), encoding="utf-8")

            current = service.detail(run["run_id"])
            self.assertEqual("STALE", current["rankings"]["FRONT"]["status"])
            self.assertIn("gaze", [gate.key for gate in service.review_gates("FRONT")])
            self.assertEqual("Keep these notes.", next(item for item in current["candidates"]
                                                         if item["candidate_id"] == candidate["candidate_id"])
                             ["human_review"]["notes"])
            with self.assertRaisesRegex(Exception, "current gate review"):
                service.select_view(run["run_id"], "FRONT", candidate["candidate_id"])

    def test_local_head_renders_view_before_gates_then_ranks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            characters = root / "Characters" / "Test" / "Adult"
            characters.mkdir(parents=True)
            shared_template = PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Character_Template.md"
            (characters / "Character.md").write_text(shared_template.read_text(encoding="utf-8"), encoding="utf-8")
            app = SimpleNamespace(config=SimpleNamespace(base_library_path=str(root / "Library"),
                                                         base_character_path=str(root / "Characters")))
            service = LocalHeadImageService(app, PROJECT_ROOT)
            run = service.create_run({"character": "Test", "phase": "Adult", "front_count": 2,
                                      "other_count": 1, "seeds": list(range(9))})
            candidates = [item for item in run["candidates"] if item["view"] == "FRONT"]
            candidate_ids = {item["candidate_id"] for item in candidates}
            events = []

            def queue(_run_id, candidate_id):
                events.append(("render", candidate_id))
                image_path = root / "renders" / f"{candidate_id}.png"
                service._update(run["run_id"], candidate_id, status="QUEUED", image_path=str(image_path))

            def wait(_run_id, candidate_id):
                events.append(("wait", candidate_id))
                candidate = next(item for item in service.detail(run["run_id"])["candidates"]
                                 if item["candidate_id"] == candidate_id)
                image_path = Path(candidate["image_path"])
                image_path.parent.mkdir(parents=True, exist_ok=True)
                image_path.write_bytes(b"image")
                service._update(run["run_id"], candidate_id, status="WAITING_FOR_GATES")
                return True

            def gates(_run_id, candidate_id):
                events.append(("gate", candidate_id))
                service._update(run["run_id"], candidate_id, status="WAITING_FOR_HUMAN_REVIEW")
                return True

            def rank(_run_id, view):
                events.append(("rank", view))
                return service.detail(run["run_id"])

            with patch.object(service, "queue_render_candidate", side_effect=queue), \
                    patch.object(service, "_wait_render", side_effect=wait), \
                    patch.object(service, "run_candidate_gates", side_effect=gates), \
                    patch.object(service, "rank_view", side_effect=rank):
                service.execute_run(run["run_id"], views={"FRONT"}, candidate_ids=candidate_ids)

            self.assertEqual([
                ("render", candidates[0]["candidate_id"]),
                ("render", candidates[1]["candidate_id"]),
                ("wait", candidates[0]["candidate_id"]),
                ("wait", candidates[1]["candidate_id"]),
                ("gate", candidates[0]["candidate_id"]),
                ("gate", candidates[1]["candidate_id"]),
                ("rank", "FRONT"),
            ], events)

    def test_local_head_ranking_closes_temporary_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            characters = root / "Characters" / "Test" / "Adult"
            characters.mkdir(parents=True)
            shared_template = PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Character_Template.md"
            (characters / "Character.md").write_text(shared_template.read_text(encoding="utf-8"), encoding="utf-8")
            app = SimpleNamespace(config=SimpleNamespace(base_library_path=str(root / "Library"),
                                                         base_character_path=str(root / "Characters")))
            service = LocalHeadImageService(app, PROJECT_ROOT)
            run = service.create_run({"character": "Test", "phase": "Adult", "front_count": 2,
                                      "other_count": 1, "seeds": list(range(9))})
            candidates = [item for item in run["candidates"] if item["view"] == "FRONT"]
            for candidate in candidates:
                image_path = root / f"{candidate['candidate_id']}.png"
                image_path.write_bytes(candidate["candidate_id"].encode())
                service._update(run["run_id"], candidate["candidate_id"],
                                status="WAITING_FOR_HUMAN_REVIEW", image_path=str(image_path))

            temporary_paths = []

            def fake_codex(command, **_kwargs):
                schema_path = Path(command[command.index("--output-schema") + 1])
                output_path = Path(command[command.index("--output-last-message") + 1])
                temporary_paths.extend((schema_path, output_path))
                self.assertIn("ranking", json.loads(schema_path.read_text(encoding="utf-8"))["properties"])
                output_path.write_text(json.dumps({"ranking": [
                    {"candidate_id": item["candidate_id"], "reason": "Clear reference"} for item in candidates
                ]}), encoding="utf-8")
                return SimpleNamespace(returncode=0)

            with patch.object(service, "review_gates", return_value=[]), \
                    patch("zet.services.local_head_image_service.shutil.which", return_value="codex"), \
                    patch("zet.services.local_head_image_service.subprocess.run", side_effect=fake_codex):
                ranked = service.rank_view(run["run_id"], "FRONT")

            self.assertEqual("COMPLETE", ranked["rankings"]["FRONT"]["status"])
            self.assertTrue(temporary_paths)
            self.assertTrue(all(not path.exists() for path in temporary_paths))

    def test_standard_source_path_compiles_all_views(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            template = PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Character_Template.md"
            source = root / "source.png"
            source.write_bytes(b"image")
            for view in FOUNDATION_VIEWS:
                references = [{"role": "head_image_source", "path": str(source)}]
                with self.subTest(view=view):
                    result = compile_head_image_job({
                        "Job": f"head-{view}-source",
                        "Task": "head-image",
                        "Character": "Test",
                        "Phase": "Adult",
                        "Head View": view,
                        "Template Path": str(template),
                        "Output Directory": str(root / view / "source"),
                        "Reference Files": references,
                    }, PROJECT_ROOT)
                    prompt = Path(result["final_prompt"]).read_text(encoding="utf-8")
                    self.assertIn("HEAD-IMAGE Adult CHARACTER REFERENCE", prompt)
                    self.assertNotIn("NECK FITMENT", prompt)
                    self.assertNotIn("simple, unobtrusive background", prompt.lower())
                    self.assertNotIn("{{", prompt)
                    self.assertNotIn("young-adult Tsaeytte", prompt)
                    self.assertNotIn("* Wrong age phase.", prompt)
                    image_review = Path(result["image_review"]).read_text(encoding="utf-8")
                    normalized_view = str(view).upper().replace("-", "_")
                    if normalized_view == "FRONT":
                        self.assertIn("eyes look forward with the face", image_review)
                    elif normalized_view == "BACK":
                        self.assertNotIn("eyes follow", image_review)
                    elif normalized_view.startswith("BACK_"):
                        self.assertIn("gaze remains aligned", image_review)
                    elif normalized_view.endswith("PROFILE"):
                        self.assertIn("visible eye follows the nose direction", image_review)
                    else:
                        self.assertIn("follow the turned face and nose direction", image_review)
                    manifest = json.loads(Path(result["dependency_manifest"]).read_text(encoding="utf-8"))
                    self.assertEqual(4, manifest["head_image_prompt_contract"]["version"])
                    self.assertEqual("deferred", manifest["head_image_prompt_contract"]["geometry_regularization"])
                    self.assertEqual([1], [item["image_index"] for item in manifest["resources"]])
                    self.assertEqual(["edit_base"], [item["prompt_role"] for item in manifest["resources"]])
                    self.assertEqual([str(source)], [item["path"] for item in manifest["resources"]])
                    self.assertEqual(2, manifest["prompt_schema_version"])
                    self.assertEqual("chatgpt_images_2_5_v1", manifest["engine_profile"])
                    self.assertEqual("edit", manifest["render_mode"])
                    if view == FOUNDATION_VIEWS[0]:
                        analysis = compile_head_image_job({
                            "Job": "head-analysis", "Task": "head-image", "Character": "Test",
                            "Phase": "Adult", "Head View": view, "Template Path": str(template),
                            "Output Directory": str(root / view / "analysis"), "Reference Files": references,
                        }, PROJECT_ROOT, prompt_variant="analysis")
                        analysis_text = Path(analysis["final_prompt"]).read_text(encoding="utf-8")
                        self.assertIn("# Review Specification", analysis_text)
                        self.assertIn("Image 1", analysis_text)
                        self.assertIn("HEAD-IMAGE Adult CHARACTER REFERENCE", analysis_text)
                        self.assertNotIn("# Render Task", analysis_text)
                        self.assertNotIn("<!-- ZET:", analysis_text)



    def test_rejects_missing_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with self.assertRaisesRegex(Exception, "requires one head_image_source"):
                compile_head_image_job({
                    "Job": "missing",
                    "Task": "head-image",
                    "Character": "Test",
                    "Phase": "Adult",
                    "Head View": "Front",
                    "Template Path": str(PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Character_Template.md"),
                    "Output Directory": str(root / "output"),
                    "Reference Files": [],
                }, PROJECT_ROOT)



class HeadImageReferenceTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[PathService, AssetRepository, ReferenceService]:
        paths = PathService(config_for(root), PROJECT_ROOT)
        for phase in ("Adult", "Elder"):
            paths.character_path("Test", phase).mkdir(parents=True)
            paths.character_asset_path("Test", phase).mkdir(parents=True)
        adult_image = paths.character_asset_path("Test", "Adult") / "Head-Image_Front.png"
        adult_image.write_bytes(b"adult")
        (paths.character_path("Test", "Adult") / "Assets.json").write_text(json.dumps({
            "schema_version": 1,
            "next_asset_id": 2,
            "assets": [Asset(1, "Test", "Adult", "Head-Image", "Front", head_view="Front", asset_state="LOCKED", pipeline_stage="LOCKED", actor="HUMAN_AGENT", final_image_output=adult_image.name).__dict__],
        }), encoding="utf-8")
        elder_assets = [Asset(index + 1, "Test", "Elder", "Head-Image", view, head_view=view, final_image_output=f"Head-Image_{view}.png").__dict__ for index, view in enumerate(FOUNDATION_VIEWS)]
        (paths.character_path("Test", "Elder") / "Assets.json").write_text(json.dumps({"schema_version": 1, "next_asset_id": 9, "assets": elder_assets}), encoding="utf-8")
        repository = AssetRepository(paths)
        return paths, repository, ReferenceService(repository, paths)

    def _config_path(self, root: Path) -> Path:
        (root / "Queue").mkdir(exist_ok=True)
        path = root / "config.toml"
        path.write_text(f"""[BaseFolders]
BaseCharacterPath = "{(root / 'Characters').as_posix()}"
BaseAssetPath = "{(root / 'Assets').as_posix()}"
BasePipelinePath = "{(root / 'Pipelines').as_posix()}"
BaseAIQueuePath = "{(root / 'Queue').as_posix()}"
""", encoding="utf-8")
        return path

    def test_local_head_image_page_and_shared_asset_lookup_are_available(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._fixture(root)
            client = TestClient(create_app(self._config_path(root)))

            page = client.get("/local-head-image")
            self.assertEqual(200, page.status_code)
            self.assertIn("Paste an image here", page.text)
            self.assertIn("Generate other views", page.text)
            self.assertIn("background:'Background'", page.text)
            self.assertIn("gaze:'Gaze direction'", page.text)
            assets = client.get("/api/local/assets", params={"character": "Test", "phase": "Adult"})
            self.assertEqual(200, assets.status_code)
            self.assertEqual([], assets.json()["assets"])



    def test_manifest_api_lists_and_saves_optional_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._fixture(root)
            client = TestClient(create_app(self._config_path(root)))
            query = {"character": "Test", "phase": "Elder"}
            tasks = client.get("/api/head-image-manifest/tasks", params=query)
            self.assertEqual(tasks.status_code, 200)
            self.assertEqual(len(tasks.json()["tasks"]), 8)
            detail = client.get("/api/head-image-manifest/1", params=query)
            source_path = detail.json()["source_options"][0]["path"]
            saved = client.post("/api/head-image-manifest/1/source", params=query, json={"source_path": source_path, "apply_all": True})
            self.assertEqual(saved.status_code, 200)
            self.assertEqual(saved.json()["selected_source"]["source_phase"], "Adult")
            remaining = client.get("/api/head-image-manifest/2", params=query)
            self.assertEqual(remaining.json()["reference_files"], [])


class HeadImageFoundationTests(unittest.TestCase):
    def test_new_foundation_contains_three_eight_view_pipelines(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            service = CharacterOnboardingService(PathService(config_for(Path(temp_dir)), PROJECT_ROOT), PROJECT_ROOT)
            assets = service._foundation_assets("Test", "Adult")
            self.assertEqual(len(assets), 24)
            self.assertEqual([item["pipeline"] for item in assets[8:16]], ["Head-Image"] * 8)



class DirectAssemblyHeadImageDefaultTests(unittest.TestCase):

    def test_manifest_defaults_to_same_view_locked_head_image(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            character_path = root / "Characters" / "Test" / "Adult"
            asset_path = root / "Assets" / "Test" / "Adult"
            character_path.mkdir(parents=True)
            asset_path.mkdir(parents=True)
            body = asset_path / "Body-Reference_Front.png"
            head = asset_path / "Head-Image_Front.png"
            body.write_bytes(b"body")
            head.write_bytes(b"head")
            records = [
                Asset(1, "Test", "Adult", "Body-Reference", "Front", asset_state="LOCKED", pipeline_stage="LOCKED", actor="HUMAN_AGENT", final_image_output=body.name).__dict__,
                Asset(2, "Test", "Adult", "Head-Image", "Front", head_view="Front", asset_state="LOCKED", pipeline_stage="LOCKED", actor="HUMAN_AGENT", final_image_output=head.name).__dict__,
                Asset(3, "Test", "Adult", "Character-Assembly", "Front", head_view="Front", pipeline_stage="MANIFEST", final_image_output="Character-Assembly_Front_Front_Assembled.png").__dict__,
            ]
            (character_path / "Assets.json").write_text(json.dumps({"schema_version": 1, "next_asset_id": 4, "assets": records}), encoding="utf-8")
            context = WorkerContext(root / "pipeline", root / "candidate.png", root / "locked.png", character_path, asset_path)
            result = character_assembly_manifest_worker.run(Asset(**records[2]), context)
            self.assertTrue(result.success)
            saved = json.loads((character_path / "Assets.json").read_text(encoding="utf-8"))["assets"][2]
            self.assertEqual(saved["reference_files"], [])
            self.assertEqual([item["role"] for item in result.reference_files], ["body_reference", "head_image"])
            self.assertEqual(result.reference_files[1]["source_asset_id"], 2)
            other = asset_path / "Head-Image_Front_other.png"
            other.write_bytes(b"other head")
            records.append({**records[1], "asset_id": 4, "final_image_output": other.name})
            (character_path / "Assets.json").write_text(json.dumps({"assets": records}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Select a source reference"):
                character_assembly_manifest_worker.run(Asset(**records[2]), context)
            selected = Asset(**records[2])
            selected.reference_files = [{"role": "head_image", "source_asset_id": 4, "path": str(other)}]
            result = character_assembly_manifest_worker.run(selected, context)
            self.assertEqual(4, result.reference_files[1]["source_asset_id"])


if __name__ == "__main__":
    unittest.main()
