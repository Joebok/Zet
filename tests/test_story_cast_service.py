import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from zet.services.story_cast_service import StoryCastService
from zet.services.story_service import ImageReferenceRow


class FakeStoryService:
    def __init__(self, root: Path, rows: list[ImageReferenceRow]):
        self.rows = rows
        self.path_service = SimpleNamespace(story_file_path=lambda slug: root / f"{slug}.md")

    @staticmethod
    def safe_slug(value):
        return value

    @staticmethod
    def get_story_settings_path_from_story_md(path):
        return Path(path).with_suffix(".story.json")

    @staticmethod
    def load_story_settings(path):
        return json.loads(Path(path).read_text(encoding="utf-8"))

    def image_reference_rows(self, **filters):
        rows = list(self.rows)
        if filters.get("character_filter"):
            rows = [row for row in rows if row.character == filters["character_filter"]]
        if filters.get("phase_filter"):
            rows = [row for row in rows if row.phase == filters["phase_filter"]]
        if filters.get("costume_filter"):
            rows = [row for row in rows if row.costume == filters["costume_filter"]]
        return rows


class StoryCastServiceTests(unittest.TestCase):
    def test_resolves_story_default_to_unique_locked_turnaround(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "demo.story.json").write_text(
                '{"cast_defaults":[{"character":"Tsaeytte","phase":"Adult",'
                '"costume":"Canonical Adventure Gear","reference_kind":"Costume-Dressing","view":"Front"}]}',
                encoding="utf-8",
            )
            expected_tag = "{{ASSET:Tsaeytte:Adult:25:Costume | Front | Canonical Adventure Gear}}"
            row = ImageReferenceRow(
                tag=expected_tag,
                label="Costume-Dressing | Turnaround | Canonical Adventure Gear",
                character="Tsaeytte",
                phase="Adult",
                kind="locked-asset",
                pipeline="Costume-Dressing",
                image_path="tsaeytte.png",
                thumbnail_path="tsaeytte.png",
                costume="Canonical Adventure Gear",
                view="Front",
                available=True,
            )

            resolved = StoryCastService(FakeStoryService(root, [row])).resolve("demo", "Tsaeytte")

            self.assertEqual(resolved["phase"], "Adult")
            self.assertEqual(resolved["costume"], "Canonical Adventure Gear")
            self.assertEqual(resolved["tag"], expected_tag)
            self.assertEqual(resolved["error"], "")

    def test_leaves_ambiguous_story_default_unresolved(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "demo.story.json").write_text(
                '{"cast_defaults":[{"character":"Tsaeytte","phase":"Adult"}]}',
                encoding="utf-8",
            )
            rows = [
                ImageReferenceRow(
                    tag=f"{{{{ASSET:Tsaeytte:Adult:{asset_id}:Costume | Turnaround | {costume}}}}}",
                    label=costume,
                    character="Tsaeytte",
                    phase="Adult",
                    kind="locked-turnaround",
                    pipeline="Costume-Dressing",
                    image_path=f"{asset_id}.png",
                    thumbnail_path=f"{asset_id}.png",
                    costume=costume,
                    available=True,
                )
                for asset_id, costume in ((25, "Adventure Gear"), (26, "Formal Wear"))
            ]

            resolved = StoryCastService(FakeStoryService(root, rows)).resolve("demo", "Tsaeytte")

            self.assertEqual(resolved["tag"], "")
            self.assertIn("No unique locked character reference", resolved["error"])


if __name__ == "__main__":
    unittest.main()
