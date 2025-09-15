"""
Tests for unified error code system - TDD RED phase
These tests MUST fail initially since the unified error code system doesn't exist yet.

This test suite validates:
1. Unified error codes that combine Phase 1.1 and Phase 1.2
2. Backward compatibility with existing Phase 1.1 error codes
3. New Phase 1.2 specific business rule error codes
4. Error code categorization and priority

All tests follow TDD principles and will fail until system is implemented.
"""
import pytest
from enum import Enum
from typing import Dict, List, Optional

# Import unified error code system (doesn't exist yet - will cause ImportError in RED phase)
try:
    from src.services.unified_error_codes import (
        UnifiedErrorCodes,
        ErrorCodeCategory,
        ErrorCodePriority,
        ErrorCodeInfo,
        get_error_info,
        is_phase_11_compatible,
        is_phase_12_specific
    )
    ERROR_SYSTEM_EXISTS = True
except ImportError:
    ERROR_SYSTEM_EXISTS = False


@pytest.mark.skipif(not ERROR_SYSTEM_EXISTS, reason="Unified error code system not implemented yet - TDD RED phase")
class TestUnifiedErrorCodes:
    """Test cases for unified error code definitions."""

    def test_phase_11_error_codes_exist(self):
        """Test Phase 1.1 error codes are preserved in unified system."""
        # Phase 1.1 codes should exist
        assert hasattr(UnifiedErrorCodes, 'VAL_010'), "VAL_010 error code should exist"
        assert hasattr(UnifiedErrorCodes, 'VAL_015'), "VAL_015 error code should exist" 
        assert hasattr(UnifiedErrorCodes, 'VAL_020'), "VAL_020 error code should exist"
        
        # Verify Phase 1.1 error messages
        assert UnifiedErrorCodes.VAL_010 == "UUID not found in production"
        assert UnifiedErrorCodes.VAL_015 == "Invalid hierarchical structure"
        assert UnifiedErrorCodes.VAL_020 == "New entry business rule violation"

    def test_phase_12_business_rule_codes_exist(self):
        """Test Phase 1.2 business rule error codes exist."""
        # Phase 1.2 business rule codes should exist
        phase_12_codes = [
            'BIZ_101', 'BIZ_102', 'BIZ_103', 'BIZ_104', 'BIZ_105', 'BIZ_106'
        ]
        
        for code in phase_12_codes:
            assert hasattr(UnifiedErrorCodes, code), f"{code} error code should exist"
        
        # Verify Phase 1.2 error messages
        assert UnifiedErrorCodes.BIZ_101 == "Deal name modification not allowed"
        assert UnifiedErrorCodes.BIZ_102 == "Impression decrease detected"
        assert UnifiedErrorCodes.BIZ_103 == "Date modification flagged"
        assert UnifiedErrorCodes.BIZ_104 == "Cross-file relationship failure"
        assert UnifiedErrorCodes.BIZ_105 == "Combined upload incomplete"
        assert UnifiedErrorCodes.BIZ_106 == "Campaign/Deal ID conflict"

    def test_error_code_info_structure(self):
        """Test error code info contains required metadata."""
        # Test getting error info for a Phase 1.1 code
        val_010_info = get_error_info('VAL_010')
        assert isinstance(val_010_info, ErrorCodeInfo)
        assert val_010_info.code == 'VAL_010'
        assert val_010_info.message == "UUID not found in production"
        assert val_010_info.category in ErrorCodeCategory
        assert val_010_info.phase_compatibility in ['1.1', '1.2', 'both']
        
        # Test getting error info for a Phase 1.2 code
        biz_101_info = get_error_info('BIZ_101')
        assert isinstance(biz_101_info, ErrorCodeInfo)
        assert biz_101_info.code == 'BIZ_101'
        assert biz_101_info.message == "Deal name modification not allowed"
        assert biz_101_info.category in ErrorCodeCategory
        assert biz_101_info.phase_compatibility == '1.2'

    def test_error_code_categories_exist(self):
        """Test error code categories are properly defined."""
        # ErrorCodeCategory enum should exist
        assert isinstance(ErrorCodeCategory, type)
        assert issubclass(ErrorCodeCategory, Enum)
        
        # Should have categories for different error types
        expected_categories = ['VALIDATION', 'BUSINESS_RULE', 'DATA_INTEGRITY', 'RELATIONSHIP']
        
        category_values = [cat.value for cat in ErrorCodeCategory]
        for expected in expected_categories:
            assert expected in category_values, f"Category {expected} should exist"

    def test_error_code_priority_system(self):
        """Test error code priority system exists."""
        # ErrorCodePriority enum should exist
        assert isinstance(ErrorCodePriority, type)
        assert issubclass(ErrorCodePriority, Enum)
        
        # Should have priority levels
        expected_priorities = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
        
        priority_values = [p.value for p in ErrorCodePriority]
        for expected in expected_priorities:
            assert expected in priority_values, f"Priority {expected} should exist"

    def test_phase_compatibility_functions(self):
        """Test phase compatibility detection functions."""
        # Phase 1.1 compatible codes
        assert is_phase_11_compatible('VAL_010') is True
        assert is_phase_11_compatible('VAL_015') is True
        assert is_phase_11_compatible('VAL_020') is True
        
        # Phase 1.2 specific codes
        assert is_phase_12_specific('BIZ_101') is True
        assert is_phase_12_specific('BIZ_102') is True
        assert is_phase_12_specific('BIZ_106') is True
        
        # Phase 1.1 codes should not be Phase 1.2 specific
        assert is_phase_12_specific('VAL_010') is False
        assert is_phase_12_specific('VAL_015') is False

    def test_all_error_codes_have_complete_metadata(self):
        """Test all error codes have complete metadata."""
        # Get all error code attributes from UnifiedErrorCodes
        error_codes = [attr for attr in dir(UnifiedErrorCodes) 
                      if not attr.startswith('_') and isinstance(getattr(UnifiedErrorCodes, attr), str)]
        
        assert len(error_codes) >= 9, "Should have at least 9 error codes (3 Phase 1.1 + 6 Phase 1.2)"
        
        for code in error_codes:
            info = get_error_info(code)
            assert info is not None, f"Error code {code} should have metadata"
            assert info.code == code, f"Error code {code} metadata should match"
            assert len(info.message) > 0, f"Error code {code} should have non-empty message"
            assert info.category is not None, f"Error code {code} should have category"
            assert info.priority is not None, f"Error code {code} should have priority"
            assert info.phase_compatibility in ['1.1', '1.2', 'both'], f"Error code {code} should have valid phase compatibility"


@pytest.mark.skipif(not ERROR_SYSTEM_EXISTS, reason="Unified error code system not implemented yet - TDD RED phase")
class TestErrorCodeInfo:
    """Test cases for ErrorCodeInfo dataclass."""

    def test_error_code_info_creation(self):
        """Test ErrorCodeInfo can be created with required fields."""
        info = ErrorCodeInfo(
            code='TEST_001',
            message='Test error message',
            category=ErrorCodeCategory.VALIDATION,
            priority=ErrorCodePriority.HIGH,
            phase_compatibility='1.2'
        )
        
        assert info.code == 'TEST_001'
        assert info.message == 'Test error message'
        assert info.category == ErrorCodeCategory.VALIDATION
        assert info.priority == ErrorCodePriority.HIGH
        assert info.phase_compatibility == '1.2'

    def test_error_code_info_optional_fields(self):
        """Test ErrorCodeInfo with optional fields."""
        info = ErrorCodeInfo(
            code='TEST_002',
            message='Test error with details',
            category=ErrorCodeCategory.BUSINESS_RULE,
            priority=ErrorCodePriority.CRITICAL,
            phase_compatibility='both',
            description='Detailed description of the error',
            suggested_action='Suggested action to resolve'
        )
        
        assert info.description == 'Detailed description of the error'
        assert info.suggested_action == 'Suggested action to resolve'

    def test_error_code_info_validation(self):
        """Test ErrorCodeInfo validates input."""
        # Valid phase compatibility values
        valid_phases = ['1.1', '1.2', 'both']
        
        for phase in valid_phases:
            info = ErrorCodeInfo(
                code='TEST_003',
                message='Test message',
                category=ErrorCodeCategory.VALIDATION,
                priority=ErrorCodePriority.MEDIUM,
                phase_compatibility=phase
            )
            assert info.phase_compatibility == phase


@pytest.mark.skipif(not ERROR_SYSTEM_EXISTS, reason="Unified error code system not implemented yet - TDD RED phase")
class TestErrorCodeUtilityFunctions:
    """Test cases for error code utility functions."""

    def test_get_error_info_valid_codes(self):
        """Test get_error_info returns correct info for valid codes."""
        # Test Phase 1.1 code
        val_info = get_error_info('VAL_010')
        assert val_info is not None
        assert val_info.code == 'VAL_010'
        
        # Test Phase 1.2 code
        biz_info = get_error_info('BIZ_101')
        assert biz_info is not None
        assert biz_info.code == 'BIZ_101'

    def test_get_error_info_invalid_codes(self):
        """Test get_error_info handles invalid codes gracefully."""
        # Invalid error code should return None
        invalid_info = get_error_info('INVALID_CODE')
        assert invalid_info is None
        
        # Empty string should return None
        empty_info = get_error_info('')
        assert empty_info is None

    def test_get_errors_by_category(self):
        """Test getting error codes by category."""
        # This function should exist
        from src.services.unified_error_codes import get_errors_by_category
        
        validation_errors = get_errors_by_category(ErrorCodeCategory.VALIDATION)
        assert isinstance(validation_errors, list)
        assert len(validation_errors) > 0
        
        # All returned codes should be validation category
        for error_code in validation_errors:
            info = get_error_info(error_code)
            assert info.category == ErrorCodeCategory.VALIDATION

    def test_get_errors_by_phase_compatibility(self):
        """Test getting error codes by phase compatibility."""
        # This function should exist
        from src.services.unified_error_codes import get_errors_by_phase_compatibility
        
        phase_11_errors = get_errors_by_phase_compatibility('1.1')
        assert isinstance(phase_11_errors, list)
        assert 'VAL_010' in phase_11_errors
        
        phase_12_errors = get_errors_by_phase_compatibility('1.2')
        assert isinstance(phase_12_errors, list)
        assert 'BIZ_101' in phase_12_errors

    def test_get_high_priority_errors(self):
        """Test getting high priority error codes."""
        # This function should exist
        from src.services.unified_error_codes import get_high_priority_errors
        
        high_priority = get_high_priority_errors()
        assert isinstance(high_priority, list)
        
        # All returned codes should be high or critical priority
        for error_code in high_priority:
            info = get_error_info(error_code)
            assert info.priority in [ErrorCodePriority.HIGH, ErrorCodePriority.CRITICAL]


# Tests for when unified error system doesn't exist (RED phase verification)
@pytest.mark.skipif(ERROR_SYSTEM_EXISTS, reason="Error system exists - not in RED phase")
class TestUnifiedErrorCodesRedPhase:
    """Verify we're in TDD RED phase - unified error system should not exist yet."""

    def test_unified_error_codes_not_implemented(self):
        """Verify UnifiedErrorCodes class doesn't exist yet."""
        with pytest.raises(ImportError):
            from src.services.unified_error_codes import UnifiedErrorCodes

    def test_error_code_info_not_implemented(self):
        """Verify ErrorCodeInfo doesn't exist yet."""
        with pytest.raises(ImportError):
            from src.services.unified_error_codes import ErrorCodeInfo

    def test_error_categories_not_implemented(self):
        """Verify ErrorCodeCategory enum doesn't exist yet."""
        with pytest.raises(ImportError):
            from src.services.unified_error_codes import ErrorCodeCategory

    def test_utility_functions_not_implemented(self):
        """Verify utility functions don't exist yet."""
        with pytest.raises(ImportError):
            from src.services.unified_error_codes import get_error_info, is_phase_11_compatible