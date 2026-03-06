#!/usr/bin/env python3
"""
Book Prompt Generator for Cover Art

Generates Stable Diffusion prompts using an LLM to describe
the main character and environment from actual book content.
Supports Ollama (local), OpenAI, and Anthropic providers.
Falls back to a hardcoded catalog when LLM is unavailable.
All prompts enforce watercolor illustration style.
"""

import logging
import re
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# Offline fallback catalog (used when Ollama is unavailable)
BOOK_PROMPTS_FALLBACK = {
    'alice': 'young girl in blue dress, magical fantasy forest, floating playing cards, Cheshire cat, mushrooms, vibrant dreamlike colors',
    'crime': 'troubled young man in worn coat, dark moody St Petersburg streets, 19th century Russian cityscape, brooding stormy sky',
    'pride': 'elegant young woman in Regency era gown, English countryside manor house, ballroom, soft pastel colors',
    'sherlock': 'tall detective in deerstalker hat with pipe, foggy Victorian London, gaslit Baker Street, sepia mystery atmosphere',
    'moby': 'bearded sea captain on ship deck, massive white whale breaching, dramatic ocean waves, stormy seas',
    'gatsby': 'man in 1920s tuxedo gazing across water, green light, Art Deco mansion party, Jazz Age luxury',
    'war_worlds': 'terrified Victorian man fleeing, alien tripod machines, Martian invasion, apocalyptic London',
    'time_machine': 'Victorian gentleman beside brass time machine, swirling vortex, clockwork gears, steampunk invention',
    'cthulhu': 'horrified sailor on small boat, eldritch tentacled creature emerging from ocean, cosmic horror, dark Gothic sea',
    'quixote': 'thin elderly knight in rusty armor on horseback, windmills in La Mancha landscape, stout companion on donkey',
    'metamorphosis': 'man transforming into giant insect, dark cramped bedroom, existential surrealism, expressionist shadows',
    'zarathustra': 'lone prophet on mountain peak cliff edge, eagle and serpent, dramatic sunrise sky, philosophical solitude',
    'origin': 'Victorian naturalist examining specimens, Galápagos finches, botanical diagrams, evolutionary tree of life',
    'brevitate': 'Roman philosopher in toga, classical marble columns, hourglass, contemplative pose, warm sepia light',
    'winnie': 'small teddy bear with honey pot, gentle woodland scene, Hundred Acre Wood, Christopher Robin, autumn colors',
    'tolstoy': 'Russian aristocrats at grand ballroom, Napoleonic war scene, sweeping winter landscape, 19th century Moscow',
    'jekyll': 'split face man light and shadow, Victorian laboratory with bubbling potions, dark London cobblestone streets',
    'little_women': 'four sisters in Victorian dresses by cozy hearth, 19th century New England home, warm golden light',
}

# Generic watercolor fallback when book is unknown AND Ollama is down
GENERIC_FALLBACK = "watercolor illustration, classic literature scene, elegant character portrait, soft flowing brushstrokes, professional book cover"


def _read_excerpt_from_middle(filepath: Path, target_words: int = 30) -> str:
    """
    Read ~30 words from the middle of a book file.

    Reads from the midpoint to avoid Gutenberg headers, metadata,
    and mixed-language frontmatter that often appears at the start.

    Args:
        filepath: Path to book markdown file
        target_words: Approximate number of words to extract

    Returns:
        Excerpt string, or empty string if file can't be read
    """
    try:
        file_size = filepath.stat().st_size
        midpoint = file_size // 2

        with open(filepath, 'r', encoding='utf-8') as f:
            f.seek(midpoint)
            # Read enough to get ~30 words (rough estimate: 8 chars/word)
            raw = f.read(target_words * 10)

        # Clean: skip partial first line, strip markdown artifacts
        lines = raw.split('\n')
        if len(lines) > 1:
            lines = lines[1:]  # Drop partial first line
        text = ' '.join(lines)
        text = re.sub(r'[#*_\[\]()>`|]', '', text)  # Strip markdown
        text = re.sub(r'\s+', ' ', text).strip()

        # Extract target_words words
        words = text.split()[:target_words]
        return ' '.join(words)
    except Exception as e:
        logger.warning(f"Could not read excerpt from {filepath}: {e}")
        return ""


def _get_default_llm():
    """Get the default LLM provider from config."""
    try:
        from lib.config import create_default_llm
        return create_default_llm()
    except Exception:
        return None


def _generate_prompt_with_llm(excerpt: str, llm=None) -> str:
    """
    Ask an LLM to describe the main character and environment from a book excerpt.

    Args:
        excerpt: ~30 words from the middle of the book
        llm: Optional LLMProvider instance. If None, uses default from config.

    Returns:
        Comma-separated visual descriptors, or empty string on failure
    """
    prompt = (
        "Translate this book excerpt into a description of how you would illustrate "
        "the main character on a book cover. Start with the character's name, then describe "
        "what makes them visually distinctive: their defining features, clothing, expression, "
        "posture, and the setting around them. "
        "Output ONLY comma-separated visual descriptors.\n"
        "Example: Sherlock Holmes, gaunt detective in deerstalker cap, sharp piercing eyes, "
        "magnifying glass, long coat, foggy gaslit London alley, mysterious shadows\n\n"
        f"Excerpt:\n{excerpt}"
    )

    try:
        if llm is None:
            llm = _get_default_llm()

        if llm:
            descriptors = llm.generate(prompt, temperature=0.7, timeout=60)
        else:
            # Direct Ollama fallback when no provider is configured
            from lib.config import get_config
            config = get_config()
            payload = {
                "model": config.models.default_translation_model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.7}
            }
            response = requests.post(
                f"{config.models.ollama_host}/api/generate",
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            descriptors = response.json().get('response', '').strip()

        # Clean up: remove any sentence-like output, keep comma-separated descriptors
        descriptors = descriptors.strip('"\'')

        # Filter garbage responses (translator model sometimes treats input as translation task)
        garbage_phrases = ['translate', 'translation', 'provide the text', 'please provide', 'i cannot']
        if any(phrase in descriptors.lower() for phrase in garbage_phrases):
            logger.warning(f"LLM returned garbage for cover prompt, falling back")
            return ""

        if descriptors:
            logger.info(f"LLM generated cover descriptors: {descriptors[:100]}...")
            return descriptors
    except requests.ConnectionError:
        logger.warning("LLM not available for cover prompt generation")
    except Exception as e:
        logger.warning(f"LLM cover prompt generation failed: {e}")

    return ""


def _resolve_book_path(title_or_filename: str) -> Path:
    """
    Try to resolve a book file path from the input string.

    Handles:
    - Direct file paths: "books/alice_adventures/book.md"
    - Book IDs: "alice_adventures"
    - Titles: "Alice in Wonderland"

    Returns:
        Path to book file, or None if not found
    """
    # Direct path
    path = Path(title_or_filename)
    if path.exists() and path.is_file():
        return path

    # Try as book_id under books/ directory
    project_root = Path(__file__).parent.parent.parent
    books_dir = project_root / "books"

    # Direct book_id match
    book_dir = books_dir / title_or_filename
    if book_dir.exists():
        book_file = book_dir / "book.md"
        if book_file.exists():
            return book_file

    # Search for matching book directory
    text_lower = title_or_filename.lower()
    if books_dir.exists():
        for d in sorted(books_dir.iterdir()):
            if d.is_dir() and text_lower in d.name.lower():
                book_file = d / "book.md"
                if book_file.exists():
                    return book_file

    return None


def get_book_prompt(title_or_filename: str, llm=None) -> str:
    """
    Generate a Stable Diffusion prompt for a book cover.

    Uses an LLM to read ~30 words from the middle of the book and
    describe the main character and environment. Falls back to a hardcoded
    catalog if LLM is unavailable.

    All prompts enforce watercolor illustration style.

    Args:
        title_or_filename: Book file path, book ID, or title
        llm: Optional LLMProvider instance. If None, uses default from config.

    Returns:
        Stable Diffusion prompt string (always includes watercolor style)
    """
    # Try to read from the actual book and generate with LLM
    book_path = _resolve_book_path(title_or_filename)
    if book_path:
        excerpt = _read_excerpt_from_middle(book_path)
        if excerpt:
            descriptors = _generate_prompt_with_llm(excerpt, llm=llm)
            if descriptors:
                return f"watercolor illustration, {descriptors}, soft flowing brushstrokes, professional book cover"

    # Fallback: hardcoded catalog (offline mode)
    text = title_or_filename.lower()
    for key, descriptors in BOOK_PROMPTS_FALLBACK.items():
        if key in text:
            return f"watercolor illustration, {descriptors}, soft flowing brushstrokes, professional book cover"

    # Last resort: generic watercolor prompt
    return GENERIC_FALLBACK


def detect_language_with_llm(filepath: Path, llm=None) -> str:
    """
    Use an LLM to detect the language of a book by reading ~30 words
    from the middle of the file.

    Args:
        filepath: Path to book file
        llm: Optional LLMProvider instance. If None, uses default from config.

    Returns:
        Language name (e.g., "English", "Latin", "French"), or empty string on failure
    """
    excerpt = _read_excerpt_from_middle(filepath)
    if not excerpt:
        return ""

    prompt = (
        "What language is this text written in? Reply with ONLY the language name "
        "(e.g., English, French, Latin, German, Spanish, Italian, Russian, Greek).\n\n"
        f"Text:\n{excerpt}"
    )

    try:
        if llm is None:
            llm = _get_default_llm()

        if llm:
            language = llm.generate(prompt, temperature=0.1, timeout=30)
        else:
            # Direct Ollama fallback
            from lib.config import get_config
            config = get_config()
            payload = {
                "model": config.models.default_translation_model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1}
            }
            response = requests.post(
                f"{config.models.ollama_host}/api/generate",
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            language = response.json().get('response', '').strip()

        # Clean up: take first word only (model might add explanation)
        language = language.split('\n')[0].strip().rstrip('.')
        # Remove any trailing explanation
        if '(' in language:
            language = language[:language.index('(')].strip()

        if language:
            logger.info(f"LLM detected language: {language}")
            return language
    except Exception as e:
        logger.warning(f"LLM language detection failed: {e}")

    return ""


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python prompts.py <book_path_or_title>")
        print("\nExamples:")
        print("  python prompts.py books/alice_adventures/book.md")
        print("  python prompts.py alice_adventures")
        print("  python prompts.py 'Alice in Wonderland'")
        sys.exit(1)

    prompt = get_book_prompt(sys.argv[1])
    print(f"\nGenerated prompt:\n{prompt}")
