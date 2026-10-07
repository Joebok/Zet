from __future__ import annotations

import tempfile
import unittest
import json
import csv
from pathlib import Path

import numpy as np
from PIL import Image

from zet.services.scene_assembly_experiment_service import (
    SceneAssemblyExperimentService,
    _SCENES,
    _fit,
    _isolated_source_cutout,
)


class SceneAssemblyExperimentTests(unittest.TestCase):
    def test_isolated_cutout_keeps_disconnected_nonpaper_objects(self) -> None:
        image = Image.new("RGB", (80, 50), "white")
        pixels = image.load()
        for y in range(8, 30):
            for x in range(10, 34):
                pixels[x, y] = (170, 30, 25)
        for y in range(35, 40):
            for x in range(62, 69):
                pixels[x, y] = (30, 40, 150)

        cutout = _isolated_source_cutout(image)

        self.assertEqual((61, 34), cutout.size)
        self.assertEqual(255, cutout.getpixel((11, 11))[3])
        self.assertEqual(255, cutout.getpixel((56, 30))[3])
        self.assertEqual(0, cutout.getpixel((41, 5))[3])

    def test_fit_uses_uniform_scale_and_bottom_alignment(self) -> None:
        layer = Image.new("RGBA", (100, 200), (1, 2, 3, 255))

        scaled, position = _fit(layer, (0.25, 0.2, 0.5, 0.6), (400, 300))

        self.assertEqual((90, 180), scaled.size)
        self.assertEqual((155, 60), position)

    def test_corrected_prompt_contains_chapter03_essentials_and_trace(self) -> None:
        scene = {
            "requirements": _SCENES["Chapter-03-Collision"]["requirements"],
            "dialogue": _SCENES["Chapter-03-Collision"]["dialogue"],
        }
        refs = [{"label": label} for label in ("Background", "Kaeldor and the Schoolboys", "Tsaeytte and Valindia")]
        prompt = SceneAssemblyExperimentService._corrected_prompt("Chapter-03-Collision", scene, refs)
        trace = SceneAssemblyExperimentService._requirement_trace(scene, prompt)

        for required in ("seated", "supporting hands", "all five books", "left foreground", 'exactly "sorry"'):
            self.assertIn(required.casefold(), prompt.casefold())
        self.assertNotIn("{{", prompt)
        self.assertTrue(all(value != "UNRESOLVED" for value in trace.values()))

    def test_layer_integration_preserves_every_pixel_outside_mask(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            scene_dir = root / "Chapter-03-Collision" / "prepared"
            scene_dir.mkdir(parents=True)
            base = Image.new("RGBA", (32, 24), (20, 30, 40, 255))
            base.putpixel((12, 12), (220, 10, 10, 255))
            base.save(scene_dir / "layer-composite.png")
            mask = Image.new("L", base.size, 0)
            for y in range(5, 10):
                for x in range(5, 10):
                    mask.putpixel((x, y), 255)
            mask.save(scene_dir / "qwen-edit-mask.png")
            protected = Image.new("L", base.size, 0)
            protected.putpixel((12, 12), 255)
            protected.save(scene_dir / "protected-foreground-mask.png")
            service = SceneAssemblyExperimentService.__new__(SceneAssemblyExperimentService)
            service.root = root
            proposal = root / "proposal.png"
            Image.new("RGBA", base.size, (0, 220, 0, 255)).save(proposal)
            output = root / "integrated.png"

            service._compose_result("Chapter-03-Collision", "C_layers", proposal, output)

            before = np.asarray(base)
            after = np.asarray(Image.open(output).convert("RGBA"))
            allowed = np.asarray(mask) > 0
            self.assertTrue(np.array_equal(before[~allowed], after[~allowed]))
            self.assertEqual((0, 220, 0, 255), tuple(after[6, 6]))
            self.assertEqual((220, 10, 10, 255), tuple(after[12, 12]))

    def test_lettering_variant_requires_review_and_uses_exact_dialogue(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            slug, arm, seed, token = "Chapter-01-Standing-in-Wonder", "A_original", 1101, "blind123"
            scene_dir = root / slug
            render_dir = scene_dir / "renders" / arm / str(seed)
            render_dir.mkdir(parents=True)
            Image.new("RGB", (832, 1248), "#8090a0").save(render_dir / "candidate.png")
            manifest = {"scenes": {slug: {"output_size": [832, 1248], "dialogue": _SCENES[slug]["dialogue"]}}}
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            evaluation = {"items": {token: {"lettering_review": {
                "action": "add", "balloon_box": [0.55, 0.1, 0.35, 0.12], "speaker_anchor": [0.65, 0.55],
            }}}}
            (root / "evaluation.json").write_text(json.dumps(evaluation), encoding="utf-8")
            (root / "unblinding-key.json").write_text(json.dumps({f"{slug}/{seed}": {token: arm}}), encoding="utf-8")
            service = SceneAssemblyExperimentService.__new__(SceneAssemblyExperimentService)
            service.root = root

            result = service.letter_variants()

            output = render_dir / "lettered" / "candidate.png"
            self.assertEqual(1, result["lettered"])
            self.assertTrue(output.is_file())
            metadata = json.loads((output.parent / "lettering.json").read_text(encoding="utf-8"))
            self.assertEqual("Potential is nothing without discipline", metadata["text"])
            self.assertEqual("Tsaeytte", metadata["speaker"])

    def test_wide_scorecard_round_trips_blinded_native_and_lettered_scores(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            slug, token = "Chapter-01-Standing-in-Wonder", "blind123"
            native = {name: {"result": "unreviewed", "reason": ""}
                      for name in SceneAssemblyExperimentService._criteria(slug)}
            lettered = {name: {"result": "unreviewed", "reason": ""}
                        for name in SceneAssemblyExperimentService._criteria(slug) if name != "native_dialogue"}
            lettered["lettered_dialogue"] = {"result": "unreviewed", "reason": ""}
            evaluation = {"items": {token: {"scene": slug, "seed": 1101, "criteria": native,
                                             "lettered_criteria": lettered,
                                             "lettering_review": {"action": "pending"}}}}
            (root / "evaluation.json").write_text(json.dumps(evaluation), encoding="utf-8")
            service = SceneAssemblyExperimentService.__new__(SceneAssemblyExperimentService)
            service.root = root
            scorecard = service.export_review_csv()

            with scorecard.open("r", newline="", encoding="utf-8-sig") as stream:
                reader = csv.DictReader(stream)
                fields = reader.fieldnames
                rows = list(reader)
            self.assertEqual(1, len(rows))
            rows[0]["native_cast_and_identity"] = "pass"
            rows[0]["native_reason_cast_and_identity"] = "All four characters are present."
            rows[0]["lettered_lettered_dialogue"] = "fail"
            rows[0]["lettering_action"] = "reuse"
            with scorecard.open("w", newline="", encoding="utf-8-sig") as stream:
                writer = csv.DictWriter(stream, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)

            count = service.import_review_csv()
            imported = json.loads((root / "evaluation.json").read_text(encoding="utf-8"))["items"][token]

            self.assertEqual(20, count)
            self.assertEqual("pass", imported["criteria"]["cast_and_identity"]["result"])
            self.assertEqual("fail", imported["lettered_criteria"]["lettered_dialogue"]["result"])
            self.assertEqual("reuse", imported["lettering_review"]["action"])

    def test_blinded_review_catalog_hides_arm_and_saves_ratings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            slug, arm, seed, token = "Chapter-01-Standing-in-Wonder", "B_corrected", 1101, "blind123"
            render = root / slug / "renders" / arm / str(seed)
            render.mkdir(parents=True)
            Image.new("RGB", (832, 1248), "#8090a0").save(render / "candidate.png")
            native = {name: {"result": "unreviewed", "reason": ""}
                      for name in SceneAssemblyExperimentService._criteria(slug)}
            lettered = {name: {"result": "unreviewed", "reason": ""}
                        for name in SceneAssemblyExperimentService._criteria(slug) if name != "native_dialogue"}
            lettered["lettered_dialogue"] = {"result": "unreviewed", "reason": ""}
            manifest = {"seeds": list(range(1101, 1109)), "scenes": {slug: {"output_size": [832, 1248]}}}
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (root / "evaluation.json").write_text(json.dumps({"items": {token: {
                "scene": slug, "seed": seed, "criteria": native, "lettered_criteria": lettered,
            }}}), encoding="utf-8")
            (root / "unblinding-key.json").write_text(json.dumps({f"{slug}/{seed}": {token: arm}}), encoding="utf-8")
            service = SceneAssemblyExperimentService.__new__(SceneAssemblyExperimentService)
            service.root = root
            service.run_id = "test-run"

            catalog = service.review_catalog()
            self.assertNotIn(arm, json.dumps(catalog))
            self.assertEqual(token, catalog["scenes"][0]["candidates"][0]["token"])
            service.save_candidate_review(token, "native", {"lettering_review": {"action": "add"}})
            incomplete = service.review_catalog()["scenes"][0]["candidates"][0]["lettering_review"]
            self.assertEqual("add", incomplete["action"])
            service.save_candidate_review(token, "native", {"criteria": {
                "cast_and_identity": {"result": "pass", "reason": "All four figures are visible."},
            }, "lettering_review": {"action": "add", "balloon_box": [0.1, 0.1, 0.2, 0.1],
                                    "speaker_anchor": [0.3, 0.4], "reason": "Native balloon is absent."}})
            updated = json.loads((root / "evaluation.json").read_text(encoding="utf-8"))["items"][token]
            self.assertEqual("pass", updated["criteria"]["cast_and_identity"]["result"])
            self.assertEqual("All four figures are visible.", updated["criteria"]["cast_and_identity"]["reason"])
            self.assertEqual("add", updated["lettering_review"]["action"])
            self.assertEqual([0.1, 0.1, 0.2, 0.1], updated["lettering_review"]["balloon_box"])
            SceneAssemblyExperimentService._inherit_non_dialogue_ratings(updated)
            self.assertEqual("pass", updated["lettered_criteria"]["cast_and_identity"]["result"])
            self.assertEqual("native", updated["lettered_criteria"]["cast_and_identity"]["inherited_from"])
            self.assertEqual("unreviewed", updated["lettered_criteria"]["lettered_dialogue"]["result"])


if __name__ == "__main__":
    unittest.main()
