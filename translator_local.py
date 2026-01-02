#!/usr/bin/env python3
"""
Universal Book Translator - Local LLM Version
Translates old books into multiple languages using your local LLM API.
Modified to work with your modular LLM API system.
"""

import os
import sys
import re
import logging
import argparse
import time
import asyncio
import requests
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from tqdm import tqdm

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Local LLM model configurations
MODELS = {
    'llama3.2:3b': {
        'name': 'llama3.2:3b',
        'description': 'Fast 3B parameter model, good for quick translations'
    },
    'deepseek-r1:14b': {
        'name': 'deepseek-r1:14b', 
        'description': 'Larger 14B model with better reasoning for complex translations'
    },
    'llama3.2:latest': {
        'name': 'llama3.2:latest',
        'description': 'Latest Llama 3.2 model (same as 3b but different identifier)'
    },
    'mistral:7b': {
        'name': 'mistral:7b',
        'description': 'Mistral 7B - Best open source language model, excellent for complex translations'
    }
}

class LocalLLMClient:
    """Client for communicating with your local LLM API"""
    
    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url
        self.session = requests.Session()
        # Test connection
        try:
            response = self.session.get(f"{base_url}/")
            response.raise_for_status()
            logging.info(f"✅ Connected to local LLM API at {base_url}")
        except Exception as e:
            logging.error(f"❌ Failed to connect to local LLM API: {e}")
            raise
    
    def chat_completion(self, model: str, messages: List[Dict], **kwargs) -> Dict:
        """
        Send a chat completion request to your local API
        Mimics OpenAI's chat.completions.create() interface
        """
        # Convert messages to a single prompt (your API expects a single prompt)
        prompt = self._messages_to_prompt(messages)
        
        payload = {
            "prompt": prompt,
            "model": model
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/query",
                json=payload,
                timeout=300  # 5 minutes timeout for long translations
            )
            response.raise_for_status()
            
            # Convert your API response to OpenAI-like format
            local_response = response.json()
            
            # Handle error responses
            if "error" in local_response:
                raise Exception(f"Local LLM error: {local_response['error']['message']}")
            
            # Convert to OpenAI-like response format
            return {
                "choices": [{
                    "message": {
                        "content": local_response["choices"][0]["message"]["content"]
                    }
                }],
                "usage": local_response.get("usage", {}),
                "model": model,
                "id": local_response.get("id")
            }
            
        except requests.exceptions.Timeout:
            raise Exception("Translation request timed out")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error: {e}")
    
    def _messages_to_prompt(self, messages: List[Dict]) -> str:
        """Convert OpenAI messages format to single prompt"""
        prompt_parts = []
        
        for message in messages:
            role = message["role"]
            content = message["content"]
            
            if role == "system":
                prompt_parts.append(f"Instructions: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
        
        return "\n\n".join(prompt_parts)

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
    client: LocalLLMClient,
    chunk: str,
    chunk_number: int,
    source_lang: str,
    target_lang: str,
    model: str,
    max_retries: int = 3
) -> str:
    """
    Translates a text chunk using your local LLM API.
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
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    # Retry logic
    for attempt in range(max_retries):
        try:
            logging.info(f"🔄 Translating chunk {chunk_number} with {model} (attempt {attempt + 1})")
            
            response = client.chat_completion(model=model, messages=messages)
            translated_text = response["choices"][0]["message"]["content"]
            
            processing_time = response.get("usage", {}).get("processing_time", 0)
            logging.info(f"✅ Chunk {chunk_number} completed in {processing_time:.1f}s")
            
            return enforce_markdown_spacing(translated_text)
                
        except Exception as e:
            logging.warning(f"⚠️  Attempt {attempt + 1} failed for chunk {chunk_number}: {str(e)}")
            if attempt == max_retries - 1:
                raise
            time.sleep(2 ** attempt)  # Exponential backoff
    
    raise RuntimeError(f"Failed to translate chunk {chunk_number} after {max_retries} attempts")

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

def translate_book(
    input_file: str,
    source_lang: str,
    target_lang: str,
    model: str,
    output_dir: Optional[str] = None,
    chunk_size: int = 250,
    api_url: str = "http://localhost:8080"
) -> str:
    """Translate a book using your local LLM API"""
    
    # Setup
    client = LocalLLMClient(api_url)
    
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
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    output_file = output_path / f"{base_name}_{target_lang.lower().replace(' ', '_')}_{timestamp}_{model.replace(':', '_')}.md"
    
    # Process chunks
    chunks = chunk_text(input_text, max_words=chunk_size)
    translated_chunks = []
    
    logging.info(f"📚 Processing {len(chunks)} chunks sequentially (due to local API queue)")
    
    start_time = time.time()
    
    for idx, chunk in enumerate(tqdm(chunks, desc="Translating chunks", unit="chunk"), start=1):
        try:
            translated_chunk = translate_chunk(
                client, chunk, idx, source_lang, target_lang, model
            )
            translated_chunks.append(translated_chunk)
        except Exception as e:
            logging.error(f"❌ Error processing chunk {idx}: {e}")
            translated_chunks.append(f"[ERROR: Translation failed for chunk {idx}]")
    
    total_time = time.time() - start_time
    
    # Save output
    final_output = "\n\n".join(translated_chunks)
    output_file.write_text(final_output, encoding="utf-8")
    
    # Copy original if needed
    original_file = output_path / f"{base_name}_original.md"
    if not original_file.exists():
        original_file.write_text(input_text, encoding="utf-8")
        logging.info(f"📄 Original file copied to: {original_file}")
    
    logging.info(f"⏱️  Total translation time: {total_time:.1f} seconds")
    logging.info(f"📊 Average time per chunk: {total_time/len(chunks):.1f} seconds")
    
    return str(output_file)

def main():
    parser = argparse.ArgumentParser(
        description='Universal Book Translator with Local LLM API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s book.md --model llama3.2:3b -s English -t Spanish
  %(prog)s book.md --model deepseek-r1:14b -s French -t English
  %(prog)s book.md --api-url http://localhost:8080
        """
    )
    
    parser.add_argument('input_file', nargs='?', help='Input markdown file to translate')
    parser.add_argument('--model', '-m', choices=list(MODELS.keys()), default='llama3.2:3b',
                       help='Local LLM model to use (default: llama3.2:3b)')
    parser.add_argument('--source-lang', '-s', help='Source language (interactive if not provided)')
    parser.add_argument('--target-lang', '-t', help='Target language (interactive if not provided)')
    parser.add_argument('--output-dir', '-o', help='Output directory (defaults to book-specific folder)')
    parser.add_argument('--chunk-size', '-c', type=int, default=200,
                       help='Words per chunk for translation (default: 200, smaller for local models)')
    parser.add_argument('--api-url', default='http://localhost:8080',
                       help='Local LLM API URL (default: http://localhost:8080)')
    parser.add_argument('--list-models', action='store_true', help='List available models and exit')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Configure logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # List models if requested
    if args.list_models:
        print("Available Local LLM Models:")
        print("=" * 80)
        for key, config in MODELS.items():
            print(f"  {key:15} | {config['description']}")
        print()
        return
    
    # Validate input
    if not args.input_file:
        parser.error("input_file is required unless using --list-models")
    
    if not Path(args.input_file).exists():
        logging.error(f"Input file not found: {args.input_file}")
        sys.exit(1)
    
    # Get languages
    source_language = args.source_lang or input("Enter the source language: ").strip()
    target_language = args.target_lang or input("Enter the target language: ").strip()
    
    logging.info(f"🌍 Translating from {source_language} to {target_language}")
    logging.info(f"🤖 Using model: {args.model} - {MODELS[args.model]['description']}")
    logging.info(f"🔗 API URL: {args.api_url}")
    
    try:
        output_file = translate_book(
            args.input_file,
            source_language,
            target_language,
            args.model,
            args.output_dir,
            args.chunk_size,
            args.api_url
        )
        
        logging.info(f"🎉 Translation complete! Output saved to: {output_file}")
        
    except KeyboardInterrupt:
        logging.info("Translation interrupted by user")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Translation failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()