#!/usr/bin/env python3
"""
Book Validator - Ensure books meet quality standards for all features

This module validates book files to ensure they support:
- Karaoke mode (text sync with audio)
- AI chat assistant (chapter-based Q&A)
- Web player (proper metadata and structure)

Usage:
    # Validate single book
    python validate.py books/alice_adventures/alice.md

    # Validate with auto-fix
    python validate.py book.md --auto-fix

    # Validate all books in directory
    python validate.py books/ --recursive

    # Require specific features
    python validate.py book.md --require karaoke,ai

    # Use as library
    from lib.book.validator import validate_book
    report = validate_book('book.md')
    if report.valid:
        print("Book is ready!")
"""

import re
import sys
import json
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
from lib.book.processor import BookProcessor


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class ValidationReport:
    """Complete validation report for a book."""

    # Overall status
    valid: bool
    file_path: str

    # Issues
    errors: List[str]
    warnings: List[str]

    # Feature support flags
    feature_support: Dict[str, bool]

    # Metrics
    metrics: Dict[str, any]

    # Auto-fix suggestions
    fixes: List[str]

    def __str__(self) -> str:
        """Human-readable report."""
        lines = []
        lines.append("=" * 70)
        lines.append("BOOK VALIDATION REPORT")
        lines.append("=" * 70)
        lines.append(f"File: {self.file_path}")
        lines.append(f"Status: {'✅ VALID' if self.valid else '❌ INVALID'}")
        lines.append("")

        # Errors
        if self.errors:
            lines.append(f"ERRORS ({len(self.errors)}):")
            for error in self.errors:
                lines.append(f"  ❌ {error}")
            lines.append("")

        # Warnings
        if self.warnings:
            lines.append(f"WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                lines.append(f"  ⚠️  {warning}")
            lines.append("")

        # Feature support
        lines.append("FEATURE SUPPORT:")
        for feature, supported in self.feature_support.items():
            icon = "✅" if supported else "❌"
            lines.append(f"  {icon} {feature.title()}: {'Ready' if supported else 'Not Ready'}")
        lines.append("")

        # Metrics
        lines.append("METRICS:")
        for metric, value in self.metrics.items():
            lines.append(f"  • {metric.replace('_', ' ').title()}: {value}")
        lines.append("")

        # Fixes
        if self.fixes:
            lines.append("SUGGESTED FIXES:")
            for fix in self.fixes:
                lines.append(f"  💡 {fix}")
            lines.append("")

        lines.append("=" * 70)
        return "\n".join(lines)

    def to_json(self) -> str:
        """Export as JSON."""
        return json.dumps(asdict(self), indent=2)


# ============================================================================
# Validation Functions
# ============================================================================

def check_file_exists(file_path: Path) -> Tuple[bool, List[str]]:
    """Check if file exists and is readable."""
    errors = []

    if not file_path.exists():
        errors.append(f"File not found: {file_path}")
        return False, errors

    if not file_path.is_file():
        errors.append(f"Path is not a file: {file_path}")
        return False, errors

    if file_path.suffix.lower() not in ['.md', '.txt', '.markdown']:
        errors.append(f"File must be markdown (.md) format, got: {file_path.suffix}")
        return False, errors

    return True, errors


def check_chapter_structure(text: str, filename: str) -> Tuple[bool, List[str], List[str], Dict]:
    """
    Validate chapter structure.

    Uses BookProcessor as the canonical chapter detection system (14+ patterns).
    Also checks TOC via ChapterDetector for TOC/content mismatch warnings.

    Returns:
        (valid, errors, warnings, metrics)
    """
    errors = []
    warnings = []
    metrics = {
        'chapter_count': 0,
        'has_toc': False,
        'toc_count': 0,
        'sequential_chapters': False,
        'missing_chapters': [],
        'duplicate_chapters': []
    }

    # Use BookProcessor as single source of truth for chapter and TOC detection
    processor = BookProcessor(verbose=False)
    cleaned_text, _ = processor.strip_gutenberg(text)

    # Check TOC
    toc = processor.detect_toc(cleaned_text)
    metrics['has_toc'] = len(toc) > 0
    metrics['toc_count'] = len(toc)

    # Detect chapters
    bp_chapters = processor.detect_chapters(cleaned_text)
    chapters = []
    for ch in bp_chapters:
        chapters.append({
            'number': ch.number,
            'marker': ch.marker,
            'line': ch.start_line + 1,
            'char_pos': ch.start_char,
            'type': ch.detection_type
        })

    metrics['chapter_count'] = len(chapters)

    if len(chapters) == 0:
        errors.append("No chapters detected in content")
        return False, errors, warnings, metrics

    # Validate sequence
    validation = processor.validate_chapter_sequence(chapters)
    metrics['sequential_chapters'] = validation.get('valid', False)
    metrics['missing_chapters'] = validation.get('missing', [])
    metrics['duplicate_chapters'] = validation.get('duplicates', [])

    # Errors vs warnings
    if not validation.get('valid', False):
        if validation.get('missing', []):
            errors.append(f"Missing chapters: {validation['missing']}")
        if validation.get('duplicates', []):
            errors.append(f"Duplicate chapters: {validation['duplicates']}")

    # TOC/content mismatch
    if toc and chapters and len(toc) != len(chapters):
        warnings.append(f"TOC has {len(toc)} entries but content has {len(chapters)} chapters")

    # Too few chapters
    if len(chapters) < 3:
        warnings.append(f"Only {len(chapters)} chapter(s) detected - book may be incomplete")

    valid = len(errors) == 0
    return valid, errors, warnings, metrics


def check_text_quality(text: str) -> Tuple[bool, List[str], List[str], Dict]:
    """
    Check for common text quality issues.

    Returns:
        (valid, errors, warnings, metrics)
    """
    errors = []
    warnings = []
    metrics = {
        'has_gutenberg_boilerplate': False,
        'word_count': 0,
        'line_count': 0,
        'empty_paragraphs': 0
    }

    lines = text.split('\n')
    words = text.split()

    metrics['word_count'] = len(words)
    metrics['line_count'] = len(lines)

    # Check for Gutenberg boilerplate
    gutenberg_markers = [
        'Project Gutenberg',
        'START OF THE PROJECT GUTENBERG',
        'END OF THE PROJECT GUTENBERG',
        'www.gutenberg.org'
    ]

    for marker in gutenberg_markers:
        if marker in text:
            metrics['has_gutenberg_boilerplate'] = True
            warnings.append(f"Contains Project Gutenberg boilerplate - consider using cleaned version")
            break

    # Check minimum content
    if len(words) < 100:
        errors.append(f"Book is too short ({len(words)} words) - minimum 100 words required")

    # Check for excessive empty paragraphs
    empty_paras = len([line for line in lines if line.strip() == ''])
    metrics['empty_paragraphs'] = empty_paras
    if empty_paras > len(lines) * 0.5:
        warnings.append(f"Excessive empty lines ({empty_paras}/{len(lines)}) - formatting may be degraded")

    valid = len(errors) == 0
    return valid, errors, warnings, metrics


def check_metadata(text: str, filename: str) -> Tuple[bool, List[str], List[str], Dict]:
    """
    Check for metadata (title, author, etc.).

    Returns:
        (valid, errors, warnings, metrics)
    """
    errors = []
    warnings = []
    metrics = {
        'has_title': False,
        'has_author': False,
        'title': None,
        'author': None
    }

    lines = text.split('\n')[:50]  # Check first 50 lines

    # Look for title patterns
    title_patterns = [
        r'^#\s+(.+)$',  # Markdown H1
        r'^Title:\s*(.+)$',  # "Title: Book Name"
        r'^##\s+(.+)$'  # Markdown H2
    ]

    for line in lines:
        for pattern in title_patterns:
            match = re.match(pattern, line.strip(), re.IGNORECASE)
            if match and not metrics['has_title']:
                metrics['has_title'] = True
                metrics['title'] = match.group(1).strip()
                break

    # Look for author patterns
    author_patterns = [
        r'Author:\s*(.+)$',
        r'by\s+(.+)$',
        r'##\s+by\s+(.+)$'
    ]

    for line in lines:
        for pattern in author_patterns:
            match = re.match(pattern, line.strip(), re.IGNORECASE)
            if match and not metrics['has_author']:
                metrics['has_author'] = True
                metrics['author'] = match.group(1).strip()
                break

    # Warnings only (metadata is optional but recommended)
    if not metrics['has_title']:
        warnings.append("No title detected in first 50 lines")

    if not metrics['has_author']:
        warnings.append("No author detected in first 50 lines")

    valid = True  # Metadata warnings don't fail validation
    return valid, errors, warnings, metrics


def check_feature_readiness(
    chapter_metrics: Dict,
    text_metrics: Dict,
    metadata_metrics: Dict,
    file_path: Path
) -> Dict[str, bool]:
    """
    Check which features this book supports.

    Returns:
        Dict of feature_name -> supported (bool)
    """
    support = {}

    # Karaoke mode: needs clean text + chapters
    support['karaoke'] = (
        chapter_metrics['chapter_count'] >= 1
        and text_metrics['word_count'] >= 100
        and file_path.suffix.lower() in ['.md', '.markdown']
    )

    # AI chat: needs chapter boundaries + reasonable chapter count
    support['ai_chat'] = (
        chapter_metrics['chapter_count'] >= 3
        and chapter_metrics['sequential_chapters']
    )

    # Web player: needs valid structure (less strict)
    support['web_player'] = (
        chapter_metrics['chapter_count'] >= 1
    )

    return support


def generate_auto_fixes(
    file_path: Path,
    chapter_metrics: Dict,
    text_metrics: Dict,
    metadata_metrics: Dict
) -> List[str]:
    """
    Generate suggestions for automatic fixes.

    Returns:
        List of fix descriptions
    """
    fixes = []

    # Gutenberg boilerplate
    if text_metrics.get('has_gutenberg_boilerplate', False):
        fixes.append(f"Run: python validate.py {file_path} --auto-fix")

    # Missing chapters
    if chapter_metrics.get('missing_chapters', []):
        fixes.append(f"Re-translate missing chapters: {chapter_metrics['missing_chapters']}")

    # No TOC but has chapters
    if chapter_metrics['chapter_count'] > 0 and not chapter_metrics['has_toc']:
        fixes.append("Generate TOC from chapter markers (auto-fixable)")

    # No metadata
    if not metadata_metrics['has_title'] or not metadata_metrics['has_author']:
        fixes.append(f"Add metadata to top of file (Title, Author)")

    return fixes


# ============================================================================
# Main Validation Function
# ============================================================================

def validate_book(file_path: str, verbose: bool = False) -> ValidationReport:
    """
    Validate a book file for quality and feature readiness.

    Args:
        file_path: Path to markdown book file
        verbose: If True, print detailed progress

    Returns:
        ValidationReport with all checks and metrics
    """
    path = Path(file_path)
    errors = []
    warnings = []
    all_metrics = {}

    # 1. Check file exists
    if verbose:
        print(f"Checking file: {path}")

    file_valid, file_errors = check_file_exists(path)
    if not file_valid:
        return ValidationReport(
            valid=False,
            file_path=str(path),
            errors=file_errors,
            warnings=[],
            feature_support={},
            metrics={},
            fixes=[]
        )

    # Read file
    try:
        with open(path, 'r', encoding='utf-8') as f:
            text = f.read()
    except Exception as e:
        return ValidationReport(
            valid=False,
            file_path=str(path),
            errors=[f"Failed to read file: {e}"],
            warnings=[],
            feature_support={},
            metrics={},
            fixes=[]
        )

    # 2. Check chapter structure
    if verbose:
        print("Checking chapter structure...")

    chapter_valid, chapter_errors, chapter_warnings, chapter_metrics = check_chapter_structure(
        text, path.name
    )
    errors.extend(chapter_errors)
    warnings.extend(chapter_warnings)
    all_metrics.update(chapter_metrics)

    # 3. Check text quality
    if verbose:
        print("Checking text quality...")

    text_valid, text_errors, text_warnings, text_metrics = check_text_quality(text)
    errors.extend(text_errors)
    warnings.extend(text_warnings)
    all_metrics.update(text_metrics)

    # 4. Check metadata
    if verbose:
        print("Checking metadata...")

    metadata_valid, metadata_errors, metadata_warnings, metadata_metrics = check_metadata(
        text, path.name
    )
    errors.extend(metadata_errors)
    warnings.extend(metadata_warnings)
    all_metrics.update(metadata_metrics)

    # 5. Check feature readiness
    if verbose:
        print("Checking feature readiness...")

    feature_support = check_feature_readiness(
        chapter_metrics, text_metrics, metadata_metrics, path
    )

    # 6. Generate auto-fix suggestions
    fixes = generate_auto_fixes(path, chapter_metrics, text_metrics, metadata_metrics)

    # Overall validation
    valid = len(errors) == 0

    return ValidationReport(
        valid=valid,
        file_path=str(path),
        errors=errors,
        warnings=warnings,
        feature_support=feature_support,
        metrics=all_metrics,
        fixes=fixes
    )


# ============================================================================
# Auto-Fix Functions
# ============================================================================

def auto_fix_book(file_path: str, backup: bool = True) -> bool:
    """
    Automatically fix common issues in book file.

    Args:
        file_path: Path to book file
        backup: If True, create .bak backup before fixing

    Returns:
        True if fixes were applied successfully
    """
    path = Path(file_path)

    # Create backup
    if backup:
        backup_path = path.with_suffix(path.suffix + '.bak')
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"✅ Backup created: {backup_path}")

    # Read file
    with open(path, 'r', encoding='utf-8') as f:
        text = f.read()

    modified = False

    # Fix 1: Strip Gutenberg boilerplate
    if 'START OF THE PROJECT GUTENBERG' in text:
        start_marker = '*** START OF THE PROJECT GUTENBERG'
        start_idx = text.find(start_marker)
        if start_idx != -1:
            # Find end of marker line
            newline_idx = text.find('\n', start_idx)
            if newline_idx != -1:
                text = text[newline_idx + 1:]
                modified = True
                print("✅ Removed Gutenberg header")

    if 'END OF THE PROJECT GUTENBERG' in text:
        end_marker = '*** END OF THE PROJECT GUTENBERG'
        end_idx = text.find(end_marker)
        if end_idx != -1:
            text = text[:end_idx]
            modified = True
            print("✅ Removed Gutenberg footer")

    # Fix 2: Generate TOC if missing
    processor = BookProcessor(verbose=False)
    bp_chapters = processor.detect_chapters(text)
    chapters = [{'number': ch.number, 'marker': ch.marker} for ch in bp_chapters]
    toc = processor.detect_toc(text)

    if len(chapters) > 0 and len(toc) == 0:
        # Generate TOC
        toc_lines = ["## Table of Contents\n"]
        for ch in chapters:
            toc_lines.append(f"{ch['number']}. [{ch['marker']}](#chapter-{ch['number']})")
        toc_lines.append("\n---\n")

        # Insert after title/author (first 20 lines)
        lines = text.split('\n')
        insert_pos = min(20, len(lines))
        lines.insert(insert_pos, '\n'.join(toc_lines))
        text = '\n'.join(lines)
        modified = True
        print(f"✅ Generated TOC with {len(chapters)} chapters")

    # Save if modified
    if modified:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"✅ Fixes applied to: {path}")
        return True
    else:
        print("ℹ️  No auto-fixable issues found")
        return False


# ============================================================================
# CLI Interface
# ============================================================================

def validate_directory(directory: Path, recursive: bool = False) -> List[ValidationReport]:
    """Validate all books in a directory."""
    reports = []

    if recursive:
        pattern = "**/*.md"
    else:
        pattern = "*.md"

    for md_file in directory.glob(pattern):
        # Skip chunk files and temp files
        if 'chunk' in md_file.name.lower() or md_file.name.startswith('_'):
            continue

        print(f"\nValidating: {md_file.relative_to(directory)}")
        report = validate_book(str(md_file))
        reports.append(report)

        # Print summary
        status = "✅ VALID" if report.valid else "❌ INVALID"
        feature_count = sum(report.feature_support.values())
        print(f"  {status} - {feature_count}/3 features supported")

    return reports


def main():
    parser = argparse.ArgumentParser(
        description="Validate book quality for Karaoke and AI features"
    )
    parser.add_argument(
        'path',
        help='Path to book file or directory'
    )
    parser.add_argument(
        '--recursive', '-r',
        action='store_true',
        help='Recursively validate all books in directory'
    )
    parser.add_argument(
        '--auto-fix',
        action='store_true',
        help='Automatically fix common issues'
    )
    parser.add_argument(
        '--require',
        help='Comma-separated list of required features (karaoke,ai,web_player)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Print detailed validation steps'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON'
    )
    parser.add_argument(
        '--no-backup',
        action='store_true',
        help='Skip creating backup when using --auto-fix'
    )

    args = parser.parse_args()
    path = Path(args.path)

    # Validate directory or single file
    if path.is_dir():
        reports = validate_directory(path, args.recursive)

        # Print summary
        print("\n" + "=" * 70)
        print("VALIDATION SUMMARY")
        print("=" * 70)
        total = len(reports)
        valid = sum(1 for r in reports if r.valid)
        print(f"Total books: {total}")
        print(f"Valid: {valid}")
        print(f"Invalid: {total - valid}")

        # Feature support summary
        feature_summary = {}
        for report in reports:
            for feature, supported in report.feature_support.items():
                if feature not in feature_summary:
                    feature_summary[feature] = 0
                if supported:
                    feature_summary[feature] += 1

        print("\nFeature Support:")
        for feature, count in feature_summary.items():
            print(f"  {feature.title()}: {count}/{total}")

        sys.exit(0 if valid == total else 1)

    else:
        # Single file validation
        if args.auto_fix:
            print("Running auto-fix...")
            auto_fix_book(str(path), backup=not args.no_backup)
            print("\nRe-validating after fixes...\n")

        report = validate_book(str(path), verbose=args.verbose)

        # Output
        if args.json:
            print(report.to_json())
        else:
            print(report)

        # Check required features
        if args.require:
            required = [f.strip() for f in args.require.split(',')]
            missing = [f for f in required if not report.feature_support.get(f, False)]

            if missing:
                print(f"\n❌ FAILED: Missing required features: {', '.join(missing)}")
                sys.exit(1)

        sys.exit(0 if report.valid else 1)


if __name__ == "__main__":
    main()
