"""
Phase 1.1 Backward Compatibility Tests
Ensures that all Phase 1.2 extensions maintain full backward compatibility 
with existing Phase 1.1 functionality.

CRITICAL: These tests must pass to ensure Phase 1.1 users are not impacted
by Phase 1.2 database extensions and business rule changes.
"""
import pytest
from datetime import datetime
from decimal import Decimal
from uuid import uuid4
from typing import Dict, List, Any

from src.database.staging_connection import StagingDatabase
from src.models.staging import CampaignsStaging, ReportingStaging, PurchaseType
from src.services.unified_error_codes import get_error_info, is_phase_11_compatible


class TestPhase11DatabaseCompatibility:
    """Test Phase 1.1 database operations remain unchanged."""

    def setup_method(self):
        """Set up test database connection."""
        self.db = StagingDatabase()
    
    def teardown_method(self):
        """Clean up after tests."""
        if hasattr(self, 'test_batch_id'):
            try:
                self.db.cleanup_batch_records(self.test_batch_id)
            except:
                pass
        self.db.close()

    def test_phase_11_campaign_data_insertion(self):
        """Test Phase 1.1 campaign data can be inserted without Phase 1.2 columns."""
        self.test_batch_id = str(uuid4())
        
        # Phase 1.1 campaign data - no Phase 1.2 fields
        phase_11_campaign = {
            'deal_campaign_id': str(uuid4()),
            'deal_campaign_name': 'Phase 1.1 Compatible Campaign',
            'start_date': datetime(2024, 1, 1),
            'end_date': datetime(2024, 12, 31),
            'impression_goal': 100000,
            'budget_eur': Decimal('15000.50'),
            'cpm_eur': Decimal('3.25'),
            'buyer': 'Phase 1.1 Test Buyer',
            'processing_batch_id': self.test_batch_id,
            'record_classification': 'existing_entry',
            'source_row_number': 1,
            'validation_errors': None
            # NOTE: No Phase 1.2 fields (phase_context, violation_details, etc.)
        }
        
        # Should insert successfully without Phase 1.2 fields
        self.db.save_campaigns_batch([phase_11_campaign])
        
        # Verify data was inserted
        batch_records = self.db.get_campaign_batch_by_processing_id(self.test_batch_id)
        assert len(batch_records) == 1
        
        record = batch_records[0]
        assert record.deal_campaign_name == 'Phase 1.1 Compatible Campaign'
        assert record.record_classification == 'existing_entry'
        
        # Phase 1.2 fields should be NULL/None (not populated)
        assert record.phase_context is None
        assert record.violation_details is None
        assert record.flagged_for_review is None
        assert record.variance_detected is None

    def test_phase_11_reporting_data_insertion(self):
        """Test Phase 1.1 reporting data can be inserted without Phase 1.2 columns."""
        self.test_batch_id = str(uuid4())
        
        # Create a campaign first
        campaign_id = str(uuid4())
        campaign_data = {
            'deal_campaign_id': campaign_id,
            'deal_campaign_name': 'Test Campaign',
            'start_date': datetime(2024, 1, 1),
            'end_date': datetime(2024, 12, 31),
            'impression_goal': 50000,
            'cpm_eur': Decimal('2.50'),
            'buyer': 'Test Buyer',
            'processing_batch_id': self.test_batch_id,
            'record_classification': 'existing_entry',
            'source_row_number': 1
        }
        
        self.db.save_campaigns_batch([campaign_data])
        
        # Phase 1.1 reporting data - no Phase 1.2 fields
        with self.db.get_session() as session:
            reporting_record = ReportingStaging(
                deal_id=campaign_id,
                date_recorded=datetime(2024, 3, 15),
                deal_name='Test Deal',
                purchase_type=PurchaseType.guaranteed,
                total_impressions=Decimal('1500.000000'),
                processing_batch_id=self.test_batch_id,
                record_classification='existing_entry',
                source_row_number=1
                # NOTE: No Phase 1.2 fields
            )
            session.add(reporting_record)
        
        # Verify data was inserted
        batch_records = self.db.get_reporting_batch_by_processing_id(self.test_batch_id)
        assert len(batch_records) == 1
        
        record = batch_records[0]
        assert record.deal_name == 'Test Deal'
        assert record.purchase_type == PurchaseType.guaranteed
        
        # Phase 1.2 fields should be NULL/None
        assert record.phase_context is None
        assert record.violation_details is None
        assert record.flagged_for_review is None
        assert record.variance_detected is None

    def test_phase_11_classification_update_compatibility(self):
        """Test Phase 1.1 classification updates still work."""
        self.test_batch_id = str(uuid4())
        
        campaign_id = str(uuid4())
        campaign_data = {
            'deal_campaign_id': campaign_id,
            'deal_campaign_name': 'Classification Test Campaign',
            'start_date': datetime(2024, 1, 1),
            'end_date': datetime(2024, 12, 31),
            'impression_goal': 75000,
            'cpm_eur': Decimal('4.00'),
            'buyer': 'Test Buyer',
            'processing_batch_id': self.test_batch_id,
            'record_classification': 'pending',
            'source_row_number': 1
        }
        
        self.db.save_campaigns_batch([campaign_data])
        
        # Create a mock classification result (Phase 1.1 style)
        class MockClassificationResult:
            def __init__(self):
                self.category = MockCategory()
                self.validation_errors = ['VAL_010: UUID not found in production']
        
        class MockCategory:
            def __init__(self):
                self.value = 'validation_error'
        
        mock_result = MockClassificationResult()
        
        # Update classification using Phase 1.1 method
        self.db.update_campaign_classification(campaign_id, mock_result)
        
        # Verify update worked
        with self.db.get_session() as session:
            record = session.query(CampaignsStaging).filter(
                CampaignsStaging.deal_campaign_id == campaign_id
            ).first()
            
            assert record is not None
            assert record.record_classification == 'validation_error'
            assert record.validation_errors == 'VAL_010: UUID not found in production'

    def test_phase_11_batch_operations_compatibility(self):
        """Test Phase 1.1 batch operations continue working."""
        self.test_batch_id = str(uuid4())
        
        # Create multiple Phase 1.1 style records
        campaigns = []
        for i in range(5):
            campaigns.append({
                'deal_campaign_id': str(uuid4()),
                'deal_campaign_name': f'Batch Campaign {i+1}',
                'start_date': datetime(2024, 1, 1),
                'end_date': datetime(2024, 12, 31),
                'impression_goal': 10000 * (i + 1),
                'cpm_eur': Decimal(f'{2.0 + i}.50'),
                'buyer': 'Batch Test Buyer',
                'processing_batch_id': self.test_batch_id,
                'record_classification': 'new_entry',
                'source_row_number': i + 1
            })
        
        # Batch insert
        self.db.save_campaigns_batch(campaigns)
        
        # Test Phase 1.1 batch operations
        record_counts = self.db.get_batch_record_counts(self.test_batch_id)
        assert record_counts['campaign_records'] == 5
        assert record_counts['reporting_records'] == 0
        assert record_counts['total_records'] == 5
        
        # Test data integrity validation
        integrity_result = self.db.validate_batch_data_integrity(self.test_batch_id)
        assert integrity_result['integrity_valid'] is True
        assert integrity_result['has_duplicates'] is False
        assert integrity_result['has_null_ids'] is False
        
        # Test backup operation
        backup_result = self.db.backup_batch_data(self.test_batch_id)
        assert backup_result['record_counts']['campaigns'] == 5
        assert len(backup_result['campaign_records']) == 5


class TestPhase11ErrorCodeCompatibility:
    """Test Phase 1.1 error codes remain fully functional."""

    def test_phase_11_error_codes_available(self):
        """Test all Phase 1.1 error codes are available in unified system."""
        phase_11_codes = ['VAL_010', 'VAL_015', 'VAL_020']
        
        for code in phase_11_codes:
            error_info = get_error_info(code)
            assert error_info is not None, f"Phase 1.1 error code {code} should be available"
            assert is_phase_11_compatible(code), f"Error code {code} should be Phase 1.1 compatible"

    def test_phase_11_error_messages_unchanged(self):
        """Test Phase 1.1 error messages remain exactly the same."""
        from src.services.unified_error_codes import UnifiedErrorCodes
        
        # These messages must not change to maintain backward compatibility
        assert UnifiedErrorCodes.VAL_010 == "UUID not found in production"
        assert UnifiedErrorCodes.VAL_015 == "Invalid hierarchical structure"
        assert UnifiedErrorCodes.VAL_020 == "New entry business rule violation"

    def test_phase_11_error_handling_patterns(self):
        """Test Phase 1.1 error handling patterns still work."""
        # Test getting Phase 1.1 compatible errors
        phase_11_errors = []
        for code in ['VAL_010', 'VAL_015', 'VAL_020']:
            if is_phase_11_compatible(code):
                phase_11_errors.append(code)
        
        assert len(phase_11_errors) == 3, "All Phase 1.1 error codes should be compatible"


class TestPhase11BusinessRuleCompatibility:
    """Test Phase 1.1 business rule processing remains unchanged."""

    def test_phase_11_rule_execution_mode(self):
        """Test Phase 1.1 mode doesn't trigger Phase 1.2 specific rules."""
        from src.services.priority_business_rules import (
            RuleExecutionContext, 
            apply_business_rules,
            BusinessRulePriority
        )
        
        # Create Phase 1.1 context
        context = RuleExecutionContext(
            phase='1.1',
            upload_type='single',
            campaign_data=[{
                'deal_campaign_id': str(uuid4()),
                'deal_campaign_name': 'Phase 1.1 Campaign'
            }],
            reporting_data=[],
            processing_batch_id=str(uuid4())
        )
        
        # Apply business rules
        result = apply_business_rules(context)
        
        # Should succeed without Phase 1.2 specific violations
        assert result is not None
        
        # Check that no Phase 1.2 specific error codes appear
        phase_12_codes = ['BIZ_101', 'BIZ_102', 'BIZ_103', 'BIZ_104', 'BIZ_105', 'BIZ_106']
        for violation in result.violations:
            assert violation.error_code not in phase_12_codes, \
                f"Phase 1.2 error code {violation.error_code} should not appear in Phase 1.1 mode"

    def test_phase_11_single_file_upload_unchanged(self):
        """Test Phase 1.1 single file uploads work without combined upload requirements."""
        from src.services.priority_business_rules import (
            RuleExecutionContext, 
            validate_combined_upload
        )
        
        # Phase 1.1 single file upload context
        context = RuleExecutionContext(
            phase='1.1',
            upload_type='single',
            campaign_data=[{'deal_campaign_id': str(uuid4())}],
            reporting_data=[],  # Empty reporting data is OK for single upload
            processing_batch_id=str(uuid4())
        )
        
        # Combined upload validation should pass for single uploads
        result = validate_combined_upload(context)
        assert result.success is True, "Single uploads should not require combined upload validation"
        assert len(result.violations) == 0, "Single uploads should not have combined upload violations"


class TestPhase11APICompatibility:
    """Test Phase 1.1 API interactions remain unchanged."""

    def test_phase_11_staging_connection_methods(self):
        """Test all Phase 1.1 StagingDatabase methods still work."""
        db = StagingDatabase()
        
        # Verify all Phase 1.1 methods exist and are callable
        phase_11_methods = [
            'save_campaigns_batch',
            'update_campaign_classification',
            'update_reporting_classification',
            'get_campaign_batch_by_processing_id',
            'get_reporting_batch_by_processing_id',
            'cleanup_batch_records',
            'get_batch_record_counts',
            'validate_batch_data_integrity',
            'backup_batch_data',
            'execute_transaction'
        ]
        
        for method_name in phase_11_methods:
            assert hasattr(db, method_name), f"Phase 1.1 method {method_name} should exist"
            method = getattr(db, method_name)
            assert callable(method), f"Phase 1.1 method {method_name} should be callable"
        
        db.close()

    def test_phase_11_model_compatibility(self):
        """Test Phase 1.1 model structures remain unchanged."""
        # Verify Phase 1.1 fields still exist
        campaigns_table = CampaignsStaging.__table__
        reporting_table = ReportingStaging.__table__
        
        # Phase 1.1 required columns for campaigns
        phase_11_campaign_columns = {
            'deal_campaign_id', 'deal_campaign_name', 'start_date', 'end_date',
            'impression_goal', 'budget_eur', 'cpm_eur', 'buyer',
            'processing_batch_id', 'record_classification', 'source_row_number',
            'validation_errors', 'created_at', 'updated_at'
        }
        
        actual_columns = set(campaigns_table.columns.keys())
        missing_columns = phase_11_campaign_columns - actual_columns
        assert len(missing_columns) == 0, f"Phase 1.1 campaign columns missing: {missing_columns}"
        
        # Phase 1.1 required columns for reporting
        phase_11_reporting_columns = {
            'deal_id', 'date_recorded', 'deal_name', 'core_dsp_audience_segment',
            'core_dsp_placement', 'core_dsp_creative', 'purchase_type',
            'total_impressions', 'processing_batch_id', 'record_classification',
            'source_row_number', 'validation_errors', 'created_at', 'updated_at'
        }
        
        actual_columns = set(reporting_table.columns.keys())
        missing_columns = phase_11_reporting_columns - actual_columns
        assert len(missing_columns) == 0, f"Phase 1.1 reporting columns missing: {missing_columns}"


class TestPhase11IntegrationScenarios:
    """Test complete Phase 1.1 workflow scenarios."""

    def setup_method(self):
        """Set up test environment."""
        self.db = StagingDatabase()
        self.test_batch_id = str(uuid4())
    
    def teardown_method(self):
        """Clean up after tests."""
        try:
            self.db.cleanup_batch_records(self.test_batch_id)
        except:
            pass
        self.db.close()

    def test_complete_phase_11_upload_workflow(self):
        """Test a complete Phase 1.1 upload workflow remains unchanged."""
        # Phase 1.1 campaign upload
        campaign_id = str(uuid4())
        campaign_data = {
            'deal_campaign_id': campaign_id,
            'deal_campaign_name': 'Complete Workflow Test Campaign',
            'start_date': datetime(2024, 2, 1),
            'end_date': datetime(2024, 11, 30),
            'impression_goal': 250000,
            'budget_eur': Decimal('45000.00'),
            'cpm_eur': Decimal('5.75'),
            'buyer': 'Premium Advertiser LLC',
            'processing_batch_id': self.test_batch_id,
            'record_classification': 'new_entry',
            'source_row_number': 1,
            'validation_errors': None
        }
        
        # 1. Save campaign data (Phase 1.1 method)
        self.db.save_campaigns_batch([campaign_data])
        
        # 2. Verify data was saved
        batch_records = self.db.get_campaign_batch_by_processing_id(self.test_batch_id)
        assert len(batch_records) == 1
        
        # 3. Update classification (Phase 1.1 method)
        class MockResult:
            def __init__(self):
                self.category = MockCategory()
                self.validation_errors = None
        
        class MockCategory:
            def __init__(self):
                self.value = 'validated'
        
        self.db.update_campaign_classification(campaign_id, MockResult())
        
        # 4. Verify classification update
        updated_records = self.db.get_campaign_batch_by_processing_id(self.test_batch_id)
        assert updated_records[0].record_classification == 'validated'
        
        # 5. Validate data integrity (Phase 1.1 method)
        integrity = self.db.validate_batch_data_integrity(self.test_batch_id)
        assert integrity['integrity_valid'] is True
        
        # 6. Create backup (Phase 1.1 method)
        backup = self.db.backup_batch_data(self.test_batch_id)
        assert backup['record_counts']['campaigns'] == 1
        
        # 7. Clean up (Phase 1.1 method)
        counts_before = self.db.get_batch_record_counts(self.test_batch_id)
        assert counts_before['total_records'] == 1
        
        self.db.cleanup_batch_records(self.test_batch_id)
        
        counts_after = self.db.get_batch_record_counts(self.test_batch_id)
        assert counts_after['total_records'] == 0

    def test_phase_11_error_handling_workflow(self):
        """Test Phase 1.1 error handling workflow remains unchanged."""
        from src.services.unified_error_codes import get_error_info
        
        # Simulate Phase 1.1 error handling
        error_code = 'VAL_010'
        error_info = get_error_info(error_code)
        
        # Phase 1.1 error processing should work
        assert error_info is not None
        assert error_info.code == error_code
        assert error_info.message == "UUID not found in production"
        assert is_phase_11_compatible(error_code)
        
        # Create campaign with validation error (Phase 1.1 style)
        campaign_with_error = {
            'deal_campaign_id': str(uuid4()),
            'deal_campaign_name': 'Error Test Campaign',
            'start_date': datetime(2024, 1, 1),
            'end_date': datetime(2024, 12, 31),
            'impression_goal': 50000,
            'budget_eur': Decimal('15000.00'),  # Add budget field
            'cpm_eur': Decimal('3.00'),
            'buyer': 'Error Test Buyer',
            'processing_batch_id': self.test_batch_id,
            'record_classification': 'validation_error',
            'source_row_number': 1,
            'validation_errors': f'{error_code}: {error_info.message}'
        }
        
        # Should save successfully with Phase 1.1 error format
        self.db.save_campaigns_batch([campaign_with_error])
        
        # Verify error was saved correctly
        with self.db.get_session() as session:
            records = session.query(CampaignsStaging).filter(
                CampaignsStaging.processing_batch_id == self.test_batch_id
            ).all()
            assert len(records) == 1
            assert records[0].record_classification == 'validation_error'
            assert error_code in records[0].validation_errors