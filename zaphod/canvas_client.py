#!/usr/bin/env python3
"""
canvas_client.py - Shared Canvas API client helper

Replaces markdown2canvas's make_canvas_api_obj() with a Zaphod-native implementation.

SECURITY: Uses centralized credential loading from security_utils.py
"""

import os
from pathlib import Path
from typing import TYPE_CHECKING, Tuple

# Lazy import - only load canvasapi when actually needed
if TYPE_CHECKING:
    from canvasapi import Canvas

# Import security utilities for credential loading
from zaphod.security_utils import (
    load_canvas_credentials_safe,
    CredentialError,
    mask_sensitive,
)


def get_canvas_credentials() -> Tuple[str, str]:
    """
    Read Canvas API credentials safely.
    
    Checks (in order):
    1. CANVAS_API_KEY and CANVAS_API_URL environment variables
    2. CANVAS_CREDENTIAL_FILE (or default ~/.canvas/credentials.txt)
    
    Returns:
        (api_url, api_key) tuple
        
    Raises:
        SystemExit: If credentials not found or missing required values
    """
    try:
        # Use centralized secure credential loading
        cred_path = os.environ.get("CANVAS_CREDENTIAL_FILE")
        if not cred_path:
            cred_path = str(Path.home() / ".canvas" / "credentials.txt")
        
        api_url, api_key = load_canvas_credentials_safe(cred_path)
        return api_url, api_key
        
    except CredentialError as e:
        raise SystemExit(
            f"Canvas credentials error: {e}\n\n"
            f"Option 1 - Environment variables:\n"
            f"  export CANVAS_API_KEY='your_token'\n"
            f"  export CANVAS_API_URL='https://canvas.yourinstitution.edu'\n\n"
            f"Option 2 - Create credentials file:\n"
            f"  mkdir -p ~/.canvas\n"
            f"  nano ~/.canvas/credentials.txt\n"
            f"  chmod 600 ~/.canvas/credentials.txt\n\n"
            f"Contents:\n"
            f'  API_KEY = "your_canvas_token"\n'
            f'  API_URL = "https://canvas.yourinstitution.edu"'
        )


def make_canvas_api_obj() -> "Canvas":
    """
    Create and return a Canvas API client.
    
    Drop-in replacement for markdown2canvas.setup_functions.make_canvas_api_obj()
    
    Returns:
        canvasapi.Canvas instance
    """
    from canvasapi import Canvas  # Lazy import
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
