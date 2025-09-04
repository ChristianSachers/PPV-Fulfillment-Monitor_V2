"""
Data validation utilities for file processing and schema validation.

This module provides a unified interface to validation functionality
that has been split across multiple focused modules for maintainability.
"""

# Import all data types for backward compatibility
from .data_types import (
    ValidationResult,
    ConflictResult,
    SchemaValidationResult,
    DataPreview
)

# Import all validation functions from their respective modules
from .structure_validation import validate_data_structure
from .conflict_detection import detect_data_conflicts
from .schema_validation import validate_csv_schema
from .data_preview import get_data_preview

# Re-export everything for backward compatibility
__all__ = [
    'ValidationResult',
    'ConflictResult', 
    'SchemaValidationResult',
    'DataPreview',
    'validate_data_structure',
    'detect_data_conflicts',
    'validate_csv_schema',
    'get_data_preview'
]