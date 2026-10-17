"""LLM wiring tests: system prompts, message assembly, and template fallback."""
from __future__ import annotations

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest import mock

from script2prompt.core import chunker, h3_builder, llm, prompts, scenes
from script2prompt.core.characters import build_bible
from script2prompt.parsers import plaintext

TEXT = (
    "INT. COFFEE SHOP - DAY\n\n"
    "MARA (30s, tired barista) wipes the counter. Rain taps the windows.\n\n"
    "MARA\nFirst batch of the morning.\n\n"
    "The bell rings. LEO enters, shaking rain from his jacket.\n"
)
MODES = ("T2VA", "I2VA", "FL2VA", "L2VA", "R2V")


def pipeline(mode: str = "T2VA"):
    found = scenes.split(plaintext.parse(TEXT))
    bible = build_bible(found)
    chunks = [c for s in found for c in chunker.chunk(s, bible, mode=mode)]
    return bible, chunks


class TestPrompts(unittest.TestCase):
    def test_all_modes_have_prompts(self) -> None:
        for mode in MODES:
            text = prompts.system_prompt(mode)
            self.assertTrue(text.strip())
            self.assertIn("<d>", text)
            self.assertIn("7000", text)

    def test_mode_specific_rules(self) -> None:
        self.assertIn(
            "<Picture 1> (from [Shot 1]) is fully referenced.",
            prompts.system_prompt("I2VA"),
        )
        self.assertIn("Picture 2 (from Shot N)", prompts.system_prompt("FL2VA"))
        self.assertIn("S.SS-second mark", prompts.system_prompt("L2VA"))
        r2v = prompts.system_prompt("R2V")
        for marker in ("subject_definitions:", "retention_analysis:", "fully_preserved",
                       "weak_reference"):
            self.assertIn(marker, r2v)

    def test_unknown_mode(self) -> None:
        with self.assertRaises(ValueError):
            prompts.system_prompt("NOPE")


class TestMessages(unittest.TestCase):
    def test_system_and_user_shape(self) -> None:
        bible, chunks = pipeline()
        msgs = llm.messages(chunks[0], bible, mode="T2VA")
        self.assertEqual([m["role"] for m in msgs], ["system", "user"])
        self.assertEqual(msgs[0]["content"], prompts.system_prompt("T2VA"))
        user = msgs[1]["content"]
        self.assertIn("COFFEE SHOP", user)
        self.assertIn("Mara (S1)", user)
        self.assertIn("First batch of the morning", user)
        self.assertIn("Live-action, cinematic", user)

    def test_keyframe_user_has_exact_instruction(self) -> None:
        bible, chunks = pipeline(mode="I2VA")
        user = llm.messages(chunks[0], bible, mode="I2VA")[1]["content"]
        self.assertIn("<Picture 1> (from [Shot 1]) is fully referenced.", user)

    def test_r2v_user_lists_reference_slots(self) -> None:
        bible, chunks = pipeline(mode="R2V")
        user = llm.messages(chunks[0], bible, mode="R2V")[1]["content"]
        self.assertIn("Reference slots", user)
        self.assertIn("<Subject 1>", user)
        self.assertIn("retention_analysis", user)

    def test_rewrite_forwards_messages_to_chat_fn(self) -> None:
        bible, chunks = pipeline()
        seen: dict = {}

        def fake(msgs):
            seen["msgs"] = msgs
            return "MODEL OUTPUT"

        out = llm.rewrite(chunks[0], bible, mode="T2VA", chat_fn=fake)
        self.assertEqual(out, "MODEL OUTPUT")
        self.assertEqual(seen["msgs"][0]["role"], "system")


class TestBuilderLLM(unittest.TestCase):
    def test_llm_output_is_primary(self) -> None:
        bible, chunks = pipeline()

        def fake(chunk, bible, mode="T2VA", style=""):
            return "integrated_multimodal_description:\nModel prose."

        out = h3_builder.build(chunks[0], bible, rewrite=fake)
        self.assertEqual(out, "integrated_multimodal_description:\nModel prose.")

    def test_falls_back_on_error(self) -> None:
        bible, chunks = pipeline()

        def boom(chunk, bible, mode="T2VA", style=""):
            raise llm.LLMError("endpoint offline")

        fallback = h3_builder.build(chunks[0], bible)
        self.assertEqual(h3_builder.build(chunks[0], bible, rewrite=boom), fallback)

    def test_unexpected_error_propagates(self) -> None:
        bible, chunks = pipeline()

        def buggy(chunk, bible, mode="T2VA", style=""):
            raise RuntimeError("a programming error, not an offline endpoint")

        with self.assertRaises(RuntimeError):
            h3_builder.build(chunks[0], bible, rewrite=buggy)

    def test_falls_back_on_empty(self) -> None:
        bible, chunks = pipeline()
        def empty(chunk, bible, mode="T2VA", style=""):
            return "   \n  "
        fallback = h3_builder.build(chunks[0], bible)
        self.assertEqual(h3_builder.build(chunks[0], bible, rewrite=empty), fallback)

    def test_template_output_still_validates(self) -> None:
        from script2prompt.core import validator

        bible, chunks = pipeline()
        prompt = h3_builder.build(chunks[0], bible)
        self.assertEqual(validator.validate(prompt, duration=chunks[0]["duration"]), [])


class _FakeEndpoint(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802 (stdlib handler naming)
        length = int(self.headers.get("Content-Length", 0))
        self.server.received = json.loads(self.rfile.read(length))
        data = json.dumps({"choices": [{"message": {"content": "SERVER PROMPT"}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args) -> None:
        pass


class _StatusEndpoint(BaseHTTPRequestHandler):
    """Always answers with the status/body stored on the server object."""

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        body = self.server.status_body
        self.send_response(self.server.status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        pass


class _SequenceEndpoint(BaseHTTPRequestHandler):
    """Answers ``(status, body)`` pairs popped from ``server.sequence``."""

    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        status, body = self.server.sequence.pop(0)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args) -> None:
        pass


_OK = json.dumps({"choices": [{"message": {"content": "SERVER PROMPT"}}]}).encode()
_MSGS = [{"role": "user", "content": "hi"}]


class TestEndpoint(unittest.TestCase):
    def setUp(self) -> None:
        self.server = HTTPServer(("127.0.0.1", 0), _FakeEndpoint)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}/v1"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()

    def test_chat_posts_and_parses(self) -> None:
        out = llm.chat([{"role": "user", "content": "hi"}], base_url=self.url, model="test-model")
        self.assertEqual(out, "SERVER PROMPT")
        self.assertEqual(self.server.received["model"], "test-model")
        self.assertEqual(self.server.received["messages"][0]["content"], "hi")
        self.assertEqual(self.server.received["max_tokens"], 2048)

    def test_build_with_live_rewrite(self) -> None:
        bible, chunks = pipeline()
        env = {"OPENAI_BASE_URL": self.url, "S2P_MODEL": "test-model"}
        with mock.patch.dict("os.environ", env):
            out = h3_builder.build(chunks[0], bible, rewrite=llm.rewrite)
        self.assertEqual(out, "SERVER PROMPT")
        self.assertEqual(self.server.received["messages"][0]["role"], "system")


class TestEndpointErrors(unittest.TestCase):
    def _serve(self, handler, **attrs) -> str:
        server = HTTPServer(("127.0.0.1", 0), handler)
        for key, value in attrs.items():
            setattr(server, key, value)
        self._server = server
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.shutdown)
        self.addCleanup(server.server_close)
        return f"http://127.0.0.1:{server.server_port}/v1"

    def test_non_2xx_raises_llmerror(self) -> None:
        url = self._serve(_StatusEndpoint, status_code=404, status_body=b"not found")
        with self.assertRaises(llm.LLMError) as ctx:
            llm.chat(_MSGS, base_url=url, retries=0)
        self.assertIn("404", str(ctx.exception))

    def test_malformed_json_raises_llmerror(self) -> None:
        url = self._serve(_StatusEndpoint, status_code=200, status_body=b"not json")
        with self.assertRaises(llm.LLMError):
            llm.chat(_MSGS, base_url=url, retries=0)

    def test_missing_choices_raises_llmerror(self) -> None:
        url = self._serve(_StatusEndpoint, status_code=200, status_body=b"{}")
        with self.assertRaises(llm.LLMError):
            llm.chat(_MSGS, base_url=url, retries=0)

    def test_unreachable_endpoint_raises_llmerror(self) -> None:
        with self.assertRaises(llm.LLMError):
            llm.chat(_MSGS, base_url="http://127.0.0.1:1/v1", retries=0)

    def test_retries_5xx_then_succeeds(self) -> None:
        url = self._serve(_SequenceEndpoint, sequence=[(503, b"boom"), (200, _OK)])
        with mock.patch("script2prompt.core.llm.time.sleep"):
            out = llm.chat(_MSGS, base_url=url, retries=1)
        self.assertEqual(out, "SERVER PROMPT")

    def test_exhausted_retries_raise(self) -> None:
        url = self._serve(_StatusEndpoint, status_code=503, status_body=b"boom")
        with mock.patch("script2prompt.core.llm.time.sleep"), self.assertRaises(llm.LLMError):
            llm.chat(_MSGS, base_url=url, retries=1)

    def test_client_error_not_retried(self) -> None:
        url = self._serve(_SequenceEndpoint, sequence=[(400, b"bad"), (200, _OK)])
        with self.assertRaises(llm.LLMError):
            llm.chat(_MSGS, base_url=url, retries=3)
        # The second (successful) response is never reached for a 4xx.
        self.assertEqual(len(self._server.sequence), 1)


if __name__ == "__main__":
    unittest.main()
