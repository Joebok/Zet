import unittest
import json
from pathlib import Path
import tempfile

from zet.services.ollama_model_service import OllamaModelService


class StubOllamaModelService(OllamaModelService):
    def __init__(self, responses):
        self.responses = responses
        self.requests = []

    def _request_json(self, path, payload=None):
        self.requests.append((path, payload))
        response = self.responses[(path, (payload or {}).get("model"))]
        if isinstance(response, Exception):
            raise response
        return response


class OllamaModelServiceTests(unittest.TestCase):
    def test_filters_to_vision_models_when_capabilities_are_available(self):
        service = StubOllamaModelService(
            {
                ("/api/tags", None): {"models": [{"name": "text:latest"}, {"name": "vision:latest"}]},
                ("/api/show", "text:latest"): {"capabilities": ["completion", "tools"]},
                ("/api/show", "vision:latest"): {"capabilities": ["completion", "vision"]},
            }
        )

        self.assertEqual(
            service.list_models(),
            {
                "models": ["text:latest", "vision:latest"],
                "vision_models": ["vision:latest"],
                "capability_metadata_available": True,
            },
        )


    def test_generates_structured_json_with_chat_api(self):
        service = StubOllamaModelService({
            ("/api/chat", "local-model"): {"message": {"content": json.dumps({"answer": "ok"})}},
            ("/api/tags", None): {"models": [{"name": "local-model", "digest": "sha256:abc"}]},
            ("/api/show", "local-model"): {"parameters": "num_ctx 65536\nnum_predict 2048"},
        })

        self.assertEqual(
            service.generate_json("local-model", "system", "prompt", {"type": "object"}),
            {"answer": "ok"},
        )
        payload = next(payload for path, payload in service.requests if path == "/api/chat")
        self.assertFalse(payload["think"])
        self.assertEqual(payload["options"], {"temperature": 0.2})

    def test_generates_structured_json_with_images(self):
        service = StubOllamaModelService({
            ("/api/chat", "vision-model"): {"message": {"content": json.dumps({"answer": "ok"})}},
            ("/api/tags", None): {"models": [{"name": "vision-model", "digest": "sha256:vision"}]},
            ("/api/show", "vision-model"): {"modelfile": "PARAMETER num_ctx 32768\nPARAMETER num_predict 1024"},
        })
        with tempfile.TemporaryDirectory() as temp_dir:
            image = Path(temp_dir) / "image.png"
            image.write_bytes(b"png")
            service.generate_json(
                "vision-model", "system", "prompt", {"type": "object"}, images=[image]
            )

        encoded = next(payload for path, payload in service.requests if path == "/api/chat")["messages"][1]["images"]
        self.assertEqual(encoded, ["cG5n"])

    def test_generation_records_managed_alias_digest_and_runtime_settings(self):
        service = StubOllamaModelService({
            ("/api/chat", "general:latest"): {
                "model": "general:latest", "message": {"content": json.dumps({"answer": "ok"})}
            },
            ("/api/tags", None): {"models": [{"name": "general:latest", "digest": "sha256:managed"}]},
            ("/api/show", "general:latest"): {
                "modelfile": "PARAMETER num_ctx 65536\nPARAMETER num_predict 2048\nPARAMETER num_batch 128"
            },
        })

        _, evidence = service.generate_json_with_evidence(
            "general:latest", "system", "prompt", {"type": "object"}
        )

        self.assertEqual("sha256:managed", evidence["digest"])
        self.assertEqual({"num_ctx": 65536, "num_predict": 2048}, evidence["runtime_settings"])


if __name__ == "__main__":
    unittest.main()
