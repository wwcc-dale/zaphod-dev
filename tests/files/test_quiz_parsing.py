# tests/test_quiz_parsing.py
"""
Tests for sync_quiz_banks.py quiz parsing
"""
import pytest
from pathlib import Path

from zaphod.sync_quiz_banks import (
    split_questions,
    detect_qtype,
    parse_question_block,
    split_frontmatter_and_body,
)


class TestQuizParsing:
    """Tests for quiz text parsing"""
    
    def test_split_frontmatter(self):
        """Should extract YAML frontmatter"""
        text = """---
title: "Week 1 Quiz"
points_per_question: 2
---

1. What is the answer?
a) Option A
*b) Option B
"""
        meta, body = split_frontmatter_and_body(text)
        
        assert meta["title"] == "Week 1 Quiz"
        assert meta["points_per_question"] == 2
        assert "1. What is the answer?" in body
    
    def test_no_frontmatter(self):
        """Should handle quiz without frontmatter"""
        text = "1. Question text\na) Answer"
        meta, body = split_frontmatter_and_body(text)
        
        assert meta == {}
        assert body == text
    
    def test_detect_multiple_choice(self):
        """Should detect multiple choice questions"""
        block = [
            "1. What is 2+2?",
            "a) 3",
            "*b) 4",
            "c) 5",
        ]
        
        qtype = detect_qtype(block)
        assert qtype == "multiple_choice"
    
    def test_detect_multiple_answers(self):
        """Should detect multiple answer questions"""
        block = [
            "1. Select all that apply:",
            "[*] Option A",
            "[ ] Option B",
            "[*] Option C",
        ]
        
        qtype = detect_qtype(block)
        assert qtype == "multiple_answers"
    
    def test_detect_true_false(self):
        """Should detect true/false questions"""
        block = [
            "1. The sky is blue.",
            "*a) True",
            "b) False",
        ]
        
        qtype = detect_qtype(block)
        assert qtype == "true_false"
    
    def test_detect_essay(self):
        """Should detect essay questions"""
        block = [
            "1. Explain the concept.",
            "####",
        ]
        
        qtype = detect_qtype(block)
        assert qtype == "essay"
    
    def test_parse_multiple_choice_question(self):
        """Should parse multiple choice question correctly"""
        block = [
            "1. What is 2+2?",
            "a) 3",
            "*b) 4",
            "c) 5",
        ]
        
        q = parse_question_block(block, default_points=1.0)
        
        assert q.number == 1
        assert q.stem == "What is 2+2?"
        assert q.qtype == "multiple_choice"
        assert len(q.answers) == 3
        assert q.answers[1].is_correct  # b) 4
        assert not q.answers[0].is_correct  # a) 3
