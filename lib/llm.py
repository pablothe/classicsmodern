"""
LLM Provider Abstraction

Unified interface for text generation across multiple LLM providers:
- Ollama (local, default)
- OpenAI (optional, requires `pip install openai`)
- Anthropic (optional, requires `pip install anthropic`)

Usage:
    from lib.llm import create_llm_provider

    # Uses LLM_PROVIDER env var, defaults to "ollama"
    llm = create_llm_provider()

    # Explicit provider
    llm = create_llm_provider(provider="openai", model="gpt-4o-mini")

    # Text generation (translation, summarization, cover prompts, language detection)
    result = llm.generate("Translate to English: Bonjour le monde", temperature=0.3)

    # Chat-style generation (AI chat with message history)
    result = llm.chat([
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "What happens in chapter 3?"}
    ], temperature=0.3)
"""

import logging
import os
from abc import ABC, abstractmethod

import requests

logger = logging.getLogger(__name__)

# Provider name constants
OLLAMA = "ollama"
OPENAI = "openai"
ANTHROPIC = "anthropic"

SUPPORTED_PROVIDERS = [OLLAMA, OPENAI, ANTHROPIC]

# Default models per provider
DEFAULT_MODELS = {
    OLLAMA: "zongwei/gemma3-translator:4b",
    OPENAI: "gpt-4o-mini",
    ANTHROPIC: "claude-haiku-4-5-20251001",
}


class LLMProvider(ABC):
    """Base class for LLM providers."""

    def __init__(self, name: str, model: str):
        self.name = name
        self.model = model

    @abstractmethod
    def generate(self, prompt: str, temperature: float = 0.3, timeout: int = 300) -> str:
        """Simple text-in/text-out generation."""
        ...

    def chat(self, messages: list[dict], temperature: float = 0.3, timeout: int = 300) -> str:
        """Chat-style generation with message arrays. Default wraps generate()."""
        # Extract the last user message as a simple prompt
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                prompt_parts.insert(0, content)
            else:
                prompt_parts.append(content)
        return self.generate("\n\n".join(prompt_parts), temperature=temperature, timeout=timeout)

    @abstractmethod
    def is_available(self) -> dict:
        """Health check. Returns {"available": bool, "provider": str, "error": str|None}."""
        ...

    def __repr__(self):
        return f"{self.__class__.__name__}(model={self.model!r})"


class OllamaProvider(LLMProvider):
    """Ollama local LLM provider using HTTP API."""

    def __init__(self, model: str = None, host: str = None):
        self.host = host or os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        super().__init__(OLLAMA, model or DEFAULT_MODELS[OLLAMA])

    def generate(self, prompt: str, temperature: float = 0.3, timeout: int = 300) -> str:
        url = f"{self.host}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": temperature},
        }
        response = requests.post(url, json=payload, timeout=timeout)
        response.raise_for_status()
        return response.json().get("response", "").strip()

    def chat(self, messages: list[dict], temperature: float = 0.3, timeout: int = 300) -> str:
        try:
            import ollama as ollama_lib
            response = ollama_lib.chat(model=self.model, messages=messages, options={"temperature": temperature})
            return response.get("message", {}).get("content", "").strip()
        except ImportError:
            # Fall back to HTTP API
            url = f"{self.host}/api/chat"
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {"temperature": temperature},
            }
            response = requests.post(url, json=payload, timeout=timeout)
            response.raise_for_status()
            return response.json().get("message", {}).get("content", "").strip()

    def is_available(self) -> dict:
        try:
            response = requests.get(f"{self.host}/api/tags", timeout=5)
            response.raise_for_status()
            models = [m.get("name", "") for m in response.json().get("models", [])]
            return {"available": True, "provider": OLLAMA, "models": models, "error": None}
        except Exception as e:
            return {"available": False, "provider": OLLAMA, "models": [], "error": str(e)}


class OpenAIProvider(LLMProvider):
    """OpenAI API provider. Requires `pip install openai`."""

    def __init__(self, model: str = None, api_key: str = None):
        try:
            import openai
            self._openai = openai
        except ImportError:
            raise ImportError(
                "OpenAI provider requires the 'openai' package. "
                "Install with: pip install openai"
            )
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not self._api_key:
            raise ValueError(
                "OpenAI API key is required. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        self._client = openai.OpenAI(api_key=self._api_key)
        super().__init__(OPENAI, model or DEFAULT_MODELS[OPENAI])

    def generate(self, prompt: str, temperature: float = 0.3, timeout: int = 300) -> str:
        return self.chat(
            [{"role": "user", "content": prompt}],
            temperature=temperature,
            timeout=timeout,
        )

    def chat(self, messages: list[dict], temperature: float = 0.3, timeout: int = 300) -> str:
        response = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=temperature,
            timeout=timeout,
        )
        return response.choices[0].message.content.strip()

    def is_available(self) -> dict:
        try:
            self._client.models.list()
            return {"available": True, "provider": OPENAI, "error": None}
        except Exception as e:
            return {"available": False, "provider": OPENAI, "error": str(e)}


class AnthropicProvider(LLMProvider):
    """Anthropic API provider. Requires `pip install anthropic`."""

    def __init__(self, model: str = None, api_key: str = None):
        try:
            import anthropic
            self._anthropic = anthropic
        except ImportError:
            raise ImportError(
                "Anthropic provider requires the 'anthropic' package. "
                "Install with: pip install anthropic"
            )
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not self._api_key:
            raise ValueError(
                "Anthropic API key is required. Set ANTHROPIC_API_KEY environment variable "
                "or pass api_key parameter."
            )
        self._client = anthropic.Anthropic(api_key=self._api_key)
        super().__init__(ANTHROPIC, model or DEFAULT_MODELS[ANTHROPIC])

    def generate(self, prompt: str, temperature: float = 0.3, timeout: int = 300) -> str:
        return self.chat(
            [{"role": "user", "content": prompt}],
            temperature=temperature,
            timeout=timeout,
        )

    def chat(self, messages: list[dict], temperature: float = 0.3, timeout: int = 300) -> str:
        # Anthropic separates system message from the messages array
        system_text = None
        chat_messages = []
        for msg in messages:
            if msg.get("role") == "system":
                system_text = msg.get("content", "")
            else:
                chat_messages.append(msg)

        # Anthropic requires at least one user message
        if not chat_messages:
            chat_messages = [{"role": "user", "content": ""}]

        kwargs = {
            "model": self.model,
            "messages": chat_messages,
            "temperature": temperature,
            "max_tokens": 4096,
        }
        if system_text:
            kwargs["system"] = system_text

        response = self._client.messages.create(**kwargs)
        return response.content[0].text.strip()

    def is_available(self) -> dict:
        try:
            # Light check — just verify the key works
            self._client.messages.create(
                model=self.model,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1,
            )
            return {"available": True, "provider": ANTHROPIC, "error": None}
        except Exception as e:
            return {"available": False, "provider": ANTHROPIC, "error": str(e)}


def create_llm_provider(
    provider: str = None,
    model: str = None,
    api_key: str = None,
    host: str = None,
) -> LLMProvider:
    """
    Factory function to create an LLM provider instance.

    Args:
        provider: Provider name ("ollama", "openai", "anthropic").
                  Defaults to LLM_PROVIDER env var, then "ollama".
        model: Model name. Defaults to LLM_MODEL env var, then provider default.
        api_key: API key for OpenAI/Anthropic. Reads from env if not provided.
        host: Ollama host URL. Reads from OLLAMA_HOST env var if not provided.

    Returns:
        LLMProvider instance
    """
    provider = provider or os.environ.get("LLM_PROVIDER", OLLAMA)
    model = model or os.environ.get("LLM_MODEL", "") or None

    if provider == OLLAMA:
        return OllamaProvider(model=model, host=host)
    elif provider == OPENAI:
        return OpenAIProvider(model=model, api_key=api_key)
    elif provider == ANTHROPIC:
        return AnthropicProvider(model=model, api_key=api_key)
    else:
        raise ValueError(
            f"Unknown LLM provider: {provider!r}. "
            f"Supported providers: {', '.join(SUPPORTED_PROVIDERS)}"
        )


def get_available_providers() -> list[dict]:
    """
    Check which LLM providers are available on this system.

    Returns list of dicts with provider info (installed, key_set, etc.).
    Used by the web UI to show/hide provider options.
    """
    providers = []

    # Ollama — always "installed" (uses requests), check if running
    try:
        resp = requests.get(
            os.environ.get("OLLAMA_HOST", "http://localhost:11434") + "/api/tags",
            timeout=3,
        )
        ollama_running = resp.status_code == 200
    except Exception:
        ollama_running = False

    providers.append({
        "name": OLLAMA,
        "installed": True,
        "available": ollama_running,
        "key_set": True,  # no key needed
        "default_model": DEFAULT_MODELS[OLLAMA],
    })

    # OpenAI
    try:
        import openai  # noqa: F401
        openai_installed = True
    except ImportError:
        openai_installed = False

    providers.append({
        "name": OPENAI,
        "installed": openai_installed,
        "available": openai_installed and bool(os.environ.get("OPENAI_API_KEY")),
        "key_set": bool(os.environ.get("OPENAI_API_KEY")),
        "default_model": DEFAULT_MODELS[OPENAI],
    })

    # Anthropic
    try:
        import anthropic  # noqa: F401
        anthropic_installed = True
    except ImportError:
        anthropic_installed = False

    providers.append({
        "name": ANTHROPIC,
        "installed": anthropic_installed,
        "available": anthropic_installed and bool(os.environ.get("ANTHROPIC_API_KEY")),
        "key_set": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "default_model": DEFAULT_MODELS[ANTHROPIC],
    })

    return providers
