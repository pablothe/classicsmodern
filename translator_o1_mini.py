import os
import sys
import textwrap
import openai

def chunk_text(text, max_chunk_size=2000):
    """
    Splits the input text into chunks not exceeding max_chunk_size characters.
    Attempts to split at paragraph boundaries for readability.
    
    Args:
        text (str): The large Markdown text to be split.
        max_chunk_size (int): Maximum number of characters per chunk.
        
    Returns:
        List[str]: A list of text chunks.
    """
    paragraphs = text.split('\n\n')
    chunks = []
    current_chunk = ""
    
    for para in paragraphs:
        if len(current_chunk) + len(para) + 2 <= max_chunk_size:
            current_chunk += para + '\n\n'
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            if len(para) > max_chunk_size:
                # If a single paragraph is too long, split it by lines
                lines = para.split('\n')
                for line in lines:
                    if len(line) + len(current_chunk) + 1 > max_chunk_size:
                        if current_chunk:
                            chunks.append(current_chunk.strip())
                        current_chunk = line + '\n'
                    else:
                        current_chunk += line + '\n'
            else:
                current_chunk = para + '\n\n'
    if current_chunk:
        chunks.append(current_chunk.strip())
        
    return chunks

def translate_chunk(chunk, translation_history):
    """
    Translates a single text chunk into modern English using the OpenAI GPT-4 API.
    Collects any footnotes indicating ambiguities from the translation.
    
    Args:
        chunk (str): The text chunk to translate.
        translation_history (str): The accumulated translation history to maintain style.
        
    Returns:
        Tuple[str, List[str]]: Translated text and a list of footnotes.
    """
    prompt = (
        "You are a translator that converts the following text into modern English, preserving its meaning and context. "
        "If there are any significant ambiguities in the original text, add a footnote marker like [^1] at the end of the relevant sentence and provide the explanation in a separate footnotes section. "
        "Ensure consistency in translation style across all chunks.\n\n"
        f"Translated Text:\n"
    )
    
    try:
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that translates text into modern English."},
                {"role": "user", "content": prompt + chunk}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        
        translated_content = response['choices'][0]['message']['content']
        
        # Split translated content into text and footnotes
        if "\nFootnotes:\n" in translated_content:
            translated_text, footnotes_section = translated_content.split("\nFootnotes:\n", 1)
            footnotes = footnotes_section.strip().split('\n')
        else:
            translated_text = translated_content
            footnotes = []
        
        return translated_text.strip(), footnotes
    except Exception as e:
        print(f"Error during translation: {e}")
        return "", []

def main():
    """
    Main function to execute the translation process.
    Reads input Markdown, translates it in chunks, collects footnotes, and writes the output.
    """
    if len(sys.argv) != 3:
        print("Usage: python translator.py input.md output.md")
        sys.exit(1)
    
    input_file = sys.argv[1]
    output_file = sys.argv[2]
    
    # Ensure OpenAI API key is set
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: The OPENAI_API_KEY environment variable is not set.")
        sys.exit(1)
    openai.api_key = api_key
    
    # Read the input Markdown file
    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            markdown_text = f.read()
    except FileNotFoundError:
        print(f"Error: The file {input_file} was not found.")
        sys.exit(1)
    
    # Split the text into chunks
    chunks = chunk_text(markdown_text)
    print(f"Total chunks to translate: {len(chunks)}")
    
    translated_chunks = []
    all_footnotes = []
    
    translation_history = ""
    
    for i, chunk in enumerate(chunks, 1):
        print(f"Translating chunk {i}/{len(chunks)}...")
        translated_text, footnotes = translate_chunk(chunk, translation_history)
        translated_chunks.append(translated_text)
        if footnotes:
            all_footnotes.extend(footnotes)
        # Optionally, update translation_history if needed for maintaining style
        translation_history += translated_text + "\n\n"
    
    # Assemble the final translated text
    final_translation = "\n\n".join(translated_chunks)
    
    # Add Footnotes section
    final_translation += "\n\n## Footnotes\n\n"
    if all_footnotes:
        for idx, footnote in enumerate(all_footnotes, 1):
            final_translation += f"[^{idx}]: {footnote}\n"
    else:
        final_translation += "No significant ambiguities identified."
    
    # Write the translated Markdown to the output file
    try:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(final_translation)
        print(f"Translation complete. Output written to {output_file}")
    except Exception as e:
        print(f"Error writing to output file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()