"""
Tests for Google Gemini Wire Protocol and Generate Content normalization.
Directives: P0-B, P0-C, P0-D, P0-I, P0-K.
"""

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Callable, Dict, Tuple
import pytest

from aegis.research.models.base import (
    ModelResponse,
    ProviderExecutionError,
    ProviderUnavailableError,
    ToolCall,
)
from aegis.research.models.gemini import (
    GeminiModelAdapter,
    normalize_tool_arguments,
)


class WireTestServer:
    def __init__(self, handler_fn: Callable[[str, str, Dict[str, str], bytes], Tuple[int, str, bytes]]):
        self.handler_fn = handler_fn
        self.server = None
        self.thread = None
        self.port = None
        self.received_requests = []

    def __enter__(self):
        handler_fn = self.handler_fn
        received = self.received_requests

        class CustomHandler(BaseHTTPRequestHandler):
            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                headers = {k: v for k, v in self.headers.items()}
                received.append({"method": "POST", "path": self.path, "headers": headers, "body": body})
                status, ctype, resp_bytes = handler_fn("POST", self.path, headers, body)
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(resp_bytes)))
                self.end_headers()
                self.wfile.write(resp_bytes)

            def do_GET(self):
                headers = {k: v for k, v in self.headers.items()}
                received.append({"method": "GET", "path": self.path, "headers": headers, "body": b""})
                status, ctype, resp_bytes = handler_fn("GET", self.path, headers, b"")
                self.send_response(status)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(resp_bytes)))
                self.end_headers()
                self.wfile.write(resp_bytes)

            def log_message(self, format, *args):
                pass

        self.server = HTTPServer(("127.0.0.1", 0), CustomHandler)
        self.port = self.server.server_port
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join(timeout=2.0)


# ---------------------------------------------------------------------------
# P0-B: Tool argument normalization tests
# ---------------------------------------------------------------------------

def test_normalize_tool_arguments_empty():
    assert normalize_tool_arguments({}) == {}
    assert normalize_tool_arguments("{}") == {}


def test_normalize_tool_arguments_non_empty():
    args1 = {"path": "solution.py"}
    assert normalize_tool_arguments(args1) == {"path": "solution.py"}
    assert normalize_tool_arguments(json.dumps(args1)) == {"path": "solution.py"}

    args2 = {"path": "solution.py", "target": "def foo(): pass", "replacement": "def foo(): return 1"}
    assert normalize_tool_arguments(args2) == args2
    assert normalize_tool_arguments(json.dumps(args2)) == args2


def test_normalize_tool_arguments_missing_and_null():
    assert normalize_tool_arguments(None) == {}
    assert normalize_tool_arguments("") == {}
    assert normalize_tool_arguments("   ") == {}
    assert normalize_tool_arguments("null") == {}


def test_normalize_tool_arguments_invalid_json():
    with pytest.raises(ValueError, match="JSON string is invalid"):
        normalize_tool_arguments("{not_valid_json")


def test_normalize_tool_arguments_non_object():
    with pytest.raises(ValueError, match="must be a JSON object"):
        normalize_tool_arguments("[1, 2, 3]")

    with pytest.raises(ValueError, match="must be a JSON object"):
        normalize_tool_arguments('"just a string"')

    with pytest.raises(ValueError, match="must be a JSON object"):
        normalize_tool_arguments("12345")


# ---------------------------------------------------------------------------
# P0-B & P0-C & P0-D: Wire serialization and conversation protocol tests
# ---------------------------------------------------------------------------

def test_gemini_tool_schema_conversion():
    adapter = GeminiModelAdapter(api_key="dummy_key", min_request_interval=0.0)
    tools = [
        {
            "type": "function",
            "function": {
                "name": "edit_file",
                "description": "Edit lines in file",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "target": {"type": "string"},
                        "replacement": {"type": "string"},
                    },
                    "required": ["path", "target", "replacement"],
                },
            },
        }
    ]
    gemini_tools = adapter._convert_tools_to_gemini_format(tools)
    assert len(gemini_tools) == 1
    assert "function_declarations" in gemini_tools[0]
    decl = gemini_tools[0]["function_declarations"][0]
    assert decl["name"] == "edit_file"
    assert "parameters" in decl
    assert decl["parameters"]["required"] == ["path", "target", "replacement"]


def test_gemini_generate_preserves_continuation_metadata_and_wire_format(monkeypatch):
    """Verify Gemini wire request formats role='user' for tool response and preserves metadata."""
    captured_payloads = []

    def mock_gemini_api(method, path, headers, body):
        payload = json.loads(body.decode("utf-8"))
        captured_payloads.append(payload)

        # Turn 1 response: return a function call with thought_signature and id
        if len(captured_payloads) == 1:
            resp_data = {
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [
                                {
                                    "functionCall": {
                                        "name": "list_files",
                                        "args": {"directory": "."},
                                        "id": "provider_fc_12345",
                                    },
                                    "thought_signature": "sig_alpha_999",
                                    "tool_type": "standard_function",
                                }
                            ],
                        },
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 120,
                    "candidatesTokenCount": 25,
                    "totalTokenCount": 145,
                },
                "modelVersion": "gemini-2.5-flash",
            }
        else:
            # Turn 2 response: return final text answer
            resp_data = {
                "candidates": [
                    {
                        "content": {
                            "role": "model",
                            "parts": [{"text": "Found solution.py and tests."}],
                        },
                        "finishReason": "STOP",
                    }
                ],
                "usageMetadata": {
                    "promptTokenCount": 200,
                    "candidatesTokenCount": 15,
                    "totalTokenCount": 215,
                },
                "modelVersion": "gemini-2.5-flash",
            }
        return 200, "application/json", json.dumps(resp_data).encode("utf-8")

    with WireTestServer(mock_gemini_api) as server:
        adapter = GeminiModelAdapter(
            model_id="gemini-2.5-flash",
            api_key="test_key",
            min_request_interval=0.0,
        )

        import urllib.request
        orig_urlopen = urllib.request.urlopen

        def mock_urlopen(req, *args, **kwargs):
            new_url = f"http://127.0.0.1:{server.port}/generate"
            new_req = urllib.request.Request(
                new_url,
                data=req.data,
                headers=req.headers,
                method=req.get_method(),
            )
            return orig_urlopen(new_req, *args, **kwargs)

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

        messages_turn1 = [{"role": "user", "content": "List the files."}]
        resp1 = adapter.generate(messages=messages_turn1)

        # Verify Turn 1 ModelResponse
        assert resp1.execution_origin == "REAL_PROVIDER"
        assert resp1.client_request_id.startswith("client_gemini_")
        assert resp1.provider_request_id is None
        assert resp1.provider_request_id_available is False
        assert len(resp1.tool_calls) == 1
        tc = resp1.tool_calls[0]
        assert tc.name == "list_files"
        assert tc.arguments == {"directory": "."}
        assert tc.id == "provider_fc_12345"  # Provider supplied id preserved
        assert tc.provider_metadata.get("thought_signature") == "sig_alpha_999"
        assert tc.provider_metadata.get("tool_type") == "standard_function"
        assert len(resp1.provider_parts) == 1

        # Build Turn 2 messages as an agent loop would
        messages_turn2 = [
            {"role": "user", "content": "List the files."},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "name": tc.name,
                        "arguments": tc.arguments,
                        "provider_metadata": tc.provider_metadata,
                    }
                ],
                "provider_parts": resp1.provider_parts,
            },
            {
                "role": "tool",
                "tool_call_id": tc.id,
                "name": tc.name,
                "output_dict": {"files": ["solution.py", "tests"]},
            },
        ]

        resp2 = adapter.generate(messages=messages_turn2)

        assert resp2.content == "Found solution.py and tests."
        assert len(resp2.tool_calls) == 0

        # Inspect captured Turn 2 payload
        assert len(captured_payloads) == 2
        payload2 = captured_payloads[1]
        contents = payload2["contents"]
        assert len(contents) == 3

        # Turn 2 user content
        assert contents[0]["role"] == "user"
        # Turn 2 model content (must preserve provider parts exactly)
        assert contents[1]["role"] == "model"
        assert contents[1]["parts"][0]["functionCall"]["id"] == "provider_fc_12345"
        assert contents[1]["parts"][0]["thought_signature"] == "sig_alpha_999"
        # Turn 2 tool content: MUST BE role == "user", NEVER "function"
        assert contents[2]["role"] == "user"
        assert "functionResponse" in contents[2]["parts"][0]
        assert contents[2]["parts"][0]["functionResponse"]["name"] == "list_files"
        assert contents[2]["parts"][0]["functionResponse"]["response"] == {"files": ["solution.py", "tests"]}


def test_gemini_429_backoff_and_retry(monkeypatch):
    """Verify Gemini adapter handles 429 rate limit with exponential backoff and retry."""
    attempts = 0

    def mock_429_then_200(method, path, headers, body):
        nonlocal attempts
        attempts += 1
        if attempts < 2:
            return 429, "application/json", json.dumps({"error": {"code": 429, "message": "Resource Exhausted"}}).encode("utf-8")
        resp_data = {
            "candidates": [
                {
                    "content": {"role": "model", "parts": [{"text": "Success after backoff"}]},
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {"promptTokenCount": 50, "candidatesTokenCount": 10, "totalTokenCount": 60},
        }
        return 200, "application/json", json.dumps(resp_data).encode("utf-8")

    with WireTestServer(mock_429_then_200) as server:
        import urllib.request
        orig_urlopen = urllib.request.urlopen

        def mock_urlopen(req, *args, **kwargs):
            new_url = f"http://127.0.0.1:{server.port}/generate"
            new_req = urllib.request.Request(new_url, data=req.data, headers=req.headers, method=req.get_method())
            return orig_urlopen(new_req, *args, **kwargs)

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

        adapter = GeminiModelAdapter(
            api_key="test_key",
            min_request_interval=0.0,
            max_429_retries=2,
        )
        monkeypatch.setattr(time, "sleep", lambda s: None)

        resp = adapter.generate(messages=[{"role": "user", "content": "hello"}])
        assert resp.content == "Success after backoff"
        assert attempts == 2


def test_gemini_http_400_rejection_raises_providerexecutionerror(monkeypatch):
    """Verify HTTP 400 error raises ProviderExecutionError and does not retry silently."""
    def mock_400(method, path, headers, body):
        return 400, "application/json", json.dumps({"error": {"code": 400, "message": "Bad Request: Struct expected"}}).encode("utf-8")

    with WireTestServer(mock_400) as server:
        import urllib.request
        orig_urlopen = urllib.request.urlopen

        def mock_urlopen(req, *args, **kwargs):
            new_url = f"http://127.0.0.1:{server.port}/generate"
            new_req = urllib.request.Request(new_url, data=req.data, headers=req.headers, method=req.get_method())
            return orig_urlopen(new_req, *args, **kwargs)

        monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)

        adapter = GeminiModelAdapter(
            api_key="test_key",
            min_request_interval=0.0,
        )

        with pytest.raises(ProviderExecutionError, match="HTTP 400"):
            adapter.generate(messages=[{"role": "user", "content": "test"}])
