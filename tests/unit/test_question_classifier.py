#!/usr/bin/env python3
"""
Unit tests for server/question_classifier.py

Tests classify_question: broad summary detection, specific factual detection,
medium confidence patterns, and default fallback.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from server.question_classifier import classify_question


class TestHighConfidenceBroadSummary:

    def test_summarize(self):
        result = classify_question("Summarize chapter 5")
        assert result['type'] == 'BROAD_SUMMARY'
        assert result['confidence'] == 'high'

    def test_summary_of(self):
        result = classify_question("Summary of the first part")
        assert result['type'] == 'BROAD_SUMMARY'
        assert result['confidence'] == 'high'

    def test_overview_of(self):
        result = classify_question("Overview of chapter 3")
        assert result['type'] == 'BROAD_SUMMARY'
        assert result['confidence'] == 'high'

    def test_what_happens_in(self):
        result = classify_question("What happens in the beginning?")
        assert result['type'] == 'BROAD_SUMMARY'
        assert result['confidence'] == 'high'

    def test_what_takes_place(self):
        result = classify_question("What takes place during the investigation?")
        assert result['type'] == 'BROAD_SUMMARY'
        assert result['confidence'] == 'high'

    def test_give_me_a_summary(self):
        result = classify_question("Give me a summary of the plot")
        assert result['type'] == 'BROAD_SUMMARY'
        assert result['confidence'] == 'high'

    def test_provide_a_summary(self):
        result = classify_question("Can you provide a summary?")
        assert result['type'] == 'BROAD_SUMMARY'
        assert result['confidence'] == 'high'


class TestHighConfidenceSpecificFactual:

    def test_how_is_described(self):
        result = classify_question("How is Cthulhu described in the book?")
        assert result['type'] == 'SPECIFIC_FACTUAL'
        assert result['confidence'] == 'high'

    def test_look_like(self):
        result = classify_question("What does Alice look like?")
        assert result['type'] == 'SPECIFIC_FACTUAL'
        assert result['confidence'] == 'high'

    def test_who_said(self):
        result = classify_question("Who said 'Off with her head'?")
        assert result['type'] == 'SPECIFIC_FACTUAL'
        assert result['confidence'] == 'high'

    def test_where_first_mentioned(self):
        result = classify_question("Where was the creature first mentioned?")
        assert result['type'] == 'SPECIFIC_FACTUAL'
        assert result['confidence'] == 'high'

    def test_what_is_called(self):
        result = classify_question("What is the monster called?")
        assert result['type'] == 'SPECIFIC_FACTUAL'
        assert result['confidence'] == 'high'

    def test_quote(self):
        result = classify_question("What's the famous quote from the book?")
        assert result['type'] == 'SPECIFIC_FACTUAL'
        assert result['confidence'] == 'high'


class TestMediumConfidence:

    def test_what_happens_medium(self):
        # "what happens" without "in/during" → medium confidence
        result = classify_question("what happens next?")
        assert result['type'] == 'BROAD_SUMMARY'
        assert result['confidence'] == 'medium'

    def test_plot_of_medium(self):
        result = classify_question("What is the plot of this book?")
        assert result['type'] == 'BROAD_SUMMARY'
        assert result['confidence'] == 'medium'

    def test_who_is_factual(self):
        result = classify_question("Who is the narrator?")
        assert result['type'] == 'SPECIFIC_FACTUAL'
        assert result['confidence'] == 'medium'

    def test_what_is_factual(self):
        result = classify_question("What is the setting?")
        assert result['type'] == 'SPECIFIC_FACTUAL'
        assert result['confidence'] == 'medium'


class TestDefaultFallback:

    def test_ambiguous_defaults_to_specific(self):
        result = classify_question("Tell me about Cthulhu")
        assert result['type'] == 'SPECIFIC_FACTUAL'

    def test_empty_question(self):
        result = classify_question("")
        assert result['type'] == 'SPECIFIC_FACTUAL'
        assert result['confidence'] == 'low'

    def test_random_text(self):
        result = classify_question("asdfghjkl")
        assert result['type'] == 'SPECIFIC_FACTUAL'
        assert result['confidence'] == 'low'
