"""
This script translates a large Markdown text from a specified source language to a simplified version
of a specified target language using GPT-4o. The goal is to simplify the vocabulary to roughly 2,000–3,000 words,
so that the translation is accessible to someone with a limited vocabulary, while preserving the original intent,
context, formatting, and approximate text length.

It handles texts that are too large for GPT-4o's context window by splitting them into smaller "pages" (chunks)
of approximately 250 words each (using sentence-boundary splitting and optional overlap), and processing each chunk individually.
Any significant ambiguities are noted with numbered footnotes, which are globally renumbered and appended at the end
of the final output.

Additionally, the script logs the sizes of the input and output texts (in characters and words) to verify translation completeness.

Usage:
    python translator_o3_mini_simple.py input_file.md

Requirements:
    - Python 3
    - The openai Python package (install via: pip install openai)
    - The tqdm package for progress logging (install via: pip install tqdm)
    - An environment variable OPENAI_API_KEY set to your OpenAI API key.

Notes:
    This script uses the modern OpenAI chat completions API for GPT-4o models.
    Ensure you are using openai>=1.0.0.
"""

import os
import sys
import re
import openai
import logging
from tqdm import tqdm
from datetime import datetime

# Set up logging for progress and debug messages.
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Set the OpenAI API key from the environment variable.
openai.api_key = os.environ.get("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("Please set the OPENAI_API_KEY environment variable.")

def chunk_text(text, max_words=250, overlap_sentences=0):
    """
    Splits the input text into chunks that are approximately max_words long,
    ensuring that sentences are not cut off mid-way. Optionally, includes overlap
    of the last N sentences between chunks to preserve context.

    Args:
        text (str): The input Markdown text.
        max_words (int): Approximate maximum words per chunk.
        overlap_sentences (int): Number of sentences to overlap between chunks.

    Returns:
        List[str]: A list of text chunks.
    """
    # Split text into sentences (using punctuation followed by whitespace)
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk_sentences = []
    current_word_count = 0

    for sentence in sentences:
        sentence_word_count = len(sentence.split())

        # If a single sentence is longer than max_words, force a break on words.
        if sentence_word_count > max_words:
            if current_chunk_sentences:
                chunk = " ".join(current_chunk_sentences)
                chunks.append(chunk)
                current_chunk_sentences = []
                current_word_count = 0
            words = sentence.split()
            for i in range(0, len(words), max_words):
                chunk = " ".join(words[i:i+max_words])
                chunks.append(chunk)
            continue

        if current_word_count + sentence_word_count <= max_words:
            current_chunk_sentences.append(sentence)
            current_word_count += sentence_word_count
        else:
            chunk = " ".join(current_chunk_sentences)
            chunks.append(chunk)
            # Include overlap from the end of the previous chunk if needed.
            if overlap_sentences > 0:
                overlap = current_chunk_sentences[-overlap_sentences:]
            else:
                overlap = []
            current_chunk_sentences = overlap + [sentence]
            current_word_count = sum(len(s.split()) for s in current_chunk_sentences)

    if current_chunk_sentences:
        chunk = " ".join(current_chunk_sentences)
        chunks.append(chunk)

    return chunks

def replace_marker(match, footnote_map):
    """
    Replaces a local footnote marker with its corresponding global marker.

    Args:
        match (re.Match): The regex match object for a footnote marker.
        footnote_map (dict): Mapping from local marker numbers (str) to global marker numbers (str).

    Returns:
        str: The updated footnote marker in the format [^global_number].
    """
    local_number = match.group(1)
    global_number = footnote_map.get(local_number, local_number)
    return f"[^{global_number}]"

def translate_chunk(chunk, chunk_number, source_lang, target_lang):
    """
    Calls the GPT-4o API to translate a text chunk from the specified source language
    to a simplified version of the specified target language using only a vocabulary of roughly 2,000–3,000 words.

    IMPORTANT: The prompt below contains all necessary instructions:
      - Translate a Markdown text while preserving the original intent, context, and formatting.
      - Simplify the language so that it uses only approximately 2,000–3,000 words, without dumbing down the content.
      - Ensure the translated output is roughly the same size (in words and characters) as the original.
      - Do not omit any parts of the text.
      - If any significant ambiguities are detected, annotate them with numbered footnotes.
      - At the end of the translation, include a 'Footnotes:' section (only if needed).

    Args:
        chunk (str): The text chunk to translate.
        chunk_number (int): The current chunk number (for prompt context).
        source_lang (str): The language of the input text.
        target_lang (str): The desired output language.

    Returns:
        str: The raw translated text (including any footnotes) returned by GPT-4o.
    """
    prompt_instructions = f"""
You will be provided with a piece of text in Markdown format in {source_lang}. Please translate this text into modern {target_lang},
but simplify the language so that it can be understood by someone with a vocabulary of only 2,000–3,000 words. Do this without dumbing down
the content; preserve the original intent, context, and formatting, and keep the translated text roughly the same size (in terms of words and characters)
as the original. 

IMPORTANT: Translate the entire text without omitting any part. If you encounter significant ambiguities, annotate them with numbered footnotes 
using markers like [^1], [^2], etc. At the end of the translation, include a 'Footnotes:' section listing all footnotes with their corresponding numbers.
If there are no ambiguities, output only the translated text without a 'Footnotes:' section.

Text (Page {chunk_number}):
{chunk}
"""
    messages = [
        {
            "role": "system",
            "content": f"You are a helpful assistant that translates texts from {source_lang} to simplified modern {target_lang} using a limited vocabulary (about 2,000–3,000 words) while preserving meaning, context, and formatting."
        },
        {"role": "user", "content": prompt_instructions}
    ]
    
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.7,
        max_completion_tokens=2000
    )
    return response.choices[0].message.content

def parse_translation(translated_text):
    """
    Parses the translated text into the main translation and a dictionary of footnotes.

    Args:
        translated_text (str): The full text returned by GPT-4o, potentially including a Footnotes section.

    Returns:
        Tuple[str, dict]: A tuple where the first element is the translation text (str) and the second element
                          is a dictionary mapping local footnote numbers (str) to their corresponding footnote text.
    """
    if "Footnotes:" in translated_text:
        parts = translated_text.split("Footnotes:", 1)
        translation_part = parts[0].strip()
        footnotes_part = parts[1].strip()
        footnote_matches = re.findall(r"\[\^(\d+)\]:\s*(.+)", footnotes_part)
        footnotes = {marker: text.strip() for marker, text in footnote_matches}
    else:
        translation_part = translated_text.strip()
        footnotes = {}
    return translation_part, footnotes

def main():
    """
    Main function to:
      1. Read a large Markdown text from an input file (provided as a command-line argument).
      2. Ask the user for the source language and the desired target language.
      3. Split the text into manageable pages (chunks) of about 250 words (using sentence boundaries).
      4. Translate each page using GPT-4o via separate API calls to simplify the language.
      5. Assemble and output the final translated Markdown text with a consolidated Footnotes section.
      6. Log the sizes of the input and output texts (in characters and words) to verify translation completeness.

    Usage:
        python translator_o3_mini_simple.py input_file.md
    """
    if len(sys.argv) < 2:
        logging.error("Usage: python translator_o3_mini_simple.py input_file.md")
        sys.exit(1)
    
    input_file = sys.argv[1]
    logging.info(f"Reading input file: {input_file}")
    
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            input_text = f.read()
    except Exception as e:
        logging.error(f"Error reading input file: {e}")
        sys.exit(1)
    
    # Ask the user for source and target languages.
    source_language = input("Enter the source language (e.g., English, Spanish, German): ").strip()
    target_language = input("Enter the target language (e.g., Spanish, French, Mexican Spanish): ").strip()

    logging.info(f"Simplifying translation from {source_language} to modern {target_language} using simplified vocabulary.")

    input_chars = len(input_text)
    input_words = len(input_text.split())
    logging.info(f"Input size: {input_chars} characters, {input_words} words.")
    
    chunks = chunk_text(input_text, max_words=250, overlap_sentences=1)
    total_chunks = len(chunks)
    logging.info(f"Input text split into {total_chunks} page(s).")
    
    translated_chunks = []
    global_footnotes = []
    footnote_counter = 1  # Global counter for footnotes.
    global_footnote_map = {}  # Maps local footnote numbers to global numbers.
    
    for idx, chunk in enumerate(tqdm(chunks, desc="Translating pages", unit="page"), start=1):
        logging.info(f"Processing page {idx} of {total_chunks}...")
        try:
            raw_translation = translate_chunk(chunk, idx, source_language, target_language)
        except Exception as e:
            logging.error(f"Error processing page {idx}: {e}")
            continue
        
        translation_text, local_footnotes = parse_translation(raw_translation)
        
        # Remap local footnotes to global numbering.
        for local_marker, note_text in local_footnotes.items():
            if local_marker not in global_footnote_map:
                global_marker = str(footnote_counter)
                global_footnote_map[local_marker] = global_marker
                global_footnotes.append(f"[^{global_marker}]: {note_text}")
                footnote_counter += 1
        
        adjusted_translation = re.sub(
            r"\[\^(\d+)\]",
            lambda match: replace_marker(match, global_footnote_map),
            translation_text
        )
        translated_chunks.append(adjusted_translation)
    
    final_output = "\n\n".join(translated_chunks)
    if global_footnotes:
        final_output += "\n\nFootnotes:\n" + "\n".join(global_footnotes)
    else:
        final_output += "\n\nNo significant ambiguities identified."
    
    output_chars = len(final_output)
    output_words = len(final_output.split())
    logging.info(f"Output size: {output_chars} characters, {output_words} words.")
    
    base_filename = os.path.splitext(os.path.basename(input_file))[0]
    current_date = datetime.now().strftime("%d_%m_%Y")
    output_file = f"{base_filename}_{source_language}_To_Simplified_{target_language}_{current_date}_4o-mini_.md"
    
    try:
        with open(output_file, "w", encoding="utf-8") as out_f:
            out_f.write(final_output)
        logging.info(f"Translation complete. The simplified translated file is: {output_file}")
    except Exception as e:
        logging.error(f"Error writing output file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
