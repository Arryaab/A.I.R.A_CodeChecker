from __future__ import annotations

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
from aegis.research.models.gemini import GeminiModelAdapter
from aegis.research.models.ollama import OllamaModelAdapter
from aegis.research.models.openai import OpenAICompatibleAdapter

__all__ = [
    "ModelCapabilities",
    "ModelMetadata",
    "ModelProvider",
    "ModelResponse",
    "ToolCall",
    "ProviderUnavailableError",
    "ProviderExecutionError",
    "ModelDigestMismatchError",
    "GeminiModelAdapter",
    "OllamaModelAdapter",
    "OpenAICompatibleAdapter",
]
