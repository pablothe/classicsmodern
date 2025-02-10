
import openai
import os
import sys
import re

# Set your OpenAI API key from the environment variable
openai.api_key = os.environ.get('OPENAI_API_KEY')
if not openai.api_key:
    raise ValueError("Please set the OPENAI_API_KEY environment variable.")

"""
This script translates a large Markdown text into modern English using GPT-4, preserving the original intent and context.
It handles texts that are too large for GPT-4's context window by splitting them into manageable chunks and processes each chunk individually.
Footnotes for significant ambiguities are collected from all chunks and appended at the end of the final output.

Usage:
    python translate_script.py input_file.md

Requirements:
    - Set the OPENAI_API_KEY environment variable with your OpenAI API key.
    - Install the openai Python package: pip install openai
"""

def chunk_text(text, max_words=5000):
    """
    Splits the text into chunks of maximum 'max_words' words.
    Returns a list of text chunks.

    Args:
        text (str): The input text to be split.
        max_words (int): Maximum number of words per chunk.

    Returns:
        List[str]: A list containing chunks of the text.
    """
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_words):
        chunk = ' '.join(words[i:i + max_words])
        chunks.append(chunk)
    return chunks

def replace_marker(match, footnote_map):
    """
    Replaces the original footnote markers with new global markers.

    Args:
        match (re.Match): The regex match object.
        footnote_map (dict): Mapping from original to new footnote markers.

    Returns:
        str: The replaced footnote marker.
    """
    original_marker = match.group(0)
    marker_number = match.group(1)
    new_marker = footnote_map.get(f"^{marker_number}", original_marker)
    return f"[^{new_marker}]"

def main():
    # Check command-line arguments
    if len(sys.argv) < 2:
        print("Usage: python translate_script.py input_file.md")
        sys.exit(1)
    input_file = sys.argv[1]

    # Read the input Markdown text
    with open(input_file, 'r', encoding='utf-8') as f:
        input_text = f.read()

    # Split the text into manageable chunks
    chunks = chunk_text(input_text)

    # Initialize lists to hold translated chunks and footnotes
    translated_chunks = []
    all_footnotes = []

    # Initialize footnote counter and mapping
    footnote_counter = 1  # To keep track of footnote numbering across all chunks
    footnote_map = {}     # Map original footnote numbers to global footnote numbers

    # Process each chunk
    for idx, chunk in enumerate(chunks):
        print(f"Processing chunk {idx + 1} of {len(chunks)}...")

        prompt_instructions = """
You will be provided with a piece of text in Markdown format. Please translate this text into modern English, preserving the original intent and context.

If you encounter any significant ambiguities in the text that might change the interpretation, please note them by adding footnotes. In the translation, indicate footnotes with numbered markers like [^1], [^2], etc.

At the end of the translation, include a 'Footnotes:' section where you list all footnotes with their corresponding numbers.

Please output only the translated text and the footnotes in the following format:

[Translation of the text with footnote markers]

Footnotes:
[^1]: Footnote text 1
[^2]: Footnote text 2

If there are no footnotes, just output the translated text without the 'Footnotes:' section.
        """

        messages = [
            {"role": "system", "content": "You are a helpful assistant that translates texts to modern English while preserving meaning and context."},
            {"role": "user", "content": prompt_instructions},
            {"role": "user", "content": f"Here is the text to translate:\n\n{chunk}"}
        ]

        # Call the OpenAI GPT-4 API to translate the chunk
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            max_tokens=2000,  # Adjust as needed based on chunk size
            n=1
        )

        # Get the assistant's reply
        translated_text = response['choices'][0]['message']['content']

        # Parse the translated text and footnotes
        if "Footnotes:" in translated_text:
            translation_part, footnotes_part = translated_text.split("Footnotes:", 1)
            translation_part = translation_part.strip()
            footnotes_part = footnotes_part.strip()

            # Process footnotes
            footnote_matches = re.findall(r'\[\^(\d+)\]:\s*(.+)', footnotes_part)
            for marker, footnote_text in footnote_matches:
                # Map original footnote numbers to global footnote numbers
                new_marker = str(footnote_counter)
                footnote_map[f"^{marker}"] = new_marker
                all_footnotes.append(f"[^{new_marker}]: {footnote_text.strip()}")
                footnote_counter += 1

            # Replace footnote markers in the translation part
            adjusted_translation = re.sub(
                r'\[\^(\d+)\]',
                lambda match: replace_marker(match, footnote_map),
                translation_part
            )
            translated_chunks.append(adjusted_translation)
        else:
            # No footnotes in this chunk
            translated_chunks.append(translated_text.strip())

    # Assemble the final translated text
    final_output = '\n\n'.join(translated_chunks)

    # Append the footnotes at the end
    if all_footnotes:
        final_output += '\n\nFootnotes:\n'
        final_output += '\n'.join(all_footnotes)
    else:
        final_output += '\n\nNo significant ambiguities identified.'

    # Print the final translated Markdown text
    print("\nFinal Translated Text:\n")
    print(final_output)

if __name__ == "__main__":
    main()
