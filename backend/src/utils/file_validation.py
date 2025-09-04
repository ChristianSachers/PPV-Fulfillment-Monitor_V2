"""
File validation utilities for upload handling
"""
import os.path
import re
from typing import List


def validate_file_type(filename: str, allowed_types: List[str]) -> bool:
    """Validate if file type is allowed"""
    if not filename:
        return False
    
    extension = get_file_extension(filename)
    return extension.lower() in [t.lower() for t in allowed_types]


def validate_file_size(file_size: int, max_size_mb: int) -> bool:
    """Validate if file size is within allowed limit"""
    if file_size <= 0:
        return False
    
    max_bytes = max_size_mb * 1024 * 1024
    return file_size <= max_bytes


def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing dangerous characters"""
    # Remove path traversal and dangerous characters
    sanitized = re.sub(r'[<>|:*?"\\./]|\.\.', '', filename)
    
    # Truncate to 255 characters
    return sanitized[:255]


def get_file_extension(filename: str) -> str:
    """Extract file extension without dot"""
    if not filename or '.' not in filename:
        return ""
    
    extension = os.path.splitext(filename)[1][1:]  # Remove leading dot
    return extension