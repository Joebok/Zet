from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from zet.services.local_prompt_improvement_service import (
    LocalPromptImprovementService, ensure_view_reviews, record_compiler_sources,
)


class FakeAdapter:
    def __init__(self, root: Path, character_root: Path):
        self.root = root
        self.app = SimpleNamespace(config=SimpleNamespace(
            codex_default_model="gpt-6-luna", base_character_path=character_root))

    def detail(self, run_id: str, costume: str = "", *, upgrade_legacy: bool = False):
        spec = json.loads((self.root / "spec.json").read_text(encoding="utf-8"))
        state = json.loads((self.root / "state.json").read_text(encoding="utf-8"))
        spec, state = ensure_view_reviews(self.root, spec, state)
        candidates = []
        for item in spec["candidates"]:
            candidates.append({**item, **(state.get("candidates", {}).get(item["candidate_id"]) or {})})
        return {**spec, **state, "root": str(self.root), "candidates": candidates}


def make_run(tmp_path: Path, *, pipeline: str = "head-image", notes: bool = False):
    project = tmp_path / "project"
    root = tmp_path / "run"
    character_root = project / "Characters"
    character = character_root / "Tsaeytte" / "Adult" / "Character.md"
    character.parent.mkdir(parents=True)
    character.write_text("<!-- ZET:BEGIN BODY_PROPORTIONS -->\nShort torso.\n<!-- ZET:END BODY_PROPORTIONS -->\n", encoding="utf-8")
    root.mkdir()
    image_a, image_b = root / "one.png", root / "two.png"
    image_a.write_bytes(b"first rendered image")
    image_b.write_bytes(b"second rendered image")
    candidates = [
        {"candidate_id": "F-001", "view": "FRONT", "status": "GATE_REJECTED", "image_path": str(image_a),
         "human_review": {"decision": "reject", **({"notes": "Top is too wide"} if notes else {})}},
        {"candidate_id": "F-002", "view": "FRONT", "status": "FAILED", "image_path": str(image_b),
         "human_review": {"decision": "undecided", **({"notes": "Sword moved"} if notes else {})}},
        {"candidate_id": "F-003", "view": "FRONT", "status": "FAILED", "image_path": "",
         "render_error": "Renderer timed out", "human_review": {"decision": "undecided"}},
    ]
    spec = {"run_id": "run-id", "character": "Tsaeytte", "phase": "Adult", "views": ["FRONT"],
            "candidates": candidates, "kind": pipeline}
    state = {"candidates": {}, "rankings": {"FRONT": {"status": "COMPLETE"}}}
    (root / "spec.json").write_text(json.dumps(spec), encoding="utf-8")
    (root / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return LocalPromptImprovementService(FakeAdapter(root, character_root), pipeline, project), root, character


def test_candidate_notes_migrate_once_without_changing_decisions(tmp_path):
    service, root, _ = make_run(tmp_path, notes=True)
    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    state["candidates"] = {"F-002": {"human_review": {"decision": "keep", "notes": "Ponytail is too short"}}}
    (root / "state.json").write_text(json.dumps(state), encoding="utf-8")
    first = service.detail("run-id")
    second = service.detail("run-id")
    assert first["view_reviews"]["FRONT"]["observations"] == (
        "F-001: Top is too wide\n\nF-002: Sword moved\n\nF-002: Ponytail is too short")
    assert second["view_reviews"] == first["view_reviews"]
    assert [item["human_review"]["decision"] for item in second["candidates"]] == ["reject", "keep", "undecided"]
    assert all("notes" not in item["human_review"] for item in second["candidates"])
    saved = json.loads((root / "spec.json").read_text(encoding="utf-8"))
    assert all("notes" not in item["human_review"] for item in saved["candidates"])
    updated = service.save_observations("run-id", "FRONT", "Garment width varies")
    assert updated["view_reviews"]["FRONT"]["observations"] == "Garment width varies"


@pytest.mark.parametrize("pipeline", ["head-image", "body-reference", "character-assembly", "costume-dressing"])
def test_analysis_includes_rejected_and_failed_images_and_runs_once(tmp_path, monkeypatch, pipeline):
    service, _, _ = make_run(tmp_path, pipeline=pipeline)
    calls = []
    def fake_run(command, **kwargs):
        calls.append((command, kwargs["input"]))
        Path(command[command.index("--output-last-message") + 1]).write_text(
            json.dumps({"observations": "F-001 and F-002 differ in top width."}), encoding="utf-8")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr("zet.services.local_prompt_improvement_service.shutil.which", lambda _: "codex")
    monkeypatch.setattr("zet.services.local_prompt_improvement_service.subprocess.run", fake_run)
    monkeypatch.setattr("zet.services.local_prompt_improvement_service._POOL", SimpleNamespace(submit=lambda fn, *args: fn(*args)))
    result = service.start("run-id", "FRONT", automatic=True)
    ai = result["view_reviews"]["FRONT"]["ai_observations"]
    assert ai["status"] == "COMPLETE"
    assert [item["candidate_id"] for item in ai["missing_candidates"]] == ["F-003"]
    assert "Renderer timed out" in calls[0][1]
    assert calls[0][0].count("--image") == 2
    service.start("run-id", "FRONT", automatic=True)
    assert len(calls) == 1
    service.start("run-id", "FRONT")
    assert len(calls) == 2
    image = Path(result["candidates"][0]["image_path"])
    image.write_bytes(b"a changed image")
    assert service.detail("run-id")["view_reviews"]["FRONT"]["ai_observations"]["status"] == "STALE"
    service.reset_after_rerender("run-id", {"FRONT"})
    service.start("run-id", "FRONT", automatic=True)
    assert len(calls) == 3


@pytest.mark.parametrize("ranking_model", ["deterministic-single-survivor", "local-only"])
def test_initial_non_luna_ranking_still_starts_analysis(tmp_path, monkeypatch, ranking_model):
    service, root, _ = make_run(tmp_path, pipeline="costume-dressing")
    state = json.loads((root / "state.json").read_text(encoding="utf-8"))
    state["rankings"]["FRONT"]["model"] = ranking_model
    (root / "state.json").write_text(json.dumps(state), encoding="utf-8")
    (root / "two.png").unlink()
    calls = []
    def fake_run(command, **kwargs):
        calls.append(command)
        Path(command[command.index("--output-last-message") + 1]).write_text(
            json.dumps({"observations": "Only one image; the top is wider than described."}), encoding="utf-8")
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr("zet.services.local_prompt_improvement_service.shutil.which", lambda _: "codex")
    monkeypatch.setattr("zet.services.local_prompt_improvement_service.subprocess.run", fake_run)
    monkeypatch.setattr("zet.services.local_prompt_improvement_service._POOL", SimpleNamespace(submit=lambda fn, *args: fn(*args)))
    result = service.start("run-id", "FRONT", automatic=True)
    assert result["view_reviews"]["FRONT"]["ai_observations"]["status"] == "COMPLETE"
    assert calls[0].count("--image") == 1


@pytest.mark.parametrize("pipeline", ["head-image", "body-reference", "character-assembly", "costume-dressing"])
def test_package_uses_saved_prompt_and_flags_changed_sources(tmp_path, pipeline):
    service, root, character = make_run(tmp_path, pipeline=pipeline)
    prompt_dir = root / "prompts" / "FRONT"
    prompt_dir.mkdir(parents=True)
    (prompt_dir / "Final_Image_Prompt.md").write_text("Original compiled prompt", encoding="utf-8")
    (prompt_dir / "Prompt_Source_Map.json").write_text(json.dumps({"fragments": [
        {"source_path": str(character), "section_name": "BODY_PROPORTIONS"}]}), encoding="utf-8")
    record_compiler_sources(prompt_dir)
    character.write_text(character.read_text(encoding="utf-8") + "New edit\n", encoding="utf-8")
    guide = service.project_root / "Docs" / "Prompt_Compiler_Guide.md"
    guide.parent.mkdir()
    guide.write_text("Compiler guide", encoding="utf-8")
    package = service.create_package("run-id")
    try:
        with zipfile.ZipFile(package) as archive:
            names = set(archive.namelist())
            manifest = json.loads(archive.read("manifest.json"))
            assert "prompts/FRONT/Final_Image_Prompt.md" in names
            assert "images/FRONT/F-001.png" in names
            assert "images/FRONT/F-002.png" in names
            assert "Prompt_Compiler_Guide.md" in names
            assert "ChatGPT_Review_Request.md" in names
            assert archive.read("prompts/FRONT/Final_Image_Prompt.md") == b"Original compiled prompt"
            assert any(item.get("status") == "FAILED" for item in manifest["missing"])
            assert manifest["source_changes"]
    finally:
        package.unlink()


def test_shared_routes_save_observations_reanalyze_and_download(tmp_path, monkeypatch):
    from zet.web import local_character_asset_pipeline_router as router_module

    service, _, _ = make_run(tmp_path)
    calls = []
    class FakeWorkflow:
        def __init__(self, app, project_root, pipeline):
            self.prompt_improvement = service

        def action(self, name, **kwargs):
            calls.append(name)
            if name == "save_observations":
                return service.save_observations(kwargs["run_id"], kwargs["view"], kwargs["payload"]["observations"])
            if name == "reanalyze":
                return {"queued": True}
            raise AssertionError(name)

    monkeypatch.setattr(router_module, "LocalImagePipelineWorkflowService", FakeWorkflow)
    app = FastAPI()
    app.include_router(router_module.create_local_character_asset_pipeline_router(lambda: object(), tmp_path))
    with TestClient(app) as client:
        saved = client.put("/api/local/head-image/runs/run-id/views/FRONT/observations",
                           json={"observations": "Top varies in width"})
        assert saved.status_code == 200
        assert saved.json()["view_reviews"]["FRONT"]["observations"] == "Top varies in width"
        assert client.post("/api/local/head-image/runs/run-id/views/FRONT/reanalyze").json() == {"queued": True}
        package = client.get("/api/local/head-image/runs/run-id/prompt-improvement-package")
        assert package.status_code == 200
        assert package.headers["content-type"] == "application/zip"
    assert calls == ["save_observations", "reanalyze"]
