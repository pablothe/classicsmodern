#!/usr/bin/env python3
"""
Audit translated book files for suspicious repetitions at chunk/paragraph boundaries.

Scans a translated markdown file (or directory of chunk files) and reports
exact and fuzzy overlaps between consecutive text blocks.

Usage:
    # Scan a single translated book
    python scripts/audit_boundaries.py books/nietzsche/translated.md

    # Custom similarity threshold (default: 0.7)
    python scripts/audit_boundaries.py books/nietzsche/translated.md --threshold 0.8

    # Scan a directory of chunk files
    python scripts/audit_boundaries.py books/nietzsche/chunks/translated/ --pattern "*.md"

    # More context (compare 5 sentences instead of default 3)
    python scripts/audit_boundaries.py translated.md --sentences 5

    # JSON output for scripting
    python scripts/audit_boundaries.py translated.md --json
"""

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.translation.deduplicate import find_exact_overlap, find_fuzzy_overlap


@dataclass
class BoundaryReport:
    """Report for a single boundary between consecutive text blocks."""
    boundary_index: int
    total_boundaries: int
    overlap_type: str  # "exact", "fuzzy", "none"
    similarity_score: Optional[float]
    text1_end: str  # Last ~100 chars of previous block
    text2_start: str  # First ~100 chars of next block
    overlap_text: Optional[str]  # The overlapping text (exact) or matched sentences (fuzzy)


def audit_boundaries(
    text: str,
    boundary_marker: str = "\n\n",
    similarity_threshold: float = 0.7,
    context_sentences: int = 3,
    max_overlap_words: int = 50,
) -> List[BoundaryReport]:
    """
    Scan text for suspicious repetitions at block boundaries.

    Args:
        text: Full text to audit
        boundary_marker: How to split into blocks (default: paragraph breaks)
        similarity_threshold: Minimum fuzzy similarity to report
        context_sentences: Number of sentences to compare at each boundary
        max_overlap_words: Max words for exact overlap search

    Returns:
        List of BoundaryReport for each boundary
    """
    blocks = [b.strip() for b in text.split(boundary_marker) if b.strip()]

    if len(blocks) < 2:
        return []

    reports = []
    total = len(blocks) - 1

    for i in range(total):
        block1 = blocks[i]
        block2 = blocks[i + 1]

        report = BoundaryReport(
            boundary_index=i + 1,
            total_boundaries=total,
            overlap_type="none",
            similarity_score=None,
            text1_end=block1[-120:],
            text2_start=block2[:120],
            overlap_text=None,
        )

        # Check exact overlap first
        exact = find_exact_overlap(block1, block2, max_words=max_overlap_words)
        if exact and len(exact.split()) >= 3:
            report.overlap_type = "exact"
            report.similarity_score = 1.0
            report.overlap_text = exact
            reports.append(report)
            continue

        # Check fuzzy overlap
        fuzzy = find_fuzzy_overlap(
            block1, block2,
            similarity_threshold=similarity_threshold,
            max_sentences=context_sentences,
        )
        if fuzzy:
            best_score = max(m[2] for m in fuzzy)
            matched_text = " | ".join(
                f"[{score:.0%}] \"{s2[:60]}\"" for _, s2, score in fuzzy
            )
            report.overlap_type = "fuzzy"
            report.similarity_score = best_score
            report.overlap_text = matched_text
            reports.append(report)

    return reports


def audit_directory(
    directory: Path,
    pattern: str = "*.md",
    similarity_threshold: float = 0.7,
    context_sentences: int = 3,
    max_overlap_words: int = 50,
) -> List[BoundaryReport]:
    """Audit consecutive chunk files in a directory."""
    files = sorted(directory.glob(pattern))
    files = [f for f in files if "_DEDUPED" not in f.name]

    if len(files) < 2:
        return []

    reports = []
    total = len(files) - 1

    for i in range(total):
        text1 = files[i].read_text(encoding="utf-8")
        text2 = files[i + 1].read_text(encoding="utf-8")

        report = BoundaryReport(
            boundary_index=i + 1,
            total_boundaries=total,
            overlap_type="none",
            similarity_score=None,
            text1_end=f"[{files[i].name}] ...{text1[-120:]}",
            text2_start=f"[{files[i+1].name}] {text2[:120]}...",
            overlap_text=None,
        )

        exact = find_exact_overlap(text1, text2, max_words=max_overlap_words)
        if exact and len(exact.split()) >= 3:
            report.overlap_type = "exact"
            report.similarity_score = 1.0
            report.overlap_text = exact
            reports.append(report)
            continue

        fuzzy = find_fuzzy_overlap(
            text1, text2,
            similarity_threshold=similarity_threshold,
            max_sentences=context_sentences,
        )
        if fuzzy:
            best_score = max(m[2] for m in fuzzy)
            matched_text = " | ".join(
                f"[{score:.0%}] \"{s2[:60]}\"" for _, s2, score in fuzzy
            )
            report.overlap_type = "fuzzy"
            report.similarity_score = best_score
            report.overlap_text = matched_text
            reports.append(report)

    return reports


def print_report(reports: List[BoundaryReport], total_boundaries: int):
    """Print human-readable audit report."""
    if not reports:
        print(f"\nNo suspicious boundaries found out of {total_boundaries} total.")
        print("All chunk/paragraph boundaries look clean.")
        return

    exact_count = sum(1 for r in reports if r.overlap_type == "exact")
    fuzzy_count = sum(1 for r in reports if r.overlap_type == "fuzzy")

    print(f"\n{'='*70}")
    print(f"BOUNDARY AUDIT REPORT")
    print(f"{'='*70}")
    print(f"Total boundaries scanned: {total_boundaries}")
    print(f"Suspicious boundaries:    {len(reports)} ({exact_count} exact, {fuzzy_count} fuzzy)")
    print(f"{'='*70}\n")

    for r in reports:
        label = "EXACT OVERLAP" if r.overlap_type == "exact" else "FUZZY OVERLAP"
        score = f"({r.similarity_score:.0%})" if r.similarity_score else ""

        print(f"Boundary {r.boundary_index}/{r.total_boundaries}: {label} {score}")
        print(f"  End:   ...{r.text1_end[-80:]}")
        print(f"  Start: {r.text2_start[:80]}...")
        if r.overlap_text:
            print(f"  Match: {r.overlap_text[:120]}")
        print()

    print(f"{'='*70}")
    print(f"Summary: {len(reports)} suspicious boundaries / {total_boundaries} total")
    if exact_count:
        print(f"  {exact_count} EXACT overlaps (definite duplicates, should be removed)")
    if fuzzy_count:
        print(f"  {fuzzy_count} FUZZY overlaps (likely duplicates, review manually)")
    print(f"{'='*70}")


def main():
    parser = argparse.ArgumentParser(
        description="Audit translated books for boundary duplication"
    )
    parser.add_argument("input", help="Markdown file or directory of chunk files")
    parser.add_argument(
        "--threshold", type=float, default=0.7,
        help="Fuzzy similarity threshold (0.0-1.0, default: 0.7)"
    )
    parser.add_argument(
        "--sentences", type=int, default=3,
        help="Sentences to compare at each boundary (default: 3)"
    )
    parser.add_argument(
        "--pattern", default="*.md",
        help="Glob pattern for chunk files in directory mode (default: *.md)"
    )
    parser.add_argument(
        "--max-words", type=int, default=50,
        help="Max words for exact overlap search (default: 50)"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output as JSON"
    )
    args = parser.parse_args()

    input_path = Path(args.input)

    if not input_path.exists():
        print(f"Error: {input_path} not found", file=sys.stderr)
        sys.exit(1)

    if input_path.is_dir():
        reports = audit_directory(
            input_path,
            pattern=args.pattern,
            similarity_threshold=args.threshold,
            context_sentences=args.sentences,
            max_overlap_words=args.max_words,
        )
        total = len(sorted(input_path.glob(args.pattern))) - 1
    else:
        text = input_path.read_text(encoding="utf-8")
        reports = audit_boundaries(
            text,
            similarity_threshold=args.threshold,
            context_sentences=args.sentences,
            max_overlap_words=args.max_words,
        )
        blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
        total = len(blocks) - 1

    if args.json:
        print(json.dumps([asdict(r) for r in reports], indent=2))
    else:
        print_report(reports, total)

    # Exit code: 1 if any exact overlaps found (definite bugs)
    if any(r.overlap_type == "exact" for r in reports):
        sys.exit(1)


if __name__ == "__main__":
    main()
