from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class AegisConfig:
    """Central configuration for Aegis-Lite."""
    model: str = "gemini-3.8-flash"
    max_retries: int = 3
    timeout_seconds: int = 60
    sandbox_enabled: bool = False
    docker_image: str = "aegis-sandbox:latest"
    api_key: str = ""  # loaded from env AEGIS_API_KEY or GEMINI_API_KEY
    temperature: float = 0.2
    max_tokens: int = 4096
    log_level: str = "INFO"


def load_config(path: str | Path | None = None) -> AegisConfig:
    """Load config from JSON file, with env variable overrides.
    
    If path is provided and exists, it will load JSON from that file.
    If path is provided but does not exist, it gracefully returns defaults.
    Environment variables AEGIS_API_KEY or GEMINI_API_KEY override the file.
    """
    config_dict = {}
    if path is not None:
        p = Path(path)
        if p.exists() and p.is_file():
            try:
                with open(p, "r", encoding="utf-8") as f:
                    config_dict = json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
    
    config = AegisConfig(**{k: v for k, v in config_dict.items() if hasattr(AegisConfig, k)})
    
    env_api_key = os.environ.get("AEGIS_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if env_api_key:
        config.api_key = env_api_key
        
    return config


def save_config(config: AegisConfig, path: str | Path) -> None:
    """Save config to JSON."""
    p = Path(path)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(asdict(config), f, indent=4)
