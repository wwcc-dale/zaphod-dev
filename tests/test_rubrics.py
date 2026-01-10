# tests/test_rubrics.py
"""
Tests for sync_rubrics.py
"""
import pytest
from pathlib import Path
import json
import yaml
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from sync_rubrics import (
    load_rubric_spec,
    build_rubric_payload,
)


class TestRubricLoading:
    """Tests for rubric file loading"""
    
    def test_load_yaml_rubric(self, tmp_path):
        """Should load YAML rubric spec"""
        rubric_data = {
            "title": "Assignment Rubric",
            "criteria": [
                {
                    "description": "Quality",
                    "points": 10,
                    "ratings": [
                        {"description": "Excellent", "points": 10},
                        {"description": "Good", "points": 7},
                    ]
                }
            ]
        }
        
        rubric_path = tmp_path / "rubric.yaml"
        rubric_path.write_text(yaml.dump(rubric_data))
        
        result = load_rubric_spec(rubric_path)
        assert result["title"] == "Assignment Rubric"
        assert len(result["criteria"]) == 1
    
    def test_load_json_rubric(self, tmp_path):
        """Should load JSON rubric spec"""
        rubric_data = {"title": "Test Rubric", "criteria": []}
        
        rubric_path = tmp_path / "rubric.json"
        rubric_path.write_text(json.dumps(rubric_data))
        
        result = load_rubric_spec(rubric_path)
        assert result["title"] == "Test Rubric"
    
    def test_invalid_extension(self, tmp_path):
        """Should raise error for invalid extension"""
        rubric_path = tmp_path / "rubric.txt"
        rubric_path.write_text("invalid")
        
        with pytest.raises(ValueError, match="Unsupported rubric file"):
            load_rubric_spec(rubric_path)