# tests/test_export_cartridge.py
"""
Tests for export_cartridge.py - Common Cartridge export functionality
"""
import pytest
from pathlib import Path
import json
import sys
import tempfile
import shutil
import zipfile
from xml.etree import ElementTree as ET

sys.path.insert(0, str(Path(__file__).parent.parent))

from export_cartridge import (
    generate_id,
    generate_content_id,
    load_content_items,
    load_quizzes,
    load_outcomes,
    load_module_structure,
    collect_assets,
    split_quiz_frontmatter,
    parse_quiz_questions,
    detect_question_type,
    generate_qti_assessment,
    generate_manifest,
    generate_content_html,
    generate_assignment_xml,
    ContentItem,
    QuizItem,
    CartridgeExport,
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
    
    def test_generate_content_id_deterministic(self, temp_course_dir):
        """Content IDs should be deterministic for same path"""
        folder = temp_course_dir / "pages" / "test.page"
        folder.mkdir(parents=True)
        
        id1 = generate_content_id(folder)
        id2 = generate_content_id(folder)
        assert id1 == id2


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


class TestQTIGeneration:
    """Tests for QTI XML generation"""
    
    def test_generate_qti_basic(self):
        """Should generate valid QTI XML"""
        quiz = QuizItem(
            identifier="quiz1",
            title="Test Quiz",
            file_path=Path("test.quiz.txt"),
            meta={"points_per_question": 1},
            questions=[
                {
                    "number": 1,
                    "stem": "What is 2+2?",
                    "type": "multiple_choice",
                    "answers": [
                        {"text": "3", "correct": False},
                        {"text": "4", "correct": True},
                    ],
                    "points": 1.0,
                }
            ],
        )
        
        xml = generate_qti_assessment(quiz)
        
        # Should be parseable XML
        root = ET.fromstring(xml)
        assert root.tag == "questestinterop"
        
        # Should have assessment element
        assessment = root.find("assessment")
        assert assessment is not None
        assert assessment.get("title") == "Test Quiz"


class TestManifestGeneration:
    """Tests for imsmanifest.xml generation"""
    
    def test_generate_manifest_basic(self):
        """Should generate valid manifest XML"""
        export = CartridgeExport(
            title="Test Course",
            identifier="test_course_123",
            content_items=[],
            quizzes=[],
            outcomes=[],
            modules=[],
            assets=[],
        )
        
        xml = generate_manifest(export)
        
        # Should be parseable XML
        root = ET.fromstring(xml)
        assert "manifest" in root.tag
        
        # Should have metadata
        metadata = root.find("{http://www.imsglobal.org/xsd/imsccv1p3/imscp_v1p1}metadata")
        assert metadata is not None


class TestContentGeneration:
    """Tests for content HTML and XML generation"""
    
    def test_generate_content_html(self):
        """Should generate valid HTML"""
        item = ContentItem(
            identifier="page1",
            title="Welcome Page",
            item_type="page",
            folder_path=Path("test.page"),
            meta={"name": "Welcome Page"},
            source_html="<p>Hello world!</p>",
        )
        
        html = generate_content_html(item)
        
        assert "<!DOCTYPE html>" in html
        assert "<title>Welcome Page</title>" in html
        assert "<p>Hello world!</p>" in html
    
    def test_generate_assignment_xml(self):
        """Should generate valid assignment XML"""
        item = ContentItem(
            identifier="assign1",
            title="Project 1",
            item_type="assignment",
            folder_path=Path("project.assignment"),
            meta={
                "name": "Project 1",
                "points_possible": 100,
                "submission_types": ["online_upload"],
            },
            source_html="<p>Instructions here</p>",
        )
        
        xml = generate_assignment_xml(item)
        
        # Should be parseable XML
        root = ET.fromstring(xml)
        assert root.tag == "assignment"
        
        # Should have title and points
        title = root.find("title")
        assert title is not None
        assert title.text == "Project 1"
        
        points = root.find("points_possible")
        assert points is not None
        assert points.text == "100"


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
        
        # Create outcomes
        outcomes_dir = temp_course_dir / "outcomes"
        outcomes_dir.mkdir(parents=True)
        (outcomes_dir / "outcomes.yaml").write_text("""
course_outcomes:
  - code: CLO1
    title: "Learning Outcome 1"
    description: "Students can demonstrate knowledge"
    mastery_points: 3
""")
        
        return temp_course_dir
    
    def test_load_content_items(self, sample_course, monkeypatch):
        """Should load all content items"""
        monkeypatch.chdir(sample_course)
        
        items = load_content_items()
        
        assert len(items) == 2
        titles = [item.title for item in items]
        assert "Welcome" in titles
        assert "Project 1" in titles
    
    def test_load_quizzes(self, sample_course, monkeypatch):
        """Should load quizzes"""
        monkeypatch.chdir(sample_course)
        
        quizzes = load_quizzes()
        
        assert len(quizzes) == 1
        assert quizzes[0].title == "Week 1 Quiz"
        assert len(quizzes[0].questions) == 1
    
    def test_load_outcomes(self, sample_course, monkeypatch):
        """Should load learning outcomes"""
        monkeypatch.chdir(sample_course)
        
        outcomes = load_outcomes()
        
        assert len(outcomes) == 1
        assert outcomes[0].code == "CLO1"
