"""
This script translates a large Markdown text from a specified source language to a modern version of a specified target language using GPT-4o.
It preserves the original intent, context, and formatting. It handles texts that are too large for GPT-4o's context window by splitting them into
smaller "pages" (chunks) of approximately 250 words each, and processing each chunk individually. Any significant ambiguities detected are annotated 
with footnotes, which are globally renumbered and appended at the end of the final output.

Additionally, the script logs the size of the input and output texts (in characters and words) to compare their sizes. The translated text should be 
roughly the same size as the original.

Usage:
    python translator_o3_mini_high.py input_file.md

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

def chunk_text(text, max_words=250):
    """
    Splits the input text into chunks of a maximum number of words.
    For example, with max_words=250, a 9212-word text will be split into roughly 37 chunks.

    Args:
        text (str): The input Markdown text.
        max_words (int): Maximum words per chunk.

    Returns:
        List[str]: A list of text chunks.
    """
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_words):
        chunk = " ".join(words[i:i+max_words])
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
    to the modern version of the specified target language.
    The prompt instructs GPT-4o to preserve meaning, context, formatting and to translate the entire text without omissions.

    Args:
        chunk (str): The text chunk to translate.
        chunk_number (int): The current chunk number (for prompt context).
        source_lang (str): The language of the input text.
        target_lang (str): The desired output language.

    Returns:
        str: The raw translated text (including any footnotes) returned by GPT-4o.
    """
    # Build dynamic prompt instructions.
    prompt_instructions = f"""
You will be provided with a piece of text in Markdown format in {source_lang}. Please translate this text into Modern {target_lang}.
Ensure that the translation preserves the original intent, context, and formatting exactly as much as possible, while using simple, clear, and modern language.
IMPORTANT: Translate the entire text without omitting any part. The translated output should be roughly the same size (in terms of words and characters) as the original, preserving paragraphs and punctuation.

If you encounter any significant ambiguities in the text that might affect interpretation, please note them by adding footnotes.
Indicate footnotes in the translation with numbered markers like [^1], [^2], etc.
At the end of the translation, include a 'Footnotes:' section where you list all footnotes with their corresponding numbers.
If there are no ambiguities, output only the translated text without a 'Footnotes:' section.

Text (Page {chunk_number}):
{chunk}
"""
    messages = [
        {
            "role": "system",
            "content": f"You are a helpful assistant that translates texts from {source_lang} to Modern {target_lang} while preserving meaning, context, and formatting."
        },
        {"role": "user", "content": prompt_instructions}
    ]
    
    # Use the modern OpenAI chat completions API with max_completion_tokens parameter.
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.7,
        max_completion_tokens=500
    )
    return response.choices[0].message.content

def parse_translation(translated_text):
    """
    Parses the translated text from GPT-4o into the main translation and a dictionary of footnotes.

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
        # Extract footnotes using regex: [^n]: description
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
      2. Ask the user for the source language and the desired output (modern) language.
      3. Split the text into manageable pages (chunks) of about 250 words each.
      4. Translate each page using GPT-4o via separate API calls.
      5. Assemble and output the final translated Markdown text with a consolidated Footnotes section.
      6. Log the sizes of the input and output texts (in characters and words) to verify translation completeness.

    Usage:
        python translator_o3_mini_high.py input_file.md
    """
    if len(sys.argv) < 2:
        logging.error("Usage: python translator_o3_mini_high.py input_file.md")
        sys.exit(1)
    
    input_file = sys.argv[1]
    logging.info(f"Reading input file: {input_file}")
    
    # Read the input Markdown text from file.
    try:
        with open(input_file, "r", encoding="utf-8") as f:
            input_text = f.read()
    except Exception as e:
        logging.error(f"Error reading input file: {e}")
        sys.exit(1)
    
    # Ask the user for source and target languages.
    source_language = input("Enter the source language (e.g., English, Spanish, German): ").strip()
    target_language = input("Enter the target language (e.g., Spanish, French): ").strip()

    # Log the language settings.
    logging.info(f"Translating from {source_language} to Modern {target_language}.")

    # Log the size of the input text.
    input_chars = len(input_text)
    input_words = len(input_text.split())
    logging.info(f"Input size: {input_chars} characters, {input_words} words.")
    
    # Split the input text into pages of ~250 words each.
    chunks = chunk_text(input_text, max_words=250)
    total_chunks = len(chunks)
    logging.info(f"Input text split into {total_chunks} page(s).")
    
    translated_chunks = []
    global_footnotes = []
    footnote_counter = 1  # Global counter for footnote numbering.
    global_footnote_map = {}  # Maps local footnote numbers to global numbers.
    
    # Process each page individually with a progress bar.
    for idx, chunk in enumerate(tqdm(chunks, desc="Translating pages", unit="page"), start=1):
        logging.info(f"Processing page {idx} of {total_chunks}...")
        try:
            raw_translation = translate_chunk(chunk, idx, source_language, target_language)
        except Exception as e:
            logging.error(f"Error processing page {idx}: {e}")
            continue
        
        translation_text, local_footnotes = parse_translation(raw_translation)
        
        # Remap local footnotes to a global numbering system.
        for local_marker, note_text in local_footnotes.items():
            if local_marker not in global_footnote_map:
                global_marker = str(footnote_counter)
                global_footnote_map[local_marker] = global_marker
                global_footnotes.append(f"[^{global_marker}]: {note_text}")
                footnote_counter += 1
        
        # Replace local footnote markers in the translation with global markers.
        adjusted_translation = re.sub(
            r"\[\^(\d+)\]",
            lambda match: replace_marker(match, global_footnote_map),
            translation_text
        )
        translated_chunks.append(adjusted_translation)
    
    # Assemble the final translated Markdown output.
    final_output = "\n\n".join(translated_chunks)
    if global_footnotes:
        final_output += "\n\nFootnotes:\n" + "\n".join(global_footnotes)
    else:
        final_output += "\n\nNo significant ambiguities identified."
    
    # Log the size of the final output.
    output_chars = len(final_output)
    output_words = len(final_output.split())
    logging.info(f"Output size: {output_chars} characters, {output_words} words.")
    
    # Generate the output file name based on the input file title, languages, and the current date.
    base_filename = os.path.splitext(os.path.basename(input_file))[0]
    current_date = datetime.now().strftime("%d_%m_%Y")
    output_file = f"{base_filename}_{source_language}_To_Modern_{target_language}_{current_date}.md"
    
    try:
        with open(output_file, "w", encoding="utf-8") as out_f:
            out_f.write(final_output)
        logging.info(f"Translation complete. The translated file is: {output_file}")
    except Exception as e:
        logging.error(f"Error writing output file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
