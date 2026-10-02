from __future__ import annotations

import hashlib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ToolCall:
    """Represents a tool call requested by the model."""
    id: str
    name: str
    arguments: Dict[str, Any]
    provider_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelCapabilities:
    """Declares what features the model/provider supports."""
    supports_tools: bool = True
    supports_system_prompt: bool = True
    supports_seed: bool = False
    supports_json_mode: bool = True
    supports_streaming: bool = False
    max_context_tokens: int = 32768
    max_output_tokens: int = 4096


@dataclass
class ModelMetadata:
    """Immutable, reproducible metadata about the provider and model."""
    provider: str
    model_id: str
    model_version: Optional[str] = None
    seed: Optional[int] = None
    temperature: float = 0.2
    top_p: float = 0.95
    max_tokens: int = 2048
    system_prompt_hash: Optional[str] = None
    capabilities: ModelCapabilities = field(default_factory=ModelCapabilities)
    extra_params: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model_id": self.model_id,
            "model_version": self.model_version,
            "seed": self.seed,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
            "system_prompt_hash": self.system_prompt_hash,
            "supports_seed": self.capabilities.supports_seed,
            "extra_params": self.extra_params,
        }


@dataclass
class ModelResponse:
    """Structured response from a model execution."""
    content: Optional[str]
    tool_calls: List[ToolCall] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0
    duration_seconds: float = 0.0
    finish_reason: str = "stop"
    client_request_id: Optional[str] = None
    provider_request_id: Optional[str] = None
    provider_request_id_available: bool = False
    execution_origin: str = "REAL_PROVIDER"
    raw_metadata: Dict[str, Any] = field(default_factory=dict)
    provider_parts: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class ProviderUnavailableError(RuntimeError):
    """Raised when a model provider backend is unavailable or not configured."""
    pass


class ProviderExecutionError(RuntimeError):
    """Raised when an actual provider API call fails during generation."""
    pass


class ModelDigestMismatchError(RuntimeError):
    """Raised when a model digest differs from the frozen experiment specification."""
    pass


class ModelProvider(ABC):
    """Abstract provider interface for multi-model research harness."""

    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs: Any,
    ) -> ModelResponse:
        """Execute a completion or tool invocation against the model."""
        pass

    @abstractmethod
    def metadata(self) -> ModelMetadata:
        """Return full reproducible metadata for this model instance."""
        pass

    @abstractmethod
    def capabilities(self) -> ModelCapabilities:
        """Return the capabilities profile for this model instance."""
        pass

    @abstractmethod
    def check_health(self) -> Dict[str, Any]:
        """Perform a minimal live health check against the real provider."""
        pass

    @staticmethod
    def hash_prompt(prompt: str) -> str:
        """Compute cryptographic SHA-256 hash of prompt content."""
        return hashlib.sha256(prompt.encode("utf-8")).hexdigest()
