# zaphod/tests/test_subfolder_features.py
"""
Test script for subfolder features:
1. Module inference from module- directory prefix
2. Asset resolution from nested subfolders

Run with pytest:
    python -m pytest zaphod/tests/test_subfolder_features.py -v
"""

import pytest
from pathlib import Path


# ============================================================================
# Module Inference Tests
# ============================================================================

class TestModuleInference:
    """Tests for module inference from directory structure"""
    
    def test_direct_child_of_module_dir(self, tmp_path):
        """Should infer module from direct parent with module- prefix"""
        from zaphod.frontmatter_to_meta import infer_module_from_path
        import zaphod.frontmatter_to_meta as fm
        
        pages = tmp_path / "pages"
        folder = pages / "module-Week 1" / "intro.page"
        folder.mkdir(parents=True)
        
        original_pages_dir = fm.PAGES_DIR
        fm.PAGES_DIR = pages
        
        try:
            result = infer_module_from_path(folder)
            assert result == "Week 1"
        finally:
            fm.PAGES_DIR = original_pages_dir
    
    def test_nested_inside_module_dir(self, tmp_path):
        """Should infer module from ancestor with module- prefix"""
        from zaphod.frontmatter_to_meta import infer_module_from_path
        import zaphod.frontmatter_to_meta as fm
        
        pages = tmp_path / "pages"
        folder = pages / "module-Week 1" / "topic" / "subtopic" / "intro.page"
        folder.mkdir(parents=True)
        
        original_pages_dir = fm.PAGES_DIR
        fm.PAGES_DIR = pages
        
        try:
            result = infer_module_from_path(folder)
            assert result == "Week 1"
        finally:
            fm.PAGES_DIR = original_pages_dir
    
    def test_no_module_prefix(self, tmp_path):
        """Should return None if no module- prefix found"""
        from zaphod.frontmatter_to_meta import infer_module_from_path
        import zaphod.frontmatter_to_meta as fm
        
        pages = tmp_path / "pages"
        folder = pages / "week1" / "intro.page"
        folder.mkdir(parents=True)
        
        original_pages_dir = fm.PAGES_DIR
        fm.PAGES_DIR = pages
        
        try:
            result = infer_module_from_path(folder)
            assert result is None
        finally:
            fm.PAGES_DIR = original_pages_dir
    
    def test_case_insensitive_prefix(self, tmp_path):
        """Should match module- prefix case-insensitively"""
        from zaphod.frontmatter_to_meta import infer_module_from_path
        import zaphod.frontmatter_to_meta as fm
        
        pages = tmp_path / "pages"
        folder = pages / "Module-Week 1" / "intro.page"
        folder.mkdir(parents=True)
        
        original_pages_dir = fm.PAGES_DIR
        fm.PAGES_DIR = pages
        
        try:
            result = infer_module_from_path(folder)
            assert result == "Week 1"
        finally:
            fm.PAGES_DIR = original_pages_dir
    
    def test_preserves_module_name_case(self, tmp_path):
        """Should preserve original case of module name"""
        from zaphod.frontmatter_to_meta import infer_module_from_path
        import zaphod.frontmatter_to_meta as fm
        
        pages = tmp_path / "pages"
        folder = pages / "module-Credit 1: Introduction" / "intro.page"
        folder.mkdir(parents=True)
        
        original_pages_dir = fm.PAGES_DIR
        fm.PAGES_DIR = pages
        
        try:
            result = infer_module_from_path(folder)
            assert result == "Credit 1: Introduction"
        finally:
            fm.PAGES_DIR = original_pages_dir


# ============================================================================
# Asset Resolution Tests
# ============================================================================

class TestAssetResolution:
    """Tests for asset file resolution from nested subfolders
    
    Note: find_local_asset() uses module-level ASSETS_DIR, so we patch it.
    """
    
    def test_find_in_content_folder(self, tmp_path):
        """Should find asset in content folder itself"""
        from zaphod.publish_all import find_local_asset
        import zaphod.publish_all as pa
        
        assets = tmp_path / "assets"
        assets.mkdir()
        content = tmp_path / "pages" / "intro.page"
        content.mkdir(parents=True)
        
        # Put file in content folder
        (content / "local.png").write_text("image data")
        
        original_assets = pa.ASSETS_DIR
        pa.ASSETS_DIR = assets
        
        try:
            result = find_local_asset(content, "local.png")
            assert result == content / "local.png"
        finally:
            pa.ASSETS_DIR = original_assets
    
    def test_find_in_assets_root(self, tmp_path):
        """Should find asset in assets/ root"""
        from zaphod.publish_all import find_local_asset
        import zaphod.publish_all as pa
        
        assets = tmp_path / "assets"
        assets.mkdir()
        content = tmp_path / "pages" / "intro.page"
        content.mkdir(parents=True)
        
        (assets / "logo.png").write_text("logo")
        
        original_assets = pa.ASSETS_DIR
        pa.ASSETS_DIR = assets
        
        try:
            result = find_local_asset(content, "logo.png")
            assert result == assets / "logo.png"
        finally:
            pa.ASSETS_DIR = original_assets
    
    def test_find_in_assets_subfolder(self, tmp_path):
        """Should find asset in assets/ subfolder"""
        from zaphod.publish_all import find_local_asset
        import zaphod.publish_all as pa
        
        assets = tmp_path / "assets"
        (assets / "images").mkdir(parents=True)
        content = tmp_path / "pages" / "intro.page"
        content.mkdir(parents=True)
        
        (assets / "images" / "logo.png").write_text("logo")
        
        original_assets = pa.ASSETS_DIR
        pa.ASSETS_DIR = assets
        
        try:
            result = find_local_asset(content, "logo.png")
            assert result == assets / "images" / "logo.png"
        finally:
            pa.ASSETS_DIR = original_assets
    
    def test_explicit_relative_path(self, tmp_path):
        """Should resolve explicit path relative to assets/"""
        from zaphod.publish_all import find_local_asset
        import zaphod.publish_all as pa
        
        assets = tmp_path / "assets"
        (assets / "images").mkdir(parents=True)
        content = tmp_path / "pages" / "intro.page"
        content.mkdir(parents=True)
        
        (assets / "images" / "logo.png").write_text("logo")
        
        original_assets = pa.ASSETS_DIR
        pa.ASSETS_DIR = assets
        
        try:
            result = find_local_asset(content, "images/logo.png")
            assert result is not None
            assert result.name == "logo.png"
        finally:
            pa.ASSETS_DIR = original_assets
    
    def test_duplicate_returns_none(self, tmp_path):
        """Should return None with warning for duplicate filenames"""
        from zaphod.publish_all import find_local_asset
        import zaphod.publish_all as pa
        
        assets = tmp_path / "assets"
        (assets / "week1").mkdir(parents=True)
        (assets / "week2").mkdir(parents=True)
        content = tmp_path / "pages" / "intro.page"
        content.mkdir(parents=True)
        
        # Same filename in different subfolders
        (assets / "week1" / "logo.png").write_text("v1")
        (assets / "week2" / "logo.png").write_text("v2")
        
        original_assets = pa.ASSETS_DIR
        pa.ASSETS_DIR = assets
        
        try:
            result = find_local_asset(content, "logo.png")
            assert result is None  # Ambiguous, should return None
        finally:
            pa.ASSETS_DIR = original_assets
    
    def test_not_found_returns_none(self, tmp_path):
        """Should return None for non-existent asset"""
        from zaphod.publish_all import find_local_asset
        import zaphod.publish_all as pa
        
        assets = tmp_path / "assets"
        assets.mkdir()
        content = tmp_path / "pages" / "intro.page"
        content.mkdir(parents=True)
        
        original_assets = pa.ASSETS_DIR
        pa.ASSETS_DIR = assets
        
        try:
            result = find_local_asset(content, "nonexistent.png")
            assert result is None
        finally:
            pa.ASSETS_DIR = original_assets
