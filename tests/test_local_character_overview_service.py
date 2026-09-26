from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import zet.services.local_character_overview_service as overview_module
from zet.services.local_asset_store_service import LocalAssetStoreService
from zet.services.local_character_asset_pipeline_service import LocalCharacterAssetPipelineService
from zet.services.local_character_overview_service import LocalCharacterOverviewService
from support.project_fixture import write_project_fixture
from zet.web.app import create_app
from fastapi.testclient import TestClient


def _app(tmp_path: Path):
    character_root = tmp_path / "Characters"
    (character_root / "Mira" / "Adult").mkdir(parents=True)
    return SimpleNamespace(
        config=SimpleNamespace(base_character_path=str(character_root), base_library_path=str(tmp_path / "Library")),
        list_costumes=lambda character, phase: [SimpleNamespace(name="Blue Coat", slug="blue-coat")],
    )


def test_overview_shows_locked_costume_front_and_idle_placeholder(tmp_path: Path) -> None:
    app = _app(tmp_path)
    store = LocalAssetStoreService(app.config.base_library_path)
    source = tmp_path / "dressing.png"
    source.write_bytes(b"front image")
    store.record_selection("Mira", "Adult", "Costume-Dressing", "FRONT", candidate_id="c001",
                           image_path=source, batch_id="run", qualifier="Blue_Coat")
    store.lock("Mira", "Adult", "Costume-Dressing", "FRONT", "Blue_Coat")
    service = LocalCharacterOverviewService(app, tmp_path)

    result = service.overview()
    slot = result["rows"][0]["costumes"][0]
    assert slot["state"] == "COMPLETE"
    assert slot["image_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert "image/" in slot["image_url"]


def test_selected_front_prefers_finished_batch_then_latest_render(tmp_path: Path) -> None:
    app = _app(tmp_path)
    service = LocalCharacterOverviewService(app, tmp_path)
    images = {}
    runs = {}
    for run_id, created_at, rendered_at, rank_status in (
        ("older", "2026-01-01T00:00:00", "2026-01-02T00:00:00", "COMPLETE"),
        ("newer", "2026-02-01T00:00:00", "2026-03-01T00:00:00", "RUNNING"),
    ):
        image = tmp_path / f"{run_id}.png"
        image.write_bytes(run_id.encode())
        images[run_id] = image
        candidate_id = f"{run_id}-front"
        runs[run_id] = {
            "run_id": run_id, "created_at": created_at, "selected_views": {"FRONT": candidate_id},
            "rankings": {"FRONT": {"status": rank_status, "input_hashes": {candidate_id: hashlib.sha256(image.read_bytes()).hexdigest()}}},
            "candidates": [{"candidate_id": candidate_id, "view": "FRONT", "image_path": str(image),
                            "rendered_at": rendered_at, "status": "COMPLETE", "human_review": {"decision": "undecided"}}],
        }

    class Adapter:
        def list_runs(self, character, phase):
            return [{"run_id": key, "created_at": run["created_at"]} for key, run in runs.items()]

        def detail(self, run_id):
            return runs[run_id]

        @staticmethod
        def _hash(path):
            return hashlib.sha256(Path(path).read_bytes()).hexdigest()

        @staticmethod
        def _candidate_gates_current(run, candidate):
            return run["rankings"]["FRONT"]["status"] == "COMPLETE"

    service._pipeline_service = lambda pipeline: SimpleNamespace(adapter=Adapter())
    selected = service._front_selection("body-reference", "Mira", "Adult", "Blue Coat")
    assert selected["run_id"] == "older"


def test_start_is_idempotent_while_slot_is_active(tmp_path: Path, monkeypatch) -> None:
    service = LocalCharacterOverviewService(_app(tmp_path), tmp_path)
    monkeypatch.setattr(service, "_submit", lambda path, job_id: None)

    first = service.start("Mira", "Adult", "Blue Coat")
    second = service.start("Mira", "Adult", "Blue Coat")
    assert first["job_id"] == second["job_id"]
    assert first["status"] == "QUEUED"


def test_autogenerate_pipeline_uses_luna_without_mutating_frozen_app_config(tmp_path: Path, monkeypatch) -> None:
    @dataclass(frozen=True)
    class FrozenConfig:
        base_character_path: str
        base_library_path: str
        codex_default_model: str

    app = SimpleNamespace(config=FrozenConfig(str(tmp_path / "Characters"), str(tmp_path / "Library"), "gpt-6-astra"))
    service = LocalCharacterOverviewService(app, tmp_path)
    constructed = {}

    class Workflow:
        def __init__(self, pipeline_app, project_root, pipeline):
            constructed["config"] = pipeline_app.config
            constructed["app"] = pipeline_app

    monkeypatch.setattr(overview_module, "LocalImagePipelineWorkflowService", Workflow)
    service._pipeline_service("body-reference")

    assert constructed["config"].codex_default_model == "gpt-6-luna"
    assert app.config.codex_default_model == "gpt-6-astra"
    assert constructed["app"] is not app


def test_stop_is_terminal_and_a_new_start_gets_a_new_job_id(tmp_path: Path, monkeypatch) -> None:
    service = LocalCharacterOverviewService(_app(tmp_path), tmp_path)
    monkeypatch.setattr(service, "_submit", lambda path, job_id: None)
    first = service.start("Mira", "Adult", "Blue Coat")
    stopped = service.stop("Mira", "Adult", "Blue Coat")
    second = service.start("Mira", "Adult", "Blue Coat")
    assert stopped["status"] == "CANCELLED"
    assert second["job_id"] != first["job_id"]


def test_overview_page_and_read_endpoint(tmp_path: Path) -> None:
    config = write_project_fixture(tmp_path)
    costume = tmp_path / "Characters" / "Test" / "Adult" / "Costume_Test_Outfit.md"
    costume.write_text(
        "Costume Name: `Test Outfit`\nFootwear: `boots`\nFootwear Contact: `Boots planted.`\n\n"
        "<!-- ZET:BEGIN COSTUME_DESCRIPTION_FACTS -->\nBlue coat and boots.\n"
        "<!-- ZET:END COSTUME_DESCRIPTION_FACTS -->\n", encoding="utf-8"
    )
    with TestClient(create_app(config)) as client:
        page = client.get("/local-character-overview")
        overview = client.get("/api/local/character-overview")
    assert page.status_code == 200
    assert "Autogenerate" in page.text
    assert overview.status_code == 200
    slot = overview.json()["rows"][0]["costumes"][0]
    assert slot["name"] == "Test Outfit"
    assert slot["state"] == "IDLE"


def test_autogenerate_walks_all_pipeline_fronts_with_stubbed_batches(tmp_path: Path, monkeypatch) -> None:
    app = _app(tmp_path)
    store = LocalAssetStoreService(app.config.base_library_path)
    adapters = {}

    class Adapter:
        def __init__(self, pipeline):
            self.pipeline = pipeline
            self.runs = {}

        @staticmethod
        def _hash(path):
            return hashlib.sha256(Path(path).read_bytes()).hexdigest()

        @staticmethod
        def _candidate_gates_current(run, candidate):
            return True

        def list_runs(self, character, phase, costume=""):
            return [{"run_id": run_id, "created_at": run["created_at"]} for run_id, run in self.runs.items()]

        def detail(self, run_id, costume=""):
            return self.runs[run_id]

        def create_run(self, payload):
            if self.pipeline in {"character-assembly", "costume-dressing"}:
                assert payload["front_only"] is True
                upstream = "Body-Reference" if self.pipeline == "character-assembly" else "Character-Assembly"
                upstreams = [upstream]
                if self.pipeline == "character-assembly":
                    upstreams.append("Head-Image")
                for name in upstreams:
                    assert store.locked_assets("Mira", "Adult", pipeline=name)
            run_id = f"{self.pipeline}-{len(self.runs)}"
            image = tmp_path / f"{run_id}.png"
            image.write_bytes(run_id.encode())
            candidate = {"candidate_id": "c001", "view": "FRONT", "image_path": str(image),
                         "rendered_at": "2026-09-25T12:00:00+00:00", "status": "COMPLETE",
                         "human_review": {"decision": "undecided"}, "gates": {}}
            self.runs[run_id] = {
                "run_id": run_id, "root": str(tmp_path / run_id), "created_at": "2026-09-25T12:00:00+00:00",
                "character": "Mira", "phase": "Adult", "costume": payload.get("costume", ""),
                "candidates": [candidate], "selected_views": {},
                "rankings": {"FRONT": {"status": "COMPLETE", "ordered_candidate_ids": ["c001"],
                                         "luna_ordered_candidate_ids": ["c001"],
                                         "input_hashes": {"c001": self._hash(image)}}},
                "sources": {"FRONT": {}},
            }
            return self.runs[run_id]

        def select_view(self, run_id, view, candidate_id, costume="", *, autogenerate=False):
            assert autogenerate is True
            run = self.runs[run_id]
            candidate = run["candidates"][0]
            candidate["autogenerate_approval"] = {"approved_at": "now"}
            run["selected_views"][view] = candidate_id
            pipeline_name = {"body-reference": "Body-Reference", "head-image": "Head-Image",
                             "character-assembly": "Character-Assembly", "costume-dressing": "Costume-Dressing"}[self.pipeline]
            qualifier = LocalCharacterAssetPipelineService._safe(costume) if self.pipeline == "costume-dressing" else ""
            dependencies = []
            depends_on = {"character-assembly": ("Body-Reference", "Head-Image"),
                          "costume-dressing": ("Character-Assembly",)}.get(self.pipeline, ())
            for parent in depends_on:
                record = store.detail("Mira", "Adult")["assets"][store.key(parent, "FRONT")]
                dependencies.append({"key": store.key(parent, "FRONT"), "image_sha256": record["image_sha256"]})
            store.record_batch_selection("Mira", "Adult", pipeline_name, "FRONT", candidate_id=candidate_id,
                                         image_path=candidate["image_path"], batch_id=run_id,
                                         dependencies=dependencies, qualifier=qualifier)
            return run

        def lock_selected_view(self, run_id, view, costume=""):
            pipeline_name = {"body-reference": "Body-Reference", "head-image": "Head-Image",
                             "character-assembly": "Character-Assembly", "costume-dressing": "Costume-Dressing"}[self.pipeline]
            qualifier = LocalCharacterAssetPipelineService._safe(costume) if self.pipeline == "costume-dressing" else ""
            return store.lock("Mira", "Adult", pipeline_name, view, qualifier)

    for pipeline in ("body-reference", "head-image", "character-assembly", "costume-dressing"):
        adapters[pipeline] = Adapter(pipeline)
    service = LocalCharacterOverviewService(app, tmp_path)
    service._pipeline_service = lambda pipeline: SimpleNamespace(adapter=adapters[pipeline])
    monkeypatch.setattr(service, "_submit", lambda path, job_id: service._run_job(path, job_id))

    result = service.start("Mira", "Adult", "Blue Coat")
    assert result["status"] == "QUEUED"
    assert service.slot_status("Mira", "Adult", "Blue Coat")["status"] == "COMPLETE"
    assert len(store.locked_assets("Mira", "Adult")) == 4
    assert service.overview()["rows"][0]["costumes"][0]["state"] == "COMPLETE"
