#!/usr/bin/env python3
"""
Book Prompt Generator for Cover Art

Simple, modular utility to generate Stable Diffusion prompts for classic books.
Can be imported or used standalone.
"""

# Book catalog with detailed visual descriptions (ALL WATERCOLOR STYLE)
BOOK_PROMPTS = {
    'alice': 'watercolor illustration, whimsical dreamlike scene, surreal fantasy forest, floating playing cards, mysterious Cheshire cat, magical mushrooms, soft vibrant colors, Victorian girl in blue dress, flowing brushstrokes, fantasy storybook art, professional book cover',
    'crime': 'watercolor illustration, dark moody Russian cityscape, St Petersburg architecture, psychological thriller atmosphere, dramatic shadows, 19th century, brooding stormy sky, muted earth tones, literary masterpiece, professional book cover',
    'pride': 'watercolor illustration, elegant Regency era ballroom, period drama, romantic English countryside, manor houses, Georgian architecture, soft pastel colors, delicate brushwork, classic romance, Jane Austen elegance, professional book cover',
    'sherlock': 'watercolor illustration, Victorian London fog, detective with deerstalker hat and pipe, gaslit streets, Baker Street, mystery atmosphere, sepia tones, vintage detective scene, soft edges, professional book cover',
    'moby': 'watercolor illustration, epic maritime adventure, massive white whale breaching, 19th century whaling ship, dramatic ocean waves, nautical theme, stormy seas, blues and grays, literary epic, professional book cover',
    'gatsby': 'watercolor illustration, Art Deco elegance, 1920s Jazz Age, lavish mansion party, champagne and luxury, green light across water, flapper era, gold and turquoise wash, American Dream, flowing watercolor style, professional book cover',
    'war_worlds': 'watercolor illustration, sci-fi Victorian era, alien tripod machines, Martian invasion, retro-futuristic, steampunk aesthetic, apocalyptic London, dramatic washes, H.G. Wells classic, professional book cover',
    'time_machine': 'watercolor illustration, Victorian steampunk time machine, brass and copper mechanisms, swirling time vortex, retro-futuristic invention, gears and clockwork, soft metallic tones, science fiction pioneer, professional book cover',
    'cthulhu': 'watercolor illustration, cosmic horror, eldritch tentacled creature emerging from ocean, dark Gothic atmosphere, Lovecraftian horror, misty deep sea, dark green and purple washes, unspeakable terror, professional book cover',
    'quixote': 'watercolor illustration, Spanish knight on horseback, windmills in La Mancha landscape, medieval armor, Sancho Panza companion, warm Spanish earth tones, classic literature, chivalric romance, soft brushwork, professional book cover',
    'metamorphosis': 'watercolor illustration, surreal transformation, man becoming insect, existential dread, Kafkaesque surrealism, dark bedroom interior, psychological horror, muted colors, expressionist watercolor art, literary modernism, professional book cover',
    'zarathustra': 'watercolor illustration, philosophical mountain peak, lone prophet on cliff edge, dramatic sky, übermensch symbolism, German philosophy, eagle and serpent, existential journey, sunrise wash, flowing clouds, professional book cover',
    'origin': 'watercolor illustration, evolutionary tree of life, Galápagos finches, natural history botanical art, Victorian scientific diagrams, Charles Darwin, biological evolution, earth tones, scientific revolution, professional book cover',
    'brevitate': 'watercolor illustration, ancient Roman philosophy, Stoic wisdom, classical marble columns, hourglass symbolism, Latin manuscript, philosophical contemplation, Roman senator, warm sepia tones, timeless wisdom, professional book cover',
    'winnie': 'watercolor illustration, gentle children\'s storybook art, Hundred Acre Wood, teddy bear with honey pot, Christopher Robin, classic Shepard style, warm autumn colors, soft flowing brushstrokes, nostalgic childhood, professional book cover',
    'tolstoy': 'watercolor illustration, epic Russian historical drama, Napoleonic wars, grand ballroom scenes, Russian aristocracy, sweeping winter landscapes, 19th century Moscow, cold blues and whites, literary masterpiece, professional book cover',
}


def get_book_prompt(title_or_filename: str) -> str:
    """
    Get Stable Diffusion prompt for a book based on title/filename.

    Args:
        title_or_filename: Book title or filename

    Returns:
        Stable Diffusion prompt string
    """
    text = title_or_filename.lower()

    # Match against known books
    for key, prompt in BOOK_PROMPTS.items():
        if key in text:
            return f"Book cover art, {prompt}"

    # Fallback for unknown books
    return "Book cover art, classic literature, elegant typography, timeless design, literary masterpiece, professional book cover, sophisticated illustration"


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python book_prompts.py <book_title_or_filename>")
        print("\nExamples:")
        print("  python book_prompts.py 'Alice in Wonderland'")
        print("  python book_prompts.py books/moby_dick/translated.md")
        sys.exit(1)

    prompt = get_book_prompt(sys.argv[1])
    print(prompt)
