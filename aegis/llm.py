from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert Python bug repair assistant.
Analyze the buggy code, the test output, and diagnose the problem.
Your task is to fix the code and return a JSON object containing your diagnosis and the complete modified file(s).

You MUST return ONLY valid JSON wrapped in ```json fences.
Format:
```json
{
    "diagnosis": "Detailed explanation of the bug and how to fix it.",
    "patch": {
        "relative/path/to/file.py": "# The COMPLETE and correct file contents"
    }
}
```
"""

@dataclass
class LLMResponse:
    content: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    duration_seconds: float


class LLMProvider(ABC):
    @abstractmethod
    def ask(self, prompt: str, system: str = "") -> LLMResponse:
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        pass


class GeminiProvider(LLMProvider):
    """Uses google-generativeai SDK if available. Falls back to REST API via urllib."""
    def __init__(self, api_key: str, model: str = "gemini-3.8-flash", temperature: float = 0.2):
        self.api_key = api_key
        self._model = model
        self.temperature = temperature
        self._setup_client()

    def _setup_client(self):
        try:
            import google.generativeai as genai
            self.genai = genai
            self.genai.configure(api_key=self.api_key)
            self.use_sdk = True
        except ImportError:
            self.use_sdk = False

    @property
    def name(self) -> str:
        return self._model

    def ask(self, prompt: str, system: str = "") -> LLMResponse:
        start_time = time.time()
        max_retries = 5

        for attempt in range(max_retries):
            try:
                if self.use_sdk:
                    return self._ask_sdk(prompt, system, start_time)
                else:
                    return self._ask_rest(prompt, system, start_time)
            except Exception as e:
                error_str = str(e)
                is_rate_limit = "429" in error_str or "quota" in error_str.lower()

                if attempt == max_retries - 1:
                    raise

                if is_rate_limit:
                    # Parse retry delay from error if available,
                    # otherwise default to 60s for rate limits.
                    wait = self._parse_retry_delay(error_str)
                    logger.warning(
                        f"Rate limited (attempt {attempt + 1}). "
                        f"Waiting {wait}s before retry..."
                    )
                    time.sleep(wait)
                else:
                    wait = min(2 ** attempt, 16)
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {wait}s..."
                    )
                    time.sleep(wait)

        raise RuntimeError("Failed to generate response from Gemini API.")

    @staticmethod
    def _parse_retry_delay(error_str: str) -> float:
        """Extract retry_delay seconds from Gemini API error message."""
        import re
        match = re.search(r'retry in (\d+(?:\.\d+)?)s', error_str, re.IGNORECASE)
        if match:
            return float(match.group(1)) + 2  # Add 2s buffer
        match = re.search(r'retry_delay\s*\{\s*seconds:\s*(\d+)', error_str)
        if match:
            return float(match.group(1)) + 2
        return 62  # Default: wait just over 1 minute

    def _ask_sdk(self, prompt: str, system: str, start_time: float) -> LLMResponse:
        generation_config = self.genai.types.GenerationConfig(
            temperature=self.temperature
        )
        # Only pass system_instruction when non-empty — Gemini SDK
        # rejects empty strings with "'content' argument must not be empty".
        model_kwargs = {"model_name": self._model}
        if system:
            model_kwargs["system_instruction"] = system
        model = self.genai.GenerativeModel(**model_kwargs)
        
        response = model.generate_content(
            prompt,
            generation_config=generation_config
        )
        
        duration = time.time() - start_time
        usage = response.usage_metadata
        prompt_tokens = usage.prompt_token_count if usage else 0
        completion_tokens = usage.candidates_token_count if usage else 0
        
        return LLMResponse(
            content=response.text,
            model=self._model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            duration_seconds=duration
        )

    def _ask_rest(self, prompt: str, system: str, start_time: float) -> LLMResponse:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self._model}:generateContent?key={self.api_key}"
        
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "temperature": self.temperature
            }
        }
        # Only include system_instruction when non-empty.
        if system:
            payload["system_instruction"] = {
                "parts": [{"text": system}]
            }
        
        req = urllib.request.Request(
            url, 
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode("utf-8"))
            
        text = result["candidates"][0]["content"]["parts"][0]["text"]
        
        usage = result.get("usageMetadata", {})
        prompt_tokens = usage.get("promptTokenCount", 0)
        completion_tokens = usage.get("candidatesTokenCount", 0)
        
        duration = time.time() - start_time
        
        return LLMResponse(
            content=text,
            model=self._model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            duration_seconds=duration
        )

class OllamaProvider(LLMProvider):
    """Uses a local Ollama instance (no API key required)."""
    def __init__(self, model: str = "qwen2.5-coder", temperature: float = 0.2):
        self._model = model
        self.temperature = temperature
        self.endpoint = "http://localhost:11434/api/generate"

    @property
    def name(self) -> str:
        return f"ollama/{self._model}"

    def ask(self, prompt: str, system: str = "") -> LLMResponse:
        start_time = time.time()
        
        payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature
            }
        }
        if system:
            payload["system"] = system

        req = urllib.request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        
        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as e:
            raise RuntimeError(f"Failed to connect to Ollama at {self.endpoint}. Is Ollama running? Error: {e}")
            
        text = result.get("response", "")
        
        duration = time.time() - start_time
        prompt_tokens = result.get("prompt_eval_count", 0)
        completion_tokens = result.get("eval_count", 0)
        
        return LLMResponse(
            content=text,
            model=self._model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            duration_seconds=duration
        )

class MockProvider(LLMProvider):
    """Returns pre-configured responses. For testing."""
    def __init__(self, responses: list[str]):
        self.responses = responses
        self.index = 0
        self._model = "mock-model"

    @property
    def name(self) -> str:
        return self._model

    def ask(self, prompt: str, system: str = "") -> LLMResponse:
        content = self.responses[self.index % len(self.responses)]
        self.index += 1
        return LLMResponse(
            content=content,
            model=self._model,
            prompt_tokens=10,
            completion_tokens=20,
            duration_seconds=0.1
        )


def build_repair_prompt(
    files: dict[str, str],
    test_output: str,
    previous_attempt: str | None = None,
    repo_map: str | None = None,
) -> str:
    """Build the prompt sent to the LLM for repair.
    Returns a prompt instructing the LLM to return JSON:
    {
        "diagnosis": "...",
        "patch": {"relative/path.py": "entire corrected file content"}
    }
    """
    prompt = ""
    if repo_map:
        prompt += f"Repository Context:\n```\n{repo_map}\n```\n\n"
        
    prompt += "Target files for repair:\n"
    for file_path, source_code in files.items():
        prompt += f"File: `{file_path}`\n```python\n{source_code}\n```\n\n"
        
    prompt += f"Test output:\n```\n{test_output}\n```\n\n"
    
    if previous_attempt:
        prompt += f"Previous attempt diagnosis or output:\n```\n{previous_attempt}\n```\n"
        prompt += "The previous attempt failed. Please learn from it and try a different approach.\n\n"
        
    prompt += "Please diagnose the problem and provide a complete patched file contents.\n"
    prompt += "Return ONLY a JSON response wrapped in ```json ... ``` code fences, with 'diagnosis' and 'patch' keys."
    
    return prompt
