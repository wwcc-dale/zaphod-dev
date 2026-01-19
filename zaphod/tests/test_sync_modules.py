# zaphod/tests/test_sync_modules.py
"""
Tests for sync_modules.py
"""
import pytest
from pathlib import Path
import json
import yaml

from zaphod.sync_modules import (
    load_module_order,
    module_has_item,
    get_folder_sort_key,
)


class TestModuleOrder:
    """Tests for module ordering"""
    
    def test_load_module_order_dict_format(self, temp_course_dir, monkeypatch):
        """Should parse dict format with 'modules' key"""
        monkeypatch.chdir(temp_course_dir)
        
        order_file = temp_course_dir / "modules" / "module_order.yaml"
        order_file.parent.mkdir(exist_ok=True)
        
        data = {
            "modules": [
                "Module 0: Start Here",
                "Module 1: Week 1",
                "Module 2: Week 2",
            ]
        }
        order_file.write_text(yaml.dump(data))
        
        # Patch MODULE_ORDER_PATH
        import zaphod.sync_modules as sm
        original_path = sm.MODULE_ORDER_PATH
        sm.MODULE_ORDER_PATH = order_file
        
        try:
            result = load_module_order()
            assert len(result) == 3
            assert result[0] == "Module 0: Start Here"
        finally:
            sm.MODULE_ORDER_PATH = original_path
    
    def test_load_module_order_list_format(self, temp_course_dir, monkeypatch):
        """Should parse bare list format"""
        monkeypatch.chdir(temp_course_dir)
        
        order_file = temp_course_dir / "modules" / "module_order.yaml"
        order_file.parent.mkdir(exist_ok=True)
        
        data = ["Module 1", "Module 2"]
        order_file.write_text(yaml.dump(data))
        
        import zaphod.sync_modules as sm
        original_path = sm.MODULE_ORDER_PATH
        sm.MODULE_ORDER_PATH = order_file
        
        try:
            result = load_module_order()
            assert len(result) == 2
        finally:
            sm.MODULE_ORDER_PATH = original_path
    
    def test_load_module_order_missing(self, temp_course_dir, monkeypatch):
        """Missing file should return empty list"""
        monkeypatch.chdir(temp_course_dir)
        
        import zaphod.sync_modules as sm
        original_path = sm.MODULE_ORDER_PATH
        sm.MODULE_ORDER_PATH = temp_course_dir / "modules" / "nonexistent.yaml"
        
        try:
            result = load_module_order()
            assert result == []
        finally:
            sm.MODULE_ORDER_PATH = original_path


class TestModuleItemChecks:
    """Tests for module item checking"""
    
    def test_module_has_page_item(self, mocker):
        """Should detect existing page items"""
        mock_module = mocker.Mock()
        
        mock_item = mocker.Mock()
        mock_item.type = "Page"
        mock_item.page_url = "welcome"
        
        mock_module.get_module_items.return_value = [mock_item]
        
        result = module_has_item(mock_module, "Page", page_url="welcome")
        assert result is True
    
    def test_module_missing_item(self, mocker):
        """Should return False for missing items"""
        mock_module = mocker.Mock()
        mock_module.get_module_items.return_value = []
        
        result = module_has_item(mock_module, "Page", page_url="missing")
        assert result is False
    
    def test_module_has_assignment_item(self, mocker):
        """Should detect existing assignment items"""
        mock_module = mocker.Mock()
        
        mock_item = mocker.Mock()
        mock_item.type = "Assignment"
        mock_item.content_id = 100
        
        mock_module.get_module_items.return_value = [mock_item]
        
        result = module_has_item(mock_module, "Assignment", content_id=100)
        assert result is True


class TestFolderSortKey:
    """Tests for folder sorting within modules"""
    
    def test_explicit_position(self, tmp_path):
        """Explicit position should take priority"""
        folder = tmp_path / "intro.page"
        meta = {"position": 5}
        
        key = get_folder_sort_key(folder, meta)
        assert key == (0, 5, "intro.page")
    
    def test_numeric_prefix(self, tmp_path):
        """Numeric prefix should be extracted"""
        folder = tmp_path / "01-intro.page"
        
        key = get_folder_sort_key(folder)
        assert key == (1, 1, "01-intro.page")
    
    def test_no_prefix(self, tmp_path):
        """No prefix should sort last"""
        folder = tmp_path / "appendix.page"
        
        key = get_folder_sort_key(folder)
        assert key == (2, 0, "appendix.page")
    
    def test_negative_position(self, tmp_path):
        """Negative position should work"""
        folder = tmp_path / "intro.page"
        meta = {"position": -1}
        
        key = get_folder_sort_key(folder, meta)
        assert key == (0, -1, "intro.page")
