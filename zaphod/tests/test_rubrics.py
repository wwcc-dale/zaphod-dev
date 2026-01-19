# zaphod/tests/test_rubrics.py
"""
Tests for sync_rubrics.py
"""
import pytest
from pathlib import Path
import json
import yaml

from zaphod.sync_rubrics import (
    load_rubric_spec,
    build_rubric_payload,
    expand_rubric_criteria,
    load_rubric_row_snippet,
)
from zaphod.errors import ContentValidationError


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
        rubric_data = {
            "title": "Test Rubric",
            "criteria": [
                {
                    "description": "Criterion 1",
                    "points": 10,
                    "ratings": [{"description": "Good", "points": 10}]
                }
            ]
        }
        
        rubric_path = tmp_path / "rubric.json"
        rubric_path.write_text(json.dumps(rubric_data))
        
        result = load_rubric_spec(rubric_path)
        assert result["title"] == "Test Rubric"
    
    def test_invalid_extension(self, tmp_path):
        """Should raise error for invalid extension"""
        rubric_path = tmp_path / "rubric.txt"
        rubric_path.write_text("invalid")
        
        with pytest.raises((ValueError, RuntimeError)):
            load_rubric_spec(rubric_path)


class TestRubricPayload:
    """Tests for rubric payload building"""
    
    def test_build_basic_payload(self, mocker):
        """Should build valid Canvas API payload"""
        mock_assignment = mocker.Mock()
        mock_assignment.id = 100
        mock_assignment.name = "Test Assignment"
        
        rubric = {
            "title": "Test Rubric",
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
        
        payload = build_rubric_payload(rubric, mock_assignment)
        
        assert payload["title"] == "Test Rubric"
        assert payload["rubric[title]"] == "Test Rubric"
        assert "rubric[criteria][0][description]" in payload
    
    def test_missing_title_raises(self, mocker):
        """Should raise error if title missing"""
        mock_assignment = mocker.Mock()
        mock_assignment.id = 100
        
        rubric = {"criteria": []}
        
        with pytest.raises(ContentValidationError):
            build_rubric_payload(rubric, mock_assignment)
    
    def test_missing_criteria_raises(self, mocker):
        """Should raise error if criteria empty"""
        mock_assignment = mocker.Mock()
        mock_assignment.id = 100
        
        rubric = {"title": "Test", "criteria": []}
        
        with pytest.raises(ContentValidationError):
            build_rubric_payload(rubric, mock_assignment)


class TestRubricRowExpansion:
    """Tests for rubric row snippet expansion"""
    
    def test_expand_with_direct_criteria(self):
        """Should pass through direct criterion dicts"""
        criteria = [
            {"description": "Test", "points": 10, "ratings": []}
        ]
        
        result = expand_rubric_criteria(criteria)
        assert len(result) == 1
        assert result[0]["description"] == "Test"
    
    def test_expand_row_reference(self, tmp_path, monkeypatch):
        """Should expand {{rubric_row:name}} references"""
        # Create rubric row file
        rows_dir = tmp_path / "rubrics" / "rows"
        rows_dir.mkdir(parents=True)
        
        row_data = [{
            "description": "Writing Quality",
            "points": 10,
            "ratings": [{"description": "Good", "points": 10}]
        }]
        (rows_dir / "writing.yaml").write_text(yaml.dump(row_data))
        
        # Patch RUBRIC_ROWS_DIR
        import zaphod.sync_rubrics as sr
        original_dir = sr.RUBRIC_ROWS_DIR
        sr.RUBRIC_ROWS_DIR = rows_dir
        
        try:
            criteria = ["{{rubric_row:writing}}"]
            result = expand_rubric_criteria(criteria)
            
            assert len(result) == 1
            assert result[0]["description"] == "Writing Quality"
        finally:
            sr.RUBRIC_ROWS_DIR = original_dir
