from __future__ import annotations

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from PIL import Image

from zet.repositories.asset_repository import AssetRepository
from zet.services.config_service import Config
from zet.services.costume_service import CostumeService
from zet.services.costume_wizard_service import CostumeWizardError, CostumeWizardService
from zet.services.path_service import PathService


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class _App:
    def __init__(self, root: Path):
        self.config = Config(base_library_path=str(root / "Library"), base_character_path=str(root / "Characters"),
                             base_asset_path=str(root / "Assets"), base_pipeline_path=str(root / "Pipelines"),
                             base_ai_queue_path=str(root / "Queue"))
        self.path_service = PathService(self.config, PROJECT_ROOT)
        self.costume_service = CostumeService(AssetRepository(self.path_service), self.path_service)

    def create_costume(self, character: str, phase: str, name: str, markdown: str):
        return self.costume_service.create_costume(character, phase, name, markdown)


def _png() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (4, 4), color="red").save(buffer, format="PNG")
    return buffer.getvalue()


class CostumeWizardServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.app = _App(Path(self.temp.name))
        self.service = CostumeWizardService(self.app, PROJECT_ROOT)
        self.service._submit = lambda *args: None

    def _create(self, *, images=None):
        return self.service.create_session("Neris", "Adult", "Travel Coat", "Blue lining", images or [
            {"filename": "front.png", "caption": "Front of the outfit", "contents": _png()},
        ])

    def _design(self):
        return {"costume_role": "Travel outfit", "footwear": "Brown boots", "footwear_contact": "Both boots contact the ground.",
                "facts": ["* Overall silhouette: fitted blue coat.", "* [f] The front has a silver clasp."],
                "view_overrides": [], "view_suppression": [], "equipment_facts": [], "equipment_view_overrides": [],
                "identity_rules": ["* Preserve the blue coat and silver clasp."], "scene_identity": "A fitted blue coat with a silver clasp.",
                "scene_anchors": ["* Silver front clasp."], "questions": []}

    def test_image_caption_validation_and_private_status(self):
        with self.assertRaisesRegex(CostumeWizardError, "description for each"):
            self._create(images=[{"filename": "front.png", "caption": "", "contents": _png()}])
        session = self._create()
        self.assertEqual(session["status"], "DRAFTING")
        self.assertEqual(len(session["images"]), 1)
        self.assertNotIn("image_paths", session)
        self.assertNotIn("test_image_path", session)
        self.assertNotIn(str(self.service.root), str(session))

    def test_three_images_are_stored_and_captioned(self):
        images = [{"filename": f"image-{index}.png", "caption": f"View {index}", "contents": _png()}
                  for index in range(1, 4)]
        session = self._create(images=images)
        self.assertEqual([item["caption"] for item in session["images"]], ["View 1", "View 2", "View 3"])

    def test_draft_uses_template_markers_and_revision_conflict_protection(self):
        session = self._create()
        responses = iter([{"facts": []}, self._design(), {"review": "Looks supported.", "refinements": []}])
        self.service._ask = lambda *args, **kwargs: next(responses)
        self.service._draft_job(session["session_id"], session["revision_id"])
        draft = self.service.get_session(session["session_id"])
        self.assertEqual(draft["status"], "DRAFT_READY")
        self.assertIn("<!-- ZET:BEGIN COSTUME_DESCRIPTION_FACTS -->", draft["markdown"])
        self.assertEqual(draft["validation_errors"], [])
        with self.assertRaisesRegex(CostumeWizardError, "changed"):
            self.service.update_draft(session["session_id"], session["revision_id"], draft["markdown"])

    def test_question_round_reconciles_answers_before_showing_draft(self):
        session = self._create()
        needs_input = self._design()
        needs_input["questions"] = ["Is the clasp silver or gold?"]
        responses = iter([{"facts": [{"text": "A front clasp is visible", "views": ["f"],
                                       "anatomical_side": "", "confidence": "high"}]}, needs_input])
        self.service._ask = lambda *args, **kwargs: next(responses)
        self.service._draft_job(session["session_id"], session["revision_id"])
        asked = self.service.get_session(session["session_id"])
        self.assertEqual(asked["status"], "NEEDS_INPUT")
        self.assertEqual(asked["questions"], needs_input["questions"])

        with self.assertRaisesRegex(CostumeWizardError, "Answer each current question"):
            self.service.generate_draft(session["session_id"], [])
        self.service.generate_draft(session["session_id"], [{"question": needs_input["questions"][0], "answer": "Silver"}])
        responses = iter([{"facts": []}, self._design(), {"review": "Supported by the source.", "refinements": []}])
        self.service._ask = lambda *args, **kwargs: next(responses)
        self.service._draft_job(session["session_id"], asked["revision_id"])
        drafted = self.service.get_session(session["session_id"])
        self.assertEqual(drafted["status"], "DRAFT_READY")
        self.assertEqual(drafted["answers"][0]["answer"], "Silver")

    def test_accept_creates_regular_costume_only_after_valid_revision(self):
        session = self._create()
        self.app.path_service.character_path("Neris", "Adult").mkdir(parents=True, exist_ok=True)
        markdown = self.service._assemble_template("Travel Coat", "Neris", "Adult", self._design())
        updated = self.service.update_draft(session["session_id"], session["revision_id"], markdown)
        result = self.service.accept(session["session_id"], updated["revision_id"])
        self.assertEqual(result.costume.name, "Travel Coat")
        self.assertTrue(Path(result.costume.path).is_file())
        self.assertEqual(self.service.get_session(session["session_id"])["status"], "ACCEPTED")

    def test_abandoned_session_cannot_be_accepted(self):
        session = self._create()
        markdown = self.service._assemble_template("Travel Coat", "Neris", "Adult", self._design())
        updated = self.service.update_draft(session["session_id"], session["revision_id"], markdown)
        abandoned = self.service.abandon(session["session_id"])
        with self.assertRaisesRegex(CostumeWizardError, "abandoned"):
            self.service.accept(session["session_id"], updated["revision_id"])
        self.assertEqual(abandoned["status"], "ABANDONED")


if __name__ == "__main__":
    unittest.main()
