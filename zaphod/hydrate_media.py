#!/usr/bin/env python3
"""
# Zaphod
# Copyright (c) 2026 Dale Chapman
# Licensed under the MIT License. See LICENSE in the project root.

hydrate_media.py

Populate missing large media files from a shared store based on the manifest.

This script:
1. Reads _course_metadata/media_manifest.json
2. For each item, checks if file exists locally with matching checksum
3. If missing or mismatched, copies from the specified source

For instructors who clone a course repo without the large media files.

Usage:
    python hydrate_media.py --source PATH_OR_URL [--verify] [--dry-run]

Examples:
    # From SMB share
    python hydrate_media.py --source "\\\\fileserver\\courses\\CS140"
    
    # From HTTP server
    python hydrate_media.py --source "https://media.example.com/courses/CS140"
    
    # From local path
    python hydrate_media.py --source "/mnt/shared/courses/CS140"
    
    # Dry run - show what would be downloaded
    python hydrate_media.py --source "..." --dry-run
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from urllib.parse import urlparse

from zaphod.security_utils import is_safe_path, is_safe_url
from zaphod.icons import SUCCESS, WARNING, fence

# Optional: requests for HTTP downloads
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


COURSE_ROOT = Path.cwd()
METADATA_DIR = COURSE_ROOT / "_course_metadata"
MANIFEST_PATH = METADATA_DIR / "media_manifest.json"


# =============================================================================
# Utility Functions
# =============================================================================

def compute_sha256(file_path: Path) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha256.update(chunk)
    return sha256.hexdigest()


def verify_checksum(file_path: Path, expected_checksum: str) -> bool:
    """Verify file checksum matches expected value."""
    if not expected_checksum:
        return True  # No checksum to verify
    
    # Parse checksum format "sha256:abcd1234..."
    if ':' in expected_checksum:
        algo, expected_hash = expected_checksum.split(':', 1)
    else:
        expected_hash = expected_checksum
    
    actual_hash = compute_sha256(file_path)
    return actual_hash == expected_hash


def load_manifest() -> Dict[str, Any]:
    """Load the media manifest."""
    if not MANIFEST_PATH.exists():
        raise SystemExit(f"[hydrate] Manifest not found: {MANIFEST_PATH}")
    
    with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def is_http_url(source: str) -> bool:
    """Check if source is an HTTP(S) URL."""
    parsed = urlparse(source)
    return parsed.scheme in ('http', 'https')


def is_smb_path(source: str) -> bool:
    """Check if source looks like an SMB/UNC path."""
    return source.startswith('\\\\') or source.startswith('//')


def copy_from_smb(source_path: str, dest_path: Path) -> bool:
    """Copy file from SMB/local path."""
    source = Path(source_path)
    
    if not source.exists():
        print(f"❌ Source not found: {source}")
        return False
    
    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest_path)
        return True
    except Exception as e:
        print(f"❌ Copy failed: {e}")
        return False


def download_from_http(url: str, dest_path: Path) -> bool:
    """Download file from HTTP(S) URL."""
    if not REQUESTS_AVAILABLE:
        print(f"❌ 'requests' library not installed. Run: pip install requests")
        return False
    
    # SECURITY: Validate URL to prevent SSRF attacks
    if not is_safe_url(url):
        print(f"🔒 Blocked potentially unsafe URL: {url}")
        print(f"🔒 Internal/private addresses are not allowed")
        return False
    
    try:
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        
        response = requests.get(url, stream=True, timeout=30)
        response.raise_for_status()
        
        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return True
    except Exception as e:
        print(f"❌ Download failed: {e}")
        return False


def hydrate_file(
    item: Dict[str, Any],
    source: str,
    verify: bool = True,
    dry_run: bool = False
) -> str:
    """
    Hydrate a single file from the manifest.
    
    Returns: 'skipped', 'downloaded', or 'failed'
    """
    relative_path = item['relative_path']
    local_path = COURSE_ROOT / relative_path
    checksum = item.get('checksum', '')
    size_bytes = item.get('size_bytes', 0)
    
    # SECURITY: Validate path is within course directory (prevent path traversal)
    if not is_safe_path(COURSE_ROOT, local_path):
        print(f"🔒 Blocked path traversal attempt: {relative_path}")
        return 'failed'
    
    # Check if file exists locally
    if local_path.exists():
        if verify and checksum:
            if verify_checksum(local_path, checksum):
                print(f"{SUCCESS} {relative_path} (exists, checksum OK)")
                return 'skipped'
            else:
                print(f"{WARNING} {relative_path} (exists, checksum MISMATCH - will re-download)")
        else:
            print(f"{SUCCESS} {relative_path} (exists)")
            return 'skipped'
    
    # Build source path
    if is_http_url(source):
        source_path = f"{source.rstrip('/')}/{relative_path}"
    else:
        # SMB or local path
        source_path = str(Path(source) / relative_path)
    
    size_mb = size_bytes / (1024 * 1024) if size_bytes else 0
    
    if dry_run:
        print(f"→ {relative_path} ({size_mb:.1f} MB) - would download from {source_path}")
        return 'skipped'

    print(f"↓ {relative_path} ({size_mb:.1f} MB)")
    print(f"from: {source_path}")
    
    # Download/copy
    if is_http_url(source):
        success = download_from_http(source_path, local_path)
    else:
        success = copy_from_smb(source_path, local_path)
    
    if not success:
        return 'failed'
    
    # Verify after download
    if verify and checksum:
        if verify_checksum(local_path, checksum):
            print(f"{SUCCESS} checksum verified")
        else:
            print(f"{WARNING} checksum mismatch after download!")
            return 'failed'
    
    return 'downloaded'


def main():
    parser = argparse.ArgumentParser(
        description="Hydrate missing media files from shared store"
    )
    parser.add_argument(
        "--source",
        required=True,
        help="Source path or URL (SMB path, local path, or HTTP URL)"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        default=True,
        help="Verify checksums (default: True)"
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="Skip checksum verification"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be downloaded without actually downloading"
    )
    args = parser.parse_args()
    
    verify = not args.no_verify
    source = args.source
    
    # Load manifest
    manifest = load_manifest()
    items = manifest.get('items', [])
    
    if not items:
        print("Manifest is empty - no media files to hydrate.")
        return

    fence("Hydrating Media Files")
    print(f"Course: {COURSE_ROOT}")
    print(f"Source: {source}")
    print(f"Items: {len(items)}")
    if args.dry_run:
        print("DRY RUN MODE")
    print()

    # Process each item
    stats = {'skipped': 0, 'downloaded': 0, 'failed': 0}

    for item in items:
        result = hydrate_file(item, source, verify=verify, dry_run=args.dry_run)
        stats[result] += 1

    # Summary
    fence("Summary")
    print(f"{SUCCESS} Downloaded: {stats['downloaded']}, Skipped: {stats['skipped']}, Failed: {stats['failed']}")
    
    if stats['failed'] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
