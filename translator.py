#!/usr/bin/env python3
"""
Universal Book Translator
Translates old books into multiple languages with configurable AI models.
Updated to use modern OpenAI API practices.
"""

import os
import sys
import re
import logging
import argparse
import time
import asyncio
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from tqdm import tqdm

try:
    from openai import OpenAI, AsyncOpenAI
    from openai.types.chat import ChatCompletion
except ImportError:
    print("Please install the latest OpenAI library: pip install openai>=1.0.0")
    sys.exit(1)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Model configurations with updated parameters
MODELS = {
    'o1-mini': {
        'name': 'o1-mini',
        'max_tokens': 65536,
        'temperature': None,  # o1 models don't support temperature
        'supports_system': False,
        'supports_streaming': False,
        'description': 'Fast and efficient reasoning model for most translations'
    },
    'o1-preview': {
        'name': 'o1-preview', 
        'max_tokens': 32768,
        'temperature': None,
        'supports_system': False,
        'supports_streaming': False,
        'description': 'Higher quality reasoning but slower'
    },
    'o3-mini': {
        'name': 'o3-mini',
        'max_tokens': 65536,
        'temperature': 0.5,
        'supports_system': True,
        'supports_streaming': True,
        'description': 'Latest reasoning model, balanced performance'
    },
    'o3-mini-high': {
        'name': 'o3-mini',
        'max_tokens': 65536,
        'temperature': 0.3,
        'supports_system': True,
        'supports_streaming': True,
        'description': 'Latest reasoning model with high precision (recommended)'
    },
    'gpt-4o': {
        'name': 'gpt-4o',
        'max_tokens': 4096,
        'temperature': 0.3,
        'supports_system': True,
        'supports_streaming': True,
        'description': 'Latest GPT-4 model with vision capabilities'
    },
    'gpt-4o-mini': {
        'name': 'gpt-4o-mini',
        'max_tokens': 16384,
        'temperature': 0.3,
        'supports_system': True,
        'supports_streaming': True,
        'description': 'Fast and cost-effective GPT-4 model'
    },
    'gpt-4-turbo': {
        'name': 'gpt-4-turbo',
        'max_tokens': 4096,
        'temperature': 0.3,
        'supports_system': True,
        'supports_streaming': True,
        'description': 'Previous generation GPT-4 model'
    }
}

def setup_openai_client() -> OpenAI:
    """Initialize OpenAI client with modern API"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Please set the OPENAI_API_KEY environment variable.")
    
    return OpenAI(api_key=api_key)

def setup_async_openai_client() -> AsyncOpenAI:
    """Initialize async OpenAI client for concurrent processing"""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("Please set the OPENAI_API_KEY environment variable.")
    
    return AsyncOpenAI(api_key=api_key)

def chunk_text(text, max_words=250):
    """
    Splits the input text into chunks that are approximately max_words long,
    ensuring that Markdown headers remain separate and are followed by blank lines.
    """
    lines = text.split("\n")
    chunks = []
    current_chunk = []
    current_word_count = 0

    for line in lines:
        line = line.strip()
        
        if re.match(r'^(#{1,6})\s', line):
            if current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = []
                current_word_count = 0
            chunks.append(line + "\n")
            continue

        line_word_count = len(line.split())
        
        if current_word_count + line_word_count > max_words:
            chunks.append("\n".join(current_chunk))
            current_chunk = [line]
            current_word_count = line_word_count
        else:
            current_chunk.append(line)
            current_word_count += line_word_count

    if current_chunk:
        chunks.append("\n".join(current_chunk))
    
    return chunks

def enforce_markdown_spacing(text):
    """
    Ensures that Markdown headers are followed by a blank line.
    """
    text = re.sub(r'^(#{1,6} .+)(\n[^\n#])', r'\1\n\n\2', text, flags=re.MULTILINE)
    return text

def translate_chunk(
    client: OpenAI,
    chunk: str,
    chunk_number: int,
    source_lang: str,
    target_lang: str,
    model_config: Dict,
    max_retries: int = 3,
    use_streaming: bool = False
) -> str:
    """
    Translates a text chunk using the specified AI model with modern API practices.
    Includes retry logic and streaming support.
    """
    system_prompt = f"You are an expert Markdown translator specializing in {source_lang} to {target_lang} translation."
    
    user_prompt = f"""
    Translate the following text into modern {target_lang}, preserving its meaning and context.
    
    Requirements:
    - Maintain all Markdown formatting (headers, lists, emphasis, etc.)
    - Ensure blank lines follow Markdown headers
    - Modernize archaic language while preserving original meaning
    - Make it accessible to contemporary readers
    - Preserve literary style and tone
    
    Text (Chunk {chunk_number}):
    {chunk}
    """
    
    # Prepare messages based on model capabilities
    if model_config['supports_system']:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
    else:
        # For models that don't support system messages (like o1)
        combined_prompt = f"{system_prompt}\n\n{user_prompt}"
        messages = [{"role": "user", "content": combined_prompt}]
    
    # Prepare API parameters
    api_params = {
        "model": model_config['name'],
        "messages": messages,
        "max_completion_tokens": model_config['max_tokens']
    }
    
    # Add temperature for models that support it
    if model_config['temperature'] is not None:
        api_params["temperature"] = model_config['temperature']
    
    # Add streaming if supported and requested
    if use_streaming and model_config['supports_streaming']:
        api_params["stream"] = True
    
    # Retry logic
    for attempt in range(max_retries):
        try:
            if use_streaming and model_config['supports_streaming']:
                return _handle_streaming_response(client, api_params)
            else:
                response = client.chat.completions.create(**api_params)
                translated_text = response.choices[0].message.content
                return enforce_markdown_spacing(translated_text)
                
        except Exception as e:
            logging.warning(f"Attempt {attempt + 1} failed for chunk {chunk_number}: {str(e)}")
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)  # Exponential backoff
    
    raise RuntimeError(f"Failed to translate chunk {chunk_number} after {max_retries} attempts")

def _handle_streaming_response(client: OpenAI, api_params: Dict) -> str:
    """Handle streaming response for real-time translation feedback"""
    full_response = ""
    
    try:
        stream = client.chat.completions.create(**api_params)
        for chunk in stream:
            if chunk.choices[0].delta.content is not None:
                content = chunk.choices[0].delta.content
                full_response += content
                # Optional: Print progress indicator
                print(".", end="", flush=True)
        print()  # New line after streaming
        return enforce_markdown_spacing(full_response)
    except Exception as e:
        logging.error(f"Streaming failed: {e}")
        # Fallback to non-streaming
        api_params.pop("stream", None)
        response = client.chat.completions.create(**api_params)
        return enforce_markdown_spacing(response.choices[0].message.content)

async def translate_chunk_async(
    client: AsyncOpenAI,
    chunk: str,
    chunk_number: int,
    source_lang: str,
    target_lang: str,
    model_config: Dict,
    semaphore: asyncio.Semaphore
) -> Tuple[int, str]:
    """Async version for concurrent processing of multiple chunks"""
    async with semaphore:  # Limit concurrent requests
        try:
            system_prompt = f"You are an expert Markdown translator specializing in {source_lang} to {target_lang} translation."
            
            user_prompt = f"""
            Translate the following text into modern {target_lang}, preserving its meaning and context.
            
            Requirements:
            - Maintain all Markdown formatting (headers, lists, emphasis, etc.)
            - Ensure blank lines follow Markdown headers
            - Modernize archaic language while preserving original meaning
            - Make it accessible to contemporary readers
            - Preserve literary style and tone
            
            Text (Chunk {chunk_number}):
            {chunk}
            """
            
            if model_config['supports_system']:
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            else:
                combined_prompt = f"{system_prompt}\n\n{user_prompt}"
                messages = [{"role": "user", "content": combined_prompt}]
            
            api_params = {
                "model": model_config['name'],
                "messages": messages,
                "max_completion_tokens": model_config['max_tokens']
            }
            
            if model_config['temperature'] is not None:
                api_params["temperature"] = model_config['temperature']
            
            response = await client.chat.completions.create(**api_params)
            translated_text = response.choices[0].message.content
            return chunk_number, enforce_markdown_spacing(translated_text)
            
        except Exception as e:
            logging.error(f"Error translating chunk {chunk_number}: {e}")
            return chunk_number, f"[ERROR: Translation failed for chunk {chunk_number}]"

def get_book_directory(input_file):
    """
    Determine the appropriate book directory based on the input file name.
    Creates the directory if it doesn't exist.
    """
    base_name = os.path.basename(input_file).lower()
    
    # Map common book patterns to directories
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
        'pooh': 'books/winnie_pooh'
    }
    
    # Find matching directory
    book_dir = None
    for key, directory in book_mappings.items():
        if key in base_name:
            book_dir = directory
            break
    
    # If no match found, create a generic directory
    if not book_dir:
        clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', os.path.splitext(base_name)[0])
        book_dir = f"books/{clean_name}"
    
    # Create directory if it doesn't exist
    os.makedirs(book_dir, exist_ok=True)
    
    return book_dir

async def translate_book_async(
    input_file: str,
    source_lang: str,
    target_lang: str,
    model_key: str,
    output_dir: Optional[str] = None,
    max_concurrent: int = 3,
    chunk_size: int = 250
) -> str:
    """Async translation for better performance with concurrent chunk processing"""
    
    # Setup
    client = setup_async_openai_client()
    model_config = MODELS[model_key]
    
    # Read input
    input_path = Path(input_file)
    input_text = input_path.read_text(encoding="utf-8")
    
    # Determine output
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
    else:
        output_path = Path(get_book_directory(input_file))
    
    base_name = input_path.stem
    timestamp = datetime.now().strftime("%Y%m%d")
    output_file = output_path / f"{base_name}_{target_lang.lower().replace(' ', '_')}_{timestamp}_{model_key}.md"
    
    # Process chunks
    chunks = chunk_text(input_text, max_words=chunk_size)
    semaphore = asyncio.Semaphore(max_concurrent)
    
    logging.info(f"Processing {len(chunks)} chunks with up to {max_concurrent} concurrent requests")
    
    # Create tasks for concurrent processing
    tasks = [
        translate_chunk_async(
            client, chunk, idx, source_lang, target_lang, model_config, semaphore
        )
        for idx, chunk in enumerate(chunks, 1)
    ]
    
    # Process with progress bar
    results = []
    with tqdm(total=len(tasks), desc="Translating chunks", unit="chunk") as pbar:
        for coro in asyncio.as_completed(tasks):
            chunk_number, translated_chunk = await coro
            results.append((chunk_number, translated_chunk))
            pbar.update(1)
    
    # Sort results by chunk number to maintain order
    results.sort(key=lambda x: x[0])
    translated_chunks = [chunk for _, chunk in results]
    
    # Save output
    final_output = "\n\n".join(translated_chunks)
    output_file.write_text(final_output, encoding="utf-8")
    
    # Copy original if needed
    original_file = output_path / f"{base_name}_original.md"
    if not original_file.exists():
        original_file.write_text(input_text, encoding="utf-8")
        logging.info(f"Original file copied to: {original_file}")
    
    return str(output_file)

def main():
    parser = argparse.ArgumentParser(
        description='Universal Book Translator with Modern OpenAI API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s book.md --model gpt-4o-mini -s English -t Spanish
  %(prog)s book.md --model o3-mini-high --streaming
  %(prog)s book.md --async --max-concurrent 5
        """
    )
    
    parser.add_argument('input_file', nargs='?', help='Input markdown file to translate')
    parser.add_argument('--model', '-m', choices=MODELS.keys(), default='o3-mini-high',
                       help='AI model to use for translation (default: o3-mini-high)')
    parser.add_argument('--source-lang', '-s', help='Source language (interactive if not provided)')
    parser.add_argument('--target-lang', '-t', help='Target language (interactive if not provided)')
    parser.add_argument('--output-dir', '-o', help='Output directory (defaults to book-specific folder)')
    parser.add_argument('--chunk-size', '-c', type=int, default=250,
                       help='Words per chunk for translation (default: 250)')
    parser.add_argument('--streaming', action='store_true',
                       help='Enable streaming for real-time translation feedback')
    parser.add_argument('--async', action='store_true', dest='use_async',
                       help='Use async processing for faster translation')
    parser.add_argument('--max-concurrent', type=int, default=3,
                       help='Maximum concurrent requests for async mode (default: 3)')
    parser.add_argument('--list-models', action='store_true', help='List available models and exit')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # List models if requested
    if args.list_models:
        print("Available AI Models:")
        print("=" * 80)
        for key, config in MODELS.items():
            streaming = "✓" if config['supports_streaming'] else "✗"
            system = "✓" if config['supports_system'] else "✗"
            temp = f"{config['temperature']}" if config['temperature'] is not None else "N/A"
            print(f"  {key:15} | {config['description']}")
            print(f"                  | Max tokens: {config['max_tokens']:,}")
            print(f"                  | Temperature: {temp} | Streaming: {streaming} | System msgs: {system}")
            print()
        return
    
    # Validate input
    if not args.input_file:
        parser.error("input_file is required unless using --list-models")
    
    if not Path(args.input_file).exists():
        logging.error(f"Input file not found: {args.input_file}")
        sys.exit(1)
    
    # Get model configuration
    model_config = MODELS[args.model]
    logging.info(f"Using model: {args.model} - {model_config['description']}")
    
    # Validate streaming option
    if args.streaming and not model_config['supports_streaming']:
        logging.warning(f"Model {args.model} doesn't support streaming. Disabling streaming.")
        args.streaming = False
    
    # Get languages
    source_language = args.source_lang or input("Enter the source language: ").strip()
    target_language = args.target_lang or input("Enter the target language: ").strip()
    
    logging.info(f"Translating from {source_language} to {target_language}")
    
    try:
        if args.use_async:
            # Use async processing
            output_file = asyncio.run(translate_book_async(
                args.input_file,
                source_language,
                target_language,
                args.model,
                args.output_dir,
                args.max_concurrent,
                args.chunk_size
            ))
        else:
            # Use synchronous processing
            client = setup_openai_client()
            
            # Read input file
            input_text = Path(args.input_file).read_text(encoding="utf-8")
            
            # Determine output
            if args.output_dir:
                output_dir = Path(args.output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)
            else:
                output_dir = Path(get_book_directory(args.input_file))
            
            base_name = Path(args.input_file).stem
            timestamp = datetime.now().strftime("%Y%m%d")
            output_file = output_dir / f"{base_name}_{target_language.lower().replace(' ', '_')}_{timestamp}_{args.model}.md"
            
            # Process chunks
            chunks = chunk_text(input_text, max_words=args.chunk_size)
            translated_chunks = []
            
            for idx, chunk in enumerate(tqdm(chunks, desc="Translating chunks", unit="chunk"), start=1):
                try:
                    translated_chunk = translate_chunk(
                        client, chunk, idx, source_language, target_language,
                        model_config, use_streaming=args.streaming
                    )
                    translated_chunks.append(translated_chunk)
                except Exception as e:
                    logging.error(f"Error processing chunk {idx}: {e}")
                    translated_chunks.append(f"[ERROR: Translation failed for chunk {idx}]")
            
            # Save output
            final_output = "\n\n".join(translated_chunks)
            output_file.write_text(final_output, encoding="utf-8")
            
            # Copy original if needed
            original_file = output_dir / f"{base_name}_original.md"
            if not original_file.exists():
                original_file.write_text(input_text, encoding="utf-8")
                logging.info(f"Original file copied to: {original_file}")
        
        logging.info(f"Translation complete! Output saved to: {output_file}")
        
    except KeyboardInterrupt:
        logging.info("Translation interrupted by user")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Translation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()