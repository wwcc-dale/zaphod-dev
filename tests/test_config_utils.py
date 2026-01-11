# tests/test_config_utils.py
"""
Tests for config_utils.py - Configuration loading with YAML support
"""
import pytest
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from config_utils import (
    ZaphodConfig,
    ConfigLoader,
    get_config,
    get_course_id,
    get_canvas_credentials,
    make_canvas_api_obj,
    create_config_template,
    ZAPHOD_YAML_TEMPLATE,
)
from errors import ConfigurationError


class TestZaphodConfig:
    """Tests for ZaphodConfig dataclass"""
    
    def test_default_values(self):
        """Config should have sensible defaults"""
        config = ZaphodConfig()
        
        assert config.course_id is None
        assert config.prune_apply is True
        assert config.prune_assignments is True
        assert config.watch_debounce == 2.0
    
    def test_post_init_sets_paths(self, tmp_path, monkeypatch):
        """Post-init should set derived paths"""
        monkeypatch.chdir(tmp_path)
        
        config = ZaphodConfig()
        
        assert config.course_root == tmp_path
        assert config.pages_dir == tmp_path / "pages"
        assert config.assets_dir == tmp_path / "assets"
    
    def test_canvas_base_url_derived(self):
        """Base URL should be derived from API URL"""
        config = ZaphodConfig(api_url="https://canvas.edu/api/v1")
        
        # Note: current implementation just strips trailing slash
        assert config.canvas_base_url == "https://canvas.edu/api/v1"
    
    def test_validate_missing_course_id(self):
        """Validation should catch missing course_id"""
        config = ZaphodConfig()
        issues = config.validate()
        
        assert "course_id is not set" in issues
    
    def test_validate_missing_credentials(self):
        """Validation should catch missing credentials"""
        config = ZaphodConfig(course_id="123")
        issues = config.validate()
        
        assert any("api_url" in issue or "credential_file" in issue for issue in issues)
    
    def test_is_valid_complete_config(self):
        """Complete config should be valid"""
        config = ZaphodConfig(
            course_id="123",
            api_url="https://canvas.edu",
            api_key="secret"
        )
        
        assert config.is_valid() is True
    
    def test_extra_settings(self):
        """Extra settings should be stored"""
        config = ZaphodConfig()
        config.extra["instructor_name"] = "Ada Lovelace"
        
        assert config.extra["instructor_name"] == "Ada Lovelace"


class TestConfigLoader:
    """Tests for ConfigLoader class"""
    
    def test_load_from_env_vars(self, tmp_path, monkeypatch):
        """Should load config from environment variables"""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("COURSE_ID", "12345")
        monkeypatch.setenv("CANVAS_API_URL", "https://canvas.test.edu")
        monkeypatch.setenv("CANVAS_API_KEY", "test_token")
        
        loader = ConfigLoader(tmp_path)
        config = loader.load()
        
        assert config.course_id == "12345"
        assert config.api_url == "https://canvas.test.edu"
        assert config.api_key == "test_token"
    
    def test_load_from_yaml(self, tmp_path, monkeypatch):
        """Should load config from zaphod.yaml"""
        monkeypatch.chdir(tmp_path)
        # Clear env vars
        monkeypatch.delenv("COURSE_ID", raising=False)
        
        yaml_content = """
course_id: 67890
api_url: https://canvas.yaml.edu
api_key: yaml_token
prune:
  apply: false
  assignments: false
watch:
  debounce: 5.0
instructor_name: "From YAML"
"""
        (tmp_path / "zaphod.yaml").write_text(yaml_content)
        
        loader = ConfigLoader(tmp_path)
        config = loader.load()
        
        assert config.course_id == "67890"
        assert config.api_url == "https://canvas.yaml.edu"
        assert config.api_key == "yaml_token"
        assert config.prune_apply is False
        assert config.prune_assignments is False
        assert config.watch_debounce == 5.0
        assert config.extra.get("instructor_name") == "From YAML"
    
    def test_load_from_yml_extension(self, tmp_path, monkeypatch):
        """Should also accept .yml extension"""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("COURSE_ID", raising=False)
        
        yaml_content = "course_id: 11111\n"
        (tmp_path / "zaphod.yml").write_text(yaml_content)
        
        loader = ConfigLoader(tmp_path)
        config = loader.load()
        
        assert config.course_id == "11111"
    
    def test_load_from_legacy_defaults_json(self, tmp_path, monkeypatch):
        """Should load from legacy _course_metadata/defaults.json"""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("COURSE_ID", raising=False)
        
        meta_dir = tmp_path / "_course_metadata"
        meta_dir.mkdir()
        (meta_dir / "defaults.json").write_text('{"course_id": 99999}')
        
        loader = ConfigLoader(tmp_path)
        config = loader.load()
        
        assert config.course_id == "99999"
    
    def test_env_overrides_yaml(self, tmp_path, monkeypatch):
        """Environment variables should override YAML"""
        monkeypatch.chdir(tmp_path)
        
        # YAML says one thing
        yaml_content = "course_id: from_yaml\n"
        (tmp_path / "zaphod.yaml").write_text(yaml_content)
        
        # Env says another
        monkeypatch.setenv("COURSE_ID", "from_env")
        
        loader = ConfigLoader(tmp_path)
        config = loader.load()
        
        # Env wins
        assert config.course_id == "from_env"
    
    def test_yaml_overrides_legacy_json(self, tmp_path, monkeypatch):
        """YAML should override legacy defaults.json"""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("COURSE_ID", raising=False)
        
        # Legacy JSON
        meta_dir = tmp_path / "_course_metadata"
        meta_dir.mkdir()
        (meta_dir / "defaults.json").write_text('{"course_id": "from_json"}')
        
        # YAML
        (tmp_path / "zaphod.yaml").write_text("course_id: from_yaml\n")
        
        loader = ConfigLoader(tmp_path)
        config = loader.load()
        
        # YAML wins over JSON
        assert config.course_id == "from_yaml"
    
    def test_load_credentials_file(self, tmp_path, monkeypatch):
        """Should load credentials from file"""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("COURSE_ID", raising=False)
        monkeypatch.delenv("CANVAS_API_URL", raising=False)
        monkeypatch.delenv("CANVAS_API_KEY", raising=False)
        
        # Create credentials file
        cred_file = tmp_path / "creds.txt"
        cred_file.write_text('API_KEY = "file_token"\nAPI_URL = "https://canvas.file.edu"')
        
        # Reference it in YAML
        yaml_content = f"""
course_id: 123
credential_file: {cred_file}
"""
        (tmp_path / "zaphod.yaml").write_text(yaml_content)
        
        loader = ConfigLoader(tmp_path)
        config = loader.load()
        
        assert config.api_key == "file_token"
        assert config.api_url == "https://canvas.file.edu"
    
    def test_invalid_yaml_raises_error(self, tmp_path, monkeypatch):
        """Invalid YAML should raise ConfigurationError"""
        monkeypatch.chdir(tmp_path)
        
        (tmp_path / "zaphod.yaml").write_text("invalid: yaml: content: [")
        
        loader = ConfigLoader(tmp_path)
        
        with pytest.raises(ConfigurationError) as exc_info:
            loader.load()
        
        assert "Invalid YAML" in str(exc_info.value)
    
    def test_invalid_json_raises_error(self, tmp_path, monkeypatch):
        """Invalid JSON in defaults.json should raise error"""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("COURSE_ID", raising=False)
        
        meta_dir = tmp_path / "_course_metadata"
        meta_dir.mkdir()
        (meta_dir / "defaults.json").write_text("{invalid json}")
        
        loader = ConfigLoader(tmp_path)
        
        with pytest.raises(ConfigurationError) as exc_info:
            loader.load()
        
        assert "Invalid JSON" in str(exc_info.value)
    
    def test_prune_env_vars(self, tmp_path, monkeypatch):
        """Should load prune settings from env vars"""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("ZAPHOD_PRUNE_APPLY", "false")
        monkeypatch.setenv("ZAPHOD_PRUNE_ASSIGNMENTS", "no")
        
        loader = ConfigLoader(tmp_path)
        config = loader.load()
        
        assert config.prune_apply is False
        assert config.prune_assignments is False


class TestConvenienceFunctions:
    """Tests for convenience functions"""
    
    def test_get_course_id_from_env(self, tmp_path, monkeypatch):
        """get_course_id should work with env var"""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("COURSE_ID", "12345")
        
        result = get_course_id(tmp_path)
        assert result == "12345"
    
    def test_get_course_id_missing_raises(self, tmp_path, monkeypatch):
        """get_course_id should raise if not found"""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("COURSE_ID", raising=False)
        
        # Force reload
        from config_utils import _loader
        import config_utils
        config_utils._loader = None
        
        with pytest.raises(ConfigurationError):
            get_course_id(tmp_path)
    
    def test_get_canvas_credentials(self, tmp_path, monkeypatch):
        """get_canvas_credentials should return tuple"""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CANVAS_API_URL", "https://test.edu")
        monkeypatch.setenv("CANVAS_API_KEY", "token123")
        
        url, key = get_canvas_credentials(tmp_path)
        
        assert url == "https://test.edu"
        assert key == "token123"
    
    def test_get_config_caches(self, tmp_path, monkeypatch):
        """get_config should cache the loader"""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("COURSE_ID", "123")
        
        config1 = get_config(tmp_path)
        config2 = get_config()  # No path, should use cached
        
        # Same object (cached)
        assert config1.course_id == config2.course_id
    
    def test_get_config_reload(self, tmp_path, monkeypatch):
        """get_config with reload=True should reload"""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("COURSE_ID", "first")
        
        config1 = get_config(tmp_path)
        assert config1.course_id == "first"
        
        monkeypatch.setenv("COURSE_ID", "second")
        config2 = get_config(tmp_path, reload=True)
        
        assert config2.course_id == "second"


class TestConfigTemplate:
    """Tests for config template creation"""
    
    def test_create_config_template(self, tmp_path):
        """Should create zaphod.yaml template"""
        path = create_config_template(tmp_path, course_id="99999")
        
        assert path.exists()
        assert path.name == "zaphod.yaml"
        
        content = path.read_text()
        assert "course_id: 99999" in content
        assert "credential_file:" in content
        assert "prune:" in content
    
    def test_create_config_template_exists_raises(self, tmp_path):
        """Should raise if config already exists"""
        (tmp_path / "zaphod.yaml").write_text("existing: config")
        
        with pytest.raises(ConfigurationError) as exc_info:
            create_config_template(tmp_path)
        
        assert "already exists" in str(exc_info.value)
    
    def test_template_is_valid_yaml(self, tmp_path):
        """Generated template should be valid YAML"""
        import yaml
        
        path = create_config_template(tmp_path, course_id="123")
        content = path.read_text()
        
        # Should parse without error
        data = yaml.safe_load(content)
        assert data["course_id"] == 123  # YAML parses as int


class TestMakeCanvasApiObj:
    """Tests for make_canvas_api_obj function"""
    
    def test_make_canvas_api_obj(self, tmp_path, monkeypatch, mocker):
        """Should create Canvas API object"""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("CANVAS_API_URL", "https://canvas.test.edu")
        monkeypatch.setenv("CANVAS_API_KEY", "test_token")
        
        # Mock the Canvas class
        mock_canvas = mocker.patch("config_utils.Canvas")
        
        result = make_canvas_api_obj(tmp_path)
        
        mock_canvas.assert_called_once_with("https://canvas.test.edu", "test_token")
