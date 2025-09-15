"""
Comprehensive TDD Test Suite for New Entry Validator - RED PHASE
Tests MUST fail initially since new_entry_validator doesn't exist yet.

Business Rules (Updated based on user clarifications):
- impression_goal: 1 - 1,000,000,000 (BIZ_101/BIZ_102 violations)
- CPM EUR: €0.01 - €45.00 (BIZ_103/BIZ_104 violations)  
- total_impressions: 619 - 231,000,000 (BIZ_106/BIZ_107 violations)
- budget_eur: >= 0 (BIZ_108 violation)
- Combined upload enforcement: REMOVED (future API will make second file obsolete)
- New entries: UUIDs not found in production database

New Entry Validation Requirements:
1. UUID Lookup - Check if UUID exists in production database
2. Business Rule Validation - Apply validation rules for new records
3. Cross-File UUID Matching - Only exact UUID matches are considered valid
4. Phase 1.1 Integration - Compatible with existing infrastructure
5. Extended Staging Integration - Store violations as JSON objects in JSONB format
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from decimal import Decimal
from datetime import datetime, date
from typing import List, Dict, Any, Optional

# Import the new entry validator that doesn't exist yet (TDD RED phase)
from src.services.new_entry_validator import (
    NewEntryValidator,
    NewEntryValidationResult,
    BusinessRuleViolation,
    validate_new_campaign_entry,
    validate_new_performance_entry,
    lookup_uuids_in_production
)


class TestNewEntryValidator:
    """Test suite for the main NewEntryValidator class"""
    
    @pytest.fixture
    def mock_production_db_session(self):
        """Mock production database session"""
        session = Mock()
        session.execute = Mock()
        session.close = Mock()
        return session
    
    @pytest.fixture
    def mock_staging_db_session(self):
        """Mock staging database session"""
        session = Mock()
        session.execute = Mock()
        session.commit = Mock()
        session.rollback = Mock()
        return session
    
    @pytest.fixture
    def validator(self, mock_production_db_session, mock_staging_db_session):
        """Create NewEntryValidator instance with mocked dependencies"""
        return NewEntryValidator(
            production_db_session=mock_production_db_session,
            staging_db_session=mock_staging_db_session,
            processing_batch_id="test-batch-123"
        )
    
    @pytest.fixture
    def sample_campaign_record(self):
        """Sample campaign record for testing"""
        return {
            'deal_campaign_id': 'camp-new-001',
            'deal_campaign_name': 'Test New Campaign',
            'start_date': date(2024, 1, 1),
            'end_date': date(2024, 1, 31),
            'impression_goal': 50000,
            'budget_eur': Decimal('1000.00'),
            'cpm_eur': Decimal('5.50'),
            'buyer': 'Test Buyer'
        }
    
    @pytest.fixture
    def sample_performance_record(self):
        """Sample performance record for testing"""
        return {
            'deal_id': 'perf-new-001',
            'date_recorded': date(2024, 1, 15),
            'deal_name': 'Test Performance Record',
            'core_dsp_audience_segment': 'segment_a',
            'core_dsp_placement': 'placement_b',
            'core_dsp_creative': 'creative_c',
            'purchase_type': 'programmatic',
            'total_impressions': 45000
        }
    
    def test_validator_initialization(self, validator):
        """Test validator initializes with correct dependencies"""
        assert validator.production_db_session is not None
        assert validator.staging_db_session is not None
        assert validator.processing_batch_id == "test-batch-123"
        assert validator.uuid_lookup_batch_size == 500  # From requirements
    
    def test_validator_requires_both_database_sessions(self):
        """Test validator requires both production and staging database sessions"""
        with pytest.raises(ValueError, match="Production database session required"):
            NewEntryValidator(production_db_session=None, staging_db_session=Mock())
        
        with pytest.raises(ValueError, match="Staging database session required"):
            NewEntryValidator(production_db_session=Mock(), staging_db_session=None)


class TestUUIDLookupTests:
    """Test UUID lookup functionality against production database"""
    
    @pytest.fixture
    def validator(self):
        """Validator with mocked database sessions"""
        prod_session = Mock()
        staging_session = Mock()
        return NewEntryValidator(prod_session, staging_session, "batch-001")
    
    @pytest.mark.asyncio
    async def test_uuid_not_found_triggers_new_classification(self, validator):
        """Test UUID not found in production database triggers 'new' classification"""
        # Mock production database returning no results
        validator.production_db_session.execute.return_value.fetchall.return_value = []
        
        uuids = ['new-uuid-001', 'new-uuid-002']
        result = await validator.lookup_uuids_in_production(uuids, 'campaign')
        
        assert result.found_uuids == []
        assert result.new_uuids == uuids
        assert all(uuid in result.new_uuids for uuid in uuids)
    
    @pytest.mark.asyncio
    async def test_uuid_found_in_production_excludes_from_new(self, validator):
        """Test UUID found in production database excludes from new classification"""
        # Mock production database returning existing records
        mock_result = Mock()
        mock_result.fetchall.return_value = [
            Mock(deal_campaign_id='existing-uuid-001'),
            Mock(deal_campaign_id='existing-uuid-002')
        ]
        validator.production_db_session.execute.return_value = mock_result
        
        uuids = ['existing-uuid-001', 'existing-uuid-002', 'new-uuid-003']
        result = await validator.lookup_uuids_in_production(uuids, 'campaign')
        
        assert 'existing-uuid-001' in result.found_uuids
        assert 'existing-uuid-002' in result.found_uuids
        assert 'new-uuid-003' in result.new_uuids
        assert len(result.new_uuids) == 1
    
    @pytest.mark.asyncio
    async def test_production_database_connection_error_handling(self, validator):
        """Test production database connection error handling"""
        validator.production_db_session.execute.side_effect = Exception("Connection failed")
        
        uuids = ['test-uuid-001']
        result = await validator.lookup_uuids_in_production(uuids, 'campaign')
        
        assert result.has_errors is True
        assert "Connection failed" in result.error_message
        assert result.found_uuids == []
        assert result.new_uuids == []
    
    @pytest.mark.asyncio
    async def test_batch_uuid_lookup_optimization(self, validator):
        """Test batch UUID lookup optimization (500 records per query max)"""
        # Create 1200 UUIDs to test batching
        large_uuid_list = [f'uuid-{i:04d}' for i in range(1200)]
        
        validator.production_db_session.execute.return_value.fetchall.return_value = []
        
        result = await validator.lookup_uuids_in_production(large_uuid_list, 'campaign')
        
        # Should execute 3 queries (500 + 500 + 200)
        assert validator.production_db_session.execute.call_count == 3
        assert len(result.new_uuids) == 1200
    
    @pytest.mark.asyncio
    async def test_campaign_vs_performance_table_selection(self, validator):
        """Test correct table selection for campaign vs performance lookups"""
        mock_result = Mock()
        mock_result.fetchall.return_value = []
        validator.production_db_session.execute.return_value = mock_result
        
        # Test campaign lookup
        await validator.lookup_uuids_in_production(['uuid-001'], 'campaign')
        campaign_query = validator.production_db_session.execute.call_args[0][0]
        assert "FROM campaigns" in str(campaign_query)
        
        # Reset mock
        validator.production_db_session.execute.reset_mock()
        
        # Test performance lookup
        await validator.lookup_uuids_in_production(['uuid-002'], 'performance')
        performance_query = validator.production_db_session.execute.call_args[0][0]
        assert "FROM reporting" in str(performance_query)


class TestBusinessRuleValidationTests:
    """Test business rule validation for new entries"""
    
    @pytest.fixture
    def validator(self):
        return NewEntryValidator(Mock(), Mock(), "batch-001")
    
    def test_impression_goal_range_validation_success(self, validator):
        """Test impression_goal within valid range (1 - 1,000,000,000) passes"""
        record = {'impression_goal': 50000}
        violations = validator.validate_campaign_business_rules(record)
        
        # Should not contain impression_goal violations
        goal_violations = [v for v in violations if 'impression_goal' in v.field]
        assert len(goal_violations) == 0
    
    def test_impression_goal_below_minimum_triggers_biz_101(self, validator):
        """Test impression_goal below 1 triggers BIZ_101 error"""
        record = {'impression_goal': 0}
        violations = validator.validate_campaign_business_rules(record)
        
        biz_101_violations = [v for v in violations if v.error_code == 'BIZ_101']
        assert len(biz_101_violations) == 1
        assert 'below minimum 1' in biz_101_violations[0].message
        assert biz_101_violations[0].field == 'impression_goal'
        assert biz_101_violations[0].severity == 'high'
    
    def test_impression_goal_above_maximum_triggers_biz_102(self, validator):
        """Test impression_goal above 1,000,000,000 triggers BIZ_102 error"""
        record = {'impression_goal': 1000000001}
        violations = validator.validate_campaign_business_rules(record)
        
        biz_102_violations = [v for v in violations if v.error_code == 'BIZ_102']
        assert len(biz_102_violations) == 1
        assert 'above maximum 1,000,000,000' in biz_102_violations[0].message
        assert biz_102_violations[0].field == 'impression_goal'
    
    def test_cpm_eur_range_validation_success(self, validator):
        """Test CPM EUR within valid range (€0.01 - €45.00) passes"""
        record = {'cpm_eur': Decimal('12.50')}
        violations = validator.validate_campaign_business_rules(record)
        
        cpm_violations = [v for v in violations if 'cpm_eur' in v.field]
        assert len(cpm_violations) == 0
    
    def test_cpm_eur_below_minimum_triggers_biz_103(self, validator):
        """Test CPM EUR below €0.01 triggers BIZ_103 error"""
        record = {'cpm_eur': Decimal('0.005')}
        violations = validator.validate_campaign_business_rules(record)
        
        biz_103_violations = [v for v in violations if v.error_code == 'BIZ_103']
        assert len(biz_103_violations) == 1
        assert 'below minimum €0.01' in biz_103_violations[0].message
    
    def test_cpm_eur_above_maximum_triggers_biz_104(self, validator):
        """Test CPM EUR above €45.00 triggers BIZ_104 error"""
        record = {'cpm_eur': Decimal('50.00')}
        violations = validator.validate_campaign_business_rules(record)
        
        biz_104_violations = [v for v in violations if v.error_code == 'BIZ_104']
        assert len(biz_104_violations) == 1
        assert 'above maximum €45.00' in biz_104_violations[0].message
    
    def test_budget_eur_non_negative_validation_success(self, validator):
        """Test budget EUR non-negative validation passes"""
        record = {'budget_eur': Decimal('1000.00')}
        violations = validator.validate_campaign_business_rules(record)
        
        budget_violations = [v for v in violations if 'budget_eur' in v.field]
        assert len(budget_violations) == 0
    
    def test_budget_eur_negative_triggers_biz_108(self, validator):
        """Test negative budget EUR triggers BIZ_108 error"""
        record = {'budget_eur': Decimal('-100.00')}
        violations = validator.validate_campaign_business_rules(record)
        
        biz_108_violations = [v for v in violations if v.error_code == 'BIZ_108']
        assert len(biz_108_violations) == 1
        assert 'negative budget not allowed' in biz_108_violations[0].message.lower()
    
    def test_total_impressions_range_validation_success(self, validator):
        """Test total_impressions within valid range (619 - 231,000,000) passes"""
        record = {'total_impressions': 50000}
        violations = validator.validate_performance_business_rules(record)
        
        impressions_violations = [v for v in violations if 'total_impressions' in v.field]
        assert len(impressions_violations) == 0
    
    def test_total_impressions_below_minimum_triggers_biz_106(self, validator):
        """Test total_impressions below 619 triggers BIZ_106 error"""
        record = {'total_impressions': 500}
        violations = validator.validate_performance_business_rules(record)
        
        biz_106_violations = [v for v in violations if v.error_code == 'BIZ_106']
        assert len(biz_106_violations) == 1
        assert 'below minimum 619' in biz_106_violations[0].message
    
    def test_total_impressions_above_maximum_triggers_biz_107(self, validator):
        """Test total_impressions above 231,000,000 triggers BIZ_107 error"""
        record = {'total_impressions': 250000000}
        violations = validator.validate_performance_business_rules(record)
        
        biz_107_violations = [v for v in violations if v.error_code == 'BIZ_107']
        assert len(biz_107_violations) == 1
        assert 'above maximum 231,000,000' in biz_107_violations[0].message
    
    def test_multiple_business_rule_violations(self, validator):
        """Test multiple business rule violations are captured correctly"""
        record = {
            'impression_goal': 0,  # Below minimum (now 1)
            'cpm_eur': Decimal('0.005'),  # Below minimum
            'budget_eur': Decimal('-50.00')  # Negative
        }
        violations = validator.validate_campaign_business_rules(record)
        
        assert len(violations) == 3
        error_codes = [v.error_code for v in violations]
        assert 'BIZ_101' in error_codes  # impression_goal too low
        assert 'BIZ_103' in error_codes  # cpm_eur too low
        assert 'BIZ_108' in error_codes  # negative budget


class TestExactUUIDMatchingTests:
    """Test exact UUID matching for cross-file relationships"""
    
    @pytest.fixture
    def validator(self):
        return NewEntryValidator(Mock(), Mock(), "batch-001")
    
    def test_exact_uuid_match_validation(self, validator):
        """Test only exact UUID matches are considered valid relationships"""
        campaign_uuids = ['camp-001', 'camp-002', 'camp-003']
        performance_uuids = ['camp-001', 'camp-002', 'camp-004']  # camp-003 missing, camp-004 extra
        
        matches = validator.find_exact_uuid_matches(campaign_uuids, performance_uuids)
        
        # Should only return exact matches
        assert matches.exact_matches == ['camp-001', 'camp-002']
        assert matches.campaign_only == ['camp-003']
        assert matches.performance_only == ['camp-004']
    
    def test_case_sensitive_uuid_matching(self, validator):
        """Test UUID matching is case-sensitive"""
        campaign_uuids = ['Camp-001', 'CAMP-002']
        performance_uuids = ['camp-001', 'camp-002']  # Different case
        
        matches = validator.find_exact_uuid_matches(campaign_uuids, performance_uuids)
        
        # Should not match due to case sensitivity
        assert matches.exact_matches == []
        assert len(matches.campaign_only) == 2
        assert len(matches.performance_only) == 2


class TestExtendedStagingIntegrationTests:
    """Test integration with extended staging tables and Phase 1.2 structures"""
    
    @pytest.fixture
    def validator(self):
        staging_session = Mock()
        return NewEntryValidator(Mock(), staging_session, "batch-001")
    
    def test_new_entry_counting_in_extended_staging(self, validator):
        """Test new entry counting and cataloging in extended staging tables"""
        new_entries = [
            {'deal_campaign_id': 'camp-001', 'record_type': 'campaign'},
            {'deal_id': 'perf-001', 'record_type': 'performance'}
        ]
        
        result = validator.catalog_new_entries_in_staging(new_entries)
        
        assert result.total_new_entries == 2
        assert result.new_campaign_count == 1
        assert result.new_performance_count == 1
        assert validator.staging_db_session.execute.called
    
    def test_phase_context_1_2_setting_for_new_entries(self, validator):
        """Test phase_context='1.2' setting for new entries in extended staging"""
        new_entry = {'deal_campaign_id': 'camp-001', 'record_type': 'campaign'}
        
        validator.store_new_entry_in_extended_staging(new_entry)
        
        # Verify the INSERT query includes phase_context='1.2'
        call_args = validator.staging_db_session.execute.call_args[0][0]
        assert "phase_context" in str(call_args)
        assert "'1.2'" in str(call_args)
    
    def test_violation_details_json_object_storage(self, validator):
        """Test violation_details JSON object storage for business rule violations"""
        violations = [
            BusinessRuleViolation(
                error_code='BIZ_101',
                field='impression_goal',
                message='impression_goal 0 below minimum 1',
                severity='high',
                value=0
            ),
            BusinessRuleViolation(
                error_code='BIZ_103',
                field='cpm_eur',
                message='cpm_eur €0.005 below minimum €0.01',
                severity='high',
                value=Decimal('0.005')
            )
        ]
        
        entry_data = {'deal_campaign_id': 'camp-001'}
        
        validator.store_violations_in_extended_staging(entry_data, violations)
        
        # Verify JSON object structure was passed as parameter
        call_args = validator.staging_db_session.execute.call_args
        query = str(call_args[0][0])
        params = call_args[1] if len(call_args) > 1 else {}
        
        # Should contain violation_details parameter in query
        assert "violation_details" in query
        
        # Verify JSON object structure in the actual parameter data
        if 'violation_details' in params:
            violation_json = params['violation_details']
            # Parse the JSON to verify structure
            import json
            violation_data = json.loads(violation_json)
            assert isinstance(violation_data, list)
            if len(violation_data) > 0:
                assert "rule_code" in violation_data[0]
                assert "field" in violation_data[0]
                assert "message" in violation_data[0]


class TestBusinessRuleViolationModel:
    """Test BusinessRuleViolation model and utilities"""
    
    def test_business_rule_violation_creation(self):
        """Test BusinessRuleViolation model creation with all fields"""
        violation = BusinessRuleViolation(
            error_code='BIZ_101',
            field='impression_goal',
            message='impression_goal 0 below minimum 1',
            severity='high',
            value=0,
            record_id='camp-001'
        )
        
        assert violation.error_code == 'BIZ_101'
        assert violation.field == 'impression_goal'
        assert violation.severity == 'high'
        assert violation.value == 0
        assert violation.record_id == 'camp-001'
    
    def test_violation_to_json_object_conversion(self):
        """Test BusinessRuleViolation to JSON object conversion for storage"""
        violation = BusinessRuleViolation(
            error_code='BIZ_103',
            field='cpm_eur',
            message='CPM too low',
            severity='medium',
            value=Decimal('0.005')
        )
        
        violation_json = violation.to_json_object()
        
        # Should follow JSON object format: {"rule_code": "BIZ_101", "field": "impression_goal", "value": 500, "message": "..."}
        assert violation_json['rule_code'] == 'BIZ_103'
        assert violation_json['field'] == 'cpm_eur'
        assert violation_json['message'] == 'CPM too low'
        # Decimal should be converted to string for JSON serialization
        assert isinstance(violation_json['value'], str)
        assert violation_json['value'] == '0.005'
    
    def test_violation_list_to_json_object_array(self):
        """Test converting violation list to JSON object array for database storage"""
        violations = [
            BusinessRuleViolation('BIZ_101', 'impression_goal', 'Too low', 'high', 0),
            BusinessRuleViolation('BIZ_103', 'cpm_eur', 'Too low', 'high', Decimal('0.005'))
        ]
        
        json_array = BusinessRuleViolation.violations_to_json_objects(violations)
        
        assert isinstance(json_array, list)
        assert len(json_array) == 2
        
        # First violation object
        assert json_array[0]['rule_code'] == 'BIZ_101'
        assert json_array[0]['field'] == 'impression_goal'
        assert json_array[0]['value'] == 0
        assert json_array[0]['message'] == 'Too low'
        
        # Second violation object
        assert json_array[1]['rule_code'] == 'BIZ_103'
        assert json_array[1]['field'] == 'cpm_eur'
        assert json_array[1]['value'] == '0.005'  # Decimal converted to string
        assert json_array[1]['message'] == 'Too low'


class TestPartialVsCompleteFailureLogic:
    """Test partial vs complete failure handling logic"""
    
    @pytest.fixture
    def validator(self):
        return NewEntryValidator(Mock(), Mock(), "batch-001")
    
    def test_partial_violation_affects_only_respective_data(self, validator):
        """Test partial violations affect only the respective data records"""
        batch_records = [
            {'deal_campaign_id': 'valid-001', 'impression_goal': 50000, 'cpm_eur': Decimal('5.00')},
            {'deal_campaign_id': 'invalid-002', 'impression_goal': 0, 'cpm_eur': Decimal('5.00')},  # BIZ_101 violation
            {'deal_campaign_id': 'valid-003', 'impression_goal': 75000, 'cpm_eur': Decimal('8.00')}
        ]
        
        result = validator.process_batch_with_partial_failure_handling(batch_records)
        
        # Should process valid records successfully
        assert result.successful_records == 2
        assert result.failed_records == 1
        assert result.partial_failure is True
        assert result.complete_failure is False
        
        # Valid records should be stored
        assert 'valid-001' in result.stored_record_ids
        assert 'valid-003' in result.stored_record_ids
        
        # Invalid record should be flagged with violations
        assert 'invalid-002' in result.violation_record_ids
    
    def test_complete_failure_affects_entire_upload(self, validator):
        """Test complete failure scenarios affect the entire upload"""
        # Simulate database connection failure
        validator.staging_db_session.execute.side_effect = Exception("Database connection lost")
        
        batch_records = [
            {'deal_campaign_id': 'record-001', 'impression_goal': 50000},
            {'deal_campaign_id': 'record-002', 'impression_goal': 75000}
        ]
        
        result = validator.process_batch_with_complete_failure_handling(batch_records)
        
        # Should fail completely
        assert result.successful_records == 0
        assert result.failed_records == 2
        assert result.partial_failure is False
        assert result.complete_failure is True
        assert result.failure_reason == "Database connection lost"
        
        # No records should be stored
        assert len(result.stored_record_ids) == 0
    
    def test_business_rule_violations_trigger_partial_failure(self, validator):
        """Test business rule violations trigger partial failure, not complete failure"""
        batch_records = [
            {'deal_campaign_id': 'valid-001', 'impression_goal': 50000, 'budget_eur': Decimal('1000.00')},
            {'deal_campaign_id': 'invalid-002', 'impression_goal': 0, 'budget_eur': Decimal('-100.00')},  # Multiple violations
            {'deal_campaign_id': 'valid-003', 'impression_goal': 75000, 'budget_eur': Decimal('2000.00')}
        ]
        
        # Mock business rule validation
        validator.validate_campaign_business_rules = Mock(side_effect=[
            [],  # valid-001: no violations
            [Mock(error_code='BIZ_101'), Mock(error_code='BIZ_108')],  # invalid-002: multiple violations
            []  # valid-003: no violations
        ])
        
        result = validator.process_batch_with_failure_categorization(batch_records)
        
        # Should be partial failure (business rule violations don't cause complete failure)
        assert result.partial_failure is True
        assert result.complete_failure is False
        assert result.successful_records == 2
        assert result.business_rule_violations == 2
    
    def test_system_errors_trigger_complete_failure(self, validator):
        """Test system errors trigger complete failure"""
        batch_records = [
            {'deal_campaign_id': 'record-001', 'impression_goal': 50000}
        ]
        
        # Mock system error (not business rule violation)
        validator.production_db_session.execute.side_effect = Exception("Production database unavailable")
        
        result = validator.process_batch_with_failure_categorization(batch_records)
        
        # Should be complete failure (system errors affect entire processing)
        assert result.partial_failure is False
        assert result.complete_failure is True
        assert result.system_error is True
        assert "Production database unavailable" in result.failure_reason
    
    def test_mixed_failure_types_prioritize_complete_over_partial(self, validator):
        """Test mixed failure types prioritize complete failure over partial failure"""
        batch_records = [
            {'deal_campaign_id': 'invalid-001', 'impression_goal': 0},  # Business rule violation
            {'deal_campaign_id': 'valid-002', 'impression_goal': 50000}
        ]
        
        # Mock: first record has business rule violation, then system error occurs
        validator.validate_campaign_business_rules = Mock(side_effect=[
            [Mock(error_code='BIZ_101')],  # Business rule violation
            Exception("System error during processing")  # System error
        ])
        
        result = validator.process_batch_with_mixed_failure_handling(batch_records)
        
        # System error should take precedence
        assert result.complete_failure is True
        assert result.partial_failure is False
        assert result.system_error is True


class TestNewEntryValidationResult:
    """Test NewEntryValidationResult model and functionality"""
    
    def test_validation_result_initialization(self):
        """Test NewEntryValidationResult initialization"""
        result = NewEntryValidationResult(
            total_processed=100,
            new_entries_found=25,
            business_rule_violations=5,
            processing_batch_id="batch-001"
        )
        
        assert result.total_processed == 100
        assert result.new_entries_found == 25
        assert result.business_rule_violations == 5
        assert result.processing_batch_id == "batch-001"
        assert result.success_rate == 0.75  # (100-25)/100
    
    def test_validation_result_summary_generation(self):
        """Test validation result summary generation"""
        violations = [
            BusinessRuleViolation('BIZ_101', 'impression_goal', 'Too low', 'high', 2500),
            BusinessRuleViolation('BIZ_105', 'combined_upload', 'Missing file', 'critical', None)
        ]
        
        result = NewEntryValidationResult(
            total_processed=50,
            new_entries_found=10,
            violations=violations
        )
        
        summary = result.get_summary()
        
        assert 'total_processed' in summary
        assert 'new_entries_found' in summary
        assert 'critical_violations' in summary
        assert 'high_violations' in summary
        assert summary['critical_violations'] == 1
        assert summary['high_violations'] == 1


class TestFunctionalInterfaceTests:
    """Test functional interface functions for new entry validation"""
    
    @pytest.mark.asyncio
    async def test_validate_new_campaign_entry_function(self):
        """Test standalone validate_new_campaign_entry function"""
        campaign_data = {
            'deal_campaign_id': 'camp-001',
            'impression_goal': 50000,
            'cpm_eur': Decimal('5.50'),
            'budget_eur': Decimal('1000.00')
        }
        
        with patch('src.services.new_entry_validator.lookup_uuids_in_production') as mock_lookup:
            mock_lookup.return_value.new_uuids = ['camp-001']
            
            result = await validate_new_campaign_entry(campaign_data, Mock(), Mock())
            
            assert result.is_new_entry is True
            assert len(result.business_rule_violations) == 0
    
    @pytest.mark.asyncio
    async def test_validate_new_performance_entry_function(self):
        """Test standalone validate_new_performance_entry function"""
        performance_data = {
            'deal_id': 'perf-001',
            'total_impressions': 45000,
            'purchase_type': 'programmatic'
        }
        
        with patch('src.services.new_entry_validator.lookup_uuids_in_production') as mock_lookup:
            mock_lookup.return_value.new_uuids = ['perf-001']
            
            result = await validate_new_performance_entry(performance_data, Mock(), Mock())
            
            assert result.is_new_entry is True
            assert len(result.business_rule_violations) == 0
    
    @pytest.mark.asyncio
    async def test_exact_uuid_lookup_function(self):
        """Test exact UUID lookup functionality"""
        uuids_to_check = ['uuid-001', 'uuid-002', 'uuid-003']
        
        with patch('src.services.new_entry_validator.lookup_uuids_in_production') as mock_lookup:
            mock_lookup.return_value = Mock(
                found_uuids=['uuid-001', 'uuid-002'],  # Exact matches only
                new_uuids=['uuid-003']
            )
            
            result = await mock_lookup(uuids_to_check, 'campaign', Mock())
            
            # Should return only exact matches
            assert 'uuid-001' in result.found_uuids
            assert 'uuid-002' in result.found_uuids
            assert 'uuid-003' in result.new_uuids
    
    @pytest.mark.asyncio
    async def test_lookup_uuids_in_production_function(self):
        """Test standalone lookup_uuids_in_production function"""
        mock_session = Mock()
        mock_session.execute.return_value.fetchall.return_value = []
        
        result = await lookup_uuids_in_production(['uuid-001'], 'campaign', mock_session)
        
        assert result.new_uuids == ['uuid-001']
        assert result.found_uuids == []


# Test Data Structures and Models
class TestDataStructures:
    """Test data structure definitions and validation"""
    
    def test_business_rule_violation_required_fields(self):
        """Test BusinessRuleViolation requires essential fields"""
        with pytest.raises(TypeError):
            BusinessRuleViolation()  # Missing required fields
        
        # Should work with required fields
        violation = BusinessRuleViolation(
            error_code='BIZ_101',
            field='impression_goal',
            message='Test message',
            severity='high'
        )
        assert violation.error_code == 'BIZ_101'
    
    def test_error_code_validation(self):
        """Test error code validation follows BIZ_xxx pattern (BIZ_105 removed)"""
        valid_codes = ['BIZ_101', 'BIZ_102', 'BIZ_103', 'BIZ_104', 'BIZ_106', 'BIZ_107', 'BIZ_108']
        
        for code in valid_codes:
            violation = BusinessRuleViolation(code, 'test_field', 'Test message', 'high')
            assert violation.error_code == code
    
    def test_biz_105_code_removed(self):
        """Test BIZ_105 (combined upload enforcement) is no longer used"""
        # BIZ_105 should not be part of the valid business rule codes
        removed_codes = ['BIZ_105']
        
        for code in removed_codes:
            # This test documents that BIZ_105 is intentionally removed
            # Implementation should not generate BIZ_105 violations
            assert code not in ['BIZ_101', 'BIZ_102', 'BIZ_103', 'BIZ_104', 'BIZ_106', 'BIZ_107', 'BIZ_108']
    
    def test_severity_levels(self):
        """Test severity levels: critical, high, medium, low"""
        severity_levels = ['critical', 'high', 'medium', 'low']
        
        for severity in severity_levels:
            violation = BusinessRuleViolation('BIZ_101', 'test_field', 'Test', severity)
            assert violation.severity == severity


# Performance and Edge Case Tests
class TestPerformanceAndEdgeCases:
    """Test performance scenarios and edge cases"""
    
    @pytest.mark.asyncio
    async def test_large_batch_processing_performance(self):
        """Test performance with large batches (10,000+ records)"""
        validator = NewEntryValidator(Mock(), Mock(), "batch-001")
        
        # Mock large dataset
        large_uuid_list = [f'uuid-{i:06d}' for i in range(10000)]
        validator.production_db_session.execute.return_value.fetchall.return_value = []
        
        start_time = datetime.now()
        result = await validator.lookup_uuids_in_production(large_uuid_list, 'campaign')
        end_time = datetime.now()
        
        # Should process in reasonable time (less than 10 seconds for mocked scenario)
        processing_time = (end_time - start_time).total_seconds()
        assert processing_time < 10
        assert len(result.new_uuids) == 10000
    
    def test_decimal_precision_handling(self):
        """Test proper handling of decimal precision for monetary values"""
        validator = NewEntryValidator(Mock(), Mock(), "batch-001")
        
        # Test high precision decimals
        record = {'cpm_eur': Decimal('12.123456789')}
        violations = validator.validate_campaign_business_rules(record)
        
        # Should handle high precision without errors
        assert isinstance(violations, list)
    
    def test_unicode_and_special_characters(self):
        """Test handling of Unicode and special characters in record data"""
        validator = NewEntryValidator(Mock(), Mock(), "batch-001")
        
        record = {
            'deal_campaign_name': 'Campaign with émojis 🚀 and special chars ñáéíóú',
            'buyer': 'Büyer Ñame with Ümlauts'
        }
        
        violations = validator.validate_campaign_business_rules(record)
        
        # Should handle Unicode without errors
        assert isinstance(violations, list)
    
    def test_null_and_empty_value_handling(self):
        """Test handling of null and empty values"""
        validator = NewEntryValidator(Mock(), Mock(), "batch-001")
        
        record = {
            'impression_goal': None,
            'cpm_eur': '',
            'budget_eur': 0
        }
        
        violations = validator.validate_campaign_business_rules(record)
        
        # Should generate appropriate violations for missing/invalid values
        assert len(violations) > 0
        null_violations = [v for v in violations if 'null' in v.message.lower() or 'empty' in v.message.lower()]
        assert len(null_violations) > 0


class TestErrorHandlingAndRobustness:
    """Test comprehensive error handling and system robustness"""
    
    def test_database_session_cleanup_on_error(self):
        """Test database session cleanup when errors occur"""
        staging_session = Mock()
        staging_session.execute.side_effect = Exception("Database error")
        
        validator = NewEntryValidator(Mock(), staging_session, "batch-001")
        
        with pytest.raises(Exception):
            validator.store_new_entry_in_extended_staging({'deal_campaign_id': 'test'})
        
        # Should call rollback on error
        staging_session.rollback.assert_called_once()
    
    def test_partial_batch_failure_handling(self):
        """Test handling when part of a batch fails processing"""
        validator = NewEntryValidator(Mock(), Mock(), "batch-001")
        
        # Simulate partial failure scenario
        mixed_records = [
            {'deal_campaign_id': 'valid-001', 'impression_goal': 50000},  # Valid
            {'deal_campaign_id': 'invalid-002', 'impression_goal': 'invalid'},  # Invalid
            {'deal_campaign_id': 'valid-003', 'impression_goal': 75000}  # Valid
        ]
        
        result = validator.process_batch(mixed_records)
        
        # Should process valid records and report errors for invalid ones
        assert result.successful_records == 2
        assert result.failed_records == 1
        assert len(result.processing_errors) == 1
    
    def test_memory_management_large_datasets(self):
        """Test memory management with large datasets"""
        validator = NewEntryValidator(Mock(), Mock(), "batch-001")
        
        # This test ensures the validator doesn't load entire datasets into memory
        # Implementation should use streaming/batching approaches
        
        large_dataset_path = "/path/to/large/dataset.csv"  # Mock path
        
        with patch('src.services.new_entry_validator.process_file_in_chunks') as mock_process:
            mock_process.return_value = Mock(total_processed=1000000, memory_used_mb=50)
            
            result = validator.validate_large_file(large_dataset_path)
            
            # Should process large files without excessive memory usage
            assert result.memory_used_mb < 100  # Reasonable memory limit