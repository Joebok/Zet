import json
from pathlib import Path
from fastapi.testclient import TestClient

from support.project_fixture import write_project_fixture
from Scripts.Run_Body_Reference_Jobs import compile_body_reference_job
from Scripts.Run_Character_Assembly_Jobs import compile_character_assembly_job
from Scripts.Run_Head_Image_Jobs import compile_head_image_job
from zet.services.pipeline_compiler_support import universe_art_style, with_universe_art_style
from zet.services.comfyui_prompt_compiler import compile_scene_prompts
from zet.services.qwen_scene_prompt import compile_qwen_scene_prompt
from zet.services.scene_render_compiler import local_render_brief, local_render_forge_couple_prompt_text, local_render_prompt_text
from zet.services.universe_service import UniverseService
from zet.web.app import create_app
from zet.services.local_prompt_improvement_service import record_compiler_sources


STYLE = "Painterly semi-realistic fantasy illustration with anime-influenced facial stylization and refined linework."


def test_universe_service_settings_are_safe_persistent_and_selection_stays_put(tmp_path):
    container = tmp_path / "Library"
    container.mkdir()
    service = UniverseService(container, tmp_path / "Config" / "universe-selection.json")

    created = service.initialize("Eberron", STYLE)
    assert created["canonical_art_style"] == STYLE
    assert service.selection() == "Moonsea"
    service.select("Eberron")
    assert service.selection() == "Eberron"

    marker = container / "Eberron" / "universe.json"
    payload = json.loads(marker.read_text(encoding="utf-8"))
    payload["custom_metadata"] = {"keep": True}
    marker.write_text(json.dumps(payload), encoding="utf-8")
    updated = service.update_settings("Eberron", canonical_art_style="New style")
    saved = json.loads(marker.read_text(encoding="utf-8"))
    assert updated["canonical_art_style"] == "New style"
    assert saved["custom_metadata"] == {"keep": True}

    for unsafe in ("../Outside", "CON", "name.", "bad/name"):
        try:
            service.initialize(unsafe)
        except ValueError:
            pass
        else:
            raise AssertionError(f"Unsafe universe name was accepted: {unsafe}")
    try:
        service.initialize("eberron")
    except ValueError:
        pass
    else:
        raise AssertionError("Case-insensitive duplicate universe name was accepted")


def test_universe_api_creates_reads_updates_and_does_not_select_new_universe(tmp_path):
    config_path = write_project_fixture(tmp_path)
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace(
            "[BaseFolders]\n", f"[BaseFolders]\nBaseLibraryPath = \"{tmp_path.as_posix()}\"\n"
        ),
        encoding="utf-8",
    )
    with TestClient(create_app(config_path, validate_catalog_on_create=False)) as client:
        created = client.post("/api/universes", json={"name": "Eberron", "canonical_art_style": STYLE})
        assert created.status_code == 200, created.text
        assert created.json()["universe"]["canonical_art_style"] == STYLE
        assert "root" not in created.json()["universe"]
        assert client.get("/api/universes/Eberron").json()["universe"]["name"] == "Eberron"
        assert client.get("/api/universes").json()["selected_universe_id"] == "Moonsea"
        assert client.patch("/api/universes/Eberron", json={"canonical_art_style": "Updated"}).json()["universe"]["canonical_art_style"] == "Updated"
        assert client.post("/api/universes", json={"name": "eberron"}).status_code == 400


def test_universe_style_is_applied_to_a_local_ir_copy_for_scene_compilers(tmp_path):
    root = tmp_path / "Moonsea"
    root.mkdir()
    marker = root / "universe.json"
    marker.write_text(json.dumps({"universe_id": "Moonsea", "name": "Moonsea", "canonical_art_style": STYLE}))
    ir = {"style": {"art_style": "Old scene style"}, "canvas": {}, "scene": {}, "elements": [], "placements": []}

    effective = with_universe_art_style(ir, root)
    style, sources = universe_art_style(root)
    assert style == STYLE
    assert sources["CANONICAL_ART_STYLE"]["source_path"] == str(marker)
    assert ir["style"]["art_style"] == "Old scene style"
    assert effective["style"]["art_style"] == "Old scene style"
    assert effective["style"]["canonical_art_style"] == STYLE
    assert STYLE[:-1] in compile_qwen_scene_prompt(effective)
    assert STYLE[:-1] in compile_scene_prompts(effective)["global"]
    brief = local_render_brief(effective)
    assert STYLE[:-1] in local_render_prompt_text(brief)
    assert STYLE[:-1] in local_render_forge_couple_prompt_text(brief)


def test_local_character_compilers_use_universe_style_and_track_descriptor(tmp_path):
    project_root = Path(__file__).resolve().parents[1]
    universe = tmp_path / "Moonsea"
    universe.mkdir()
    marker = universe / "universe.json"
    marker.write_text(json.dumps({"universe_id": "Moonsea", "name": "Moonsea", "canonical_art_style": STYLE}))
    template = tmp_path / "Character.md"
    shared = project_root / "Shared_Library" / "Characters" / "_Shared" / "Character_Template.md"
    template.write_text(shared.read_text(encoding="utf-8").replace(
        "Canonical Art Style: `[Painterly semi-realistic, anime-influenced facial proportions, etc.]`",
        f"Canonical Art Style: `{STYLE}`",
    ).replace("Species / Ancestry: `[Species]`", "Species / Ancestry: `Human`"), encoding="utf-8")
    universe_template = universe / "Characters" / "Test" / "Adult" / "Character.md"
    universe_template.parent.mkdir(parents=True)
    universe_template.write_text(template.read_text(encoding="utf-8"), encoding="utf-8")

    body = compile_body_reference_job({
        "Job": "body", "Task": "body-reference", "Character": "Test", "Phase": "Adult",
        "Body View": "Front", "Output Directory": str(tmp_path / "body"),
    }, project_root, pipeline_mode="local", universe_root=universe)
    body_prompt = Path(body["final_prompt"]).read_text(encoding="utf-8")
    assert STYLE in body_prompt

    front_image = tmp_path / "front.png"
    front_image.write_bytes(b"front")
    head = compile_head_image_job({
        "Job": "head", "Task": "head-image", "Character": "Test", "Phase": "Adult",
        "Head View": "Back Right 3/4", "Template Path": str(template), "Output Directory": str(tmp_path / "head"),
            "Reference Files": [{"role": "head_image_source", "path": str(front_image)}],
    }, project_root, pipeline_mode="local", universe_root=universe)
    head_prompt = Path(head["final_prompt"]).read_text(encoding="utf-8")
    assert STYLE in head_prompt
    assert "Old character style" not in head_prompt

    body_image, head_image = tmp_path / "body.png", tmp_path / "head.png"
    body_image.write_bytes(b"body")
    head_image.write_bytes(b"head")
    assembly = compile_character_assembly_job({
        "Job": "assembly", "Task": "character-assembly", "Character": "Test", "Phase": "Adult",
        "Body View": "Front", "Head View": "Front", "Template Path": str(template),
        "Output Directory": str(tmp_path / "assembly"),
        "Reference Files": [
            {"role": "body_reference", "path": str(body_image), "body_view": "FRONT", "character": "Test", "phase": "Adult"},
            {"role": "head_image", "path": str(head_image), "body_view": "FRONT", "head_view": "FRONT", "character": "Test", "phase": "Adult"},
        ],
    }, project_root, pipeline_mode="local", universe_root=universe)
    assembly_prompt = Path(assembly["final_prompt"]).read_text(encoding="utf-8")
    assert STYLE in assembly_prompt
    record_compiler_sources(Path(assembly["output_dir"]))
    source_hashes = json.loads((Path(assembly["output_dir"]) / "Prompt_Source_Hashes.json").read_text())
    assert str(marker.resolve()) in source_hashes
