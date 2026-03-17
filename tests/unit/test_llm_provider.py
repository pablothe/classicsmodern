#!/usr/bin/env python3
"""Unit tests for lib/llm.py - LLM provider abstraction"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.llm import (
    create_llm_provider, OllamaProvider, LLMProvider,
    OLLAMA, OPENAI, ANTHROPIC, SUPPORTED_PROVIDERS, DEFAULT_MODELS,
    get_available_providers,
)


class TestCreateLLMProvider:
    def test_default_creates_ollama(self, monkeypatch):
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        monkeypatch.delenv("LLM_MODEL", raising=False)
        provider = create_llm_provider()
        assert isinstance(provider, OllamaProvider)

    def test_env_var_selects_ollama(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "ollama")
        monkeypatch.delenv("LLM_MODEL", raising=False)
        provider = create_llm_provider()
        assert isinstance(provider, OllamaProvider)

    def test_explicit_provider_overrides_env(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        provider = create_llm_provider(provider="ollama")
        assert isinstance(provider, OllamaProvider)

    def test_unknown_provider_raises_valueerror(self):
        with pytest.raises(ValueError, match="Unknown LLM provider"):
            create_llm_provider(provider="nonexistent")

    def test_ollama_default_model(self, monkeypatch):
        monkeypatch.delenv("LLM_MODEL", raising=False)
        provider = create_llm_provider(provider="ollama")
        assert provider.model == DEFAULT_MODELS[OLLAMA]

    def test_custom_model_passed_through(self, monkeypatch):
        monkeypatch.delenv("LLM_MODEL", raising=False)
        provider = create_llm_provider(provider="ollama", model="custom:7b")
        assert provider.model == "custom:7b"


class TestOllamaProvider:
    def test_generate_calls_http(self, monkeypatch):
        mock_response = MagicMock()
        mock_response.json.return_value = {"response": "translated text"}
        mock_response.raise_for_status = MagicMock()

        with patch("lib.llm.requests.post", return_value=mock_response) as mock_post:
            provider = OllamaProvider(model="test:1b")
            result = provider.generate("test prompt")
            assert result == "translated text"
            mock_post.assert_called_once()

    def test_is_available_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "test:1b"}]}
        mock_response.raise_for_status = MagicMock()

        with patch("lib.llm.requests.get", return_value=mock_response):
            provider = OllamaProvider()
            result = provider.is_available()
            assert result["available"] is True

    def test_is_available_failure(self):
        with patch("lib.llm.requests.get", side_effect=Exception("connection refused")):
            provider = OllamaProvider()
            result = provider.is_available()
            assert result["available"] is False
            assert "connection refused" in result["error"]


class TestOpenAIProvider:
    def test_missing_package_raises_importerror(self, monkeypatch):
        # Simulate openai not being installed
        import importlib
        with patch.dict('sys.modules', {'openai': None}):
            with pytest.raises(ImportError, match="openai"):
                from lib.llm import OpenAIProvider
                OpenAIProvider()

    def test_missing_api_key_raises_valueerror(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        try:
            from lib.llm import OpenAIProvider
            mock_openai = MagicMock()
            with patch.dict('sys.modules', {'openai': mock_openai}):
                with pytest.raises(ValueError, match="API key"):
                    OpenAIProvider(api_key="")
        except ImportError:
            pytest.skip("openai package not installed")


class TestAnthropicProvider:
    def test_missing_package_raises_importerror(self):
        with patch.dict('sys.modules', {'anthropic': None}):
            with pytest.raises(ImportError, match="anthropic"):
                from lib.llm import AnthropicProvider
                AnthropicProvider()

    def test_missing_api_key_raises_valueerror(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        try:
            from lib.llm import AnthropicProvider
            mock_anthropic = MagicMock()
            with patch.dict('sys.modules', {'anthropic': mock_anthropic}):
                with pytest.raises(ValueError, match="API key"):
                    AnthropicProvider(api_key="")
        except ImportError:
            pytest.skip("anthropic package not installed")


class TestGetAvailableProviders:
    def test_returns_three_providers(self):
        with patch("lib.llm.requests.get", side_effect=Exception("offline")):
            providers = get_available_providers()
            assert len(providers) == 3
            names = [p["name"] for p in providers]
            assert OLLAMA in names
            assert OPENAI in names
            assert ANTHROPIC in names

    def test_ollama_not_running(self):
        with patch("lib.llm.requests.get", side_effect=Exception("refused")):
            providers = get_available_providers()
            ollama = next(p for p in providers if p["name"] == OLLAMA)
            assert ollama["available"] is False

    def test_all_have_default_model(self):
        with patch("lib.llm.requests.get", side_effect=Exception("offline")):
            providers = get_available_providers()
            for p in providers:
                assert "default_model" in p


class TestLLMProviderBaseChat:
    def test_chat_default_wraps_generate(self):
        """Test that the default chat() implementation calls generate()."""
        class TestProvider(LLMProvider):
            def generate(self, prompt, temperature=0.3, timeout=300):
                return f"generated: {prompt[:20]}"
            def is_available(self):
                return {"available": True}

        provider = TestProvider("test", "test-model")
        result = provider.chat([
            {"role": "system", "content": "Be helpful"},
            {"role": "user", "content": "Hello"}
        ])
        assert "generated:" in result
