from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional
import uuid

from aegis.research.models.base import (
    ModelCapabilities,
    ModelDigestMismatchError,
    ModelMetadata,
    ModelProvider,
    ModelResponse,
    ProviderExecutionError,
    ProviderUnavailableError,
    ToolCall,
)

logger = logging.getLogger(__name__)


class OllamaModelAdapter(ModelProvider):
    """Real model execution adapter for local Ollama instances."""

    def __init__(
        self,
        model_id: str = "qwen2.5-coder:latest",
        endpoint: str = "http://localhost:11434",
        temperature: float = 0.2,
        seed: Optional[int] = None,
        top_p: float = 0.95,
        max_tokens: int = 2048,
        expected_digest: Optional[str] = None,
    ):
        self._model_id = model_id
        self._endpoint = endpoint.rstrip("/")
        self._temperature = temperature
        self._seed = seed
        self._top_p = top_p
        self._max_tokens = max_tokens
        self._expected_digest = expected_digest
        self._version = self._detect_version()
        self._digest = self._detect_digest()

        if self._expected_digest and self._digest and self._digest != self._expected_digest:
            raise ModelDigestMismatchError(
                f"Ollama model digest mismatch for '{self._model_id}': "
                f"expected '{self._expected_digest}', found '{self._digest}'"
            )

    def _detect_version(self) -> Optional[str]:
        try:
            req = urllib.request.Request(f"{self._endpoint}/api/version")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("version")
        except Exception:
            return None

    def _detect_digest(self) -> Optional[str]:
        try:
            req = urllib.request.Request(f"{self._endpoint}/api/tags")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for m in data.get("models", []):
                    m_name = m.get("name", "")
                    m_model = m.get("model", "")
                    if m_name == self._model_id or m_model == self._model_id:
                        return m.get("digest")
                    if m_name.startswith(self._model_id) or m_model.startswith(self._model_id):
                        return m.get("digest")
            return None
        except Exception:
            return None

    @property
    def digest(self) -> Optional[str]:
        return self._digest

    @property
    def version(self) -> Optional[str]:
        return self._version

    def check_health(self) -> Dict[str, Any]:
        """Perform a live health check on the Ollama endpoint and model availability."""
        version = self._detect_version()
        if not version:
            return {
                "provider": "ollama",
                "model": self._model_id,
                "healthy": False,
                "endpoint": self._endpoint,
                "error": f"Ollama endpoint {self._endpoint} unreachable",
                "request_success": False,
            }
        digest = self._detect_digest()
        if not digest:
            return {
                "provider": "ollama",
                "model": self._model_id,
                "healthy": False,
                "version": version,
                "endpoint": self._endpoint,
                "error": f"Model '{self._model_id}' not found in local Ollama instance",
                "request_success": False,
            }
        if self._expected_digest and digest != self._expected_digest:
            return {
                "provider": "ollama",
                "model": self._model_id,
                "healthy": False,
                "version": version,
                "digest": digest,
                "expected_digest": self._expected_digest,
                "error": f"Model digest mismatch: expected {self._expected_digest}, found {digest}",
                "request_success": False,
            }
        return {
            "provider": "ollama",
            "model": self._model_id,
            "healthy": True,
            "version": version,
            "digest": digest,
            "endpoint": self._endpoint,
            "request_success": True,
            "tool_call_support": True,
            "usage_metadata_support": True,
            "timestamp": time.time(),
        }

    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            supports_tools=True,
            supports_system_prompt=True,
            supports_seed=True,
            supports_json_mode=True,
            supports_streaming=False,
            max_context_tokens=32768,
            max_output_tokens=self._max_tokens,
        )

    def metadata(self) -> ModelMetadata:
        return ModelMetadata(
            provider="ollama",
            model_id=self._model_id,
            model_version=self._version,
            seed=self._seed,
            temperature=self._temperature,
            top_p=self._top_p,
            max_tokens=self._max_tokens,
            capabilities=self.capabilities(),
            extra_params={
                "endpoint": self._endpoint,
                "model_digest": self._digest,
                "server_version": self._version,
            },
        )

    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> ModelResponse:
        # Fail closed if provider is unavailable
        if self._version is None:
            self._version = self._detect_version()
        if self._version is None:
            raise ProviderUnavailableError(
                f"Ollama server is unavailable at endpoint {self._endpoint}"
            )

        if self._digest is None:
            self._digest = self._detect_digest()
        if self._digest is None:
            raise ProviderUnavailableError(
                f"Requested model '{self._model_id}' is not loaded or missing from Ollama at {self._endpoint}"
            )

        if self._expected_digest and self._digest != self._expected_digest:
            raise ModelDigestMismatchError(
                f"Ollama model digest mismatch! Expected '{self._expected_digest}', found '{self._digest}'"
            )

        start_time = time.time()
        options: Dict[str, Any] = {
            "temperature": kwargs.get("temperature", self._temperature),
            "top_p": kwargs.get("top_p", self._top_p),
            "num_predict": kwargs.get("max_tokens", self._max_tokens),
        }
        effective_seed = kwargs.get("seed", self._seed)
        if effective_seed is not None:
            options["seed"] = effective_seed

        # Normalize messages to conform strictly to Ollama API schema
        ollama_messages = []
        for m in messages:
            role = m.get("role")
            if role == "tool":
                ollama_messages.append({
                    "role": "tool",
                    "content": str(m.get("content", "")),
                })
            elif role == "assistant" and "tool_calls" in m and m["tool_calls"]:
                clean_tcs = []
                for tc in m["tool_calls"]:
                    fn = tc.get("function", {})
                    fn_name = fn.get("name", "")
                    raw_args = fn.get("arguments", {})
                    if isinstance(raw_args, str):
                        try:
                            raw_args = json.loads(raw_args)
                        except Exception:
                            raw_args = {}
                    clean_tcs.append({
                        "function": {
                            "name": fn_name,
                            "arguments": raw_args,
                        }
                    })
                ollama_messages.append({
                    "role": "assistant",
                    "content": m.get("content") or "",
                    "tool_calls": clean_tcs,
                })
            else:
                ollama_messages.append({
                    "role": role,
                    "content": m.get("content") or "",
                })

        payload: Dict[str, Any] = {
            "model": self._model_id,
            "messages": ollama_messages,
            "stream": False,
            "options": options,
        }
        if tools:
            payload["tools"] = tools

        req = urllib.request.Request(
            f"{self._endpoint}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )

        try:
            with urllib.request.urlopen(req, timeout=120.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise ProviderExecutionError(
                f"Failed to communicate with Ollama at {self._endpoint}: {e}"
            )
        except Exception as e:
            raise ProviderExecutionError(f"Ollama execution error: {e}")

        duration = time.time() - start_time
        msg = data.get("message", {})
        raw_content = msg.get("content")
        raw_tool_calls = msg.get("tool_calls", [])

        tool_calls: List[ToolCall] = []

        # 1. Native Ollama tool_calls
        if raw_tool_calls:
            for tc in raw_tool_calls:
                fn = tc.get("function", {})
                call_id = tc.get("id") or f"call_{uuid.uuid4().hex[:8]}"
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {"raw": args}
                tool_calls.append(
                    ToolCall(id=call_id, name=fn.get("name", ""), arguments=args)
                )

        # 2. If no native tool_calls, check if the content contains a JSON tool call
        if not tool_calls and raw_content:
            extracted = self._parse_json_tool_call(raw_content)
            if extracted:
                tool_calls.append(extracted)

        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)
        client_req_id = f"client_ollama_{self._model_id}_{int(start_time*1000)}"

        return ModelResponse(
            content=raw_content,
            tool_calls=tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            duration_seconds=duration,
            finish_reason=data.get("done_reason", "stop"),
            client_request_id=client_req_id,
            provider_request_id=None,
            provider_request_id_available=False,
            execution_origin="REAL_PROVIDER",
            raw_metadata={
                "total_duration": data.get("total_duration"),
                "load_duration": data.get("load_duration"),
                "digest": self._digest,
                "server_version": self._version,
            },
        )

    def _parse_json_tool_call(self, text: str) -> Optional[ToolCall]:
        """Parse structured tool call encoded inside assistant text."""
        clean = text.strip()
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", clean, re.DOTALL)
        if match:
            clean = match.group(1).strip()
        elif "{" in clean and "}" in clean:
            start = clean.find("{")
            end = clean.rfind("}") + 1
            clean = clean[start:end]

        try:
            parsed = json.loads(clean)
            if isinstance(parsed, dict) and "name" in parsed:
                args = parsed.get("arguments", {})
                if not isinstance(args, dict):
                    args = {}
                return ToolCall(
                    id=f"call_{uuid.uuid4().hex[:8]}",
                    name=parsed["name"],
                    arguments=args,
                )
        except Exception:
            pass
        return None
