# config_utils.py - YAML Configuration System for Zaphod
"""
Zaphod configuration utilities with YAML file support.

Configuration Resolution Order (highest to lowest priority):
1. Environment variables (COURSE_ID, CANVAS_CREDENTIAL_FILE, etc.)
2. zaphod.yaml in course root
3. _course_metadata/defaults.json (legacy support)
4. ~/.zaphod/config.yaml (global defaults)

Usage:
    from config_utils import get_config, get_course_id
    
    # Get full configuration
    config = get_config()
    print(config.course_id)
    print(config.api_url)
    
    # Legacy function (backward compatible)
    course_id = get_course_id()
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List

# Try to import yaml, fall back gracefully
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False


# Error classes (inline to avoid dependency)
class ConfigurationError(Exception):
    """Configuration is missing or invalid"""
    def __init__(self, message: str, suggestion: Optional[str] = None, context: Optional[Dict] = None):
        self.message = message
        self.suggestion = suggestion
        self.context = context or {}
        super().__init__(self._format())
    
    def _format(self) -> str:
        lines = ["", "=" * 70, f"❌ ConfigurationError", "=" * 70, "", self.message]
        if self.context:
            lines.extend(["", "Context:"] + [f"  {k}: {v}" for k, v in self.context.items()])
        if self.suggestion:
            lines.extend(["", "💡 Suggestion:", f"  {self.suggestion}"])
        lines.extend(["", "=" * 70, ""])
        return "\n".join(lines)


@dataclass
class ZaphodConfig:
    """Complete Zaphod configuration"""
    # Canvas connection
    course_id: Optional[str] = None
    course_name: Optional[str] = None
    api_url: Optional[str] = None
    api_key: Optional[str] = None
    credential_file: Optional[Path] = None
    
    # markdown2canvas settings
    replacements: Optional[str] = None
    style: Optional[str] = None
    markdown_extensions: Optional[List[str]] = None
    
    # Prune settings
    prune_apply: bool = True
    prune_assignments: bool = True
    
    # Watch settings
    watch_debounce: float = 2.0
    
    # Paths (resolved at load time)
    course_root: Optional[Path] = None
    
    # Extra settings from config file
    extra: Dict[str, Any] = field(default_factory=dict)
    
    # Track where values came from (for debugging)
    _sources: Dict[str, str] = field(default_factory=dict)


class ConfigLoader:
    """Load configuration from multiple sources"""
    
    def __init__(self, course_dir: Optional[Path] = None):
        self.course_dir = Path(course_dir) if course_dir else Path.cwd()
        self.config = ZaphodConfig(course_root=self.course_dir)
    
    def load(self) -> ZaphodConfig:
        """Load configuration from all sources in priority order"""
        # Load in reverse priority (lowest first, higher overwrites)
        self._load_global_config()
        self._load_legacy_defaults()
        self._load_yaml_config()
        self._load_env_vars()
        
        # Resolve credentials if needed
        self._resolve_credentials()
        
        return self.config
    
    def _load_global_config(self):
        """Load ~/.zaphod/config.yaml if it exists"""
        global_config = Path.home() / ".zaphod" / "config.yaml"
        if global_config.exists() and YAML_AVAILABLE:
            self._load_yaml_file(global_config, "global")
    
    def _load_legacy_defaults(self):
        """Load _course_metadata/defaults.json for backward compatibility"""
        defaults_path = self.course_dir / "_course_metadata" / "defaults.json"
        if defaults_path.exists():
            try:
                data = json.loads(defaults_path.read_text())
                
                if data.get("course_id"):
                    self.config.course_id = str(data["course_id"])
                    self.config._sources["course_id"] = "defaults.json"
                
                if data.get("course_name"):
                    self.config.course_name = data["course_name"]
                    self.config._sources["course_name"] = "defaults.json"
                
                if data.get("canvas_api_url"):
                    self.config.api_url = data["canvas_api_url"]
                    self.config._sources["api_url"] = "defaults.json"
                
                if data.get("replacements"):
                    self.config.replacements = data["replacements"]
                    self.config._sources["replacements"] = "defaults.json"
                
                if data.get("style"):
                    self.config.style = data["style"]
                    self.config._sources["style"] = "defaults.json"
                
                if data.get("markdown_extensions"):
                    self.config.markdown_extensions = data["markdown_extensions"]
                    self.config._sources["markdown_extensions"] = "defaults.json"
                    
            except (json.JSONDecodeError, Exception) as e:
                print(f"[config:warn] Failed to load {defaults_path}: {e}")
    
    def _load_yaml_config(self):
        """Load zaphod.yaml from course root"""
        yaml_path = self.course_dir / "zaphod.yaml"
        if yaml_path.exists():
            if not YAML_AVAILABLE:
                print("[config:warn] zaphod.yaml found but PyYAML not installed. Run: pip install pyyaml")
                return
            self._load_yaml_file(yaml_path, "zaphod.yaml")
    
    def _load_yaml_file(self, path: Path, source_name: str):
        """Load settings from a YAML file"""
        try:
            data = yaml.safe_load(path.read_text()) or {}
        except Exception as e:
            print(f"[config:warn] Failed to parse {path}: {e}")
            return
        
        # Map YAML keys to config attributes
        mappings = {
            "course_id": "course_id",
            "course_name": "course_name",
            "api_url": "api_url",
            "api_key": "api_key",
            "credential_file": "credential_file",
            "replacements": "replacements",
            "style": "style",
            "markdown_extensions": "markdown_extensions",
        }
        
        for yaml_key, attr in mappings.items():
            if yaml_key in data:
                value = data[yaml_key]
                if yaml_key == "credential_file":
                    value = Path(value).expanduser()
                setattr(self.config, attr, value)
                self.config._sources[attr] = source_name
        
        # Handle nested prune settings
        if "prune" in data and isinstance(data["prune"], dict):
            prune = data["prune"]
            if "apply" in prune:
                self.config.prune_apply = bool(prune["apply"])
                self.config._sources["prune_apply"] = source_name
            if "assignments" in prune:
                self.config.prune_assignments = bool(prune["assignments"])
                self.config._sources["prune_assignments"] = source_name
        
        # Handle nested watch settings
        if "watch" in data and isinstance(data["watch"], dict):
            watch = data["watch"]
            if "debounce" in watch:
                self.config.watch_debounce = float(watch["debounce"])
                self.config._sources["watch_debounce"] = source_name
        
        # Store any extra settings
        known_keys = {"course_id", "course_name", "api_url", "api_key", "credential_file", 
                      "replacements", "style", "markdown_extensions", "prune", "watch"}
        for key, value in data.items():
            if key not in known_keys:
                self.config.extra[key] = value
    
    def _load_env_vars(self):
        """Load from environment variables (highest priority)"""
        if os.environ.get("COURSE_ID"):
            self.config.course_id = os.environ["COURSE_ID"]
            self.config._sources["course_id"] = "env:COURSE_ID"
        
        if os.environ.get("CANVAS_CREDENTIAL_FILE"):
            self.config.credential_file = Path(os.environ["CANVAS_CREDENTIAL_FILE"])
            self.config._sources["credential_file"] = "env:CANVAS_CREDENTIAL_FILE"
        
        if os.environ.get("CANVAS_API_URL"):
            self.config.api_url = os.environ["CANVAS_API_URL"]
            self.config._sources["api_url"] = "env:CANVAS_API_URL"
        
        if os.environ.get("CANVAS_API_KEY"):
            self.config.api_key = os.environ["CANVAS_API_KEY"]
            self.config._sources["api_key"] = "env:CANVAS_API_KEY"
        
        # Prune settings from env
        prune_apply = os.environ.get("ZAPHOD_PRUNE_APPLY")
        if prune_apply is not None:
            self.config.prune_apply = prune_apply.lower() in {"1", "true", "yes", "on"}
            self.config._sources["prune_apply"] = "env:ZAPHOD_PRUNE_APPLY"
        
        prune_assignments = os.environ.get("ZAPHOD_PRUNE_ASSIGNMENTS")
        if prune_assignments is not None:
            self.config.prune_assignments = prune_assignments.lower() in {"1", "true", "yes", "on"}
            self.config._sources["prune_assignments"] = "env:ZAPHOD_PRUNE_ASSIGNMENTS"
    
    def _resolve_credentials(self):
        """Load API credentials from credential file if not set directly"""
        if self.config.api_url and self.config.api_key:
            return  # Already have credentials
        
        # Try credential file
        cred_file = self.config.credential_file
        if not cred_file:
            # Default location
            cred_file = Path.home() / ".canvas" / "credentials.txt"
        
        if cred_file.exists():
            try:
                ns: Dict[str, Any] = {}
                exec(cred_file.read_text(), ns)
                if not self.config.api_url and "API_URL" in ns:
                    self.config.api_url = ns["API_URL"]
                    self.config._sources["api_url"] = f"credentials:{cred_file.name}"
                if not self.config.api_key and "API_KEY" in ns:
                    self.config.api_key = ns["API_KEY"]
                    self.config._sources["api_key"] = f"credentials:{cred_file.name}"
            except Exception as e:
                print(f"[config:warn] Failed to load credentials from {cred_file}: {e}")


# ============================================================================
# Public API
# ============================================================================

def get_config(course_dir: Optional[Path] = None) -> ZaphodConfig:
    """
    Get complete Zaphod configuration.
    
    Args:
        course_dir: Course directory (defaults to cwd)
    
    Returns:
        ZaphodConfig with all settings resolved
    """
    loader = ConfigLoader(course_dir)
    return loader.load()


def get_course_id(course_dir: Optional[Path] = None) -> Optional[str]:
    """
    Get course ID from configuration.
    
    Backward-compatible function that checks:
    1. COURSE_ID environment variable
    2. zaphod.yaml in course root
    3. _course_metadata/defaults.json
    
    Args:
        course_dir: Course directory (defaults to cwd)
    
    Returns:
        Course ID string or None if not found
    
    Raises:
        ConfigurationError: If course ID not found anywhere
    """
    config = get_config(course_dir)
    if config.course_id:
        return config.course_id
    
    # Raise helpful error
    raise ConfigurationError(
        message="Course ID not configured",
        suggestion=(
            "Set course ID using one of these methods:\n\n"
            "1. Environment variable:\n"
            "   export COURSE_ID=12345\n\n"
            "2. Create zaphod.yaml in course root:\n"
            "   course_id: 12345\n\n"
            "3. Create _course_metadata/defaults.json:\n"
            '   {"course_id": "12345"}'
        ),
        context={
            "checked_locations": [
                "COURSE_ID environment variable",
                "zaphod.yaml",
                "_course_metadata/defaults.json",
            ]
        }
    )


def make_canvas_api_obj(config: Optional[ZaphodConfig] = None):
    """
    Create a Canvas API object from configuration.
    
    Replaces markdown2canvas.setup_functions.make_canvas_api_obj
    
    Args:
        config: Optional ZaphodConfig (loads fresh if not provided)
    
    Returns:
        canvasapi.Canvas object
    
    Raises:
        ConfigurationError: If credentials not found
    """
    from canvasapi import Canvas
    
    if config is None:
        config = get_config()
    
    if not config.api_url or not config.api_key:
        cred_path = config.credential_file or Path.home() / ".canvas" / "credentials.txt"
        raise ConfigurationError(
            message="Canvas API credentials not found",
            suggestion=(
                f"Create credentials file at: {cred_path}\n\n"
                "Contents:\n"
                '  API_KEY = "your_token_here"\n'
                '  API_URL = "https://canvas.yourinstitution.edu"\n\n'
                "Or add to zaphod.yaml:\n"
                "  api_url: https://canvas.yourinstitution.edu\n"
                "  api_key: your_token_here"
            ),
            context={
                "credential_file": str(cred_path),
            }
        )
    
    return Canvas(config.api_url, config.api_key)


def create_config_template(course_dir: Optional[Path] = None, include_comments: bool = True) -> str:
    """
    Generate a zaphod.yaml template.
    
    Args:
        course_dir: Course directory for context
        include_comments: Whether to include explanatory comments
    
    Returns:
        YAML string ready to write to file
    """
    if include_comments:
        return '''# Zaphod Configuration File
# See documentation for all options

# Canvas course ID (required)
course_id: REPLACE_WITH_YOUR_COURSE_ID

# Canvas API credentials
# Option 1: Reference a credentials file (recommended)
credential_file: ~/.canvas/credentials.txt

# Option 2: Inline credentials (less secure)
# api_url: https://canvas.yourinstitution.edu
# api_key: your_api_token_here

# Prune settings
prune:
  apply: true          # Actually delete orphaned content
  assignments: true    # Include assignments in pruning

# Watch mode settings
watch:
  debounce: 2.0        # Seconds to wait after file change before syncing
'''
    else:
        return '''course_id: REPLACE_WITH_YOUR_COURSE_ID
credential_file: ~/.canvas/credentials.txt
prune:
  apply: true
  assignments: true
watch:
  debounce: 2.0
'''
