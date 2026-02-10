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

def extract_toc_and_structure(text):
    """
    Extract table of contents and document structure to preserve them through translation.
    Returns the TOC, structure map, and the content for translation.
    """
    # Extract table of contents section if it exists
    toc_match = re.search(r'(###\s*Table of Contents.*?)(?=##|$)', text, re.DOTALL)
    toc = toc_match.group(1) if toc_match else ""
    
    # Create a map of all headers and their link IDs
    header_pattern = r'^(#{1,6})\s+(.+?)(?:\s*\{#([^}]+)\})?\s*$'
    headers = re.finditer(header_pattern, text, re.MULTILINE)
    
    structure_map = {}
    for match in headers:
        level = len(match.group(1))
        header_text = match.group(2).strip()
        header_id = match.group(3) if match.group(3) else None
        
        # If no ID is specified, look for link references in TOC
        if not header_id and toc:
            id_match = re.search(r'\[' + re.escape(header_text) + r'\]\(#([^)]+)\)', toc)
            if id_match:
                header_id = id_match.group(1)
        
        structure_map[header_text] = {
            'level': level,
            'id': header_id
        }
    
    # Also extract special markdown elements like links, tables, etc.
    special_elements = {
        'links': re.findall(r'\[([^\]]+)\]\(([^)]+)\)', text),
        'images': re.findall(r'!\[([^\]]*)\]\(([^)]+)\)', text),
        'tables': re.findall(r'(\|.+\|[\r\n]+\|[-:| ]+\|[\r\n]+((?:\|.+\|[\r\n]+)+))', text, re.DOTALL)
    }
    
    return toc, structure_map, special_elements

def identify_markdown_sections(text):
    """
    Identify and preserve Markdown sections like headers, code blocks, etc.
    Returns a list of sections with their type and content.
    """
    # Split text into logical sections
    sections = []
    
    # Regex patterns for different section types
    patterns = {
        'header1': r'^(#\s+.+)$',
        'header2': r'^(##\s+.+)$',
        'header3': r'^(###\s+.+)$',
        'header4': r'^(####\s+.+)$',
        'header5': r'^(#####\s+.+)$',
        'header6': r'^(######\s+.+)$',
        'code_block': r'```[\s\S]*?```',
        'block_quote': r'^(>\s+.+)$',
        'list_item': r'^(\s*[-*+]\s+.+)$',
        'numbered_list': r'^(\s*\d+\.\s+.+)$',
        'horizontal_rule': r'^(\s*[-*_]{3,}\s*)$',
        'table': r'^\s*\|.+\|\s*$'
    }
    
    # Current section buffer
    current_type = 'paragraph'
    current_content = []
    
    # Process line by line
    lines = text.split('\n')
    i = 0
    while i < len(lines):
        line = lines[i]
        section_type = None
        
        # Check for section type
        for type_name, pattern in patterns.items():
            if re.match(pattern, line, re.MULTILINE):
                section_type = type_name
                break
        
        # Handle special case of code blocks
        if line.strip().startswith('```'):
            # Find the end of the code block
            start = i
            i += 1
            while i < len(lines) and not lines[i].strip().startswith('```'):
                i += 1
            
            if i < len(lines):  # Include closing ```
                i += 1
            
            code_block = '\n'.join(lines[start:i])
            sections.append(('code_block', code_block))
            continue
        
        # Handle ordinary sections
        if section_type:
            # If we were building a paragraph, save it
            if current_content and current_type == 'paragraph':
                sections.append((current_type, '\n'.join(current_content)))
                current_content = []
            
            # Start a new section
            sections.append((section_type, line))
        else:
            # If line is empty and we have content, complete current section
            if not line.strip() and current_content:
                sections.append((current_type, '\n'.join(current_content)))
                current_content = []
                sections.append(('blank', ''))
            # Otherwise add to paragraph
            elif line.strip():
                if not current_content:  # Start new paragraph
                    current_type = 'paragraph'
                current_content.append(line)
        
        i += 1
    
    # Don't forget the last section
    if current_content:
        sections.append((current_type, '\n'.join(current_content)))
    
    return sections

def chunk_text_with_structure(text, max_words=250):
    """
    Split text into chunks that respect Markdown structure while staying within max_words limit.
    """
    sections = identify_markdown_sections(text)
    chunks = []
    current_chunk = []
    current_word_count = 0
    
    # Keep track of header hierarchy to maintain context
    current_header_context = []
    
    for section_type, content in sections:
        # Track header hierarchy
        if section_type.startswith('header'):
            header_level = int(section_type[-1])  # Extract level from 'header1', 'header2', etc.
            
            # Update header context
            while current_header_context and current_header_context[-1][0] >= header_level:
                current_header_context.pop()
            current_header_context.append((header_level, content))
        
        # Headers with level 1-3 always start a new chunk if the current chunk has content
        if section_type.startswith('header') and int(section_type[-1]) <= 3 and current_chunk:
            chunks.append('\n'.join(current_chunk))
            current_chunk = []
            current_word_count = 0
        
        # Check if adding this section would exceed word count
        section_word_count = len(content.split())
        
        # If it's a large section that exceeds max_words on its own, we need to split it
        if section_word_count > max_words and section_type == 'paragraph':
            # If we have content in the current chunk, finalize it
            if current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
                current_word_count = 0
            
            # For paragraphs, try to split at sentence boundaries rather than arbitrary word positions
            sentences = re.split(r'(?<=[.!?])\s+', content)
            current_sentence_group = []
            current_group_word_count = 0
            
            for sentence in sentences:
                sentence_word_count = len(sentence.split())
                
                if current_group_word_count + sentence_word_count > max_words and current_sentence_group:
                    chunks.append(' '.join(current_sentence_group))
                    current_sentence_group = [sentence]
                    current_group_word_count = sentence_word_count
                else:
                    current_sentence_group.append(sentence)
                    current_group_word_count += sentence_word_count
            
            if current_sentence_group:
                chunks.append(' '.join(current_sentence_group))
        else:
            # If adding this section would exceed limit, create a new chunk
            if current_word_count + section_word_count > max_words and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = []
                current_word_count = 0
            
            # Add the section to the current chunk
            current_chunk.append(content)
            current_word_count += section_word_count
    
    # Don't forget the last chunk
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
    
    return chunks

def translate_chunk(chunk, chunk_number, source_lang, target_lang, toc=None, structure_map=None):
    """
    Calls the GPT-4o API to translate a text chunk while preserving Markdown structure.
    """
    # Prepare special instructions based on the chunk content
    special_instructions = """
    IMPORTANT: DO NOT add ```markdown or any other formatting markers around your translation.
    DO NOT add phrases like 'end chapter' or other section markers.
    Keep the exact same paragraph structure as the original.
    """
    
    # Check if chunk contains headers
    if re.search(r'^(#{1,6}\s+.+)$', chunk, re.MULTILINE):
        special_instructions += """
        - This chunk contains headers. Translate the header text but keep the exact number of hash symbols (#).
        - If headers appear to be section titles or chapter names, preserve any numbering.
        """
    
    # Check if chunk contains links
    if '[' in chunk and '](' in chunk:
        special_instructions += """
        - This chunk contains Markdown links. Translate the link text but DO NOT change the URLs.
        - Keep the format exactly as [translated text](#unchanged_id).
        """
    
    # Check if chunk contains tables
    if '|' in chunk and '\n|' in chunk:
        special_instructions += """
        - This chunk contains Markdown tables. Translate the table content but preserve the table structure.
        - Keep all table delimiters (|) and alignment indicators (:---:) exactly as they are.
        """
    
    # Check if chunk contains code blocks
    if '```' in chunk:
        special_instructions += """
        - If this chunk contains code blocks with actual code, DO NOT translate the code itself, only translate comments.
        - If the code blocks are simply wrapping normal text, REMOVE the code block markers and just provide the translated text without the ```marks.
        """
    
    # If we have TOC information and this chunk seems to be part of TOC
    if toc and ("Table of Contents" in chunk or "Inhaltsverzeichnis" in chunk):
        special_instructions += """
        - This chunk appears to be a Table of Contents. Translate the section titles but DO NOT change the link IDs.
        - Keep the format exactly as [translated title](#unchanged_id).
        - Maintain the exact same list structure and indentation.
        """
    
    prompt_instructions = f"""
    You will be provided with a piece of text in Markdown format in {source_lang}. 
    Please translate this text into modern {target_lang}, ensuring that:
    
    - All Markdown formatting remains intact and functional
    - Headers (e.g., #, ##, ###) maintain their exact formatting and hierarchy
    - Lists (numbered and bulleted) maintain their structure
    - Link URLs remain unchanged but link text is translated
    - Table structure is preserved
    - IDs in links like [text](#id) must keep the exact same ID
    - Spacing between paragraphs should be consistent: just one blank line between paragraphs
    
    {special_instructions}
    
    Text (Chunk {chunk_number}):
    {chunk}
    """
    
    messages = [
        {"role": "system", "content": f"You are an expert Markdown translator for {source_lang} to {target_lang}. Your task is to translate precisely while preserving all Markdown formatting and structural elements."},
        {"role": "user", "content": prompt_instructions}
    ]

    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.3,  # Lower temperature for more consistent output
        max_completion_tokens=2000
    )
    
    translated_text = response.choices[0].message.content
    
    # Post-processing to ensure Markdown structure is maintained
    translated_text = enforce_markdown_structure(translated_text)
    
    return translated_text

def enforce_markdown_structure(text):
    """
    Ensures correct Markdown formatting is maintained.
    """
    # Remove explicit markdown language identifiers within triple backticks
    text = re.sub(r'```markdown\n', '```\n', text, flags=re.MULTILINE)
    
    # Remove any triple backticks entirely if they're just wrapping normal text
    # This pattern looks for code blocks that don't contain actual code
    text = re.sub(r'```\n((?:[^`]|`[^`]|``[^`])+?)```', r'\1', text, flags=re.DOTALL)
    
    # Fix any excessive newlines (more than 2 consecutive newlines)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Ensure headers are followed by blank lines (but not excessive ones)
    text = re.sub(r'^(#{1,6} .+)(\n[^\n#])', r'\1\n\n\2', text, flags=re.MULTILINE)
    
    # Ensure blank lines between paragraphs
    text = re.sub(r'(\n[^\s\n].+)(\n[^\s\n#])', r'\1\n\n\2', text, flags=re.MULTILINE)
    
    # Remove any "end chapter" markers that might have been added
    text = re.sub(r'\n\s*end chapter\s*\n', '\n\n', text, flags=re.IGNORECASE)
    
    # Preserve actual code blocks formatting (ones that likely contain code)
    text = re.sub(r'```(\w+)?\n(.+?)```', lambda m: f"```{m.group(1) or ''}\n{m.group(2).strip()}\n```", 
                 text, flags=re.DOTALL)
    
    return text

def reassemble_document(translated_chunks, original_text, source_lang, target_lang):
    """
    Reassemble the translated chunks into a complete document while ensuring 
    the document structure and TOC are properly maintained.
    """
    # Extract TOC and structure from original document
    toc, structure_map, special_elements = extract_toc_and_structure(original_text)
    
    # If there's a TOC, translate it as a special chunk to preserve link IDs
    translated_toc = ""
    if toc:
        translated_toc = translate_chunk(toc, 0, source_lang, target_lang, toc, structure_map)
    
    # Process each chunk before joining to remove any added formatting artifacts
    processed_chunks = []
    for chunk in translated_chunks:
        # Apply initial cleanup to each chunk
        cleaned_chunk = chunk.strip()
        # Remove any markdown code block markers around text
        cleaned_chunk = re.sub(r'^```markdown\s*\n', '', cleaned_chunk)
        cleaned_chunk = re.sub(r'\n```\s*$', '', cleaned_chunk)
        processed_chunks.append(cleaned_chunk)
    
    # Join all translated chunks with proper spacing
    assembled_text = "\n\n".join(processed_chunks)
    
    # Check if we need to insert the translated TOC
    if translated_toc:
        # Find appropriate position to insert TOC (after title, before main content)
        title_match = re.search(r'^(#{1,2}\s+.+?)\n+', assembled_text)
        if title_match:
            insert_pos = title_match.end()
            assembled_text = assembled_text[:insert_pos] + "\n\n" + translated_toc + "\n\n" + assembled_text[insert_pos:]
    
    # Ensure consistent formatting for the entire document
    assembled_text = enforce_markdown_structure(assembled_text)
    
    # Final cleanup for any remaining artifacts
    assembled_text = re.sub(r'end chapter', '', assembled_text, flags=re.IGNORECASE)
    
    # More aggressive cleanup for excessive newlines in the entire document
    assembled_text = re.sub(r'\n{3,}', '\n\n', assembled_text)
    
    # Fix excessive spacing in Project Gutenberg header section (common issue)
    assembled_text = re.sub(r'(This ebook is for the use of anyone anywhere[^\n]*)\n\s*\n([^\n]*)', r'\1 \2', assembled_text)
    assembled_text = re.sub(r'(most other parts of the world[^\n]*)\n\s*\n([^\n]*)', r'\1 \2', assembled_text)
    assembled_text = re.sub(r'(whatsoever\.[^\n]*)\n\s*\n([^\n]*)', r'\1 \2', assembled_text)
    assembled_text = re.sub(r'(of the Project Gutenberg License[^\n]*)\n\s*\n([^\n]*)', r'\1 \2', assembled_text)
    assembled_text = re.sub(r'(at[^\n]*www\.gutenberg\.org[^\n]*)\n\s*\n([^\n]*)', r'\1 \2', assembled_text)
    assembled_text = re.sub(r'(you will have to check[^\n]*)\n\s*\n([^\n]*)', r'\1 \2', assembled_text)
    assembled_text = re.sub(r'(before using this eBook[^\n]*)\n\s*\n(Title:[^\n]*)', r'\1\n\n\2', assembled_text)
    
    return assembled_text

def add_translation_metadata(text, source_lang, target_lang):
    """
    Adds translation metadata to the document, including date of translation with year.
    """
    # Get current date in a readable format with year emphasized
    today_date = datetime.now().strftime("%Y-%m-%d")
    year = datetime.now().year
    
    # Create metadata block
    metadata = f"\n\n---\n\n**Translation Information:**\n\n"
    metadata += f"* Translated from {source_lang} to {target_lang}\n"
    metadata += f"* Translation date: {today_date} ({year})\n"
    metadata += f"* Translated using improved Markdown translator v1.1\n"
    metadata += "---\n\n"
    
    # Find the right spot to insert metadata (after title or at the beginning)
    title_match = re.search(r'^(#{1,2}\s+.+?)\n+', text, re.MULTILINE)
    
    if title_match:
        # Insert after the title
        insert_pos = title_match.end()
        result = text[:insert_pos] + metadata + text[insert_pos:]
    else:
        # Insert at the beginning if no title was found
        result = metadata + text
    
    return result

def main():
    if len(sys.argv) < 2:
        logging.error("Usage: python improved_translator.py input_file.md [--debug]")
        sys.exit(1)
    
    input_file = sys.argv[1]
    debug_mode = "--debug" in sys.argv
    
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
    
    # Extract TOC and structure before chunking
    toc, structure_map, special_elements = extract_toc_and_structure(input_text)
    
    # Chunk text with structure preservation
    chunks = chunk_text_with_structure(input_text, max_words=250)
    
    # Save chunks for debugging if requested
    if debug_mode:
        debug_dir = "debug_chunks"
        os.makedirs(debug_dir, exist_ok=True)
        for idx, chunk in enumerate(chunks):
            with open(f"{debug_dir}/chunk_{idx+1}.md", "w", encoding="utf-8") as f:
                f.write(chunk)
        logging.info(f"Saved {len(chunks)} chunks to {debug_dir}/ for debugging")
    
    translated_chunks = []
    
    for idx, chunk in enumerate(tqdm(chunks, desc="Translating chunks", unit="chunk"), start=1):
        logging.info(f"Processing chunk {idx}/{len(chunks)}...")
        try:
            translated = translate_chunk(chunk, idx, source_language, target_language, toc, structure_map)
            translated_chunks.append(translated)
            
            # Save translated chunks for debugging if requested
            if debug_mode:
                with open(f"debug_chunks/translated_chunk_{idx}.md", "w", encoding="utf-8") as f:
                    f.write(translated)
        except Exception as e:
            logging.error(f"Error processing chunk {idx}: {e}")
            continue
    
    # Reassemble the document
    final_output = reassemble_document(translated_chunks, input_text, source_language, target_language)
    
    # Add translation metadata including date
    final_output = add_translation_metadata(final_output, source_language, target_language)
    
    # Save the final translation
    output_file = f"{os.path.splitext(input_file)[0]}_{target_language.lower().replace(' ', '_')}.md"
    
    try:
        with open(output_file, "w", encoding="utf-8") as out_f:
            out_f.write(final_output)
        logging.info(f"Translation complete. The translated file is: {output_file}")
        
        # Verify the output file has correct structure
        logging.info("Performing final verification...")
        
        # Check for common issues in the final output
        verification_issues = []
        
        with open(output_file, "r", encoding="utf-8") as out_f:
            content = out_f.read()
            
            # Check for ```markdown tags
            if "```markdown" in content:
                verification_issues.append("Found ```markdown tags in output")
            
            # Check for "end chapter" text
            if re.search(r'\bend chapter\b', content, re.IGNORECASE):
                verification_issues.append("Found 'end chapter' text in output")
            
            # Check for excessive newlines
            if re.search(r'\n{4,}', content):
                verification_issues.append("Found excessive newlines in output")
        
        if verification_issues:
            logging.warning("Verification found issues in the output file:")
            for issue in verification_issues:
                logging.warning(f" - {issue}")
            logging.info("Applying final cleanup...")
            
            # Apply final cleanup
            with open(output_file, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Final cleanup for any remaining artifacts
            content = re.sub(r'```markdown', '', content)
            content = re.sub(r'end chapter', '', content, flags=re.IGNORECASE)
            content = re.sub(r'\n{3,}', '\n\n', content)
            
            with open(output_file, "w", encoding="utf-8") as f:
                f.write(content)
            
            logging.info("Final cleanup complete.")
        else:
            logging.info("Verification successful - no issues found.")
            
    except Exception as e:
        logging.error(f"Error writing output file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()