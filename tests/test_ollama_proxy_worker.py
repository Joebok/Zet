import json
import unittest
from unittest.mock import patch

from AI_Manager.ollama_proxy_worker import call_ollama_once


class OllamaProxyWorkerTests(unittest.TestCase):
    def test_call_ollama_once_sets_keep_alive_zero(self):
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"response": "ok"}'

        captured = {}

        def fake_urlopen(request, timeout):
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse()

        with patch("AI_Manager.ollama_proxy_worker.urllib.request.urlopen", fake_urlopen):
            response = call_ollama_once("http://localhost:11434/api/generate", "llama3", "hello")

        self.assertEqual(response, "ok")
        self.assertEqual(captured["payload"]["keep_alive"], 0)
