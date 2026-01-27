#!/usr/bin/env python3

"""
path_utils.py - Shared path utilities for Zaphod

Provides consistent directory resolution across all Zaphod scripts.
Supports both new (content/, shared/) and legacy (pages/, includes/) folder names.
"""

from pathlib import Path

# Course root is always the current working directory
COURSE_ROOT = Path.cwd()

# Content directories (prefer content/, fall back to pages/)
CONTENT_DIR = COURSE_ROOT / "content"
PAGES_DIR = COURSE_ROOT / "pages"

# Shared folder for variables and includes
SHARED_DIR = COURSE_ROOT / "shared"


def get_content_dir() -> Path:
    """
    Get the content root directory.
    Prefers content/ if it exists, otherwise uses pages/ for backward compatibility.
    
    Returns:
        Path to content/ or pages/ directory
    """
    if CONTENT_DIR.exists():
        return CONTENT_DIR
    return PAGES_DIR


def get_content_dir_name() -> str:
    """
    Get the name of the content directory being used.
    
    Returns:
        "content" or "pages"
    """
    return get_content_dir().name


def content_dir_exists() -> bool:
    """
    Check if either content/ or pages/ exists.
    
    Returns:
        True if either directory exists
    """
    return CONTENT_DIR.exists() or PAGES_DIR.exists()


def get_shared_dir() -> Path:
    """
    Get the shared folder path for variables and includes.
    
    Returns:
        Path to shared/ directory (may not exist)
    """
    return SHARED_DIR


def get_assets_dir() -> Path:
    """
    Get the assets directory path.
    
    Returns:
        Path to assets/ directory (may not exist)
    """
    return COURSE_ROOT / "assets"


def get_metadata_dir() -> Path:
    """
    Get the metadata directory path.
    
    Returns:
        Path to _course_metadata/ directory
    """
    return COURSE_ROOT / "_course_metadata"


def iter_content_folders(extensions: list[str] | None = None):
    """
    Iterate over all content folders in the content directory.
    
    Args:
        extensions: List of extensions to match (e.g., [".page", ".assignment"])
                   If None, matches all known extensions.
    
    Yields:
        Path objects for each matching folder
    """
    if extensions is None:
        extensions = [".page", ".assignment", ".link", ".file", ".quiz"]
    
    content_root = get_content_dir()
    if not content_root.exists():
        return
    
    for ext in extensions:
        for folder in content_root.rglob(f"*{ext}"):
            if folder.is_dir():
                yield folder
