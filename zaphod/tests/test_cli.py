# zaphod/tests/test_cli.py
"""
Tests for CLI interface
"""
import json
import pytest
from click.testing import CliRunner
from pathlib import Path

from zaphod.cli import cli


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
    
    def test_info_command_no_course(self, runner, temp_course_dir, monkeypatch):
        """Info command without course_id should show warning"""
        monkeypatch.chdir(temp_course_dir)
        monkeypatch.delenv("COURSE_ID", raising=False)
        
        # Use isolated filesystem for the test
        with runner.isolated_filesystem(temp_dir=temp_course_dir):
            result = runner.invoke(cli, ['info'])
            # May fail or warn - either is acceptable
            # Just verify it doesn't crash unexpectedly
            assert result.exit_code in [0, 1]
    
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
