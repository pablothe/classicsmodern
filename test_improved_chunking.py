#!/usr/bin/env python3
"""
Test the improved chunking logic to verify no harsh sentence splits
"""

from local_tts_xtts import XTTSAudioGenerator

# Sample text that would have caused harsh splits
test_text = """
Indeed they even lead others to become possessors of many things and great power.
This is a very long sentence that goes on and on and needs to be split intelligently at natural pause points, like commas or semicolons, rather than cutting right in the middle of a thought.
Short sentence here.
Another medium-length sentence that flows naturally.
"""

print("="*70)
print("TESTING IMPROVED CHUNKING LOGIC")
print("="*70)
print(f"\nInput text ({len(test_text)} chars):\n")
print(test_text)
print("\n" + "="*70)

# Create generator (no voice needed for chunking test)
generator = XTTSAudioGenerator(reference_voice=None, language="en")

# Test chunking
chunks = generator.chunk_text(test_text, max_chars=250)

print(f"\nGenerated {len(chunks)} chunks:\n")

for i, chunk in enumerate(chunks, 1):
    print(f"CHUNK {i} ({len(chunk)} chars):")
    print(f"  \"{chunk}\"")
    print()

    # Check for harsh splits (sentence ending without punctuation)
    if chunk and chunk[-1] not in '.!?,;:':
        print(f"  ⚠️  WARNING: Chunk ends without punctuation (harsh split!)")
        print()

print("="*70)
print("ANALYSIS:")
print("="*70)

# Count how many chunks end at sentence boundaries
proper_endings = sum(1 for chunk in chunks if chunk and chunk[-1] in '.!?')
total_chunks = len(chunks)

print(f"Chunks ending at sentences: {proper_endings}/{total_chunks}")
print(f"Proper sentence boundaries: {proper_endings/total_chunks*100:.1f}%")

if proper_endings == total_chunks:
    print("\n✅ PERFECT! All chunks end at sentence boundaries")
elif proper_endings / total_chunks > 0.8:
    print("\n✓ GOOD: Most chunks end at natural boundaries")
else:
    print("\n⚠️  NEEDS WORK: Too many harsh splits")
