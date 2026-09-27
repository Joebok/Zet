import re
import unittest
from pathlib import Path

from zet.repositories.asset_repository import AssetRepository
from zet.services.config_service import Config
from zet.services.costume_service import CostumeService, CostumeServiceError
from zet.services.path_service import PathService


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class CostumeMarkdownContractTests(unittest.TestCase):
    def setUp(self) -> None:
        config = Config(
            base_library_path=".",
            base_character_path="Characters",
            base_asset_path="Assets",
            base_pipeline_path="Pipelines",
            base_ai_queue_path="Queue",
        )
        paths = PathService(config, PROJECT_ROOT)
        self.service = CostumeService(AssetRepository(paths), paths)
        self.template_path = paths.shared_costume_template_path()

    def test_scene_costume_anchors_are_supported(self) -> None:
        markdown = self.template_path.read_text(encoding="utf-8")
        markdown = re.sub(
            r"(<!-- ZET:BEGIN COSTUME_DESCRIPTION_FACTS -->).*?(<!-- ZET:END COSTUME_DESCRIPTION_FACTS -->)",
            r"\1\nTest costume facts.\n\2",
            markdown,
            flags=re.DOTALL,
        )

        self.service._validate_costume_markdown(markdown)

    def test_unknown_costume_section_is_still_rejected(self) -> None:
        markdown = self.template_path.read_text(encoding="utf-8") + (
            "\n<!-- ZET:BEGIN UNKNOWN_COSTUME_SECTION -->\n"
            "text\n"
            "<!-- ZET:END UNKNOWN_COSTUME_SECTION -->\n"
        )

        with self.assertRaisesRegex(CostumeServiceError, "unsupported sections: UNKNOWN_COSTUME_SECTION"):
            self.service._validate_costume_markdown(markdown)


if __name__ == "__main__":
    unittest.main()
