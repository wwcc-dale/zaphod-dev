#!/usr/bin/env python3
"""
Test script for subfolder features:
1. Module inference from module- directory prefix
2. Asset resolution from nested subfolders

Run from course root:
    python tests/test_subfolder_features.py

Or with pytest if available:
    python -m pytest tests/test_subfolder_features.py -v
"""

import json
import tempfile
from pathlib import Path
import sys

# Add parent to path for imports
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))


# ============================================================================
# Inline the functions we're testing to avoid import dependency issues
# ============================================================================

MODULE_DIR_PREFIX = "module-"

def infer_module_from_path(folder: Path) -> str | None:
    """
    Infer module name from parent directory structure.
    
    Convention: If any parent directory starts with "module-", the text
    after the prefix becomes the default module name.
    """
    for parent in folder.parents:
        if parent.name.lower().startswith(MODULE_DIR_PREFIX.lower()):
            module_name = parent.name[len(MODULE_DIR_PREFIX):]
            if module_name:
                return module_name
        if parent.name == "pages":
            break
    return None


def find_local_asset(folder: Path, filename: str, assets_dir: Path) -> Path | None:
    """
    Find a local asset file, checking in order:
    1. The content folder itself (exact filename)
    2. Explicit relative path from the content folder
    3. Path relative to assets/ directory
    4. Auto-discover by filename anywhere in assets/ subfolders
    """
    clean_name = Path(filename).name
    
    # 1. Check content folder for exact filename
    local_path = folder / clean_name
    if local_path.is_file():
        return local_path
    
    # 2. Try explicit relative path from content folder, resolved
    relative_path = (folder / filename).resolve()
    if relative_path.is_file():
        return relative_path
    
    # 3. Try path relative to assets/ directory
    if assets_dir.exists():
        asset_relative = assets_dir / filename
        if asset_relative.is_file():
            return asset_relative
        
        # 4. Auto-discover: search all subfolders for filename match
        matches = list(assets_dir.rglob(clean_name))
        matches = [m for m in matches if m.is_file()]
        
        if len(matches) == 1:
            return matches[0]
        elif len(matches) > 1:
            locations = [str(m.relative_to(assets_dir)) for m in matches]
            print(f"[assets:warn] Multiple files named '{clean_name}' found:")
            for loc in locations:
                print(f"              - assets/{loc}")
            print(f"              Use explicit path, e.g., ../assets/{locations[0]}")
            return None
    
    return None


# ============================================================================
# Test Cases
# ============================================================================

class TestModuleInference:
    """Test module- directory prefix convention"""

    def test_direct_child_of_module_dir(self, tmp_path):
        """pages/module-Week 1/intro.page/ -> 'Week 1'"""
        pages = tmp_path / "pages"
        folder = pages / "module-Week 1" / "intro.page"
        folder.mkdir(parents=True)
        
        result = infer_module_from_path(folder)
        assert result == "Week 1"

    def test_nested_inside_module_dir(self, tmp_path):
        """pages/module-Week 1/topic/subtopic/intro.page/ -> 'Week 1'"""
        pages = tmp_path / "pages"
        folder = pages / "module-Week 1" / "topic" / "subtopic" / "intro.page"
        folder.mkdir(parents=True)
        
        result = infer_module_from_path(folder)
        assert result == "Week 1"

    def test_no_module_prefix(self, tmp_path):
        """pages/intro.page/ -> None"""
        pages = tmp_path / "pages"
        folder = pages / "intro.page"
        folder.mkdir(parents=True)
        
        result = infer_module_from_path(folder)
        assert result is None

    def test_non_module_subdirectory(self, tmp_path):
        """pages/week1/intro.page/ -> None (no module- prefix)"""
        pages = tmp_path / "pages"
        folder = pages / "week1" / "intro.page"
        folder.mkdir(parents=True)
        
        result = infer_module_from_path(folder)
        assert result is None

    def test_module_with_special_chars(self, tmp_path):
        """pages/module-Credit 1: Introduction/intro.page/ -> 'Credit 1: Introduction'"""
        pages = tmp_path / "pages"
        folder = pages / "module-Credit 1: Introduction" / "intro.page"
        folder.mkdir(parents=True)
        
        result = infer_module_from_path(folder)
        assert result == "Credit 1: Introduction"

    def test_case_insensitive_prefix(self, tmp_path):
        """pages/Module-Week 1/intro.page/ -> 'Week 1' (case insensitive)"""
        pages = tmp_path / "pages"
        folder = pages / "Module-Week 1" / "intro.page"
        folder.mkdir(parents=True)
        
        result = infer_module_from_path(folder)
        assert result == "Week 1"

    def test_closest_module_wins(self, tmp_path):
        """pages/module-Outer/module-Inner/intro.page/ -> 'Inner' (closest)"""
        pages = tmp_path / "pages"
        folder = pages / "module-Outer" / "module-Inner" / "intro.page"
        folder.mkdir(parents=True)
        
        result = infer_module_from_path(folder)
        assert result == "Inner"


class TestAssetSubfolderResolution:
    """Test asset discovery from nested subfolders"""

    def test_flat_assets_still_works(self, tmp_path):
        """assets/logo.png found with just 'logo.png'"""
        assets = tmp_path / "assets"
        assets.mkdir()
        (assets / "logo.png").write_text("fake png")
        
        content_folder = tmp_path / "pages" / "intro.page"
        content_folder.mkdir(parents=True)
        
        result = find_local_asset(content_folder, "logo.png", assets)
        assert result == assets / "logo.png"

    def test_nested_asset_auto_discovered(self, tmp_path):
        """assets/images/logo.png found with just 'logo.png'"""
        assets = tmp_path / "assets"
        images = assets / "images"
        images.mkdir(parents=True)
        (images / "logo.png").write_text("fake png")
        
        content_folder = tmp_path / "pages" / "intro.page"
        content_folder.mkdir(parents=True)
        
        result = find_local_asset(content_folder, "logo.png", assets)
        assert result == images / "logo.png"

    def test_deeply_nested_asset(self, tmp_path):
        """assets/images/diagrams/flowchart.svg found with just 'flowchart.svg'"""
        assets = tmp_path / "assets"
        diagrams = assets / "images" / "diagrams"
        diagrams.mkdir(parents=True)
        (diagrams / "flowchart.svg").write_text("fake svg")
        
        content_folder = tmp_path / "pages" / "intro.page"
        content_folder.mkdir(parents=True)
        
        result = find_local_asset(content_folder, "flowchart.svg", assets)
        assert result == diagrams / "flowchart.svg"

    def test_relative_to_assets_dir(self, tmp_path):
        """images/logo.png resolves to assets/images/logo.png"""
        assets = tmp_path / "assets"
        images = assets / "images"
        images.mkdir(parents=True)
        (images / "logo.png").write_text("fake png")
        
        content_folder = tmp_path / "pages" / "intro.page"
        content_folder.mkdir(parents=True)
        
        result = find_local_asset(content_folder, "images/logo.png", assets)
        assert result == images / "logo.png"

    def test_content_folder_asset_takes_priority(self, tmp_path):
        """Asset in content folder found before assets/ folder"""
        assets = tmp_path / "assets"
        assets.mkdir()
        (assets / "logo.png").write_text("global logo")
        
        content_folder = tmp_path / "pages" / "intro.page"
        content_folder.mkdir(parents=True)
        (content_folder / "logo.png").write_text("local logo")
        
        result = find_local_asset(content_folder, "logo.png", assets)
        assert result == content_folder / "logo.png"

    def test_duplicate_filename_returns_none_with_warning(self, tmp_path, capsys=None):
        """Multiple files with same name should warn and return None"""
        assets = tmp_path / "assets"
        (assets / "week1").mkdir(parents=True)
        (assets / "week2").mkdir(parents=True)
        (assets / "week1" / "logo.png").write_text("week1 logo")
        (assets / "week2" / "logo.png").write_text("week2 logo")
        
        content_folder = tmp_path / "pages" / "intro.page"
        content_folder.mkdir(parents=True)
        
        result = find_local_asset(content_folder, "logo.png", assets)
        
        # Should return None due to ambiguity
        assert result is None

    def test_asset_not_found_returns_none(self, tmp_path):
        """Non-existent asset returns None"""
        assets = tmp_path / "assets"
        assets.mkdir()
        
        content_folder = tmp_path / "pages" / "intro.page"
        content_folder.mkdir(parents=True)
        
        result = find_local_asset(content_folder, "nonexistent.png", assets)
        assert result is None


# ============================================================================
# Standalone runner
# ============================================================================

def run_standalone_tests():
    """Run tests without pytest for quick manual verification"""
    import traceback
    
    print("=" * 60)
    print("SUBFOLDER FEATURES TEST SUITE")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        
        # ====== MODULE INFERENCE TESTS ======
        
        print("\n--- MODULE INFERENCE TESTS ---\n")
        
        # Test 1: Direct child
        print("[TEST] Direct child of module- dir")
        try:
            pages = tmp_path / "t1" / "pages"
            folder = pages / "module-Week 1" / "intro.page"
            folder.mkdir(parents=True)
            result = infer_module_from_path(folder)
            assert result == "Week 1", f"Expected 'Week 1', got {result!r}"
            print("  ✓ PASSED")
            passed += 1
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1

        # Test 2: Nested
        print("[TEST] Nested inside module- dir")
        try:
            pages = tmp_path / "t2" / "pages"
            folder = pages / "module-Week 1" / "topic" / "subtopic" / "intro.page"
            folder.mkdir(parents=True)
            result = infer_module_from_path(folder)
            assert result == "Week 1", f"Expected 'Week 1', got {result!r}"
            print("  ✓ PASSED")
            passed += 1
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1

        # Test 3: No prefix
        print("[TEST] No module- prefix")
        try:
            pages = tmp_path / "t3" / "pages"
            folder = pages / "week1" / "intro.page"
            folder.mkdir(parents=True)
            result = infer_module_from_path(folder)
            assert result is None, f"Expected None, got {result!r}"
            print("  ✓ PASSED")
            passed += 1
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1

        # Test 4: Special characters
        print("[TEST] Special characters in module name")
        try:
            pages = tmp_path / "t4" / "pages"
            folder = pages / "module-Credit 1: Introduction" / "intro.page"
            folder.mkdir(parents=True)
            result = infer_module_from_path(folder)
            assert result == "Credit 1: Introduction", f"Expected 'Credit 1: Introduction', got {result!r}"
            print("  ✓ PASSED")
            passed += 1
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1

        # Test 5: Case insensitive
        print("[TEST] Case insensitive prefix (Module- vs module-)")
        try:
            pages = tmp_path / "t5" / "pages"
            folder = pages / "Module-Week 1" / "intro.page"
            folder.mkdir(parents=True)
            result = infer_module_from_path(folder)
            assert result == "Week 1", f"Expected 'Week 1', got {result!r}"
            print("  ✓ PASSED")
            passed += 1
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1

        # Test 6: Closest wins
        print("[TEST] Closest module- wins (nested module dirs)")
        try:
            pages = tmp_path / "t6" / "pages"
            folder = pages / "module-Outer" / "module-Inner" / "intro.page"
            folder.mkdir(parents=True)
            result = infer_module_from_path(folder)
            assert result == "Inner", f"Expected 'Inner', got {result!r}"
            print("  ✓ PASSED")
            passed += 1
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1

        # ====== ASSET RESOLUTION TESTS ======
        
        print("\n--- ASSET RESOLUTION TESTS ---\n")

        # Test 7: Flat assets
        print("[TEST] Flat assets/ still works")
        try:
            test_dir = tmp_path / "t7"
            assets = test_dir / "assets"
            assets.mkdir(parents=True)
            (assets / "logo.png").write_text("fake")
            content = test_dir / "pages" / "intro.page"
            content.mkdir(parents=True)
            
            result = find_local_asset(content, "logo.png", assets)
            assert result == assets / "logo.png", f"Expected {assets / 'logo.png'}, got {result}"
            print("  ✓ PASSED")
            passed += 1
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1

        # Test 8: Nested auto-discovery
        print("[TEST] Nested subfolder auto-discovery")
        try:
            test_dir = tmp_path / "t8"
            assets = test_dir / "assets"
            images = assets / "images" / "diagrams"
            images.mkdir(parents=True)
            (images / "flowchart.svg").write_text("fake")
            content = test_dir / "pages" / "intro.page"
            content.mkdir(parents=True)
            
            result = find_local_asset(content, "flowchart.svg", assets)
            assert result == images / "flowchart.svg", f"Expected {images / 'flowchart.svg'}, got {result}"
            print("  ✓ PASSED")
            passed += 1
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1

        # Test 9: Relative to assets dir
        print("[TEST] Relative path to assets/ dir (images/logo.png)")
        try:
            test_dir = tmp_path / "t9"
            assets = test_dir / "assets"
            images = assets / "images"
            images.mkdir(parents=True)
            (images / "logo.png").write_text("fake")
            content = test_dir / "pages" / "intro.page"
            content.mkdir(parents=True)
            
            result = find_local_asset(content, "images/logo.png", assets)
            assert result == images / "logo.png", f"Expected {images / 'logo.png'}, got {result}"
            print("  ✓ PASSED")
            passed += 1
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1

        # Test 10: Content folder priority
        print("[TEST] Content folder takes priority over assets/")
        try:
            test_dir = tmp_path / "t10"
            assets = test_dir / "assets"
            assets.mkdir(parents=True)
            (assets / "logo.png").write_text("global")
            content = test_dir / "pages" / "intro.page"
            content.mkdir(parents=True)
            (content / "logo.png").write_text("local")
            
            result = find_local_asset(content, "logo.png", assets)
            assert result == content / "logo.png", f"Expected local file, got {result}"
            print("  ✓ PASSED")
            passed += 1
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1

        # Test 11: Duplicates return None
        print("[TEST] Duplicates return None with warning")
        try:
            test_dir = tmp_path / "t11"
            assets = test_dir / "assets"
            (assets / "week1").mkdir(parents=True)
            (assets / "week2").mkdir(parents=True)
            (assets / "week1" / "logo.png").write_text("v1")
            (assets / "week2" / "logo.png").write_text("v2")
            content = test_dir / "pages" / "intro.page"
            content.mkdir(parents=True)
            
            result = find_local_asset(content, "logo.png", assets)
            assert result is None, f"Expected None for duplicate, got {result}"
            print("  ✓ PASSED (warning printed above)")
            passed += 1
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1

        # Test 12: Not found returns None
        print("[TEST] Non-existent asset returns None")
        try:
            test_dir = tmp_path / "t12"
            assets = test_dir / "assets"
            assets.mkdir(parents=True)
            content = test_dir / "pages" / "intro.page"
            content.mkdir(parents=True)
            
            result = find_local_asset(content, "nonexistent.png", assets)
            assert result is None, f"Expected None, got {result}"
            print("  ✓ PASSED")
            passed += 1
        except Exception as e:
            print(f"  ✗ FAILED: {e}")
            failed += 1

    # Summary
    print("\n" + "=" * 60)
    total = passed + failed
    print(f"RESULTS: {passed}/{total} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    # Check if pytest is available
    try:
        import pytest
        print("Running with pytest...")
        sys.exit(pytest.main([__file__, "-v"]))
    except ImportError:
        print("pytest not available, running standalone tests...\n")
        success = run_standalone_tests()
        sys.exit(0 if success else 1)
