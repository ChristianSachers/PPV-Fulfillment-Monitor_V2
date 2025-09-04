"""
Data types and structures for validation utilities.

This module contains all dataclass definitions used across validation modules.
"""
from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class ValidationResult:
    """Result of data structure validation"""
    is_valid: bool
    errors: List[str]
    missing_columns: List[str]
    extra_columns: List[str]
    type_errors: List[str]


@dataclass
class ConflictResult:
    """Result of data conflict detection"""
    has_conflicts: bool
    conflicting_records: List[dict]
    resolution_suggestions: List[str]
    metadata: dict
    conflict_type: str = None


@dataclass
class SchemaValidationResult:
    """Result of CSV schema validation"""
    is_valid: bool
    errors: List[str]
    row_count: int
    column_names: List[str]
    parsing_errors: List[str]
    dialect_info: dict = None
    metadata: dict = None


@dataclass
class DataPreview:
    """Result of data preview generation"""
    is_valid: bool
    sample_data: List[dict]
    column_types: Dict[str, str]
    statistics: Dict[str, Any]
    errors: List[str]
    file_type: str = None
    column_names: List[str] = None
    total_records: int = 0
    sheet_names: List[str] = None