"""
This script translates a large Markdown text into modern English using GPT-4o,
preserving the original intent and context. It handles texts that are too large
for GPT-4o's context window by splitting them into manageable chunks and processing
each chunk individually. Any significant ambiguities detected are annotated with
footnotes, which are globally renumbered and appended at the end of the final output.

Usage:
    python translate_script.py input_file.md

Requirements:
    - Python 3
    - The openai Python package (install via: pip install openai)
    - An environment variable OPENAI_API_KEY set to your OpenAI API key.
    
Notes:
    This script uses the newer chat completions API for GPT-4o models.
    Ensure you are using openai>=1.0.0.
"""

import os
import sys
import re
import openai

# Set the OpenAI API key from the environment variable.
openai.api_key = os.environ.get("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("Please set the OPENAI_API_KEY environment variable.")

def chunk_text(text, max_words=5000):
    """
    Splits the input text into chunks of a maximum number of words.
    This ensures each chunk is small enough for GPT-4o's context window.

    Args:
        text (str): The input Markdown text.
        max_words (int): Maximum words per chunk.

    Returns:
        List[str]: A list of text chunks.
    """
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_words):
        chunk = " ".join(words[i:i + max_words])
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

def translate_chunk(chunk, chunk_number):
    """
    Calls the GPT-4o API to translate a text chunk into modern English.
    The prompt instructs GPT-4o to preserve meaning and context, and to annotate
    significant ambiguities with footnotes.

    Args:
        chunk (str): The text chunk to translate.
        chunk_number (int): The current chunk number (for prompt context).

    Returns:
        str: The raw translated text (including any footnotes) returned by GPT-4o.
    """
    prompt_instructions = f"""
You will be provided with a piece of text in Markdown format. Please translate this text into modern English, preserving the original intent and context. The text should use words commonly used.

If you encounter any significant ambiguities in the text that might change the interpretation, please note them by adding footnotes. In the translation, indicate footnotes with numbered markers like [^1], [^2], etc.

At the end of the translation, include a 'Footnotes:' section where you list all footnotes with their corresponding numbers.
If there are no ambiguities, output only the translated text without a 'Footnotes:' section.

Text (Chunk {chunk_number}):
{chunk}
"""
    messages = [
        {
            "role": "developer",  # or "system" if you prefer the older naming
            "content": (
                "You are a helpful assistant that translates texts to modern English "
                "while preserving meaning and context."
            )
        },
        {"role": "user", "content": prompt_instructions}
    ]

    # The new openai>=1.0 call - note the difference in accessing the response data
    response = openai.chat.completions.create(
        model="gpt-4o",
        messages=messages,
        temperature=0.7,
        max_tokens=2000
    )
    # Access the text using the typed object attributes:
    return response.choices[0].message.content

def parse_translation(translated_text):
    """
    Parses the translated text from GPT-4o into the main translation and a dictionary of footnotes.

    Args:
        translated_text (str): The full text returned by GPT-4o, potentially including a footnotes section.

    Returns:
        Tuple[str, dict]: A tuple where the first element is the translation text (str)
                          and the second element is a dictionary mapping local footnote numbers (str)
                          to their corresponding footnote text.
    """
    if "Footnotes:" in translated_text:
        parts = translated_text.split("Footnotes:", 1)
        translation_part = parts[0].strip()
        footnotes_part = parts[1].strip()
        # Use regex to extract footnote markers and text.
        footnote_matches = re.findall(r"\[\^(\d+)\]:\s*(.+)", footnotes_part)
        footnotes = {marker: text.strip() for marker, text in footnote_matches}
    else:
        translation_part = translated_text.strip()
        footnotes = {}
    return translation_part, footnotes

def main():
    # Check for command-line argument: input file path.
    if len(sys.argv) < 2:
        print("Usage: python translate_script.py input_file.md")
        sys.exit(1)
    input_file = sys.argv[1]

    # Read the input Markdown text from file.
    with open(input_file, "r", encoding="utf-8") as f:
        input_text = f.read()

    # Split the input text into manageable chunks.
    chunks = chunk_text(input_text, max_words=5000)

    translated_chunks = []
    global_footnotes = []
    footnote_counter = 1  # Global counter for footnote numbering.
    global_footnote_map = {}  # Maps local footnote numbers to global numbers.

    # Process each chunk individually.
    for idx, chunk in enumerate(chunks, start=1):
        print(f"Processing chunk {idx} of {len(chunks)}...")
        raw_translation = translate_chunk(chunk, idx)
        translation_text, local_footnotes = parse_translation(raw_translation)

        # Process and remap local footnotes to a global numbering system.
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

    # Build the output filename based on the original file + "_english_to_english"
    output_file = f"{input_file}_english_to_english"

    # Write the final output to the file
    with open(output_file, "w", encoding="utf-8") as out_f:
        out_f.write(final_output)

    print(f"Translation complete. The translated file is: {output_file}")

if __name__ == "__main__":
    main()
