from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient
from zet.services.comfyui_workflow_registry import compile_prompt_workflow, QWEN_IMAGE_21_LOCAL_EDIT_WORKFLOW
from zet.services.local_asset_store_service import LocalAssetStoreService
from zet.services.local_body_reference_service import LocalBodyReferenceService
from zet.services.local_character_asset_pipeline_service import LocalCharacterAssetPipelineService, VIEWS
from zet.web.app import create_app


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class LocalCharacterAssetPipelineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.library = self.root / "Library"
        self.characters = self.library / "Characters"
        character_root = self.characters / "Test" / "Adult"
        character_root.mkdir(parents=True)
        shared_character = PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared" / "Character_Template.md"
        (character_root / "Character.md").write_text(shared_character.read_text(encoding="utf-8"), encoding="utf-8")
        (character_root / "Costume_Test_Outfit.md").write_text(
            "Costume Name: `Test Outfit`\nFootwear: `boots`\nFootwear Contact: `Boots planted.`\n\n"
            "<!-- ZET:BEGIN COSTUME_DESCRIPTION_FACTS -->\nBlue coat and boots.\n<!-- ZET:END COSTUME_DESCRIPTION_FACTS -->\n",
            encoding="utf-8",
        )
        self.app = SimpleNamespace(config=SimpleNamespace(base_library_path=str(self.library), base_character_path=str(self.characters)))
        self.store = LocalAssetStoreService(self.library)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _lock(self, pipeline: str, view: str, qualifier: str = "") -> dict:
        image = self.root / f"{pipeline}_{qualifier}_{view}.png"
        image.write_bytes(f"{pipeline}/{qualifier}/{view}".encode())
        self.store.record_selection("Test", "Adult", pipeline, view, candidate_id=f"{pipeline}_{view}",
                                    image_path=image, batch_id="fixture", qualifier=qualifier)
        return self.store.lock("Test", "Adult", pipeline, view, qualifier)

    def _sources(self, pipeline: str) -> None:
        for view in VIEWS:
            if pipeline == "character-assembly":
                self._lock("Body-Reference", view)
                self._lock("Head-Image", view)
            else:
                self._lock("Character-Assembly", view)

    def _set_assembly_front_anchor(self, service, run, *, lock: bool = False):
        candidate = next(item for item in run["candidates"] if item["view"] == "FRONT")
        image = Path(run["root"]) / "renders" / candidate["candidate_id"] / "front.png"
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b"selected assembly front")
        service._update(run["run_id"], candidate["candidate_id"], status="WAITING_FOR_GATES", image_path=str(image))
        service.run_candidate_gates(run["run_id"], candidate["candidate_id"])
        service.update_candidate(run["run_id"], candidate["candidate_id"], {"decision": "keep", "notes": "passed"})
        service.rank_view(run["run_id"], "FRONT")
        selected = service.select_view(run["run_id"], "FRONT", candidate["candidate_id"])
        if lock:
            service.lock_selected_view(run["run_id"], "FRONT")
        return selected, candidate

    def test_assembly_snapshots_matching_locked_inputs_and_uses_selected_front_anchor(self) -> None:
        self._sources("character-assembly")
        service = LocalCharacterAssetPipelineService(self.app, PROJECT_ROOT, "character-assembly")
        run = service.create_run({"character": "Test", "phase": "Adult", "front_count": 1, "other_count": 1,
                                  "seeds": list(range(8))})
        self.assertIsNone(run["front_anchor"])
        self.assertEqual(8, run["candidate_count"])
        self.assertEqual(set(VIEWS), set(run["sources"]))
        for view in VIEWS:
            self.assertEqual({"body_reference", "head_image"}, set(run["sources"][view]))
        with self.assertRaisesRegex(ValueError, "FRONT"):
            service._references(run, "LEFT_PROFILE")
        run, _ = self._set_assembly_front_anchor(service, run)
        self.assertEqual(["body_reference", "head_image", "front_assembly"],
                         [item["role"] for item in service._references(run, "LEFT_PROFILE")])
        compiled = service._compile(run, "LEFT_PROFILE", service._references(run, "LEFT_PROFILE"))
        prompt = Path(compiled["final_prompt"]).read_text(encoding="utf-8")
        self.assertIn("Image 1 is the locked Body-Reference image", prompt)
        self.assertIn("Image 3 is the selected FRONT Character-Assembly anchor", prompt)
        self.assertIn("preserve the established head-to-body scale", prompt)
        self.assertNotIn("legacy_static_prompt", json.dumps(compiled))

    def test_front_only_assembly_batch_snapshots_other_inputs_when_later_started(self) -> None:
        self._lock("Body-Reference", "FRONT")
        self._lock("Head-Image", "FRONT")
        service = LocalCharacterAssetPipelineService(self.app, PROJECT_ROOT, "character-assembly")
        run = service.create_run({"character": "Test", "phase": "Adult", "front_count": 1,
                                  "other_count": 1, "front_only": True, "seeds": list(range(8))})
        self.assertEqual({"FRONT"}, set(run["sources"]))
        self.assertEqual(8, run["candidate_count"])
        run, _ = self._set_assembly_front_anchor(service, run, lock=True)
        self._lock("Body-Reference", "LEFT_PROFILE")
        self._lock("Head-Image", "LEFT_PROFILE")
        refreshed = service.detail(run["run_id"])
        refs = service._references(refreshed, "LEFT_PROFILE")
        self.assertEqual(["body_reference", "head_image", "front_assembly"], [item["role"] for item in refs])
        self.assertIn("LEFT_PROFILE", service.detail(run["run_id"])["sources"])

    def test_autogenerate_front_selection_records_distinct_approval(self) -> None:
        self._sources("character-assembly")
        service = LocalCharacterAssetPipelineService(self.app, PROJECT_ROOT, "character-assembly")
        run = service.create_run({"character": "Test", "phase": "Adult", "front_count": 1,
                                  "other_count": 1, "seeds": list(range(8))})
        front = next(item for item in run["candidates"] if item["view"] == "FRONT")
        image = Path(run["root"]) / "renders" / front["candidate_id"] / "front.png"
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b"autogenerated front")
        service._update(run["run_id"], front["candidate_id"], status="WAITING_FOR_GATES", image_path=str(image))
        service.run_candidate_gates(run["run_id"], front["candidate_id"])
        ranked = service.rank_view(run["run_id"], "FRONT")
        self.assertEqual([front["candidate_id"]], ranked["rankings"]["FRONT"]["luna_ordered_candidate_ids"])
        selected = service.select_view(run["run_id"], "FRONT", front["candidate_id"], autogenerate=True)
        selected_front = next(item for item in selected["candidates"] if item["candidate_id"] == front["candidate_id"])
        self.assertEqual("undecided", selected_front["human_review"]["decision"])
        self.assertIn("autogenerate_approval", selected_front)
        self.assertTrue(service.lock_selected_view(run["run_id"], "FRONT")["locked"])

    def test_costume_dressing_autogenerate_front_selection_records_and_locks(self) -> None:
        self._sources("costume-dressing")
        service = LocalCharacterAssetPipelineService(self.app, PROJECT_ROOT, "costume-dressing")
        costume = "Test Outfit"
        run = service.create_run({"character": "Test", "phase": "Adult", "costume": costume,
                                  "front_count": 1, "other_count": 1, "seeds": list(range(8))})
        front = next(item for item in run["candidates"] if item["view"] == "FRONT")
        image = Path(run["root"]) / "renders" / front["candidate_id"] / "front.png"
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b"autogenerated costume front")
        service._update(run["run_id"], front["candidate_id"], costume, status="WAITING_FOR_GATES",
                        image_path=str(image))
        service.run_candidate_gates(run["run_id"], front["candidate_id"], costume)
        ranked = service.rank_view(run["run_id"], "FRONT", costume)
        self.assertEqual([front["candidate_id"]], ranked["rankings"]["FRONT"]["luna_ordered_candidate_ids"])

        selected = service.select_view(run["run_id"], "FRONT", front["candidate_id"], costume,
                                       autogenerate=True)
        selected_front = next(item for item in selected["candidates"] if item["candidate_id"] == front["candidate_id"])
        self.assertEqual("undecided", selected_front["human_review"]["decision"])
        self.assertIn("autogenerate_approval", selected_front)
        self.assertTrue(service.lock_selected_view(run["run_id"], "FRONT", costume)["locked"])

    def test_manual_rank_changes_preserve_original_luna_order(self) -> None:
        self._sources("character-assembly")
        service = LocalCharacterAssetPipelineService(self.app, PROJECT_ROOT, "character-assembly")
        run = service.create_run({"character": "Test", "phase": "Adult", "front_count": 2,
                                  "other_count": 1, "seeds": list(range(9))})
        ids = [item["candidate_id"] for item in run["candidates"] if item["view"] == "FRONT"]
        root, state = service._state(run["run_id"])
        state["rankings"] = {"FRONT": {"status": "COMPLETE", "ordered_candidate_ids": ids.copy(),
                                        "luna_ordered_candidate_ids": ids.copy(), "entries": [
                                            {"candidate_id": item} for item in ids]}}
        service._write(root / "state.json", state)
        moved = service.move_rank(run["run_id"], "FRONT", ids[0], "down")
        ranking = moved["rankings"]["FRONT"]
        self.assertEqual(ids[::-1], ranking["ordered_candidate_ids"])
        self.assertEqual(ids, ranking["luna_ordered_candidate_ids"])

    def test_non_front_assembly_view_depends_on_locked_front_anchor(self) -> None:
        self._sources("character-assembly")
        service = LocalCharacterAssetPipelineService(self.app, PROJECT_ROOT, "character-assembly")
        run = service.create_run({"character": "Test", "phase": "Adult", "front_count": 1, "other_count": 1,
                                  "seeds": list(range(8))})
        run, front_candidate = self._set_assembly_front_anchor(service, run, lock=True)
        candidate = next(item for item in run["candidates"] if item["view"] == "RIGHT_PROFILE")
        image = Path(run["root"]) / "renders" / candidate["candidate_id"] / "Local_Test_Renders" / "candidate.png"
        image.parent.mkdir(parents=True)
        image.write_bytes(b"right profile assembly")
        service._update(run["run_id"], candidate["candidate_id"], status="WAITING_FOR_GATES", image_path=str(image))
        service.run_candidate_gates(run["run_id"], candidate["candidate_id"])
        ranked = service.rank_view(run["run_id"], "RIGHT_PROFILE")
        selected = service.select_view(run["run_id"], "RIGHT_PROFILE", candidate["candidate_id"])
        locked = service.lock_selected_view(run["run_id"], "RIGHT_PROFILE")
        self.assertEqual("COMPLETE", ranked["rankings"]["RIGHT_PROFILE"]["status"])
        self.assertEqual(candidate["candidate_id"], selected["selected_views"]["RIGHT_PROFILE"])
        self.assertTrue(locked["locked"])
        self.assertEqual(front_candidate["candidate_id"], selected["front_anchor"])
        self.assertIn(service.asset_store.key("Character-Assembly", "FRONT"),
                      [item["key"] for item in locked["dependencies"]])

    def test_other_views_are_claimed_once_and_require_a_passed_front_anchor(self) -> None:
        self._sources("character-assembly")
        service = LocalCharacterAssetPipelineService(self.app, PROJECT_ROOT, "character-assembly")
        run = service.create_run({"character": "Test", "phase": "Adult", "front_count": 1, "other_count": 1,
                                  "seeds": list(range(8))})
        front = next(item for item in run["candidates"] if item["view"] == "FRONT")
        image = Path(run["root"]) / "renders" / front["candidate_id"] / "front.png"
        image.parent.mkdir(parents=True, exist_ok=True)
        image.write_bytes(b"front")
        service._update(run["run_id"], front["candidate_id"], status="WAITING_FOR_GATES", image_path=str(image))
        service.run_candidate_gates(run["run_id"], front["candidate_id"])
        with self.assertRaisesRegex(ValueError, "pass a FRONT"):
            service.select_view(run["run_id"], "FRONT", front["candidate_id"])
        service.update_candidate(run["run_id"], front["candidate_id"], {"decision": "keep"})
        service.rank_view(run["run_id"], "FRONT")
        service.select_view(run["run_id"], "FRONT", front["candidate_id"])
        first = service.proceed(run["run_id"])
        second = service.proceed(run["run_id"])
        self.assertEqual(list(VIEWS[1:]), first["target_views"])
        self.assertEqual([], second["target_views"])
        self.assertTrue(all(item["status"] == "QUEUED" for item in second["candidates"] if item["view"] != "FRONT"))

    def test_human_review_preserves_ranking_unless_rejection_changes_survivors(self) -> None:
        self._sources("character-assembly")
        service = LocalCharacterAssetPipelineService(self.app, PROJECT_ROOT, "character-assembly")
        run = service.create_run({"character": "Test", "phase": "Adult", "front_count": 2, "other_count": 1,
                                  "seeds": list(range(9))})
        candidates = [item for item in run["candidates"] if item["view"] == "FRONT"]
        for candidate in candidates:
            image = Path(run["root"]) / "renders" / candidate["candidate_id"] / "front.png"
            image.parent.mkdir(parents=True, exist_ok=True)
            image.write_bytes(candidate["candidate_id"].encode())
            service._update(run["run_id"], candidate["candidate_id"], status="WAITING_FOR_HUMAN_REVIEW",
                           image_path=str(image))
        candidates = [item for item in service.detail(run["run_id"])["candidates"] if item["view"] == "FRONT"]
        root, state = service._state(run["run_id"])
        state["rankings"] = {"FRONT": {
            "status": "COMPLETE", "ordered_candidate_ids": ["c002", "c001"],
            "entries": [{"candidate_id": "c002", "reason": "Best match."},
                        {"candidate_id": "c001", "reason": "Second best."}],
            "input_hashes": {item["candidate_id"]: service._hash(Path(item["image_path"])) for item in candidates},
        }}
        service._write(root / "state.json", state)

        saved = service.update_candidate(run["run_id"], "c001", {"decision": "keep", "notes": "Looks good."})
        self.assertEqual("COMPLETE", saved["rankings"]["FRONT"]["status"])
        self.assertEqual(["c002", "c001"], saved["rankings"]["FRONT"]["ordered_candidate_ids"])
        self.assertEqual("Second best.", saved["rankings"]["FRONT"]["entries"][1]["reason"])

        rejected = service.update_candidate(run["run_id"], "c001", {"decision": "reject", "notes": "Changed my mind."})
        self.assertEqual("STALE", rejected["rankings"]["FRONT"]["status"])
        self.assertEqual(["c002", "c001"], rejected["rankings"]["FRONT"]["ordered_candidate_ids"])
        self.assertIn("Re-rank", rejected["rankings"]["FRONT"]["stale_reason"])

        service._update(run["run_id"], "c001", rejection_gate="framing", status="WAITING_FOR_HUMAN_REVIEW",
                        human_review={"decision": "undecided", "notes": ""})
        root, state = service._state(run["run_id"])
        state["rankings"]["FRONT"] = {
            "status": "COMPLETE", "ordered_candidate_ids": ["c002"],
            "entries": [{"candidate_id": "c002", "reason": "Only current survivor."}],
            "input_hashes": {"c002": service._hash(Path(next(item for item in candidates if item["candidate_id"] == "c002")["image_path"]))},
        }
        service._write(root / "state.json", state)
        newly_eligible = service.update_candidate(run["run_id"], "c001", {"decision": "keep"})
        self.assertEqual("STALE", newly_eligible["rankings"]["FRONT"]["status"])

    def test_assembly_batch_does_not_start_non_front_views_without_anchor(self) -> None:
        self._sources("character-assembly")
        service = LocalCharacterAssetPipelineService(self.app, PROJECT_ROOT, "character-assembly")
        run = service.create_run({"character": "Test", "phase": "Adult", "front_count": 1, "other_count": 1,
                                  "seeds": list(range(8))})
        front = next(item for item in run["candidates"] if item["view"] == "FRONT")
        service._update(run["run_id"], front["candidate_id"], status="GATE_REJECTED")

        service.execute_run(run["run_id"])
        waiting = service.detail(run["run_id"])

        self.assertEqual("AWAITING_FRONT_ANCHOR", waiting["status"])
        self.assertTrue(all(not item.get("ask_id") for item in waiting["candidates"] if item["view"] != "FRONT"))

        service.execute_run(run["run_id"], views={"BACK"})
        blocked = service.detail(run["run_id"])
        self.assertEqual("AWAITING_FRONT_ANCHOR", blocked["status"])
        self.assertIn("Select a FRONT candidate", blocked["error"])

    def test_assembly_automatically_ranks_after_all_candidate_gates_finish(self) -> None:
        self._sources("character-assembly")
        service = LocalCharacterAssetPipelineService(self.app, PROJECT_ROOT, "character-assembly")
        run = service.create_run({"character": "Test", "phase": "Adult", "front_count": 2, "other_count": 1,
                                  "seeds": list(range(9))})
        front = [item for item in run["candidates"] if item["view"] == "FRONT"]
        events = []
        for candidate in front:
            image = Path(run["root"]) / "renders" / candidate["candidate_id"] / "front.png"
            image.parent.mkdir(parents=True, exist_ok=True)
            image.write_bytes(candidate["candidate_id"].encode())
            service._update(run["run_id"], candidate["candidate_id"], status="WAITING_FOR_GATES", image_path=str(image))

        def finish_gates(run_id: str, candidate_id: str, costume: str = "") -> bool:
            events.append(("gates", candidate_id))
            service._update(run_id, candidate_id, costume, status="WAITING_FOR_HUMAN_REVIEW")
            return True

        def rank(run_id: str, view: str, costume: str = "") -> dict:
            events.append(("rank", view))
            return service.detail(run_id, costume)

        with patch.object(service, "run_candidate_gates", side_effect=finish_gates), \
             patch.object(service, "rank_view", side_effect=rank):
            service.execute_run(run["run_id"])

        self.assertEqual([("gates", item["candidate_id"]) for item in front] + [("rank", "FRONT")], events)

    def test_changed_locked_source_makes_candidate_gates_stale(self) -> None:
        self._sources("character-assembly")
        service = LocalCharacterAssetPipelineService(self.app, PROJECT_ROOT, "character-assembly")
        run = service.create_run({"character": "Test", "phase": "Adult", "front_count": 1, "other_count": 1,
                                  "seeds": list(range(8))})
        run, _ = self._set_assembly_front_anchor(service, run)
        candidate = next(item for item in run["candidates"] if item["view"] == "BACK")
        image = Path(run["root"]) / "renders" / candidate["candidate_id"] / "Local_Test_Renders" / "candidate.png"
        image.parent.mkdir(parents=True)
        image.write_bytes(b"back assembly")
        service._update(run["run_id"], candidate["candidate_id"], status="WAITING_FOR_GATES", image_path=str(image))
        service.run_candidate_gates(run["run_id"], candidate["candidate_id"])
        current = service.detail(run["run_id"])
        self.assertTrue(service._candidate_gates_current(current, candidate | {"image_path": str(image),
                           "gates": next(item for item in current["candidates"] if item["candidate_id"] == candidate["candidate_id"])["gates"]}))
        body_key = service.asset_store.key("Body-Reference", "BACK")
        body_path = Path(current["local_assets"][body_key]["locked_image_path"])
        body_path.write_bytes(b"changed locked image")
        refreshed = service.detail(run["run_id"])
        changed = next(item for item in refreshed["candidates"] if item["candidate_id"] == candidate["candidate_id"])
        self.assertFalse(service._candidate_gates_current(refreshed, changed))
        self.assertEqual("EMPTY", service.rank_view(run["run_id"], "BACK")["rankings"]["BACK"]["status"])

    def test_costume_keys_are_scoped_and_later_prompt_uses_front_guide(self) -> None:
        self._sources("costume-dressing")
        self._lock("Costume-Dressing", "FRONT", "Other Outfit")
        self.assertNotEqual(self.store.key("Costume-Dressing", "FRONT", "Test Outfit"),
                            self.store.key("Costume-Dressing", "FRONT", "Other Outfit"))
        service = LocalCharacterAssetPipelineService(self.app, PROJECT_ROOT, "costume-dressing")
        run = service.create_run({"character": "Test", "phase": "Adult", "costume": "Test Outfit",
                                  "front_count": 1, "other_count": 1, "use_front_anchor": True,
                                  "seeds": list(range(8))})
        front_candidate = next(item for item in run["candidates"] if item["view"] == "FRONT")
        front_image = Path(run["root"]) / "renders" / front_candidate["candidate_id"] / "front.png"
        front_image.parent.mkdir(parents=True, exist_ok=True)
        front_image.write_bytes(b"selected costume front")
        state = service._read(Path(run["root"]) / "state.json")
        state["selected_views"]["FRONT"] = front_candidate["candidate_id"]
        state["front_anchor"] = front_candidate["candidate_id"]
        service._write(Path(run["root"]) / "state.json", state)
        service._update(run["run_id"], front_candidate["candidate_id"], "Test Outfit", image_path=str(front_image))
        current = service.detail(run["run_id"], "Test Outfit")
        refs = service._references(current, "BACK")
        compiled = service._compile(current, "BACK", refs)
        prompt = Path(compiled["final_prompt"]).read_text(encoding="utf-8")
        self.assertEqual(["character_assembly", "front_costume"], [item["role"] for item in refs])
        self.assertIn("Image 2 is the selected FRONT costume image", prompt)

    def test_qwen_local_edit_binds_one_to_three_images_in_input_order(self) -> None:
        profile = {"text_encoder": "encoder", "vae": "vae", "steps": 2}
        common = {"positive_prompt": "edit", "negative_prompt": "", "profile": profile,
                  "checkpoint": "model", "seed": 1, "width": 832, "height": 1216, "output_prefix": "test",
                  "available_node_types": {"UNETLoader", "CLIPLoader", "VAELoader", "TextEncodeQwenImage21",
                                            "LoadImage", "EmptyLatentImage", "KSampler", "VAEDecode", "SaveImage"}}
        for count in (1, 2, 3):
            with self.subTest(reference_count=count):
                refs = [{"role": str(index), "path": f"image_{index}.png"} for index in range(1, count + 1)]
                compiled = compile_prompt_workflow(QWEN_IMAGE_21_LOCAL_EDIT_WORKFLOW, **common, reference_files=refs)
                node = compiled.workflow["4"]["inputs"]
                self.assertEqual([f"image_{index}.png" for index in range(1, count + 1)],
                                 [compiled.debug["references_used"][index - 1]["path"] for index in range(1, count + 1)])
                self.assertEqual(count, len([key for key in node if key.startswith("images.image_")]))

    def test_local_pipeline_pages_and_gate_catalog_are_exposed(self) -> None:
        config_path = self.root / "config.toml"
        asset_root, pipeline_root, queue_root = self.library / "Assets", self.library / "Pipelines", self.library / "Queue"
        config_path.write_text(f"""[BaseFolders]
BaseLibraryPath = "{self.library.as_posix()}"
BaseCharacterPath = "{self.characters.as_posix()}"
BaseAssetPath = "{asset_root.as_posix()}"
BasePipelinePath = "{pipeline_root.as_posix()}"
BaseAIQueuePath = "{queue_root.as_posix()}"
""", encoding="utf-8")
        with TestClient(create_app(config_path, validate_catalog_on_create=False)) as client:
            assembly = client.get("/local-character-assembly", follow_redirects=False)
            dressing = client.get("/local-costume-dressing", follow_redirects=False)
            body_reference = client.get("/local-body-reference", follow_redirects=False)
            head_image = client.get("/local-head-image", follow_redirects=False)
            context = {"character": "Test", "phase": "Adult", "front_count": 1, "other_count": 1}
            previews = {
                pipeline: client.post(f"/api/local/{pipeline}/preview", json={**context, **extra})
                for pipeline, extra in (("body-reference", {}), ("head-image", {}),
                                        ("character-assembly", {}), ("costume-dressing", {"costume": "Test Outfit"}))
            }
            assembly_gates = client.get("/api/local-gates/local-character-assembly")
            self.assertEqual((307, "/?page=local-character-assembly"), (assembly.status_code, assembly.headers["location"]))
            self.assertEqual((307, "/?page=local-costume-dressing"), (dressing.status_code, dressing.headers["location"]))
            self.assertEqual((307, "/?page=local-body-reference"), (body_reference.status_code, body_reference.headers["location"]))
            self.assertEqual((307, "/?page=local-head-image"), (head_image.status_code, head_image.headers["location"]))
            self.assertEqual({200}, {response.status_code for response in previews.values()})
            for pipeline, response in previews.items():
                self.assertEqual(pipeline, response.json()["pipeline_config"]["key"])
                self.assertIn("can_create", response.json())
                self.assertIn("blocking_reasons", response.json())
            self.assertTrue(previews["body-reference"].json()["can_create"])
            self.assertTrue(previews["head-image"].json()["can_create"])
            self.assertFalse(previews["character-assembly"].json()["can_create"])
            self.assertFalse(previews["costume-dressing"].json()["can_create"])
            self.assertEqual(200, assembly_gates.status_code)
            self.assertEqual({"Disabled"}, set(assembly_gates.json()["statuses"].values()))

            body_service = LocalBodyReferenceService(self.app, PROJECT_ROOT)
            with patch.object(body_service, "_compile_view", side_effect=lambda root, character, phase, view, index: {
                "view": view, "view_index": index, "manual_prompt": view, "qwen_prompt": view,
                "prompt_path": "", "prompt_sha256": view, "source_map": "", "dependency_manifest": "",
            }):
                run = body_service.create_run({**context, "seeds": list(range(8))})
            image = Path(run["root"]) / "renders" / "c001" / "front.png"
            image.parent.mkdir(parents=True)
            image.write_bytes(b"body reference image")
            body_service._candidate_update(run["run_id"], "c001", {"image_path": str(image)})
            response = client.get(f"/api/local/body-reference/runs/{run['run_id']}/images/c001")
            self.assertEqual(200, response.status_code)
            self.assertEqual(b"body reference image", response.content)


if __name__ == "__main__":
    unittest.main()
