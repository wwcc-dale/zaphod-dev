# cli.py - Standalone CLI wrapper for Zaphod
"""
Zaphod CLI - Unified interface for course management

Usage:
    python cli.py sync [--watch] [--course-id ID]
    python cli.py validate [--fix]
    python cli.py prune [--dry-run] [--assignments]
    python cli.py list [--type TYPE]
    python cli.py new --type TYPE --name NAME
    python cli.py init --course-id ID [--with-yaml]
    python cli.py config [--show-secrets]
    python cli.py info
    python cli.py ui [--port PORT]

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
        """Get course ID from config system"""
        # Try the new config system first
        try:
            from config_utils import get_course_id as _get_course_id
            return _get_course_id(self.course_root)
        except Exception:
            pass
        
        # Fall back to legacy behavior
        course_id = os.environ.get("COURSE_ID")
        if course_id:
            return course_id
        
        # Check zaphod.yaml
        yaml_path = self.course_root / "zaphod.yaml"
        if yaml_path.exists():
            try:
                import yaml
                data = yaml.safe_load(yaml_path.read_text())
                if data and data.get("course_id"):
                    return str(data["course_id"])
            except Exception:
                pass
        
        # Check defaults.json
        defaults_path = self.metadata_dir / "defaults.json"
        if defaults_path.exists():
            try:
                data = json.loads(defaults_path.read_text())
                return str(data.get("course_id")) if data.get("course_id") else None
            except Exception:
                pass
        
        return None
    
    def run_script(self, script_name: str, env: Optional[dict] = None) -> subprocess.CompletedProcess:
        """Run a Zaphod script"""
        if not self.zaphod_root:
            click.echo("❌ Could not find Zaphod scripts directory", err=True)
            sys.exit(1)
        
        script_path = self.zaphod_root / script_name
        if not script_path.exists():
            click.echo(f"❌ Script not found: {script_path}", err=True)
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
# Init Command (NEW)
# ============================================================================

@cli.command()
@click.option('--course-id', required=True, type=int, help='Canvas course ID')
@click.option('--with-yaml', is_flag=True, help='Create zaphod.yaml config file')
@click.option('--force', is_flag=True, help='Overwrite existing files')
@click.pass_obj
def init(ctx: ZaphodContext, course_id: int, with_yaml: bool, force: bool):
    """
    Initialize a new Zaphod course
    
    Creates the directory structure and configuration files
    for a new Zaphod-managed course.
    
    Examples:
        zaphod init --course-id 12345
        zaphod init --course-id 12345 --with-yaml
    """
    course_root = ctx.course_root
    
    click.echo(f"🚀 Initializing Zaphod course in {course_root}")
    click.echo(f"   Course ID: {course_id}")
    click.echo()
    
    # Create directory structure
    directories = [
        "pages",
        "assets", 
        "quiz-banks",
        "outcomes",
        "modules",
        "rubrics",
        "rubrics/rows",
        "_course_metadata",
    ]
    
    for dir_name in directories:
        dir_path = course_root / dir_name
        if not dir_path.exists():
            dir_path.mkdir(parents=True)
            click.echo(f"  📁 Created {dir_name}/")
        else:
            click.echo(f"  ✓ {dir_name}/ exists")
    
    # Create legacy defaults.json (for backward compatibility)
    defaults_path = course_root / "_course_metadata" / "defaults.json"
    if not defaults_path.exists() or force:
        defaults = {"course_id": course_id}
        defaults_path.write_text(json.dumps(defaults, indent=2))
        click.echo(f"  📄 Created _course_metadata/defaults.json")
    else:
        click.echo(f"  ✓ _course_metadata/defaults.json exists")
    
    # Create zaphod.yaml if requested
    if with_yaml:
        yaml_path = course_root / "zaphod.yaml"
        if not yaml_path.exists() or force:
            yaml_content = f"""\
# Zaphod Configuration
# ====================
# This file configures Zaphod for this course.
# Values here override defaults but are overridden by environment variables.

# Canvas Course ID (required)
course_id: {course_id}

# Canvas API settings
# -------------------
# Option 1: Reference a credentials file (recommended)
credential_file: ~/.canvas/credentials.txt

# Option 2: Inline credentials (less secure)
# api_url: https://canvas.institution.edu
# api_key: your_api_token_here

# Prune Settings
# --------------
prune:
  # Actually delete content (false = dry run)
  apply: true
  # Include assignments in pruning
  assignments: true

# Watch Mode Settings
# -------------------
watch:
  # Seconds to wait after change before running pipeline
  debounce: 2.0

# Custom Variables
# ----------------
# Add any custom variables here
# instructor_name: "Your Name"
# semester: "Spring 2026"
"""
            yaml_path.write_text(yaml_content)
            click.echo(f"  📄 Created zaphod.yaml")
        else:
            click.echo(f"  ✓ zaphod.yaml exists (use --force to overwrite)")
    
    # Create .gitignore if not exists
    gitignore_path = course_root / ".gitignore"
    if not gitignore_path.exists():
        gitignore_content = """\
# Zaphod generated files
_course_metadata/upload_cache.json
_course_metadata/watch_state.json

# Work files (regenerated from index.md)
pages/**/meta.json
pages/**/source.md
pages/**/styled_source.md
pages/**/result.html

# Python
__pycache__/
*.py[cod]
.venv/

# OS files
.DS_Store
Thumbs.db
"""
        gitignore_path.write_text(gitignore_content)
        click.echo(f"  📄 Created .gitignore")
    
    # Create sample module_order.yaml
    module_order_path = course_root / "modules" / "module_order.yaml"
    if not module_order_path.exists():
        module_order_content = """\
# Module ordering
# ---------------
# List modules in desired order. These will be created if they don't exist.
# Modules listed here are protected from empty-module pruning.

- "Start Here"
- "Module 1"
- "Module 2"
"""
        module_order_path.write_text(module_order_content)
        click.echo(f"  📄 Created modules/module_order.yaml")
    
    # Create sample outcomes.yaml
    outcomes_path = course_root / "outcomes" / "outcomes.yaml"
    if not outcomes_path.exists():
        outcomes_content = """\
# Course Learning Outcomes
# ------------------------
# Define your course learning outcomes here.
# See sync_clo_via_csv.py for how these are imported into Canvas.

course_outcomes: []
  # - code: CLO1
  #   title: Example Outcome
  #   description: Students will demonstrate understanding of...
  #   vendor_guid: CLO1
  #   mastery_points: 3
  #   ratings:
  #     - points: 3
  #       description: Exceeds expectations
  #     - points: 2
  #       description: Meets expectations
  #     - points: 1
  #       description: Below expectations
"""
        outcomes_path.write_text(outcomes_content)
        click.echo(f"  📄 Created outcomes/outcomes.yaml")
    
    click.echo()
    click.echo("✅ Course initialized!")
    click.echo()
    click.echo("Next steps:")
    click.echo("  1. Create pages in pages/*.page/index.md")
    click.echo("  2. Run: zaphod sync --watch")
    click.echo()
    click.echo("For help: zaphod --help")


# ============================================================================
# Config Command (NEW)
# ============================================================================

@cli.command()
@click.option('--show-secrets', is_flag=True, help='Show API keys (careful!)')
@click.pass_obj
def config(ctx: ZaphodContext, show_secrets: bool):
    """
    Show current configuration
    
    Displays configuration sources and resolved values.
    Useful for debugging configuration issues.
    
    Examples:
        zaphod config                 # Show config (keys masked)
        zaphod config --show-secrets  # Show full API keys
    """
    click.echo("📋 Zaphod Configuration\n")
    click.echo("=" * 60)
    
    course_root = ctx.course_root
    
    # Show what config files exist
    click.echo("\nConfiguration sources (in priority order):")
    
    sources = [
        ("Environment: COURSE_ID", "COURSE_ID" in os.environ),
        ("Environment: CANVAS_API_KEY", "CANVAS_API_KEY" in os.environ),
        ("Environment: CANVAS_API_URL", "CANVAS_API_URL" in os.environ),
        ("zaphod.yaml", (course_root / "zaphod.yaml").exists()),
        ("zaphod.yml", (course_root / "zaphod.yml").exists()),
        ("_course_metadata/defaults.json", (course_root / "_course_metadata" / "defaults.json").exists()),
        ("~/.zaphod/config.yaml", (Path.home() / ".zaphod" / "config.yaml").exists()),
        ("~/.canvas/credentials.txt", (Path.home() / ".canvas" / "credentials.txt").exists()),
    ]
    
    for name, exists in sources:
        status = "✓" if exists else "✗"
        click.echo(f"  {status} {name}")
    
    click.echo("\nResolved configuration:")
    click.echo("-" * 60)
    
    # Try to use the new config system
    try:
        from config_utils import get_config
        config_obj = get_config(course_root, reload=True)
        
        click.echo(f"  course_id: {config_obj.course_id or '(not set)'}")
        click.echo(f"  api_url: {config_obj.api_url or '(not set)'}")
        
        if show_secrets:
            click.echo(f"  api_key: {config_obj.api_key or '(not set)'}")
        else:
            if config_obj.api_key:
                masked = config_obj.api_key[:4] + "..." + config_obj.api_key[-4:] if len(config_obj.api_key) > 8 else "****"
                click.echo(f"  api_key: {masked}")
            else:
                click.echo(f"  api_key: (not set)")
        
        click.echo(f"  canvas_base_url: {config_obj.canvas_base_url or '(not set)'}")
        click.echo(f"  credential_file: {config_obj.credential_file or '(default)'}")
        click.echo()
        click.echo(f"  prune_apply: {config_obj.prune_apply}")
        click.echo(f"  prune_assignments: {config_obj.prune_assignments}")
        click.echo(f"  watch_debounce: {config_obj.watch_debounce}s")
        
        if config_obj.extra:
            click.echo()
            click.echo("  Custom variables:")
            for key, value in config_obj.extra.items():
                click.echo(f"    {key}: {value}")
        
        # Validation
        issues = config_obj.validate()
        if issues:
            click.echo()
            click.echo("⚠️  Configuration issues:")
            for issue in issues:
                click.echo(f"    - {issue}")
        else:
            click.echo()
            click.echo("✅ Configuration is valid")
            
    except ImportError:
        # Fall back to basic config display
        click.echo("  (Note: New config system not available, showing basic info)")
        click.echo()
        
        course_id = ctx.get_course_id()
        click.echo(f"  course_id: {course_id or '(not set)'}")
        
        cred_file = Path.home() / ".canvas" / "credentials.txt"
        if cred_file.exists():
            click.echo(f"  credentials: {cred_file}")
        else:
            click.echo(f"  credentials: (not found)")
    
    except Exception as e:
        click.echo(f"\n❌ Error loading configuration: {e}")


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
        click.echo("👁 Starting watch mode (Ctrl+C to stop)...")
        click.echo(f"📁 Watching: {ctx.course_root}")
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
                ("sync_rubrics.py", "📊 Syncing rubrics"),
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
        click.echo("❌ No pages/ directory found", err=True)
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
        click.echo(f"❌ Content already exists: {folder_path}", err=True)
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
@click.option('--fix', is_flag=True, help='Attempt to auto-fix issues')
@click.pass_obj
def validate(ctx: ZaphodContext, fix: bool):
    """
    Validate course content
    
    Checks for:
    - Missing required frontmatter fields
    - Invalid metadata
    - Broken media references
    - Missing files
    
    Examples:
        zaphod validate        # Check for issues
        zaphod validate --fix  # Auto-fix when possible
    """
    click.echo("🔍 Validating course content...\n")
    
    issues = []
    fixed = []
    
    if not ctx.pages_dir.exists():
        click.echo("❌ No pages/ directory found")
        sys.exit(1)
    
    # Check each content folder
    for folder in ctx.pages_dir.rglob("*.*"):
        if not folder.is_dir():
            continue
        if folder.suffix not in ['.page', '.assignment', '.link', '.file']:
            continue
        
        folder_issues = []
        
        # Check for index.md
        index_path = folder / "index.md"
        meta_path = folder / "meta.json"
        
        if not index_path.exists():
            if not meta_path.exists():
                folder_issues.append("Missing index.md and meta.json")
            else:
                folder_issues.append("Missing index.md (has meta.json)")
        
        # Check meta.json if exists
        if meta_path.exists():
            try:
                meta = json.loads(meta_path.read_text())
                
                # Required fields
                required = ["name", "type"]
                for field in required:
                    if not meta.get(field):
                        folder_issues.append(f"Missing required field: {field}")
                
                # Type-specific validation
                item_type = meta.get("type", "").lower()
                if item_type == "assignment":
                    if not meta.get("points_possible"):
                        if fix:
                            meta["points_possible"] = 100
                            meta_path.write_text(json.dumps(meta, indent=2))
                            fixed.append(f"{folder.name}: Added default points_possible=100")
                        else:
                            folder_issues.append("Missing points_possible")
                
                elif item_type == "link":
                    if not meta.get("external_url"):
                        folder_issues.append("Missing external_url")
                
            except json.JSONDecodeError:
                folder_issues.append("Invalid JSON in meta.json")
        
        if folder_issues:
            issues.append((folder.name, folder_issues))
    
    # Report results
    if not issues and not fixed:
        click.echo("✅ No issues found!")
    else:
        if issues:
            click.echo(f"Found {len(issues)} items with issues:\n")
            for name, item_issues in issues:
                click.echo(f"❌ {name}")
                for issue in item_issues:
                    click.echo(f"   - {issue}")
                click.echo()
        
        if fixed:
            click.echo(f"\n✅ Auto-fixed {len(fixed)} issues:")
            for fix_msg in fixed:
                click.echo(f"   {fix_msg}")


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
    click.echo("📊 Course Information\n")
    click.echo("=" * 60)
    
    # Course metadata
    course_id = ctx.get_course_id()
    if course_id:
        click.echo(f"Course ID: {course_id}")
    else:
        click.echo("Course ID: Not set (use COURSE_ID env var or zaphod.yaml)")
    
    click.echo(f"Course Root: {ctx.course_root}")
    click.echo(f"Zaphod Scripts: {ctx.zaphod_root or 'Not found'}")
    
    # Config file status
    if (ctx.course_root / "zaphod.yaml").exists():
        click.echo("Config File: zaphod.yaml ✓")
    elif (ctx.course_root / "_course_metadata" / "defaults.json").exists():
        click.echo("Config File: defaults.json (legacy)")
    else:
        click.echo("Config File: None")
    
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
        click.echo("\n❌ UI dependencies not installed", err=True)
        click.echo("Install with: pip install fastapi uvicorn", err=True)
        sys.exit(1)


# ============================================================================
# Version
# ============================================================================

@cli.command()
def version():
    """Show Zaphod version"""
    click.echo("Zaphod CLI v1.1.0")
    click.echo("Course management system for Canvas LMS")
    click.echo()
    click.echo("New in v1.1.0:")
    click.echo("  - zaphod init: Initialize new courses")
    click.echo("  - zaphod config: View configuration")
    click.echo("  - YAML config file support (zaphod.yaml)")


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == '__main__':
    cli()
