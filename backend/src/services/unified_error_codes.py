"""
Unified Error Code System for Phase 1.1 and Phase 1.2
Provides a centralized error code management system that maintains 
backward compatibility with Phase 1.1 while adding Phase 1.2 specific codes.
"""
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Union


class ErrorCodeCategory(Enum):
    """Error code categories for classification."""
    VALIDATION = "VALIDATION"
    BUSINESS_RULE = "BUSINESS_RULE"
    DATA_INTEGRITY = "DATA_INTEGRITY"
    RELATIONSHIP = "RELATIONSHIP"


class ErrorCodePriority(Enum):
    """Error code priority levels."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


@dataclass
class ErrorCodeInfo:
    """Comprehensive error code information."""
    code: str
    message: str
    category: ErrorCodeCategory
    priority: ErrorCodePriority
    phase_compatibility: str  # '1.1', '1.2', 'both'
    description: Optional[str] = None
    suggested_action: Optional[str] = None

    def __post_init__(self):
        """Validate phase compatibility."""
        valid_phases = ['1.1', '1.2', 'both']
        if self.phase_compatibility not in valid_phases:
            raise ValueError(f"Invalid phase compatibility: {self.phase_compatibility}")


class UnifiedErrorCodes:
    """Unified error codes combining Phase 1.1 and Phase 1.2."""
    
    # Phase 1.1 Compatible Error Codes (Reused from existing system)
    VAL_010 = "UUID not found in production"
    VAL_015 = "Invalid hierarchical structure"
    VAL_020 = "New entry business rule violation"
    
    # Phase 1.2 Specific Business Rule Error Codes
    BIZ_101 = "Deal name modification not allowed"
    BIZ_102 = "Impression decrease detected"
    BIZ_103 = "Date modification flagged"
    BIZ_104 = "Cross-file relationship failure"
    BIZ_105 = "Combined upload incomplete"
    BIZ_106 = "Campaign/Deal ID conflict"


# Error code metadata registry
_ERROR_CODE_REGISTRY: Dict[str, ErrorCodeInfo] = {
    # Phase 1.1 Compatible Codes
    'VAL_010': ErrorCodeInfo(
        code='VAL_010',
        message=UnifiedErrorCodes.VAL_010,
        category=ErrorCodeCategory.VALIDATION,
        priority=ErrorCodePriority.HIGH,
        phase_compatibility='both',
        description='UUID referenced in staging data does not exist in production database',
        suggested_action='Verify UUID exists in production or remove invalid reference'
    ),
    'VAL_015': ErrorCodeInfo(
        code='VAL_015',
        message=UnifiedErrorCodes.VAL_015,
        category=ErrorCodeCategory.DATA_INTEGRITY,
        priority=ErrorCodePriority.MEDIUM,
        phase_compatibility='both',
        description='Data structure does not follow expected hierarchical relationships',
        suggested_action='Review data structure and ensure proper parent-child relationships'
    ),
    'VAL_020': ErrorCodeInfo(
        code='VAL_020',
        message=UnifiedErrorCodes.VAL_020,
        category=ErrorCodeCategory.BUSINESS_RULE,
        priority=ErrorCodePriority.HIGH,
        phase_compatibility='both',
        description='New entry violates established business rules',
        suggested_action='Review business rules and ensure data complies with requirements'
    ),
    
    # Phase 1.2 Specific Business Rule Codes
    'BIZ_101': ErrorCodeInfo(
        code='BIZ_101',
        message=UnifiedErrorCodes.BIZ_101,
        category=ErrorCodeCategory.BUSINESS_RULE,
        priority=ErrorCodePriority.CRITICAL,
        phase_compatibility='1.2',
        description='Deal name cannot be modified in Phase 1.2 strict mode',
        suggested_action='Revert deal name to original value or request approval for modification'
    ),
    'BIZ_102': ErrorCodeInfo(
        code='BIZ_102',
        message=UnifiedErrorCodes.BIZ_102,
        category=ErrorCodeCategory.BUSINESS_RULE,
        priority=ErrorCodePriority.HIGH,
        phase_compatibility='1.2',
        description='Impression goal decreased from previous value, requires review',
        suggested_action='Verify impression decrease is intentional or correct the value'
    ),
    'BIZ_103': ErrorCodeInfo(
        code='BIZ_103',
        message=UnifiedErrorCodes.BIZ_103,
        category=ErrorCodeCategory.BUSINESS_RULE,
        priority=ErrorCodePriority.MEDIUM,
        phase_compatibility='1.2',
        description='Date modification detected that may affect campaign integrity',
        suggested_action='Review date changes and ensure they do not conflict with existing schedules'
    ),
    'BIZ_104': ErrorCodeInfo(
        code='BIZ_104',
        message=UnifiedErrorCodes.BIZ_104,
        category=ErrorCodeCategory.RELATIONSHIP,
        priority=ErrorCodePriority.CRITICAL,
        phase_compatibility='1.2',
        description='Cross-file relationship validation failed between campaign and reporting data',
        suggested_action='Ensure all campaign IDs in reporting data have corresponding campaign entries'
    ),
    'BIZ_105': ErrorCodeInfo(
        code='BIZ_105',
        message=UnifiedErrorCodes.BIZ_105,
        category=ErrorCodeCategory.VALIDATION,
        priority=ErrorCodePriority.CRITICAL,
        phase_compatibility='1.2',
        description='Combined upload missing required file pairs (campaign + reporting)',
        suggested_action='Upload both campaign and reporting files together'
    ),
    'BIZ_106': ErrorCodeInfo(
        code='BIZ_106',
        message=UnifiedErrorCodes.BIZ_106,
        category=ErrorCodeCategory.DATA_INTEGRITY,
        priority=ErrorCodePriority.HIGH,
        phase_compatibility='1.2',
        description='Campaign ID conflicts detected between different upload sources',
        suggested_action='Resolve ID conflicts by ensuring unique campaign identifiers'
    )
}


def get_error_info(error_code: str) -> Optional[ErrorCodeInfo]:
    """
    Get comprehensive information for an error code.
    
    Args:
        error_code: The error code to look up
        
    Returns:
        ErrorCodeInfo object or None if code not found
    """
    if not error_code or not isinstance(error_code, str):
        return None
    
    return _ERROR_CODE_REGISTRY.get(error_code)


def is_phase_11_compatible(error_code: str) -> bool:
    """
    Check if error code is compatible with Phase 1.1.
    
    Args:
        error_code: The error code to check
        
    Returns:
        True if compatible with Phase 1.1
    """
    info = get_error_info(error_code)
    if not info:
        return False
    
    return info.phase_compatibility in ['1.1', 'both']


def is_phase_12_specific(error_code: str) -> bool:
    """
    Check if error code is specific to Phase 1.2.
    
    Args:
        error_code: The error code to check
        
    Returns:
        True if specific to Phase 1.2 only
    """
    info = get_error_info(error_code)
    if not info:
        return False
    
    return info.phase_compatibility == '1.2'


def get_errors_by_category(category: ErrorCodeCategory) -> List[str]:
    """
    Get all error codes in a specific category.
    
    Args:
        category: The error category to filter by
        
    Returns:
        List of error codes in the category
    """
    return [
        code for code, info in _ERROR_CODE_REGISTRY.items()
        if info.category == category
    ]


def get_errors_by_phase_compatibility(phase: str) -> List[str]:
    """
    Get all error codes compatible with a specific phase.
    
    Args:
        phase: The phase to filter by ('1.1', '1.2', 'both')
        
    Returns:
        List of error codes compatible with the phase
    """
    if phase == '1.1':
        return [
            code for code, info in _ERROR_CODE_REGISTRY.items()
            if info.phase_compatibility in ['1.1', 'both']
        ]
    elif phase == '1.2':
        return [
            code for code, info in _ERROR_CODE_REGISTRY.items()
            if info.phase_compatibility in ['1.2', 'both']
        ]
    elif phase == 'both':
        return [
            code for code, info in _ERROR_CODE_REGISTRY.items()
            if info.phase_compatibility == 'both'
        ]
    else:
        return []


def get_high_priority_errors() -> List[str]:
    """
    Get all error codes with HIGH or CRITICAL priority.
    
    Returns:
        List of high priority error codes
    """
    return [
        code for code, info in _ERROR_CODE_REGISTRY.items()
        if info.priority in [ErrorCodePriority.HIGH, ErrorCodePriority.CRITICAL]
    ]


def get_all_error_codes() -> List[str]:
    """
    Get all available error codes.
    
    Returns:
        List of all error codes
    """
    return list(_ERROR_CODE_REGISTRY.keys())


def validate_error_code_structure() -> Dict[str, bool]:
    """
    Validate the error code system structure.
    
    Returns:
        Dictionary with validation results
    """
    results = {
        'has_phase_11_codes': False,
        'has_phase_12_codes': False,
        'all_codes_have_info': True,
        'categories_complete': True,
        'priorities_assigned': True
    }
    
    # Check for Phase 1.1 codes
    phase_11_codes = get_errors_by_phase_compatibility('1.1')
    results['has_phase_11_codes'] = len(phase_11_codes) >= 3
    
    # Check for Phase 1.2 codes
    phase_12_codes = [code for code in _ERROR_CODE_REGISTRY.keys() if code.startswith('BIZ_')]
    results['has_phase_12_codes'] = len(phase_12_codes) >= 6
    
    # Validate all codes have complete information
    for code, info in _ERROR_CODE_REGISTRY.items():
        if not info.message or not info.category or not info.priority:
            results['all_codes_have_info'] = False
            break
    
    return results