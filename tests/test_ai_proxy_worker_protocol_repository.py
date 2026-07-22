from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import tempfile
import unittest

from zet.repositories import ai_proxy_worker_protocol_repository as worker_protocol


class AIProxyWorkerProtocolRepositoryTests(unittest.TestCase):
    def test_only_one_concurrent_claim_file_creation_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            claim_path = Path(temp_dir) / "Ask_1.claim.json"

            with ThreadPoolExecutor(max_workers=8) as executor:
                results = list(
                    executor.map(
                        lambda worker_id: worker_protocol.write_claim_file(
                            claim_path,
                            "Ask_1",
                            worker_id,
                            "2026-07-22T12:00:00",
                        ),
                        [f"worker-{index}" for index in range(8)],
                    )
                )

            self.assertEqual(1, results.count(True))
            self.assertEqual(7, results.count(False))
            payload = json.loads(claim_path.read_text(encoding="utf-8"))
            self.assertEqual("Ask_1", payload["ask_folder"])
            self.assertIn(payload["worker_id"], {f"worker-{index}" for index in range(8)})


if __name__ == "__main__":
    unittest.main()
