#!/usr/bin/env python3
"""
canvas_client.py - Shared Canvas API client helper

Replaces markdown2canvas's make_canvas_api_obj() with a Zaphod-native implementation.
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional

from canvasapi import Canvas


def get_canvas_credentials() -> tuple[str, str]:
    """
    Read Canvas API credentials from CANVAS_CREDENTIAL_FILE.
    
    The file should contain Python-style assignments:
        API_KEY = "your_token_here"
        API_URL = "https://canvas.yourinstitution.edu"
    
    Returns:
        (api_url, api_key) tuple
        
    Raises:
        SystemExit: If credentials file not found or missing required values
    """
    cred_path = os.environ.get("CANVAS_CREDENTIAL_FILE")
    if not cred_path:
        # Default location
        cred_path = str(Path.home() / ".canvas" / "credentials.txt")
    
    cred_file = Path(cred_path)
    if not cred_file.is_file():
        raise SystemExit(
            f"Canvas credentials file not found: {cred_file}\n\n"
            f"Create it with:\n"
            f"  mkdir -p ~/.canvas\n"
            f"  nano ~/.canvas/credentials.txt\n\n"
            f"Contents:\n"
            f'  API_KEY = "your_canvas_token"\n'
            f'  API_URL = "https://canvas.yourinstitution.edu"'
        )
    
    # Execute the file to get API_KEY and API_URL
    ns: Dict[str, Any] = {}
    try:
        exec(cred_file.read_text(encoding="utf-8"), ns)
    except Exception as e:
        raise SystemExit(f"Error parsing credentials file {cred_file}: {e}")
    
    try:
        api_key = ns["API_KEY"]
        api_url = ns["API_URL"]
    except KeyError as e:
        raise SystemExit(
            f"Credentials file must define API_KEY and API_URL. Missing: {e}"
        )
    
    # Normalize URL (remove trailing slash)
    api_url = api_url.rstrip("/")
    
    return api_url, api_key


def make_canvas_api_obj() -> Canvas:
    """
    Create and return a Canvas API client.
    
    Drop-in replacement for markdown2canvas.setup_functions.make_canvas_api_obj()
    
    Returns:
        canvasapi.Canvas instance
    """
    api_url, api_key = get_canvas_credentials()
    return Canvas(api_url, api_key)


def get_canvas_base_url() -> str:
    """
    Get the base Canvas URL (without /api/v1).
    
    Useful for constructing URLs like media_attachments_iframe.
    
    Returns:
        Base URL string (e.g., "https://canvas.institution.edu")
    """
    api_url, _ = get_canvas_credentials()
    return api_url
