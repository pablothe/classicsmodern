"""
Job Handlers - Worker implementations for different job types

Each handler processes a specific job type:
- download_handler: Gutenberg book downloads
- translate_handler: Book translation
- pipeline_handler: Full audiobook pipeline
"""

from .cover_handler import cover_handler
from .download_handler import download_handler
from .pipeline_handler import pipeline_handler
from .translate_handler import translate_handler

__all__ = ['cover_handler', 'download_handler', 'pipeline_handler', 'translate_handler']
