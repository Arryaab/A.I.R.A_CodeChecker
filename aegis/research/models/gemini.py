from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional
import uuid

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

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

# Class-level rate limiter to ensure max 5 requests per minute on free tier
_rate_limit_lock = threading.Lock()
_last_request_time: float = 0.0


def normalize_tool_arguments(arguments: Any) -> Dict[str, Any]:
    """Strictly normalizes tool call arguments to a Python dict (Struct).

    Directive P0-B Requirements:
    if arguments is a string:
        parse JSON
        require parsed value to be an object
    elif arguments is an object:
        accept it
    else:
        fail closed

    Never send a JSON-encoded string where Gemini expects a Struct/object.
    Supports empty/missing/null arguments as {}.
    """
    if arguments is None:
        return {}
    if isinstance(arguments, dict):
        return arguments
    if isinstance(arguments, str):
        trimmed = arguments.strip()
        if not trimmed or trimmed == "null":
            return {}
        try:
            parsed = json.loads(trimmed)
        except Exception as e:
            raise ValueError(f"Function call arguments JSON string is invalid: {e}")
        if parsed is None:
            return {}
        if not isinstance(parsed, dict):
            raise ValueError(f"Function call arguments must be a JSON object (dict), got {type(parsed).__name__}")
        return parsed
    raise ValueError(f"Function call arguments must be dict or JSON string, got {type(arguments).__name__}")


class GeminiModelAdapter(ModelProvider):
    """Real model execution adapter for Google Gemini models with rate limiting and quota backoff."""

    def __init__(
        self,
        model_id: str = "gemini-2.5-flash",
        api_key: Optional[str] = None,
        temperature: float = 0.2,
        seed: Optional[int] = None,
        top_p: float = 0.95,
        max_tokens: int = 4096,
        min_request_interval: float = 12.5,  # 5 req/min -> 12.5s interval
        max_429_retries: int = 3,
    ):
        self._model_id = model_id
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("AEGIS_API_KEY", "")
        self._temperature = temperature
        self._seed = seed
        self._top_p = top_p
        self._max_tokens = max_tokens
        self._min_request_interval = min_request_interval
        self._max_429_retries = max_429_retries

    def check_health(self) -> Dict[str, Any]:
        """Perform a minimal live check against Gemini endpoint."""
        if not self._api_key:
            return {
                "provider": "gemini",
                "model": self._model_id,
                "healthy": False,
                "error": "GEMINI_API_KEY is not set or empty",
                "request_success": False,
            }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model_id}?key={self._api_key}"
        req = urllib.request.Request(url, headers={"User-Agent": "Aegis-Research/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=8.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "provider": "gemini",
                    "model": self._model_id,
                    "healthy": True,
                    "request_success": True,
                    "display_name": data.get("displayName"),
                    "version": data.get("version"),
                    "tool_call_support": True,
                    "usage_metadata_support": True,
                    "timestamp": time.time(),
                }
        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8")
            except Exception:
                pass
            return {
                "provider": "gemini",
                "model": self._model_id,
                "healthy": False,
                "error": f"HTTP {e.code}: {e.reason} - {err_body}",
                "request_success": False,
            }
        except Exception as e:
            return {
                "provider": "gemini",
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
            max_context_tokens=1000000,
            max_output_tokens=self._max_tokens,
        )

    def metadata(self) -> ModelMetadata:
        return ModelMetadata(
            provider="google",
            model_id=self._model_id,
            seed=self._seed,
            temperature=self._temperature,
            top_p=self._top_p,
            max_tokens=self._max_tokens,
            capabilities=self.capabilities(),
        )

    def _convert_tools_to_gemini_format(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Convert standard OpenAI-style tool specifications to Gemini function declarations."""
        declarations = []
        for t in tools:
            if t.get("type") == "function" and "function" in t:
                fn = t["function"]
                declarations.append({
                    "name": fn.get("name"),
                    "description": fn.get("description", ""),
                    "parameters": fn.get("parameters", {}),
                })
            elif "name" in t:
                declarations.append({
                    "name": t.get("name"),
                    "description": t.get("description", ""),
                    "parameters": t.get("parameters", {}),
                })
        return [{"function_declarations": declarations}] if declarations else []

    def _wait_for_rate_limit(self) -> None:
        """Enforces client-side rate limit spacing (e.g. 5 requests/minute)."""
        global _last_request_time
        with _rate_limit_lock:
            now = time.time()
            elapsed = now - _last_request_time
            if elapsed < self._min_request_interval:
                sleep_secs = self._min_request_interval - elapsed
                logger.info(f"Gemini API rate limiter: waiting {sleep_secs:.2f}s to respect free-tier quota (5 req/min)")
                time.sleep(sleep_secs)
            _last_request_time = time.time()

    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> ModelResponse:
        if not self._api_key:
            raise ProviderUnavailableError(
                "GEMINI_API_KEY is required but not set. Cannot invoke Gemini API."
            )

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model_id}:generateContent?key={self._api_key}"

        contents = []
        system_instruction = None

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                system_instruction = {"parts": [{"text": content}]}
            elif role == "assistant":
                # Directive P0-C: Preserve provider parts verbatim if present
                if msg.get("provider_parts"):
                    contents.append({"role": "model", "parts": msg["provider_parts"]})
                else:
                    parts = []
                    if content:
                        parts.append({"text": content})
                    for tc in msg.get("tool_calls", []):
                        fn = tc.get("function", {})
                        fc_name = fn.get("name") or tc.get("name")
                        raw_args = fn.get("arguments", tc.get("arguments", {}))
                        norm_args = normalize_tool_arguments(raw_args)
                        fc_dict: Dict[str, Any] = {
                            "name": fc_name,
                            "args": norm_args,
                        }
                        p_meta = tc.get("provider_metadata", {})
                        if "id" in p_meta:
                            fc_dict["id"] = p_meta["id"]
                        elif tc.get("id") and not tc.get("id").startswith("call_"):
                            fc_dict["id"] = tc.get("id")
                        part_entry: Dict[str, Any] = {"functionCall": fc_dict}
                        if "thought_signature" in p_meta:
                            part_entry["thought_signature"] = p_meta["thought_signature"]
                        if "tool_type" in p_meta:
                            part_entry["tool_type"] = p_meta["tool_type"]
                        parts.append(part_entry)
                    contents.append({"role": "model", "parts": parts if parts else [{"text": ""}]})
            elif role == "tool":
                # Directive P0-D: role MUST be "user" containing functionResponse Struct
                tool_output = msg.get("output_dict")
                if tool_output is None:
                    raw_c = msg.get("content", "")
                    try:
                        tool_output = json.loads(raw_c) if isinstance(raw_c, str) else raw_c
                    except Exception:
                        tool_output = {"result": raw_c}
                    if not isinstance(tool_output, dict):
                        tool_output = {"result": tool_output}

                tool_part = {
                    "functionResponse": {
                        "name": msg.get("name", "tool_result"),
                        "response": tool_output,
                    }
                }
                if contents and contents[-1].get("role") == "user":
                    contents[-1]["parts"].append(tool_part)
                else:
                    contents.append({"role": "user", "parts": [tool_part]})
            else:
                contents.append({"role": "user", "parts": [{"text": content}]})

        gen_config: Dict[str, Any] = {
            "temperature": kwargs.get("temperature", self._temperature),
            "topP": kwargs.get("top_p", self._top_p),
            "maxOutputTokens": kwargs.get("max_tokens", self._max_tokens),
        }
        effective_seed = kwargs.get("seed", self._seed)
        if effective_seed is not None:
            gen_config["seed"] = effective_seed

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": gen_config,
        }
        if system_instruction:
            payload["system_instruction"] = system_instruction
        if tools:
            gemini_tools = self._convert_tools_to_gemini_format(tools)
            if gemini_tools:
                payload["tools"] = gemini_tools

        req_bytes = json.dumps(payload).encode("utf-8")

        # Execute with client-side rate limiting and 429 exponential backoff
        retries = 0
        backoff_delay = 15.0

        while True:
            self._wait_for_rate_limit()
            start_time = time.time()
            req = urllib.request.Request(
                url,
                data=req_bytes,
                headers={"Content-Type": "application/json", "User-Agent": "Aegis-Research/1.0"},
            )

            try:
                with urllib.request.urlopen(req, timeout=90.0) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    duration = time.time() - start_time
                    break
            except urllib.error.HTTPError as e:
                err_body = ""
                try:
                    err_body = e.read().decode("utf-8")
                except Exception:
                    pass

                # If rate-limited (429), back off and retry
                if e.code == 429 and retries < self._max_429_retries:
                    retries += 1
                    logger.warning(
                        f"Gemini API 429 Too Many Requests (attempt {retries}/{self._max_429_retries}). "
                        f"Backing off for {backoff_delay:.1f}s..."
                    )
                    time.sleep(backoff_delay)
                    backoff_delay *= 2.0
                    continue

                raise ProviderExecutionError(
                    f"Gemini API HTTP {e.code} error: {e.reason} - {err_body}"
                )
            except urllib.error.URLError as e:
                raise ProviderExecutionError(f"Gemini connection error: {e}")
            except Exception as e:
                raise ProviderExecutionError(f"Gemini API error: {e}")

        candidates = data.get("candidates", [])
        if not candidates:
            raise ProviderExecutionError(f"Gemini returned empty candidates array: {data}")

        candidate = candidates[0]
        text_parts = []
        tool_calls: List[ToolCall] = []

        parts = candidate.get("content", {}).get("parts", [])
        for p in parts:
            if "text" in p:
                text_parts.append(p["text"])
            if "functionCall" in p:
                fc = p["functionCall"]
                fc_name = fc.get("name", "")
                raw_args = fc.get("args", {})
                norm_args = normalize_tool_arguments(raw_args)
                call_id = fc.get("id") or f"call_{uuid.uuid4().hex[:8]}"
                provider_metadata = {
                    "raw_part": p,
                    "name": fc_name,
                    "args": norm_args,
                }
                if "id" in fc:
                    provider_metadata["id"] = fc["id"]
                if "thought_signature" in fc:
                    provider_metadata["thought_signature"] = fc["thought_signature"]
                elif "thought_signature" in p:
                    provider_metadata["thought_signature"] = p["thought_signature"]
                if "tool_type" in fc:
                    provider_metadata["tool_type"] = fc["tool_type"]
                elif "tool_type" in p:
                    provider_metadata["tool_type"] = p["tool_type"]

                tool_calls.append(
                    ToolCall(
                        id=call_id,
                        name=fc_name,
                        arguments=norm_args,
                        provider_metadata=provider_metadata,
                    )
                )

        full_content = "\n".join(text_parts) if text_parts else None

        usage = data.get("usageMetadata", {})
        prompt_tokens = usage.get("promptTokenCount", 0)
        completion_tokens = usage.get("candidatesTokenCount", 0)

        # Directive P0-I: Split client correlation ID from provider ID
        client_req_id = f"client_gemini_{self._model_id}_{int(start_time*1000)}_{uuid.uuid4().hex[:6]}"

        return ModelResponse(
            content=full_content,
            tool_calls=tool_calls,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            duration_seconds=duration,
            finish_reason=candidate.get("finishReason", "stop"),
            client_request_id=client_req_id,
            provider_request_id=None,
            provider_request_id_available=False,
            execution_origin="REAL_PROVIDER",
            raw_metadata={"usage": usage, "modelVersion": data.get("modelVersion")},
            provider_parts=parts,
        )
