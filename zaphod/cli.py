# cli.py - Standalone CLI wrapper for Zaphod
"""
Zaphod CLI - Unified interface for course management

Usage:
    zaphod sync [--watch] [--course-id ID]
    zaphod validate [--verbose]
    zaphod prune [--dry-run] [--assignments]
    zaphod list [--type TYPE]
    zaphod new --type TYPE --name NAME
    zaphod info
    zaphod ui [--port PORT]

This CLI wraps existing Zaphod scripts without modifying them.
"""

import click
import subprocess
import sys
import os
import json
import webbrowser
from pathlib import Path
from typing import Optional, List
from datetime import datetime
import time


# ============================================================================
# Configuration & Utilities
# ============================================================================

class ZaphodContext:
    """Shared context for CLI commands"""
    
    def __init__(self):
        self.course_root = Path.cwd()
        self.pages_dir = self.course_root / "pages"
        self.metadata_dir = self.course_root / "_course_metadata"
        self.zaphod_root = self._find_zaphod_root()
        self.python_exe = self._find_python()
        
    def _find_zaphod_root(self) -> Optional[Path]:
        """Find the zaphod script directory"""
        # Try common locations
        candidates = [
            self.course_root.parent / "zaphod",
            self.course_root / "zaphod",
            Path(__file__).parent,
        ]
        for path in candidates:
            if (path / "publish_all.py").exists():
                return path
        return None
    
    def _find_python(self) -> str:
        """Find Python executable (prefer venv if available)"""
        if self.zaphod_root:
            venv_python = self.zaphod_root / ".venv" / "bin" / "python"
            if venv_python.exists():
                return str(venv_python)
        return sys.executable
    
    def get_course_id(self) -> Optional[str]:
        """Get course ID from env or defaults.json"""
        course_id = os.environ.get("COURSE_ID")
        if course_id:
            return course_id
        
        defaults_path = self.metadata_dir / "defaults.json"
        if defaults_path.exists():
            try:
                data = json.loads(defaults_path.read_text())
                return data.get("course_id")
            except Exception:
                pass
        return None
    
    def run_script(self, script_name: str, env: Optional[dict] = None) -> subprocess.CompletedProcess:
        """Run a Zaphod script"""
        if not self.zaphod_root:
            click.echo("✗ Could not find Zaphod scripts directory", err=True)
            sys.exit(1)
        
        script_path = self.zaphod_root / script_name
        if not script_path.exists():
            click.echo(f"✗ Script not found: {script_path}", err=True)
            sys.exit(1)
        
        full_env = os.environ.copy()
        if env:
            full_env.update(env)
        
        # Ensure credentials are set
        if "CANVAS_CREDENTIAL_FILE" not in full_env:
            full_env["CANVAS_CREDENTIAL_FILE"] = str(Path.home() / ".canvas" / "credentials.txt")
        
        return subprocess.run(
            [self.python_exe, str(script_path)],
            cwd=str(self.course_root),
            env=full_env,
            text=True
        )


# ============================================================================
# Click Group Setup
# ============================================================================

@click.group()
@click.pass_context
def cli(ctx):
    """
    Zaphod - Local-first Canvas course management
    
    Manage your Canvas course content using local Markdown files.
    """
    ctx.obj = ZaphodContext()


# ============================================================================
# Sync Commands
# ============================================================================

@cli.command()
@click.option('--watch', is_flag=True, help='Watch for changes and auto-sync')
@click.option('--course-id', type=int, help='Override course ID')
@click.option('--assets-only', is_flag=True, help='Only upload assets, skip content')
@click.pass_obj
def sync(ctx: ZaphodContext, watch: bool, course_id: Optional[int], assets_only: bool):
    """
    Sync local content to Canvas
    
    Examples:
        zaphod sync                    # Sync once
        zaphod sync --watch            # Watch and auto-sync
        zaphod sync --course-id 12345  # Override course ID
        zaphod sync --assets-only      # Only upload media files
    """
    if watch:
        click.echo("👀 Starting watch mode (Ctrl+C to stop)...")
        click.echo(f"📂 Watching: {ctx.course_root}")
        click.echo()
        
        env = {}
        if course_id:
            env["COURSE_ID"] = str(course_id)
        
        try:
            ctx.run_script("watch_and_publish.py", env=env)
        except KeyboardInterrupt:
            click.echo("\n\n👋 Stopping watch mode...")
    else:
        click.echo("🚀 Running sync pipeline...")
        
        env = {}
        if course_id:
            env["COURSE_ID"] = str(course_id)
        
        # Run the pipeline steps manually
        steps = [
            ("frontmatter_to_meta.py", "📝 Processing frontmatter"),
        ]
        
        if assets_only:
            steps.append(("publish_all.py --assets-only", "📦 Uploading assets"))
        else:
            steps.extend([
                ("publish_all.py", "📤 Publishing content"),
                ("sync_modules.py", "📚 Syncing modules"),
                ("sync_clo_via_csv.py", "🎯 Syncing outcomes"),
                ("sync_rubrics.py", "📋 Syncing rubrics"),
                ("sync_quiz_banks.py", "❓ Syncing quizzes"),
            ])
        
        for script, description in steps:
            click.echo(f"\n{description}...")
            result = ctx.run_script(script.split()[0], env=env)
            if result.returncode != 0:
                click.echo(f"⚠️  {script} completed with warnings/errors")
        
        click.echo("\n✅ Sync complete!")


# ============================================================================
# Content Management
# ============================================================================

@cli.command()
@click.option('--type', 'content_type', type=click.Choice(['page', 'assignment', 'link', 'file', 'all']), 
              default='all', help='Filter by content type')
@click.option('--module', help='Filter by module name')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
@click.pass_obj
def list(ctx: ZaphodContext, content_type: str, module: Optional[str], as_json: bool):
    """
    List course content
    
    Examples:
        zaphod list                      # List all content
        zaphod list --type assignment    # Only assignments
        zaphod list --module "Week 1"    # Content in specific module
        zaphod list --json               # JSON output
    """
    if not ctx.pages_dir.exists():
        click.echo("✗ No pages/ directory found", err=True)
        sys.exit(1)
    
    items = []
    extensions = ['.page', '.assignment', '.link', '.file'] if content_type == 'all' else [f'.{content_type}']
    
    for ext in extensions:
        for folder in ctx.pages_dir.rglob(f"*{ext}"):
            meta_path = folder / "meta.json"
            if not meta_path.exists():
                continue
            
            try:
                meta = json.loads(meta_path.read_text())
                
                # Filter by module if specified
                if module:
                    modules = meta.get("modules", [])
                    if module not in modules:
                        continue
                
                items.append({
                    "name": meta.get("name", "Untitled"),
                    "type": meta.get("type", "unknown"),
                    "modules": meta.get("modules", []),
                    "published": meta.get("published", False),
                    "path": str(folder.relative_to(ctx.course_root)),
                })
            except Exception as e:
                click.echo(f"⚠️  Could not read {folder.name}: {e}", err=True)
    
    if as_json:
        click.echo(json.dumps(items, indent=2))
    else:
        if not items:
            click.echo("No content found.")
            return
        
        # Group by type
        by_type = {}
        for item in items:
            t = item["type"]
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(item)
        
        for content_type, type_items in sorted(by_type.items()):
            click.echo(f"\n{content_type.upper()}S ({len(type_items)}):")
            for item in sorted(type_items, key=lambda x: x["name"]):
                status = "✓" if item["published"] else "○"
                modules_str = ", ".join(item["modules"]) if item["modules"] else "No modules"
                click.echo(f"  {status} {item['name']}")
                click.echo(f"     {modules_str}")


@cli.command()
@click.option('--type', 'content_type', type=click.Choice(['page', 'assignment', 'link']), 
              required=True, help='Content type to create')
@click.option('--name', required=True, help='Content name')
@click.option('--module', multiple=True, help='Module(s) to add content to')
@click.pass_obj
def new(ctx: ZaphodContext, content_type: str, name: str, module: tuple):
    """
    Create new content item
    
    Examples:
        zaphod new --type page --name "Welcome"
        zaphod new --type assignment --name "Project 1" --module "Week 1"
    """
    # Generate folder name
    folder_name = f"{name.lower().replace(' ', '-')}.{content_type}"
    folder_path = ctx.pages_dir / folder_name
    
    if folder_path.exists():
        click.echo(f"✗ Content already exists: {folder_path}", err=True)
        sys.exit(1)
    
    # Create folder
    folder_path.mkdir(parents=True, exist_ok=True)
    
    # Create index.md with frontmatter
    frontmatter = [
        "---",
        f'name: "{name}"',
        f'type: "{content_type}"',
    ]
    
    if module:
        frontmatter.append("modules:")
        for m in module:
            frontmatter.append(f'  - "{m}"')
    else:
        frontmatter.append("modules: []")
    
    frontmatter.append("published: false")
    
    if content_type == "assignment":
        frontmatter.extend([
            "",
            "# assignment settings",
            "points_possible: 100",
            "submission_types:",
            '  - "online_upload"',
        ])
    elif content_type == "link":
        frontmatter.extend([
            "",
            'external_url: "https://example.com"',
            "new_tab: true",
        ])
    
    frontmatter.append("---")
    frontmatter.append("")
    frontmatter.append(f"# {name}")
    frontmatter.append("")
    frontmatter.append("Add your content here...")
    frontmatter.append("")
    
    index_path = folder_path / "index.md"
    index_path.write_text("\n".join(frontmatter))
    
    click.echo(f"✅ Created: {folder_path}")
    click.echo(f"📝 Edit: {index_path}")


# ============================================================================
# Validation
# ============================================================================

@cli.command()
@click.option('--verbose', '-v', is_flag=True, help='Show more details')
@click.pass_obj
def validate(ctx: ZaphodContext, verbose: bool):
    """
    Validate course content before syncing
    
    Checks for:
    - Missing required frontmatter fields
    - Invalid YAML syntax
    - Missing include files
    - Quiz questions without correct answers
    - Rubric configuration errors
    - Undefined module references
    
    Examples:
        zaphod validate           # Check for issues
        zaphod validate -v        # Verbose output
    """
    click.echo(f"🔍 Validating course: {ctx.course_root}\n")
    
    # Import the validator
    try:
        from validate import CourseValidator, print_results
    except ImportError:
        # Fall back to running as script
        ctx.run_script("validate.py")
        return
    
    validator = CourseValidator(ctx.course_root)
    result = validator.validate()
    print_results(result, verbose=verbose)
    
    # Exit with error code if invalid
    if not result.is_valid:
        sys.exit(1)


# ============================================================================
# Prune
# ============================================================================

@cli.command()
@click.option('--dry-run', is_flag=True, help='Show what would be deleted without deleting')
@click.option('--assignments', is_flag=True, help='Include assignments in pruning')
@click.pass_obj
def prune(ctx: ZaphodContext, dry_run: bool, assignments: bool):
    """
    Remove orphaned Canvas content
    
    Deletes Canvas items not present in local files:
    - Pages not in any .page folder
    - Assignments not in any .assignment folder (with --assignments)
    - Empty modules
    - Module items in wrong modules
    
    Examples:
        zaphod prune --dry-run              # Preview changes
        zaphod prune                        # Delete orphaned content
        zaphod prune --assignments          # Include assignments
    """
    env = {}
    if dry_run:
        env["ZAPHOD_PRUNE_APPLY"] = "false"
    else:
        env["ZAPHOD_PRUNE_APPLY"] = "true"
    
    if assignments:
        env["ZAPHOD_PRUNE_ASSIGNMENTS"] = "true"
    
    if dry_run:
        click.echo("🔍 Dry run - showing what would be deleted...\n")
    else:
        click.confirm("⚠️  This will delete content from Canvas. Continue?", abort=True)
        click.echo("\n🗑️  Pruning orphaned content...\n")
    
    ctx.run_script("prune_canvas_content.py", env=env)
    
    if not dry_run:
        click.echo("\n✅ Prune complete!")


# ============================================================================
# Info & Status
# ============================================================================

@cli.command()
@click.pass_obj
def info(ctx: ZaphodContext):
    """
    Show course information and status
    
    Displays:
    - Course metadata
    - Content statistics
    - Last sync time
    - Configuration
    """
    click.echo("📋 Course Information\n")
    click.echo("=" * 60)
    
    # Course metadata
    course_id = ctx.get_course_id()
    if course_id:
        click.echo(f"Course ID: {course_id}")
    else:
        click.echo("Course ID: Not set (use COURSE_ID env var)")
    
    click.echo(f"Course Root: {ctx.course_root}")
    click.echo(f"Zaphod Scripts: {ctx.zaphod_root or 'Not found'}")
    
    # Sync status
    click.echo("\n📅 Last Sync")
    click.echo("-" * 60)
    state_file = ctx.metadata_dir / "watch_state.json"
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text())
            last_run = state.get("last_run_datetime", "Never")
            run_count = state.get("run_count", 0)
            click.echo(f"Last Run: {last_run}")
            click.echo(f"Total Runs: {run_count}")
        except Exception:
            click.echo("Last Run: Unknown")
    else:
        click.echo("Last Run: Never")
    
    # Content statistics
    click.echo("\n📚 Content Statistics")
    click.echo("-" * 60)
    
    if ctx.pages_dir.exists():
        stats = {
            "pages": len(list(ctx.pages_dir.rglob("*.page"))),
            "assignments": len(list(ctx.pages_dir.rglob("*.assignment"))),
            "links": len(list(ctx.pages_dir.rglob("*.link"))),
            "files": len(list(ctx.pages_dir.rglob("*.file"))),
        }
        
        for content_type, count in stats.items():
            click.echo(f"{content_type.capitalize()}: {count}")
    else:
        click.echo("No pages/ directory found")
    
    # Check for issues
    click.echo("\n🔍 Quick Check")
    click.echo("-" * 60)
    
    checks = []
    if not ctx.zaphod_root:
        checks.append("⚠️  Zaphod scripts not found")
    if not course_id:
        checks.append("⚠️  Course ID not configured")
    
    cred_file = Path(os.environ.get("CANVAS_CREDENTIAL_FILE", Path.home() / ".canvas" / "credentials.txt"))
    if not cred_file.exists():
        checks.append(f"⚠️  Canvas credentials not found at {cred_file}")
    
    if checks:
        for check in checks:
            click.echo(check)
    else:
        click.echo("✅ All checks passed")


# ============================================================================
# Export
# ============================================================================

@cli.command()
@click.option('--output', '-o', type=click.Path(), help='Output file path (default: _course_metadata/<n>_export.imscc)')
@click.option('--title', '-t', help='Course title (default: from zaphod.yaml or folder name)')
@click.option('--format', 'export_format', type=click.Choice(['cartridge', 'qti']), default='cartridge',
              help='Export format: cartridge (full course) or qti (quizzes only)')
@click.pass_obj
def export(ctx: ZaphodContext, output: Optional[str], title: Optional[str], export_format: str):
    """
    Export course to portable format
    
    Creates an IMS Common Cartridge (.imscc) package that can be
    imported into Canvas, Moodle, Blackboard, Brightspace, or other
    CC-compliant LMS platforms.
    
    Examples:
        zaphod export                           # Export full course
        zaphod export --output course.imscc     # Custom output path
        zaphod export --title "My Course"       # Override title
        zaphod export --format qti              # Quizzes only (future)
    """
    if export_format == 'qti':
        click.echo("⚠️  QTI-only export not yet implemented")
        click.echo("Use --format cartridge for full course export (includes quizzes)")
        sys.exit(1)
    
    click.echo(f"📦 Exporting course from: {ctx.course_root}")
    
    # Build command
    script_path = ctx.zaphod_root / "export_cartridge.py" if ctx.zaphod_root else None
    
    if not script_path or not script_path.exists():
        # Try relative to this file
        script_path = Path(__file__).parent / "export_cartridge.py"
    
    if not script_path.exists():
        click.echo("✗ export_cartridge.py not found", err=True)
        sys.exit(1)
    
    cmd = [ctx.python_exe, str(script_path)]
    
    if output:
        cmd.extend(['--output', output])
    if title:
        cmd.extend(['--title', title])
    
    result = subprocess.run(cmd, cwd=str(ctx.course_root))
    
    if result.returncode == 0:
        click.echo("\n✅ Export complete!")
    else:
        click.echo("\n✗ Export failed", err=True)
        sys.exit(result.returncode)


# ============================================================================
# UI Server
# ============================================================================

@cli.command()
@click.option('--port', default=8000, help='Port to run UI server on')
@click.option('--no-browser', is_flag=True, help='Do not open browser automatically')
@click.pass_obj
def ui(ctx: ZaphodContext, port: int, no_browser: bool):
    """
    Launch web UI
    
    Starts a local web server with a graphical interface for
    managing course content.
    
    Examples:
        zaphod ui                  # Start UI on port 8000
        zaphod ui --port 3000      # Use different port
        zaphod ui --no-browser     # Don't open browser
    """
    click.echo(f"🚀 Starting Zaphod UI on http://localhost:{port}")
    click.echo("Press Ctrl+C to stop")
    
    if not no_browser:
        time.sleep(1)
        webbrowser.open(f"http://localhost:{port}")
    
    # Try to import and run the UI
    try:
        # This would be your FastAPI app from the UI implementation
        click.echo("\n⚠️  UI not yet implemented")
        click.echo("Run the standalone UI server instead:")
        click.echo(f"  python simple_ui.py")
    except ImportError:
        click.echo("\n✗ UI dependencies not installed", err=True)
        click.echo("Install with: pip install fastapi uvicorn", err=True)
        sys.exit(1)


# ============================================================================
# Version
# ============================================================================

@cli.command()
def version():
    """Show Zaphod version"""
    click.echo("Zaphod CLI v1.0.0")
    click.echo("Course management system for Canvas LMS")


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == '__main__':
    cli()
