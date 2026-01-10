# tests/run_tests.py
"""
Test runner script with coverage reporting
"""
import sys
import pytest


def main():
    """Run all tests with coverage"""
    args = [
        'tests/',
        '-v',  # Verbose
        '--tb=short',  # Short traceback
        '--cov=.',  # Coverage for all modules
        '--cov-report=term-missing',  # Show missing lines
        '--cov-report=html',  # HTML report
        '-W', 'ignore::DeprecationWarning',  # Ignore deprecation warnings
    ]
    
    # Add any command-line arguments
    args.extend(sys.argv[1:])
    
    return pytest.main(args)


if __name__ == '__main__':
    sys.exit(main())