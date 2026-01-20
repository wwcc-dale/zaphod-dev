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
    stem_to_html,
    answer_to_html,
    escape_html,
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
    
    def test_split_preserves_code_blocks(self):
        """Blank lines inside code blocks should not split questions"""
        text = """1. What does this code output?

```python
def greet():
    print("Hello")

greet()
```

a) Hello
*b) Hello followed by newline
c) Nothing

2. Another question
a) A
*b) B
"""
        blocks = split_questions(text)
        
        # Should have 2 questions, not more
        assert len(blocks) == 2
        
        # First block should contain the entire code block
        first_block = '\n'.join(blocks[0])
        assert "```python" in first_block
        assert 'print("Hello")' in first_block
        assert "greet()" in first_block


class TestHtmlEscaping:
    """Tests for HTML escaping"""
    
    def test_escape_html_basic(self):
        """Should escape HTML special characters"""
        result = escape_html("Is 1 < 2 && 3 > 2?")
        assert "&lt;" in result
        assert "&gt;" in result
        assert "&amp;" in result
    
    def test_escape_html_quotes(self):
        """Should escape quotes"""
        result = escape_html('Say "hello"')
        assert "&quot;" in result


class TestStemToHtml:
    """Tests for stem_to_html conversion"""
    
    def test_simple_text(self):
        """Simple text should be wrapped in paragraph"""
        result = stem_to_html("What is 2+2?")
        assert "<p>" in result
        assert "What is 2+2?" in result
    
    def test_inline_code(self):
        """Inline code should use <code> tags"""
        result = stem_to_html("What does `print()` do?")
        assert "<code>print()</code>" in result
    
    def test_fenced_code_block(self):
        """Fenced code blocks should use <pre><code>"""
        stem = """What does this output?

```python
x = 1
print(x)
```"""
        result = stem_to_html(stem)
        
        assert "<pre><code" in result
        assert "x = 1" in result
        assert "print(x)" in result
        assert 'class="language-python"' in result
    
    def test_code_block_without_language(self):
        """Code blocks without language specifier should work"""
        stem = """Consider:

```
some code
```"""
        result = stem_to_html(stem)
        
        assert "<pre><code>" in result
        assert "some code" in result
    
    def test_escapes_html_in_text(self):
        """HTML entities should be escaped in regular text"""
        result = stem_to_html("Is 1 < 2 && 3 > 2?")
        assert "&lt;" in result
        assert "&gt;" in result
        assert "&amp;" in result
    
    def test_escapes_html_in_code_block(self):
        """HTML in code blocks should be escaped"""
        stem = """What does this do?

```html
<div class="test">Hello</div>
```"""
        result = stem_to_html(stem)
        
        assert "&lt;div" in result
        assert "&gt;" in result


class TestAnswerToHtml:
    """Tests for answer_to_html conversion"""
    
    def test_plain_text(self):
        """Plain text should be escaped"""
        result = answer_to_html("Option A")
        assert result == "Option A"
    
    def test_inline_code(self):
        """Inline code should be converted"""
        result = answer_to_html("The `print()` function")
        assert "<code>print()</code>" in result
    
    def test_escapes_html(self):
        """HTML should be escaped"""
        result = answer_to_html("x < y && y > z")
        assert "&lt;" in result
        assert "&gt;" in result
        assert "&amp;" in result
    
    def test_code_with_special_chars(self):
        """Code containing special chars should be escaped"""
        result = answer_to_html("Use `x < 5` to compare")
        assert "<code>" in result
        assert "&lt;" in result


class TestCodeBlockHandling:
    """Integration tests for code blocks in quiz questions"""
    
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
    
    def test_multiline_code_block_in_question(self):
        """Multi-line code block with blank lines should stay together"""
        text = """1. What does this output?

```python
def foo():
    x = 1

    return x
```

a) 1
*b) None
c) Error

2. Next question
*a) Yes
b) No
"""
        blocks = split_questions(text)
        assert len(blocks) == 2
        
        # Parse first question
        q = parse_question_block(blocks[0], default_points=1.0)
        assert "def foo():" in q.stem
        assert "return x" in q.stem
