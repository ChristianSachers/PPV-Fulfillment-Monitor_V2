"""
Tests for priority-based business rule framework - TDD RED phase
These tests MUST fail initially since the business rule framework doesn't exist yet.

This test suite validates:
1. BusinessRulePriority enum with correct priority ordering
2. Business rule execution framework with priority handling
3. Rule violation detection and reporting
4. Integration with unified error code system
5. Phase 1.2 specific business rule enforcement

All tests follow TDD principles and will fail until framework is implemented.
"""
import pytest
from enum import Enum
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

# Import priority-based business rule framework (doesn't exist yet - will cause ImportError in RED phase)
try:
    from src.services.priority_business_rules import (
        BusinessRulePriority,
        BusinessRuleResult,
        BusinessRuleViolation,
        BusinessRuleEngine,
        RuleExecutionContext,
        apply_business_rules,
        get_rule_by_priority,
        validate_combined_upload,
        detect_impression_decrease,
        check_deal_name_modification,
        validate_cross_file_relationships
    )
    BUSINESS_RULES_EXIST = True
except ImportError:
    BUSINESS_RULES_EXIST = False


@pytest.mark.skipif(not BUSINESS_RULES_EXIST, reason="Business rule framework not implemented yet - TDD RED phase")
class TestBusinessRulePriority:
    """Test cases for business rule priority system."""

    def test_business_rule_priority_enum_exists(self):
        """Test BusinessRulePriority enum exists with correct values."""
        assert isinstance(BusinessRulePriority, type)
        assert issubclass(BusinessRulePriority, Enum)
        
        # Verify all required priorities exist in correct order (lower number = higher priority)
        expected_priorities = [
            'COMBINED_UPLOAD_ENFORCEMENT',      # Priority 1 - Highest
            'UUID_ORPHANING_DETECTION',         # Priority 2
            'CROSS_FILE_RELATIONSHIP_CONSISTENCY', # Priority 3
            'IMPRESSION_DECREASE_DETECTION',    # Priority 4
            'DEAL_NAME_EXACT_MATCHING',        # Priority 5
            'DATE_CHANGE_INCONSISTENCY',       # Priority 6
            'HIERARCHICAL_NAME_STRUCTURE',     # Priority 7
            'MUTUAL_EXCLUSION_VIOLATIONS',     # Priority 8
            'NEW_ENTRY_BUSINESS_RULES'         # Priority 9 - Lowest
        ]
        
        for priority in expected_priorities:
            assert hasattr(BusinessRulePriority, priority), f"Priority {priority} should exist"

    def test_business_rule_priority_ordering(self):
        """Test business rule priorities have correct numeric ordering."""
        # Priority 1 should be highest (most critical)
        assert BusinessRulePriority.COMBINED_UPLOAD_ENFORCEMENT.value == 1
        assert BusinessRulePriority.UUID_ORPHANING_DETECTION.value == 2
        assert BusinessRulePriority.CROSS_FILE_RELATIONSHIP_CONSISTENCY.value == 3
        assert BusinessRulePriority.IMPRESSION_DECREASE_DETECTION.value == 4
        assert BusinessRulePriority.DEAL_NAME_EXACT_MATCHING.value == 5
        assert BusinessRulePriority.DATE_CHANGE_INCONSISTENCY.value == 6
        assert BusinessRulePriority.HIERARCHICAL_NAME_STRUCTURE.value == 7
        assert BusinessRulePriority.MUTUAL_EXCLUSION_VIOLATIONS.value == 8
        # Priority 9 should be lowest
        assert BusinessRulePriority.NEW_ENTRY_BUSINESS_RULES.value == 9

    def test_priority_comparison(self):
        """Test business rule priorities can be compared correctly."""
        # Higher priority rules should be less than lower priority rules
        assert BusinessRulePriority.COMBINED_UPLOAD_ENFORCEMENT < BusinessRulePriority.UUID_ORPHANING_DETECTION
        assert BusinessRulePriority.IMPRESSION_DECREASE_DETECTION < BusinessRulePriority.NEW_ENTRY_BUSINESS_RULES
        assert BusinessRulePriority.CROSS_FILE_RELATIONSHIP_CONSISTENCY < BusinessRulePriority.DATE_CHANGE_INCONSISTENCY


@pytest.mark.skipif(not BUSINESS_RULES_EXIST, reason="Business rule framework not implemented yet - TDD RED phase")
class TestBusinessRuleResult:
    """Test cases for business rule result structures."""

    def test_business_rule_violation_creation(self):
        """Test BusinessRuleViolation dataclass creation."""
        violation = BusinessRuleViolation(
            rule_priority=BusinessRulePriority.DEAL_NAME_EXACT_MATCHING,
            error_code='BIZ_101',
            message='Deal name modification not allowed',
            severity='CRITICAL',
            affected_records=['campaign_123'],
            context={'original_name': 'Campaign A', 'new_name': 'Campaign B'}
        )
        
        assert violation.rule_priority == BusinessRulePriority.DEAL_NAME_EXACT_MATCHING
        assert violation.error_code == 'BIZ_101'
        assert violation.message == 'Deal name modification not allowed'
        assert violation.severity == 'CRITICAL'
        assert violation.affected_records == ['campaign_123']
        assert violation.context['original_name'] == 'Campaign A'

    def test_business_rule_result_creation(self):
        """Test BusinessRuleResult dataclass creation."""
        violation = BusinessRuleViolation(
            rule_priority=BusinessRulePriority.IMPRESSION_DECREASE_DETECTION,
            error_code='BIZ_102',
            message='Impression decrease detected',
            severity='HIGH',
            affected_records=['campaign_456']
        )
        
        result = BusinessRuleResult(
            success=False,
            violations=[violation],
            processed_records=100,
            flagged_records=1,
            execution_time_ms=150.5
        )
        
        assert result.success is False
        assert len(result.violations) == 1
        assert result.violations[0].error_code == 'BIZ_102'
        assert result.processed_records == 100
        assert result.flagged_records == 1
        assert result.execution_time_ms == 150.5

    def test_business_rule_result_with_no_violations(self):
        """Test BusinessRuleResult with successful execution."""
        result = BusinessRuleResult(
            success=True,
            violations=[],
            processed_records=50,
            flagged_records=0,
            execution_time_ms=75.2
        )
        
        assert result.success is True
        assert len(result.violations) == 0
        assert result.flagged_records == 0


@pytest.mark.skipif(not BUSINESS_RULES_EXIST, reason="Business rule framework not implemented yet - TDD RED phase")
class TestRuleExecutionContext:
    """Test cases for rule execution context."""

    def test_rule_execution_context_creation(self):
        """Test RuleExecutionContext dataclass creation."""
        context = RuleExecutionContext(
            phase='1.2',
            upload_type='combined',
            campaign_data=[{'id': 'camp_1', 'name': 'Campaign 1'}],
            reporting_data=[{'id': 'rep_1', 'deal_id': 'camp_1'}],
            existing_production_data={'campaigns': [], 'reporting': []},
            processing_batch_id=str(uuid4())
        )
        
        assert context.phase == '1.2'
        assert context.upload_type == 'combined'
        assert len(context.campaign_data) == 1
        assert len(context.reporting_data) == 1
        assert context.existing_production_data is not None
        assert context.processing_batch_id is not None

    def test_rule_execution_context_optional_fields(self):
        """Test RuleExecutionContext with optional fields."""
        context = RuleExecutionContext(
            phase='1.1',
            upload_type='single',
            campaign_data=[],
            reporting_data=[],
            processing_batch_id=str(uuid4()),
            user_id='user_123',
            request_timestamp=datetime.now(),
            validation_mode='strict'
        )
        
        assert context.user_id == 'user_123'
        assert context.request_timestamp is not None
        assert context.validation_mode == 'strict'


@pytest.mark.skipif(not BUSINESS_RULES_EXIST, reason="Business rule framework not implemented yet - TDD RED phase")
class TestBusinessRuleEngine:
    """Test cases for business rule engine."""

    def test_business_rule_engine_creation(self):
        """Test BusinessRuleEngine can be created."""
        engine = BusinessRuleEngine()
        assert engine is not None
        
        # Should have method to register rules
        assert hasattr(engine, 'register_rule'), "Engine should have register_rule method"
        assert hasattr(engine, 'execute_rules'), "Engine should have execute_rules method"
        assert hasattr(engine, 'get_rules_by_priority'), "Engine should have get_rules_by_priority method"

    def test_business_rule_engine_rule_registration(self):
        """Test business rule engine can register rules."""
        engine = BusinessRuleEngine()
        
        # Should be able to register a rule with priority
        rule_function = lambda context: BusinessRuleResult(success=True, violations=[], processed_records=0, flagged_records=0)
        
        engine.register_rule(
            priority=BusinessRulePriority.COMBINED_UPLOAD_ENFORCEMENT,
            rule_function=rule_function,
            description='Test combined upload rule'
        )
        
        # Should be able to get registered rules
        rules = engine.get_rules_by_priority()
        assert len(rules) >= 1
        
        # Rules should be ordered by priority
        for i in range(len(rules) - 1):
            assert rules[i]['priority'].value <= rules[i + 1]['priority'].value

    def test_business_rule_engine_execution(self):
        """Test business rule engine can execute rules."""
        engine = BusinessRuleEngine()
        
        # Register a test rule
        def test_rule(context):
            return BusinessRuleResult(
                success=True,
                violations=[],
                processed_records=len(context.campaign_data),
                flagged_records=0,
                execution_time_ms=10.0
            )
        
        engine.register_rule(
            priority=BusinessRulePriority.NEW_ENTRY_BUSINESS_RULES,
            rule_function=test_rule,
            description='Test rule'
        )
        
        # Create execution context
        context = RuleExecutionContext(
            phase='1.2',
            upload_type='single',
            campaign_data=[{'id': 'test_campaign'}],
            reporting_data=[],
            processing_batch_id=str(uuid4())
        )
        
        # Execute rules
        results = engine.execute_rules(context)
        assert isinstance(results, list)
        assert len(results) >= 1
        assert all(isinstance(result, BusinessRuleResult) for result in results)


@pytest.mark.skipif(not BUSINESS_RULES_EXIST, reason="Business rule framework not implemented yet - TDD RED phase")
class TestSpecificBusinessRules:
    """Test cases for specific business rule implementations."""

    def test_validate_combined_upload_function(self):
        """Test combined upload validation function."""
        # Should validate that both campaign and reporting data are present
        context_valid = RuleExecutionContext(
            phase='1.2',
            upload_type='combined',
            campaign_data=[{'id': 'camp_1'}],
            reporting_data=[{'id': 'rep_1'}],
            processing_batch_id=str(uuid4())
        )
        
        result = validate_combined_upload(context_valid)
        assert isinstance(result, BusinessRuleResult)
        assert result.success is True
        
        # Should fail when reporting data is missing
        context_invalid = RuleExecutionContext(
            phase='1.2',
            upload_type='combined',
            campaign_data=[{'id': 'camp_1'}],
            reporting_data=[],
            processing_batch_id=str(uuid4())
        )
        
        result_invalid = validate_combined_upload(context_invalid)
        assert result_invalid.success is False
        assert len(result_invalid.violations) > 0
        assert result_invalid.violations[0].error_code == 'BIZ_105'

    def test_detect_impression_decrease_function(self):
        """Test impression decrease detection function."""
        context = RuleExecutionContext(
            phase='1.2',
            upload_type='single',
            campaign_data=[
                {'deal_campaign_id': 'camp_1', 'impression_goal': 50000}
            ],
            reporting_data=[],
            existing_production_data={
                'campaigns': [
                    {'deal_campaign_id': 'camp_1', 'impression_goal': 100000}
                ]
            },
            processing_batch_id=str(uuid4())
        )
        
        result = detect_impression_decrease(context)
        assert isinstance(result, BusinessRuleResult)
        
        # Should detect decrease from 100k to 50k
        assert result.success is False
        assert len(result.violations) > 0
        assert result.violations[0].error_code == 'BIZ_102'

    def test_check_deal_name_modification_function(self):
        """Test deal name modification check function."""
        context = RuleExecutionContext(
            phase='1.2',
            upload_type='single',
            campaign_data=[
                {'deal_campaign_id': 'camp_1', 'deal_campaign_name': 'New Campaign Name'}
            ],
            reporting_data=[],
            existing_production_data={
                'campaigns': [
                    {'deal_campaign_id': 'camp_1', 'deal_campaign_name': 'Original Campaign Name'}
                ]
            },
            processing_batch_id=str(uuid4())
        )
        
        result = check_deal_name_modification(context)
        assert isinstance(result, BusinessRuleResult)
        
        # Should detect name modification
        assert result.success is False
        assert len(result.violations) > 0
        assert result.violations[0].error_code == 'BIZ_101'

    def test_validate_cross_file_relationships_function(self):
        """Test cross-file relationship validation function."""
        # Valid relationship - reporting data references existing campaign
        context_valid = RuleExecutionContext(
            phase='1.2',
            upload_type='combined',
            campaign_data=[
                {'deal_campaign_id': 'camp_1', 'deal_campaign_name': 'Campaign 1'}
            ],
            reporting_data=[
                {'deal_id': 'camp_1', 'total_impressions': 1000}
            ],
            processing_batch_id=str(uuid4())
        )
        
        result_valid = validate_cross_file_relationships(context_valid)
        assert result_valid.success is True
        
        # Invalid relationship - reporting data references non-existent campaign
        context_invalid = RuleExecutionContext(
            phase='1.2',
            upload_type='combined',
            campaign_data=[
                {'deal_campaign_id': 'camp_1', 'deal_campaign_name': 'Campaign 1'}
            ],
            reporting_data=[
                {'deal_id': 'camp_2', 'total_impressions': 1000}  # References non-existent camp_2
            ],
            processing_batch_id=str(uuid4())
        )
        
        result_invalid = validate_cross_file_relationships(context_invalid)
        assert result_invalid.success is False
        assert len(result_invalid.violations) > 0
        assert result_invalid.violations[0].error_code == 'BIZ_104'


@pytest.mark.skipif(not BUSINESS_RULES_EXIST, reason="Business rule framework not implemented yet - TDD RED phase")
class TestBusinessRuleIntegration:
    """Test cases for business rule framework integration."""

    def test_apply_business_rules_function(self):
        """Test main apply_business_rules function."""
        context = RuleExecutionContext(
            phase='1.2',
            upload_type='combined',
            campaign_data=[{'deal_campaign_id': 'camp_1'}],
            reporting_data=[{'deal_id': 'camp_1'}],
            processing_batch_id=str(uuid4())
        )
        
        results = apply_business_rules(context)
        assert isinstance(results, BusinessRuleResult)
        
        # Should have executed multiple rules
        assert results.processed_records >= 0
        assert results.execution_time_ms > 0

    def test_get_rule_by_priority_function(self):
        """Test getting rules by priority."""
        # Should be able to get rules by specific priority
        rules = get_rule_by_priority(BusinessRulePriority.COMBINED_UPLOAD_ENFORCEMENT)
        assert isinstance(rules, list)
        
        # Should be able to get all rules ordered by priority
        all_rules = get_rule_by_priority()
        assert isinstance(all_rules, list)
        
        # Rules should be ordered by priority (highest priority first)
        for i in range(len(all_rules) - 1):
            assert all_rules[i]['priority'].value <= all_rules[i + 1]['priority'].value

    def test_business_rule_error_code_integration(self):
        """Test business rules integrate with unified error code system."""
        from src.services.unified_error_codes import get_error_info
        
        # Business rule violations should use unified error codes
        violation = BusinessRuleViolation(
            rule_priority=BusinessRulePriority.DEAL_NAME_EXACT_MATCHING,
            error_code='BIZ_101',
            message='Deal name modification not allowed',
            severity='CRITICAL',
            affected_records=['camp_1']
        )
        
        # Error code should exist in unified system
        error_info = get_error_info(violation.error_code)
        assert error_info is not None
        assert error_info.code == 'BIZ_101'
        assert error_info.phase_compatibility == '1.2'


# Tests for when business rule framework doesn't exist (RED phase verification)
@pytest.mark.skipif(BUSINESS_RULES_EXIST, reason="Business rules exist - not in RED phase")
class TestPriorityBusinessRulesRedPhase:
    """Verify we're in TDD RED phase - business rule framework should not exist yet."""

    def test_business_rule_priority_not_implemented(self):
        """Verify BusinessRulePriority enum doesn't exist yet."""
        with pytest.raises(ImportError):
            from src.services.priority_business_rules import BusinessRulePriority

    def test_business_rule_engine_not_implemented(self):
        """Verify BusinessRuleEngine class doesn't exist yet."""
        with pytest.raises(ImportError):
            from src.services.priority_business_rules import BusinessRuleEngine

    def test_business_rule_functions_not_implemented(self):
        """Verify specific business rule functions don't exist yet."""
        with pytest.raises(ImportError):
            from src.services.priority_business_rules import (
                validate_combined_upload,
                detect_impression_decrease,
                check_deal_name_modification
            )

    def test_apply_business_rules_not_implemented(self):
        """Verify main apply_business_rules function doesn't exist yet."""
        with pytest.raises(ImportError):
            from src.services.priority_business_rules import apply_business_rules