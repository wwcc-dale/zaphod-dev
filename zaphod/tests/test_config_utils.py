# zaphod/tests/test_config_utils.py
"""
Tests for config_utils.py
"""
import pytest
from pathlib import Path
import json

from zaphod.config_utils import get_course_id, get_config, ConfigLoader, ConfigurationError


class TestGetCourseId:
    """Tests for get_course_id function"""
    
    def test_from_environment(self, monkeypatch, temp_course_dir):
        """Should read course ID from environment variable"""
        monkeypatch.setenv("COURSE_ID", "12345")
        monkeypatch.chdir(temp_course_dir)
        result = get_course_id(temp_course_dir)
        assert result == "12345"
    
    def test_from_defaults_json(self, monkeypatch, temp_course_dir):
        """Should read from defaults.json when env var not set"""
        monkeypatch.delenv("COURSE_ID", raising=False)
        monkeypatch.chdir(temp_course_dir)
        
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
        monkeypatch.chdir(temp_course_dir)
        
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
        monkeypatch.chdir(temp_course_dir)
        
        # Note: ConfigurationError is imported from config_utils, not errors
        with pytest.raises(ConfigurationError):
            get_course_id(temp_course_dir)


class TestGetConfig:
    """Tests for get_config function"""
    
    def test_returns_config_object(self, temp_course_dir, monkeypatch):
        """Should return ZaphodConfig object"""
        monkeypatch.setenv("COURSE_ID", "12345")
        monkeypatch.chdir(temp_course_dir)
        config = get_config(temp_course_dir)
        assert config.course_id == "12345"
    
    def test_loads_from_zaphod_yaml(self, temp_course_dir, monkeypatch):
        """Should load settings from zaphod.yaml"""
        monkeypatch.delenv("COURSE_ID", raising=False)
        monkeypatch.chdir(temp_course_dir)
        
        yaml_content = """
course_id: "yaml_course_id"
course_name: "Test Course"
"""
        (temp_course_dir / "zaphod.yaml").write_text(yaml_content)
        
        config = get_config(temp_course_dir)
        assert config.course_id == "yaml_course_id"
        assert config.course_name == "Test Course"
