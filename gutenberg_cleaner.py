#!/usr/bin/env python3
"""
Project Gutenberg Book Cleaner and Chapter Indexer
Removes Gutenberg headers/footers and generates clean chapter indices.
"""

import os
import re
import argparse
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def remove_gutenberg_header(text):
    """
    Remove Project Gutenberg header up to the *** START *** marker.
    """
    # Find the start marker
    start_patterns = [
        r'\*\*\* START OF (?:THE )?PROJECT GUTENBERG EBOOK .+ \*\*\*',
        r'\*\*\* START OF (?:THE )?PROJECT GUTENBERG .+ \*\*\*',
        r'\*\*_ START OF (?:THE )?PROJECT GUTENBERG EBOOK .+ _\*\*'
    ]
    
    for pattern in start_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # Keep everything after the start marker
            return text[match.end():].lstrip()
    
    # If no start marker found, try to find the actual book title
    # Look for a line that's likely the book title (after Gutenberg metadata)
    lines = text.split('\n')
    for i, line in enumerate(lines):
        # Skip empty lines and Gutenberg metadata
        if (line.strip() and 
            not line.startswith('##') and 
            'Project Gutenberg' not in line and
            'This ebook is for the use' not in line and
            'Release date:' not in line and
            'Language:' not in line and
            'Credits:' not in line and
            'Author:' not in line and
            'Title:' not in line and
            'www.gutenberg.org' not in line and
            not re.match(r'^\s*$', line)):
            
            # Check if this looks like a book title
            if (len(line.strip()) > 5 and 
                (line.startswith('#') or 
                 line.isupper() or 
                 any(word in line.lower() for word in ['by', 'chapter', 'contents']))):
                return '\n'.join(lines[i:])
    
    return text

def remove_gutenberg_footer(text):
    """
    Remove Project Gutenberg footer from the *** END *** marker onwards.
    """
    # Find the end marker
    end_patterns = [
        r'\*\*\* END OF (?:THE )?PROJECT GUTENBERG EBOOK .+ \*\*\*',
        r'\*\*\* END OF (?:THE )?PROJECT GUTENBERG .+ \*\*\*',
        r'\*\*_ END OF (?:THE )?PROJECT GUTENBERG EBOOK .+ _\*\*'
    ]
    
    for pattern in end_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return text[:match.start()].rstrip()
    
    # If no end marker, look for common footer patterns
    footer_patterns = [
        r'Section \d+\.\s+Information about the Project Gutenberg',
        r'Project Gutenberg™ depends upon and cannot survive',
        r'Please check the Project Gutenberg web pages',
        r'Most people start at our website which has the main PG search'
    ]
    
    for pattern in footer_patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            # Find the start of the paragraph containing this pattern
            lines = text[:match.start()].split('\n')
            # Remove empty lines from the end
            while lines and not lines[-1].strip():
                lines.pop()
            return '\n'.join(lines)
    
    return text

def extract_title_and_author(text):
    """
    Extract the book title and author from the cleaned text.
    """
    lines = text.split('\n')
    title = None
    author = None
    
    for i, line in enumerate(lines[:30]):  # Check first 30 lines
        line = line.strip()
        if not line:
            continue
            
        # Look for title (usually the first substantial heading)
        if not title and line.startswith('#'):
            title_candidate = re.sub(r'^#+\s*', '', line).strip()
            # Clean up title
            if 'by' in title_candidate.lower():
                # Split title and author if they're on the same line
                parts = re.split(r'\s+by\s+', title_candidate, flags=re.IGNORECASE)
                if len(parts) == 2:
                    title = parts[0].strip()
                    author = parts[1].strip()
                else:
                    title = title_candidate
            else:
                title = title_candidate
        elif not title and (line.isupper() or (len(line) > 10 and len(line) < 100)):
            # Check if this looks like a title
            if not any(word in line.lower() for word in ['chapter', 'contents', 'by', 'author', 'table']):
                title = line
        
        # Look for author patterns
        if not author:
            # Direct "by Author" pattern
            if 'by ' in line.lower() and len(line) < 100:
                author_match = re.search(r'by\s+([^,\n\r]+)', line, re.IGNORECASE)
                if author_match:
                    author = author_match.group(1).strip()
            # Author might be on the line after title
            elif title and i > 0 and i < 10:
                if (line and len(line) < 50 and len(line) > 3 and
                    not line.startswith('#') and 
                    'chapter' not in line.lower() and
                    'contents' not in line.lower() and
                    'table' not in line.lower() and
                    not line.isdigit()):
                    # Check if this looks like an author name
                    if re.match(r'^[A-Z][a-z]+ [A-Z][a-z]+', line) or any(name in line for name in ['Scott', 'Wells', 'Melville', 'Austen', 'Doyle']):
                        author = line
    
    # Clean up title
    if title:
        # Remove extra whitespace and fix common issues
        title = re.sub(r'\s+', ' ', title).strip()
        # Remove trailing punctuation like periods or semicolons at the end
        title = re.sub(r'[;,.]$', '', title)
    
    return title, author

def detect_chapters(text):
    """
    Detect chapter patterns and extract chapter information.
    Returns list of (chapter_number, chapter_title, line_number) tuples.
    """
    # Clean up "end chapter" markers that might interfere
    text = re.sub(r'end chapter', '', text, flags=re.IGNORECASE)
    
    lines = text.split('\n')
    chapters = []
    
    # Roman numeral mapping
    roman_to_int = {
        'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6, 'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10,
        'XI': 11, 'XII': 12, 'XIII': 13, 'XIV': 14, 'XV': 15, 'XVI': 16, 'XVII': 17, 'XVIII': 18, 'XIX': 19, 'XX': 20
    }
    
    # First, check for content lines that have multiple chapters run together
    for i, line in enumerate(lines):
        # Look for lines with multiple Roman numeral chapters like "I[Title](#chap01)II[Title](#chap02)"
        if re.search(r'[IVX]+\[.+?\]\(#chap\d+\)', line):
            # Extract individual chapters from this line
            chapter_matches = re.finditer(r'([IVX]+)\[([^\]]+)\]\(#chap\d+\)', line)
            for match in chapter_matches:
                roman_num = match.group(1)
                title = match.group(2)
                if roman_num in roman_to_int:
                    chapters.append((roman_to_int[roman_num], title, i + 1))
    
    # If we found chapters in contents, don't continue with line-by-line detection
    if chapters:
        chapters.sort(key=lambda x: x[0])
        return chapters
    
    # Chapter patterns to look for
    chapter_patterns = [
        r'^###?\s+CHAPTER\s+(\d+)\.?\s*(.*)$',          # ## CHAPTER 1. Title
        r'^###?\s+Chapter\s+(\d+)\.?\s*(.*)$',          # ## Chapter 1. Title  
        r'^###?\s+([IVX]+)\.?\s*(.*)$',                 # ## I. Title (Roman numerals)
        r'^###?\s+(\d+)\.?\s*(.*)$',                    # ## 1. Title
        r'^CHAPTER\s+(\d+)\.?\s*(.*)$',                 # CHAPTER 1. Title (no #)
        r'^Chapter\s+(\d+)\.?\s*(.*)$',                 # Chapter 1. Title (no #)
        r'^###?\s+([IVX]+)\.([^#\n]+)$',                # ## I.Title (Roman with period)
        r'^([IVX]+)\.([^#\n]+)$',                       # I.Title (Roman with period, no #)
        r'^###?\s+([IVX]+)\.([A-Z][^#\n]+)$',           # ## I.TITLE (Roman with period, uppercase)
        r'^###?\s+([IVX]+)\.?\s*$',                     # ### I. (Roman only, title on next line)
        r'^([IVX]+)\.?\s*$',                            # I. (Roman only, title on next line)
        r'^(\d+)\.\s+(.+)$',                            # 1. Title (number with period and title)
        r'^(\d+)\.?\s*$'                                # 1. (Number only, title on next line)
    ]
    
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
            
        for pattern in chapter_patterns:
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                chapter_num_str = match.group(1)
                chapter_title = match.group(2).strip() if len(match.groups()) > 1 and match.group(2) else ""
                
                # Convert roman numerals to integers
                if chapter_num_str.upper() in roman_to_int:
                    chapter_num = roman_to_int[chapter_num_str.upper()]
                else:
                    try:
                        chapter_num = int(chapter_num_str)
                    except ValueError:
                        continue
                
                # If no title and this is just a number/roman, check next line
                if not chapter_title and i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and not next_line.startswith('#') and len(next_line) < 100 and len(next_line) > 2:
                        chapter_title = next_line
                
                chapters.append((chapter_num, chapter_title, i + 1))
                break
    
    # Sort chapters by number to ensure proper order
    chapters.sort(key=lambda x: x[0])
    
    # Remove duplicates (sometimes chapters appear in TOC and then again in text)
    seen_chapters = set()
    unique_chapters = []
    for chapter in chapters:
        if chapter[0] not in seen_chapters:
            seen_chapters.add(chapter[0])
            unique_chapters.append(chapter)
    
    return unique_chapters

def create_chapter_index(chapters, title=None):
    """
    Create a clean table of contents from detected chapters.
    """
    if not chapters:
        return ""
    
    index_lines = ["## Table of Contents", ""]
    
    for chapter_num, chapter_title, _ in chapters:
        if chapter_title:
            index_lines.append(f"{chapter_num}. [Chapter {chapter_num}: {chapter_title}](#chapter-{chapter_num})")
        else:
            index_lines.append(f"{chapter_num}. [Chapter {chapter_num}](#chapter-{chapter_num})")
    
    index_lines.extend(["", "---", ""])
    return '\n'.join(index_lines)

def add_chapter_anchors(text, chapters):
    """
    Add anchor tags to chapter headings for navigation.
    """
    lines = text.split('\n')
    
    for chapter_num, chapter_title, line_num in chapters:
        if line_num <= len(lines):
            original_line = lines[line_num - 1]
            
            # Check if line already has an anchor
            if '{#chapter-' not in original_line:
                # Add anchor to the chapter heading
                if original_line.startswith('#'):
                    # It's already a markdown heading
                    lines[line_num - 1] = f"{original_line} {{#chapter-{chapter_num}}}"
                else:
                    # Convert to markdown heading
                    if chapter_title:
                        lines[line_num - 1] = f"## Chapter {chapter_num}: {chapter_title} {{#chapter-{chapter_num}}}"
                    else:
                        lines[line_num - 1] = f"## Chapter {chapter_num} {{#chapter-{chapter_num}}}"
    
    return '\n'.join(lines)

def clean_and_format_text(text):
    """
    General text cleanup and formatting improvements.
    """
    # Remove excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Fix spacing around headers
    text = re.sub(r'\n(#{1,6}[^\n]+)\n(?!\n)', r'\n\n\1\n\n', text)
    
    # Remove any remaining Gutenberg references
    gutenberg_patterns = [
        r'This ebook is for the use of anyone anywhere[^\n]*\n',
        r'You may copy it, give it away[^\n]*\n',
        r'at\s*www\.gutenberg\.org[^\n]*\n',
        r'Release date:[^\n]*\n',
        r'Language:[^\n]*\n',
        r'Credits:[^\n]*\n'
    ]
    
    for pattern in gutenberg_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    # Clean up any malformed headers
    text = re.sub(r'^(#{1,6})\s*(.+?)\s*$', r'\1 \2', text, flags=re.MULTILINE)
    
    return text.strip()

def process_book(input_file, output_file=None, preserve_original=True):
    """
    Process a single Project Gutenberg book file.
    """
    input_path = Path(input_file)
    
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")
    
    # Read the original file
    with open(input_path, 'r', encoding='utf-8') as f:
        original_text = f.read()
    
    logging.info(f"Processing: {input_path.name}")
    
    # Clean the text
    text = remove_gutenberg_header(original_text)
    text = remove_gutenberg_footer(text)
    
    # Extract title and author
    title, author = extract_title_and_author(text)
    logging.info(f"Detected - Title: {title}, Author: {author}")
    
    # Detect chapters
    chapters = detect_chapters(text)
    logging.info(f"Found {len(chapters)} chapters")
    
    if chapters:
        for chapter_num, chapter_title, _ in chapters[:5]:  # Show first 5
            logging.info(f"  Chapter {chapter_num}: {chapter_title}")
    
    # Create the cleaned book
    cleaned_text = clean_and_format_text(text)
    
    # Add chapter anchors
    if chapters:
        cleaned_text = add_chapter_anchors(cleaned_text, chapters)
    
    # Create the final document
    final_lines = []
    
    # Add title
    if title:
        final_lines.append(f"# {title}")
        if author:
            final_lines.append(f"**by {author}**")
        final_lines.extend(["", "---", ""])
    
    # Add table of contents
    if chapters:
        index = create_chapter_index(chapters, title)
        final_lines.append(index)
    
    # Add the main content
    final_lines.append(cleaned_text)
    
    final_text = '\n'.join(final_lines)
    
    # Determine output file
    if not output_file:
        output_file = input_path.parent / f"{input_path.stem}_cleaned.md"
    
    # Write the cleaned file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(final_text)
    
    logging.info(f"Cleaned file saved to: {output_file}")
    
    # Optionally preserve original with _original suffix
    if preserve_original:
        original_backup = input_path.parent / f"{input_path.stem}_original.md"
        if not original_backup.exists():
            with open(original_backup, 'w', encoding='utf-8') as f:
                f.write(original_text)
            logging.info(f"Original preserved as: {original_backup}")
    
    return output_file, len(chapters)

def main():
    parser = argparse.ArgumentParser(description='Clean Project Gutenberg books and generate chapter indices')
    parser.add_argument('input', nargs='?', help='Input file or directory to process')
    parser.add_argument('--output', '-o', help='Output file (for single file) or directory')
    parser.add_argument('--recursive', '-r', action='store_true', help='Process all .md files in directory recursively')
    parser.add_argument('--no-preserve', action='store_true', help='Do not preserve original files')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be processed without making changes')
    
    args = parser.parse_args()
    
    if not args.input:
        # Process all books in the current books directory
        books_dir = Path('books')
        if books_dir.exists():
            args.input = str(books_dir)
            args.recursive = True
        else:
            parser.error("No input specified and no 'books' directory found")
    
    input_path = Path(args.input)
    
    if input_path.is_file():
        # Process single file
        if args.dry_run:
            print(f"Would process: {input_path}")
            return
        
        try:
            output_file, chapter_count = process_book(
                args.input, 
                args.output, 
                preserve_original=not args.no_preserve
            )
            print(f"✅ Processed {input_path.name} -> {chapter_count} chapters found")
        except Exception as e:
            logging.error(f"Error processing {input_path}: {e}")
    
    elif input_path.is_dir():
        # Process directory
        if args.recursive:
            pattern = '**/*.md'
        else:
            pattern = '*.md'
        
        md_files = list(input_path.glob(pattern))
        
        # Filter out already cleaned files and originals
        md_files = [f for f in md_files if not f.name.endswith('_cleaned.md') and not f.name.endswith('_original.md')]
        
        if not md_files:
            print(f"No markdown files found in {input_path}")
            return
        
        print(f"Found {len(md_files)} files to process")
        
        if args.dry_run:
            for file in md_files:
                print(f"Would process: {file}")
            return
        
        successful = 0
        for file in md_files:
            try:
                output_file, chapter_count = process_book(
                    str(file), 
                    preserve_original=not args.no_preserve
                )
                print(f"✅ {file.name} -> {chapter_count} chapters")
                successful += 1
            except Exception as e:
                print(f"❌ {file.name} -> Error: {e}")
                logging.error(f"Error processing {file}: {e}")
        
        print(f"\n🎉 Successfully processed {successful}/{len(md_files)} files")
    
    else:
        parser.error(f"Input path does not exist: {args.input}")

if __name__ == "__main__":
    main()