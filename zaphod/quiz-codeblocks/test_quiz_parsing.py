# tests/test_quiz_parsing.py
"""
Tests for sync_quiz_banks.py quiz parsing
"""
import pytest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from sync_quiz_banks import (
    split_questions,
    detect_qtype,
    parse_question_block,
    split_frontmatter_and_body,
    stem_to_html,
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


class TestCodeBlockHandling:
    """Tests for code blocks in quiz questions"""
    
    def test_split_questions_preserves_code_blocks(self):
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
    
    def test_stem_to_html_simple(self):
        """Simple text should be wrapped in paragraph"""
        result = stem_to_html("What is 2+2?")
        assert result == "<p>What is 2+2?</p>"
    
    def test_stem_to_html_inline_code(self):
        """Inline code should use <code> tags"""
        result = stem_to_html("What does `print()` do?")
        assert "<code>print()</code>" in result
    
    def test_stem_to_html_fenced_code_block(self):
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
    
    def test_stem_to_html_code_block_without_language(self):
        """Code blocks without language specifier should work"""
        stem = """Consider:

```
some code
```"""
        result = stem_to_html(stem)
        
        assert "<pre><code>" in result
        assert "some code" in result
    
    def test_stem_to_html_escapes_html(self):
        """HTML entities should be escaped"""
        result = stem_to_html("Is 1 < 2 && 3 > 2?")
        assert "&lt;" in result
        assert "&gt;" in result
        assert "&amp;" in result
    
    def test_stem_to_html_code_block_escapes_html(self):
        """HTML in code blocks should be escaped"""
        stem = """What does this do?

```html
<div class="test">Hello</div>
```"""
        result = stem_to_html(stem)
        
        assert "&lt;div" in result
        assert "&gt;" in result
    
    def test_parse_question_with_code_block(self):
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