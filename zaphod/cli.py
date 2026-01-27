# cli.py - Standalone CLI wrapper for Zaphod
"""
Zaphod CLI - Unified interface for course management

COMMANDS:
    Course Setup:
        zaphod init [--course-id ID]              Initialize new course structure
        zaphod info                               Show course information and status
        zaphod validate [--verbose]               Validate course content

    Content Management:
        zaphod list [--type TYPE] [--module M]    List course content
        zaphod new --type TYPE --name NAME        Create new content item

    Syncing:
        zaphod sync [--watch] [--dry-run]         Sync local content to Canvas
        zaphod prune [--dry-run] [--assignments]  Remove orphaned Canvas content

    Media Management:
        zaphod manifest                           Build media manifest for large files
        zaphod hydrate --source PATH              Download missing media files

    Export:
        zaphod export [--output FILE]             Export course to Common Cartridge

    Other:
        zaphod version                            Show version information
        zaphod ui [--port PORT]                   Launch web UI (experimental)

EXAMPLES:
    # Initialize a new course
    zaphod init --course-id 12345

    # Sync with auto-watch mode
    zaphod sync --watch

    # Preview what sync would do
    zaphod sync --dry-run

    # List all quizzes
    zaphod list --type quiz

    # Create a new assignment
    zaphod new --type assignment --name "Essay 1" --module "Week 2"

    # Validate before syncing
    zaphod validate

    # Export for another LMS
    zaphod export --output my-course.imscc

For more information, see the user guide in docs/user-guide/
"""

import click
import subprocess
import sys
import os
import json
import re
import webbrowser
from pathlib import Path
from typing import Optional, List
from datetime import datetime
import time


# ============================================================================
# Security Utilities
# ============================================================================

def _sanitize_filename(name: str) -> str:
    r"""
    Create a safe filename from user input.
    
    SECURITY: Prevents path traversal and shell injection by:
    - Rejecting path traversal attempts (.., /, \)
    - Rejecting shell metacharacters (; | & $ ` etc.)
    - Limiting to alphanumeric, spaces, hyphens, underscores
    """
    if not name:
        raise click.ClickException("Name cannot be empty")
    
    # SECURITY: Check for dangerous patterns BEFORE sanitization
    # Path traversal attempts
    if '..' in name:
        raise click.ClickException(f"Invalid name: path traversal not allowed (contains '..')")
    
    if name.startswith('/') or name.startswith('\\'):
        raise click.ClickException(f"Invalid name: absolute paths not allowed")
    
    # Shell injection attempts
    shell_chars = [';', '|', '&', '$', '`', '(', ')', '{', '}', '<', '>', '!', '\n', '\r']
    for char in shell_chars:
        if char in name:
            raise click.ClickException(f"Invalid name: shell metacharacter '{char}' not allowed")
    
    # Now sanitize for filesystem safety (remove remaining special chars)
    safe = re.sub(r'[^\w\s-]', '', name)
    safe = re.sub(r'[-\s]+', '-', safe)
    safe = safe.strip('-').lower()
    
    if not safe:
        raise click.ClickException(f"Name '{name}' results in empty filename after sanitization")
    
    # Final safety check on the result
    if '..' in safe or safe.startswith('/') or safe.startswith('\\'):
        raise click.ClickException(f"Invalid name after sanitization: {safe}")
    
    return safe


# ============================================================================
# Configuration & Utilities
# ============================================================================

class ZaphodContext:
    """Shared context for CLI commands"""
    
    def __init__(self):
        self.course_root = Path.cwd()
        # Support both content/ (preferred) and pages/ (legacy)
        content_dir = self.course_root / "content"
        pages_dir = self.course_root / "pages"
        self.content_dir = content_dir if content_dir.exists() else pages_dir
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
        # 1. Check environment variable
        course_id = os.environ.get("COURSE_ID")
        if course_id:
            return course_id
        
        # 2. Check zaphod.yaml
        yaml_path = self.course_root / "zaphod.yaml"
        if yaml_path.exists():
            try:
                import yaml
                data = yaml.safe_load(yaml_path.read_text())
                if data and data.get("course_id"):
                    return str(data["course_id"])
            except ImportError:
                pass  # PyYAML not installed
            except Exception:
                pass
        
        # 3. Check defaults.json (legacy)
        defaults_path = self.metadata_dir / "defaults.json"
        if defaults_path.exists():
            try:
                data = json.loads(defaults_path.read_text())
                return data.get("course_id")
            except Exception:
                pass
        
        return None
    
    def run_script(self, script_name: str, args: Optional[list] = None, env: Optional[dict] = None) -> subprocess.CompletedProcess:
        """Run a Zaphod script with optional arguments"""
        if not self.zaphod_root:
            click.echo("[x] Could not find Zaphod scripts directory", err=True)
            sys.exit(1)
        
        script_path = self.zaphod_root / script_name
        if not script_path.exists():
            click.echo(f"[x] Script not found: {script_path}", err=True)
            sys.exit(1)
        
        full_env = os.environ.copy()
        if env:
            full_env.update(env)
        
        # Ensure credentials are set
        if "CANVAS_CREDENTIAL_FILE" not in full_env:
            full_env["CANVAS_CREDENTIAL_FILE"] = str(Path.home() / ".canvas" / "credentials.txt")
        
        cmd = [self.python_exe, str(script_path)]
        if args:
            cmd.extend(args)
        
        return subprocess.run(
            cmd,
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
@click.option('--no-prune', is_flag=True, help='Skip cleanup/prune step')
@click.option('--dry-run', '-n', is_flag=True, help='Preview changes without making them')
@click.pass_obj
def sync(ctx: ZaphodContext, watch: bool, course_id: Optional[int], assets_only: bool, no_prune: bool, dry_run: bool):
    """
    Sync local content to Canvas
    
    The sync pipeline runs these steps in order:
    1. frontmatter_to_meta - Process index.md files
    2. publish_all - Upload pages, assignments, assets
    3. sync_banks - Import question banks
    4. sync_quizzes - Create/update quizzes
    5. sync_modules - Organize content into modules
    6. sync_clo - Sync learning outcomes
    7. sync_rubrics - Sync rubrics to assignments
    8. prune - Clean up orphaned content (unless --no-prune)
    
    Examples:
        zaphod sync                    # Sync once
        zaphod sync --watch            # Watch and auto-sync
        zaphod sync --course-id 12345  # Override course ID
        zaphod sync --assets-only      # Only upload media files
        zaphod sync --no-prune         # Skip cleanup step
        zaphod sync --dry-run          # Preview what would happen
    """
    if dry_run and watch:
        click.echo("[!] --dry-run and --watch cannot be used together", err=True)
        sys.exit(1)
    
    if watch:
        click.echo("[*] Starting watch mode (Ctrl+C to stop)...")
        click.echo(f"[*] Watching: {ctx.course_root}")
        click.echo()
        
        env = {}
        if course_id:
            env["COURSE_ID"] = str(course_id)
        
        try:
            ctx.run_script("watch_and_publish.py", env=env)
        except KeyboardInterrupt:
            click.echo("\n\n[wave] Stopping watch mode...")
    else:
        if dry_run:
            click.echo("[*] Running sync pipeline (DRY RUN - no changes will be made)...")
        else:
            click.echo("[*] Running sync pipeline...")
        
        env = {}
        if course_id:
            env["COURSE_ID"] = str(course_id)
        
        # Build script commands with --dry-run where supported
        dry_flag = " --dry-run" if dry_run else ""
        
        # Run the pipeline steps manually
        steps = [
            ("frontmatter_to_meta.py", "[*] Processing frontmatter"),
        ]
        
        if assets_only:
            steps.append(("publish_all.py --assets-only", "[pkg] Uploading assets"))
        else:
            steps.extend([
                (f"publish_all.py{dry_flag}", "[up] Publishing content"),
                (f"sync_banks.py{dry_flag}", "[bank] Importing question banks"),  # Banks before quizzes
                (f"sync_quizzes.py{dry_flag}", "[quiz] Syncing quiz folders"),    # Quizzes before modules
            ])
            
            # These steps require content to exist in Canvas, skip in dry-run
            if dry_run:
                steps.append(("SKIP", "[books] Syncing modules (skipped - requires content to exist)"))
                steps.append(("SKIP", "[target] Syncing outcomes (skipped - requires content to exist)"))
                steps.append(("SKIP", "[list] Syncing rubrics (skipped - requires content to exist)"))
            else:
                steps.extend([
                    ("sync_modules.py", "[books] Syncing modules"),
                    ("sync_clo_via_csv.py", "[target] Syncing outcomes"),
                    ("sync_rubrics.py", "[list] Syncing rubrics"),
                ])
            
            # Add prune step unless --no-prune
            # Note: prune uses --apply for real runs, default is dry-run
            if not no_prune:
                if dry_run:
                    steps.append(("prune_canvas_content.py", "[sweep] Cleaning up orphaned content (preview)"))
                else:
                    steps.append(("prune_canvas_content.py --apply", "[sweep] Cleaning up orphaned content"))
        
        for script, description in steps:
            click.echo(f"\n{description}...")
            if script == "SKIP":
                continue  # Just printed the skip message
            parts = script.split()
            script_name = parts[0]
            script_args = parts[1:] if len(parts) > 1 else None
            result = ctx.run_script(script_name, args=script_args, env=env)
            if result.returncode != 0:
                click.echo(f"[!]  {script} completed with warnings/errors")
        
        if dry_run:
            click.echo("\n[v] Dry run complete! No changes were made.")
        else:
            click.echo("\n[v] Sync complete!")


# ============================================================================
# Content Management
# ============================================================================

@cli.command('list')  # Keep CLI name as 'list' but Python function is 'list_content'
@click.option('--type', 'content_type', type=click.Choice(['page', 'assignment', 'link', 'file', 'quiz', 'all']), 
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
        zaphod list --type quiz          # Only quizzes
        zaphod list --module "Week 1"    # Content in specific module
        zaphod list --json               # JSON output
    """
    if not ctx.content_dir.exists():
        click.echo(f"[x] No content directory found (content/ or pages/)", err=True)
        sys.exit(1)
    
    items = []
    extensions = ['.page', '.assignment', '.link', '.file', '.quiz'] if content_type == 'all' else [f'.{content_type}']
    
    for ext in extensions:
        for folder in ctx.content_dir.rglob(f"*{ext}"):
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
                click.echo(f"[!]  Could not read {folder.name}: {e}", err=True)
    
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
                status = "[v]" if item["published"] else "[ ]"
                modules_str = ", ".join(item["modules"]) if item["modules"] else "No modules"
                click.echo(f"  {status} {item['name']}")
                click.echo(f"     {modules_str}")


@cli.command()
@click.option('--type', 'content_type', type=click.Choice(['page', 'assignment', 'link', 'quiz']), 
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
        zaphod new --type quiz --name "Midterm" --module "Week 5"
    """
    # SECURITY: Sanitize folder name to prevent path traversal
    safe_name = _sanitize_filename(name)
    folder_name = f"{safe_name}.{content_type}"
    folder_path = ctx.content_dir / folder_name
    
    # SECURITY: Verify path is within content directory
    try:
        folder_path.resolve().relative_to(ctx.content_dir.resolve())
    except ValueError:
        click.echo(f"Error: Invalid name (path traversal detected): {name}", err=True)
        sys.exit(1)
    
    if folder_path.exists():
        click.echo(f"Content already exists: {folder_path}", err=True)
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
    elif content_type == "quiz":
        frontmatter.extend([
            "",
            "# quiz settings",
            "quiz_type: assignment  # or graded_survey, practice_quiz, survey",
            "time_limit: 30  # minutes, or null for unlimited",
            "allowed_attempts: 1  # -1 for unlimited",
            "shuffle_answers: true",
            "show_correct_answers: true",
            "",
            "# Optional: pull questions from banks",
            "# question_groups:",
            "#   - bank_id: 12345",
            "#     pick: 5",
            "#     points_per_question: 2",
        ])
    
    frontmatter.append("---")
    frontmatter.append("")
    frontmatter.append(f"# {name}")
    frontmatter.append("")
    
    if content_type == "quiz":
        frontmatter.extend([
            "Quiz description here...",
            "",
            "## 1. Sample Question",
            "",
            "What is 2 + 2?",
            "",
            "a. 3",
            "b. 4 *",
            "c. 5",
            "d. 6",
            "",
        ])
    else:
        frontmatter.append("Add your content here...")
        frontmatter.append("")
    
    index_path = folder_path / "index.md"
    index_path.write_text("\n".join(frontmatter))
    
    click.echo(f"[v] Created: {folder_path}")
    click.echo(f"[*] Edit: {index_path}")


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
    click.echo(f"[*] Validating course: {ctx.course_root}\n")
    
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
    args = []
    
    if not dry_run:
        args.append("--apply")
    
    if assignments:
        args.append("--prune-assignments")
    
    if dry_run:
        click.echo("[*] Dry run - showing what would be deleted...\n")
    else:
        click.confirm("[!] This will delete content from Canvas. Continue?", abort=True)
        click.echo("\n[*] Pruning orphaned content...\n")
    
    ctx.run_script("prune_canvas_content.py", args=args if args else None)
    
    if not dry_run:
        click.echo("\n[v] Prune complete!")


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
    click.echo("[list] Course Information\n")
    click.echo("=" * 60)
    
    # Course metadata
    course_id = ctx.get_course_id()
    if course_id:
        click.echo(f"Course ID: {course_id}")
    else:
        click.echo("Course ID: Not set (add to zaphod.yaml or set COURSE_ID env var)")
    
    click.echo(f"Course Root: {ctx.course_root}")
    click.echo(f"Content Dir: {ctx.content_dir.name}/" if ctx.content_dir.exists() else "Content Dir: Not found")
    click.echo(f"Zaphod Scripts: {ctx.zaphod_root or 'Not found'}")
    
    # Sync status
    click.echo("\n[*] Last Sync")
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
    click.echo("\n[books] Content Statistics")
    click.echo("-" * 60)
    
    if ctx.content_dir.exists():
        stats = {
            "pages": len(list(ctx.content_dir.rglob("*.page"))),
            "assignments": len(list(ctx.content_dir.rglob("*.assignment"))),
            "quizzes": len([d for d in ctx.content_dir.rglob("*.quiz") if d.is_dir()]),
            "links": len(list(ctx.content_dir.rglob("*.link"))),
            "files": len(list(ctx.content_dir.rglob("*.file"))),
        }
        
        for content_type, count in stats.items():
            click.echo(f"{content_type.capitalize()}: {count}")
    else:
        click.echo("No content directory found (content/ or pages/)")
    
    # Question banks
    banks_dir = ctx.course_root / "quiz-banks"
    if banks_dir.exists():
        bank_count = len(list(banks_dir.glob("*.bank.md")))
        legacy_count = len(list(banks_dir.glob("*.quiz.txt")))
        click.echo(f"Question Banks: {bank_count}")
        if legacy_count:
            click.echo(f"Legacy Banks: {legacy_count} (consider migrating to .bank.md)")
    
    # Check for issues
    click.echo("\n[*] Quick Check")
    click.echo("-" * 60)
    
    checks = []
    if not ctx.zaphod_root:
        checks.append("[!]  Zaphod scripts not found")
    if not course_id:
        checks.append("[!]  Course ID not configured")
    
    cred_file = Path(os.environ.get("CANVAS_CREDENTIAL_FILE", Path.home() / ".canvas" / "credentials.txt"))
    if not cred_file.exists():
        checks.append(f"[!]  Canvas credentials not found at {cred_file}")
    
    if checks:
        for check in checks:
            click.echo(check)
    else:
        click.echo("[v] All checks passed")


# ============================================================================
# Init / Scaffold
# ============================================================================

@cli.command()
@click.option('--course-id', type=int, help='Canvas course ID')
@click.option('--force', is_flag=True, help='Overwrite existing template files')
@click.pass_obj
def init(ctx: ZaphodContext, course_id: Optional[int], force: bool):
    """
    Initialize a new Zaphod course structure
    
    Creates the standard directory structure and sample content:
    - content/         Content folders (.page, .assignment, .quiz, etc.)
    - shared/          Shared variables and includes
    - assets/          Shared media files (images, videos, PDFs)
    - quiz-banks/      Question bank files (.bank.md)
    - modules/         Module ordering configuration
    - outcomes/        Learning outcomes definitions
    - rubrics/         Shared rubrics and reusable rows
    - _course_metadata/ Internal state and cache files
    
    Also creates sample content to help you get started.
    
    Examples:
        zaphod init                        # Initialize with prompts
        zaphod init --course-id 12345      # Set course ID during init
        zaphod init --force                # Overwrite existing templates
    """
    click.echo(f"[*] Initializing Zaphod course in: {ctx.course_root}")
    
    # Create zaphod.yaml if course_id provided
    if course_id:
        yaml_path = ctx.course_root / "zaphod.yaml"
        if yaml_path.exists() and not force:
            click.echo(f"[!] zaphod.yaml already exists (use --force to overwrite)")
        else:
            yaml_content = f"""# Zaphod Course Configuration
course_id: {course_id}

# Optional: Course metadata
# title: "My Course"
# term: "Spring 2026"
"""
            yaml_path.write_text(yaml_content)
            click.echo(f"[v] Created zaphod.yaml with course_id: {course_id}")
    
    # Run scaffold script
    args = []
    if force:
        args.append("--force")
    
    ctx.run_script("scaffold_course.py", args=args if args else None)
    
    click.echo()
    click.echo("[v] Course initialized!")
    click.echo()
    click.echo("Next steps:")
    click.echo("  1. Edit zaphod.yaml to set your course_id (if not set)")
    click.echo("  2. Edit the sample content in content/")
    click.echo("  3. Run: zaphod sync --dry-run")
    click.echo("  4. Run: zaphod sync")


# ============================================================================
# Media Management
# ============================================================================

@cli.command()
@click.pass_obj
def manifest(ctx: ZaphodContext):
    """
    Build media manifest for large files
    
    Scans the course for large media files (videos, audio) and creates
    a manifest at _course_metadata/media_manifest.json. This manifest
    tracks files that should be excluded from Git but need to be
    available for syncing.
    
    The manifest includes:
    - File paths relative to course root
    - SHA256 checksums for verification
    - File sizes
    
    Use this with 'zaphod hydrate' for team workflows where large
    files are stored on a shared network drive or server.
    
    Examples:
        zaphod manifest                    # Build manifest
    
    See also:
        zaphod hydrate                     # Download files listed in manifest
    """
    click.echo(f"[*] Building media manifest for: {ctx.course_root}")
    click.echo()
    
    ctx.run_script("build_media_manifest.py")
    
    manifest_path = ctx.metadata_dir / "media_manifest.json"
    if manifest_path.exists():
        click.echo()
        click.echo(f"[v] Manifest saved to: {manifest_path}")


@cli.command()
@click.option('--source', required=True, help='Source path or URL (SMB path, local path, or HTTP URL)')
@click.option('--verify/--no-verify', default=True, help='Verify checksums after download')
@click.option('--dry-run', is_flag=True, help='Show what would be downloaded')
@click.pass_obj
def hydrate(ctx: ZaphodContext, source: str, verify: bool, dry_run: bool):
    """
    Download missing media files from a shared source
    
    Reads the media manifest and downloads any missing files from
    the specified source location. Supports:
    
    - Local paths: /mnt/shared/courses/CS101
    - SMB paths: \\\\server\\courses\\CS101
    - HTTP URLs: https://media.example.com/courses/CS101
    
    Files are verified against checksums in the manifest to ensure
    integrity.
    
    Examples:
        # From a network share
        zaphod hydrate --source "\\\\fileserver\\courses\\CS101"
        
        # From a local path
        zaphod hydrate --source /mnt/shared/courses/CS101
        
        # From HTTP server
        zaphod hydrate --source https://media.example.edu/CS101
        
        # Preview what would be downloaded
        zaphod hydrate --source /path/to/source --dry-run
        
        # Skip checksum verification (faster)
        zaphod hydrate --source /path/to/source --no-verify
    
    See also:
        zaphod manifest                    # Build the manifest first
    """
    manifest_path = ctx.metadata_dir / "media_manifest.json"
    if not manifest_path.exists():
        click.echo("[!] No media manifest found. Run 'zaphod manifest' first.", err=True)
        sys.exit(1)
    
    click.echo(f"[*] Hydrating media from: {source}")
    if dry_run:
        click.echo("[*] DRY RUN - no files will be downloaded")
    click.echo()
    
    args = ["--source", source]
    if not verify:
        args.append("--no-verify")
    if dry_run:
        args.append("--dry-run")
    
    ctx.run_script("hydrate_media.py", args=args)


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
        click.echo("[!]  QTI-only export not yet implemented")
        click.echo("Use --format cartridge for full course export (includes quizzes)")
        sys.exit(1)
    
    click.echo(f"[pkg] Exporting course from: {ctx.course_root}")
    
    # Build command
    script_path = ctx.zaphod_root / "export_cartridge.py" if ctx.zaphod_root else None
    
    if not script_path or not script_path.exists():
        # Try relative to this file
        script_path = Path(__file__).parent / "export_cartridge.py"
    
    if not script_path.exists():
        click.echo("[x] export_cartridge.py not found", err=True)
        sys.exit(1)
    
    cmd = [ctx.python_exe, str(script_path)]
    
    if output:
        cmd.extend(['--output', output])
    if title:
        cmd.extend(['--title', title])
    
    result = subprocess.run(cmd, cwd=str(ctx.course_root))
    
    if result.returncode == 0:
        click.echo("\n[v] Export complete!")
    else:
        click.echo("\n[x] Export failed", err=True)
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
    click.echo(f"[*] Starting Zaphod UI on http://localhost:{port}")
    click.echo("Press Ctrl+C to stop")
    
    if not no_browser:
        time.sleep(1)
        webbrowser.open(f"http://localhost:{port}")
    
    # Try to import and run the UI
    try:
        # This would be your FastAPI app from the UI implementation
        click.echo("\n[!]  UI not yet implemented")
        click.echo("Run the standalone UI server instead:")
        click.echo(f"  python simple_ui.py")
    except ImportError:
        click.echo("\n[x] UI dependencies not installed", err=True)
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
