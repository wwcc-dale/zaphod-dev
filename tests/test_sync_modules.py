# tests/test_sync_modules.py
"""
Tests for sync_modules.py
"""
import pytest
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from sync_modules import (
    load_module_order,
    module_has_item,
)


class TestModuleOrder:
    """Tests for module ordering"""
    
    def test_load_module_order_dict_format(self, temp_course_dir):
        """Should parse dict format with 'modules' key"""
        import yaml
        
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
        
        result = load_module_order()
        assert len(result) == 3
        assert result[0] == "Module 0: Start Here"
    
    def test_load_module_order_list_format(self, temp_course_dir):
        """Should parse bare list format"""
        import yaml
        
        order_file = temp_course_dir / "modules" / "module_order.yaml"
        order_file.parent.mkdir(exist_ok=True)
        
        data = ["Module 1", "Module 2"]
        order_file.write_text(yaml.dump(data))
        
        result = load_module_order()
        assert len(result) == 2
    
    def test_load_module_order_missing(self, temp_course_dir):
        """Missing file should return empty list"""
        result = load_module_order()
        assert result == []


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