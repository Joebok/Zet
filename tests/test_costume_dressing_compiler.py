from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
from Scripts.Run_Costume_Dressing_Jobs import compile_costume_dressing_job
from zet.repositories.entity_library_repository import EntityLibraryRepository
from zet.services.entity_library_service import EntityLibraryService
from zet.services.path_service import PathService


class CostumeDressingCompilerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.library = self.root / "library"
        config_dir = self.root / "Config"
        template_dir = config_dir / "Prompt_Templates"
        template_dir.mkdir(parents=True)
        for name in (
            "Prompt_Task_Bundles.json",
            "Prompt_View_Text.json",
            "Prompt_View_Aliases.json",
            "Prompt_Background_Text.json",
            "Prompt_Section_Metadata.json",
        ):
            shutil.copyfile(PROJECT_ROOT / "Config" / name, config_dir / name)
        for name in ("costume_dressing_v1.md", "costume_dressing_v2.md"):
            shutil.copyfile(
                PROJECT_ROOT / "Config" / "Prompt_Templates" / name,
                template_dir / name,
            )
        self.root.joinpath("config.toml").write_text(
            "\n".join(
                [
                    "[BaseFolders]",
                    f'BaseLibraryPath = "{self.library.as_posix()}"',
                    'BaseCharacterPath = "Characters"',
                    'BaseAssetPath = "Assets"',
                    'BasePipelinePath = "Pipelines"',
                    'BaseAIQueuePath = "AI_Queue"',
                ]
            ),
            encoding="utf-8",
        )
        self.character_dir = self.library / "Characters" / "Tsaeytte" / "Youth"
        self.character_dir.mkdir(parents=True)
        self.character_dir.joinpath("Character.md").write_text(
            "Character Name: `Tsaeytte`\nCharacter Phase: `Youth`\nCanonical Art Style: `Painterly animation`\n",
            encoding="utf-8",
        )
        self.reference = self.library / "assembled.png"
        self.reference.write_bytes(b"image")

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _add_auxiliary_images(self) -> tuple[str, str]:
        resource_dir = self.library / "AuxiliaryResources" / "Images" / "costume-details"
        resource_dir.mkdir(parents=True)
        embroidery = resource_dir / "embroidery.png"
        jewelry = resource_dir / "jewelry.png"
        embroidery.write_bytes(b"embroidery")
        jewelry.write_bytes(b"jewelry")
        embroidery_tag = "{{AUX:thing:costume-details:embroidery}}"
        jewelry_tag = "{{AUX:thing:costume-details:jewelry}}"
        inventory = {
            "resources": [{
                "category": "thing",
                "resource_id": "costume-details",
                "label": "Costume Details",
                "images": [
                    {
                        "image_id": "embroidery",
                        "label": "Overskirt Embroidery",
                        "tag": embroidery_tag,
                        "image_path": str(embroidery),
                    },
                    {
                        "image_id": "jewelry",
                        "label": "Jewelry",
                        "tag": jewelry_tag,
                        "image_path": str(jewelry),
                    },
                ],
            }],
        }
        (self.library / "AuxiliaryResources" / "AuxiliaryResources.json").write_text(
            json.dumps(inventory), encoding="utf-8"
        )
        return embroidery_tag, jewelry_tag

    def _compile(self, costume_sections: str, body_view: str = "FRONT", head_view: str | None = None, *, prompt_variant: str = "generation", pipeline_mode: str = "traditional", universe_root: Path | None = None) -> tuple[str, dict, dict]:
        costume_path = self.character_dir / "Costume_Test_Outfit.md"
        costume_path.write_text(
            "\n".join(
                [
                    "Costume Name: `Test Outfit`",
                    "Footwear: `boots`",
                    "Footwear Contact: `Both boots remain planted.`",
                    "",
                    costume_sections,
                ]
            ),
            encoding="utf-8",
        )
        output_dir = self.root / "output" / body_view / (head_view or body_view) / prompt_variant
        result = compile_costume_dressing_job(
            {
                "Job": f"Test_{body_view}_{head_view or body_view}",
                "Task": "costume-dressing",
                "Character": "Tsaeytte",
                "Phase": "Youth",
                "Body View": body_view,
                "Head View": head_view or body_view,
                "Costume": "Test Outfit",
                "Costume Path": str(costume_path),
                "Output Directory": str(output_dir),
                "Expected Output": "result.png",
                "Reference Files": [{"role": "character_assembly", "path": str(self.reference)}],
            },
            self.root,
            prompt_variant=prompt_variant,
            pipeline_mode=pipeline_mode,
            universe_root=universe_root,
        )
        prompt = Path(result["final_prompt"]).read_text(encoding="utf-8")
        source_map = json.loads((output_dir / "Prompt_Source_Map.json").read_text(encoding="utf-8"))
        return prompt, source_map, result

    def test_local_prompt_uses_universe_canonical_style(self) -> None:
        (self.library / "universe.json").write_text(json.dumps({
            "universe_id": "Moonsea", "name": "Moonsea", "canonical_art_style": "Painterly fantasy illustration.",
        }), encoding="utf-8")
        prompt, source_map, _ = self._compile("", pipeline_mode="local", universe_root=self.library)
        self.assertIn("Apply the universe's Canonical Art Style: Painterly fantasy illustration.", prompt)
        self.assertNotIn("Preserve the supplied rendering style.", prompt)
        self.assertTrue(any(item.get("source_path", "").endswith("universe.json")
                            for item in source_map.get("fragments", [])))

    def test_analysis_variant_preserves_costume_facts(self) -> None:
        prompt, _, _ = self._compile(
            "<!-- ZET:BEGIN COSTUME_DESCRIPTION_FACTS -->\n"
            "Blue coat and fitted boots.\n"
            "<!-- ZET:END COSTUME_DESCRIPTION_FACTS -->",
            prompt_variant="analysis",
        )
        self.assertIn("# Review Specification", prompt)
        self.assertIn("Image 1", prompt)
        self.assertIn("Blue coat and fitted boots.", prompt)
        self.assertNotIn("# Render Task", prompt)
        self.assertNotIn("<!-- ZET:", prompt)

    def test_local_library_references_use_job_universe_root(self) -> None:
        universe = self.library / "Moonsea"
        universe.mkdir()
        (universe / "universe.json").write_text(json.dumps({
            "universe_id": "Moonsea", "name": "Moonsea",
        }), encoding="utf-8")
        other = self.library / "Other"
        other.mkdir()
        (other / "universe.json").write_text(json.dumps({
            "universe_id": "Other", "name": "Other",
        }), encoding="utf-8")
        (self.root / "Config" / "universe-selection.json").write_text(
            json.dumps({"universe_id": "Other"}), encoding="utf-8",
        )
        character_template = self.character_dir / "Character.md"
        self.character_dir = universe / "Characters" / "Tsaeytte" / "Youth"
        self.character_dir.mkdir(parents=True)
        shutil.copyfile(character_template, self.character_dir / "Character.md")
        repository = EntityLibraryRepository(universe / "catalog.sqlite3")
        repository.initialize()
        image_library = EntityLibraryService(
            PathService(SimpleNamespace(base_library_path=str(universe)), self.root), repository,
        )
        image = image_library.import_asset("Jewelry", "image/png", b"jewelry")
        image_library.save_logical_reference({
            "reference_key": "jewelry.front", "asset_id": image["asset_id"],
        })

        _, _, result = self._compile(
            "<!-- ZET:BEGIN COSTUME_DESCRIPTION_FACTS -->\n"
            "* Jewelry: matching necklace and earrings. {{LIB:REF:jewelry.front}}\n"
            "<!-- ZET:END COSTUME_DESCRIPTION_FACTS -->",
            pipeline_mode="local", universe_root=universe,
        )

        references = [item for item in result["reference_files"] if item["role"] == "entity_library"]
        self.assertEqual([image["image_path"]], [item["path"] for item in references])

    def test_view_conditioned_logical_references_resolve_to_the_matching_image(self) -> None:
        repository = EntityLibraryRepository(self.library / "catalog.sqlite3")
        repository.initialize()
        image_library = EntityLibraryService(
            PathService(SimpleNamespace(base_library_path=str(self.library)), self.root), repository
        )
        png = (b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR" + b"\x00\x00\x00\x20\x00\x00\x00\x10"
               + b"\x08\x06\x00\x00\x00")
        front = image_library.import_asset("Front jewelry", "image/png", png + b"front")
        rear = image_library.import_asset("Rear jewelry", "image/png", png + b"rear")
        image_library.save_logical_reference({
            "reference_key": "tsaeytte.canonical_adventure_gear.jewelry.front_side",
            "label": "Front jewelry", "asset_id": front["asset_id"],
        })
        image_library.save_logical_reference({
            "reference_key": "tsaeytte.canonical_adventure_gear.jewelry.rear",
            "label": "Rear jewelry", "asset_id": rear["asset_id"],
        })
        sections = (
            "<!-- ZET:BEGIN EQUIPMENT_JEWELRY_PROPS_FACTS -->\n"
            "* Jewelry: matching necklace and earrings.\n"
            "* [body:frontish,profiles] Jewelry reference: {{LIB:REF:tsaeytte.canonical_adventure_gear.jewelry.front_side}}\n"
            "* [body:rearish] Jewelry reference: {{LIB:REF:tsaeytte.canonical_adventure_gear.jewelry.rear}}\n"
            "<!-- ZET:END EQUIPMENT_JEWELRY_PROPS_FACTS -->"
        )

        _, _, front_result = self._compile(sections, "FRONT")
        _, _, back_result = self._compile(sections, "BACK")

        front_refs = [item for item in front_result["reference_files"] if item["role"] == "entity_library"]
        back_refs = [item for item in back_result["reference_files"] if item["role"] == "entity_library"]
        self.assertEqual([front["image_path"]], [item["path"] for item in front_refs])
        self.assertEqual([rear["image_path"]], [item["path"] for item in back_refs])

    def test_body_and_head_views_condition_costume_guidance_independently(self) -> None:
        prompt, _, _ = self._compile(
            self._sections(
                "<!-- ZET:BEGIN COSTUME_DESCRIPTION_FACTS -->\n"
                "* Silhouette: `Long continuous rear drape.`\n"
                "<!-- ZET:END COSTUME_DESCRIPTION_FACTS -->",
                "<!-- ZET:BEGIN COSTUME_DESCRIPTION_VIEW_OVERRIDES -->\n"
                "<!-- ZET:VIEW_DOMAIN body -->\n"
                "* [body:rear_costume_visible] Keep one continuous rear overskirt drape.\n"
                "* [body:front_costume_visible] Show the open front bodice.\n"
                "<!-- ZET:END COSTUME_DESCRIPTION_VIEW_OVERRIDES -->",
                "<!-- ZET:BEGIN EQUIPMENT_JEWELRY_PROPS_FACTS -->\n"
                "* [head:all] Earrings: `Dangling gemstone earrings.`\n"
                "<!-- ZET:END EQUIPMENT_JEWELRY_PROPS_FACTS -->",
                "<!-- ZET:BEGIN EQUIPMENT_JEWELRY_PROPS_VIEW_OVERRIDES -->\n"
                "<!-- ZET:VIEW_DOMAIN body -->\n"
                "* [head:pr] Show the right earring when unobstructed.\n"
                "<!-- ZET:END EQUIPMENT_JEWELRY_PROPS_VIEW_OVERRIDES -->",
            ),
            body_view="BACK",
            head_view="RIGHT_PROFILE",
        )

        self.assertIn("continuous rear overskirt drape", prompt)
        self.assertIn("Dangling gemstone earrings", prompt)
        self.assertIn("right earring", prompt)
        self.assertNotIn("open front bodice", prompt)

    @staticmethod
    def _sections(*parts: str) -> str:
        return "\n\n".join(parts)

    def test_front_prompt_is_ordered_and_suppresses_empty_equipment(self) -> None:
        prompt, _, result = self._compile(
            self._sections(
                "<!-- ZET:BEGIN COSTUME_DESCRIPTION_FACTS -->\n"
                "* Costume name: `Test Outfit`.\n"
                "* Silhouette: `Fitted tunic and boots.`.\n"
                "* Jewelry: `Small blue pendant.`.\n"
                "* Equipment: `None.`.\n"
                "<!-- ZET:END COSTUME_DESCRIPTION_FACTS -->",
                "<!-- ZET:BEGIN COSTUME_DESCRIPTION_VIEW_OVERRIDES -->\n"
                "<!-- ZET:VIEW_DOMAIN body -->\n"
                "* [f] Front detail: `Visible center overlap.`.\n"
                "<!-- ZET:END COSTUME_DESCRIPTION_VIEW_OVERRIDES -->",
                "<!-- ZET:BEGIN EQUIPMENT_JEWELRY_PROPS_FACTS -->\n"
                "* Use anatomical left and right.\n"
                "* Right side: `None.`.\n"
                "* Left side: `None.`.\n"
                "* Jewelry: `Small blue pendant.`.\n"
                "* Primary weapon/tool: `N/A`.\n"
                "<!-- ZET:END EQUIPMENT_JEWELRY_PROPS_FACTS -->",
                "<!-- ZET:BEGIN EQUIPMENT_JEWELRY_PROPS_VIEW_OVERRIDES -->\n"
                "<!-- ZET:VIEW_DOMAIN body -->\n"
                "* [f] Front view should show `jewelry only; no equipment.`.\n"
                "<!-- ZET:END EQUIPMENT_JEWELRY_PROPS_VIEW_OVERRIDES -->",
            )
        )

        self.assertTrue(prompt.startswith("# Render Task\n"))
        opening = prompt[:500]
        for value in ("Tsaeytte", "Youth", "Test Outfit", "FRONT"):
            self.assertIn(value, opening)
        self.assertLess(prompt.index("# Image Inputs"), prompt.index("# Costume"))
        self.assertLess(prompt.index("# Change Contract"), prompt.index("# Preserve Contract"))
        self.assertLess(prompt.index("# Preserve Contract"), prompt.index("# Costume"))
        self.assertIn("Requested body view: DIRECT FRONT.", prompt)
        self.assertIn("Preserve a true direct front orientation", prompt)
        self.assertIn("Small blue pendant", prompt)
        self.assertNotIn("None.", prompt)
        self.assertNotIn("Right side", prompt)
        self.assertNotIn("Left side", prompt)
        self.assertNotIn("GOOD OUTPUT", prompt.upper())
        self.assertNotIn("BAD OUTPUT", prompt.upper())
        self.assertIn("# Constraints", prompt)
        self.assertEqual(result["status"], "READY_FOR_RENDER")
        self.assertEqual(result["next_actor"], "AI_AGENT")
        manifest = json.loads(Path(result["dependency_manifest"]).read_text(encoding="utf-8"))
        self.assertEqual("edit", manifest["render_mode"])
        self.assertEqual(["edit_base"], [item["role"] for item in manifest["image_inputs"]])
        for name in ("Final_Image_Prompt.md", "Compiled_Sections.md", "Prompt_Source_Map.json", "dependency_manifest.json", "Prompt_Review.md", "Image_Review.md"):
            self.assertTrue((Path(result["output_dir"]) / name).exists())

    def test_embedded_costume_images_use_numbered_image_level_citations(self) -> None:
        embroidery_tag, jewelry_tag = self._add_auxiliary_images()
        prompt, _, result = self._compile(
            self._sections(
                "<!-- ZET:BEGIN COSTUME_DESCRIPTION_FACTS -->\n"
                "* Silhouette: `Fitted teal outfit.`.\n"
                f"* Overskirt hem reference: {embroidery_tag}.\n"
                f"* Repeat the same hem reference at the rear: {embroidery_tag}.\n"
                f"* Use this jewelry design for the pendant and earrings: {jewelry_tag}.\n"
                "<!-- ZET:END COSTUME_DESCRIPTION_FACTS -->",
            )
        )

        self.assertIn(
            "**Image 2 — object_reference:** Costume Details — Overskirt Embroidery.",
            prompt,
        )
        self.assertIn("**Image 3 — object_reference:** Costume Details — Jewelry.", prompt)
        self.assertEqual(2, prompt.count("Image 2 (Costume Details — Overskirt Embroidery)"))
        self.assertIn("Image 3 (Costume Details — Jewelry)", prompt)
        self.assertNotIn("Image file:", prompt)
        self.assertNotIn("{{AUX:", prompt)
        self.assertNotIn(str(self.library), prompt)

        manifest = json.loads(Path(result["dependency_manifest"]).read_text(encoding="utf-8"))
        embedded = manifest["image_inputs"][1:]
        self.assertEqual([2, 3], [item["index"] for item in embedded])
        self.assertEqual(
            ["Costume Details — Overskirt Embroidery", "Costume Details — Jewelry"],
            [item["label"] for item in embedded],
        )
        self.assertEqual(3, len(manifest["image_inputs"]))

    def test_profile_and_back_three_quarter_locks_do_not_cross_contaminate(self) -> None:
        facts = (
            "<!-- ZET:BEGIN COSTUME_DESCRIPTION_FACTS -->\n"
            "* Silhouette: `Simple fitted outfit.`.\n"
            "<!-- ZET:END COSTUME_DESCRIPTION_FACTS -->"
        )
        left, _, _ = self._compile(facts, "LEFT_PROFILE")
        right, _, _ = self._compile(facts, "RIGHT_PROFILE")
        back, _, _ = self._compile(facts, "BACK_LEFT_3_4")

        self.assertIn("Requested body view: LEFT PROFILE.", left)
        self.assertNotIn("Requested body view: RIGHT PROFILE.", left)
        self.assertIn("Requested body view: RIGHT PROFILE.", right)
        self.assertNotIn("Requested body view: LEFT PROFILE.", right)
        self.assertIn("Requested body view: BACK-LEFT THREE-QUARTER.", back)
        self.assertIn("Do not rotate the head or torso toward the viewer", back)
        self.assertIn("Preserve the exact supplied away-facing back-left three-quarter angle", back)


    def test_sided_equipment_keeps_side_rules_and_source_provenance(self) -> None:
        prompt, source_map, _ = self._compile(
            self._sections(
                "<!-- ZET:BEGIN COSTUME_DESCRIPTION_FACTS -->\n"
                "* Silhouette: `Travel coat and boots.`.\n"
                "<!-- ZET:END COSTUME_DESCRIPTION_FACTS -->",
                "<!-- ZET:BEGIN EQUIPMENT_JEWELRY_PROPS_FACTS -->\n"
                "* Use anatomical left and right.\n"
                "* Right side / right hip: `Ordered lantern.`.\n"
                "* Left side / left hip: `Map satchel.`.\n"
                "* Front-view reminder: anatomical right appears on the viewer's left; anatomical left appears on the viewer's right.\n"
                "<!-- ZET:END EQUIPMENT_JEWELRY_PROPS_FACTS -->",
            )
        )

        self.assertIn("# Equipment and Jewelry", prompt)
        self.assertIn("Ordered lantern", prompt)
        self.assertIn("Map satchel", prompt)
        self.assertIn("viewer's left", prompt)
        costume_sources = [fragment for fragment in source_map["fragments"] if fragment.get("source_kind") == "costume_template_section"]
        self.assertTrue(costume_sources)



if __name__ == "__main__":
    unittest.main()
