"""
Comprehensive test cases for Record Classification Engine (TDD Implementation)

Tests cover all 4 classification categories:
- New Entries: UUID not found in production database
- Updated Entries: UUID exists with acceptable changes (Total Impressions only)
- Unchanged Records: Identical data to production
- Inconsistent Data: Changes to restricted fields

Production Database Optimization:
- Batch UUID lookups (500 records per query maximum)
- Connection pooling with read-only transactions
- Query result caching for duplicate UUIDs within same batch
"""
import pytest
from datetime import datetime
from decimal import Decimal
from uuid import uuid4, UUID
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any, Optional

from src.services.record_classification_engine import (
    RecordClassificationEngine,
    ClassificationResult,
    BatchClassificationResult,
    ProductionRecord,
    ClassificationCategory
)
from src.models.staging import CampaignsStaging, ReportingStaging, PurchaseType


class TestRecordClassificationEngine:
    """Test suite for Record Classification Engine with comprehensive TDD coverage."""
    
    @pytest.fixture
    def classification_engine(self):
        """Create classification engine instance for testing."""
        return RecordClassificationEngine()
    
    @pytest.fixture
    def sample_campaign_staging_record(self):
        """Create sample campaign staging record for testing."""
        return CampaignsStaging(
            deal_campaign_id=uuid4(),
            deal_campaign_name="Test Campaign",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            impression_goal=100000,
            budget_eur=Decimal('5000.00'),
            cpm_eur=Decimal('2.50'),
            buyer="Test Buyer",
            processing_batch_id=uuid4(),
            record_classification="pending",
            source_row_number=1
        )
    
    @pytest.fixture
    def sample_reporting_staging_record(self):
        """Create sample reporting staging record for testing."""
        return ReportingStaging(
            deal_id=uuid4(),
            date_recorded=datetime(2024, 6, 15),
            deal_name="Test Deal",
            core_dsp_audience_segment="Test Segment",
            core_dsp_placement="Test Placement",
            core_dsp_creative="Test Creative",
            purchase_type=PurchaseType.guaranteed,
            total_impressions=Decimal('50000.00'),
            processing_batch_id=uuid4(),
            record_classification="pending",
            source_row_number=1
        )
    
    @pytest.fixture
    def sample_production_campaign_record(self):
        """Create sample production campaign record for testing."""
        return ProductionRecord(
            uuid=uuid4(),
            data={
                'deal_campaign_name': 'Test Campaign',
                'start_date': datetime(2024, 1, 1),
                'end_date': datetime(2024, 12, 31),
                'impression_goal': 100000,
                'budget_eur': Decimal('5000.00'),
                'cpm_eur': Decimal('2.50'),
                'buyer': 'Test Buyer'
            }
        )
    
    # Test Category 1: New Entries (UUID not found in production)
    def test_classify_new_campaign_entry_uuid_not_found(self, classification_engine, sample_campaign_staging_record):
        """Test classification of new campaign entry - UUID not found in production."""
        # Arrange: Mock production lookup to return None (not found)
        with patch.object(classification_engine, '_batch_lookup_production_records') as mock_lookup:
            mock_lookup.return_value = {}  # Empty dict = no records found
            
            # Act
            result = classification_engine.classify_campaign_record(sample_campaign_staging_record)
            
            # Assert
            assert result.category == ClassificationCategory.NEW
            assert result.uuid == sample_campaign_staging_record.deal_campaign_id
            assert result.changes == []
            assert result.validation_errors == []
            assert "UUID not found in production database" in result.reason
    
    def test_classify_new_reporting_entry_uuid_not_found(self, classification_engine, sample_reporting_staging_record):
        """Test classification of new reporting entry - UUID not found in production."""
        # Arrange: Mock production lookup to return None
        with patch.object(classification_engine, '_batch_lookup_production_records') as mock_lookup:
            mock_lookup.return_value = {}
            
            # Act
            result = classification_engine.classify_reporting_record(sample_reporting_staging_record)
            
            # Assert
            assert result.category == ClassificationCategory.NEW
            assert result.uuid == sample_reporting_staging_record.deal_id
            assert result.changes == []
            assert "UUID not found in production database" in result.reason
    
    # Test Category 2: Updated Entries (UUID exists with acceptable changes)
    def test_classify_updated_campaign_acceptable_changes(self, classification_engine, sample_campaign_staging_record):
        """Test classification of updated campaign - only Total Impressions changed (acceptable)."""
        # Arrange: Mock production record with different impression goal (acceptable change)
        production_record = ProductionRecord(
            uuid=sample_campaign_staging_record.deal_campaign_id,
            data={
                'deal_campaign_name': sample_campaign_staging_record.deal_campaign_name,
                'start_date': sample_campaign_staging_record.start_date,
                'end_date': sample_campaign_staging_record.end_date,
                'impression_goal': 80000,  # Different from staging (100000) - acceptable
                'budget_eur': sample_campaign_staging_record.budget_eur,
                'cpm_eur': sample_campaign_staging_record.cpm_eur,
                'buyer': sample_campaign_staging_record.buyer
            }
        )
        
        with patch.object(classification_engine, '_batch_lookup_production_records') as mock_lookup:
            mock_lookup.return_value = {sample_campaign_staging_record.deal_campaign_id: production_record}
            
            # Act
            result = classification_engine.classify_campaign_record(sample_campaign_staging_record)
            
            # Assert
            assert result.category == ClassificationCategory.UPDATED
            assert result.uuid == sample_campaign_staging_record.deal_campaign_id
            assert len(result.changes) == 1
            assert result.changes[0]['field'] == 'impression_goal'
            assert result.changes[0]['old_value'] == 80000
            assert result.changes[0]['new_value'] == 100000
            assert "acceptable changes" in result.reason.lower()
    
    def test_classify_updated_reporting_acceptable_changes(self, classification_engine, sample_reporting_staging_record):
        """Test classification of updated reporting - only Total Impressions changed (acceptable)."""
        # Arrange: Mock production record with different total impressions
        production_record = ProductionRecord(
            uuid=sample_reporting_staging_record.deal_id,
            data={
                'date_recorded': sample_reporting_staging_record.date_recorded,
                'deal_name': sample_reporting_staging_record.deal_name,
                'core_dsp_audience_segment': sample_reporting_staging_record.core_dsp_audience_segment,
                'core_dsp_placement': sample_reporting_staging_record.core_dsp_placement,
                'core_dsp_creative': sample_reporting_staging_record.core_dsp_creative,
                'purchase_type': sample_reporting_staging_record.purchase_type,
                'total_impressions': Decimal('40000.00')  # Different from staging (50000) - acceptable
            }
        )
        
        with patch.object(classification_engine, '_batch_lookup_production_records') as mock_lookup:
            mock_lookup.return_value = {sample_reporting_staging_record.deal_id: production_record}
            
            # Act
            result = classification_engine.classify_reporting_record(sample_reporting_staging_record)
            
            # Assert
            assert result.category == ClassificationCategory.UPDATED
            assert len(result.changes) == 1
            assert result.changes[0]['field'] == 'total_impressions'
            assert result.changes[0]['old_value'] == Decimal('40000.00')
            assert result.changes[0]['new_value'] == Decimal('50000.00')
    
    # Test Category 3: Unchanged Records (Identical data to production)
    def test_classify_unchanged_campaign_identical_data(self, classification_engine, sample_campaign_staging_record):
        """Test classification of unchanged campaign - identical to production data."""
        # Arrange: Mock production record identical to staging
        production_record = ProductionRecord(
            uuid=sample_campaign_staging_record.deal_campaign_id,
            data={
                'deal_campaign_name': sample_campaign_staging_record.deal_campaign_name,
                'start_date': sample_campaign_staging_record.start_date,
                'end_date': sample_campaign_staging_record.end_date,
                'impression_goal': sample_campaign_staging_record.impression_goal,
                'budget_eur': sample_campaign_staging_record.budget_eur,
                'cpm_eur': sample_campaign_staging_record.cpm_eur,
                'buyer': sample_campaign_staging_record.buyer
            }
        )
        
        with patch.object(classification_engine, '_batch_lookup_production_records') as mock_lookup:
            mock_lookup.return_value = {sample_campaign_staging_record.deal_campaign_id: production_record}
            
            # Act
            result = classification_engine.classify_campaign_record(sample_campaign_staging_record)
            
            # Assert
            assert result.category == ClassificationCategory.UNCHANGED
            assert result.changes == []
            assert "identical to production" in result.reason.lower()
    
    def test_classify_unchanged_reporting_identical_data(self, classification_engine, sample_reporting_staging_record):
        """Test classification of unchanged reporting - identical to production data."""
        # Arrange: Mock production record identical to staging
        production_record = ProductionRecord(
            uuid=sample_reporting_staging_record.deal_id,
            data={
                'date_recorded': sample_reporting_staging_record.date_recorded,
                'deal_name': sample_reporting_staging_record.deal_name,
                'core_dsp_audience_segment': sample_reporting_staging_record.core_dsp_audience_segment,
                'core_dsp_placement': sample_reporting_staging_record.core_dsp_placement,
                'core_dsp_creative': sample_reporting_staging_record.core_dsp_creative,
                'purchase_type': sample_reporting_staging_record.purchase_type,
                'total_impressions': sample_reporting_staging_record.total_impressions
            }
        )
        
        with patch.object(classification_engine, '_batch_lookup_production_records') as mock_lookup:
            mock_lookup.return_value = {sample_reporting_staging_record.deal_id: production_record}
            
            # Act
            result = classification_engine.classify_reporting_record(sample_reporting_staging_record)
            
            # Assert
            assert result.category == ClassificationCategory.UNCHANGED
            assert result.changes == []
    
    # Test Category 4: Inconsistent Data (Changes to restricted fields)
    def test_classify_inconsistent_campaign_restricted_field_changes(self, classification_engine, sample_campaign_staging_record):
        """Test classification of inconsistent campaign - restricted field changes."""
        # Test each restricted field: Deal/Campaign Name, Runtime, Budget, CPM, Buyer
        restricted_fields_tests = [
            ('deal_campaign_name', 'Different Campaign Name'),
            ('start_date', datetime(2024, 2, 1)),  # Runtime change
            ('end_date', datetime(2024, 11, 30)),  # Runtime change
            ('budget_eur', Decimal('6000.00')),
            ('cpm_eur', Decimal('3.00')),
            ('buyer', 'Different Buyer')
        ]
        
        for field_name, new_value in restricted_fields_tests:
            # Arrange: Production record with different restricted field
            production_data = {
                'deal_campaign_name': sample_campaign_staging_record.deal_campaign_name,
                'start_date': sample_campaign_staging_record.start_date,
                'end_date': sample_campaign_staging_record.end_date,
                'impression_goal': sample_campaign_staging_record.impression_goal,
                'budget_eur': sample_campaign_staging_record.budget_eur,
                'cpm_eur': sample_campaign_staging_record.cpm_eur,
                'buyer': sample_campaign_staging_record.buyer
            }
            production_data[field_name] = new_value  # Change the restricted field
            
            production_record = ProductionRecord(
                uuid=sample_campaign_staging_record.deal_campaign_id,
                data=production_data
            )
            
            with patch.object(classification_engine, '_batch_lookup_production_records') as mock_lookup:
                mock_lookup.return_value = {sample_campaign_staging_record.deal_campaign_id: production_record}
                
                # Act
                result = classification_engine.classify_campaign_record(sample_campaign_staging_record)
                
                # Assert
                assert result.category == ClassificationCategory.INCONSISTENT, f"Field {field_name} should be inconsistent"
                assert len(result.changes) >= 1
                assert any(change['field'] == field_name for change in result.changes)
                assert "restricted field" in result.reason.lower()
    
    def test_classify_inconsistent_reporting_restricted_field_changes(self, classification_engine, sample_reporting_staging_record):
        """Test classification of inconsistent reporting - restricted field changes."""
        # Test restricted fields: Deal Name, Purchase Type
        restricted_fields_tests = [
            ('deal_name', 'Different Deal Name'),
            ('purchase_type', PurchaseType.unguaranteed)
        ]
        
        for field_name, new_value in restricted_fields_tests:
            # Arrange: Production record with different restricted field
            production_data = {
                'date_recorded': sample_reporting_staging_record.date_recorded,
                'deal_name': sample_reporting_staging_record.deal_name,
                'core_dsp_audience_segment': sample_reporting_staging_record.core_dsp_audience_segment,
                'core_dsp_placement': sample_reporting_staging_record.core_dsp_placement,
                'core_dsp_creative': sample_reporting_staging_record.core_dsp_creative,
                'purchase_type': sample_reporting_staging_record.purchase_type,
                'total_impressions': sample_reporting_staging_record.total_impressions
            }
            production_data[field_name] = new_value
            
            production_record = ProductionRecord(
                uuid=sample_reporting_staging_record.deal_id,
                data=production_data
            )
            
            with patch.object(classification_engine, '_batch_lookup_production_records') as mock_lookup:
                mock_lookup.return_value = {sample_reporting_staging_record.deal_id: production_record}
                
                # Act
                result = classification_engine.classify_reporting_record(sample_reporting_staging_record)
                
                # Assert
                assert result.category == ClassificationCategory.INCONSISTENT
                assert len(result.changes) >= 1
                assert any(change['field'] == field_name for change in result.changes)
    
    # Test Production Database Optimization
    def test_batch_uuid_lookup_optimization_500_records_per_query(self, classification_engine):
        """Test batch UUID lookup optimization - max 500 records per query."""
        # Arrange: Create 1200 UUIDs (should result in 3 queries: 500, 500, 200)
        uuids = [uuid4() for _ in range(1200)]
        
        with patch.object(classification_engine, '_execute_production_query') as mock_query:
            mock_query.return_value = []  # Empty results for test
            
            # Act
            classification_engine._batch_lookup_production_records(uuids, 'campaigns')
            
            # Assert: Should have made 3 calls (1200 / 500 = 2.4 -> 3 calls)
            assert mock_query.call_count == 3
            
            # Verify batch sizes
            call_args_list = mock_query.call_args_list
            assert len(call_args_list[0][0][0]) == 500  # First batch
            assert len(call_args_list[1][0][0]) == 500  # Second batch
            assert len(call_args_list[2][0][0]) == 200  # Third batch
    
    def test_batch_uuid_lookup_caching_duplicate_uuids(self, classification_engine):
        """Test UUID lookup caching for duplicate UUIDs within same batch."""
        # Arrange: Create list with duplicate UUIDs
        uuid1 = uuid4()
        uuid2 = uuid4()
        uuids = [uuid1, uuid2, uuid1, uuid2, uuid1]  # 3 duplicates of uuid1, 2 of uuid2
        
        production_records = [
            ProductionRecord(uuid=uuid1, data={'field': 'value1'}),
            ProductionRecord(uuid=uuid2, data={'field': 'value2'})
        ]
        
        with patch.object(classification_engine, '_execute_production_query') as mock_query:
            mock_query.return_value = production_records
            
            # Act
            result = classification_engine._batch_lookup_production_records(uuids, 'campaigns')
            
            # Assert: Should only query unique UUIDs
            assert mock_query.call_count == 1
            query_uuids = mock_query.call_args[0][0]
            assert len(query_uuids) == 2  # Only unique UUIDs
            assert uuid1 in query_uuids
            assert uuid2 in query_uuids
            
            # Verify both UUIDs are in result
            assert uuid1 in result
            assert uuid2 in result
    
    def test_production_database_connection_pooling(self, classification_engine):
        """Test production database uses connection pooling with read-only transactions."""
        # Arrange
        uuids = [uuid4()]
        
        with patch.object(classification_engine, '_get_production_engine') as mock_engine:
            mock_connection = Mock()
            mock_engine.return_value.connect.return_value.__enter__.return_value = mock_connection
            mock_connection.execute.return_value.fetchall.return_value = []
            
            # Act
            classification_engine._batch_lookup_production_records(uuids, 'campaigns')
            
            # Assert: Connection should be created with read-only transaction
            mock_engine.assert_called_once()
            mock_engine.return_value.connect.assert_called_once()
    
    def test_production_query_where_in_pattern(self, classification_engine):
        """Test production queries use WHERE uuid IN (...) pattern."""
        # Arrange
        uuids = [uuid4(), uuid4(), uuid4()]
        
        with patch.object(classification_engine, '_execute_production_query') as mock_query:
            mock_query.return_value = []
            
            # Act
            classification_engine._batch_lookup_production_records(uuids, 'campaigns')
            
            # Assert: Query should use WHERE IN pattern
            query_sql = mock_query.call_args[0][1]
            assert "WHERE" in query_sql.upper()
            assert "IN" in query_sql.upper()
            assert len(mock_query.call_args[0][0]) == 3  # All UUIDs passed
    
    # Test Batch Classification
    def test_batch_classify_mixed_categories(self, classification_engine):
        """Test batch classification with mixed categories."""
        # Arrange: Create records representing all 4 categories
        new_uuid = uuid4()
        updated_uuid = uuid4()
        unchanged_uuid = uuid4()
        inconsistent_uuid = uuid4()
        
        staging_records = [
            CampaignsStaging(
                deal_campaign_id=new_uuid,
                deal_campaign_name="New Campaign",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 12, 31),
                impression_goal=100000,
                budget_eur=Decimal('5000.00'),
                cpm_eur=Decimal('2.50'),
                buyer="Buyer A",
                processing_batch_id=uuid4(),
                record_classification="pending",
                source_row_number=1
            ),
            CampaignsStaging(
                deal_campaign_id=updated_uuid,
                deal_campaign_name="Updated Campaign",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 12, 31),
                impression_goal=120000,  # Will be different in production
                budget_eur=Decimal('6000.00'),
                cpm_eur=Decimal('3.00'),
                buyer="Buyer B",
                processing_batch_id=uuid4(),
                record_classification="pending",
                source_row_number=2
            ),
            CampaignsStaging(
                deal_campaign_id=unchanged_uuid,
                deal_campaign_name="Unchanged Campaign",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 12, 31),
                impression_goal=80000,
                budget_eur=Decimal('4000.00'),
                cpm_eur=Decimal('2.00'),
                buyer="Buyer C",
                processing_batch_id=uuid4(),
                record_classification="pending",
                source_row_number=3
            ),
            CampaignsStaging(
                deal_campaign_id=inconsistent_uuid,
                deal_campaign_name="Inconsistent Campaign",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 12, 31),
                impression_goal=90000,
                budget_eur=Decimal('4500.00'),
                cpm_eur=Decimal('2.25'),
                buyer="Buyer D",
                processing_batch_id=uuid4(),
                record_classification="pending",
                source_row_number=4
            )
        ]
        
        # Mock production records (new_uuid intentionally missing)
        production_records = {
            updated_uuid: ProductionRecord(
                uuid=updated_uuid,
                data={
                    'deal_campaign_name': 'Updated Campaign',
                    'start_date': datetime(2024, 1, 1),
                    'end_date': datetime(2024, 12, 31),
                    'impression_goal': 100000,  # Different from staging (120000)
                    'budget_eur': Decimal('6000.00'),
                    'cpm_eur': Decimal('3.00'),
                    'buyer': 'Buyer B'
                }
            ),
            unchanged_uuid: ProductionRecord(
                uuid=unchanged_uuid,
                data={
                    'deal_campaign_name': 'Unchanged Campaign',
                    'start_date': datetime(2024, 1, 1),
                    'end_date': datetime(2024, 12, 31),
                    'impression_goal': 80000,
                    'budget_eur': Decimal('4000.00'),
                    'cpm_eur': Decimal('2.00'),
                    'buyer': 'Buyer C'
                }
            ),
            inconsistent_uuid: ProductionRecord(
                uuid=inconsistent_uuid,
                data={
                    'deal_campaign_name': 'Different Campaign Name',  # Restricted field change
                    'start_date': datetime(2024, 1, 1),
                    'end_date': datetime(2024, 12, 31),
                    'impression_goal': 90000,
                    'budget_eur': Decimal('4500.00'),
                    'cpm_eur': Decimal('2.25'),
                    'buyer': 'Buyer D'
                }
            )
        }
        
        with patch.object(classification_engine, '_batch_lookup_production_records') as mock_lookup:
            mock_lookup.return_value = production_records
            
            # Act
            batch_result = classification_engine.classify_campaign_batch(staging_records)
            
            # Assert
            assert len(batch_result.results) == 4
            
            # Verify each category
            category_counts = {}
            for result in batch_result.results:
                category_counts[result.category] = category_counts.get(result.category, 0) + 1
            
            assert category_counts[ClassificationCategory.NEW] == 1
            assert category_counts[ClassificationCategory.UPDATED] == 1
            assert category_counts[ClassificationCategory.UNCHANGED] == 1
            assert category_counts[ClassificationCategory.INCONSISTENT] == 1
    
    # Test Error Handling
    def test_classification_handles_production_database_errors(self, classification_engine, sample_campaign_staging_record):
        """Test classification handles production database connection errors gracefully."""
        # Arrange: Mock database error
        with patch.object(classification_engine, '_batch_lookup_production_records') as mock_lookup:
            mock_lookup.side_effect = Exception("Database connection failed")
            
            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                classification_engine.classify_campaign_record(sample_campaign_staging_record)
            
            assert "Database connection failed" in str(exc_info.value)
    
    def test_classification_handles_malformed_production_data(self, classification_engine, sample_campaign_staging_record):
        """Test classification handles malformed production data gracefully."""
        # Arrange: Mock production record with missing fields
        malformed_production_record = ProductionRecord(
            uuid=sample_campaign_staging_record.deal_campaign_id,
            data={'deal_campaign_name': 'Test'}  # Missing required fields
        )
        
        with patch.object(classification_engine, '_batch_lookup_production_records') as mock_lookup:
            mock_lookup.return_value = {sample_campaign_staging_record.deal_campaign_id: malformed_production_record}
            
            # Act
            result = classification_engine.classify_campaign_record(sample_campaign_staging_record)
            
            # Assert: Should handle gracefully and not crash
            assert result is not None
            assert len(result.validation_errors) > 0
    
    # Test Cross-file Consistency Validation
    def test_cross_file_consistency_validation(self, classification_engine):
        """Test cross-file consistency validation between campaign and reporting records."""
        # Arrange: Campaign and reporting records with matching UUIDs
        campaign_uuid = uuid4()
        
        campaign_record = CampaignsStaging(
            deal_campaign_id=campaign_uuid,
            deal_campaign_name="Test Campaign",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31),
            impression_goal=100000,
            budget_eur=Decimal('5000.00'),
            cpm_eur=Decimal('2.50'),
            buyer="Test Buyer",
            processing_batch_id=uuid4(),
            record_classification="pending",
            source_row_number=1
        )
        
        reporting_record = ReportingStaging(
            deal_id=campaign_uuid,  # Same UUID
            date_recorded=datetime(2024, 6, 15),
            deal_name="Different Deal Name",  # Should match campaign name
            core_dsp_audience_segment="Test Segment",
            core_dsp_placement="Test Placement",
            core_dsp_creative="Test Creative",
            purchase_type=PurchaseType.guaranteed,
            total_impressions=Decimal('50000.00'),
            processing_batch_id=uuid4(),
            record_classification="pending",
            source_row_number=1
        )
        
        # Act
        consistency_result = classification_engine.validate_cross_file_consistency(
            [campaign_record], [reporting_record]
        )
        
        # Assert
        assert len(consistency_result.validation_errors) > 0
        assert any("deal name mismatch" in error.lower() for error in consistency_result.validation_errors)
    
    def test_business_rule_validation_integration(self, classification_engine, sample_campaign_staging_record):
        """Test business rule validation integration with classification."""
        # Arrange: Create scenario that violates business rules
        sample_campaign_staging_record.impression_goal = 1000  # Below minimum
        sample_campaign_staging_record.cpm_eur = Decimal('50.00')  # Above maximum
        
        with patch.object(classification_engine, '_batch_lookup_production_records') as mock_lookup:
            mock_lookup.return_value = {}  # No production records
            
            # Act
            result = classification_engine.classify_campaign_record(sample_campaign_staging_record)
            
            # Assert
            assert len(result.validation_errors) > 0
            assert any("impression_goal" in error for error in result.validation_errors)
            assert any("cpm_eur" in error for error in result.validation_errors)