import unittest

from zet.services.ollama_model_service import OllamaModelService


class StubOllamaModelService(OllamaModelService):
    def __init__(self, responses):
        self.responses = responses

    def _request_json(self, path, payload=None):
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
            {"models": ["vision:latest"], "vision_filtered": True},
        )

    def test_returns_all_models_when_capabilities_are_unavailable(self):
        service = StubOllamaModelService(
            {
                ("/api/tags", None): {"models": [{"name": "zeta"}, {"name": "Alpha"}]},
                ("/api/show", "Alpha"): RuntimeError("unsupported"),
                ("/api/show", "zeta"): RuntimeError("unsupported"),
            }
        )

        self.assertEqual(
            service.list_models(),
            {"models": ["Alpha", "zeta"], "vision_filtered": False},
        )


if __name__ == "__main__":
    unittest.main()
