import json
import re
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from AI_Manager.ollama_proxy_worker import (
    call_ollama_once,
    ensure_explicit_image_tags,
    ollama_generation_options,
    process_claimed,
)
from AI_Manager.proxy_worker_output import ANSI_GREEN, ANSI_RED, ANSI_WHITE, ANSI_YELLOW, job_type, log_job


class OllamaProxyWorkerTests(unittest.TestCase):
    def test_local_image_jobs_use_local_render_job_type(self):
        self.assertEqual(
            "LOCAL_RENDER",
            job_type({"worker_type": "local_image_render", "pipeline_stage": "PROMPT_REVIEW"}),
        )

    def test_job_output_uses_brief_multiline_format_and_colors(self):
        manifest = {
            "ask_id": "Ask_Story_Test",
            "pipeline_stage": "PROMPT_ANALYSIS",
            "worker_type": "ollama_generate",
        }

        output = StringIO()
        with redirect_stdout(output):
            log_job(manifest, "START")
            log_job(manifest, "DONE", result="SUCCESS")

        lines = output.getvalue().splitlines()
        self.assertRegex(lines[0], rf"^{re.escape(ANSI_YELLOW)}\d{{2}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}} PROMPT_ANALYSIS START")
        self.assertEqual(f"{ANSI_WHITE}    Ask_Story_Test\033[0m", lines[1])
        self.assertRegex(lines[2], rf"^{re.escape(ANSI_GREEN)}\d{{2}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}} PROMPT_ANALYSIS DONE SUCCESS")

        errors = StringIO()
        with redirect_stderr(errors):
            log_job(manifest, "DONE", result="ERROR", error_message="render failed")

        error_lines = errors.getvalue().splitlines()
        self.assertRegex(error_lines[0], rf"^{re.escape(ANSI_RED)}\d{{2}}-\d{{2}}-\d{{2}} \d{{2}}:\d{{2}} PROMPT_ANALYSIS DONE ERROR")
        self.assertEqual(f"{ANSI_WHITE}    Ask_Story_Test\033[0m", error_lines[1])
        self.assertEqual(f"{ANSI_RED}render failed\033[0m", error_lines[2])

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
        self.assertIs(captured["payload"]["think"], False)

    def test_call_ollama_once_forwards_multimodal_json_options(self):
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, exc_type, exc, tb): return False
            def read(self): return b'{"message":{"role":"assistant","content":"{}"}}'

        captured = {}
        def fake_urlopen(request, timeout):
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            captured["url"] = request.full_url
            return FakeResponse()

        with patch("AI_Manager.ollama_proxy_worker.urllib.request.urlopen", fake_urlopen):
            call_ollama_once(
                "http://localhost:11434/api/generate", "vision", "compare",
                images=["first", "second"], json_output=True,
            )

        message = captured["payload"]["messages"][0]
        self.assertEqual("user", message["role"])
        self.assertEqual(["first", "second"], message["images"])
        self.assertEqual("Image 1: [img]\nImage 2: [img]\n\ncompare", message["content"])
        self.assertEqual("http://localhost:11434/api/chat", captured["url"])
        self.assertEqual("json", captured["payload"]["format"])

    def test_call_ollama_once_forwards_response_schema_to_generate_and_chat(self):
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, exc_type, exc, tb): return False
            def read(self): return b'{"response":"{}","message":{"content":"{}"}}'

        schema = {"type": "object", "properties": {"operations": {"type": "array"}}}
        captured = []
        def fake_urlopen(request, timeout):
            captured.append(json.loads(request.data.decode("utf-8")))
            return FakeResponse()

        with patch("AI_Manager.ollama_proxy_worker.urllib.request.urlopen", fake_urlopen):
            call_ollama_once("http://localhost:11434/api/generate", "text", "refine", response_schema=schema)
            call_ollama_once(
                "http://localhost:11434/api/generate", "vision", "refine",
                images=["reference", "candidate"], response_schema=schema,
            )

        self.assertEqual(schema, captured[0]["format"])
        self.assertEqual(schema, captured[1]["format"])

    def test_explicit_image_tags_preserve_matching_prompt_and_reject_mismatch(self):
        tagged = "Reference: [img]\nCandidate: [img]\nCompare them."
        self.assertEqual(tagged, ensure_explicit_image_tags(tagged, 2))
        with self.assertRaisesRegex(ValueError, "1 .* tags for 2 images"):
            ensure_explicit_image_tags("Reference: [img]", 2)

    def test_generation_options_keep_legacy_defaults(self):
        self.assertEqual((0.1, None), ollama_generation_options({}))

    def test_generation_options_reject_invalid_values(self):
        for manifest in (
            {"ollama_temperature": True},
            {"ollama_temperature": 2.1},
            {"ollama_num_ctx": 0},
            {"ollama_num_ctx": 1.5},
        ):
            with self.subTest(manifest=manifest), self.assertRaises(ValueError):
                ollama_generation_options(manifest)

    def test_process_claimed_forwards_manifest_generation_options(self):
        with TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir) / "Running" / "zet" / "Ask_Storyizer_test"
            folder.mkdir(parents=True)
            (folder / "OLLAMA_PROMPT.md").write_text("hello", encoding="utf-8")
            (folder / "ask_manifest.json").write_text(
                json.dumps(
                    {
                        "version": 1,
                        "ask_id": folder.name,
                        "worker_type": "ollama_generate",
                        "ollama_model": "qwen3.5:9b",
                        "ollama_temperature": 0.7,
                        "ollama_num_ctx": 32768,
                        "response_schema": {"type": "object"},
                        "prompt_file": "OLLAMA_PROMPT.md",
                        "expected_output": "MODEL_RESPONSE.md",
                    }
                ),
                encoding="utf-8",
            )

            with patch("AI_Manager.ollama_proxy_worker.call_ollama", return_value="ok") as call:
                result = process_claimed(
                    folder,
                    "worker-1",
                    "http://localhost:11434/api/generate",
                    30,
                    0,
                    0,
                    0,
                )

            self.assertEqual("SUCCESS", result)
            self.assertEqual(0.7, call.call_args.kwargs["temperature"])
            self.assertEqual(32768, call.call_args.kwargs["num_ctx"])
            self.assertEqual({"type": "object"}, call.call_args.kwargs["response_schema"])
