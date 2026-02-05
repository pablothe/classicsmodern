#!/usr/bin/env python3
"""
Improved Question Classifier for Hybrid RAG System

Key insight: Default to SPECIFIC_FACTUAL for safety
(Better to use semantic search unnecessarily than dump 8K tokens)
"""

import re
from typing import Dict, Literal

QuestionType = Literal['SPECIFIC_FACTUAL', 'BROAD_SUMMARY']


def classify_question(question: str) -> Dict:
    """
    Classify question to determine retrieval strategy.

    Strategy:
    1. Check EXPLICIT summary requests → BROAD_SUMMARY
    2. Check EXPLICIT factual requests → SPECIFIC_FACTUAL
    3. Default to SPECIFIC_FACTUAL (safer)

    Returns:
        {
            'type': 'SPECIFIC_FACTUAL' | 'BROAD_SUMMARY',
            'confidence': 'high' | 'medium' | 'low',
            'reasoning': str
        }
    """
    q = question.lower().strip()

    # ========================================================================
    # HIGH CONFIDENCE: BROAD_SUMMARY
    # ========================================================================
    # Explicit summary requests
    broad_explicit = [
        q.startswith('summarize'),
        q.startswith('summary of'),
        q.startswith('overview of'),
        q.startswith('give me a summary'),
        q.startswith('give an overview'),
        re.match(r'^what (happens|occurred|takes place) (in|during)', q),
        'give me an overview' in q,
        'provide a summary' in q,
    ]

    if any(broad_explicit):
        return {
            'type': 'BROAD_SUMMARY',
            'confidence': 'high',
            'reasoning': 'Explicit summary/overview request'
        }

    # ========================================================================
    # HIGH CONFIDENCE: SPECIFIC_FACTUAL
    # ========================================================================
    # Questions about descriptions, appearances, quotes
    specific_explicit = [
        # "How is X described"
        re.match(r'^how (is|was|does|did) .+ (described|portrayed|depicted)', q),

        # "What does X look like"
        'look like' in q,
        'appear like' in q,
        'appearance of' in q,

        # "Who said X" / "What did X say"
        re.match(r'^who (said|says|mentioned)', q),
        re.match(r'^what (did|does) .+ (say|tell|mention)', q),
        'quote' in q,

        # "Where/When did X happen" (specific events)
        re.match(r'^(where|when) (is|was|does|did) .+ (first|mentioned|happen)', q),

        # "What is X called/named"
        re.match(r'^what (is|was) .+ (called|named)', q),
    ]

    if any(specific_explicit):
        return {
            'type': 'SPECIFIC_FACTUAL',
            'confidence': 'high',
            'reasoning': 'Question asks for specific fact/description/quote'
        }

    # ========================================================================
    # MEDIUM CONFIDENCE: Pattern matching
    # ========================================================================

    # Check for summary keywords (even without explicit "summarize")
    summary_indicators = [
        'what happens' in q,
        'plot of' in q,
        'story of' in q,
        'events of' in q,
        'tell me about' in q and 'chapter' in q,
        'explain' in q and ('chapter' in q or 'section' in q),
    ]

    if any(summary_indicators):
        return {
            'type': 'BROAD_SUMMARY',
            'confidence': 'medium',
            'reasoning': 'Contains summary indicators (what happens, plot, story)'
        }

    # Check for factual question words
    factual_starters = [
        q.startswith('who is'),
        q.startswith('who was'),
        q.startswith('what is'),
        q.startswith('what was'),
        q.startswith('how is'),
        q.startswith('how did'),
        q.startswith('where is'),
        q.startswith('where did'),
        q.startswith('when did'),
        q.startswith('why did'),
    ]

    if any(factual_starters):
        return {
            'type': 'SPECIFIC_FACTUAL',
            'confidence': 'medium',
            'reasoning': 'Starts with factual interrogative (who/what/how/where/when)'
        }

    # ========================================================================
    # DEFAULT: SPECIFIC_FACTUAL (safer choice)
    # ========================================================================
    # Rationale: Better to over-use semantic search than dump 8K tokens
    return {
        'type': 'SPECIFIC_FACTUAL',
        'confidence': 'low',
        'reasoning': 'Default to semantic search (safer than full context dump)'
    }


# ============================================================================
# Alternative: LLM-based classifier for edge cases
# ============================================================================

def classify_question_with_llm(question: str, model: str = 'llama3.2:3b') -> Dict:
    """
    Use LLM to classify ambiguous questions.

    Use this for low-confidence classifications if accuracy is critical.
    """
    import ollama

    prompt = f"""You are a question classifier. Classify this question into EXACTLY ONE category:

SPECIFIC_FACTUAL: Questions asking for specific facts, descriptions, quotes, names, or details about a particular thing or event.
Examples:
- "How is Cthulhu described?"
- "What does Alice look like?"
- "Who said 'Off with her head'?"
- "Where did the creature first appear?"
- "What is the monster called?"

BROAD_SUMMARY: Questions asking for summaries, overviews, general explanations, or narrative of events.
Examples:
- "Summarize chapter 5"
- "What happens in the beginning?"
- "Give me an overview of the plot"
- "Explain the events of chapter 3"
- "Tell me about the middle section"

Question: "{question}"

Answer with ONLY the category name (one word): SPECIFIC_FACTUAL or BROAD_SUMMARY"""

    try:
        response = ollama.generate(model=model, prompt=prompt)
        result = response['response'].strip().upper()

        if 'BROAD_SUMMARY' in result:
            return {
                'type': 'BROAD_SUMMARY',
                'confidence': 'high',
                'reasoning': 'LLM classified as summary request'
            }
        else:
            return {
                'type': 'SPECIFIC_FACTUAL',
                'confidence': 'high',
                'reasoning': 'LLM classified as factual question'
            }
    except Exception as e:
        # Fallback to rule-based
        return classify_question(question)


# ============================================================================
# Test Suite
# ============================================================================

def test_classifier():
    test_cases = [
        # Clear SPECIFIC_FACTUAL
        ("How is Cthulhu described in the first 25% of the book?", "SPECIFIC_FACTUAL"),
        ("What does Alice look like?", "SPECIFIC_FACTUAL"),
        ("Who said 'Off with her head'?", "SPECIFIC_FACTUAL"),
        ("What is the creature called?", "SPECIFIC_FACTUAL"),
        ("Where did the monster first appear?", "SPECIFIC_FACTUAL"),

        # Clear BROAD_SUMMARY
        ("Summarize chapter 5", "BROAD_SUMMARY"),
        ("What happens in the first 25% of the book?", "BROAD_SUMMARY"),
        ("Give me an overview of the beginning", "BROAD_SUMMARY"),
        ("Summary of chapter 3", "BROAD_SUMMARY"),
        ("What takes place during the investigation?", "BROAD_SUMMARY"),

        # Edge cases (should default to SPECIFIC_FACTUAL for safety)
        ("What is the theme of chapter 5?", "SPECIFIC_FACTUAL"),
        ("Describe the creature", "SPECIFIC_FACTUAL"),
        ("Tell me about Cthulhu", "SPECIFIC_FACTUAL"),
        ("What's significant about the creature?", "SPECIFIC_FACTUAL"),
    ]

    print("=" * 80)
    print("QUESTION CLASSIFIER TEST SUITE")
    print("=" * 80)

    correct = 0
    total = len(test_cases)

    for question, expected_type in test_cases:
        result = classify_question(question)
        actual_type = result['type']
        is_correct = actual_type == expected_type

        if is_correct:
            correct += 1
            status = "✅"
        else:
            status = "❌"

        print(f"\n{status} Q: {question}")
        print(f"   Expected: {expected_type}")
        print(f"   Got: {actual_type} (confidence: {result['confidence']})")
        print(f"   Reasoning: {result['reasoning']}")

    print("\n" + "=" * 80)
    print(f"ACCURACY: {correct}/{total} ({(correct/total)*100:.1f}%)")
    print("=" * 80)


if __name__ == '__main__':
    test_classifier()
