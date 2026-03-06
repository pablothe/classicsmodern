"""
Local Reader Configuration Module

Central configuration management for the local reader application.
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List
import json

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


@dataclass
class ModelConfig:
    """Configuration for AI models"""
    # Translation models
    translation_model_1b: str = "zongwei/gemma3-translator:1b"
    translation_model_4b: str = "zongwei/gemma3-translator:4b"
    default_translation_model: str = "zongwei/gemma3-translator:4b"

    # TTS models
    tts_model_local: str = "kokoro"

    # Ollama configuration
    ollama_host: str = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
    ollama_timeout: int = 300  # seconds

    # LLM provider configuration (ollama, openai, anthropic)
    llm_provider: str = os.environ.get("LLM_PROVIDER", "ollama")
    llm_model: str = os.environ.get("LLM_MODEL", "")  # empty = provider default


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
    # Kokoro TTS voices (100% local)
    kokoro_voices: List[str] = field(default_factory=lambda: [
        "af_sky", "bf_emma", "bm_george", "am_adam", "am_onyx"
    ])
    default_voice: str = "bf_emma"

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
                "llm_provider": self.models.llm_provider,
                "llm_model": self.models.llm_model,
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
                "kokoro_voices": self.audio.kokoro_voices,
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


def create_default_llm():
    """Create an LLM provider from the current config. Convenience wrapper."""
    from lib.llm import create_llm_provider
    config = get_config()
    return create_llm_provider(
        provider=config.models.llm_provider,
        model=config.models.llm_model or None,
        host=config.models.ollama_host,
    )


@dataclass
class LoggingConfig:
    """Configuration for centralized logging"""
    log_dir: str = "logs"
    log_format: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    console_level: str = "INFO"
    file_level: str = "DEBUG"
    max_bytes: int = 5 * 1024 * 1024  # 5MB per file
    backup_count: int = 3


def setup_logging(config: LoggingConfig = None) -> None:
    """
    Configure centralized logging with rotating file handlers.

    Call once at application startup. Creates two log files:
      - logs/server.log  (all application logs)
      - logs/jobs.log    (job execution: translation, audio, cover)
    """
    if config is None:
        config = LoggingConfig()

    # Resolve logs/ relative to project root (lib/ is one level down)
    log_dir = Path(__file__).parent.parent / config.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(config.log_format)

    # Root logger — catches everything
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers.clear()

    # Console handler — same output as before (print-like)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, config.console_level))
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Server log file — all application logs
    server_handler = RotatingFileHandler(
        log_dir / "server.log",
        maxBytes=config.max_bytes,
        backupCount=config.backup_count,
    )
    server_handler.setLevel(getattr(logging, config.file_level))
    server_handler.setFormatter(formatter)
    root_logger.addHandler(server_handler)

    # Jobs log file — only job-related modules
    jobs_handler = RotatingFileHandler(
        log_dir / "jobs.log",
        maxBytes=config.max_bytes,
        backupCount=config.backup_count,
    )
    jobs_handler.setLevel(getattr(logging, config.file_level))
    jobs_handler.setFormatter(formatter)

    for name in [
        "server.job_queue",
        "server.audiobook_pipeline",
        "server.job_handlers",
        "lib.translation.engine",
        "lib.translation.structured",
        "lib.audio.kokoro",
        "lib.cover.generator",
        "lib.cover.prompts",
        "lib.summarize.engine",
    ]:
        logging.getLogger(name).addHandler(jobs_handler)

    # Suppress uvicorn access logs from file handlers.
    # They still appear in the terminal via the console handler.
    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.handlers.clear()
    uvicorn_access.propagate = False
    uvicorn_access.addHandler(console_handler)


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
