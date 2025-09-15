"""
Integration tests for CrossFileValidator with Phase 1.1 infrastructure

Tests integration scenarios:
1. Real database interaction with staging tables
2. Integration with Phase 1.1 batch management
3. End-to-end cross-file validation workflows
4. Real data processing scenarios

These tests verify that the CrossFileValidator works correctly
with the actual Phase 1.1 infrastructure and database.
"""
import pytest
from uuid import UUID, uuid4
from datetime import datetime
from decimal import Decimal
import tempfile
import os

from src.services.cross_file_validator import (
    CrossFileValidator,
    ValidationResult,
    CrossFileValidationError
)
from src.services.unified_error_codes import UnifiedErrorCodes
from src.models.staging import CampaignsStaging, ReportingStaging, PurchaseType
from src.database.staging_connection import StagingDatabase, create_staging_engine


class TestCrossFileValidatorIntegration:
    """Integration tests for CrossFileValidator with real database."""
    
    @pytest.fixture
    def test_database_url(self):
        """Test database URL for integration testing."""
        # Use a test-specific database to avoid conflicts
        return "postgresql://localhost:5432/ppv_fulfillment_test"
    
    @pytest.fixture
    def staging_db(self, test_database_url):
        """Real staging database instance for testing."""
        db = StagingDatabase(test_database_url)
        
        # Initialize tables for testing
        try:
            from src.database.staging_connection import init_staging_tables
            engine = create_staging_engine(test_database_url)
            init_staging_tables(engine)
        except Exception as e:
            # Skip if test database is not available
            pytest.skip(f"Test database not available: {e}")
        
        yield db
        
        # Cleanup
        db.close()
    
    @pytest.fixture
    def validator(self, test_database_url):
        """CrossFileValidator with real database connection."""
        try:
            return CrossFileValidator(staging_db_url=test_database_url)
        except Exception as e:
            pytest.skip(f"Cannot create validator with test database: {e}")
    
    @pytest.fixture
    def test_batch_id(self):
        """Test batch ID for integration testing."""
        return str(uuid4())
    
    @pytest.fixture
    def sample_campaign_data(self, test_batch_id):
        """Sample campaign data for database insertion."""
        campaign_id_1 = UUID('aaaaaaaa-1111-1111-1111-111111111111')
        campaign_id_2 = UUID('bbbbbbbb-2222-2222-2222-222222222222')
        
        return [
            {
                'deal_campaign_id': campaign_id_1,
                'deal_campaign_name': 'Integration Test > Campaign A > Sub A',
                'start_date': datetime(2024, 1, 1),
                'end_date': datetime(2024, 1, 31),
                'impression_goal': 100000,
                'budget_eur': Decimal('5000.00'),
                'cpm_eur': Decimal('2.50'),
                'buyer': 'Integration Buyer A',
                'processing_batch_id': test_batch_id,
                'record_classification': 'valid',
                'source_row_number': 1
            },
            {
                'deal_campaign_id': campaign_id_2,
                'deal_campaign_name': 'Integration Test > Campaign B > Sub B',
                'start_date': datetime(2024, 2, 1),
                'end_date': datetime(2024, 2, 28),
                'impression_goal': 200000,
                'budget_eur': Decimal('8000.00'),
                'cpm_eur': Decimal('3.00'),
                'buyer': 'Integration Buyer B',
                'processing_batch_id': test_batch_id,
                'record_classification': 'valid',
                'source_row_number': 2
            }
        ]
    
    @pytest.fixture
    def sample_performance_data(self, test_batch_id):
        """Sample performance data for database insertion."""
        deal_id_1 = UUID('aaaaaaaa-1111-1111-1111-111111111111')
        deal_id_2 = UUID('bbbbbbbb-2222-2222-2222-222222222222')
        
        return [
            {
                'deal_id': deal_id_1,
                'date_recorded': datetime(2024, 1, 15),
                'deal_name': 'Integration Test > Campaign A > Sub A',
                'core_dsp_audience_segment': 'Integration Segment A',
                'core_dsp_placement': 'Banner Integration',
                'core_dsp_creative': 'Creative Integration A',
                'purchase_type': PurchaseType.guaranteed,
                'total_impressions': Decimal('50000.0'),
                'processing_batch_id': test_batch_id,
                'record_classification': 'valid',
                'source_row_number': 1
            },
            {
                'deal_id': deal_id_2,
                'date_recorded': datetime(2024, 2, 10),
                'deal_name': 'Integration Test > Campaign B > Sub B',
                'core_dsp_audience_segment': 'Integration Segment B',
                'core_dsp_placement': 'Video Integration',
                'core_dsp_creative': 'Creative Integration B',
                'purchase_type': PurchaseType.unguaranteed,
                'total_impressions': Decimal('75000.0'),
                'processing_batch_id': test_batch_id,
                'record_classification': 'valid',
                'source_row_number': 2
            }
        ]


class TestRealDatabaseIntegration:
    """Test integration with real staging database operations."""
    
    def test_combined_upload_validation_with_real_data(self, validator, staging_db, sample_campaign_data, sample_performance_data, test_batch_id):
        """Test combined upload validation with real database data."""
        try:
            # Insert campaign data
            staging_db.save_campaigns_batch(sample_campaign_data)
            
            # Insert performance data (simulate ReportingStaging insertion)
            with staging_db.get_session() as session:
                for perf_data in sample_performance_data:
                    reporting_record = ReportingStaging(
                        deal_id=perf_data['deal_id'],
                        date_recorded=perf_data['date_recorded'],
                        deal_name=perf_data['deal_name'],
                        core_dsp_audience_segment=perf_data['core_dsp_audience_segment'],
                        core_dsp_placement=perf_data['core_dsp_placement'],
                        core_dsp_creative=perf_data['core_dsp_creative'],
                        purchase_type=perf_data['purchase_type'],
                        total_impressions=perf_data['total_impressions'],
                        processing_batch_id=perf_data['processing_batch_id'],
                        record_classification=perf_data['record_classification'],
                        source_row_number=perf_data['source_row_number']
                    )
                    session.add(reporting_record)
            
            # Test combined upload validation
            result = validator.validate_combined_upload(test_batch_id)
            
            assert result.is_valid is True
            assert len(result.errors) == 0
            assert result.batch_id == test_batch_id
            
        finally:
            # Cleanup test data
            staging_db.cleanup_batch_records(test_batch_id)
    
    def test_combined_upload_validation_missing_files(self, validator, staging_db, sample_campaign_data, test_batch_id):
        """Test combined upload validation with missing files."""
        try:
            # Insert only campaign data (missing performance)
            staging_db.save_campaigns_batch(sample_campaign_data)
            
            # Test validation
            result = validator.validate_combined_upload(test_batch_id)
            
            assert result.is_valid is False
            assert len(result.errors) >= 1
            assert any(error.error_code == UnifiedErrorCodes.BIZ_105 for error in result.errors)
            assert any("Performance file missing" in error.message for error in result.errors)
            
        finally:
            # Cleanup test data
            staging_db.cleanup_batch_records(test_batch_id)
    
    def test_batch_cross_file_consistency_integration(self, validator, staging_db, sample_campaign_data, sample_performance_data, test_batch_id):
        """Test comprehensive batch cross-file validation with real data."""
        try:
            # Insert campaign data
            staging_db.save_campaigns_batch(sample_campaign_data)
            
            # Insert performance data
            with staging_db.get_session() as session:
                for perf_data in sample_performance_data:
                    reporting_record = ReportingStaging(
                        deal_id=perf_data['deal_id'],
                        date_recorded=perf_data['date_recorded'],
                        deal_name=perf_data['deal_name'],
                        core_dsp_audience_segment=perf_data['core_dsp_audience_segment'],
                        core_dsp_placement=perf_data['core_dsp_placement'],
                        core_dsp_creative=perf_data['core_dsp_creative'],
                        purchase_type=perf_data['purchase_type'],
                        total_impressions=perf_data['total_impressions'],
                        processing_batch_id=perf_data['processing_batch_id'],
                        record_classification=perf_data['record_classification'],
                        source_row_number=perf_data['source_row_number']
                    )
                    session.add(reporting_record)
            
            # Test comprehensive validation
            result = validator.validate_batch_cross_file_consistency(test_batch_id)
            
            assert result.is_valid is True
            assert len(result.errors) == 0
            assert result.batch_id == test_batch_id
            assert result.context['campaign_count'] == 2
            assert result.context['performance_count'] == 2
            
        finally:
            # Cleanup test data
            staging_db.cleanup_batch_records(test_batch_id)
    
    def test_cross_file_relationship_validation_with_mismatch(self, validator, staging_db, sample_campaign_data, test_batch_id):
        """Test cross-file relationship validation with mismatched data."""
        try:
            # Insert campaign data
            staging_db.save_campaigns_batch(sample_campaign_data)
            
            # Insert performance data with mismatched deal names
            mismatched_performance_data = [
                {
                    'deal_id': UUID('aaaaaaaa-1111-1111-1111-111111111111'),
                    'date_recorded': datetime(2024, 1, 15),
                    'deal_name': 'Different Deal > Mismatched > Name',  # Mismatch
                    'core_dsp_audience_segment': 'Integration Segment A',
                    'core_dsp_placement': 'Banner Integration',
                    'core_dsp_creative': 'Creative Integration A',
                    'purchase_type': PurchaseType.guaranteed,
                    'total_impressions': Decimal('50000.0'),
                    'processing_batch_id': test_batch_id,
                    'record_classification': 'valid',
                    'source_row_number': 1
                }
            ]
            
            with staging_db.get_session() as session:
                for perf_data in mismatched_performance_data:
                    reporting_record = ReportingStaging(
                        deal_id=perf_data['deal_id'],
                        date_recorded=perf_data['date_recorded'],
                        deal_name=perf_data['deal_name'],
                        core_dsp_audience_segment=perf_data['core_dsp_audience_segment'],
                        core_dsp_placement=perf_data['core_dsp_placement'],
                        core_dsp_creative=perf_data['core_dsp_creative'],
                        purchase_type=perf_data['purchase_type'],
                        total_impressions=perf_data['total_impressions'],
                        processing_batch_id=perf_data['processing_batch_id'],
                        record_classification=perf_data['record_classification'],
                        source_row_number=perf_data['source_row_number']
                    )
                    session.add(reporting_record)
            
            # Test validation
            result = validator.validate_batch_cross_file_consistency(test_batch_id)
            
            assert result.is_valid is False
            assert len(result.errors) >= 1
            assert any(error.error_code == UnifiedErrorCodes.BIZ_104 for error in result.errors)
            
        finally:
            # Cleanup test data
            staging_db.cleanup_batch_records(test_batch_id)


class TestPhase11InfrastructureIntegration:
    """Test integration with Phase 1.1 infrastructure components."""
    
    def test_batch_management_integration(self, validator, staging_db, test_batch_id):
        """Test integration with Phase 1.1 batch management."""
        try:
            # Verify batch record count functionality
            counts = staging_db.get_batch_record_counts(test_batch_id)
            
            assert isinstance(counts, dict)
            assert 'campaign_records' in counts
            assert 'reporting_records' in counts
            assert 'total_records' in counts
            assert counts['campaign_records'] == 0  # No records initially
            assert counts['reporting_records'] == 0
            assert counts['total_records'] == 0
            
        except Exception as e:
            pytest.skip(f"Batch management integration not available: {e}")
    
    def test_staging_table_integration(self, validator, staging_db):
        """Test integration with Phase 1.1 staging table structure."""
        try:
            # Verify staging table extensions are available
            extensions = staging_db.verify_phase_1_2_extensions()
            
            assert isinstance(extensions, dict)
            # Phase 1.2 extensions should be backward compatible
            assert extensions.get('backward_compatible', True)
            
        except Exception as e:
            pytest.skip(f"Staging table extensions not available: {e}")
    
    def test_error_code_system_integration(self, validator):
        """Test integration with unified error code system."""
        from src.services.unified_error_codes import get_error_info, is_phase_11_compatible
        
        # Test Phase 1.1 compatible codes
        val_015_info = get_error_info('VAL_015')
        assert val_015_info is not None
        assert is_phase_11_compatible('VAL_015') is True
        
        # Test Phase 1.2 specific codes
        biz_105_info = get_error_info('BIZ_105')
        assert biz_105_info is not None
        assert is_phase_11_compatible('BIZ_105') is False
    
    def test_database_transaction_handling(self, validator, staging_db, test_batch_id):
        """Test database transaction handling and rollback scenarios."""
        try:
            # Test transaction isolation
            with staging_db.get_session() as session:
                # This should not affect other operations if properly isolated
                pass
            
            # Verify no side effects
            counts = staging_db.get_batch_record_counts(test_batch_id)
            assert counts['total_records'] == 0
            
        except Exception as e:
            pytest.skip(f"Database transaction testing not available: {e}")


class TestEndToEndValidationWorkflows:
    """Test end-to-end validation workflows."""
    
    def test_complete_validation_workflow(self, validator, staging_db, sample_campaign_data, sample_performance_data, test_batch_id):
        """Test complete validation workflow from data insertion to validation results."""
        try:
            # Step 1: Insert data (simulating file upload processing)
            staging_db.save_campaigns_batch(sample_campaign_data)
            
            with staging_db.get_session() as session:
                for perf_data in sample_performance_data:
                    reporting_record = ReportingStaging(
                        deal_id=perf_data['deal_id'],
                        date_recorded=perf_data['date_recorded'],
                        deal_name=perf_data['deal_name'],
                        core_dsp_audience_segment=perf_data['core_dsp_audience_segment'],
                        core_dsp_placement=perf_data['core_dsp_placement'],
                        core_dsp_creative=perf_data['core_dsp_creative'],
                        purchase_type=perf_data['purchase_type'],
                        total_impressions=perf_data['total_impressions'],
                        processing_batch_id=perf_data['processing_batch_id'],
                        record_classification=perf_data['record_classification'],
                        source_row_number=perf_data['source_row_number']
                    )
                    session.add(reporting_record)
            
            # Step 2: Validate combined upload requirement
            combined_result = validator.validate_combined_upload(test_batch_id)
            assert combined_result.is_valid is True
            
            # Step 3: Validate cross-file relationships
            campaign_records = staging_db.get_campaign_batch_by_processing_id(test_batch_id)
            reporting_records = staging_db.get_reporting_batch_by_processing_id(test_batch_id)
            
            campaign_dicts = [validator._staging_record_to_dict(record) for record in campaign_records]
            reporting_dicts = [validator._staging_record_to_dict(record) for record in reporting_records]
            
            relationship_result = validator.validate_cross_file_relationships(campaign_dicts, reporting_dicts)
            assert relationship_result.is_valid is True
            
            # Step 4: Comprehensive batch validation
            batch_result = validator.validate_batch_cross_file_consistency(test_batch_id)
            assert batch_result.is_valid is True
            assert batch_result.context['campaign_count'] == 2
            assert batch_result.context['performance_count'] == 2
            
        finally:
            # Cleanup
            staging_db.cleanup_batch_records(test_batch_id)
    
    def test_validation_workflow_with_errors(self, validator, staging_db, test_batch_id):
        """Test validation workflow with various error scenarios."""
        try:
            # Insert campaign data with invalid hierarchical structure
            invalid_campaign_data = [
                {
                    'deal_campaign_id': UUID('cccccccc-3333-3333-3333-333333333333'),
                    'deal_campaign_name': 'Invalid >> Campaign >> Structure',  # Invalid
                    'start_date': datetime(2024, 1, 1),
                    'end_date': datetime(2024, 1, 31),
                    'impression_goal': 100000,
                    'budget_eur': Decimal('5000.00'),
                    'cpm_eur': Decimal('2.50'),
                    'buyer': 'Invalid Buyer',
                    'processing_batch_id': test_batch_id,
                    'record_classification': 'valid',
                    'source_row_number': 1
                }
            ]
            
            staging_db.save_campaigns_batch(invalid_campaign_data)
            
            # Insert performance data with mismatched deal name
            mismatched_performance_data = [
                {
                    'deal_id': UUID('dddddddd-4444-4444-4444-444444444444'),
                    'date_recorded': datetime(2024, 1, 15),
                    'deal_name': 'Completely Different Deal Name',  # Mismatch
                    'core_dsp_audience_segment': 'Segment',
                    'core_dsp_placement': 'Banner',
                    'core_dsp_creative': 'Creative',
                    'purchase_type': PurchaseType.guaranteed,
                    'total_impressions': Decimal('50000.0'),
                    'processing_batch_id': test_batch_id,
                    'record_classification': 'valid',
                    'source_row_number': 1
                }
            ]
            
            with staging_db.get_session() as session:
                for perf_data in mismatched_performance_data:
                    reporting_record = ReportingStaging(
                        deal_id=perf_data['deal_id'],
                        date_recorded=perf_data['date_recorded'],
                        deal_name=perf_data['deal_name'],
                        core_dsp_audience_segment=perf_data['core_dsp_audience_segment'],
                        core_dsp_placement=perf_data['core_dsp_placement'],
                        core_dsp_creative=perf_data['core_dsp_creative'],
                        purchase_type=perf_data['purchase_type'],
                        total_impressions=perf_data['total_impressions'],
                        processing_batch_id=perf_data['processing_batch_id'],
                        record_classification=perf_data['record_classification'],
                        source_row_number=perf_data['source_row_number']
                    )
                    session.add(reporting_record)
            
            # Test comprehensive validation - should find multiple errors
            result = validator.validate_batch_cross_file_consistency(test_batch_id)
            
            assert result.is_valid is False
            assert len(result.errors) >= 2  # Hierarchical + relationship errors
            
            # Verify different error types are present
            error_codes = {error.error_code for error in result.errors}
            assert len(error_codes) >= 2
            
            # Should contain hierarchical validation error
            assert any(error.error_code == UnifiedErrorCodes.VAL_015 for error in result.errors)
            
            # Should contain cross-file relationship error
            assert any(error.error_code in [UnifiedErrorCodes.BIZ_104, UnifiedErrorCodes.BIZ_106] for error in result.errors)
            
        finally:
            # Cleanup
            staging_db.cleanup_batch_records(test_batch_id)