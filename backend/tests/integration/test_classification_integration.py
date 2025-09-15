"""
Integration tests for Classification Integration Service

Tests the complete workflow:
1. Creating staging records
2. Running classification engine
3. Updating staging records with results
4. Cross-file consistency validation
"""
import pytest
from datetime import datetime
from decimal import Decimal
from uuid import uuid4
from unittest.mock import patch, Mock

from src.services.classification_integration_service import ClassificationIntegrationService
from src.services.record_classification_engine import (
    RecordClassificationEngine,
    ClassificationResult,
    ClassificationCategory,
    ProductionRecord
)
from src.database.staging_connection import StagingDatabase
from src.models.staging import CampaignsStaging, ReportingStaging, PurchaseType


class TestClassificationIntegration:
    """Integration tests for classification workflow."""
    
    @pytest.fixture
    def integration_service(self):
        """Create classification integration service for testing."""
        return ClassificationIntegrationService()
    
    @pytest.fixture
    def processing_batch_id(self):
        """Create a processing batch ID for testing."""
        return uuid4()
    
    @pytest.fixture
    def sample_campaign_records(self, processing_batch_id):
        """Create sample campaign staging records."""
        return [
            CampaignsStaging(
                deal_campaign_id=uuid4(),
                deal_campaign_name="Test Campaign 1",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 12, 31),
                impression_goal=100000,
                budget_eur=Decimal('5000.00'),
                cpm_eur=Decimal('2.50'),
                buyer="Test Buyer 1",
                processing_batch_id=processing_batch_id,
                record_classification="pending",
                source_row_number=1
            ),
            CampaignsStaging(
                deal_campaign_id=uuid4(),
                deal_campaign_name="Test Campaign 2",
                start_date=datetime(2024, 2, 1),
                end_date=datetime(2024, 11, 30),
                impression_goal=150000,
                budget_eur=Decimal('7500.00'),
                cpm_eur=Decimal('3.00'),
                buyer="Test Buyer 2",
                processing_batch_id=processing_batch_id,
                record_classification="pending",
                source_row_number=2
            )
        ]
    
    @pytest.fixture
    def sample_reporting_records(self, processing_batch_id):
        """Create sample reporting staging records."""
        return [
            ReportingStaging(
                deal_id=uuid4(),
                date_recorded=datetime(2024, 6, 15),
                deal_name="Test Deal 1",
                core_dsp_audience_segment="Test Segment 1",
                core_dsp_placement="Test Placement 1",
                core_dsp_creative="Test Creative 1",
                purchase_type=PurchaseType.guaranteed,
                total_impressions=Decimal('50000.00'),
                processing_batch_id=processing_batch_id,
                record_classification="pending",
                source_row_number=1
            ),
            ReportingStaging(
                deal_id=uuid4(),
                date_recorded=datetime(2024, 7, 15),
                deal_name="Test Deal 2",
                core_dsp_audience_segment="Test Segment 2",
                core_dsp_placement="Test Placement 2",
                core_dsp_creative="Test Creative 2",
                purchase_type=PurchaseType.unguaranteed,
                total_impressions=Decimal('75000.00'),
                processing_batch_id=processing_batch_id,
                record_classification="pending",
                source_row_number=2
            )
        ]
    
    def test_campaign_batch_classification_workflow(self, integration_service, processing_batch_id, sample_campaign_records):
        """Test complete campaign batch classification workflow."""
        # Mock staging database operations
        with patch.object(integration_service.staging_db, 'get_campaign_batch_by_processing_id') as mock_get_campaigns:
            with patch.object(integration_service.staging_db, 'update_campaign_classification') as mock_update_campaign:
                with patch.object(integration_service.classification_engine, 'classify_campaign_batch') as mock_classify:
                    
                    # Arrange
                    mock_get_campaigns.return_value = sample_campaign_records
                    
                    # Mock classification results
                    mock_results = [
                        ClassificationResult(
                            uuid=sample_campaign_records[0].deal_campaign_id,
                            category=ClassificationCategory.NEW,
                            reason="UUID not found in production database",
                            source_row_number=1
                        ),
                        ClassificationResult(
                            uuid=sample_campaign_records[1].deal_campaign_id,
                            category=ClassificationCategory.UPDATED,
                            reason="Acceptable changes to: impression_goal",
                            changes=[{
                                'field': 'impression_goal',
                                'old_value': 120000,
                                'new_value': 150000,
                                'is_restricted': False
                            }],
                            source_row_number=2
                        )
                    ]
                    
                    from src.services.record_classification_engine import BatchClassificationResult
                    mock_classify.return_value = BatchClassificationResult(
                        results=mock_results,
                        total_processed=2,
                        categories_summary={
                            ClassificationCategory.NEW: 1,
                            ClassificationCategory.UPDATED: 1
                        }
                    )
                    
                    # Act
                    result = integration_service.classify_campaign_batch(processing_batch_id)
                    
                    # Assert
                    assert result.total_processed == 2
                    assert result.categories_summary[ClassificationCategory.NEW] == 1
                    assert result.categories_summary[ClassificationCategory.UPDATED] == 1
                    assert len(result.processing_errors) == 0
                    
                    # Verify staging database was called correctly
                    mock_get_campaigns.assert_called_once_with(str(processing_batch_id))
                    assert mock_update_campaign.call_count == 2
                    
                    # Verify classification engine was called with correct records
                    mock_classify.assert_called_once_with(sample_campaign_records)
    
    def test_reporting_batch_classification_workflow(self, integration_service, processing_batch_id, sample_reporting_records):
        """Test complete reporting batch classification workflow."""
        # Mock staging database operations
        with patch.object(integration_service.staging_db, 'get_reporting_batch_by_processing_id') as mock_get_reporting:
            with patch.object(integration_service.staging_db, 'update_reporting_classification') as mock_update_reporting:
                with patch.object(integration_service.classification_engine, 'classify_reporting_record') as mock_classify:
                    
                    # Arrange
                    mock_get_reporting.return_value = sample_reporting_records
                    
                    # Mock classification results
                    mock_results = [
                        ClassificationResult(
                            uuid=sample_reporting_records[0].deal_id,
                            category=ClassificationCategory.UNCHANGED,
                            reason="Record is identical to production data",
                            source_row_number=1
                        ),
                        ClassificationResult(
                            uuid=sample_reporting_records[1].deal_id,
                            category=ClassificationCategory.INCONSISTENT,
                            reason="Changes to restricted fields: deal_name",
                            changes=[{
                                'field': 'deal_name',
                                'old_value': 'Original Deal Name',
                                'new_value': 'Test Deal 2',
                                'is_restricted': True
                            }],
                            source_row_number=2
                        )
                    ]
                    
                    mock_classify.side_effect = mock_results
                    
                    # Act
                    result = integration_service.classify_reporting_batch(processing_batch_id)
                    
                    # Assert
                    assert result.total_processed == 2
                    assert result.categories_summary[ClassificationCategory.UNCHANGED] == 1
                    assert result.categories_summary[ClassificationCategory.INCONSISTENT] == 1
                    assert len(result.processing_errors) == 0
                    
                    # Verify staging database was called correctly
                    mock_get_reporting.assert_called_once_with(str(processing_batch_id))
                    assert mock_update_reporting.call_count == 2
                    
                    # Verify classification engine was called for each record
                    assert mock_classify.call_count == 2
    
    def test_complete_batch_classification_with_cross_file_validation(self, integration_service, processing_batch_id, 
                                                                    sample_campaign_records, sample_reporting_records):
        """Test complete batch classification including cross-file consistency validation."""
        # Mock all staging database operations
        with patch.object(integration_service.staging_db, 'get_campaign_batch_by_processing_id') as mock_get_campaigns:
            with patch.object(integration_service.staging_db, 'get_reporting_batch_by_processing_id') as mock_get_reporting:
                with patch.object(integration_service.staging_db, 'update_campaign_classification'):
                    with patch.object(integration_service.staging_db, 'update_reporting_classification'):
                        with patch.object(integration_service.classification_engine, 'classify_campaign_batch') as mock_classify_campaigns:
                            with patch.object(integration_service.classification_engine, 'classify_reporting_record') as mock_classify_reporting:
                                with patch.object(integration_service.classification_engine, 'validate_cross_file_consistency') as mock_validate:
                                    
                                    # Arrange
                                    mock_get_campaigns.return_value = sample_campaign_records
                                    mock_get_reporting.return_value = sample_reporting_records
                                    
                                    # Mock campaign classification results
                                    from src.services.record_classification_engine import BatchClassificationResult
                                    mock_classify_campaigns.return_value = BatchClassificationResult(
                                        results=[
                                            ClassificationResult(
                                                uuid=sample_campaign_records[0].deal_campaign_id,
                                                category=ClassificationCategory.NEW,
                                                reason="New campaign",
                                                source_row_number=1
                                            )
                                        ],
                                        total_processed=1,
                                        categories_summary={ClassificationCategory.NEW: 1}
                                    )
                                    
                                    # Mock reporting classification results
                                    mock_classify_reporting.return_value = ClassificationResult(
                                        uuid=sample_reporting_records[0].deal_id,
                                        category=ClassificationCategory.UNCHANGED,
                                        reason="Unchanged reporting",
                                        source_row_number=1
                                    )
                                    
                                    # Mock cross-file consistency results
                                    from src.services.record_classification_engine import CrossFileConsistencyResult
                                    mock_validate.return_value = CrossFileConsistencyResult(
                                        validation_errors=[],
                                        warnings=["Found 1 reporting record without corresponding campaign"]
                                    )
                                    
                                    # Act
                                    result = integration_service.classify_complete_batch(processing_batch_id)
                                    
                                    # Assert
                                    assert result['processing_batch_id'] == str(processing_batch_id)
                                    assert result['campaign_classification']['total_processed'] == 1
                                    assert result['reporting_classification']['total_processed'] == 2
                                    assert len(result['cross_file_consistency']['warnings']) == 1
                                    assert result['overall_success'] is True
                                    
                                    # Verify cross-file validation was called
                                    mock_validate.assert_called_once_with(sample_campaign_records, sample_reporting_records)
    
    def test_classification_handles_empty_batch(self, integration_service, processing_batch_id):
        """Test classification handles empty processing batch gracefully."""
        # Mock empty batch
        with patch.object(integration_service.staging_db, 'get_campaign_batch_by_processing_id') as mock_get_campaigns:
            mock_get_campaigns.return_value = []
            
            # Act
            result = integration_service.classify_campaign_batch(processing_batch_id)
            
            # Assert
            assert result.total_processed == 0
            assert len(result.processing_errors) == 1
            assert "No campaign records found" in result.processing_errors[0]
    
    def test_classification_handles_database_errors(self, integration_service, processing_batch_id):
        """Test classification handles database errors gracefully."""
        # Mock database error
        with patch.object(integration_service.staging_db, 'get_campaign_batch_by_processing_id') as mock_get_campaigns:
            mock_get_campaigns.side_effect = Exception("Database connection failed")
            
            # Act
            result = integration_service.classify_campaign_batch(processing_batch_id)
            
            # Assert
            assert result.total_processed == 0
            assert len(result.processing_errors) == 1
            assert "Database connection failed" in result.processing_errors[0]
    
    def test_get_classification_summary(self, integration_service, processing_batch_id, sample_campaign_records, sample_reporting_records):
        """Test getting classification summary for a processing batch."""
        # Update records with classification results
        sample_campaign_records[0].record_classification = "new"
        sample_campaign_records[1].record_classification = "updated"
        sample_reporting_records[0].record_classification = "unchanged"
        sample_reporting_records[1].record_classification = "inconsistent"
        
        # Mock staging database operations
        with patch.object(integration_service.staging_db, 'get_campaign_batch_by_processing_id') as mock_get_campaigns:
            with patch.object(integration_service.staging_db, 'get_reporting_batch_by_processing_id') as mock_get_reporting:
                mock_get_campaigns.return_value = sample_campaign_records
                mock_get_reporting.return_value = sample_reporting_records
                
                # Act
                result = integration_service.get_classification_summary(processing_batch_id)
                
                # Assert
                assert result['processing_batch_id'] == str(processing_batch_id)
                assert result['campaign_records']['total'] == 2
                assert result['campaign_records']['categories']['new'] == 1
                assert result['campaign_records']['categories']['updated'] == 1
                assert result['reporting_records']['total'] == 2
                assert result['reporting_records']['categories']['unchanged'] == 1
                assert result['reporting_records']['categories']['inconsistent'] == 1