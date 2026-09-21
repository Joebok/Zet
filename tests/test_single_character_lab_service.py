from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from zet.app import ZetApp
from zet.services.single_character_lab_service import (
    SingleCharacterLabError,
    SingleCharacterLabService,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _fixture(tmp_path: Path) -> tuple[ZetApp, SingleCharacterLabService]:
    library = tmp_path / "Library"
    character_root = library / "Characters" / "Ada" / "Adult"
    assets_root = library / "Assets" / "Ada" / "Adult"
    character_root.mkdir(parents=True)
    assets_root.mkdir(parents=True)
    costume_image = assets_root / "Costume-Dressing_Front_Formal-Gown.png"
    pose_image = assets_root / "Body-Reference_Front.png"
    Image.new("RGB", (100, 200), "blue").save(costume_image)
    Image.new("RGB", (100, 200), "white").save(pose_image)
    (character_root / "Assets.json").write_text(json.dumps({
        "next_asset_id": 3,
        "assets": [
            {
                "asset_id": 1,
                "character": "Ada",
                "phase": "Adult",
                "pipeline": "Costume-Dressing",
                "body_view": "Front",
                "costume": "Formal Gown",
                "asset_state": "LOCKED",
                "pipeline_stage": "LOCKED",
                "final_image_output": costume_image.name,
                "costume_path": "Characters/Ada/Adult/Costume_Formal_Gown.md",
            },
            {
                "asset_id": 2,
                "character": "Ada",
                "phase": "Adult",
                "pipeline": "Body-Reference",
                "body_view": "Front",
                "asset_state": "LOCKED",
                "pipeline_stage": "LOCKED",
                "final_image_output": pose_image.name,
            },
        ],
    }), encoding="utf-8")
    (character_root / "Character.md").write_text(
        "<!-- ZET:BEGIN BODY_DESCRIPTION_FACTS -->\nSilver-haired elf.\n<!-- ZET:END BODY_DESCRIPTION_FACTS -->\n"
        "<!-- ZET:BEGIN HEAD_DESCRIPTION_FACTS -->\nGreen eyes.\n<!-- ZET:END HEAD_DESCRIPTION_FACTS -->\n"
        "<!-- ZET:BEGIN HAIR_DESCRIPTION_FACTS -->\nChin-length silver hair.\n<!-- ZET:END HAIR_DESCRIPTION_FACTS -->\n",
        encoding="utf-8",
    )
    (character_root / "Costume_Formal_Gown.md").write_text(
        "<!-- ZET:BEGIN COSTUME_DESCRIPTION_FACTS -->\nDeep green formal gown.\n* Forbidden drift: no train, no armor.\n<!-- ZET:END COSTUME_DESCRIPTION_FACTS -->\n"
        "<!-- ZET:BEGIN COSTUME_DESCRIPTION_VIEW_FRONT -->\nEven floor-length hem.\n<!-- ZET:END COSTUME_DESCRIPTION_VIEW_FRONT -->\n",
        encoding="utf-8",
    )
    config = tmp_path / "config.toml"
    config.write_text(
        f"""
[BaseFolders]
BaseLibraryPath = "{library.as_posix()}"
BaseCharacterPath = "Characters"
BaseAssetPath = "Assets"
BasePipelinePath = "Pipelines"
BaseAIQueuePath = "{(tmp_path / 'Queue').as_posix()}"

[ComfyUI]
Profile = "comfyui-ipadapter-preview"
Checkpoint = "tastyrice.safetensors"
ServerURL = "http://127.0.0.1:8188"
""".lstrip(),
        encoding="utf-8",
    )
    app = ZetApp.from_config(config)
    return app, SingleCharacterLabService(app, PROJECT_ROOT)


def test_options_and_prompt_use_locked_costume_and_body_reference(tmp_path: Path) -> None:
    _app, service = _fixture(tmp_path)

    options = service.options("Ada", "Adult")
    prompt = service.prompt("Ada", "Adult", 1)

    assert options["appearances"][0]["label"] == "Formal Gown · Front"
    assert options["poses"][0]["view"] == "Front"
    assert options["default_checkpoint"] == "tastyrice.safetensors"
    assert "Silver-haired elf" in prompt["positive_prompt"]
    assert "Deep green formal gown" in prompt["positive_prompt"]
    assert "Even floor-length hem" in prompt["positive_prompt"]
    assert "Forbidden drift" not in prompt["positive_prompt"]
    assert "train, armor" in prompt["negative_prompt"]


def test_run_persists_and_completes_through_ai_proxy(tmp_path: Path, monkeypatch) -> None:
    app, service = _fixture(tmp_path)
    pose_tag = service.pose_options("Ada", "Adult")[0]["tag"]
    run = service.create_run({
        "character": "Ada",
        "phase": "Adult",
        "asset_id": 1,
        "pose_tag": pose_tag,
        "checkpoint": "tastyrice.safetensors",
        "count": 2,
        "reference_weight": 0.45,
    })
    asks_root = tmp_path / "asks"
    staged = []

    def fake_stage(manifest, prompt_path, target_output_dir, **kwargs):
        index = len(staged) + 1
        assert manifest["pipeline"] == "Single-Character-Lab"
        assert prompt_path.name == "Prompt.md"
        assert kwargs["image_generation"] == "comfyui"
        assert kwargs["render_preset"] == "image-recipe-lab-ipadapter-controlnet-sdxl"
        assert kwargs["render_overrides"]["character_reference_weight"] == 0.45
        references = kwargs["reference_files"]
        assert [item["role"] for item in references] == [
            "prompt_evolution_appearance", "prompt_evolution_pose", "prompt_evolution_init",
        ]
        with Image.open(references[0]["path"]) as conditioned:
            assert conditioned.size == (832, 1216)
        ask_path = asks_root / f"ask-{index}"
        ask_path.mkdir(parents=True)
        expected_output = f"result-{index}.png"
        (ask_path / "ask_manifest.json").write_text(json.dumps({
            "ask_id": ask_path.name,
            "expected_output": expected_output,
        }), encoding="utf-8")
        output = Path(target_output_dir) / "Local_Test_Renders" / expected_output
        output.parent.mkdir(parents=True)
        Image.new("RGB", (832, 1216), "blue").save(output)
        staged.append(kwargs)
        return ask_path

    monkeypatch.setattr(app.ai_proxy_service, "stage_render_task_local_render_ask", fake_stage)

    service.execute_run(run["run_id"])
    completed = service.detail(run["run_id"])

    assert completed["status"] == "COMPLETE"
    assert len(staged) == 2
    assert len(completed["proxy_jobs"]) == 2
    assert Path(completed["candidates"][0]["image_path"]).is_file()
    assert Path(completed["contact_sheet"]).is_file()
    assert completed["conditioning_width"] == 832
    assert completed["conditioning_height"] == 1216
    assert service.list_runs("Ada", "Adult")[0]["run_id"] == run["run_id"]


def test_padding_preserves_full_source_frame(tmp_path: Path) -> None:
    source = tmp_path / "source.png"
    destination = tmp_path / "conditioned.png"
    image = Image.new("RGB", (100, 200), "white")
    for y in range(20):
        for x in range(100):
            image.putpixel((x, y), (255, 0, 0))
            image.putpixel((x, 199 - y), (0, 255, 0))
    image.save(source)

    SingleCharacterLabService._pad_image_to_size(source, destination, 100, 150)

    with Image.open(destination) as conditioned:
        assert conditioned.size == (100, 150)
        assert conditioned.getpixel((50, 0))[0] > 200
        assert conditioned.getpixel((50, 149))[1] > 200


def test_recipe_search_plans_shared_seeds_and_freezes_inputs(tmp_path: Path) -> None:
    _app, service = _fixture(tmp_path)
    pose_tag = service.pose_options("Ada", "Adult")[0]["tag"]
    run = service.create_run({
        "character": "Ada", "phase": "Adult", "asset_id": 1, "pose_tag": pose_tag,
        "checkpoint": "tastyrice.safetensors", "mode": "recipe_search",
        "appearance_strengths": [0.35, 0.65], "pose_strengths": [0.5, 1.0],
        "seed_count": 2, "seeds": [9007199254740993, 9007199254740995],
    })

    assert run["candidate_count"] == 8
    assert len(run["recipes"]) == 4
    assert run["seeds"] == ["9007199254740993", "9007199254740995"]
    assert [item["seed"] for item in run["candidates"][:4]] == [
        "9007199254740993", "9007199254740995", "9007199254740993", "9007199254740995",
    ]
    assert Path(run["reference_image"]).is_file()
    assert Path(run["pose_image"]).is_file()
    assert run["reference_sha256"] == service._hash(Path(run["reference_image"]))


def test_candidate_review_and_resume_are_persistent(tmp_path: Path) -> None:
    _app, service = _fixture(tmp_path)
    pose_tag = service.pose_options("Ada", "Adult")[0]["tag"]
    run = service.create_run({
        "character": "Ada", "phase": "Adult", "asset_id": 1, "pose_tag": pose_tag,
        "checkpoint": "tastyrice.safetensors", "count": 2,
    })
    result = service.update_review(run["run_id"], "c001", {
        "decision": "keep", "shortlisted": True, "failure_reasons": [], "notes": "best", "cleanup_minutes": 2,
    })
    assert result["summary"]["acceptance_rate"] == 1.0
    stopped = service.request_stop(run["run_id"])
    assert stopped["status"] == "STOPPED"
    resumed = service.prepare_resume(run["run_id"])
    assert resumed["status"] == "QUEUED"
    assert service.detail(run["run_id"])["candidates"][0]["review"]["notes"] == "best"


def test_human_review_stores_only_differences_from_automatic_scores(tmp_path: Path) -> None:
    _app, service = _fixture(tmp_path)
    pose_tag = service.pose_options("Ada", "Adult")[0]["tag"]
    run = service.create_run({
        "character": "Ada", "phase": "Adult", "asset_id": 1, "pose_tag": pose_tag,
        "checkpoint": "tastyrice.safetensors", "count": 1,
    })
    run_path = service._run_path(run["run_id"])
    persisted = json.loads(run_path.read_text(encoding="utf-8"))
    automatic_scores = {
        "identity_fidelity": 4, "costume_fidelity": 3, "pose_orientation": 3,
        "composition_framing": 2, "technical_quality": 4, "style_fit": 3,
    }
    persisted["candidates"][0]["automatic_review"] = {"scores": automatic_scores}
    service._write(run_path, persisted)

    result = service.update_review(run["run_id"], "c001", {
        "decision": "keep", "scores": {**automatic_scores, "costume_fidelity": 2},
    })

    assert result["candidate"]["review"]["score_overrides"] == {"costume_fidelity": 2}
    assert "scores" not in result["candidate"]["review"]


def test_delete_run_removes_completed_run_and_refuses_active_run(tmp_path: Path) -> None:
    _app, service = _fixture(tmp_path)
    pose_tag = service.pose_options("Ada", "Adult")[0]["tag"]
    run = service.create_run({
        "character": "Ada", "phase": "Adult", "asset_id": 1, "pose_tag": pose_tag,
        "checkpoint": "tastyrice.safetensors", "count": 1,
    })
    run_root = service._run_path(run["run_id"]).parent

    try:
        service.delete_run(run["run_id"])
    except SingleCharacterLabError as exc:
        assert "Stop or finish" in str(exc)
    else:
        raise AssertionError("Expected active run deletion to be rejected")

    persisted = service.detail(run["run_id"])
    persisted["status"] = "COMPLETE"
    service._write(service._run_path(run["run_id"]), persisted)

    result = service.delete_run(run["run_id"])

    assert result == {"deleted": True, "run_id": run["run_id"]}
    assert not run_root.exists()


def test_candidate_limit_is_rejected(tmp_path: Path) -> None:
    _app, service = _fixture(tmp_path)
    try:
        service.preview({"mode": "recipe_search", "appearance_strengths": [0.1, 0.2, 0.3],
                         "pose_strengths": [0.1, 0.2, 0.3], "seed_count": 29})
    except SingleCharacterLabError as exc:
        assert "256" in str(exc)
    else:
        raise AssertionError("Expected candidate limit validation")


def test_modern_recipe_search_uses_supported_generation_axes(tmp_path: Path) -> None:
    _app, service = _fixture(tmp_path)

    plan = service.preview({
        "mode": "recipe_search", "adapter_id": "qwen-image-edit-2511",
        "appearance_strengths": [0.35, 0.45, 0.65], "pose_strengths": [0.5, 0.75, 1.0],
        "step_values": [16, 20, 24], "guidance_values": [1.0], "denoise_values": [1.0],
        "seed_count": 2,
    })

    assert plan["appearance_strengths"] == [0.0]
    assert plan["pose_strengths"] == [0.0]
    assert plan["step_values"] == [16.0, 20.0, 24.0]
    assert plan["recipe_count"] == 3
    assert plan["candidate_count"] == 6


def test_automatic_review_uses_ai_proxy_and_reconciles_result(tmp_path: Path) -> None:
    _app, service = _fixture(tmp_path)
    pose_tag = service.pose_options("Ada", "Adult")[0]["tag"]
    run = service.create_run({
        "character": "Ada", "phase": "Adult", "asset_id": 1, "pose_tag": pose_tag,
        "checkpoint": "tastyrice.safetensors", "count": 1,
    })
    run_path = service._run_path(run["run_id"])
    persisted = json.loads(run_path.read_text(encoding="utf-8"))
    candidate_image = run_path.parent / "candidate.png"
    Image.new("RGB", (832, 1216), "green").save(candidate_image)
    persisted["status"] = "COMPLETE"
    persisted["candidates"][0].update({"status": "COMPLETE", "image_path": str(candidate_image)})
    service._write(run_path, persisted)

    queued = service.queue_automatic_review(run["run_id"], "vision-model", [])

    assert queued["status"] == "QUEUED"
    assert len(queued["jobs"]) == 1
    ask = next(service.app.ai_proxy_service.ai_proxy_path_service.file_proxy_client.task_paths("ask"))
    manifest = json.loads((ask / "ask_manifest.json").read_text(encoding="utf-8"))
    assert manifest["worker_type"] == "ollama_generate"
    assert manifest["task_type"] == "single_character_lab_automatic_review"
    assert manifest["ollama_model"] == "vision-model"
    assert len(manifest["image_files"]) == 3
    assert manifest["candidate_id"] == "c001"
    assert "response_schema" in manifest

    output = Path(queued["jobs"][0]["output_path"])
    output.write_text(json.dumps({
        "hard_gates": {"identity": True, "costume": True, "anatomy": True, "composition": True},
        "scores": {"identity_fidelity": 4, "costume_fidelity": 4, "technical_quality": 3,
                   "pose_orientation": 3, "composition_framing": 3, "style_fit": 3},
        "failure_reasons": [], "evidence": "The visible requirements match.", "uncertainty": "",
    }), encoding="utf-8")

    reconciled = service.detail(run["run_id"])

    assert reconciled["automatic_review"]["status"] == "COMPLETE"
    assert reconciled["automatic_review"]["completed_count"] == 1
    review = reconciled["candidates"][0]["automatic_review"]
    assert review["model"] == "vision-model"
    assert review["rubric_version"] == 2
    assert review["prefilter_pass"] is True
