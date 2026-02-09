#!/usr/bin/env python3
"""
Batch Cover Generation Script
Generates watercolor covers for books that don't have covers yet.
"""

import sys
from pathlib import Path
from book_prompts import get_book_prompt
from generate import CoverArtGenerator

# Books that need new covers (excluding test_audiobook)
BOOKS_TO_GENERATE = [
    'alice_adventures',
    'don_quijote',
    'metamorphosis',
    'moby_dick',
    'origin_species',
    'pride_prejudice',
    'sherlock_holmes',
    'time_machine',
    'war_worlds',
    'winnie_pooh'
]

def main():
    print("="*70)
    print("BATCH WATERCOLOR COVER GENERATION")
    print("="*70)
    print(f"Generating covers for {len(BOOKS_TO_GENERATE)} books\n")

    # Initialize generator once (model loads once)
    print("Loading Stable Diffusion model...")
    generator = CoverArtGenerator()
    print()

    results = []

    for i, book in enumerate(BOOKS_TO_GENERATE, 1):
        print(f"\n[{i}/{len(BOOKS_TO_GENERATE)}] Generating cover for: {book}")
        print("-"*70)

        # Get watercolor prompt
        prompt = get_book_prompt(book)

        # Output path
        cover_path = Path(f"books/{book}/cover.png")

        # Skip if already exists
        if cover_path.exists():
            print(f"⏭️  Cover already exists, skipping...")
            results.append((book, 'skipped', str(cover_path)))
            continue

        try:
            # Generate cover
            output = generator.generate_cover(
                prompt=prompt,
                output_path=str(cover_path),
                guidance_scale=7.5,
                num_inference_steps=50,
                width=512,
                height=512
            )

            results.append((book, 'success', str(output)))
            print(f"✅ Success!")

        except Exception as e:
            print(f"❌ Failed: {e}")
            results.append((book, 'failed', str(e)))

    # Summary
    print("\n" + "="*70)
    print("GENERATION COMPLETE")
    print("="*70)

    success_count = sum(1 for _, status, _ in results if status == 'success')
    skipped_count = sum(1 for _, status, _ in results if status == 'skipped')
    failed_count = sum(1 for _, status, _ in results if status == 'failed')

    print(f"\nResults:")
    print(f"  ✅ Success: {success_count}")
    print(f"  ⏭️  Skipped: {skipped_count}")
    print(f"  ❌ Failed: {failed_count}")

    if failed_count > 0:
        print("\nFailed books:")
        for book, status, error in results:
            if status == 'failed':
                print(f"  - {book}: {error}")

    print("\nGenerated covers:")
    for book, status, path in results:
        if status == 'success':
            print(f"  ✓ {path}")

    print("="*70)

if __name__ == "__main__":
    main()
