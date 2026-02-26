#!/usr/bin/env python3
"""
Language Detector for Book Pipeline

Detects the language of source text files to determine if translation is needed.
Uses Gutenberg metadata (if available), script detection, LLM analysis, and pattern matching.
"""

import json
import logging
import re
from pathlib import Path
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class LanguageDetector:
    """Detect language of book text"""

    # Common language codes
    LANGUAGE_CODES = {
        'en': 'English',
        'es': 'Spanish',
        'fr': 'French',
        'de': 'German',
        'it': 'Italian',
        'ru': 'Russian',
        'pt': 'Portuguese',
        'la': 'Latin',
        'el': 'Greek',
        'zh': 'Chinese',
        'ja': 'Japanese',
        'ar': 'Arabic'
    }

    # Filename patterns that indicate language
    FILENAME_PATTERNS = {
        'russian': r'(russian|ru_|_ru|русский|преступление|война)',
        'spanish': r'(spanish|es_|_es|español|quijote|cien)',
        'french': r'(french|fr_|_fr|français|comte)',
        'german': r'(german|de_|_de|deutsch|faust)',
        'latin': r'(latin|la_|_la|vitae|seneca)',
        'greek': r'(greek|el_|_el|ελληνικά)',
    }

    def __init__(self):
        """Initialize language detector"""

    def _detect_from_gutenberg_metadata(self, filepath: Path) -> Optional[Dict]:
        """
        Check for gutenberg_metadata.json in the same directory.
        This is the most reliable source since it comes from Gutenberg's own catalog.

        Args:
            filepath: Path to file

        Returns:
            Full detection result dict, or None if no metadata found
        """
        meta_path = filepath.parent / "gutenberg_metadata.json"
        if not meta_path.exists():
            return None

        try:
            with open(meta_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            code = data.get('language')
            if not code:
                return None

            language_name = self.LANGUAGE_CODES.get(code, code.title())
            return {
                'language': language_name,
                'code': code,
                'confidence': 1.0,
                'method': 'gutenberg_metadata',
                'needs_translation': code != 'en'
            }
        except (json.JSONDecodeError, IOError):
            return None

    def _detect_from_filename(self, filepath: Path) -> Optional[str]:
        """
        Detect language from filename patterns.

        Args:
            filepath: Path to file

        Returns:
            Language name or None
        """
        filename_lower = str(filepath).lower()

        for lang, pattern in self.FILENAME_PATTERNS.items():
            if re.search(pattern, filename_lower):
                return lang.title()

        return None

    def _detect_from_script(self, text_sample: str) -> Optional[str]:
        """
        Detect language from script/character set.

        Args:
            text_sample: Sample of text to analyze

        Returns:
            Language name or None
        """
        # Cyrillic characters → Russian
        if re.search(r'[а-яА-ЯёЁ]', text_sample):
            return 'Russian'

        # Greek characters → Greek
        if re.search(r'[α-ωΑ-Ω]', text_sample):
            return 'Greek'

        # Chinese/Japanese characters
        if re.search(r'[\u4e00-\u9fff]', text_sample):
            # Could be Chinese or Japanese, need more analysis
            if re.search(r'[\u3040-\u309f\u30a0-\u30ff]', text_sample):
                return 'Japanese'
            return 'Chinese'

        # Arabic characters
        if re.search(r'[\u0600-\u06ff]', text_sample):
            return 'Arabic'

        return None

    def _detect_with_llm(self, filepath: Path) -> Optional[str]:
        """
        Use LLM to detect language from ~30 words in the middle of the book.

        Reads from the midpoint to avoid Gutenberg headers and mixed-language
        frontmatter. Handles Latin-script languages (French, Spanish, Latin, etc.)
        that script detection can't distinguish.

        Args:
            filepath: Path to book file

        Returns:
            Language name or None
        """
        try:
            import sys
            # Ensure project root is on path for lib imports
            project_root = str(Path(__file__).parent.parent)
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            from lib.cover.prompts import detect_language_with_llm
            language = detect_language_with_llm(filepath)
            if language:
                return language
        except Exception as e:
            logger.warning(f"LLM language detection failed: {e}")

        return None

    def detect_language(self, filepath: Path) -> Dict:
        """
        Detect the language of a book file using multiple methods.

        Args:
            filepath: Path to book markdown file

        Returns:
            Dictionary with detection results:
            {
                'language': 'Russian',
                'code': 'ru',
                'confidence': 0.95,
                'method': 'script|filename|english_default',
                'needs_translation': True
            }
        """
        # Method 0: Gutenberg metadata (highest priority, 100% reliable)
        gutenberg_result = self._detect_from_gutenberg_metadata(filepath)
        if gutenberg_result:
            return gutenberg_result

        # Read file sample
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                # Read first 2000 characters (enough for detection)
                text_sample = f.read(2000)
        except Exception as e:
            return {
                'language': 'Unknown',
                'code': 'unknown',
                'confidence': 0.0,
                'method': 'error',
                'needs_translation': False,
                'error': str(e)
            }

        # Method 1: Script-based detection (fastest, most reliable for non-Latin scripts)
        script_lang = self._detect_from_script(text_sample)
        if script_lang:
            return {
                'language': script_lang,
                'code': self._get_language_code(script_lang),
                'confidence': 0.99,
                'method': 'script',
                'needs_translation': script_lang.lower() != 'english'
            }

        # Method 2: LLM-based detection (reads ~30 words from middle of book)
        # Handles Latin-script languages that script detection can't distinguish
        llm_lang = self._detect_with_llm(filepath)
        if llm_lang:
            return {
                'language': llm_lang,
                'code': self._get_language_code(llm_lang),
                'confidence': 0.9,
                'method': 'llm',
                'needs_translation': llm_lang.lower() != 'english'
            }

        # Method 3: Filename pattern matching
        filename_lang = self._detect_from_filename(filepath)
        if filename_lang:
            return {
                'language': filename_lang,
                'code': self._get_language_code(filename_lang),
                'confidence': 0.7,
                'method': 'filename',
                'needs_translation': filename_lang.lower() != 'english'
            }

        # Default: Assume English
        return {
            'language': 'English',
            'code': 'en',
            'confidence': 0.5,
            'method': 'english_default',
            'needs_translation': False
        }

    def _get_language_code(self, language_name: str) -> str:
        """Get ISO 639-1 language code from language name"""
        language_lower = language_name.lower()

        # Reverse lookup in LANGUAGE_CODES
        for code, name in self.LANGUAGE_CODES.items():
            if name.lower() == language_lower:
                return code

        # Common special cases
        if language_lower in ['русский', 'russian']:
            return 'ru'
        elif language_lower in ['español', 'spanish']:
            return 'es'
        elif language_lower in ['français', 'french']:
            return 'fr'

        # Default: Use first 2 letters
        return language_lower[:2]


# Singleton instance
_detector = None


def get_detector() -> LanguageDetector:
    """Get singleton language detector instance"""
    global _detector
    if _detector is None:
        _detector = LanguageDetector()
    return _detector


def detect_language(filepath: Path) -> Dict:
    """
    Convenience function to detect language of a file.

    Args:
        filepath: Path to book file

    Returns:
        Detection results dictionary
    """
    detector = get_detector()
    return detector.detect_language(filepath)


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 2:
        print("Usage: python3 language_detector.py <file_path>")
        sys.exit(1)

    filepath = Path(sys.argv[1])
    if not filepath.exists():
        print(f"❌ File not found: {filepath}")
        sys.exit(1)

    result = detect_language(filepath)

    print("\n" + "="*60)
    print("LANGUAGE DETECTION RESULTS")
    print("="*60)
    print(f"File: {filepath.name}")
    print(f"Language: {result['language']}")
    print(f"Code: {result['code']}")
    print(f"Confidence: {result['confidence']*100:.1f}%")
    print(f"Method: {result['method']}")
    print(f"Needs Translation: {'Yes' if result['needs_translation'] else 'No'}")
    if 'error' in result:
        print(f"Error: {result['error']}")
    print("="*60)
