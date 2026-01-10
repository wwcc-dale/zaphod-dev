# config_utils.py - UPDATED with better errors
"""
Zaphod configuration utilities with improved error handling
"""

import os
import json
from pathlib import Path
from errors import missing_course_id_error, ConfigurationError


def get_course_id(course_dir=None):
    """
    Get course ID from environment or defaults.json
    
    Raises:
        ConfigurationError: If course ID not found anywhere
    """
    # First check environment variable
    course_id = os.environ.get("COURSE_ID")
    if course_id:
        return course_id
    
    # Fall back to defaults.json
    if course_dir is None:
        course_dir = Path.cwd()
    
    config_path = Path(course_dir) / "_course_metadata" / "defaults.json"
    if config_path.exists():
        try:
            with open(config_path) as f:
                config = json.load(f)
                course_id = config.get("course_id")
                if course_id:
                    return course_id
        except json.JSONDecodeError as e:
            raise ConfigurationError(
                message=f"Invalid JSON in {config_path}",
                suggestion="Check JSON syntax - ensure valid formatting",
                context={"file": str(config_path)},
                cause=e
            )
        except Exception as e:
            raise ConfigurationError(
                message=f"Error reading {config_path}",
                context={"file": str(config_path)},
                cause=e
            )
    
    # Not found anywhere - provide helpful error
    raise missing_course_id_error()