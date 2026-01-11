# tests/conftest.py
"""
Pytest configuration and shared fixtures for Zaphod tests
"""
import pytest
import json
import tempfile
import shutil
from pathlib import Path
from typing import Generator
import os


@pytest.fixture
def temp_course_dir() -> Generator[Path, None, None]:
    """Create a temporary course directory structure"""
    tmpdir = Path(tempfile.mkdtemp())
    
    # Create standard structure
    (tmpdir / "pages").mkdir()
    (tmpdir / "assets").mkdir()
    (tmpdir / "quiz-banks").mkdir()
    (tmpdir / "outcomes").mkdir()
    (tmpdir / "modules").mkdir()
    (tmpdir / "_course_metadata").mkdir()
    
    yield tmpdir
    
    # Cleanup
    shutil.rmtree(tmpdir)


@pytest.fixture
def sample_page_folder(temp_course_dir: Path) -> Path:
    """Create a sample .page folder with index.md"""
    folder = temp_course_dir / "pages" / "welcome.page"
    folder.mkdir(parents=True)
    
    index_content = """---
name: "Welcome to the Course"
type: "page"
modules:
  - "Module 0: Start Here"
published: true
---

# Welcome!

This is a sample page with {{var:course_name}}.
"""
    
    (folder / "index.md").write_text(index_content)
    return folder


@pytest.fixture
def sample_assignment_folder(temp_course_dir: Path) -> Path:
    """Create a sample .assignment folder"""
    folder = temp_course_dir / "pages" / "project-1.assignment"
    folder.mkdir(parents=True)
    
    index_content = """---
name: "Project 1: Design Basics"
type: "assignment"
modules:
  - "Module 1: Getting Started"
published: false
points_possible: 100
submission_types:
  - "online_upload"
allowed_extensions:
  - "pdf"
---

# Project 1

Complete the design exercise.

## Requirements

1. Create a mockup
2. Export as PDF
3. Submit via Canvas
"""
    
    (folder / "index.md").write_text(index_content)
    return folder


@pytest.fixture
def sample_meta_json(tmp_path: Path) -> Path:
    """Create a sample meta.json file"""
    meta = {
        "name": "Test Assignment",
        "type": "assignment",
        "modules": ["Module 1"],
        "published": False,
        "points_possible": 100,
    }
    
    meta_path = tmp_path / "meta.json"
    meta_path.write_text(json.dumps(meta, indent=2))
    return meta_path


@pytest.fixture
def mock_canvas_course(mocker):
    """Mock Canvas course object"""
    mock_course = mocker.Mock()
    mock_course.id = 12345
    mock_course.name = "Test Course"
    
    # Mock pages
    mock_page = mocker.Mock()
    mock_page.title = "Welcome"
    mock_page.url = "welcome"
    mock_page.id = 1
    mock_course.get_pages.return_value = [mock_page]
    
    # Mock assignments
    mock_assignment = mocker.Mock()
    mock_assignment.name = "Project 1"
    mock_assignment.id = 100
    mock_course.get_assignments.return_value = [mock_assignment]
    
    # Mock modules
    mock_module = mocker.Mock()
    mock_module.name = "Module 1"
    mock_module.id = 10
    mock_module.position = 1
    mock_course.get_modules.return_value = [mock_module]
    
    return mock_course


@pytest.fixture
def mock_canvas_api(mocker, mock_canvas_course):
    """Mock Canvas API object"""
    mock_canvas = mocker.Mock()
    mock_canvas.get_course.return_value = mock_canvas_course
    return mock_canvas


@pytest.fixture
def set_course_env(temp_course_dir: Path, monkeypatch):
    """Set up environment variables for testing"""
    monkeypatch.setenv("COURSE_ID", "12345")
    monkeypatch.setenv("CANVAS_CREDENTIAL_FILE", str(temp_course_dir / "credentials.txt"))
    
    # Create dummy credentials file
    cred_file = temp_course_dir / "credentials.txt"
    cred_file.write_text('API_KEY = "test_key"\nAPI_URL = "https://canvas.test.edu"')
    
    # Set working directory
    monkeypatch.chdir(temp_course_dir)