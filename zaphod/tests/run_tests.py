#!/usr/bin/env python3
# zaphod/tests/run_tests.py
"""
Test runner script for Zaphod tests

Usage:
    # From zaphod directory:
    python -m pytest tests/ -v
    
    # Or run this script:
    python tests/run_tests.py
    
    # With coverage:
    python tests/run_tests.py --cov
"""
import sys
import os
from pathlib import Path

# Ensure zaphod package is importable
TESTS_DIR = Path(__file__).parent
ZAPHOD_DIR = TESTS_DIR.parent
PROJECT_ROOT = ZAPHOD_DIR.parent

# Add project root to path so 'zaphod' package is importable
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main():
    """Run all tests with optional coverage"""
    import pytest
    
    args = [
        str(TESTS_DIR),
        '-v',  # Verbose
        '--tb=short',  # Short traceback
        '-W', 'ignore::DeprecationWarning',  # Ignore deprecation warnings
    ]
    
    # Check for coverage flag
    if '--cov' in sys.argv:
        args.extend([
            '--cov=zaphod',  # Coverage for zaphod package
            '--cov-report=term-missing',  # Show missing lines
            '--cov-report=html',  # HTML report
        ])
        sys.argv.remove('--cov')
    
    # Add any additional command-line arguments
    args.extend(sys.argv[1:])
    
    return pytest.main(args)


if __name__ == '__main__':
    sys.exit(main())
