#!/usr/bin/env python3
"""
security_utils.py (Zaphod)

Shared security utilities for safe credential loading, input validation,
path traversal protection, and secure logging.

This module centralizes security-critical functions to ensure consistent
handling across all Zaphod scripts.
"""

from __future__ import annotations

import hashlib
import os
import re
import stat
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union
import warnings


# ============================================================================
# Credential Loading (Safe - No exec())
# ============================================================================

class CredentialError(Exception):
    """Raised when credentials cannot be loaded or are invalid."""
    pass


def load_canvas_credentials_safe(cred_path: Optional[str] = None) -> Tuple[str, str]:
    """
    Safely load Canvas API credentials without using exec().
    
    Supports multiple formats:
    1. Environment variables (CANVAS_API_KEY, CANVAS_API_URL)
    2. Simple KEY=VALUE format file
    3. Python-style assignment file (parsed safely, not executed)
    
    Args:
        cred_path: Path to credentials file, or None to use env var
        
    Returns:
        Tuple of (api_url, api_key)
        
    Raises:
        CredentialError: If credentials cannot be loaded
    """
    # Priority 1: Environment variables
    env_key = os.environ.get("CANVAS_API_KEY")
    env_url = os.environ.get("CANVAS_API_URL")
    
    if env_key and env_url:
        return env_url.rstrip("/"), env_key
    
    # Priority 2: Credential file
    if cred_path is None:
        cred_path = os.environ.get("CANVAS_CREDENTIAL_FILE")
    
    if not cred_path:
        raise CredentialError(
            "No credentials found. Set CANVAS_API_KEY and CANVAS_API_URL environment "
            "variables, or set CANVAS_CREDENTIAL_FILE to point to a credentials file."
        )
    
    cred_file = Path(cred_path)
    if not cred_file.is_file():
        raise CredentialError(f"Credentials file not found: {cred_file}")
    
    # Check file permissions (warn if too permissive)
    check_file_permissions(cred_file)
    
    # Parse credentials file safely
    api_key, api_url = _parse_credentials_file(cred_file)
    
    if not api_key or not api_url:
        raise CredentialError(
            f"Credentials file must define API_KEY and API_URL: {cred_file}"
        )
    
    return api_url.rstrip("/"), api_key


def _parse_credentials_file(cred_file: Path) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse credentials file safely without exec().
    
    Supports formats:
    - API_KEY = "value" or API_KEY = 'value'
    - API_KEY="value" (no spaces)
    - API_KEY: value (YAML-style)
    """
    content = cred_file.read_text(encoding="utf-8")
    
    api_key = None
    api_url = None
    
    # Patterns to match different formats
    patterns = [
        # Python-style: API_KEY = "value" or API_KEY = 'value'
        (r'API_KEY\s*=\s*["\']([^"\']+)["\']', r'API_URL\s*=\s*["\']([^"\']+)["\']'),
        # No quotes: API_KEY = value
        (r'API_KEY\s*=\s*(\S+)', r'API_URL\s*=\s*(\S+)'),
        # YAML-style: API_KEY: value
        (r'API_KEY\s*:\s*["\']?([^"\'\n]+)["\']?', r'API_URL\s*:\s*["\']?([^"\'\n]+)["\']?'),
    ]
    
    for key_pattern, url_pattern in patterns:
        if api_key is None:
            match = re.search(key_pattern, content)
            if match:
                api_key = match.group(1).strip()
        
        if api_url is None:
            match = re.search(url_pattern, content)
            if match:
                api_url = match.group(1).strip()
        
        if api_key and api_url:
            break
    
    return api_key, api_url


def check_file_permissions(file_path: Path, warn_only: bool = True) -> bool:
    """
    Check if file has secure permissions (not readable by group/others).
    
    Args:
        file_path: Path to check
        warn_only: If True, warn but don't raise. If False, raise on insecure.
        
    Returns:
        True if permissions are secure, False otherwise
    """
    try:
        mode = os.stat(file_path).st_mode
        is_secure = not (mode & (stat.S_IRWXG | stat.S_IRWXO))
        
        if not is_secure:
            msg = (
                f"Credentials file has insecure permissions: {file_path}\n"
                f"Other users may be able to read your API key.\n"
                f"Fix with: chmod 600 {file_path}"
            )
            if warn_only:
                warnings.warn(msg, UserWarning)
            else:
                raise CredentialError(msg)
        
        return is_secure
    except OSError:
        # Can't check permissions (e.g., Windows)
        return True


# ============================================================================
# API Key Masking for Logs
# ============================================================================

def mask_sensitive(value: str, visible_chars: int = 4) -> str:
    """
    Mask a sensitive value for safe logging.
    
    Args:
        value: The sensitive string to mask
        visible_chars: Number of characters to show at start and end
        
    Returns:
        Masked string like "abc1****xyz9"
    """
    if not value:
        return "****"
    
    if len(value) <= visible_chars * 2:
        return "****"
    
    return f"{value[:visible_chars]}****{value[-visible_chars:]}"


# ============================================================================
# Path Validation and Sanitization
# ============================================================================

def is_safe_path(base_dir: Path, target_path: Path) -> bool:
    """
    Check if target_path is safely within base_dir (no symlink escape).
    
    Prevents path traversal attacks via symlinks or ../ sequences.
    
    Args:
        base_dir: The allowed base directory
        target_path: The path to validate
        
    Returns:
        True if target is within base (safe), False otherwise
    """
    try:
        # Resolve both paths to absolute, following symlinks
        base_resolved = base_dir.resolve()
        target_resolved = target_path.resolve()
        
        # Check if target is within base
        target_resolved.relative_to(base_resolved)
        return True
    except ValueError:
        return False


def sanitize_filename(name: str, max_length: int = 255) -> str:
    """
    Create a safe filename from user input.
    
    Removes or replaces dangerous characters that could cause:
    - Path traversal (../, /, \\)
    - Shell injection
    - Filesystem issues
    
    Args:
        name: User-provided name
        max_length: Maximum allowed length
        
    Returns:
        Sanitized filename safe for filesystem use
        
    Raises:
        ValueError: If name results in empty or invalid filename
    """
    if not name:
        raise ValueError("Filename cannot be empty")
    
    # Remove or replace dangerous characters
    # Allow: alphanumeric, spaces, hyphens, underscores
    safe = re.sub(r'[^\w\s-]', '', name)
    
    # Replace multiple spaces/hyphens with single hyphen
    safe = re.sub(r'[-\s]+', '-', safe)
    
    # Remove leading/trailing hyphens
    safe = safe.strip('-')
    
    # Convert to lowercase for consistency
    safe = safe.lower()
    
    # Ensure not empty after sanitization
    if not safe:
        raise ValueError(f"Name '{name}' results in empty filename after sanitization")
    
    # Check for path traversal attempts
    if '..' in safe or safe.startswith('/') or safe.startswith('\\'):
        raise ValueError(f"Invalid characters in filename: {name}")
    
    # Truncate if too long
    if len(safe) > max_length:
        safe = safe[:max_length].rstrip('-')
    
    return safe


def validate_course_path(path: Path, course_root: Path) -> bool:
    """
    Validate that a path is within the course directory structure.
    
    Args:
        path: Path to validate
        course_root: Root directory of the course
        
    Returns:
        True if path is valid and within course_root
    """
    if not is_safe_path(course_root, path):
        return False
    
    # Additional checks for expected course structure
    try:
        rel = path.relative_to(course_root)
        # Don't allow access to hidden directories (except _course_metadata)
        for part in rel.parts:
            if part.startswith('.') and part != '.':
                return False
        return True
    except ValueError:
        return False


# ============================================================================
# Input Validation
# ============================================================================

def validate_course_id(course_id: Union[str, int, None]) -> int:
    """
    Validate and convert course ID to integer.
    
    Args:
        course_id: Course ID as string, int, or None
        
    Returns:
        Validated course ID as integer
        
    Raises:
        ValueError: If course_id is invalid
    """
    if course_id is None:
        raise ValueError("Course ID is required")
    
    try:
        cid = int(course_id)
        if cid <= 0:
            raise ValueError(f"Course ID must be positive: {course_id}")
        return cid
    except (TypeError, ValueError):
        raise ValueError(f"Invalid course ID: {course_id}")


def validate_url(url: str) -> str:
    """
    Validate and normalize a URL.
    
    Args:
        url: URL to validate
        
    Returns:
        Normalized URL
        
    Raises:
        ValueError: If URL is invalid
    """
    if not url:
        raise ValueError("URL cannot be empty")
    
    # Basic URL validation
    url = url.strip()
    
    if not url.startswith(('http://', 'https://')):
        raise ValueError(f"URL must start with http:// or https://: {url}")
    
    # Check for suspicious patterns
    if '..' in url or '\x00' in url:
        raise ValueError(f"Invalid URL: {url}")
    
    return url.rstrip('/')


# ============================================================================
# Safe JSON/API Response Handling
# ============================================================================

def safe_get(data: Dict[str, Any], key: str, expected_type: type = None, 
             default: Any = None) -> Any:
    """
    Safely get a value from a dictionary with optional type validation.
    
    Args:
        data: Dictionary to get value from
        key: Key to look up
        expected_type: Expected type of value (optional)
        default: Default value if key not found
        
    Returns:
        The value, or default if not found
        
    Raises:
        TypeError: If value exists but is wrong type (when expected_type specified)
    """
    value = data.get(key, default)
    
    if value is not None and expected_type is not None:
        if not isinstance(value, expected_type):
            raise TypeError(
                f"Expected {expected_type.__name__} for '{key}', "
                f"got {type(value).__name__}"
            )
    
    return value


# ============================================================================
# Content Hashing for Change Detection
# ============================================================================

def get_file_hash(file_path: Path) -> str:
    """
    Get SHA-256 hash of file contents for change detection.
    
    Args:
        file_path: Path to file
        
    Returns:
        Hex string of SHA-256 hash
    """
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def get_content_hash(content: Union[str, bytes]) -> str:
    """
    Get SHA-256 hash of content string/bytes.
    
    Args:
        content: String or bytes to hash
        
    Returns:
        Hex string of SHA-256 hash
    """
    if isinstance(content, str):
        content = content.encode('utf-8')
    return hashlib.sha256(content).hexdigest()


# ============================================================================
# Request Timeout Constants
# ============================================================================

# Default timeouts for HTTP requests (connect, read)
DEFAULT_TIMEOUT = (10, 30)  # 10s connect, 30s read
UPLOAD_TIMEOUT = (10, 120)  # Longer read timeout for uploads
MIGRATION_TIMEOUT = (10, 60)  # For migration status checks


# ============================================================================
# Rate Limiting for Canvas API
# ============================================================================

import time
from collections import deque
from threading import Lock

class RateLimiter:
    """
    Simple rate limiter for API calls.
    
    Canvas typically allows ~700 requests per 10 minutes (varies by instance).
    This provides a conservative limit to avoid hitting rate limits.
    """
    
    def __init__(self, max_requests: int = 100, window_seconds: float = 60.0):
        """
        Initialize rate limiter.
        
        Args:
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.timestamps: deque = deque()
        self.lock = Lock()
        self._slowdown_until = 0.0
    
    def wait_if_needed(self):
        """
        Wait if rate limit would be exceeded.
        
        Call this before making an API request.
        """
        with self.lock:
            now = time.time()
            
            # Check if we're in slowdown mode (from rate limit response)
            if now < self._slowdown_until:
                sleep_time = self._slowdown_until - now
                print(f"[rate-limit] Waiting {sleep_time:.1f}s (rate limit cooldown)")
                time.sleep(sleep_time)
                now = time.time()
            
            # Remove timestamps outside window
            cutoff = now - self.window_seconds
            while self.timestamps and self.timestamps[0] < cutoff:
                self.timestamps.popleft()
            
            # Check if at limit
            if len(self.timestamps) >= self.max_requests:
                # Wait until oldest request is outside window
                sleep_time = self.timestamps[0] - cutoff + 0.1
                if sleep_time > 0:
                    print(f"[rate-limit] Waiting {sleep_time:.1f}s to stay under limit")
                    time.sleep(sleep_time)
                    now = time.time()
                    # Clean up again
                    cutoff = now - self.window_seconds
                    while self.timestamps and self.timestamps[0] < cutoff:
                        self.timestamps.popleft()
            
            # Record this request
            self.timestamps.append(now)
    
    def handle_rate_limit_response(self, retry_after: float = 60.0):
        """
        Handle a rate limit response from Canvas.
        
        Call this when you receive a 403 rate limit error.
        
        Args:
            retry_after: Seconds to wait (from X-Rate-Limit-Remaining or default)
        """
        with self.lock:
            self._slowdown_until = time.time() + retry_after
            print(f"[rate-limit] Canvas rate limit hit, backing off for {retry_after}s")
    
    def check_response_headers(self, headers: dict):
        """
        Check Canvas API response headers for rate limit info.
        
        Args:
            headers: Response headers dict
        """
        remaining = headers.get('X-Rate-Limit-Remaining')
        if remaining is not None:
            try:
                remaining = float(remaining)
                if remaining < 50:
                    # Getting low, slow down
                    slowdown = max(1.0, (50 - remaining) / 10)
                    print(f"[rate-limit] Low rate limit remaining ({remaining}), adding {slowdown:.1f}s delay")
                    time.sleep(slowdown)
            except (ValueError, TypeError):
                pass


# Global rate limiter instance
_canvas_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Get the global Canvas API rate limiter."""
    global _canvas_rate_limiter
    if _canvas_rate_limiter is None:
        # Conservative defaults: 100 requests per minute
        _canvas_rate_limiter = RateLimiter(max_requests=100, window_seconds=60.0)
    return _canvas_rate_limiter


def rate_limited_request(func):
    """
    Decorator to add rate limiting to API request functions.
    
    Usage:
        @rate_limited_request
        def my_api_call():
            return requests.get(...)
    """
    def wrapper(*args, **kwargs):
        get_rate_limiter().wait_if_needed()
        return func(*args, **kwargs)
    return wrapper
