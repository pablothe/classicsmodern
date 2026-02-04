#!/usr/bin/env python3
"""
LLM Chat Integration - Tool-calling AI assistant for audiobooks

Features:
- Tool-calling loop with Ollama llama3.2:3b
- Dynamic chapter retrieval
- Smart context management
- Error handling and timeouts
"""

import re
import json
from pathlib import Path
from typing import Dict, List, Optional
import ollama


class BookTools:
    """Tools available to LLM for querying book content"""

    def __init__(self, book_md_path: Path, chapters_metadata: Optional[List[Dict]] = None):
        """
        Initialize book tools.

        Args:
            book_md_path: Path to source markdown file
            chapters_metadata: List of chapter dicts with {number, title, ...}
        """
        self.book_path = book_md_path
        self.chapters = chapters_metadata or []
        self._cached_text = None
        self._chapter_boundaries = None

    def _load_book_text(self) -> str:
        """Load and cache full book text"""
        if self._cached_text is None:
            with open(self.book_path, 'r', encoding='utf-8') as f:
                self._cached_text = f.read()
        return self._cached_text

    def _detect_chapter_boundaries(self) -> List[Dict]:
        """
        Detect chapter start positions in markdown.

        Returns:
            List of {number, title, start_line, end_line}
        """
        if self._chapter_boundaries is not None:
            return self._chapter_boundaries

        text = self._load_book_text()
        lines = text.split('\n')
        boundaries = []

        # Multiple patterns for different chapter formats
        patterns = [
            # Pattern 1: ## CHAPTER I. or ## CHAPTER 1. or # Chapter 1:
            re.compile(r'#{1,3}\s*(CHAPTER|Chapter)\s+([IVXLCDM]+|\d+)\.?\s*(.*?)$', re.IGNORECASE),

            # Pattern 2: Numbered list format: "1. The Horror in Clay."
            re.compile(r'^(\d+)\.\s+(.+?)$'),

            # Pattern 3: Roman numeral without "Chapter" keyword: "I. Title" or "I - Title"
            re.compile(r'^([IVXLCDM]+)[\.:\-]\s+(.+?)$'),
        ]

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Try each pattern
            for pattern_idx, pattern in enumerate(patterns):
                match = pattern.search(line if pattern_idx == 0 else line_stripped)
                if match:
                    if pattern_idx == 0:  # Markdown chapter format
                        chapter_num_str = match.group(2)
                        chapter_title = match.group(3).strip()
                    elif pattern_idx == 1:  # Numbered list: "1. Title"
                        chapter_num_str = match.group(1)
                        chapter_title = match.group(2).strip()
                    else:  # Roman numeral: "I. Title"
                        chapter_num_str = match.group(1)
                        chapter_title = match.group(2).strip()

                    # Convert to chapter number
                    if chapter_num_str.isdigit():
                        chapter_num = int(chapter_num_str)
                    elif chapter_num_str.upper() in ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII', 'XIII', 'XIV', 'XV']:
                        roman_map = {'I': 1, 'II': 2, 'III': 3, 'IV': 4, 'V': 5, 'VI': 6, 'VII': 7, 'VIII': 8, 'IX': 9, 'X': 10, 'XI': 11, 'XII': 12, 'XIII': 13, 'XIV': 14, 'XV': 15}
                        chapter_num = roman_map.get(chapter_num_str.upper(), len(boundaries) + 1)
                    else:
                        continue  # Skip if can't parse chapter number

                    boundaries.append({
                        'number': chapter_num,
                        'title': chapter_title,
                        'start_line': i
                    })
                    break  # Stop after first match

        # Set end_line for each chapter
        for i in range(len(boundaries)):
            if i + 1 < len(boundaries):
                boundaries[i]['end_line'] = boundaries[i + 1]['start_line'] - 1
            else:
                boundaries[i]['end_line'] = len(lines) - 1

        self._chapter_boundaries = boundaries
        return boundaries

    def get_chapter(self, chapter_num: int) -> str:
        """
        Retrieve text of specific chapter.

        Args:
            chapter_num: Chapter number (1-indexed)

        Returns:
            Chapter text as markdown string
        """
        boundaries = self._detect_chapter_boundaries()
        text = self._load_book_text()
        lines = text.split('\n')

        # Find matching chapter
        for ch in boundaries:
            if ch['number'] == chapter_num:
                chapter_lines = lines[ch['start_line']:ch['end_line'] + 1]
                return '\n'.join(chapter_lines)

        return f"[Chapter {chapter_num} not found in book]"

    def get_chapters(self, start: int, end: int) -> str:
        """
        Retrieve range of chapters.

        Args:
            start: First chapter number
            end: Last chapter number (inclusive)

        Returns:
            Combined chapter text
        """
        chapters_text = []
        for chapter_num in range(start, end + 1):
            chapter_text = self.get_chapter(chapter_num)
            if "[Chapter" not in chapter_text:  # Skip errors
                chapters_text.append(f"\n--- Chapter {chapter_num} ---\n{chapter_text}")

        return '\n\n'.join(chapters_text) if chapters_text else f"[Chapters {start}-{end} not found]"

    def list_chapters(self) -> List[Dict]:
        """
        Get table of contents with chapter titles.

        Returns:
            List of {number, title}
        """
        if self.chapters:
            # Use metadata if available
            return [{'number': ch['number'], 'title': ch['title']} for ch in self.chapters]
        else:
            # Fallback to detected boundaries
            boundaries = self._detect_chapter_boundaries()
            return [{'number': ch['number'], 'title': ch['title']} for ch in boundaries]

    def get_book_section(self, start_pct: float, end_pct: float) -> str:
        """
        Retrieve section of book by percentage.

        Useful for books without chapters or for percentage-based queries
        like "summarize the first 10%" or "what happens in the middle 50%".

        Args:
            start_pct: Starting percentage (0-100)
            end_pct: Ending percentage (0-100)

        Returns:
            Text from start_pct to end_pct of the book
        """
        text = self._load_book_text()
        total_chars = len(text)

        # Convert percentages to character positions
        start_pos = int(total_chars * (start_pct / 100.0))
        end_pos = int(total_chars * (end_pct / 100.0))

        # Clamp to valid range
        start_pos = max(0, min(start_pos, total_chars))
        end_pos = max(start_pos, min(end_pos, total_chars))

        section = text[start_pos:end_pos]

        # Add context info
        word_count = len(section.split())
        return f"[Section: {start_pct}%-{end_pct}% of book, ~{word_count} words]\n\n{section}"

    def get_full_book(self) -> str:
        """
        Retrieve entire book text.

        Warning: May exceed token limits for large books.

        Returns:
            Full book text
        """
        return self._load_book_text()


def ask_with_tools(
    question: str,
    current_chapter: int,
    tools: BookTools,
    model: str = "llama3.2:3b"
) -> Dict:
    """
    Main LLM query handler with tool-calling loop.

    Flow:
    1. Send question + tool definitions to LLM
    2. LLM responds with either:
       - Tool call: [TOOL: get_chapter(5)]
       - Final answer: "In Chapter 5..."
    3. If tool call, execute and send result back to LLM
    4. Repeat until LLM provides final answer (max 5 iterations)

    Args:
        question: User question
        current_chapter: Which chapter user is currently listening to
        tools: BookTools instance for this book
        model: Ollama model name

    Returns:
        {
            'answer': str,
            'tools_used': ['get_chapter(5)', ...],
            'iterations': int,
            'context_tokens': int,
            'model': str,
            'error': str (if failed)
        }
    """
    # Build system prompt with tool definitions
    chapter_list = tools.list_chapters()
    if chapter_list:
        chapter_titles = '\n'.join([f"Chapter {ch['number']}: {ch['title']}" for ch in chapter_list])
        chapters_info = f"**Book Chapters:**\n{chapter_titles}\n\n"
    else:
        chapters_info = "**Note:** This book has no explicit chapters.\n\n"

    system_prompt = f"""You are a knowledgeable AI assistant for audiobook listeners. The user is currently listening to Chapter {current_chapter} of this book.

{chapters_info}**Available Tools:**
You can call the following tools to retrieve book content:

1. `get_chapter(chapter_num)` - Retrieve text of a specific chapter (if book has chapters)
   Example: [TOOL: get_chapter(5)]

2. `get_chapters(start, end)` - Retrieve a range of chapters
   Example: [TOOL: get_chapters(3, 5)]

3. `get_book_section(start_pct, end_pct)` - Retrieve section by percentage (0-100)
   Example: [TOOL: get_book_section(0, 10)] for first 10%
   Example: [TOOL: get_book_section(25, 50)] for middle 25%
   **Use this for queries like "first 10%", "beginning", "middle", "end"**

4. `list_chapters()` - Get table of contents

**How to use tools:**
- Format tool calls EXACTLY like: [TOOL: get_chapter(5)]
- You can call multiple tools: [TOOL: get_chapter(3)] and [TOOL: get_chapter(5)]
- For percentage queries ("first 10%", "beginning"), use get_book_section
- For books without chapters, ALWAYS use get_book_section
- After receiving tool results, provide a clear answer based on the content

**Important:**
- Be concise and accurate
- Cite sources when answering (e.g., "In Chapter 5..." or "In the first 10%...")
- If you already know the answer without tools, answer directly
- Don't request the full book unless absolutely necessary
"""

    messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': question}
    ]

    tools_used = []
    iterations = 0
    max_iterations = 5

    try:
        while iterations < max_iterations:
            iterations += 1

            # Call LLM
            response = ollama.chat(model=model, messages=messages)
            assistant_message = response['message']['content']

            # Check if LLM wants to call a tool
            tool_calls = re.findall(r'\[TOOL:\s*([^\]]+)\]', assistant_message)

            if not tool_calls:
                # No tool calls - this is the final answer
                return {
                    'answer': assistant_message.strip(),
                    'tools_used': tools_used,
                    'iterations': iterations,
                    'model': model,
                    'error': None
                }

            # Execute tool calls
            tool_results = []
            for tool_call in tool_calls:
                tool_call = tool_call.strip()
                tools_used.append(tool_call)

                # Parse tool call
                if tool_call.startswith('get_chapter(') and tool_call.endswith(')'):
                    # Extract chapter number
                    match = re.match(r'get_chapter\((\d+)\)', tool_call)
                    if match:
                        chapter_num = int(match.group(1))
                        result = tools.get_chapter(chapter_num)
                        tool_results.append(f"[RESULT for get_chapter({chapter_num})]\n{result}\n[/RESULT]")

                elif tool_call.startswith('get_chapters(') and tool_call.endswith(')'):
                    # Extract range
                    match = re.match(r'get_chapters\((\d+),\s*(\d+)\)', tool_call)
                    if match:
                        start = int(match.group(1))
                        end = int(match.group(2))
                        result = tools.get_chapters(start, end)
                        tool_results.append(f"[RESULT for get_chapters({start}, {end})]\n{result}\n[/RESULT]")

                elif tool_call.startswith('get_book_section(') and tool_call.endswith(')'):
                    # Extract percentages
                    match = re.match(r'get_book_section\((\d+\.?\d*),\s*(\d+\.?\d*)\)', tool_call)
                    if match:
                        start_pct = float(match.group(1))
                        end_pct = float(match.group(2))
                        result = tools.get_book_section(start_pct, end_pct)
                        tool_results.append(f"[RESULT for get_book_section({start_pct}, {end_pct})]\n{result}\n[/RESULT]")

                elif tool_call.startswith('list_chapters()'):
                    chapter_list_text = '\n'.join([f"{ch['number']}. {ch['title']}" for ch in chapter_list])
                    tool_results.append(f"[RESULT for list_chapters()]\n{chapter_list_text}\n[/RESULT]")

                else:
                    tool_results.append(f"[ERROR: Unknown tool call: {tool_call}]")

            # Add assistant message + tool results to conversation
            messages.append({'role': 'assistant', 'content': assistant_message})
            messages.append({'role': 'user', 'content': '\n\n'.join(tool_results)})

        # Max iterations reached
        return {
            'answer': "Sorry, I couldn't generate a complete answer. The question might be too complex. Try asking something more specific.",
            'tools_used': tools_used,
            'iterations': iterations,
            'model': model,
            'error': 'max_iterations_reached'
        }

    except Exception as e:
        return {
            'answer': f"Error: {str(e)}",
            'tools_used': tools_used,
            'iterations': iterations,
            'model': model,
            'error': str(e)
        }


def check_ollama_available() -> Dict:
    """
    Health check for Ollama service.

    Returns:
        {
            'available': bool,
            'models': [...],
            'error': str (if failed)
        }
    """
    try:
        # Try to list models
        models = ollama.list()
        model_names = [m['name'] for m in models.get('models', [])]

        return {
            'available': True,
            'models': model_names,
            'error': None
        }
    except Exception as e:
        return {
            'available': False,
            'models': [],
            'error': str(e)
        }
