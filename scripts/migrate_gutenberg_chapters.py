#!/usr/bin/env python3
"""
Migrate gutenberg_chapters.json files from v1.0 to v2.0 format.

For each book with a v1.0 gutenberg_chapters.json:
1. Scans book.md for ## headers to populate header_line_number
2. Classifies front matter sections (prologue, preface, dedication, etc.)
3. Builds hierarchy for parts/books/volumes
4. Uses sequential ordinals instead of parsed numbers
5. Sets review_status to 'needs_review'

Usage:
    python3 scripts/migrate_gutenberg_chapters.py books/          # Migrate all
    python3 scripts/migrate_gutenberg_chapters.py books/ --dry-run  # Preview only
    python3 scripts/migrate_gutenberg_chapters.py books/alice_adventures/  # Single book
"""

import json
import re
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from server.gutenberg_downloader import GutenbergDownloader


def migrate_book(book_dir: Path, dry_run: bool = False) -> dict:
    """Migrate a single book's gutenberg_chapters.json to v2.0.

    Returns dict with migration status and details.
    """
    gutenberg_json = book_dir / "gutenberg_chapters.json"
    book_md = book_dir / "book.md"

    if not gutenberg_json.exists():
        return {'status': 'skipped', 'reason': 'no gutenberg_chapters.json'}

    with open(gutenberg_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    version = data.get('version', '1.0')
    if version == '2.0':
        return {'status': 'skipped', 'reason': 'already v2.0'}

    chapters = data.get('chapters', [])
    if not chapters:
        return {'status': 'skipped', 'reason': 'no chapters'}

    # Read book.md to find ## header line numbers
    md_text = ''
    md_lines = []
    if book_md.exists():
        with open(book_md, 'r', encoding='utf-8') as f:
            md_text = f.read()
        md_lines = md_text.split('\n')

    # Collect all ## headers from book.md with their line numbers
    header_entries = []
    for i, line in enumerate(md_lines):
        stripped = line.strip()
        m = re.match(r'^##\s+(.+)', stripped)
        if m:
            header_text = m.group(1).strip()
            # Skip metadata headers
            skip = {'contents', 'table of contents', 'copyright', 'about the author',
                    'acknowledgements', 'acknowledgments', 'colophon', 'bibliography',
                    'footnotes', 'endnotes', 'glossary', 'index', 'notes'}
            if header_text.lower() in skip:
                continue
            if header_text.lower().startswith('by '):
                continue
            if re.match(r'^\[.*\]\(#', header_text):
                continue
            header_entries.append({
                'line_num': i,
                'raw_line': stripped,
                'header_text': header_text,
                'normalized': re.sub(r'\s+', ' ', header_text).strip().lower()
            })

    # Build v2.0 chapters by matching v1.0 entries to ## headers
    downloader = GutenbergDownloader()
    new_chapters = []
    matched_headers = set()

    for i, old_ch in enumerate(chapters):
        old_title = old_ch.get('title', '')
        clean_title = downloader._clean_toc_title(old_title)
        section_type = downloader._classify_section_type(clean_title)

        # Override with existing section_type if reasonable
        existing_type = old_ch.get('section_type', 'chapter')
        if existing_type != 'chapter':
            section_type = existing_type

        # Try to find matching ## header
        header_line_number = None
        markdown_header = None
        norm_title = re.sub(r'\s+', ' ', clean_title).strip().lower()

        # Strategy 1: Exact match
        for he in header_entries:
            if he['line_num'] in matched_headers:
                continue
            if norm_title == he['normalized'] or clean_title.lower() == he['header_text'].lower():
                header_line_number = he['line_num']
                markdown_header = he['raw_line']
                matched_headers.add(he['line_num'])
                break

        # Strategy 2: Substring match
        if header_line_number is None and len(norm_title) > 5:
            for he in header_entries:
                if he['line_num'] in matched_headers:
                    continue
                if norm_title in he['normalized'] or he['normalized'] in norm_title:
                    header_line_number = he['line_num']
                    markdown_header = he['raw_line']
                    matched_headers.add(he['line_num'])
                    break

        ch_entry = {
            'ordinal': i + 1,
            'title': clean_title,
            'section_type': section_type,
        }
        if header_line_number is not None:
            ch_entry['header_line_number'] = header_line_number
            ch_entry['markdown_header'] = markdown_header

        new_chapters.append(ch_entry)

    # Position-filling: assign remaining headers by order
    unmatched_ch = [i for i, ch in enumerate(new_chapters) if 'header_line_number' not in ch]
    unmatched_he = sorted([he for he in header_entries if he['line_num'] not in matched_headers],
                          key=lambda x: x['line_num'])

    for ch_idx, he in zip(unmatched_ch, unmatched_he):
        new_chapters[ch_idx]['header_line_number'] = he['line_num']
        new_chapters[ch_idx]['markdown_header'] = he['raw_line']

    # Build front_matter
    front_matter_types = {'prologue', 'preface', 'foreword', 'introduction', 'dedication'}
    fm_sections = [
        {'title': ch['title'], 'section_type': ch['section_type']}
        for ch in new_chapters if ch['section_type'] in front_matter_types
    ]
    front_matter = {
        'has_prologue': any(s['section_type'] == 'prologue' for s in fm_sections),
        'has_preface': any(s['section_type'] in ('preface', 'foreword') for s in fm_sections),
        'has_dedication': any(s['section_type'] == 'dedication' for s in fm_sections),
        'has_introduction': any(s['section_type'] == 'introduction' for s in fm_sections),
        'sections': fm_sections
    }

    # Build hierarchy
    parent_types = {'part', 'book', 'volume'}
    hierarchy = []
    parent_indices = [i for i, ch in enumerate(new_chapters) if ch['section_type'] in parent_types]
    for pi, parent_idx in enumerate(parent_indices):
        parent = new_chapters[parent_idx]
        child_start = parent_idx + 1
        child_end = parent_indices[pi + 1] - 1 if pi + 1 < len(parent_indices) else len(new_chapters) - 1
        hierarchy.append({
            'type': parent['section_type'],
            'title': parent['title'],
            'ordinal': parent['ordinal'],
            'children_range': [child_start, child_end]
        })

    # Determine review status
    review_status = 'needs_review'
    matched_count = sum(1 for ch in new_chapters if 'header_line_number' in ch)
    if matched_count == len(new_chapters) and len(new_chapters) <= 50:
        review_status = 'auto'

    # Get gutenberg_id from metadata if available
    gutenberg_id = None
    meta_path = book_dir / "gutenberg_metadata.json"
    if meta_path.exists():
        with open(meta_path, 'r', encoding='utf-8') as f:
            meta = json.load(f)
        gutenberg_id = meta.get('gutenberg_id')

    new_data = {
        'version': '2.0',
        'source': 'migrated_from_v1',
        'review_status': review_status,
        'chapter_count': len(new_chapters),
        'front_matter': front_matter,
        'hierarchy': hierarchy,
        'chapters': new_chapters
    }
    if gutenberg_id:
        new_data['gutenberg_id'] = gutenberg_id

    result = {
        'status': 'migrated',
        'book': book_dir.name,
        'chapters': len(new_chapters),
        'matched_headers': matched_count,
        'total_headers': len(header_entries),
        'review_status': review_status,
        'front_matter': bool(fm_sections),
        'hierarchy': bool(hierarchy),
    }

    if not dry_run:
        with open(gutenberg_json, 'w', encoding='utf-8') as f:
            json.dump(new_data, f, indent=2, ensure_ascii=False)

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/migrate_gutenberg_chapters.py <path> [--dry-run]")
        sys.exit(1)

    target = Path(sys.argv[1])
    dry_run = '--dry-run' in sys.argv

    if not target.exists():
        print(f"Path not found: {target}")
        sys.exit(1)

    if dry_run:
        print("DRY RUN - no files will be modified\n")

    # Determine if target is a single book or parent directory
    if (target / "gutenberg_chapters.json").exists():
        book_dirs = [target]
    else:
        book_dirs = sorted([d for d in target.iterdir() if d.is_dir()])

    stats = {'migrated': 0, 'skipped': 0, 'errors': 0}

    for book_dir in book_dirs:
        try:
            result = migrate_book(book_dir, dry_run)
            status = result['status']

            if status == 'migrated':
                stats['migrated'] += 1
                matched = result['matched_headers']
                total = result['chapters']
                flag = ' !' if result['review_status'] == 'needs_review' else ''
                fm = ' [fm]' if result['front_matter'] else ''
                hier = ' [hier]' if result['hierarchy'] else ''
                print(f"  + {book_dir.name:<45} {matched}/{total} matched{fm}{hier}{flag}")
            elif status == 'skipped':
                stats['skipped'] += 1
                if result.get('reason') != 'no gutenberg_chapters.json':
                    print(f"  - {book_dir.name:<45} {result.get('reason', '')}")
        except Exception as e:
            stats['errors'] += 1
            print(f"  ! {book_dir.name:<45} ERROR: {e}")

    print(f"\nResults:")
    print(f"  Migrated:  {stats['migrated']}")
    print(f"  Skipped:   {stats['skipped']}")
    print(f"  Errors:    {stats['errors']}")

    if dry_run:
        print("\n  (dry run - no files were modified)")


if __name__ == '__main__':
    main()
