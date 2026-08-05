from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from zet.services.character_source_service import CharacterSourceService
from zet.services.config_service import Config
from zet.services.path_service import PathService


def _section(name: str, text: str) -> str:
    return f"<!-- ZET:BEGIN {name} -->\n{text}\n<!-- ZET:END {name} -->\n"


class FakeCostumeService:
    @staticmethod
    def costume_name_from_slug(slug: str) -> str:
        return " ".join(slug.split("_"))

    @staticmethod
    def safe_costume_slug(name: str) -> str:
        return "_".join(name.split())


class FakeReferenceService:
    def __init__(self, image_path: Path):
        self.image_path = image_path

    def resolve_image_tag(self, tag: str) -> dict:
        return {
            "tag": tag,
            "label": "Canonical turnaround",
            "role": "story_reference",
            "kind": "turnaround",
            "path": str(self.image_path),
        }


class FakeStoryService:
    def __init__(self, image_path: Path):
        self.story_reference_service = FakeReferenceService(image_path)


class CharacterSourceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        phase = self.root / "Characters" / "Hero" / "Adult"
        phase.mkdir(parents=True)
        (phase / "Character.md").write_text(
            _section("GENERAL_DESCRIPTION_FACTS", "adult elf")
            + _section("IDENTITY_PRESERVATION_CORE", "preserve identity")
            + _section("BODY_DESCRIPTION_FACTS", "petite proportions")
            + _section("BODY_DESCRIPTION_VIEW_FRONT", "front body")
            + _section("IDENTITY_PRESERVATION_BODY", "preserve body"),
            encoding="utf-8",
        )
        (phase / "Costume_Canonical_Adventure_Gear.md").write_text(
            _section("COSTUME_DESCRIPTION_FACTS", "green adventure gear")
            + _section("COSTUME_DESCRIPTION_VIEW_FRONT", "front costume")
            + _section("IDENTITY_PRESERVATION_COSTUME", "preserve costume"),
            encoding="utf-8",
        )
        missing = self.root / "Characters" / "Hero" / "Draft"
        missing.mkdir()
        self.reference = self.root / "turnaround.png"
        self.reference.write_bytes(b"image")
        config = Config(
            base_library_path=str(self.root),
            base_character_path=str(self.root / "Characters"),
            base_asset_path=str(self.root / "Assets"),
            base_pipeline_path=str(self.root / "Pipelines"),
            base_ai_queue_path=str(self.root / "Queue"),
        )
        self.service = CharacterSourceService(
            PathService(config),
            FakeCostumeService(),
            FakeStoryService(self.reference),
            Path(__file__).resolve().parents[1],
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_options_are_ordered_and_explain_unready_phases(self) -> None:
        options = self.service.options("Hero", "Adult")

        self.assertEqual(["Adult", "Draft"], [row["value"] for row in options["phases"]])
        self.assertFalse(options["phases"][1]["available"])
        self.assertIn("missing", options["phases"][1]["disabled_reason"].lower())
        self.assertEqual(
            "Canonical_Adventure_Gear",
            options["costumes"][0]["value"],
        )
        self.assertTrue(any(row["value"] == "FRONT" for row in options["views"]))

    def test_compile_preserves_exact_reference_tag(self) -> None:
        tag = "{{ASSET:Hero:Adult:25:Costume | Turnaround | Canonical Adventure Gear}}"
        snapshot = self.service.compile(
            character="Hero",
            phase="Adult",
            costume_slug="Canonical_Adventure_Gear",
            view_token="FRONT",
            selected_sections=(
                "identity anchors",
                "body proportions",
                "selected costume",
            ),
            reference_tags=(tag,),
        )

        self.assertEqual(tag, snapshot["references"][0]["tag"])
        self.assertEqual([tag], snapshot["source_snapshot"]["reference_tags"])
        self.assertEqual("zet_character_costume", snapshot["source_kind"])


if __name__ == "__main__":
    unittest.main()
