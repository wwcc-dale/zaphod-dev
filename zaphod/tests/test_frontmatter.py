# zaphod/tests/test_frontmatter.py
"""
Tests for frontmatter_to_meta.py
"""
import pytest
from pathlib import Path
import json

from zaphod.frontmatter_to_meta import (
    process_folder,
    interpolate_body,
    interpolate_includes,
    infer_module_from_path,
    get_changed_files,
    iter_changed_content_dirs,
)


class TestInterpolation:
    """Tests for variable interpolation"""
    
    def test_interpolate_body_simple(self):
        """Should replace {{var:key}} with value"""
        body = "Hello {{var:name}}, welcome to {{var:course}}!"
        meta = {"name": "Alice", "course": "CS101"}
        
        result = interpolate_body(body, meta)
        assert result == "Hello Alice, welcome to CS101!"
    
    def test_interpolate_body_missing_key(self):
        """Should leave placeholder if key not in metadata"""
        body = "Hello {{var:unknown}}!"
        meta = {}
        
        result = interpolate_body(body, meta)
        assert result == "Hello {{var:unknown}}!"
    
    def test_interpolate_body_no_placeholders(self):
        """Should return unchanged text if no placeholders"""
        body = "Plain text with no variables"
        meta = {"unused": "value"}
        
        result = interpolate_body(body, meta)
        assert result == body


class TestModuleInference:
    """Tests for module inference from directory structure"""
    
    def test_infer_direct_child(self, temp_course_dir):
        """Should infer module from direct parent with module- prefix"""
        folder = temp_course_dir / "pages" / "module-Week 1" / "intro.page"
        folder.mkdir(parents=True)
        
        # Need to set PAGES_DIR for the function
        import zaphod.frontmatter_to_meta as fm
        original_pages_dir = fm.PAGES_DIR
        fm.PAGES_DIR = temp_course_dir / "pages"
        
        try:
            result = infer_module_from_path(folder)
            assert result == "Week 1"
        finally:
            fm.PAGES_DIR = original_pages_dir
    
    def test_infer_nested(self, temp_course_dir):
        """Should infer module from ancestor with module- prefix"""
        folder = temp_course_dir / "pages" / "module-Week 1" / "topic" / "intro.page"
        folder.mkdir(parents=True)
        
        import zaphod.frontmatter_to_meta as fm
        original_pages_dir = fm.PAGES_DIR
        fm.PAGES_DIR = temp_course_dir / "pages"
        
        try:
            result = infer_module_from_path(folder)
            assert result == "Week 1"
        finally:
            fm.PAGES_DIR = original_pages_dir
    
    def test_no_module_prefix(self, temp_course_dir):
        """Should return None if no module- prefix found"""
        folder = temp_course_dir / "pages" / "week1" / "intro.page"
        folder.mkdir(parents=True)
        
        import zaphod.frontmatter_to_meta as fm
        original_pages_dir = fm.PAGES_DIR
        fm.PAGES_DIR = temp_course_dir / "pages"
        
        try:
            result = infer_module_from_path(folder)
            assert result is None
        finally:
            fm.PAGES_DIR = original_pages_dir


class TestProcessFolder:
    """Tests for process_folder function"""
    
    def test_process_valid_index_md(self, temp_course_dir, capsys):
        """Should create meta.json and source.md from valid index.md"""
        folder = temp_course_dir / "pages" / "test.page"
        folder.mkdir(parents=True)
        
        index_content = """---
name: "Test Page"
type: "page"
modules:
  - "Module 1"
---

# Test Content

This is the body.
"""
        (folder / "index.md").write_text(index_content)
        
        process_folder(folder)
        
        # Check meta.json created
        meta_path = folder / "meta.json"
        assert meta_path.exists()
        meta = json.loads(meta_path.read_text())
        assert meta["name"] == "Test Page"
        assert meta["type"] == "page"
        
        # Check source.md created
        source_path = folder / "source.md"
        assert source_path.exists()
        assert "# Test Content" in source_path.read_text()
    
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
