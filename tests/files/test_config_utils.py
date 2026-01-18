# tests/test_config_utils.py
"""
Tests for config_utils.py
"""
import pytest
from pathlib import Path
import json

from zaphod.config_utils import get_course_id
from zaphod.errors import ConfigurationError


class TestGetCourseId:
    """Tests for get_course_id function"""
    
    def test_from_environment(self, monkeypatch, temp_course_dir):
        """Should read course ID from environment variable"""
        monkeypatch.setenv("COURSE_ID", "12345")
        result = get_course_id(temp_course_dir)
        assert result == "12345"
    
    def test_from_defaults_json(self, monkeypatch, temp_course_dir):
        """Should read from defaults.json when env var not set"""
        monkeypatch.delenv("COURSE_ID", raising=False)
        
        # Create defaults.json
        meta_dir = temp_course_dir / "_course_metadata"
        meta_dir.mkdir(exist_ok=True)
        defaults = {"course_id": "67890"}
        (meta_dir / "defaults.json").write_text(json.dumps(defaults))
        
        result = get_course_id(temp_course_dir)
        assert result == "67890"
    
    def test_env_takes_priority(self, monkeypatch, temp_course_dir):
        """Environment variable should take priority over defaults.json"""
        monkeypatch.setenv("COURSE_ID", "env_id")
        
        # Create defaults.json with different value
        meta_dir = temp_course_dir / "_course_metadata"
        meta_dir.mkdir(exist_ok=True)
        defaults = {"course_id": "file_id"}
        (meta_dir / "defaults.json").write_text(json.dumps(defaults))
        
        result = get_course_id(temp_course_dir)
        assert result == "env_id"
    
    def test_missing_raises_error(self, monkeypatch, temp_course_dir):
        """Should raise ConfigurationError when course ID not found"""
        monkeypatch.delenv("COURSE_ID", raising=False)
        
        with pytest.raises(ConfigurationError):
            get_course_id(temp_course_dir)
