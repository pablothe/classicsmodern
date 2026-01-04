"""
Local Reader Configuration Module

Central configuration management for the local reader application.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List
import json


@dataclass
class ModelConfig:
    """Configuration for AI models"""
    # Translation models
    translation_model_1b: str = "zongwei/gemma3-translator:1b"
    translation_model_4b: str = "zongwei/gemma3-translator:4b"
    default_translation_model: str = "zongwei/gemma3-translator:4b"

    # TTS models (to be configured later)
    tts_model_local: str = "orpheus-3b"  # Placeholder
    tts_model_temporary: str = "openai-whisper"  # Temporary fallback

    # Ollama configuration
    ollama_host: str = "http://localhost:11434"
    ollama_timeout: int = 300  # seconds


@dataclass
class TranslationConfig:
    """Configuration for translation process"""
    chunk_size_words: int = 250
    context_overlap_words: int = 20
    max_retries: int = 3
    retry_delay_seconds: int = 5

    # Language pairs
    supported_source_languages: List[str] = field(default_factory=lambda: [
        "German", "French", "Spanish", "Italian", "Russian",
        "Latin", "Ancient Greek", "Old English"
    ])

    supported_target_languages: List[str] = field(default_factory=lambda: [
        "Modern English", "Spanish", "French", "German"
    ])


@dataclass
class CompressionConfig:
    """Configuration for text compression/summarization"""
    default_compression_ratio: float = 0.5  # 50% of original
    min_compression_ratio: float = 0.1  # 10% minimum
    max_compression_ratio: float = 0.9  # 90% maximum

    # Audiobook reading speed (words per minute)
    words_per_minute_slow: int = 140
    words_per_minute_normal: int = 160
    words_per_minute_fast: int = 180
    default_words_per_minute: int = 160


@dataclass
class AudioConfig:
    """Configuration for audio generation"""
    # OpenAI voices (temporary)
    openai_voices: List[str] = field(default_factory=lambda: [
        "alloy", "echo", "fable", "onyx", "nova", "shimmer"
    ])
    default_voice: str = "fable"

    # Audio format settings
    default_format: str = "wav"
    supported_formats: List[str] = field(default_factory=lambda: ["wav", "mp3", "flac"])

    # Chunking for audio generation
    audio_chunk_chars: int = 4000
    generate_playlist: bool = True


@dataclass
class StorageConfig:
    """Configuration for file storage"""
    base_data_dir: str = "local_reader_data"

    @property
    def books_dir(self) -> Path:
        return Path(self.base_data_dir) / "books"

    @property
    def translations_dir(self) -> Path:
        return Path(self.base_data_dir) / "translations"

    @property
    def compressed_dir(self) -> Path:
        return Path(self.base_data_dir) / "compressed"

    @property
    def audio_dir(self) -> Path:
        return Path(self.base_data_dir) / "audio"

    @property
    def cache_dir(self) -> Path:
        return Path(self.base_data_dir) / "cache"

    def ensure_directories(self):
        """Create all necessary directories if they don't exist"""
        for directory in [
            self.books_dir,
            self.translations_dir,
            self.compressed_dir,
            self.audio_dir,
            self.cache_dir
        ]:
            directory.mkdir(parents=True, exist_ok=True)


@dataclass
class WebConfig:
    """Configuration for web interface"""
    host: str = "0.0.0.0"  # Allow external connections
    port: int = 5000
    debug: bool = True
    secret_key: str = os.environ.get("SECRET_KEY", "dev-secret-key-change-in-production")

    # API settings for mobile app
    enable_mobile_api: bool = True
    api_prefix: str = "/api"
    enable_mdns: bool = True  # Auto-discovery
    api_token: str = os.environ.get("API_TOKEN", "")  # Optional authentication


@dataclass
class AppConfig:
    """Main application configuration"""
    models: ModelConfig = field(default_factory=ModelConfig)
    translation: TranslationConfig = field(default_factory=TranslationConfig)
    compression: CompressionConfig = field(default_factory=CompressionConfig)
    audio: AudioConfig = field(default_factory=AudioConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    web: WebConfig = field(default_factory=WebConfig)

    # External API keys (optional)
    openai_api_key: str = os.environ.get("OPENAI_API_KEY", "")

    def __post_init__(self):
        """Initialize directories after config is created"""
        self.storage.ensure_directories()

    def to_dict(self) -> Dict:
        """Convert configuration to dictionary"""
        return {
            "models": {
                "translation_model_1b": self.models.translation_model_1b,
                "translation_model_4b": self.models.translation_model_4b,
                "default_translation_model": self.models.default_translation_model,
                "ollama_host": self.models.ollama_host,
            },
            "translation": {
                "chunk_size_words": self.translation.chunk_size_words,
                "supported_source_languages": self.translation.supported_source_languages,
                "supported_target_languages": self.translation.supported_target_languages,
            },
            "compression": {
                "default_compression_ratio": self.compression.default_compression_ratio,
                "default_words_per_minute": self.compression.default_words_per_minute,
            },
            "audio": {
                "openai_voices": self.audio.openai_voices,
                "default_voice": self.audio.default_voice,
                "supported_formats": self.audio.supported_formats,
            },
            "storage": {
                "base_data_dir": self.storage.base_data_dir,
            }
        }

    @classmethod
    def from_file(cls, config_file: str = "local_reader_config.json") -> "AppConfig":
        """
        Load configuration from a JSON file.

        Args:
            config_file: Path to configuration file

        Returns:
            AppConfig instance
        """
        if not os.path.exists(config_file):
            # Return default config if file doesn't exist
            return cls()

        with open(config_file, 'r') as f:
            config_dict = json.load(f)

        # Create config with values from file
        config = cls()

        # Update model settings
        if "models" in config_dict:
            for key, value in config_dict["models"].items():
                if hasattr(config.models, key):
                    setattr(config.models, key, value)

        # Update translation settings
        if "translation" in config_dict:
            for key, value in config_dict["translation"].items():
                if hasattr(config.translation, key):
                    setattr(config.translation, key, value)

        # Update compression settings
        if "compression" in config_dict:
            for key, value in config_dict["compression"].items():
                if hasattr(config.compression, key):
                    setattr(config.compression, key, value)

        # Update audio settings
        if "audio" in config_dict:
            for key, value in config_dict["audio"].items():
                if hasattr(config.audio, key):
                    setattr(config.audio, key, value)

        # Update storage settings
        if "storage" in config_dict:
            for key, value in config_dict["storage"].items():
                if hasattr(config.storage, key):
                    setattr(config.storage, key, value)

        return config

    def save_to_file(self, config_file: str = "local_reader_config.json"):
        """
        Save configuration to a JSON file.

        Args:
            config_file: Path to save configuration
        """
        with open(config_file, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)


# Global configuration instance
_config: AppConfig = None


def get_config() -> AppConfig:
    """
    Get the global configuration instance.

    Returns:
        AppConfig instance
    """
    global _config
    if _config is None:
        _config = AppConfig.from_file()
    return _config


def reload_config(config_file: str = "local_reader_config.json"):
    """
    Reload configuration from file.

    Args:
        config_file: Path to configuration file
    """
    global _config
    _config = AppConfig.from_file(config_file)


if __name__ == "__main__":
    # Create and save default configuration
    config = AppConfig()
    config.save_to_file("local_reader_config.json")
    print("Default configuration saved to local_reader_config.json")
    print("\nConfiguration summary:")
    print(f"  Translation model: {config.models.default_translation_model}")
    print(f"  Ollama host: {config.models.ollama_host}")
    print(f"  Data directory: {config.storage.base_data_dir}")
    print(f"  Web server: {config.web.host}:{config.web.port}")
    print(f"  Supported source languages: {', '.join(config.translation.supported_source_languages)}")
