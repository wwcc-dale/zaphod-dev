# zaphod/tests/test_publish_all.py
"""
Tests for publish_all.py
"""
import pytest
from pathlib import Path
import json

from zaphod.publish_all import (
    load_upload_cache,
    save_upload_cache,
    get_changed_files,
    iter_all_content_dirs,
    iter_changed_content_dirs,
    find_local_asset,
    VIDEO_RE,
)


class TestUploadCache:
    """Tests for upload cache functionality"""
    
    def test_load_empty_cache(self, temp_course_dir, monkeypatch):
        """Should return empty dict when no cache exists"""
        monkeypatch.chdir(temp_course_dir)
        
        import zaphod.publish_all as pa
        original_file = pa.UPLOAD_CACHE_FILE
        pa.UPLOAD_CACHE_FILE = temp_course_dir / "_course_metadata" / "upload_cache.json"
        
        try:
            cache = load_upload_cache()
            assert cache == {}
        finally:
            pa.UPLOAD_CACHE_FILE = original_file
    
    def test_load_existing_cache(self, temp_course_dir, monkeypatch):
        """Should load cache from file"""
        monkeypatch.chdir(temp_course_dir)
        
        # Create cache file
        cache_data = {"12345:video.mp4:abc123": 100}
        cache_dir = temp_course_dir / "_course_metadata"
        cache_dir.mkdir(exist_ok=True)
        (cache_dir / "upload_cache.json").write_text(json.dumps(cache_data))
        
        import zaphod.publish_all as pa
        original_file = pa.UPLOAD_CACHE_FILE
        pa.UPLOAD_CACHE_FILE = cache_dir / "upload_cache.json"
        
        try:
            cache = load_upload_cache()
            assert cache == cache_data
        finally:
            pa.UPLOAD_CACHE_FILE = original_file
    
    def test_save_cache(self, temp_course_dir, monkeypatch):
        """Should save cache to file"""
        monkeypatch.chdir(temp_course_dir)
        
        cache_dir = temp_course_dir / "_course_metadata"
        cache_file = cache_dir / "upload_cache.json"
        
        import zaphod.publish_all as pa
        original_file = pa.UPLOAD_CACHE_FILE
        original_dir = pa.METADATA_DIR
        pa.UPLOAD_CACHE_FILE = cache_file
        pa.METADATA_DIR = cache_dir
        
        try:
            cache_data = {"12345:video.mp4:abc123": 100}
            save_upload_cache(cache_data)
            
            assert cache_file.exists()
            loaded = json.loads(cache_file.read_text())
            assert loaded == cache_data
        finally:
            pa.UPLOAD_CACHE_FILE = original_file
            pa.METADATA_DIR = original_dir


class TestChangedFiles:
    """Tests for incremental mode changed files handling"""
    
    def test_get_changed_files_empty(self, monkeypatch):
        """Should return empty list when env var not set"""
        monkeypatch.delenv("ZAPHOD_CHANGED_FILES", raising=False)
        result = get_changed_files()
        assert result == []
    
    def test_get_changed_files_from_env(self, monkeypatch, temp_course_dir):
        """Should parse newline-separated paths from env"""
        files = [
            str(temp_course_dir / "pages" / "a.page" / "source.md"),
            str(temp_course_dir / "pages" / "b.page" / "source.md"),
        ]
        monkeypatch.setenv("ZAPHOD_CHANGED_FILES", "\n".join(files))
        
        result = get_changed_files()
        assert len(result) == 2
        assert all(isinstance(p, Path) for p in result)


class TestContentDirIteration:
    """Tests for content directory iteration"""
    
    def test_iter_all_content_dirs(self, temp_course_dir, monkeypatch):
        """Should find all content directories"""
        monkeypatch.chdir(temp_course_dir)
        
        # Create some content folders
        (temp_course_dir / "pages" / "page1.page").mkdir(parents=True)
        (temp_course_dir / "pages" / "assign1.assignment").mkdir(parents=True)
        (temp_course_dir / "pages" / "link1.link").mkdir(parents=True)
        (temp_course_dir / "pages" / "file1.file").mkdir(parents=True)
        
        import zaphod.publish_all as pa
        original_pages = pa.PAGES_DIR
        pa.PAGES_DIR = temp_course_dir / "pages"
        
        try:
            dirs = list(iter_all_content_dirs())
            assert len(dirs) == 4
        finally:
            pa.PAGES_DIR = original_pages
    
    def test_iter_changed_content_dirs(self, temp_course_dir, monkeypatch):
        """Should filter to only changed content directories"""
        monkeypatch.chdir(temp_course_dir)
        
        # Create content folders
        page1 = temp_course_dir / "pages" / "page1.page"
        page1.mkdir(parents=True)
        (page1 / "source.md").write_text("content")
        
        page2 = temp_course_dir / "pages" / "page2.page"
        page2.mkdir(parents=True)
        (page2 / "source.md").write_text("content")
        
        # Only page1 is changed
        changed = [page1 / "source.md"]
        
        import zaphod.publish_all as pa
        original_root = pa.COURSE_ROOT
        pa.COURSE_ROOT = temp_course_dir
        
        try:
            dirs = list(iter_changed_content_dirs(changed))
            assert len(dirs) == 1
            assert dirs[0] == page1
        finally:
            pa.COURSE_ROOT = original_root


class TestLocalAssetResolution:
    """Tests for local asset file resolution
    
    Note: find_local_asset() uses module-level ASSETS_DIR, so we must patch it.
    """
    
    def test_find_in_content_folder(self, temp_course_dir):
        """Should find asset in content folder itself"""
        content = temp_course_dir / "pages" / "intro.page"
        content.mkdir(parents=True)
        
        # Put file in content folder
        (content / "local.png").write_text("image data")
        
        import zaphod.publish_all as pa
        original_assets = pa.ASSETS_DIR
        pa.ASSETS_DIR = temp_course_dir / "assets"
        
        try:
            result = find_local_asset(content, "local.png")
            assert result == content / "local.png"
        finally:
            pa.ASSETS_DIR = original_assets
    
    def test_find_in_assets_root(self, temp_course_dir):
        """Should find asset in assets/ root"""
        content = temp_course_dir / "pages" / "intro.page"
        content.mkdir(parents=True)
        
        # assets/ already exists from fixture
        (temp_course_dir / "assets" / "logo.png").write_text("logo")
        
        import zaphod.publish_all as pa
        original_assets = pa.ASSETS_DIR
        pa.ASSETS_DIR = temp_course_dir / "assets"
        
        try:
            result = find_local_asset(content, "logo.png")
            assert result == temp_course_dir / "assets" / "logo.png"
        finally:
            pa.ASSETS_DIR = original_assets
    
    def test_find_in_assets_subfolder(self, temp_course_dir):
        """Should auto-discover asset in assets/ subfolder"""
        content = temp_course_dir / "pages" / "intro.page"
        content.mkdir(parents=True)
        
        # Create nested asset
        images = temp_course_dir / "assets" / "images"
        images.mkdir(parents=True)
        (images / "logo.png").write_text("logo")
        
        import zaphod.publish_all as pa
        original_assets = pa.ASSETS_DIR
        pa.ASSETS_DIR = temp_course_dir / "assets"
        
        try:
            result = find_local_asset(content, "logo.png")
            assert result == images / "logo.png"
        finally:
            pa.ASSETS_DIR = original_assets
    
    def test_not_found_returns_none(self, temp_course_dir):
        """Should return None for non-existent asset"""
        content = temp_course_dir / "pages" / "intro.page"
        content.mkdir(parents=True)
        
        import zaphod.publish_all as pa
        original_assets = pa.ASSETS_DIR
        pa.ASSETS_DIR = temp_course_dir / "assets"
        
        try:
            result = find_local_asset(content, "nonexistent.png")
            assert result is None
        finally:
            pa.ASSETS_DIR = original_assets
    
    def test_duplicate_returns_none(self, temp_course_dir):
        """Should return None when same filename exists in multiple subfolders"""
        content = temp_course_dir / "pages" / "intro.page"
        content.mkdir(parents=True)
        
        # Same filename in different subfolders
        (temp_course_dir / "assets" / "week1").mkdir(parents=True)
        (temp_course_dir / "assets" / "week2").mkdir(parents=True)
        (temp_course_dir / "assets" / "week1" / "logo.png").write_text("v1")
        (temp_course_dir / "assets" / "week2" / "logo.png").write_text("v2")
        
        import zaphod.publish_all as pa
        original_assets = pa.ASSETS_DIR
        pa.ASSETS_DIR = temp_course_dir / "assets"
        
        try:
            result = find_local_asset(content, "logo.png")
            assert result is None  # Ambiguous
        finally:
            pa.ASSETS_DIR = original_assets
    
    def test_explicit_path_resolves(self, temp_course_dir):
        """Should resolve explicit path to assets/"""
        content = temp_course_dir / "pages" / "intro.page"
        content.mkdir(parents=True)
        
        images = temp_course_dir / "assets" / "images"
        images.mkdir(parents=True)
        (images / "logo.png").write_text("logo")
        
        import zaphod.publish_all as pa
        original_assets = pa.ASSETS_DIR
        pa.ASSETS_DIR = temp_course_dir / "assets"
        
        try:
            # Use explicit path relative to assets/
            result = find_local_asset(content, "images/logo.png")
            assert result is not None
            assert result.name == "logo.png"
        finally:
            pa.ASSETS_DIR = original_assets


class TestVideoPlaceholders:
    """Tests for video placeholder handling"""
    
    def test_video_regex_simple(self):
        """Should match simple video placeholder"""
        text = "Watch this: {{video:intro.mp4}}"
        match = VIDEO_RE.search(text)
        
        assert match is not None
        assert match.group(1) == "intro.mp4"
    
    def test_video_regex_with_quotes(self):
        """Should match video placeholder with quotes"""
        text = '{{video:"intro video.mp4"}}'
        match = VIDEO_RE.search(text)
        
        assert match is not None
        assert match.group(1) == "intro video.mp4"
    
    def test_video_regex_with_path(self):
        """Should match video placeholder with path"""
        text = "{{video:videos/week1/intro.mp4}}"
        match = VIDEO_RE.search(text)
        
        assert match is not None
        assert match.group(1) == "videos/week1/intro.mp4"
