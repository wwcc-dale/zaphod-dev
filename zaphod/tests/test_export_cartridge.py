# zaphod/tests/test_export_cartridge.py
"""
Tests for export_cartridge.py - Common Cartridge export functionality
"""
import pytest
from pathlib import Path
import json
from xml.etree import ElementTree as ET

from zaphod.export_cartridge import (
    generate_id,
    generate_content_id,
    load_content_items,
    load_quizzes,
    split_quiz_frontmatter,
    parse_quiz_questions,
    detect_question_type,
    ContentItem,
    QuizItem,
)


class TestIdGeneration:
    """Tests for ID generation functions"""
    
    def test_generate_id_uniqueness(self):
        """Generated IDs should be unique"""
        ids = [generate_id() for _ in range(100)]
        assert len(set(ids)) == 100
    
    def test_generate_id_prefix(self):
        """Generated IDs should use the prefix"""
        id1 = generate_id("test")
        assert id1.startswith("test")
    
    def test_generate_content_id_deterministic(self, temp_course_dir, monkeypatch):
        """Content IDs should be deterministic for same path"""
        import zaphod.export_cartridge as ec
        
        folder = temp_course_dir / "pages" / "test.page"
        folder.mkdir(parents=True)
        
        # Patch COURSE_ROOT to temp dir
        original_root = ec.COURSE_ROOT
        ec.COURSE_ROOT = temp_course_dir
        
        try:
            id1 = generate_content_id(folder)
            id2 = generate_content_id(folder)
            assert id1 == id2
        finally:
            ec.COURSE_ROOT = original_root


class TestQuizParsing:
    """Tests for quiz file parsing"""
    
    def test_split_frontmatter(self):
        """Should extract YAML frontmatter from quiz text"""
        text = """---
title: "Week 1 Quiz"
points_per_question: 2
---

1. What is the answer?
a) Option A
*b) Option B
"""
        meta, body = split_quiz_frontmatter(text)
        
        assert meta["title"] == "Week 1 Quiz"
        assert meta["points_per_question"] == 2
        assert "1. What is the answer?" in body
    
    def test_split_no_frontmatter(self):
        """Should handle quiz without frontmatter"""
        text = "1. Question text\na) Answer A\n*b) Answer B"
        meta, body = split_quiz_frontmatter(text)
        
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
        assert detect_question_type(block) == "multiple_choice"
    
    def test_detect_multiple_answers(self):
        """Should detect multiple answer questions"""
        block = [
            "1. Select all that apply:",
            "[*] Option A",
            "[ ] Option B",
            "[*] Option C",
        ]
        assert detect_question_type(block) == "multiple_answers"
    
    def test_detect_true_false(self):
        """Should detect true/false questions"""
        block = [
            "1. The sky is blue.",
            "*a) True",
            "b) False",
        ]
        assert detect_question_type(block) == "true_false"
    
    def test_detect_essay(self):
        """Should detect essay questions"""
        block = [
            "1. Explain the concept.",
            "####",
        ]
        assert detect_question_type(block) == "essay"
    
    def test_parse_multiple_choice(self):
        """Should parse multiple choice questions correctly"""
        body = """
1. What is 2+2?
a) 3
*b) 4
c) 5

2. What color is the sky?
*a) Blue
b) Red
"""
        questions = parse_quiz_questions(body, default_points=1.0)
        
        assert len(questions) == 2
        assert questions[0]["stem"] == "What is 2+2?"
        assert questions[0]["type"] == "multiple_choice"
        assert len(questions[0]["answers"]) == 3
        assert questions[0]["answers"][1]["correct"] is True


class TestContentLoading:
    """Tests for loading content items"""
    
    def test_load_content_items_page(self, temp_course_dir, monkeypatch):
        """Should load page content items"""
        import zaphod.export_cartridge as ec
        
        monkeypatch.chdir(temp_course_dir)
        
        # Create a page
        page_dir = temp_course_dir / "pages" / "welcome.page"
        page_dir.mkdir(parents=True)
        (page_dir / "index.md").write_text("""---
name: "Welcome"
type: "page"
modules:
  - "Module 1"
---

# Welcome!
""")
        
        # Patch both PAGES_DIR and COURSE_ROOT
        original_pages_dir = ec.PAGES_DIR
        original_course_root = ec.COURSE_ROOT
        ec.PAGES_DIR = temp_course_dir / "pages"
        ec.COURSE_ROOT = temp_course_dir
        
        try:
            items = load_content_items()
            assert len(items) == 1
            assert items[0].title == "Welcome"
            assert items[0].item_type == "page"
        finally:
            ec.PAGES_DIR = original_pages_dir
            ec.COURSE_ROOT = original_course_root


class TestFullExport:
    """Integration tests for full export process"""
    
    @pytest.fixture
    def sample_course(self, temp_course_dir):
        """Create a sample course structure for testing"""
        # Create a page
        page_dir = temp_course_dir / "pages" / "welcome.page"
        page_dir.mkdir(parents=True)
        (page_dir / "index.md").write_text("""---
name: "Welcome"
type: "page"
modules:
  - "Module 1"
---

# Welcome to the course!
""")
        
        # Create an assignment
        assign_dir = temp_course_dir / "pages" / "project.assignment"
        assign_dir.mkdir(parents=True)
        (assign_dir / "index.md").write_text("""---
name: "Project 1"
type: "assignment"
points_possible: 100
modules:
  - "Module 1"
---

# Project Instructions
""")
        
        # Create a quiz
        quiz_dir = temp_course_dir / "quiz-banks"
        quiz_dir.mkdir(parents=True)
        (quiz_dir / "week1.quiz.txt").write_text("""---
title: "Week 1 Quiz"
points_per_question: 2
---

1. What is 2+2?
a) 3
*b) 4
c) 5
""")
        
        return temp_course_dir
