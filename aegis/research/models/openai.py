from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional
import uuid

from aegis.research.models.base import (
    ModelCapabilities,
    ModelMetadata,
    ModelProvider,
    ModelResponse,
    ProviderExecutionError,
    ProviderUnavailableError,
    ToolCall,
)

logger = logging.getLogger(__name__)


class OpenAICompatibleAdapter(ModelProvider):
    """Adapter for OpenAI-compatible Chat Completions endpoints."""

    def __init__(
        self,
        model_id: str = "gpt-4o-mini-2024-07-18",
        api_key: Optional[str] = None,
        base_url: str = "https://api.openai.com/v1",
        temperature: float = 0.2,
        seed: Optional[int] = None,
        top_p: float = 0.95,
        max_tokens: int = 4096,
    ):
        self._model_id = model_id
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._base_url = base_url.rstrip("/")
        self._temperature = temperature
        self._seed = seed
        self._top_p = top_p
        self._max_tokens = max_tokens

    def check_health(self) -> Dict[str, Any]:
        """Perform a minimal live check against OpenAI endpoint."""
        if not self._api_key:
            return {
                "provider": "openai",
                "model": self._model_id,
                "healthy": False,
                "error": "OPENAI_API_KEY is not set or empty",
                "request_success": False,
            }

        url = f"{self._base_url}/models/{self._model_id}"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "User-Agent": "Aegis-Research/1.0",
        }
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "provider": "openai",
                    "model": self._model_id,
                    "healthy": True,
                    "request_success": True,
                    "model_id_confirmed": data.get("id"),
                    "tool_call_support": True,
                    "usage_metadata_support": True,
                    "timestamp": time.time(),
                }
        except urllib.error.HTTPError as e:
            # If /models is restricted, try minimal chat completion
            if e.code == 404 or e.code == 403:
                try:
                    chat_url = f"{self._base_url}/chat/completions"
                    chat_payload = {
                        "model": self._model_id,
                        "messages": [{"role": "user", "content": "ping"}],
                        "max_tokens": 1,
                    }
                    chat_req = urllib.request.Request(
                        chat_url,
                        data=json.dumps(chat_payload).encode("utf-8"),
                        headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
                    )
                    with urllib.request.urlopen(chat_req, timeout=8.0) as resp:
                        return {
                            "provider": "openai",
                            "model": self._model_id,
                            "healthy": True,
                            "request_success": True,
                            "tool_call_support": True,
                            "usage_metadata_support": True,
                            "timestamp": time.time(),
                        }
                except Exception as ex:
                    return {
                        "provider": "openai",
                        "model": self._model_id,
                        "healthy": False,
                        "error": f"OpenAI auth/ping check failed: {ex}",
                        "request_success": False,
                    }
            return {
                "provider": "openai",
                "model": self._model_id,
                "healthy": False,
                "error": f"HTTP {e.code}: {e.reason}",
                "request_success": False,
            }
        except Exception as e:
            return {
                "provider": "openai",
                "model": self._model_id,
                "healthy": False,
                "error": str(e),
                "request_success": False,
            }

    def capabilities(self) -> ModelCapabilities:
        return ModelCapabilities(
            supports_tools=True,
            supports_system_prompt=True,
            supports_seed=True,
            supports_json_mode=True,
            supports_streaming=False,
            max_context_tokens=128000,
            max_output_tokens=self._max_tokens,
        )

    def metadata(self) -> ModelMetadata:
        return ModelMetadata(
            provider="openai_compatible",
            model_id=self._model_id,
            seed=self._seed,
            temperature=self._temperature,
            top_p=self._top_p,
            max_tokens=self._max_tokens,
            capabilities=self.capabilities(),
            extra_params={"base_url": self._base_url},
        )

    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> ModelResponse:
        if not self._api_key:
            raise ProviderUnavailableError(
                "OPENAI_API_KEY is not set or empty. Cannot invoke OpenAI API."
            )

        start_time = time.time()
        url = f"{self._base_url}/chat/completions"

        payload: Dict[str, Any] = {
            "model": self._model_id,
            "messages": messages,
            "temperature": kwargs.get("temperature", self._temperature),
            "top_p": kwargs.get("top_p", self._top_p),
            "max_tokens": kwargs.get("max_tokens", self._max_tokens),
        }
        effective_seed = kwargs.get("seed", self._seed)
        if effective_seed is not None:
            payload["seed"] = effective_seed
        if tools:
            payload["tools"] = tools

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
            "User-Agent": "Aegis-Research/1.0",
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
        )

        try:
            with urllib.request.urlopen(req, timeout=90.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8")
            except Exception:
                pass
            raise ProviderExecutionError(
                f"OpenAI API HTTP {e.code} error: {e.reason} - {err_body}"
            )
        except urllib.error.URLError as e:
            raise ProviderExecutionError(f"OpenAI connection error: {e}")
        except Exception as e:
            raise ProviderExecutionError(f"OpenAI generation error: {e}")

        duration = time.time() - start_time
        choices = data.get("choices", [])
        if not choices:
            raise ProviderExecutionError(f"OpenAI returned empty choices array: {data}")

        choice = choices[0]
        message = choice.get("message", {})
        content = message.get("content")
        raw_tool_calls = message.get("tool_calls", [])

        tool_calls: List[ToolCall] = []
        for tc in raw_tool_calls:
            fn = tc.get("function", {})
            args = fn.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError:
                    args = {"raw": args}
            tool_calls.append(
                ToolCall(
                    id=tc.get("id", f"call_{uuid.uuid4().hex[:8]}"),
                    name=fn.get("name", ""),
                    arguments=args,
                )
            )

        usage = data.get("usage", {})
        prompt_tokens = usage.get("prompt_tokens", 0)
        completion_tokens = usage.get("completion_tokens", 0)
        total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)
        client_req_id = f"client_openai_{self._model_id}_{int(start_time*1000)}"
        raw_id = data.get("id")
        provider_req_id = str(raw_id) if raw_id else None
        provider_req_id_avail = provider_req_id is not None

        return ModelResponse(
            content=content,
            tool_calls=tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            duration_seconds=duration,
            finish_reason=choice.get("finish_reason", "stop"),
            client_request_id=client_req_id,
            provider_request_id=provider_req_id,
            provider_request_id_available=provider_req_id_avail,
            execution_origin="REAL_PROVIDER",
            raw_metadata={
                "system_fingerprint": data.get("system_fingerprint"),
                "model": data.get("model"),
                "created": data.get("created"),
            },
        )
