import os
import sys
import re
import openai
import logging
from tqdm import tqdm
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

openai.api_key = os.environ.get("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("Please set the OPENAI_API_KEY environment variable.")

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
            chunks.append(line + "\n")  # Ensure a blank line after the header
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

def translate_chunk(chunk, chunk_number, source_lang, target_lang):
    """
    Calls the GPT-4o API to translate a text chunk while enforcing correct Markdown formatting.
    """
    prompt_instructions = f"""
    You are a translator that converts the following text into modern {target_lang}, preserving its meaning and context.
    Please ensure that:
    
    - Markdown headers (e.g., #, ##, ###) remain properly formatted.
    - A blank line always follows Markdown headers.
    - Lists and indentation are preserved.
    - It can be read by a modern audience, despite the text being old, modernize it but preserve the meaning and context.

    Text (Page {chunk_number}):
    {chunk}
    """
    
    messages = [
        {"role": "system", "content": f"You are an expert Markdown translator for {source_lang} to {target_lang}."},
        {"role": "user", "content": prompt_instructions}
    ]

    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.5,
        max_completion_tokens=2000
    )
    
    translated_text = response.choices[0].message.content
    return enforce_markdown_spacing(translated_text)

def main():
    if len(sys.argv) < 2:
        logging.error("Usage: python translator_o3_mini_high.py input_file.md")
        sys.exit(1)
    
    input_file = sys.argv[1]
    logging.info(f"Reading input file: {input_file}")
    
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            input_text = f.read()
    except Exception as e:
        logging.error(f"Error reading input file: {e}")
        sys.exit(1)
    
    source_language = input("Enter the source language: ").strip()
    target_language = input("Enter the target language: ").strip()

    logging.info(f"Translating from {source_language} to {target_language}.")

    chunks = chunk_text(input_text, max_words=250)
    translated_chunks = []
    
    for idx, chunk in enumerate(tqdm(chunks, desc="Translating pages", unit="page"), start=1):
        logging.info(f"Processing page {idx}...")
        try:
            translated_chunks.append(translate_chunk(chunk, idx, source_language, target_language))
        except Exception as e:
            logging.error(f"Error processing page {idx}: {e}")
            continue
    
    final_output = "\n\n".join(translated_chunks)
    output_file = f"{os.path.splitext(input_file)[0]}_translated.md"
    
    try:
        with open(output_file, "w", encoding="utf-8") as out_f:
            out_f.write(final_output)
        logging.info(f"Translation complete. The translated file is: {output_file}")
    except Exception as e:
        logging.error(f"Error writing output file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
