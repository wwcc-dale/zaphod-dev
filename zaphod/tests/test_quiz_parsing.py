# zaphod/tests/test_quiz_parsing.py
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


class TestFrontmatterParsing:
    """Tests for quiz frontmatter parsing"""
    
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


class TestQuestionTypeDetection:
    """Tests for question type detection"""
    
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
    
    def test_detect_file_upload(self):
        """Should detect file upload questions"""
        block = [
            "1. Upload your project.",
            "^^^^",
        ]
        
        qtype = detect_qtype(block)
        assert qtype == "file_upload"
    
    def test_detect_short_answer(self):
        """Should detect short answer questions"""
        block = [
            "1. What is the capital of France?",
            "* Paris",
            "* paris",
        ]
        
        qtype = detect_qtype(block)
        assert qtype == "short_answer"


class TestQuestionParsing:
    """Tests for question block parsing"""
    
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
    
    def test_parse_true_false_true(self):
        """Should parse true/false with True correct"""
        block = [
            "1. The sky is blue.",
            "*a) True",
            "b) False",
        ]
        
        q = parse_question_block(block, default_points=1.0)
        
        assert q.qtype == "true_false"
        assert len(q.answers) == 2
        assert q.answers[0].text == "True"
        assert q.answers[0].is_correct
    
    def test_parse_essay(self):
        """Should parse essay question"""
        block = [
            "1. Explain your reasoning.",
            "Be thorough.",
            "####",
        ]
        
        q = parse_question_block(block, default_points=5.0)
        
        assert q.qtype == "essay"
        assert q.points == 5.0
        assert "Explain your reasoning" in q.stem


class TestQuestionSplitting:
    """Tests for splitting quiz text into question blocks"""
    
    def test_split_basic_questions(self):
        """Should split by blank lines"""
        text = """1. First question
a) A
*b) B

2. Second question
*a) X
b) Y"""
        
        blocks = split_questions(text)
        assert len(blocks) == 2
    
    def test_split_preserves_lines(self):
        """Should preserve all lines in each block"""
        text = """1. Question with
multiple lines
in the stem
a) Answer
*b) Correct"""
        
        blocks = split_questions(text)
        assert len(blocks) == 1
        assert len(blocks[0]) == 5


class TestCodeBlockHandling:
    """Tests for code blocks in quiz questions"""
    
    def test_question_with_code_block(self):
        """Question with code block should preserve code in stem"""
        block = [
            "1. What does this code output?",
            "```python",
            "print('hello')",
            "```",
            "a) hello",
            "*b) hello with newline",
            "c) error",
        ]
        
        q = parse_question_block(block, default_points=1.0)
        
        assert "```python" in q.stem
        assert "print('hello')" in q.stem
        assert q.qtype == "multiple_choice"
        assert len(q.answers) == 3
