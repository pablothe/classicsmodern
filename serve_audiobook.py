#!/usr/bin/env python3
"""
Simple HTTP server to play audiobooks locally.
Serves the audiobook player and audio files.
"""

import http.server
import socketserver
import webbrowser
from pathlib import Path
import sys


def serve_audiobook(audio_dir: str, port: int = 8000):
    """
    Start a local web server to play the audiobook.

    Args:
        audio_dir: Directory containing audio files
        port: Port to serve on (default: 8000)
    """
    audio_path = Path(audio_dir).absolute()

    if not audio_path.exists():
        raise FileNotFoundError(f"Audio directory not found: {audio_dir}")

    # Change to audio directory so files are served from there
    import os
    os.chdir(audio_path)

    # Copy player HTML to audio directory
    template_path = Path(__file__).parent / "templates" / "audiobook_player.html"
    player_path = audio_path / "player.html"

    if template_path.exists():
        import shutil
        shutil.copy(template_path, player_path)
        print(f"✓ Player copied to: {player_path}")
    else:
        print(f"⚠️  Warning: Player template not found at {template_path}")

    # Start server
    Handler = http.server.SimpleHTTPRequestHandler
    Handler.extensions_map.update({
        '.mp3': 'audio/mpeg',
        '.m3u': 'audio/x-mpegurl',
        '.html': 'text/html'
    })

    with socketserver.TCPServer(("", port), Handler) as httpd:
        url = f"http://localhost:{port}/player.html"

        print("\n" + "="*60)
        print("AUDIOBOOK WEB PLAYER")
        print("="*60)
        print(f"Server running at: http://localhost:{port}")
        print(f"Audio directory: {audio_path}")
        print(f"\nOpen in browser: {url}")
        print("\nPress Ctrl+C to stop")
        print("="*60 + "\n")

        # Try to open browser automatically
        try:
            webbrowser.open(url)
        except:
            pass

        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n\n✓ Server stopped")


def main():
    if len(sys.argv) < 2:
        print("Usage: python serve_audiobook.py <audio_directory> [port]")
        print("\nExample:")
        print("  python serve_audiobook.py books/crime_punishment/chunks/test_chunk/translated/audio/")
        print("  python serve_audiobook.py books/crime_punishment/chunks/test_chunk/translated/audio/ 8080")
        print("\nThis will:")
        print("  1. Start a local web server")
        print("  2. Open the audiobook player in your browser")
        print("  3. Allow you to play the audiobook with progress tracking")
        sys.exit(1)

    audio_dir = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000

    try:
        serve_audiobook(audio_dir, port)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
