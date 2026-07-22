import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from zet.services.ai_answer_harvester import AIAnswerHarvester


class StubProxyPathService:
    def __init__(self, answer_root: Path):
        self._answer_root = answer_root

    def answer_root(self) -> Path:
        return self._answer_root


class AIAnswerHarvesterExternalConsumerTests(unittest.TestCase):
    def test_harvest_once_ignores_external_consumer(self):
        with TemporaryDirectory() as temp_dir:
            answer_root = Path(temp_dir) / "Answer"
            answer = answer_root / "Ask_Storyizer_test"
            answer.mkdir(parents=True)
            (answer / "ask_manifest.json").write_text(
                json.dumps({"version": 1, "consumer": "storyizer"}),
                encoding="utf-8",
            )
            harvester = AIAnswerHarvester(
                None,
                None,
                StubProxyPathService(answer_root),
                None,
                None,
                None,
                lambda: "now",
            )

            self.assertEqual([], harvester.harvest_once())
            self.assertFalse((answer / "harvest_manifest.json").exists())

    def test_missing_consumer_remains_owned_by_zet(self):
        with TemporaryDirectory() as temp_dir:
            answer = Path(temp_dir) / "answer"
            answer.mkdir()
            (answer / "ask_manifest.json").write_text(json.dumps({"version": 1}), encoding="utf-8")
            harvester = AIAnswerHarvester(None, None, None, None, None, None, lambda: "now")

            self.assertFalse(harvester._has_external_consumer(answer))
