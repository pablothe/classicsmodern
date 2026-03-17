"""
EPUB to Markdown Converter

Converts EPUB files to clean Markdown for use in the audiobook pipeline.
Extracts HTML content from each EPUB document item, converts it to Markdown
via markdownify, and concatenates into a single output file.

Usage:
    python3 epub_to_md.py <epub_file> <output_directory>

Requires: pip install ebooklib markdownify
"""

import os
import sys

try:
    import ebooklib
    from ebooklib import epub
except ImportError:
    print("Error: ebooklib is required but not installed.")
    print("It uses the AGPL v3 license. Install separately with:")
    print("  pip install ebooklib")
    sys.exit(1)

from bs4 import BeautifulSoup
from markdownify import markdownify

def epub_to_markdown(epub_path, output_dir):
    """Convert an EPUB file to a single Markdown file.

    Reads the EPUB, extracts the title from Dublin Core metadata,
    then iterates over all HTML items converting each to Markdown.

    Args:
        epub_path: Path to the source EPUB file.
        output_dir: Directory where the output .md file will be created.
    """
    # Load the EPUB book
    book = epub.read_epub(epub_path)

    # Get the title of the book
    title = "converted_book"
    for item in book.get_metadata('DC', 'title'):
        title = item[0].replace(" ", "_")

    # Create an output directory
    os.makedirs(output_dir, exist_ok=True)
    
    # Define output markdown file
    output_file = os.path.join(output_dir, f"{title}.md")

    with open(output_file, "w", encoding="utf-8") as md_file:
        for item in book.items:
            if isinstance(item, epub.EpubHtml):
                # Extract HTML content
                soup = BeautifulSoup(item.get_body_content(), "html.parser")
                markdown_text = markdownify(str(soup))

                # Write to markdown file
                md_file.write(markdown_text + "\n\n")

    print(f"Markdown file saved: {output_file}")

# Run the script
if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python epub_to_md.py <epub_file> <output_directory>")
        sys.exit(1)

    epub_file = sys.argv[1]
    output_directory = sys.argv[2]

    if not os.path.exists(epub_file):
        print(f"Error: File '{epub_file}' not found.")
        sys.exit(1)

    epub_to_markdown(epub_file, output_directory)
