"""
Test suite for CrossFileValidator - Cross-file validation and relationship enforcement

Tests comprehensive cross-file validation scenarios:
1. Combined Upload Requirement (BIZ_105 error enforcement)
2. Cross-file relationship validation (Deal names, UUIDs)
3. Hierarchical name parsing (" > " structure validation)
4. Integration with Phase 1.1 file upload tracking and batch management

Following TDD principles - these tests define the expected behavior before implementation.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from uuid import UUID, uuid4
from datetime import datetime
from decimal import Decimal
import tempfile
import os

# Import the service we're testing (to be implemented)
from src.services.cross_file_validator import (
    CrossFileValidator,
    ValidationResult,
    CrossFileValidationError,
    HierarchicalNameError,
    CombinedUploadError
)
from src.services.unified_error_codes import UnifiedErrorCodes
from src.models.staging import CampaignsStaging, ReportingStaging, PurchaseType
from src.database.staging_connection import StagingDatabase


# Global fixtures for all test classes
@pytest.fixture
def mock_staging_db():
    """Mock staging database for testing."""
    mock_db = Mock(spec=StagingDatabase)
    mock_db.get_campaign_batch_by_processing_id.return_value = []
    mock_db.get_reporting_batch_by_processing_id.return_value = []
    return mock_db


@pytest.fixture
def validator(mock_staging_db):
    """CrossFileValidator instance for testing."""
    with patch('src.services.cross_file_validator.StagingDatabase', return_value=mock_staging_db):
        return CrossFileValidator()


@pytest.fixture
def sample_campaign_records():
    """Sample campaign records for testing."""
    # Use fixed UUIDs for consistent testing
    campaign_id_1 = UUID('11111111-1111-1111-1111-111111111111')
    campaign_id_2 = UUID('22222222-2222-2222-2222-222222222222')
    
    return [
        {
            'deal_campaign_id': campaign_id_1,
            'deal_campaign_name': 'Campaign > Main Campaign > Sub Campaign 1',
            'start_date': datetime(2024, 1, 1),
            'end_date': datetime(2024, 1, 31),
            'impression_goal': 100000,
            'budget_eur': Decimal('5000.00'),
            'cpm_eur': Decimal('2.50'),
            'buyer': 'Test Buyer 1',
            'processing_batch_id': uuid4(),
            'record_classification': 'valid',
            'source_row_number': 1
        },
        {
            'deal_campaign_id': campaign_id_2,
            'deal_campaign_name': 'Deal Name > Parent Deal > Child Deal',
            'start_date': datetime(2024, 2, 1),
            'end_date': datetime(2024, 2, 28),
            'impression_goal': 200000,
            'budget_eur': Decimal('8000.00'),
            'cpm_eur': Decimal('3.00'),
            'buyer': 'Test Buyer 2',
            'processing_batch_id': uuid4(),
            'record_classification': 'valid',
            'source_row_number': 2
        }
    ]


@pytest.fixture
def sample_performance_records():
    """Sample performance records for testing."""
    # Use matching UUIDs from campaign records
    deal_id_1 = UUID('11111111-1111-1111-1111-111111111111')
    deal_id_2 = UUID('22222222-2222-2222-2222-222222222222')
    
    return [
        {
            'deal_id': deal_id_1,
            'date_recorded': datetime(2024, 1, 15),
            'deal_name': 'Campaign > Main Campaign > Sub Campaign 1',
            'core_dsp_audience_segment': 'Segment A',
            'core_dsp_placement': 'Banner',
            'core_dsp_creative': 'Creative 1',
            'purchase_type': PurchaseType.guaranteed,
            'total_impressions': Decimal('50000.0'),
            'processing_batch_id': uuid4(),
            'record_classification': 'valid',
            'source_row_number': 1
        },
        {
            'deal_id': deal_id_2,
            'date_recorded': datetime(2024, 2, 10),
            'deal_name': 'Deal Name > Parent Deal > Child Deal',
            'core_dsp_audience_segment': 'Segment B',
            'core_dsp_placement': 'Video',
            'core_dsp_creative': 'Creative 2',
            'purchase_type': PurchaseType.unguaranteed,
            'total_impressions': Decimal('75000.0'),
            'processing_batch_id': uuid4(),
            'record_classification': 'valid',
            'source_row_number': 2
        }
    ]


class TestCrossFileValidator:
    """Test suite for CrossFileValidator functionality."""


class TestCombinedUploadRequirement:
    """Test combined upload requirement enforcement (BIZ_105)."""
    
    def test_validate_combined_upload_both_files_present_success(self, validator, mock_staging_db):
        """Test successful validation when both Campaign and Performance files are present."""
        batch_id = str(uuid4())
        
        # Mock both file types present
        mock_staging_db.get_campaign_batch_by_processing_id.return_value = [Mock()]  # Non-empty
        mock_staging_db.get_reporting_batch_by_processing_id.return_value = [Mock()]  # Non-empty
        
        result = validator.validate_combined_upload(batch_id)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
        assert result.batch_id == batch_id
    
    def test_validate_combined_upload_missing_campaign_file_biz_105(self, validator, mock_staging_db):
        """Test BIZ_105 error when Campaign file is missing."""
        batch_id = str(uuid4())
        
        # Mock only Performance file present
        mock_staging_db.get_campaign_batch_by_processing_id.return_value = []  # Empty
        mock_staging_db.get_reporting_batch_by_processing_id.return_value = [Mock()]  # Non-empty
        
        result = validator.validate_combined_upload(batch_id)
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].error_code == UnifiedErrorCodes.BIZ_105
        assert "Campaign file missing" in result.errors[0].message
    
    def test_validate_combined_upload_missing_performance_file_biz_105(self, validator, mock_staging_db):
        """Test BIZ_105 error when Performance file is missing."""
        batch_id = str(uuid4())
        
        # Mock only Campaign file present
        mock_staging_db.get_campaign_batch_by_processing_id.return_value = [Mock()]  # Non-empty
        mock_staging_db.get_reporting_batch_by_processing_id.return_value = []  # Empty
        
        result = validator.validate_combined_upload(batch_id)
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert result.errors[0].error_code == UnifiedErrorCodes.BIZ_105
        assert "Performance file missing" in result.errors[0].message
    
    def test_validate_combined_upload_both_files_missing_biz_105(self, validator, mock_staging_db):
        """Test BIZ_105 error when both files are missing."""
        batch_id = str(uuid4())
        
        # Mock both file types missing
        mock_staging_db.get_campaign_batch_by_processing_id.return_value = []  # Empty
        mock_staging_db.get_reporting_batch_by_processing_id.return_value = []  # Empty
        
        result = validator.validate_combined_upload(batch_id)
        
        assert result.is_valid is False
        assert len(result.errors) >= 1
        assert any(error.error_code == UnifiedErrorCodes.BIZ_105 for error in result.errors)
        assert any("both Campaign and Performance files missing" in error.message for error in result.errors)
    
    def test_validate_combined_upload_database_error_handling(self, validator, mock_staging_db):
        """Test proper error handling when database queries fail."""
        batch_id = str(uuid4())
        
        # Mock database error
        mock_staging_db.get_campaign_batch_by_processing_id.side_effect = Exception("Database connection failed")
        
        with pytest.raises(CrossFileValidationError) as exc_info:
            validator.validate_combined_upload(batch_id)
        
        assert "Database error during combined upload validation" in str(exc_info.value)


class TestCrossFileRelationshipValidation:
    """Test cross-file relationship validation between Campaign and Performance data."""
    
    def test_validate_cross_file_relationships_success(self, validator, sample_campaign_records, sample_performance_records):
        """Test successful cross-file relationship validation."""
        result = validator.validate_cross_file_relationships(sample_campaign_records, sample_performance_records)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_cross_file_relationships_exact_deal_name_matching(self, validator, sample_campaign_records):
        """Test exact Deal name matching requirement (case-sensitive)."""
        # Create performance record with slightly different deal name (case mismatch)
        performance_records = [{
            'deal_id': uuid4(),
            'date_recorded': datetime(2024, 1, 15),
            'deal_name': 'campaign > main campaign > sub campaign 1',  # lowercase 'c'
            'core_dsp_audience_segment': 'Segment A',
            'purchase_type': PurchaseType.guaranteed,
            'total_impressions': Decimal('50000.0'),
            'processing_batch_id': uuid4(),
            'record_classification': 'valid',
            'source_row_number': 1
        }]
        
        result = validator.validate_cross_file_relationships(sample_campaign_records, performance_records)
        
        assert result.is_valid is False
        assert len(result.errors) >= 1
        assert any(error.error_code == UnifiedErrorCodes.BIZ_101 for error in result.errors)
        assert any("Deal name case mismatch" in error.message for error in result.errors)
    
    def test_validate_cross_file_relationships_missing_deal_name_biz_104(self, validator, sample_campaign_records):
        """Test BIZ_104 error when Performance record has deal name not found in Campaign data."""
        # Create performance record with deal name not in campaign data
        performance_records = [{
            'deal_id': uuid4(),
            'date_recorded': datetime(2024, 1, 15),
            'deal_name': 'Nonexistent Deal > Missing > Not Found',
            'core_dsp_audience_segment': 'Segment A',
            'purchase_type': PurchaseType.guaranteed,
            'total_impressions': Decimal('50000.0'),
            'processing_batch_id': uuid4(),
            'record_classification': 'valid',
            'source_row_number': 1
        }]
        
        result = validator.validate_cross_file_relationships(sample_campaign_records, performance_records)
        
        assert result.is_valid is False
        assert len(result.errors) >= 1
        assert any(error.error_code == UnifiedErrorCodes.BIZ_104 for error in result.errors)
        assert any("Deal name not found in Campaign data" in error.message for error in result.errors)
    
    def test_validate_cross_file_relationships_uuid_validation(self, validator):
        """Test UUID relationship validation between file types."""
        matching_uuid = uuid4()
        
        campaign_records = [{
            'deal_campaign_id': matching_uuid,
            'deal_campaign_name': 'Test Campaign > Main > Sub',
            'start_date': datetime(2024, 1, 1),
            'end_date': datetime(2024, 1, 31),
            'impression_goal': 100000,
            'budget_eur': Decimal('5000.00'),
            'cpm_eur': Decimal('2.50'),
            'buyer': 'Test Buyer',
            'processing_batch_id': uuid4(),
            'record_classification': 'valid',
            'source_row_number': 1
        }]
        
        performance_records = [{
            'deal_id': matching_uuid,  # Matching UUID
            'date_recorded': datetime(2024, 1, 15),
            'deal_name': 'Test Campaign > Main > Sub',
            'core_dsp_audience_segment': 'Segment A',
            'purchase_type': PurchaseType.guaranteed,
            'total_impressions': Decimal('50000.0'),
            'processing_batch_id': uuid4(),
            'record_classification': 'valid',
            'source_row_number': 1
        }]
        
        result = validator.validate_cross_file_relationships(campaign_records, performance_records)
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_cross_file_relationships_uuid_mismatch_biz_106(self, validator):
        """Test BIZ_106 error when UUIDs don't match between files."""
        campaign_uuid = uuid4()
        performance_uuid = uuid4()  # Different UUID
        
        campaign_records = [{
            'deal_campaign_id': campaign_uuid,
            'deal_campaign_name': 'Test Campaign > Main > Sub',
            'start_date': datetime(2024, 1, 1),
            'end_date': datetime(2024, 1, 31),
            'impression_goal': 100000,
            'budget_eur': Decimal('5000.00'),
            'cpm_eur': Decimal('2.50'),
            'buyer': 'Test Buyer',
            'processing_batch_id': uuid4(),
            'record_classification': 'valid',
            'source_row_number': 1
        }]
        
        performance_records = [{
            'deal_id': performance_uuid,  # Different UUID
            'date_recorded': datetime(2024, 1, 15),
            'deal_name': 'Test Campaign > Main > Sub',  # Same name but different UUID
            'core_dsp_audience_segment': 'Segment A',
            'purchase_type': PurchaseType.guaranteed,
            'total_impressions': Decimal('50000.0'),
            'processing_batch_id': uuid4(),
            'record_classification': 'valid',
            'source_row_number': 1
        }]
        
        result = validator.validate_cross_file_relationships(campaign_records, performance_records)
        
        assert result.is_valid is False
        assert len(result.errors) >= 1
        assert any(error.error_code == UnifiedErrorCodes.BIZ_106 for error in result.errors)
        assert any("UUID mismatch" in error.message for error in result.errors)


class TestHierarchicalNameParsing:
    """Test hierarchical name parsing and " > " structure validation."""
    
    def test_validate_hierarchical_names_valid_structure(self, validator):
        """Test validation of valid hierarchical name structure with " > " separators."""
        records = [
            {'deal_campaign_name': 'Level1 > Level2 > Level3'},
            {'deal_campaign_name': 'Campaign > Main Campaign > Sub Campaign'},
            {'deal_campaign_name': 'Deal > Parent > Child > Grandchild'}
        ]
        
        errors = validator.validate_hierarchical_names(records)
        
        assert len(errors) == 0
    
    def test_validate_hierarchical_names_invalid_structure_val_015(self, validator):
        """Test VAL_015 error for invalid hierarchical structure."""
        records = [
            {'deal_campaign_name': 'Level1 >> Level2 > Level3'},  # Double ">>"
            {'deal_campaign_name': 'Campaign > > Sub Campaign'},   # Empty middle segment
            {'deal_campaign_name': 'Level1 > '}                   # Trailing separator
        ]
        
        errors = validator.validate_hierarchical_names(records)
        
        assert len(errors) >= 3
        assert all(error.error_code == UnifiedErrorCodes.VAL_015 for error in errors)
        assert any("Invalid hierarchical structure" in error.message for error in errors)
    
    def test_validate_hierarchical_names_missing_separators(self, validator):
        """Test handling of names without hierarchical structure."""
        records = [
            {'deal_campaign_name': 'Simple Campaign Name'},
            {'deal_campaign_name': 'Another Campaign'}
        ]
        
        errors = validator.validate_hierarchical_names(records)
        
        # Should not fail - simple names are allowed
        assert len(errors) == 0
    
    def test_validate_hierarchical_names_campaign_name_extraction(self, validator):
        """Test campaign name segment extraction from hierarchical structure."""
        records = [
            {'deal_campaign_name': 'Level1 > Level2 > FinalCampaign'},
            {'deal_campaign_name': 'Parent > ChildCampaign'}
        ]
        
        # This test would verify internal logic for extracting the last segment
        # Implementation should extract "FinalCampaign" and "ChildCampaign"
        errors = validator.validate_hierarchical_names(records)
        
        assert len(errors) == 0
    
    def test_validate_hierarchical_names_whitespace_handling(self, validator):
        """Test proper whitespace handling in hierarchical names."""
        records = [
            {'deal_campaign_name': ' Level1 > Level2 > Level3 '},      # Leading/trailing spaces
            {'deal_campaign_name': 'Level1>Level2>Level3'},            # No spaces around separators
            {'deal_campaign_name': 'Level1  >  Level2  >  Level3'}     # Multiple spaces
        ]
        
        errors = validator.validate_hierarchical_names(records)
        
        # Implementation should handle whitespace normalization
        assert len(errors) == 0


class TestPhaseIntegration:
    """Test integration with Phase 1.1 infrastructure and batch management."""
    
    def test_integration_with_processing_batches_table(self, validator, mock_staging_db):
        """Test integration with shared processing_batches table."""
        batch_id = str(uuid4())
        
        # Mock successful batch retrieval
        mock_staging_db.get_campaign_batch_by_processing_id.return_value = [Mock()]
        mock_staging_db.get_reporting_batch_by_processing_id.return_value = [Mock()]
        
        result = validator.validate_combined_upload(batch_id)
        
        # Verify database methods were called with correct batch_id
        mock_staging_db.get_campaign_batch_by_processing_id.assert_called_once_with(batch_id)
        mock_staging_db.get_reporting_batch_by_processing_id.assert_called_once_with(batch_id)
        
        assert result.is_valid is True
    
    def test_reuse_of_phase_11_upload_tracking(self, validator):
        """Test reuse of Phase 1.1 file upload tracking infrastructure."""
        # This test verifies that the validator properly integrates with existing upload tracking
        # without duplicating functionality
        
        # Create validator with custom database URL (Phase 1.1 pattern)
        custom_db_url = "postgresql://test_user@localhost:5432/test_db"
        validator_with_custom_db = CrossFileValidator(staging_db_url=custom_db_url)
        
        # Verify it can be instantiated with custom database configuration
        assert validator_with_custom_db is not None
    
    def test_batch_management_coordination(self, validator, mock_staging_db):
        """Test coordination with Phase 1.1 batch management."""
        batch_id = str(uuid4())
        
        # Mock batch record counts
        mock_staging_db.get_batch_record_counts.return_value = {
            "campaign_records": 5,
            "reporting_records": 10,
            "total_records": 15
        }
        
        # This would test integration with existing batch management
        result = validator.validate_combined_upload(batch_id)
        
        assert result.batch_id == batch_id
    
    def test_error_code_compatibility_with_phase_11(self, validator):
        """Test error code compatibility with Phase 1.1 system."""
        # Verify that Phase 1.1 compatible error codes are properly used
        from src.services.unified_error_codes import is_phase_11_compatible
        
        # VAL_015 should be compatible with Phase 1.1
        assert is_phase_11_compatible('VAL_015') is True
        
        # BIZ_105 should be Phase 1.2 specific
        assert is_phase_11_compatible('BIZ_105') is False


class TestErrorHandlingAndRollback:
    """Test comprehensive error handling and rollback scenarios."""
    
    def test_validation_error_aggregation(self, validator):
        """Test proper aggregation of multiple validation errors."""
        campaign_records = [
            {
                'deal_campaign_name': 'Invalid >> Structure',  # VAL_015 error
                'source_row_number': 1
            }
        ]
        
        performance_records = [
            {
                'deal_name': 'Nonexistent Deal',  # BIZ_104 error
                'source_row_number': 1
            }
        ]
        
        result = validator.validate_cross_file_relationships(campaign_records, performance_records)
        
        assert result.is_valid is False
        assert len(result.errors) >= 2  # Multiple error types
        
        # Verify different error codes are present
        error_codes = {error.error_code for error in result.errors}
        assert len(error_codes) >= 2  # Multiple different error types
    
    def test_database_transaction_rollback(self, validator, mock_staging_db):
        """Test proper database transaction rollback on validation failure."""
        batch_id = str(uuid4())
        
        # Mock partial success followed by failure
        mock_staging_db.get_campaign_batch_by_processing_id.return_value = [Mock()]
        mock_staging_db.get_reporting_batch_by_processing_id.side_effect = Exception("Database error")
        
        with pytest.raises(CrossFileValidationError):
            validator.validate_combined_upload(batch_id)
        
        # Verify proper error handling and no partial state corruption
        assert mock_staging_db.get_campaign_batch_by_processing_id.called
    
    def test_comprehensive_error_context(self, validator):
        """Test that validation errors include comprehensive context information."""
        records = [
            {'deal_campaign_name': 'Invalid >> Structure', 'source_row_number': 5}
        ]
        
        errors = validator.validate_hierarchical_names(records)
        
        assert len(errors) >= 1
        error = errors[0]
        
        # Verify error includes context
        assert hasattr(error, 'context')
        assert hasattr(error, 'source_row_number')
        assert error.source_row_number == 5


# Integration helper fixtures for complex test scenarios
@pytest.fixture
def complex_cross_file_scenario():
    """Complex scenario with multiple campaigns and performance records."""
    batch_id = uuid4()
    
    campaign_id_1 = uuid4()
    campaign_id_2 = uuid4()
    campaign_id_3 = uuid4()
    
    campaigns = [
        {
            'deal_campaign_id': campaign_id_1,
            'deal_campaign_name': 'Brand A > Campaign 2024 > Q1 Launch',
            'processing_batch_id': batch_id,
            'source_row_number': 1
        },
        {
            'deal_campaign_id': campaign_id_2,
            'deal_campaign_name': 'Brand B > Retargeting > Mobile Focus',
            'processing_batch_id': batch_id,
            'source_row_number': 2
        },
        {
            'deal_campaign_id': campaign_id_3,
            'deal_campaign_name': 'Brand A > Campaign 2024 > Q2 Extension',
            'processing_batch_id': batch_id,
            'source_row_number': 3
        }
    ]
    
    performance = [
        {
            'deal_id': campaign_id_1,
            'deal_name': 'Brand A > Campaign 2024 > Q1 Launch',
            'processing_batch_id': batch_id,
            'source_row_number': 1
        },
        {
            'deal_id': campaign_id_2,
            'deal_name': 'Brand B > Retargeting > Mobile Focus',
            'processing_batch_id': batch_id,
            'source_row_number': 2
        },
        {
            'deal_id': campaign_id_3,
            'deal_name': 'Brand A > Campaign 2024 > Q2 Extension',
            'processing_batch_id': batch_id,
            'source_row_number': 3
        }
    ]
    
    return {
        'batch_id': str(batch_id),
        'campaigns': campaigns,
        'performance': performance
    }


class TestComplexCrossFileScenarios:
    """Test complex cross-file validation scenarios."""
    
    def test_complex_successful_validation(self, validator, complex_cross_file_scenario):
        """Test successful validation of complex cross-file scenario."""
        scenario = complex_cross_file_scenario
        
        result = validator.validate_cross_file_relationships(
            scenario['campaigns'], 
            scenario['performance']
        )
        
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_complex_partial_failure_scenario(self, validator, complex_cross_file_scenario):
        """Test partial failure scenario with some valid and some invalid relationships."""
        scenario = complex_cross_file_scenario
        
        # Modify one performance record to have mismatched deal name
        scenario['performance'][1]['deal_name'] = 'Brand B > Different Campaign > Mobile Focus'
        
        result = validator.validate_cross_file_relationships(
            scenario['campaigns'], 
            scenario['performance']
        )
        
        assert result.is_valid is False
        assert len(result.errors) >= 1
        
        # Verify specific record error context
        assert any(error.source_row_number == 2 for error in result.errors)