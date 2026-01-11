# tests/test_frontmatter.py
"""
Tests for frontmatter_to_meta.py
"""
import pytest
from pathlib import Path
import json
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from frontmatter_to_meta import (
    interpolate_body,
    interpolate_includes,
    process_folder,
    get_changed_files,
    iter_changed_content_dirs,
)
import frontmatter_to_meta


class TestVariableInterpolation:
    """Tests for {{var:key}} interpolation"""
    
    def test_simple_interpolation(self):
        """Basic variable replacement"""
        text = "Hello {{var:name}}"
        metadata = {"name": "World"}
        result = interpolate_body(text, metadata)
        assert result == "Hello World"
    
    def test_multiple_variables(self):
        """Multiple variables in same text"""
        text = "{{var:greeting}} {{var:name}}!"
        metadata = {"greeting": "Hello", "name": "Alice"}
        result = interpolate_body(text, metadata)
        assert result == "Hello Alice!"
    
    def test_missing_variable(self):
        """Missing variable should remain unchanged"""
        text = "Hello {{var:missing}}"
        metadata = {"name": "World"}
        result = interpolate_body(text, metadata)
        assert result == "Hello {{var:missing}}"
    
    def test_numeric_values(self):
        """Numeric values should convert to strings"""
        text = "Points: {{var:points}}"
        metadata = {"points": 100}
        result = interpolate_body(text, metadata)
        assert result == "Points: 100"
    
    def test_special_characters(self):
        """Variables with hyphens and underscores"""
        text = "{{var:course_name}} - {{var:section-id}}"
        metadata = {"course_name": "Design", "section-id": "A"}
        result = interpolate_body(text, metadata)
        assert result == "Design - A"


class TestIncludeInterpolation:
    """Tests for {{include:name}} functionality"""
    
    def test_include_not_found(self, temp_course_dir, capsys, monkeypatch):
        """Missing include should print warning and leave placeholder"""
        # Patch COURSE_ROOT to point to our temp directory
        monkeypatch.setattr(frontmatter_to_meta, "COURSE_ROOT", temp_course_dir)
        
        text = "Content: {{include:missing}}"
        result = interpolate_includes(text, temp_course_dir, {})
        
        captured = capsys.readouterr()
        assert "include 'missing' not found" in captured.out
        assert "{{include:missing}}" in result
    
    def test_include_with_variables(self, temp_course_dir, monkeypatch):
        """Include file with variables should interpolate"""
        # Patch COURSE_ROOT to point to our temp directory
        monkeypatch.setattr(frontmatter_to_meta, "COURSE_ROOT", temp_course_dir)
        
        # Create include file in the location the code actually looks
        includes_dir = temp_course_dir / "includes"
        includes_dir.mkdir()
        include_file = includes_dir / "header.md"
        include_file.write_text("# {{var:title}}\n\nWelcome!")
        
        text = "{{include:header}}"
        metadata = {"title": "My Course"}
        result = interpolate_includes(text, temp_course_dir, metadata)
        
        assert "# My Course" in result
        assert "Welcome!" in result


class TestProcessFolder:
    """Tests for process_folder() function"""
    
    def test_process_valid_page(self, sample_page_folder):
        """Process a valid page folder"""
        process_folder(sample_page_folder)
        
        # Check meta.json created
        meta_path = sample_page_folder / "meta.json"
        assert meta_path.exists()
        
        meta = json.loads(meta_path.read_text())
        assert meta["name"] == "Welcome to the Course"
        assert meta["type"] == "page"
        assert "Module 0: Start Here" in meta["modules"]
        
        # Check source.md created
        source_path = sample_page_folder / "source.md"
        assert source_path.exists()
        assert "# Welcome!" in source_path.read_text()
    
    def test_process_missing_required_fields(self, temp_course_dir, capsys):
        """Folder with missing required fields should warn"""
        folder = temp_course_dir / "pages" / "broken.page"
        folder.mkdir(parents=True)
        
        # Index with missing 'name'
        (folder / "index.md").write_text("---\ntype: page\n---\nContent")
        
        process_folder(folder)
        
        captured = capsys.readouterr()
        assert "missing 'name'" in captured.out
    
    def test_fallback_to_meta_json(self, temp_course_dir, capsys):
        """Should fall back to existing meta.json if index.md invalid"""
        folder = temp_course_dir / "pages" / "legacy.page"
        folder.mkdir(parents=True)
        
        # Create valid meta.json and source.md
        meta = {"name": "Legacy Page", "type": "page"}
        (folder / "meta.json").write_text(json.dumps(meta))
        (folder / "source.md").write_text("Legacy content")
        
        process_folder(folder)
        
        captured = capsys.readouterr()
        assert "meta.json" in captured.out


class TestIncrementalMode:
    """Tests for incremental processing"""
    
    def test_get_changed_files_empty(self, monkeypatch):
        """No env var should return empty list"""
        monkeypatch.delenv("ZAPHOD_CHANGED_FILES", raising=False)
        result = get_changed_files()
        assert result == []
    
    def test_get_changed_files_from_env(self, monkeypatch, temp_course_dir):
        """Should parse newline-separated paths from env"""
        files = [
            str(temp_course_dir / "pages" / "a.page" / "index.md"),
            str(temp_course_dir / "pages" / "b.page" / "index.md"),
        ]
        monkeypatch.setenv("ZAPHOD_CHANGED_FILES", "\n".join(files))
        
        result = get_changed_files()
        assert len(result) == 2
        assert all(isinstance(p, Path) for p in result)
    
    def test_iter_changed_content_dirs(self, temp_course_dir, monkeypatch):
        """Should identify content directories from changed files"""
        # Patch COURSE_ROOT to point to our temp directory
        monkeypatch.setattr(frontmatter_to_meta, "COURSE_ROOT", temp_course_dir)
        
        # Create folders
        page_folder = temp_course_dir / "pages" / "test.page"
        page_folder.mkdir(parents=True)
        (page_folder / "index.md").write_text("test")
        
        assignment_folder = temp_course_dir / "pages" / "hw.assignment"
        assignment_folder.mkdir(parents=True)
        (assignment_folder / "index.md").write_text("test")
        
        # Set changed files
        changed = [
            page_folder / "index.md",
            assignment_folder / "index.md",
        ]
        monkeypatch.setenv(
            "ZAPHOD_CHANGED_FILES",
            "\n".join(str(p) for p in changed)
        )
        
        result = list(iter_changed_content_dirs(get_changed_files()))
        
        assert len(result) == 2
        assert page_folder in result
        assert assignment_folder in result