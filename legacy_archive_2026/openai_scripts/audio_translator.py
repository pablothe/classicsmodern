#!/usr/bin/env python3
"""
Universal Book Audio Generator
Converts book text files to audio using OpenAI's audio models.
"""

import os
import sys
import re
import openai
import base64
import argparse
import logging
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Voice options available in OpenAI
VOICES = {
    'alloy': 'Neutral, balanced voice',
    'echo': 'Male voice with clear pronunciation',
    'fable': 'British accent, good for storytelling',
    'onyx': 'Deep male voice',
    'nova': 'Young female voice',
    'shimmer': 'Soft female voice'
}

# Audio format options
FORMATS = ['wav', 'mp3', 'flac']

def setup_openai():
    """Initialize OpenAI API key"""
    openai.api_key = os.environ.get("OPENAI_API_KEY")
    if not openai.api_key:
        raise ValueError("Please set the OPENAI_API_KEY environment variable.")

def load_markdown_text(file_path):
    """Reads a Markdown file and returns its text content."""
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    except Exception as e:
        logging.error(f"Error reading file {file_path}: {e}")
        raise

def clean_text_for_audio(text):
    """
    Clean markdown text for better audio generation.
    Removes markdown formatting that doesn't translate well to speech.
    """
    # Remove markdown headers symbols but keep the text
    text = re.sub(r'^(#{1,6})\s+(.+)$', r'\2', text, flags=re.MULTILINE)
    
    # Remove markdown links but keep the text
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    
    # Remove markdown emphasis symbols
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)  # Bold
    text = re.sub(r'\*([^*]+)\*', r'\1', text)      # Italic
    text = re.sub(r'_([^_]+)_', r'\1', text)        # Italic
    
    # Remove code blocks
    text = re.sub(r'```[^`]*```', '', text, flags=re.DOTALL)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    
    # Remove horizontal rules
    text = re.sub(r'^[-*_]{3,}$', '', text, flags=re.MULTILINE)
    
    # Clean up excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'[ \t]+', ' ', text)
    
    # Remove Project Gutenberg headers/footers if present
    text = re.sub(r'^\*\*\* START OF .*? \*\*\*.*?^\*\*\* END OF .*? \*\*\*', '', text, flags=re.MULTILINE | re.DOTALL)
    
    return text.strip()

def chunk_text_for_audio(text, max_chars=4000):
    """
    Split text into chunks suitable for audio generation.
    Tries to break at natural boundaries like paragraphs or sentences.
    """
    if len(text) <= max_chars:
        return [text]
    
    chunks = []
    current_chunk = ""
    paragraphs = text.split('\n\n')
    
    for paragraph in paragraphs:
        # If adding this paragraph would exceed the limit
        if len(current_chunk) + len(paragraph) + 2 > max_chars:
            if current_chunk:
                chunks.append(current_chunk.strip())
                current_chunk = paragraph
            else:
                # Paragraph is too long, split by sentences
                sentences = re.split(r'(?<=[.!?])\s+', paragraph)
                for sentence in sentences:
                    if len(current_chunk) + len(sentence) + 1 > max_chars:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                            current_chunk = sentence
                        else:
                            # Even single sentence is too long, force split
                            words = sentence.split()
                            temp_chunk = ""
                            for word in words:
                                if len(temp_chunk) + len(word) + 1 > max_chars:
                                    if temp_chunk:
                                        chunks.append(temp_chunk.strip())
                                        temp_chunk = word
                                    else:
                                        chunks.append(word)
                                else:
                                    temp_chunk += " " + word if temp_chunk else word
                            if temp_chunk:
                                current_chunk = temp_chunk
                    else:
                        current_chunk += " " + sentence if current_chunk else sentence
        else:
            current_chunk += "\n\n" + paragraph if current_chunk else paragraph
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks

def generate_audio_chunk(text, voice="alloy", format="wav"):
    """Generates audio from text using OpenAI's audio model."""
    client = openai.OpenAI()
    
    # Create a clear instruction for audiobook narration
    instruction = f"Please read the following text aloud as a narrator for an audiobook. Read it naturally and clearly, without adding any commentary or summarization:\n\n{text}"
    
    response = client.chat.completions.create(
        model="gpt-4o-audio-preview",
        messages=[{"role": "user", "content": instruction}],
        modalities=["text", "audio"],
        audio={"voice": voice, "format": format},
        store=True,
    )
    
    # Extract and decode audio data
    audio_data = base64.b64decode(response.choices[0].message.audio.data)
    return audio_data

def get_book_directory(input_file):
    """
    Determine the appropriate book directory based on the input file path.
    Returns the correct book directory path for organizing audio files.
    """
    input_path = Path(input_file)
    
    # If the file is already in a books directory, use that directory
    if 'books' in input_path.parts:
        book_index = input_path.parts.index('books')
        if book_index + 1 < len(input_path.parts):
            # Get the book directory (books/book_name)
            book_name = input_path.parts[book_index + 1]
            return Path('books') / book_name
    
    # Otherwise, try to determine from filename
    base_name = input_path.stem.lower()
    
    book_mappings = {
        'zarathustra': 'books/zarathustra',
        'alice': 'books/alice_adventures',
        'origin': 'books/origin_species',
        'species': 'books/origin_species',
        'brevitate': 'books/de_brevitate_vitae',
        'brevitae': 'books/de_brevitate_vitae',
        'crime': 'books/crime_punishment',
        'punishment': 'books/crime_punishment',
        'quijote': 'books/don_quijote',
        'quixote': 'books/don_quijote',
        'pride': 'books/pride_prejudice',
        'prejudice': 'books/pride_prejudice',
        'cthulhu': 'books/call_cthulhu',
        'winnie': 'books/winnie_pooh',
        'pooh': 'books/winnie_pooh',
        'moby': 'books/moby_dick',
        'gatsby': 'books/great_gatsby',
        'time_machine': 'books/time_machine',
        'metamorphosis': 'books/metamorphosis',
        'war': 'books/war_worlds',
        'sherlock': 'books/sherlock_holmes',
        'great_gatsby': 'books/great_gatsby',
        'call_of_cthulhu': 'books/call_cthulhu',
        'moby_dick': 'books/moby_dick',
        'war_of_worlds': 'books/war_worlds'
    }
    
    for key, directory in book_mappings.items():
        if key in base_name:
            return Path(directory)
    
    # Create a generic directory based on filename
    clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', base_name)
    # Remove common suffixes to get cleaner directory names
    clean_name = re.sub(r'_(cleaned|original|translated|modern|english).*$', '', clean_name)
    return Path(f"books/{clean_name}")

def main():
    parser = argparse.ArgumentParser(description='Universal Book Audio Generator')
    parser.add_argument('input_file', nargs='?', help='Input markdown file to convert to audio')
    parser.add_argument('--voice', '-v', choices=VOICES.keys(), default='alloy',
                       help='Voice to use for audio generation (default: alloy)')
    parser.add_argument('--format', '-f', choices=FORMATS, default='wav',
                       help='Audio format (default: wav)')
    parser.add_argument('--output-dir', '-o', help='Output directory (defaults to book-specific folder)')
    parser.add_argument('--chunk-size', '-c', type=int, default=4000,
                       help='Maximum characters per audio chunk (default: 4000)')
    parser.add_argument('--list-voices', action='store_true', help='List available voices and exit')
    parser.add_argument('--single-file', '-s', action='store_true',
                       help='Combine all chunks into a single audio file (experimental)')
    parser.add_argument('--audio-subdir', action='store_true',
                       help='Create audio files in an "audio" subdirectory within the book folder')
    
    args = parser.parse_args()
    
    # List voices if requested
    if args.list_voices:
        print("Available voices:")
        for voice, description in VOICES.items():
            print(f"  {voice:10} - {description}")
        return
    
    # Check if input file is provided
    if not args.input_file:
        parser.error("input_file is required unless using --list-voices")
    
    # Setup OpenAI
    try:
        setup_openai()
    except ValueError as e:
        logging.error(str(e))
        sys.exit(1)
    
    # Validate input file
    if not os.path.exists(args.input_file):
        logging.error(f"Input file not found: {args.input_file}")
        sys.exit(1)
    
    logging.info(f"Processing file: {args.input_file}")
    logging.info(f"Using voice: {args.voice} - {VOICES[args.voice]}")
    
    # Load and clean text
    try:
        raw_text = load_markdown_text(args.input_file)
        clean_text = clean_text_for_audio(raw_text)
        logging.info(f"Text cleaned. Length: {len(clean_text)} characters")
    except Exception as e:
        logging.error(f"Error processing text: {e}")
        sys.exit(1)
    
    # Determine output directory
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = get_book_directory(args.input_file)
        
        # Optionally create audio subdirectory for better organization
        if args.audio_subdir:
            output_dir = output_dir / "audio"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    logging.info(f"Audio files will be saved to: {output_dir}")
    
    # Generate output filename base
    input_path = Path(args.input_file)
    base_name = input_path.stem
    timestamp = datetime.now().strftime("%Y%m%d")
    
    if args.single_file:
        # Single file output (experimental - may hit API limits)
        output_file = output_dir / f"{base_name}_audiobook_{args.voice}_{timestamp}.{args.format}"
        
        logging.info("Generating single audio file...")
        try:
            audio_data = generate_audio_chunk(clean_text[:32000], args.voice, args.format)  # Limit to avoid API errors
            
            with open(output_file, "wb") as f:
                f.write(audio_data)
            
            logging.info(f"Audio saved to: {output_file}")
            
        except Exception as e:
            logging.error(f"Error generating audio: {e}")
            sys.exit(1)
    else:
        # Multi-file output (recommended)
        chunks = chunk_text_for_audio(clean_text, args.chunk_size)
        logging.info(f"Text split into {len(chunks)} chunks")
        
        audio_files = []
        
        for i, chunk in enumerate(chunks, 1):
            output_file = output_dir / f"{base_name}_part{i:03d}_{args.voice}_{timestamp}.{args.format}"
            
            logging.info(f"Generating audio for chunk {i}/{len(chunks)}...")
            
            try:
                audio_data = generate_audio_chunk(chunk, args.voice, args.format)
                
                with open(output_file, "wb") as f:
                    f.write(audio_data)
                
                audio_files.append(output_file)
                logging.info(f"Saved: {output_file}")
                
            except Exception as e:
                logging.error(f"Error generating audio for chunk {i}: {e}")
                continue
        
        logging.info(f"Audio generation complete. {len(audio_files)} files created in: {output_dir}")
        
        # Create a playlist file
        playlist_file = output_dir / f"{base_name}_audiobook_playlist_{timestamp}.m3u"
        with open(playlist_file, "w") as f:
            f.write("#EXTM3U\n")
            for audio_file in audio_files:
                f.write(f"{audio_file.name}\n")
        
        logging.info(f"Playlist created: {playlist_file}")

if __name__ == "__main__":
    main()