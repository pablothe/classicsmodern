#!/usr/bin/env python3
"""
Unit Tests for Configuration Module

Tests configuration defaults, file I/O, and environment variable handling.
"""

import pytest
import json
from pathlib import Path

from lib.config import (
    AppConfig, ModelConfig, TranslationConfig, CompressionConfig,
    AudioConfig, StorageConfig, WebConfig, LoggingConfig,
)


# ============================================================================
# Default Configuration Tests
# ============================================================================

class TestConfigDefaults:
    """Test that configuration defaults are sensible."""

    def test_model_defaults(self):
        config = ModelConfig()
        assert config.default_translation_model == "zongwei/gemma3-translator:4b"
        assert "localhost" in config.ollama_host
        assert config.llm_provider == "ollama" or config.llm_provider in ("openai", "anthropic")

    def test_translation_defaults(self):
        config = TranslationConfig()
        assert config.chunk_size_words > 0
        assert config.max_retries >= 1
        assert "German" in config.supported_source_languages
        assert "Modern English" in config.supported_target_languages

    def test_compression_defaults(self):
        config = CompressionConfig()
        assert 0 < config.min_compression_ratio < config.max_compression_ratio <= 1.0
        assert config.default_compression_ratio == 0.5
        assert config.default_words_per_minute > 0

    def test_audio_defaults(self):
        config = AudioConfig()
        assert config.default_voice in config.kokoro_voices
        assert "wav" in config.supported_formats
        assert config.mp3_vbr_quality >= 0

    def test_storage_paths(self, temp_dir):
        config = StorageConfig(base_data_dir=str(temp_dir / "data"))
        assert config.books_dir == Path(str(temp_dir / "data")) / "books"
        assert config.audio_dir == Path(str(temp_dir / "data")) / "audio"
        assert config.cache_dir == Path(str(temp_dir / "data")) / "cache"

    def test_storage_ensure_directories(self, temp_dir):
        config = StorageConfig(base_data_dir=str(temp_dir / "data"))
        config.ensure_directories()

        assert config.books_dir.exists()
        assert config.translations_dir.exists()
        assert config.audio_dir.exists()
        assert config.cache_dir.exists()


# ============================================================================
# AppConfig Serialization Tests
# ============================================================================

class TestAppConfigSerialization:
    """Test configuration save/load round-trip."""

    def test_to_dict_has_expected_keys(self, temp_dir):
        config = AppConfig(storage=StorageConfig(base_data_dir=str(temp_dir / "data")))
        d = config.to_dict()

        assert "models" in d
        assert "translation" in d
        assert "compression" in d
        assert "audio" in d
        assert "storage" in d

    def test_save_and_load_roundtrip(self, temp_dir):
        config_file = str(temp_dir / "config.json")
        original = AppConfig(storage=StorageConfig(base_data_dir=str(temp_dir / "data")))
        original.save_to_file(config_file)

        loaded = AppConfig.from_file(config_file)
        assert loaded.models.default_translation_model == original.models.default_translation_model
        assert loaded.audio.default_voice == original.audio.default_voice

    def test_from_file_returns_defaults_if_missing(self, temp_dir):
        config = AppConfig.from_file(str(temp_dir / "nonexistent.json"))
        assert config.models.default_translation_model == "zongwei/gemma3-translator:4b"

    def test_from_file_handles_partial_config(self, temp_dir):
        config_file = temp_dir / "partial.json"
        config_file.write_text(json.dumps({"models": {"ollama_host": "http://custom:11434"}}))

        config = AppConfig.from_file(str(config_file))
        assert config.models.ollama_host == "http://custom:11434"
        # Other fields should keep defaults
        assert config.audio.default_voice == "bf_emma"

    def test_save_creates_valid_json(self, temp_dir):
        config_file = str(temp_dir / "config.json")
        config = AppConfig(storage=StorageConfig(base_data_dir=str(temp_dir / "data")))
        config.save_to_file(config_file)

        with open(config_file) as f:
            data = json.load(f)
        assert isinstance(data, dict)


# ============================================================================
# LoggingConfig Tests
# ============================================================================

class TestLoggingConfig:
    """Test logging configuration defaults."""

    def test_defaults(self):
        config = LoggingConfig()
        assert config.log_dir == "logs"
        assert config.console_level == "INFO"
        assert config.file_level == "DEBUG"
        assert config.max_bytes > 0
        assert config.backup_count >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
