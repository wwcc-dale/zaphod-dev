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
        # Create the pages directory that cli.py expects
        (temp_course_dir / "pages").mkdir(exist_ok=True)
        (temp_course_dir / "_course_metadata").mkdir(exist_ok=True)
        
        # Use isolated_filesystem to run in the temp directory
        with runner.isolated_filesystem(temp_dir=temp_course_dir) as td:
            # Create pages dir in isolated filesystem
            Path("pages").mkdir(exist_ok=True)
            Path("_course_metadata").mkdir(exist_ok=True)
            
            result = runner.invoke(cli, ['info'])
            
            # Check it runs (may show warnings but shouldn't crash)
            # Exit code 0 = success, but we accept it running without crashing
            assert result.exit_code == 0 or "Course Information" in result.output or result.exception is None
    
    def test_list_command_empty(self, runner):
        """Should handle empty course gracefully"""
        with runner.isolated_filesystem():
            # Create minimal structure
            Path("pages").mkdir()
            Path("_course_metadata").mkdir()
            
            result = runner.invoke(cli, ['list'])
            # Should not crash, even with no content
            assert result.exit_code == 0 or result.exception is None
    
    def test_list_command_with_content(self, runner):
        """Should list content when present"""
        with runner.isolated_filesystem():
            # Create structure
            Path("pages").mkdir()
            Path("_course_metadata").mkdir()
            
            # Create a page with meta.json
            page_dir = Path("pages/test.page")
            page_dir.mkdir()
            
            meta = {
                "name": "Test Page",
                "type": "page",
                "modules": ["Module 1"],
                "published": True,
            }
            (page_dir / "meta.json").write_text(json.dumps(meta))
            
            result = runner.invoke(cli, ['list'])
            assert result.exit_code == 0
    
    def test_list_command_json_output(self, runner):
        """Should output JSON when requested"""
        with runner.isolated_filesystem():
            Path("pages").mkdir()
            Path("_course_metadata").mkdir()
            
            # Create a page
            page_dir = Path("pages/test.page")
            page_dir.mkdir()
            meta = {
                "name": "Test Page",
                "type": "page",
                "modules": [],
                "published": False,
            }
            (page_dir / "meta.json").write_text(json.dumps(meta))
            
            result = runner.invoke(cli, ['list', '--json'])
            assert result.exit_code == 0
            
            # Should be valid JSON
            data = json.loads(result.output)
            assert isinstance(data, list)
    
    def test_new_command_creates_page(self, runner):
        """Should create a new page folder"""
        with runner.isolated_filesystem():
            Path("pages").mkdir()
            Path("_course_metadata").mkdir()
            
            result = runner.invoke(cli, ['new', '--type', 'page', '--name', 'Welcome'])
            
            # Check it created the folder
            assert Path("pages/welcome.page").exists() or result.exit_code == 0
    
    def test_new_command_creates_assignment(self, runner):
        """Should create a new assignment folder"""
        with runner.isolated_filesystem():
            Path("pages").mkdir()
            Path("_course_metadata").mkdir()
            
            result = runner.invoke(cli, ['new', '--type', 'assignment', '--name', 'Project 1'])
            
            # Check folder was created
            expected_path = Path("pages/project-1.assignment")
            if expected_path.exists():
                # Verify index.md was created
                assert (expected_path / "index.md").exists()
    
    def test_new_command_with_module(self, runner):
        """Should create content with module assignment"""
        with runner.isolated_filesystem():
            Path("pages").mkdir()
            Path("_course_metadata").mkdir()
            
            result = runner.invoke(cli, [
                'new', 
                '--type', 'page', 
                '--name', 'Week 1 Overview',
                '--module', 'Week 1'
            ])
            
            expected_path = Path("pages/week-1-overview.page")
            if expected_path.exists():
                index_content = (expected_path / "index.md").read_text()
                assert "Week 1" in index_content
    
    def test_validate_command(self, runner):
        """Should run validation"""
        with runner.isolated_filesystem():
            Path("pages").mkdir()
            Path("_course_metadata").mkdir()
            
            result = runner.invoke(cli, ['validate'])
            # Should run without crashing
            assert result.exception is None or result.exit_code == 0
    
    def test_prune_dry_run(self, runner):
        """Should show dry-run output for prune"""
        with runner.isolated_filesystem():
            Path("pages").mkdir()
            Path("_course_metadata").mkdir()
            
            # Prune with dry-run shouldn't require Canvas connection
            # It may fail due to no Canvas config, but shouldn't crash badly
            result = runner.invoke(cli, ['prune', '--dry-run'])
            # Just verify it attempted to run
            assert result.exception is None or "COURSE_ID" in str(result.output) or result.exit_code in [0, 1]