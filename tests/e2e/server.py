"""Run Zet against an isolated copy of the small local test library."""
from __future__ import annotations

import argparse
import atexit
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import webbrowser
from urllib.error import URLError
from urllib.request import urlopen

import uvicorn

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEED = PROJECT_ROOT / "tests" / "library"
RUN_ROOT = PROJECT_ROOT / "test-results" / "narrative-e2e"


def scenario_slug(value: str) -> str:
    safe = "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
    return "-".join(part for part in safe.split("-") if part)[:70] or "failed"


def live_preflight(root: Path) -> list[str]:
    blockers = []
    model = os.environ.get("ZET_LIVE_TEST_NARRATIVE_MODEL", "").strip()
    checkpoint = os.environ.get("ZET_LIVE_TEST_CHECKPOINT", "").strip()
    comfy = os.environ.get("ZET_LIVE_TEST_COMFYUI_URL", "http://127.0.0.1:8188").rstrip("/")
    if not model:
        blockers.append("Set ZET_LIVE_TEST_NARRATIVE_MODEL to an installed Ollama model.")
    if not checkpoint:
        blockers.append("Set ZET_LIVE_TEST_CHECKPOINT to an installed ComfyUI checkpoint.")
    proxy_root = PROJECT_ROOT.parent / "AI_Proxy"
    proxy_python = proxy_root / ".venv" / "Scripts" / "python.exe" if os.name == "nt" else proxy_root / ".venv" / "bin" / "python"
    if not proxy_python.is_file():
        blockers.append(f"AI Proxy interpreter not found: {proxy_python}")
    else:
        try:
            result = subprocess.run([str(proxy_python), "-c", "import sys, file_proxy; assert sys.version_info.major == 3"],
                                    capture_output=True, text=True, timeout=5, check=False)
            if result.returncode:
                blockers.append("AI Proxy Python 3 cannot import its File Proxy runtime.")
        except (OSError, subprocess.TimeoutExpired):
            blockers.append("AI Proxy Python 3 failed its runtime preflight.")
    try:
        with urlopen(comfy + "/system_stats", timeout=3):
            pass
        with urlopen(comfy + "/models/checkpoints", timeout=3) as response:
            checkpoints = json.loads(response.read().decode("utf-8"))
        if checkpoint and checkpoint not in checkpoints:
            blockers.append(f"ComfyUI checkpoint is unavailable: {checkpoint}")
    except (OSError, URLError, ValueError, TimeoutError):
        blockers.append(f"ComfyUI is not ready at {comfy}.")
    if model:
        try:
            with urlopen("http://127.0.0.1:11434/api/tags", timeout=3) as response:
                models = json.loads(response.read().decode("utf-8")).get("models", [])
            if model not in {str(item.get("name") or "") for item in models}:
                blockers.append(f"Ollama model is unavailable: {model}")
        except (OSError, URLError, ValueError, TimeoutError):
            blockers.append("Ollama is not ready at http://127.0.0.1:11434.")
    try:
        result = subprocess.run([sys.executable, "-c", "import sys, AI_Manager.ollama_proxy_worker, AI_Manager.local_image_proxy_worker; assert sys.version_info.major == 3"],
                                cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=5, check=False)
        if result.returncode:
            blockers.append("The verified Zet Python 3 interpreter cannot load the registered live workers.")
    except (OSError, subprocess.TimeoutExpired):
        blockers.append("The verified Zet Python 3 interpreter failed its worker preflight.")
    return blockers


def start_private_proxy(root: Path, config: Path, comfy_url: str):
    proxy_root = PROJECT_ROOT.parent / "AI_Proxy"
    proxy_python = proxy_root / ".venv" / "Scripts" / "python.exe" if os.name == "nt" else proxy_root / ".venv" / "bin" / "python"
    registry = root / "registry"
    registry.mkdir(parents=True, exist_ok=True)
    registry_data = {"subscriber_id": "zet", "workers": {
        name: {"backend": provider, "command": [str(proxy_python), "-m", "file_proxy.ai_worker", "--provider", provider],
               "working_directory": str(proxy_root), "timeout_seconds": 7600}
        for name, provider in (("ai_ollama", "ollama"), ("ai_codex", "codex"), ("ai_comfyui", "comfyui"))}}
    (registry / "zet.json").write_text(json.dumps(registry_data, indent=2), encoding="utf-8")
    runtime = {"runtime_dir": str(root / "AI_Proxy_Runtime"),
               "managed_comfyui": {"enabled": False, "upstream": comfy_url},
               "queue_wait_seconds": 600, "generation_settlement_seconds": 1200}
    runtime_path = root / "runtime-config.json"
    runtime_path.write_text(json.dumps(runtime, indent=2), encoding="utf-8")
    validation = subprocess.run(
        [str(proxy_python), "-m", "file_proxy.cli", "--root", str(root / "Queue"),
         "--registry-dir", str(registry), "--runtime-config", str(runtime_path),
         "validate-subscriber", "zet"],
        cwd=proxy_root, capture_output=True, text=True, timeout=10, check=False,
    )
    if validation.returncode:
        raise RuntimeError(f"Private AI Proxy configuration is invalid: {validation.stderr.strip() or validation.stdout.strip()}")
    log = (root / "ai-proxy.log").open("ab")
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        return subprocess.Popen([str(proxy_python), "-m", "file_proxy.cli", "--root", str(root / "Queue"),
                                 "--registry-dir", str(registry), "--runtime-config", str(runtime_path),
                                 "run", "--external-comfyui"], cwd=proxy_root, stdout=log,
                                stderr=subprocess.STDOUT, creationflags=flags)
    finally:
        log.close()


def prepare(mode: str) -> Path:
    root = RUN_ROOT / mode
    expected_parent = (PROJECT_ROOT / "test-results").resolve()
    if root.resolve().parent.parent != expected_parent:
        raise RuntimeError(f"Refusing to prepare unexpected test path: {root}")
    if root.exists():
        shutil.rmtree(root)
    library = root / "Library"
    queue = root / "Queue"
    library.mkdir(parents=True)
    shutil.copytree(SEED / "Test", library / "Test")
    shutil.copytree(PROJECT_ROOT / "Shared_Library" / "Characters" / "_Shared",
                    root / "Shared_Library" / "Characters" / "_Shared")
    (root / "Config").mkdir()
    for name in ("Prompt_Section_Metadata.json", "Local_Render_Presets.json"):
        shutil.copy2(PROJECT_ROOT / "Config" / name, root / "Config" / name)
    universe = library / "Test"
    for folder in ("Assets", "PipelineCandidates", "_state", "images", "Stories"):
        (universe / folder).mkdir(parents=True, exist_ok=True)
    queue.mkdir()
    config = root / "config.toml"
    base = library.as_posix()
    queue_path = queue.as_posix()
    live_model = os.environ.get("ZET_LIVE_TEST_NARRATIVE_MODEL", "general:latest") if mode == "live" else "general:latest"
    comfy_url = os.environ.get("ZET_LIVE_TEST_COMFYUI_URL", "http://127.0.0.1:8188") if mode == "live" else "http://127.0.0.1:8188"
    checkpoint = os.environ.get("ZET_LIVE_TEST_CHECKPOINT", "test-placeholder") if mode == "live" else "test-placeholder"
    config.write_text(
        "[BaseFolders]\n"
        f'BaseLibraryPath = "{base}"\n'
        'BaseCharacterPath = "Characters"\n'
        'BaseAssetPath = "Assets"\n'
        'BasePipelinePath = "PipelineCandidates"\n'
        f'BaseAIQueuePath = "{queue_path}"\n\n'
        "[AIHarvest]\nAutoEnabled = false\n\n"
        '[Runtime]\nRole = "development"\n\n'
        f'[AIModels]\nNarrativeScene = {json.dumps(live_model)}\nCodexDefault = "gpt-6-luna"\n\n'
        f'[ComfyUI]\nServerURL = {json.dumps(comfy_url)}\nCheckpoint = {json.dumps(checkpoint)}\n'
        "[Render]\nBackend = \"manual_chatgpt\"\n",
        encoding="utf-8",
    )
    shutil.copy2(library / "Test" / "responses" / "render-1344x768.png", root / "render-1344x768.png")
    shutil.copy2(library / "Test" / "responses" / "render-1216x832.png", root / "render-1216x832.png")
    return config


def build_app(config: Path, index_root: Path):
    os.environ["ZET_CONFIG_PATH"] = str(config.resolve())
    os.environ["ZET_TEST_QUEUE_STATE_ROOT"] = str(config.parent / "QueueState")
    os.chdir(config.parent)
    sys.path.insert(0, str(PROJECT_ROOT))

    # Keep Zet's rebuildable SQLite index outside both Git and the authored seed.
    from zet.repositories.library_index_repository import LibraryIndexRepository
    from zet.services.ollama_model_service import OllamaModelService
    from zet.services import local_prompt_improvement_service

    def seed_catalog():
        from zet.services.atomic_file_service import write_json_atomic
        models = [{"id": value, "name": value, "provider": "ollama", "capabilities": ["text", "vision", "structured_json"]}
                  for value in ("general:latest", "image-analysis:latest", "image-analysis-alt:latest")]
        models.append({"id": "codex:gpt-6-luna", "name": "gpt-6-luna", "provider": "codex", "capabilities": ["text", "vision", "structured_json"]})
        models.append({"id": "text-only:latest", "name": "text-only:latest", "provider": "ollama", "capabilities": ["text"]})
        models.append({"id": "qwen_image_2.1_int8_convrot.safetensors", "name": "qwen_image_2.1_int8_convrot.safetensors",
                       "provider": "comfyui", "capabilities": ["image_generation"]})
        write_json_atomic(config.parent / "Queue/File_Proxy/Control/model_catalog.json", {
            "version": 1, "models": models, "refreshed_at": "2026-10-16T00:00:00Z", "errors": {},
            "comfyui_node_types": ["UNETLoader", "CLIPLoader", "VAELoader", "LoadImage", "TextEncodeQwenImage21",
                                    "EmptyLatentImage", "KSampler", "VAEDecode", "SaveImage", "QwenImage21Cache"]})

    seed_catalog()
    catalog_fixture = json.loads((config.parent / "Queue/File_Proxy/Control/model_catalog.json").read_text(encoding="utf-8"))

    LibraryIndexRepository.default_index_root = staticmethod(lambda: index_root)
    OllamaModelService.refresh_model_catalog = lambda self: {"models": [], "vision_models": []}

    def prepared_observations(self, run_id, view, costume, job_id, hashes, missing):
        self._save_ai(self._run(run_id, costume), view, job_id, {
            "status": "COMPLETE", "text": "Prepared one-candidate review against the saved reference.",
            "input_hashes": hashes, "missing_candidates": missing,
        })
        with local_prompt_improvement_service._ACTIVE_LOCK:
            local_prompt_improvement_service._ACTIVE_JOBS.discard(job_id)

    local_prompt_improvement_service.LocalPromptImprovementService._analyze = prepared_observations

    from zet.app import ZetApp
    from zet.web.app import create_app

    zet_app = ZetApp.from_config(config, validate_catalog=False, universe_id="Test")
    from zet.services.local_asset_store_service import LocalAssetStoreService
    store = LocalAssetStoreService(config.parent / "Library" / "Test")
    prerequisite_image = config.parent / "Library" / "Test" / "images" / "traveler-reference.png"
    for pipeline, batch_id in (("Body-Reference", "a" * 32), ("Head-Image", "b" * 32)):
        batch = config.parent / "Library" / "Test" / "PipelineCandidates" / "Character-Pipeline" / "Traveler" / "Adult"
        batch = batch / ("Head-Image" if pipeline == "Head-Image" else "") / batch_id
        batch.mkdir(parents=True, exist_ok=True)
        (batch / "spec.json").write_text(json.dumps({"kind": pipeline, "run_id": batch_id}), encoding="utf-8")
        store.lock_batch_selection("Traveler", "Adult", pipeline, "FRONT", candidate_id=f"seed-{pipeline.lower()}",
                                   image_path=prerequisite_image, batch_id=batch_id)
    author = zet_app.narrative_scene_service
    asset = zet_app.entity_library_service.import_asset(
        "Traveler reference", "image/png", (config.parent / "Library" / "Test" / "images" / "traveler-reference.png").read_bytes(),
        origin="import", origin_key="test-traveler-reference",
    )
    ids = seed_narrative(author, asset["asset_id"])
    application = create_app(config, validate_catalog_on_create=False)
    application.state.ai_catalog_fixture = catalog_fixture
    application.state.test_ids = {
        **ids,
        "asset": asset["asset_id"], "library": str(config.parent / "Library"),
        "queue": str(config.parent / "Queue"),
        "local_asset_state": str(config.parent / "Library" / "_state" / "LocalAssets"),
    }
    return application


def seed_narrative(author, asset_id: str) -> dict[str, str]:
    seed = json.loads((SEED / "Test" / "seed.json").read_text(encoding="utf-8"))
    story = author.create_story(seed["story"])
    scene = author.create_scene(story["id"], seed["scene"])
    element = author.save_element(story["id"], scene["id"], {
        "name": "Traveler", "kind": "subject", "asset_id": asset_id,
        "appearance": "Adult traveler in a blue coat and brown boots", "reference_role": "appearance",
    })
    backdrop = author.create_target(story["id"], scene["id"], {
        "title": "Forest backdrop", "kind": "backdrop", "narrative": "A quiet forest path.",
    })
    subscene = author.create_target(story["id"], scene["id"], {
        "title": "Traveler at the gate", "kind": "subscene", "narrative": "The traveler arrives.",
        "element_ids": [element["id"]],
    })
    assembly = author.create_target(story["id"], scene["id"], {
        "title": "Final assembly", "kind": "assembly", "narrative": "The traveler arrives at the gate.",
        "assembly_mode": "finish_composite",
    })
    return {"story": story["id"], "scene": scene["id"], "backdrop": backdrop["id"],
            "subscene": subscene["id"], "assembly": assembly["id"], "element": element["id"]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("fast", "live"), default="fast")
    parser.add_argument("--open-library", action="store_true")
    args = parser.parse_args()
    mode = "inspection" if args.open_library else args.mode
    config = prepare(mode)
    index_root = Path(tempfile.mkdtemp(prefix="zet-e2e-index-"))
    atexit.register(shutil.rmtree, index_root, ignore_errors=True)
    app = build_app(config, index_root)
    scenario_number = 0
    live_blockers = []
    proxy_process = None
    if mode == "live":
        if os.environ.get("ZET_LIVE_TEST_ENABLED") != "1":
            live_blockers = ["Live execution was not explicitly enabled with ZET_LIVE_TEST_ENABLED=1."]
        else:
            live_blockers = live_preflight(config.parent)
            if not live_blockers:
                try:
                    proxy_process = start_private_proxy(config.parent, config,
                        os.environ.get("ZET_LIVE_TEST_COMFYUI_URL", "http://127.0.0.1:8188"))
                    def stop_private_proxy():
                        if proxy_process and proxy_process.poll() is None:
                            proxy_process.terminate()
                            try:
                                proxy_process.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                proxy_process.kill()
                    atexit.register(stop_private_proxy)
                    if proxy_process.poll() is not None:
                        live_blockers.append("The private AI Proxy process stopped during startup; see test-results/narrative-e2e/live/ai-proxy.log.")
                except (OSError, subprocess.SubprocessError) as exc:
                    live_blockers.append(f"Could not start the private AI Proxy: {exc}")
    app.state.live_blockers = live_blockers

    @app.get("/__test/context")
    def test_context():
        return {
            "ids": app.state.test_ids,
            "library": str(config.parent / "Library"),
            "runtime_library": str(app.state.zet_app.config.base_library_path),
            "runtime_universe": str(app.state.zet_app.universe_id),
            "queue": str(config.parent / "Queue"),
        }

    @app.get("/__test/live-preflight")
    def live_test_preflight():
        return {"ready": not app.state.live_blockers, "blockers": app.state.live_blockers}

    @app.post("/__test/ai-submit")
    def submit_ai_fixture(data: dict):
        from fastapi import HTTPException
        universe = data.get("universe", "Test")
        if universe == "TestOther":
            other = config.parent / "Library/TestOther"
            if not other.exists():
                shutil.copytree(SEED / "Test", other)
                marker = json.loads((other / "universe.json").read_text(encoding="utf-8"))
                marker.update(universe_id="TestOther", name="Other test universe")
                (other / "universe.json").write_text(json.dumps(marker), encoding="utf-8")
        runtime = app.state.ai_job_coordinator.resolve_app(universe)
        try:
            job_id = runtime.ai_proxy_service.ai_proxy_path_service.jobs.submit_text(
                data.get("model", "general:latest"), "Return JSON", "Prepared unified queue check",
                {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"]},
                images=[runtime.entity_library_asset(app.state.test_ids["asset"])["image_path"]] if data.get("vision") and universe == "Test" else [],
                task_type="unified_queue_check")
            return {"ask_id": job_id}
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @app.post("/__test/reset")
    def reset_test_scenario():
        nonlocal scenario_number
        runtime = app.state.zet_app
        app.state.ai_job_coordinator.stop()
        previous = app.state.test_ids
        author = runtime.narrative_scene_service
        protected = author.protected_images(previous["story"])
        author.delete(previous["story"], confirmed=[item["id"] for item in protected])
        test_root = (Path(previous["library"]) / "Test").resolve()
        if not test_root.is_relative_to(RUN_ROOT.resolve()):
            raise RuntimeError(f"Refusing to reset unexpected test library: {test_root}")
        for relative in ("_state/LocalAssets/Traveler/Adult",
                         "PipelineCandidates/Character-Pipeline/Traveler/Adult"):
            target = (test_root / relative).resolve()
            if not target.is_relative_to(test_root):
                raise RuntimeError(f"Refusing to remove unexpected test data: {target}")
            shutil.rmtree(target, ignore_errors=True)
        shutil.rmtree(Path(previous["queue"]) / "File_Proxy", ignore_errors=True)
        from zet.services.atomic_file_service import write_json_atomic
        catalog = app.state.ai_catalog_fixture
        write_json_atomic(Path(previous["queue"]) / "File_Proxy/Control/model_catalog.json", catalog)
        scenario_number += 1
        ids = seed_narrative(runtime.narrative_scene_service, previous["asset"])
        app.state.test_ids = {**previous, **ids}
        from zet.services.local_asset_store_service import LocalAssetStoreService
        store = LocalAssetStoreService(test_root)
        for pipeline, batch_id in (("Body-Reference", "a" * 32), ("Head-Image", "b" * 32)):
            batch = test_root / "PipelineCandidates" / "Character-Pipeline" / "Traveler" / "Adult"
            batch = batch / ("Head-Image" if pipeline == "Head-Image" else "") / batch_id
            batch.mkdir(parents=True, exist_ok=True)
            (batch / "spec.json").write_text(json.dumps({"kind": pipeline, "run_id": batch_id}), encoding="utf-8")
            store.lock_batch_selection("Traveler", "Adult", pipeline, "FRONT", candidate_id=f"seed-{pipeline.lower()}",
                                       image_path=test_root / "images" / "traveler-reference.png", batch_id=batch_id)
        app.state.ai_job_coordinator.start()
        return {"reset": True, "scenario": scenario_number}

    @app.post("/__test/retain-failure")
    def retain_failed_scenario(data: dict):
        source = (config.parent / "Library" / "Test").resolve()
        failure_root = (RUN_ROOT / "failures" / f"scenario-{scenario_number}-{scenario_slug(str(data.get('title') or 'failed'))}").resolve()
        if not source.is_relative_to(RUN_ROOT.resolve()) or not failure_root.is_relative_to(RUN_ROOT.resolve()):
            raise RuntimeError("Refusing to retain test files outside the local test-results directory.")
        shutil.rmtree(failure_root, ignore_errors=True)
        failure_root.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source, failure_root / "Library")
        shutil.copytree(config.parent / "Queue", failure_root / "Queue", dirs_exist_ok=True)
        shutil.copy2(config, failure_root / "config.toml")
        return {"retained": str(failure_root)}

    port = 8766 if mode in {"live", "inspection"} else 8765
    if args.open_library:
        threading.Timer(1.0, webbrowser.open, args=(f"http://127.0.0.1:{port}/narrative",)).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
