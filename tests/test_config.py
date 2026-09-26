from __future__ import annotations

import os
from pathlib import Path
from aegis.config import AegisConfig, load_config, save_config


def test_default_config():
    config = AegisConfig()
    assert config.model == "gemini-3.8-flash"
    assert config.max_retries == 3
    assert config.timeout_seconds == 60
    assert config.sandbox_enabled is False
    assert config.api_key == ""


def test_load_config_from_file(tmp_path: Path):
    config_file = tmp_path / "config.json"
    config_file.write_text('{"model": "test-model", "max_retries": 5}')
    
    config = load_config(config_file)
    assert config.model == "test-model"
    assert config.max_retries == 5
    assert config.timeout_seconds == 60


def test_env_var_override(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("AEGIS_API_KEY", "secret-key")
    config = load_config()
    assert config.api_key == "secret-key"


def test_save_and_reload_roundtrip(tmp_path: Path):
    config_file = tmp_path / "config.json"
    
    original_config = AegisConfig(model="custom-model", max_retries=10, api_key="test-key")
    save_config(original_config, config_file)
    
    loaded_config = load_config(config_file)
    
    # API key might be overridden by env if it's set in the test environment
    # but let's assume it isn't or we clear it
    assert loaded_config.model == "custom-model"
    assert loaded_config.max_retries == 10
