#!/usr/bin/env python3
"""
Test book_processor.py on all books in the collection.

This script processes all existing books to validate that:
1. Chapter detection works for various formats
2. TOC generation is successful
3. Gutenberg boilerplate is properly removed
4. The processor handles edge cases
"""

import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List
from lib.book.processor import BookProcessor, BookManifest


def test_all_books(books_dir: Path = Path("books"), verbose: bool = False) -> Dict:
    """
    Test book processor on all books in the collection.

    Args:
        books_dir: Directory containing book subdirectories
        verbose: Whether to show detailed output

    Returns:
        Dictionary with test results for each book
    """
    # List of books to test (in expected complexity order)
    test_books = [
        ('alice_adventures', 'Roman numerals (I., II., III.)'),
        ('call_cthulhu', 'Markdown headers (## Chapter N)'),
        ('crime_punishment', 'Multi-part structure'),
        ('de_brevitate_vitae', 'Latin with Roman numerals'),
        ('don_quijote', 'Spanish, complex structure'),
        ('great_gatsby', 'Standard numbered chapters'),
        ('metamorphosis', 'Short work, few sections'),
        ('moby_dick', 'Many chapters + special sections'),
        ('origin_species', 'Academic style sections'),
        ('pride_prejudice', 'Volume + Chapter structure'),
        ('sherlock_holmes', 'Story collection'),
        ('time_machine', 'Roman numerals'),
        ('war_worlds', 'Book + Chapter structure'),
        ('winnie_pooh', '"In Which..." style chapters'),
        ('zarathustra', 'Philosophical parts/sections'),
    ]

    results = {}
    processor = BookProcessor(verbose=verbose)

    print("=" * 80)
    print("BOOK PROCESSOR TEST - Processing All Books")
    print("=" * 80)
    print()

    successful = 0
    failed = 0

    for book_name, expected_format in test_books:
        book_path = books_dir / book_name / "book.md"

        # Check if book exists
        if not book_path.exists():
            print(f"⚠️  {book_name:20s} : SKIPPED (file not found)")
            results[book_name] = {
                'status': 'skipped',
                'reason': 'File not found'
            }
            continue

        try:
            print(f"📖 {book_name:20s} : Processing... ", end="", flush=True)

            # Process the book
            manifest = processor.process(book_path, auto_fix=True)

            # Save manifest
            manifest_path = book_path.parent / "book_manifest.json"
            manifest.save(manifest_path)

            # Collect results
            chapter_types = {}
            for ch in manifest.chapters:
                dtype = ch.detection_type
                chapter_types[dtype] = chapter_types.get(dtype, 0) + 1

            results[book_name] = {
                'status': 'success',
                'chapters_found': len(manifest.chapters),
                'chapter_types': chapter_types,
                'toc_generated': bool(manifest.toc_markdown),
                'gutenberg_stripped': manifest.processing.get('gutenberg_stripped', False),
                'word_count': manifest.processing.get('total_words', 0),
                'title': manifest.metadata.get('title', 'Unknown'),
                'author': manifest.metadata.get('author', 'Unknown'),
                'language': manifest.metadata.get('language', 'Unknown'),
                'expected_format': expected_format,
                'processing_log': manifest.processing_log
            }

            # Print result
            status_icon = "✅" if len(manifest.chapters) > 0 else "⚠️"
            print(f"{status_icon} {len(manifest.chapters)} chapters")

            successful += 1

        except Exception as e:
            print(f"❌ ERROR: {str(e)[:50]}")
            results[book_name] = {
                'status': 'error',
                'error': str(e),
                'expected_format': expected_format
            }
            failed += 1

    print()
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print()

    # Generate summary report
    generate_summary_report(results, successful, failed, len(test_books))

    # Save detailed results
    results_path = books_dir / "processing_results.json"
    with open(results_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)

    print(f"\n📊 Detailed results saved to: {results_path}")

    return results


def generate_summary_report(results: Dict, successful: int, failed: int, total: int):
    """Generate and print a summary report of the test results."""

    # Count books by status
    print(f"📚 Books Processed: {successful}/{total}")
    if failed > 0:
        print(f"❌ Failed: {failed}")

    # Books with no chapters detected
    no_chapters = [book for book, res in results.items()
                   if res.get('status') == 'success' and res.get('chapters_found', 0) == 0]
    if no_chapters:
        print(f"⚠️  No chapters detected: {', '.join(no_chapters)}")

    print()

    # Chapter detection patterns used
    print("📖 Chapter Detection Patterns Used:")
    pattern_usage = {}
    for book, res in results.items():
        if res.get('status') == 'success':
            for pattern_type, count in res.get('chapter_types', {}).items():
                pattern_usage[pattern_type] = pattern_usage.get(pattern_type, 0) + 1

    for pattern, count in sorted(pattern_usage.items(), key=lambda x: x[1], reverse=True):
        print(f"  • {pattern:20s} : {count} books")

    print()

    # Total statistics
    total_chapters = sum(res.get('chapters_found', 0) for res in results.values()
                        if res.get('status') == 'success')
    total_words = sum(res.get('word_count', 0) for res in results.values()
                      if res.get('status') == 'success')

    print("📊 Total Statistics:")
    print(f"  • Total chapters detected: {total_chapters:,}")
    print(f"  • Total words processed: {total_words:,}")

    # Books that had Gutenberg stripped
    gutenberg_books = [book for book, res in results.items()
                       if res.get('gutenberg_stripped')]
    if gutenberg_books:
        print(f"  • Gutenberg boilerplate removed: {len(gutenberg_books)} books")

    # TOC generation
    toc_generated = [book for book, res in results.items()
                    if res.get('toc_generated')]
    print(f"  • TOCs generated: {len(toc_generated)} books")

    print()

    # Language distribution
    print("🌐 Language Distribution:")
    languages = {}
    for res in results.values():
        if res.get('status') == 'success':
            lang = res.get('language', 'Unknown')
            languages[lang] = languages.get(lang, 0) + 1

    for lang, count in sorted(languages.items(), key=lambda x: x[1], reverse=True):
        print(f"  • {lang:12s} : {count} books")

    print()

    # Per-book details (compact)
    print("📚 Individual Results:")
    print("-" * 80)
    print(f"{'Book':<20} {'Chapters':<10} {'Type':<25} {'TOC':<5} {'Status':<10}")
    print("-" * 80)

    for book_name, res in sorted(results.items()):
        if res.get('status') == 'success':
            chapters = res.get('chapters_found', 0)
            # Get primary chapter type
            chapter_types = res.get('chapter_types', {})
            if chapter_types:
                primary_type = max(chapter_types, key=chapter_types.get)
            else:
                primary_type = "none"
            toc = "✓" if res.get('toc_generated') else "✗"
            status = "✅" if chapters > 0 else "⚠️"

            print(f"{book_name:<20} {chapters:<10} {primary_type:<25} {toc:<5} {status:<10}")
        elif res.get('status') == 'error':
            error = res.get('error', 'Unknown error')[:30]
            print(f"{book_name:<20} {'ERROR':<10} {error:<25} {'-':<5} {'❌':<10}")
        else:
            print(f"{book_name:<20} {'SKIPPED':<10} {'-':<25} {'-':<5} {'⚠️':<10}")

    print("-" * 80)


def generate_html_report(results: Dict, output_path: Path):
    """Generate an HTML report with detailed results."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Book Processing Report</title>
        <style>
            body {{ font-family: -apple-system, sans-serif; margin: 40px; }}
            table {{ border-collapse: collapse; width: 100%; }}
            th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
            th {{ background-color: #4CAF50; color: white; }}
            tr:nth-child(even) {{ background-color: #f2f2f2; }}
            .success {{ color: green; }}
            .error {{ color: red; }}
            .warning {{ color: orange; }}
        </style>
    </head>
    <body>
        <h1>Book Processing Report</h1>
        <p>Generated: {timestamp}</p>
        <table>
            <tr>
                <th>Book</th>
                <th>Title</th>
                <th>Author</th>
                <th>Chapters</th>
                <th>Words</th>
                <th>Language</th>
                <th>Status</th>
            </tr>
    """

    for book_name, res in sorted(results.items()):
        if res.get('status') == 'success':
            status_class = 'success' if res.get('chapters_found', 0) > 0 else 'warning'
            status_icon = "✅" if res.get('chapters_found', 0) > 0 else "⚠️"
            html += f"""
            <tr>
                <td>{book_name}</td>
                <td>{res.get('title', 'Unknown')}</td>
                <td>{res.get('author', 'Unknown')}</td>
                <td>{res.get('chapters_found', 0)}</td>
                <td>{res.get('word_count', 0):,}</td>
                <td>{res.get('language', 'Unknown')}</td>
                <td class="{status_class}">{status_icon}</td>
            </tr>
            """
        else:
            html += f"""
            <tr>
                <td>{book_name}</td>
                <td colspan="5">{res.get('error', res.get('reason', 'Unknown'))}</td>
                <td class="error">❌</td>
            </tr>
            """

    html += """
        </table>
    </body>
    </html>
    """

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)


def main():
    """Command-line interface."""
    import argparse

    parser = argparse.ArgumentParser(description="Test book processor on all books")
    parser.add_argument(
        '--books-dir',
        default="books",
        help="Directory containing book folders (default: books)"
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help="Show detailed processing output"
    )
    parser.add_argument(
        '--html-report',
        action='store_true',
        help="Generate HTML report"
    )

    args = parser.parse_args()

    books_dir = Path(args.books_dir)
    if not books_dir.exists():
        print(f"❌ Books directory not found: {books_dir}")
        return 1

    # Run tests
    results = test_all_books(books_dir, verbose=args.verbose)

    # Generate HTML report if requested
    if args.html_report:
        html_path = books_dir / "processing_report.html"
        generate_html_report(results, html_path)
        print(f"📄 HTML report saved to: {html_path}")

    # Return success if at least 80% of books processed successfully
    success_rate = sum(1 for r in results.values() if r.get('status') == 'success') / len(results)
    return 0 if success_rate >= 0.8 else 1


if __name__ == "__main__":
    exit(main())