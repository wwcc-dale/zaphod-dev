# cli.py - Standalone CLI wrapper for Zaphod
"""
Zaphod CLI - Unified interface for course management

Usage:
    zaphod sync [--watch] [--dry-run] [--course-id ID]
    zaphod validate [--fix]
    zaphod prune [--dry-run] [--assignments]
    zaphod list [--type TYPE]
    zaphod new --type TYPE --name NAME
    zaphod info
    zaphod config [--show-sources]
    zaphod init --course-id ID [--with-yaml]

This CLI wraps existing Zaphod scripts without modifying them.
"""

import click
import subprocess
import sys
import os
import json
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
        """Get course ID from env, zaphod.yaml, or defaults.json"""
        # Check environment first
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
        
        # Fall back to defaults.json
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
# Sync Commands
# ============================================================================

@cli.command()
@click.option('--watch', is_flag=True, help='Watch for changes and auto-sync')
@click.option('--dry-run', is_flag=True, help='Show what would happen without making changes')
@click.option('--course-id', type=int, help='Override course ID')
@click.option('--assets-only', is_flag=True, help='Only upload assets, skip content')
@click.pass_obj
def sync(ctx: ZaphodContext, watch: bool, dry_run: bool, course_id: Optional[int], assets_only: bool):
    """
    Sync local content to Canvas
    
    Examples:
        zaphod sync                    # Sync once
        zaphod sync --dry-run          # Preview what would happen
        zaphod sync --watch            # Watch and auto-sync
        zaphod sync --course-id 12345  # Override course ID
        zaphod sync --assets-only      # Only upload media files
    """
    if watch and dry_run:
        click.echo("❌ Cannot use --watch and --dry-run together", err=True)
        sys.exit(1)
    
    if dry_run:
        _run_dry_run(ctx, course_id)
        return
    
    if watch:
        click.echo("🔄 Starting watch mode (Ctrl+C to stop)...")
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


def _run_dry_run(ctx: ZaphodContext, course_id: Optional[int]):
    """
    Run a dry-run sync that shows what would happen without making changes.
    """
    click.echo("🔍 DRY RUN - No changes will be made to Canvas\n")
    click.echo("=" * 60)
    
    # Get course ID
    cid = str(course_id) if course_id else ctx.get_course_id()
    if not cid:
        click.echo("❌ No course ID found. Set COURSE_ID or use --course-id", err=True)
        sys.exit(1)
    
    click.echo(f"📋 Course ID: {cid}")
    click.echo(f"📁 Course Root: {ctx.course_root}")
    click.echo("=" * 60)
    
    # Step 1: Process frontmatter (this is local-only, safe to run)
    click.echo("\n📝 Processing frontmatter...")
    env = {"COURSE_ID": cid}
    result = ctx.run_script("frontmatter_to_meta.py", env=env)
    if result.returncode != 0:
        click.echo("⚠️  Frontmatter processing had warnings/errors")
    
    # Step 2: Analyze what would be published
    click.echo("\n" + "=" * 60)
    click.echo("📤 CONTENT THAT WOULD BE PUBLISHED:")
    click.echo("=" * 60)
    
    pages_dir = ctx.pages_dir
    if not pages_dir.exists():
        click.echo("❌ No pages/ directory found")
        return
    
    # Collect content by type
    content = {
        "pages": [],
        "assignments": [],
        "links": [],
        "files": [],
    }
    
    for ext, content_type in [(".page", "pages"), (".assignment", "assignments"), 
                               (".link", "links"), (".file", "files")]:
        for folder in pages_dir.rglob(f"*{ext}"):
            meta_path = folder / "meta.json"
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text())
                    content[content_type].append({
                        "name": meta.get("name", folder.name),
                        "folder": folder.name,
                        "published": meta.get("published", False),
                        "modules": meta.get("modules", []),
                    })
                except Exception as e:
                    click.echo(f"  ⚠️  Could not read {folder.name}: {e}")
    
    # Display content summary
    for content_type, items in content.items():
        if items:
            click.echo(f"\n{content_type.upper()} ({len(items)}):")
            for item in sorted(items, key=lambda x: x["name"]):
                status = "✓" if item["published"] else "○"
                modules = ", ".join(item["modules"]) if item["modules"] else "No modules"
                click.echo(f"  {status} {item['name']}")
                click.echo(f"      └─ {modules}")
    
    # Step 3: Analyze modules
    click.echo("\n" + "=" * 60)
    click.echo("📚 MODULES THAT WOULD BE CREATED/UPDATED:")
    click.echo("=" * 60)
    
    all_modules = set()
    for content_type, items in content.items():
        for item in items:
            all_modules.update(item["modules"])
    
    # Check module_order.yaml
    module_order_path = ctx.course_root / "modules" / "module_order.yaml"
    ordered_modules = []
    if module_order_path.exists():
        try:
            import yaml
            data = yaml.safe_load(module_order_path.read_text())
            if isinstance(data, dict):
                ordered_modules = data.get("modules", [])
            elif isinstance(data, list):
                ordered_modules = data
        except Exception:
            pass
    
    if ordered_modules:
        click.echo("\nFrom module_order.yaml:")
        for m in ordered_modules:
            in_content = "✓" if m in all_modules else "○"
            click.echo(f"  {in_content} {m}")
    
    extra_modules = all_modules - set(ordered_modules)
    if extra_modules:
        click.echo("\nFrom content (not in module_order.yaml):")
        for m in sorted(extra_modules):
            click.echo(f"  + {m}")
    
    # Step 4: Check for outcomes
    click.echo("\n" + "=" * 60)
    click.echo("🎯 OUTCOMES:")
    click.echo("=" * 60)
    
    outcomes_path = ctx.course_root / "outcomes" / "outcomes.yaml"
    outcomes = []
    if outcomes_path.exists():
        try:
            import yaml
            data = yaml.safe_load(outcomes_path.read_text())
            outcomes = data.get("course_outcomes", [])
            click.echo(f"\n{len(outcomes)} outcome(s) would be synced:")
            for o in outcomes:
                click.echo(f"  • {o.get('code', '?')}: {o.get('title', 'Untitled')}")
        except Exception as e:
            click.echo(f"  ⚠️  Could not read outcomes: {e}")
    else:
        click.echo("\n  No outcomes/outcomes.yaml found")
    
    # Step 5: Check for quizzes
    click.echo("\n" + "=" * 60)
    click.echo("❓ QUIZZES:")
    click.echo("=" * 60)
    
    quiz_dir = ctx.course_root / "quiz-banks"
    quiz_files = []
    if quiz_dir.exists():
        quiz_files = list(quiz_dir.glob("*.quiz.txt"))
        if quiz_files:
            click.echo(f"\n{len(quiz_files)} quiz file(s) would be synced:")
            for qf in sorted(quiz_files):
                click.echo(f"  • {qf.stem}")
        else:
            click.echo("\n  No .quiz.txt files found")
    else:
        click.echo("\n  No quiz-banks/ directory found")
    
    # Step 6: Check for rubrics
    click.echo("\n" + "=" * 60)
    click.echo("📊 RUBRICS:")
    click.echo("=" * 60)
    
    rubric_count = 0
    for folder in pages_dir.rglob("*.assignment"):
        for rubric_name in ["rubric.yaml", "rubric.yml", "rubric.json"]:
            if (folder / rubric_name).exists():
                rubric_count += 1
                click.echo(f"  • {folder.name}/{rubric_name}")
                break
    
    if rubric_count == 0:
        click.echo("\n  No rubrics found in assignments")
    
    # Summary
    click.echo("\n" + "=" * 60)
    click.echo("📋 SUMMARY:")
    click.echo("=" * 60)
    total_content = sum(len(items) for items in content.values())
    click.echo(f"""
  Content items:  {total_content}
  Modules:        {len(all_modules)}
  Outcomes:       {len(outcomes)}
  Quizzes:        {len(quiz_files)}
  Rubrics:        {rubric_count}
""")
    click.echo("Run 'zaphod sync' to apply these changes to Canvas.")


# ============================================================================
# Content Management
# ============================================================================

@cli.command('list')
@click.option('--type', 'content_type', type=click.Choice(['page', 'assignment', 'link', 'file', 'all']), 
              default='all', help='Filter by content type')
@click.option('--module', help='Filter by module name')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
@click.pass_obj
def list_content(ctx: ZaphodContext, content_type: str, module: Optional[str], as_json: bool):
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
                content_type = meta.get("type", "").lower()
                if content_type == "assignment":
                    if not meta.get("points_possible"):
                        if fix:
                            meta["points_possible"] = 100
                            meta_path.write_text(json.dumps(meta, indent=2))
                            fixed.append(f"{folder.name}: Added default points_possible=100")
                        else:
                            folder_issues.append("Missing points_possible")
                
                elif content_type == "link":
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
# Info & Config
# ============================================================================

@cli.command()
@click.pass_obj
def info(ctx: ZaphodContext):
    """
    Show course information and status
    """
    click.echo("📊 Course Information\n")
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


@cli.command()
@click.option('--show-sources', is_flag=True, help='Show where each setting comes from')
@click.pass_obj
def config(ctx: ZaphodContext, show_sources: bool):
    """
    Display current configuration
    
    Shows resolved configuration from all sources:
    - Environment variables
    - zaphod.yaml
    - _course_metadata/defaults.json
    - ~/.zaphod/config.yaml
    """
    click.echo("⚙️  Zaphod Configuration\n")
    click.echo("=" * 60)
    
    try:
        from config_utils import get_config
        cfg = get_config(ctx.course_root)
        
        click.echo(f"Course ID:      {cfg.course_id or 'Not set'}")
        click.echo(f"Course Name:    {cfg.course_name or 'Not set'}")
        click.echo(f"API URL:        {cfg.api_url or 'Not set'}")
        click.echo(f"API Key:        {'***' + cfg.api_key[-4:] if cfg.api_key else 'Not set'}")
        click.echo(f"Credential File: {cfg.credential_file or 'Default'}")
        click.echo()
        click.echo(f"Prune Apply:    {cfg.prune_apply}")
        click.echo(f"Prune Assign:   {cfg.prune_assignments}")
        click.echo(f"Watch Debounce: {cfg.watch_debounce}s")
        
        if cfg.replacements or cfg.style or cfg.markdown_extensions:
            click.echo()
            click.echo("Markdown2Canvas:")
            if cfg.replacements:
                click.echo(f"  Replacements: {cfg.replacements}")
            if cfg.style:
                click.echo(f"  Style:        {cfg.style}")
            if cfg.markdown_extensions:
                click.echo(f"  Extensions:   {', '.join(cfg.markdown_extensions)}")
        
        if show_sources and cfg._sources:
            click.echo()
            click.echo("Sources:")
            for key, source in sorted(cfg._sources.items()):
                click.echo(f"  {key}: {source}")
                
    except ImportError:
        click.echo("❌ config_utils not available")
        click.echo("\nFallback info:")
        click.echo(f"  Course ID: {ctx.get_course_id() or 'Not set'}")


@cli.command()
@click.option('--course-id', required=True, type=int, help='Canvas course ID')
@click.option('--with-yaml', is_flag=True, help='Create zaphod.yaml instead of defaults.json')
@click.pass_obj
def init(ctx: ZaphodContext, course_id: int, with_yaml: bool):
    """
    Initialize a new Zaphod course
    
    Creates the standard directory structure and configuration files.
    
    Examples:
        zaphod init --course-id 12345
        zaphod init --course-id 12345 --with-yaml
    """
    click.echo(f"🚀 Initializing Zaphod course in {ctx.course_root}\n")
    
    # Create directories
    dirs = ["pages", "assets", "quiz-banks", "outcomes", "modules", "rubrics", "_course_metadata"]
    for d in dirs:
        path = ctx.course_root / d
        path.mkdir(parents=True, exist_ok=True)
        click.echo(f"  📁 {d}/")
    
    # Create config file
    if with_yaml:
        config_path = ctx.course_root / "zaphod.yaml"
        config_content = f"""# Zaphod Configuration
course_id: {course_id}
credential_file: ~/.canvas/credentials.txt

prune:
  apply: true
  assignments: true

watch:
  debounce: 2.0
"""
        config_path.write_text(config_content)
        click.echo(f"  📄 zaphod.yaml")
    else:
        config_path = ctx.course_root / "_course_metadata" / "defaults.json"
        config_content = json.dumps({"course_id": str(course_id)}, indent=2)
        config_path.write_text(config_content)
        click.echo(f"  📄 _course_metadata/defaults.json")
    
    # Create .gitignore
    gitignore_path = ctx.course_root / ".gitignore"
    if not gitignore_path.exists():
        gitignore_content = """# Zaphod
_course_metadata/upload_cache.json
_course_metadata/watch_state.json
*.pyc
__pycache__/
.venv/
"""
        gitignore_path.write_text(gitignore_content)
        click.echo(f"  📄 .gitignore")
    
    # Create module_order.yaml
    module_order_path = ctx.course_root / "modules" / "module_order.yaml"
    if not module_order_path.exists():
        module_order_path.write_text("modules:\n  - \"Module 1\"\n")
        click.echo(f"  📄 modules/module_order.yaml")
    
    # Create outcomes.yaml
    outcomes_path = ctx.course_root / "outcomes" / "outcomes.yaml"
    if not outcomes_path.exists():
        outcomes_path.write_text("course_outcomes: []\n")
        click.echo(f"  📄 outcomes/outcomes.yaml")
    
    click.echo(f"\n✅ Course initialized!")
    click.echo(f"\nNext steps:")
    click.echo(f"  1. Create content in pages/")
    click.echo(f"  2. Run 'zaphod sync --dry-run' to preview")
    click.echo(f"  3. Run 'zaphod sync' to publish to Canvas")


# ============================================================================
# Version
# ============================================================================

@cli.command()
def version():
    """Show Zaphod version"""
    click.echo("Zaphod CLI v1.2.0")
    click.echo("Course management system for Canvas LMS")


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == '__main__':
    cli()
