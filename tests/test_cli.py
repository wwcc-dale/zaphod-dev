# tests/test_cli.py
"""
Tests for CLI interface
"""
import json
import pytest
from click.testing import CliRunner
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from cli import cli


class TestCLI:
    """Tests for CLI commands"""
    
    @pytest.fixture
    def runner(self):
        return CliRunner()
    
    def test_cli_help(self, runner):
        """Should show help message"""
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert "Zaphod" in result.output
    
    def test_version_command(self, runner):
        """Should show version"""
        result = runner.invoke(cli, ['version'])
        assert result.exit_code == 0
        assert "Zaphod CLI" in result.output
    
    def test_info_command(self, runner, temp_course_dir, monkeypatch):
        """Should display course info"""
        monkeypatch.chdir(temp_course_dir)
        result = runner.invoke(cli, ['info'])
        assert result.exit_code == 0
        assert "Course Information" in result.output
    
    def test_list_command(self, runner, sample_page_folder, monkeypatch):
        """Should list content"""
        monkeypatch.chdir(sample_page_folder.parent.parent)
        
        # Create meta.json for the page
        meta = {
            "name": "Test Page",
            "type": "page",
            "modules": ["Module 1"],
        }
        (sample_page_folder / "meta.json").write_text(json.dumps(meta))
        
        result = runner.invoke(cli, ['list'])
        assert result.exit_code == 0
        # Should show content in output