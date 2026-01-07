#!/usr/bin/env python3
"""
Book Prompt Generator for Cover Art

Simple, modular utility to generate Stable Diffusion prompts for classic books.
Can be imported or used standalone.
"""

# Book catalog with detailed visual descriptions
BOOK_PROMPTS = {
    'alice': 'whimsical dreamlike scene, surreal fantasy forest, floating playing cards, mysterious Cheshire cat, magical mushrooms, vibrant colors, Victorian girl in blue dress, fantasy illustration, storybook art, professional book cover',
    'crime': 'dark moody Russian cityscape, St Petersburg architecture, psychological thriller, noir atmosphere, dramatic shadows, 19th century, brooding atmosphere, literary masterpiece, professional book cover',
    'pride': 'elegant Regency era ballroom, period drama, romantic English countryside, manor houses, Georgian architecture, soft pastel colors, classic romance, Jane Austen elegance, professional book cover',
    'sherlock': 'Victorian London fog, detective with deerstalker hat and pipe, gaslit streets, Baker Street, mystery noir, magnifying glass, vintage detective illustration, professional book cover',
    'moby': 'epic maritime adventure, massive white whale breaching, 19th century whaling ship, dramatic ocean waves, nautical theme, stormy seas, literary epic, professional book cover',
    'gatsby': 'Art Deco elegance, 1920s Jazz Age, lavish mansion party, champagne and luxury, green light across water, flapper era, gold and turquoise, American Dream, professional book cover',
    'war_worlds': 'sci-fi Victorian era, alien tripod machines, Martian invasion, retro-futuristic, steampunk aesthetic, apocalyptic London, H.G. Wells classic, professional book cover',
    'time_machine': 'Victorian steampunk time machine, brass and copper mechanisms, swirling time vortex, retro-futuristic invention, gears and clockwork, science fiction pioneer, professional book cover',
    'cthulhu': 'cosmic horror, eldritch tentacled creature emerging from ocean, dark Gothic atmosphere, Lovecraftian horror, misty deep sea, unspeakable terror, pulp horror illustration, professional book cover',
    'quixote': 'Spanish knight on horseback, windmills in La Mancha landscape, medieval armor, Sancho Panza companion, classic Spanish literature, chivalric romance, tilting at windmills, professional book cover',
    'metamorphosis': 'surreal transformation, man becoming insect, existential dread, Kafkaesque surrealism, dark bedroom interior, psychological horror, expressionist art, literary modernism, professional book cover',
    'zarathustra': 'philosophical mountain peak, lone prophet on cliff edge, dramatic sky, übermensch symbolism, German philosophy, eagle and serpent, existential journey, dramatic sunrise, professional book cover',
    'origin': 'evolutionary tree of life, Galápagos finches, natural history illustration, Victorian scientific diagrams, Charles Darwin, biological evolution, scientific revolution, professional book cover',
    'brevitate': 'ancient Roman philosophy, Stoic wisdom, classical marble columns, hourglass symbolism, Latin manuscript, philosophical contemplation, Roman senator, timeless wisdom, professional book cover',
    'winnie': 'gentle watercolor children\'s illustration, Hundred Acre Wood, teddy bear with honey pot, Christopher Robin, classic storybook art, warm autumn colors, nostalgic childhood, professional book cover',
    'tolstoy': 'epic Russian historical drama, Napoleonic wars, grand ballroom scenes, Russian aristocracy, sweeping winter landscapes, 19th century Moscow, literary masterpiece, professional book cover',
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
