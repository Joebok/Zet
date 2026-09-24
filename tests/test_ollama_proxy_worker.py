import json
import re
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from AI_Manager.ollama_proxy_worker import (
    OllamaGenerationResult,
    call_ollama_once,
    ensure_explicit_image_tags,
    ollama_generation_options,
    ollama_think_option,
    process_claimed,
    scheduled_keep_alive,
)
from AI_Manager.proxy_worker_output import ANSI_GREEN, ANSI_RED, ANSI_WHITE, ANSI_YELLOW, job_type, log_job


class OllamaProxyWorkerTests(unittest.TestCase):




    def test_call_ollama_once_forwards_multimodal_json_options(self):
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, exc_type, exc, tb): return False
            def read(self):
                return b'{"message":{"role":"assistant","content":"{}"},"done_reason":"length","eval_count":2048}'

        captured = {}
        def fake_urlopen(request, timeout):
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            captured["url"] = request.full_url
            return FakeResponse()

        with patch("AI_Manager.ollama_proxy_worker.urllib.request.urlopen", fake_urlopen):
            result = call_ollama_once(
                "http://localhost:11434/api/generate", "vision", "compare",
                images=["first", "second"], json_output=True,
            )

        message = captured["payload"]["messages"][0]
        self.assertEqual("user", message["role"])
        self.assertEqual(["first", "second"], message["images"])
        self.assertEqual("Image 1: [img]\nImage 2: [img]\n\ncompare", message["content"])
        self.assertEqual("http://localhost:11434/api/chat", captured["url"])
        self.assertEqual("json", captured["payload"]["format"])
        self.assertEqual("{}", result.response)
        self.assertEqual("length", result.done_reason)
        self.assertEqual(2048, result.eval_count)


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

    def test_call_ollama_once_captures_thinking_from_generate_and_chat(self):
        class FakeResponse:
            def __init__(self, body): self.body = body
            def __enter__(self): return self
            def __exit__(self, exc_type, exc, tb): return False
            def read(self): return self.body

        captured = []
        def fake_urlopen(request, timeout):
            captured.append(json.loads(request.data.decode("utf-8")))
            if request.full_url.endswith("/api/chat"):
                return FakeResponse(b'{"message":{"content":"TRUE","thinking":"chat trace"}}')
            return FakeResponse(b'{"response":"TRUE","thinking":"generate trace"}')

        with patch("AI_Manager.ollama_proxy_worker.urllib.request.urlopen", fake_urlopen):
            generated = call_ollama_once(
                "http://localhost:11434/api/generate", "vision", "check", images=["candidate"], think=True,
            )
            chatted = call_ollama_once(
                "http://localhost:11434/api/generate", "vision", "compare",
                images=["anchor", "candidate"], think=True,
            )

        self.assertEqual([True, True], [payload["think"] for payload in captured])
        self.assertEqual("generate trace", generated.thinking)
        self.assertEqual("chat trace", chatted.thinking)

    def test_single_image_chat_disables_thinking_and_uses_requested_temperature(self):
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, exc_type, exc, tb): return False
            def read(self): return b'{"message":{"content":"TRUE"},"done_reason":"stop"}'

        captured = {}
        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse()

        with patch("AI_Manager.ollama_proxy_worker.urllib.request.urlopen", fake_urlopen):
            result = call_ollama_once(
                "http://localhost:11434/api/generate", "image-analysis-alt:latest", "orientation prompt",
                images=["candidate"], temperature=1.0, think=False, use_chat=True,
            )

        self.assertEqual("http://localhost:11434/api/chat", captured["url"])
        self.assertEqual([{"role": "user", "content": "orientation prompt", "images": ["candidate"]}],
                         captured["payload"]["messages"])
        self.assertIs(captured["payload"]["think"], False)
        self.assertEqual({"temperature": 1.0}, captured["payload"]["options"])
        self.assertNotIn("prompt", captured["payload"])
        self.assertEqual("TRUE", result.response)

    def test_call_ollama_once_forwards_advanced_options_and_keeps_requested_api(self):
        class FakeResponse:
            def __enter__(self): return self
            def __exit__(self, exc_type, exc, tb): return False
            def read(self): return b'{"response":"TRUE"}'

        captured = {}
        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["payload"] = json.loads(request.data.decode("utf-8"))
            return FakeResponse()

        with patch("AI_Manager.ollama_proxy_worker.urllib.request.urlopen", fake_urlopen):
            call_ollama_once(
                "http://localhost:11434/api/generate", "gemma4:12b", "Judge this image.",
                images=["anchor", "candidate"], force_generate=True,
                sampler_options={"num_ctx": 32768, "top_p": 0.8},
                request_options={"system": "Be concise.", "raw": True},
            )

        self.assertEqual("http://localhost:11434/api/generate", captured["url"])
        self.assertEqual(["anchor", "candidate"], captured["payload"]["images"])
        self.assertEqual({"temperature": 0.1, "num_ctx": 32768, "top_p": 0.8},
                         captured["payload"]["options"])
        self.assertEqual("Be concise.", captured["payload"]["system"])
        self.assertTrue(captured["payload"]["raw"])

    def test_gate_rig_can_capture_best_effort_evidence_for_direct_models(self):
        with TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir) / "Ask_gate_rig"
            folder.mkdir()
            (folder / "OLLAMA_PROMPT.md").write_text("Judge orientation.", encoding="utf-8")
            (folder / "ask_manifest.json").write_text(json.dumps({
                "version": 1, "ask_id": folder.name, "worker_type": "ollama_generate",
                "prompt_file": "OLLAMA_PROMPT.md", "expected_output": "verdict.txt",
                "ollama_allow_unmanaged_model": True, "ollama_model": "gemma4:12b",
                "ollama_options": {"num_predict": 64},
                "ollama_request_options": {"raw": True},
            }), encoding="utf-8")
            generation = OllamaGenerationResult(response="TRUE", done_reason="stop", eval_count=2)
            with patch("AI_Manager.ollama_proxy_worker.call_ollama", return_value=generation) as call, patch(
                "AI_Manager.ollama_proxy_worker.ollama_runtime_evidence",
                side_effect=RuntimeError("no managed alias evidence"),
            ):
                result = process_claimed(folder, "worker-1", "http://localhost:11434/api/generate",
                                         30, 0, 0, 0)
            self.assertEqual("SUCCESS", result)
            self.assertEqual({"num_predict": 64}, call.call_args.kwargs["sampler_options"])
            self.assertEqual({"raw": True}, call.call_args.kwargs["request_options"])
            answer = json.loads((folder / "answer_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual("no managed alias evidence", answer["ollama_runtime_evidence_error"])

    def test_explicit_image_tags_preserve_matching_prompt_and_reject_mismatch(self):
        tagged = "Reference: [img]\nCandidate: [img]\nCompare them."
        self.assertEqual(tagged, ensure_explicit_image_tags(tagged, 2))
        with self.assertRaisesRegex(ValueError, "1 .* tags for 2 images"):
            ensure_explicit_image_tags("Reference: [img]", 2)


    def test_generation_options_reject_invalid_values(self):
        for manifest in (
            {"ollama_temperature": True},
            {"ollama_temperature": 2.1},
        ):
            with self.subTest(manifest=manifest), self.assertRaises(ValueError):
                ollama_generation_options(manifest)
        self.assertFalse(ollama_think_option({}))
        self.assertTrue(ollama_think_option({"ollama_think": True}))
        self.assertIsNone(ollama_think_option({"ollama_think": None}))
        with self.assertRaisesRegex(ValueError, "must be a boolean"):
            ollama_think_option({"ollama_think": "true"})

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
                        "ollama_think": True,
                        "ollama_num_ctx": 32768,
                        "response_schema": {"type": "object"},
                        "prompt_file": "OLLAMA_PROMPT.md",
                        "expected_output": "MODEL_RESPONSE.md",
                    }
                ),
                encoding="utf-8",
            )

            runtime = {
                "requested_alias": "qwen3.5:9b", "effective_alias": "qwen3.5:9b",
                "digest": "sha256:model", "runtime_settings": {"num_ctx": 65536, "num_predict": 2048},
            }
            generation = OllamaGenerationResult(
                response="ok", done_reason="stop", eval_count=12, thinking="visible diagnostic trace",
            )
            with patch("AI_Manager.ollama_proxy_worker.call_ollama", return_value=generation) as call, patch(
                "AI_Manager.ollama_proxy_worker.ollama_runtime_evidence", return_value=runtime
            ):
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
            self.assertTrue(call.call_args.kwargs["think"])
            self.assertNotIn("num_ctx", call.call_args.kwargs)
            self.assertEqual({"type": "object"}, call.call_args.kwargs["response_schema"])
            self.assertEqual("5m", call.call_args.kwargs["keep_alive"])
            answer = json.loads((folder / "answer_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(runtime, answer["ollama_runtime"])
            self.assertEqual({"done_reason": "stop", "eval_count": 12,
                              "think_requested": True, "thinking_file": "OLLAMA_THINKING.txt"},
                             answer["ollama_generation"])
            self.assertEqual("visible diagnostic trace",
                             (folder / "OLLAMA_THINKING.txt").read_text(encoding="utf-8"))

    def test_length_limited_thinking_retries_and_keeps_both_traces(self):
        with TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir) / "Ask_gate"
            folder.mkdir()
            (folder / "OLLAMA_PROMPT.md").write_text("Judge orientation.", encoding="utf-8")
            (folder / "ask_manifest.json").write_text(json.dumps({
                "version": 1, "ask_id": folder.name, "worker_type": "ollama_generate",
                "prompt_file": "OLLAMA_PROMPT.md", "expected_output": "verdict.txt",
                "ollama_think": None, "ollama_chat": True, "ollama_temperature": 1.0,
            }), encoding="utf-8")
            first = OllamaGenerationResult(response="", done_reason="length", eval_count=4096,
                                           thinking="first trace")
            second = OllamaGenerationResult(response="TRUE", done_reason="stop", eval_count=300,
                                            thinking="second trace")
            with patch("AI_Manager.ollama_proxy_worker.call_ollama", side_effect=[first, second]) as call, patch(
                "AI_Manager.ollama_proxy_worker.ollama_runtime_evidence", return_value={}
            ):
                result = process_claimed(folder, "worker-1", "http://localhost:11434/api/generate",
                                         30, 0, 0, 0)
            self.assertEqual("SUCCESS", result)
            self.assertEqual(2, call.call_count)
            self.assertIsNone(call.call_args_list[0].kwargs["think"])
            self.assertTrue(call.call_args_list[0].kwargs["use_chat"])
            self.assertEqual(1.0, call.call_args_list[0].kwargs["temperature"])
            self.assertEqual("Judge orientation.", call.call_args_list[0].args[2])
            self.assertIn("Limit your private analysis to 200 tokens", call.call_args_list[1].args[2])
            self.assertEqual("TRUE", (folder / "verdict.txt").read_text(encoding="utf-8"))
            self.assertEqual("first trace", (folder / "OLLAMA_THINKING_ATTEMPT_1.txt").read_text())
            self.assertEqual("second trace", (folder / "OLLAMA_THINKING.txt").read_text())
            answer = json.loads((folder / "answer_manifest.json").read_text())
            self.assertEqual("length", answer["ollama_generation"]["initial_attempt"]["done_reason"])
            self.assertEqual("OLLAMA_RETRY_PROMPT.md", answer["ollama_generation"]["retry_prompt_file"])

    def test_empty_model_answer_is_reported_as_worker_error(self):
        with TemporaryDirectory() as temp_dir:
            folder = Path(temp_dir) / "Ask_gate"
            folder.mkdir()
            (folder / "OLLAMA_PROMPT.md").write_text("Judge orientation.", encoding="utf-8")
            (folder / "ask_manifest.json").write_text(json.dumps({
                "version": 1, "ask_id": folder.name, "worker_type": "ollama_generate",
                "prompt_file": "OLLAMA_PROMPT.md", "expected_output": "verdict.txt",
                "ollama_think": True,
            }), encoding="utf-8")
            empty = OllamaGenerationResult(response="", done_reason="length", eval_count=4096,
                                           thinking="unfinished trace")
            with patch("AI_Manager.ollama_proxy_worker.call_ollama", return_value=empty), patch(
                "AI_Manager.ollama_proxy_worker.ollama_runtime_evidence", return_value={}
            ):
                result = process_claimed(folder, "worker-1", "http://localhost:11434/api/generate",
                                         30, 0, 0, 0)
            self.assertEqual("ERROR", result)
            self.assertFalse((folder / "verdict.txt").exists())
            answer = json.loads((folder / "answer_manifest.json").read_text())
            self.assertEqual("ERROR", answer["status"])
            self.assertIn("returned no answer", answer["error_message"])
            self.assertEqual("OLLAMA_THINKING.txt", answer["ollama_generation"]["thinking_file"])
