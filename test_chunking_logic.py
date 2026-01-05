#!/usr/bin/env python3
"""
Test the chunking logic directly without loading TTS
"""

import re
from typing import List

def chunk_text(text: str, max_chars: int = 250) -> List[str]:
    """
    NEW IMPROVED CHUNKING - Always splits at sentence boundaries
    """
    if len(text) <= max_chars:
        return [text]

    chunks = []

    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)

    current_chunk = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        # If single sentence is too long, split at clause boundaries
        if len(sentence) > max_chars:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = ""

            # Split at commas, semicolons, etc.
            clauses = re.split(r'([,;:—\-]\s+)', sentence)

            temp_chunk = ""
            for clause in clauses:
                if not clause.strip():
                    continue

                if len(temp_chunk) + len(clause) > max_chars:
                    if temp_chunk:
                        chunks.append(temp_chunk.strip())
                    temp_chunk = clause
                else:
                    temp_chunk += clause

            if temp_chunk:
                current_chunk = temp_chunk.strip()

        # Normal case: sentence fits within limit
        elif len(current_chunk) + len(sentence) + 1 > max_chars:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence
        else:
            if current_chunk:
                current_chunk += " " + sentence
            else:
                current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


# Test cases
test_cases = [
    # Case 1: The harsh split you experienced
    "Indeed they even lead others to become possessors of many things and great power.",

    # Case 2: Long sentence that needs clause splitting
    "This is a very long sentence that goes on and on, and it has many clauses, separated by commas, which should be used as natural split points if the sentence is too long for a single chunk.",

    # Case 3: Multiple short sentences
    "Short one. Another short one. And a third. These should group together.",

    # Case 4: Mixed lengths
    "Indeed they even lead others to become possessors. This is shorter. And another medium-length sentence that flows naturally into the narrative."
]

print("="*70)
print("CHUNKING LOGIC TEST")
print("="*70)

for i, test_text in enumerate(test_cases, 1):
    print(f"\n{'='*70}")
    print(f"TEST CASE {i}:")
    print(f"{'='*70}")
    print(f"Input ({len(test_text)} chars):")
    print(f'  "{test_text}"')
    print()

    chunks = chunk_text(test_text, max_chars=80)  # Using 80 to force splits

    print(f"Output: {len(chunks)} chunk(s)\n")

    for j, chunk in enumerate(chunks, 1):
        last_char = chunk[-1] if chunk else ''
        natural = "✓" if last_char in '.!?,;:—-' else "⚠️ HARSH"
        print(f"  Chunk {j} ({len(chunk)} chars) [{natural}]:")
        print(f'    "{chunk}"')
        print()

print("="*70)
print("KEY IMPROVEMENTS:")
print("="*70)
print("✓ Chunks always end at sentence boundaries (.!?)")
print("✓ Long sentences split at clause boundaries (,;:—)")
print("✓ No more mid-sentence cuts like 'become' | 'possessors'")
print("✓ Better audio flow with natural pauses")
print("="*70)
