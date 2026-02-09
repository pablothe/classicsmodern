#!/usr/bin/env python3
"""
Test the clean architecture for audiobook generation.

This tests:
1. Simple TTS module (text → audio only)
2. Orchestrator (handles chapters)
3. Minimal test books
"""

import sys
from pathlib import Path
from tts_simple import SimpleKokoroTTS
from book_manifest import BookManifest


def test_simple_tts():
    """Test that simple TTS works without any chapter knowledge."""
    print("\n" + "=" * 60)
    print("TEST 1: Simple TTS Module")
    print("=" * 60)

    # Create simple TTS instance
    tts = SimpleKokoroTTS(voice="af_sky")

    # Test text (no chapter markers needed!)
    test_text = "This is a simple test. The TTS module only converts text to audio."

    # Generate audio
    output = Path("test_output") / "simple_test.mp3"
    output.parent.mkdir(exist_ok=True)

    try:
        print("Generating audio for simple text...")
        audio_file = tts.generate_audio_from_text(test_text, output, verbose=False)
        print(f"✅ Success! Audio generated: {audio_file}")
        return True
    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


def test_manifest():
    """Test book manifest creation."""
    print("\n" + "=" * 60)
    print("TEST 2: Book Manifest")
    print("=" * 60)

    # Create a minimal manifest
    manifest = BookManifest.create_minimal(
        title="Test Book",
        author="Test Author",
        chapters=["Chapter 1", "Chapter 2", "Chapter 3"]
    )

    print(f"Created manifest with {manifest.get_chapter_count()} chapters:")
    for chapter in manifest.chapters:
        print(f"  Chapter {chapter['number']}: {chapter['title']}")

    return manifest.get_chapter_count() == 3


def test_orchestrator_simulation():
    """
    Simulate what the orchestrator does without full implementation.
    This shows the clean separation of concerns.
    """
    print("\n" + "=" * 60)
    print("TEST 3: Orchestrator Simulation")
    print("=" * 60)

    # Step 1: Create manifest (orchestrator's job)
    manifest = BookManifest.create_minimal(
        title="Das Testbuch",
        author="Test Autor",
        chapters=["Der Anfang", "Die Mitte", "Das Ende"]
    )

    # Add minimal content to chapters
    manifest.chapters[0]['content'] = "Dies ist der erste Satz."
    manifest.chapters[1]['content'] = "Hier ist der zweite Satz."
    manifest.chapters[2]['content'] = "Der letzte Satz."

    print(f"📖 Processing book: {manifest.metadata['title']}")
    print(f"   Chapters: {manifest.get_chapter_count()}")

    # Step 2: Create TTS instance (stateless, no book knowledge)
    tts = SimpleKokoroTTS(voice="af_sky")

    # Step 3: Generate audio for each chapter (orchestrator's loop)
    output_dir = Path("test_output") / "orchestrated"
    output_dir.mkdir(parents=True, exist_ok=True)

    chapter_files = []
    for chapter in manifest.chapters:
        chapter_num = chapter['number']
        chapter_text = chapter['content']
        output_file = output_dir / f"chapter_{chapter_num:02d}.mp3"

        print(f"\n🎵 Generating Chapter {chapter_num}: {chapter['title']}")
        print(f"   Text: '{chapter_text}'")

        try:
            # TTS only knows about text, not chapters!
            audio_file = tts.generate_audio_from_text(
                chapter_text,
                output_file,
                verbose=False
            )
            chapter_files.append(audio_file)
            print(f"   ✅ Generated: {audio_file.name}")
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            return False

    # Step 4: Create playlist (orchestrator's job)
    playlist_path = output_dir / "audiobook.m3u"
    with open(playlist_path, 'w') as f:
        f.write("#EXTM3U\n")
        for i, audio_file in enumerate(chapter_files, 1):
            f.write(f"#EXTINF:-1,Chapter {i}\n")
            f.write(f"{audio_file.name}\n")

    print(f"\n📋 Playlist created: {playlist_path}")
    print(f"✅ Orchestration complete! {len(chapter_files)} chapters generated")

    return len(chapter_files) == 3


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("CLEAN ARCHITECTURE TEST SUITE")
    print("=" * 60)

    tests = [
        ("Simple TTS", test_simple_tts),
        ("Book Manifest", test_manifest),
        ("Orchestrator Simulation", test_orchestrator_simulation),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"\n❌ Test '{test_name}' crashed: {e}")
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    for test_name, success in results:
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status}: {test_name}")

    passed = sum(1 for _, s in results if s)
    total = len(results)
    print(f"\nTotal: {passed}/{total} tests passed")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())