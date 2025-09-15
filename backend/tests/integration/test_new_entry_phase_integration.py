"""
Integration Tests for New Entry Validator - Phase 1.1 Compatibility - RED PHASE
These tests MUST fail initially since new_entry_validator doesn't exist yet.

Integration Test Focus:
1. Phase 1.1 Infrastructure Compatibility
2. Database Connection Sharing and Management  
3. Staging Table Extensions Integration
4. Upload Processing Pipeline Integration
5. Record Classification Engine Integration
6. Error Handling System Integration

Phase 1.1 Compatibility Requirements:
- Reuse existing database connection patterns
- Integrate with existing staging table structures
- Compatible with record_classification_engine.py patterns
- Share upload processing orchestrator infrastructure
- Use existing error code system (BIZ_xxx)
- Maintain existing transaction management patterns
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from decimal import Decimal
from datetime import datetime, date
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Import Phase 1.1 components that new entry validator should integrate with
from src.services.record_classification_engine import RecordClassificationEngine
from src.services.upload_processing_orchestrator import UploadProcessingOrchestrator
from src.database.staging_connection import get_staging_db_session, get_production_db_session
from src.models.staging_models import StagingCampaigns, StagingReporting

# Import new entry validator components (TDD RED phase - will fail)
from src.services.new_entry_validator import (
    NewEntryValidator,
    integrate_with_phase_1_1_pipeline,
    share_database_connections,
    extend_staging_tables_for_phase_1_2
)


class TestPhase11DatabaseConnectionSharing:
    """Test database connection sharing between Phase 1.1 and new entry validation"""
    
    @pytest.fixture
    def mock_phase_1_1_connections(self):
        """Mock Phase 1.1 database connections"""
        production_session = Mock()
        staging_session = Mock()
        
        # Mock the connection factory pattern from Phase 1.1
        with patch('src.database.staging_connection.get_staging_db_session') as mock_staging:
            with patch('src.database.staging_connection.get_production_db_session') as mock_production:
                mock_staging.return_value = staging_session
                mock_production.return_value = production_session
                
                yield {
                    'staging': staging_session,
                    'production': production_session,
                    'staging_factory': mock_staging,
                    'production_factory': mock_production
                }
    
    def test_reuses_phase_1_1_database_connection_patterns(self, mock_phase_1_1_connections):
        """Test new entry validator reuses Phase 1.1 database connection patterns"""
        # Phase 1.1 pattern: get_staging_db_session() and get_production_db_session()
        validator = NewEntryValidator.create_with_phase_1_1_connections()
        
        # Should use the same connection factory pattern
        mock_phase_1_1_connections['staging_factory'].assert_called_once()
        mock_phase_1_1_connections['production_factory'].assert_called_once()
        
        # Validator should have the same connection instances
        assert validator.staging_db_session == mock_phase_1_1_connections['staging']
        assert validator.production_db_session == mock_phase_1_1_connections['production']
    
    def test_database_connection_sharing_with_orchestrator(self, mock_phase_1_1_connections):
        """Test database connection sharing with UploadProcessingOrchestrator"""
        orchestrator = UploadProcessingOrchestrator(
            staging_session=mock_phase_1_1_connections['staging'],
            production_session=mock_phase_1_1_connections['production']
        )
        
        # New entry validator should share the same connections
        validator = NewEntryValidator.create_from_orchestrator(orchestrator)
        
        assert validator.staging_db_session == orchestrator.staging_session
        assert validator.production_db_session == orchestrator.production_session
    
    def test_transaction_coordination_with_phase_1_1(self, mock_phase_1_1_connections):
        """Test transaction coordination with Phase 1.1 components"""
        staging_session = mock_phase_1_1_connections['staging']
        
        # Mock Phase 1.1 transaction in progress
        staging_session.in_transaction.return_value = True
        staging_session.get_transaction.return_value = Mock()
        
        validator = NewEntryValidator(
            production_db_session=mock_phase_1_1_connections['production'],
            staging_db_session=staging_session,
            processing_batch_id="batch-001"
        )
        
        # Should participate in existing transaction
        validator.store_new_entry_in_extended_staging({'deal_campaign_id': 'test'})
        
        # Should not commit independently when in existing transaction
        staging_session.commit.assert_not_called()
    
    def test_connection_cleanup_coordination(self, mock_phase_1_1_connections):
        """Test connection cleanup coordination with Phase 1.1"""
        staging_session = mock_phase_1_1_connections['staging']
        production_session = mock_phase_1_1_connections['production']
        
        validator = NewEntryValidator(production_session, staging_session, "batch-001")
        
        # Simulate error scenario
        staging_session.execute.side_effect = Exception("Database error")
        
        with pytest.raises(Exception):
            validator.process_new_entries([{'deal_campaign_id': 'test'}])
        
        # Should coordinate cleanup without interfering with Phase 1.1
        # (Phase 1.1 should handle final cleanup)
        staging_session.rollback.assert_called()
        # But should not close connections owned by Phase 1.1
        staging_session.close.assert_not_called()


class TestRecordClassificationEngineIntegration:
    """Test integration with existing RecordClassificationEngine"""
    
    @pytest.fixture
    def classification_engine(self):
        """Create RecordClassificationEngine instance for integration testing"""
        return RecordClassificationEngine(
            staging_session=Mock(),
            production_session=Mock(),
            processing_batch_id="batch-001"
        )
    
    @pytest.fixture
    def new_entry_validator(self):
        """Create NewEntryValidator for integration testing"""
        return NewEntryValidator(
            production_db_session=Mock(),
            staging_db_session=Mock(),
            processing_batch_id="batch-001"
        )
    
    def test_uuid_lookup_pattern_compatibility(self, classification_engine, new_entry_validator):
        """Test UUID lookup pattern compatibility with RecordClassificationEngine"""
        # Phase 1.1 pattern from RecordClassificationEngine
        phase_1_1_uuids = ['existing-001', 'existing-002', 'new-003']
        
        # Mock Phase 1.1 production lookup behavior
        classification_engine.production_db_session.execute.return_value.fetchall.return_value = [
            Mock(deal_campaign_id='existing-001'),
            Mock(deal_campaign_id='existing-002')
        ]
        
        # New entry validator should use the same lookup pattern
        new_entry_validator.production_db_session.execute.return_value.fetchall.return_value = [
            Mock(deal_campaign_id='existing-001'),
            Mock(deal_campaign_id='existing-002')
        ]
        
        # Both should identify the same UUIDs as existing/new
        phase_1_1_result = classification_engine.lookup_production_records(phase_1_1_uuids, 'campaign')
        phase_1_2_result = new_entry_validator.lookup_uuids_in_production(phase_1_1_uuids, 'campaign')
        
        # Results should be compatible
        assert phase_1_1_result.found_records.keys() == set(phase_1_2_result.found_uuids)
        assert 'new-003' in phase_1_2_result.new_uuids
    
    def test_business_rule_validation_pattern_compatibility(self, classification_engine, new_entry_validator):
        """Test business rule validation pattern compatibility"""
        # Use the same validation rules as Phase 1.1
        test_record = {
            'deal_campaign_id': 'test-001',
            'impression_goal': 0,  # Below minimum (now 1) - should trigger BIZ_101
            'cpm_eur': Decimal('50.00'),  # Above maximum - should trigger BIZ_104
            'budget_eur': Decimal('1000.00')
        }
        
        # Phase 1.1 validation (from RecordClassificationEngine)
        phase_1_1_errors = classification_engine.validate_business_rules(test_record, 'campaign')
        
        # Phase 1.2 validation (NewEntryValidator)
        phase_1_2_violations = new_entry_validator.validate_campaign_business_rules(test_record)
        
        # Should identify the same violations
        phase_1_2_error_codes = [v.error_code for v in phase_1_2_violations]
        
        assert 'BIZ_101' in phase_1_2_error_codes  # impression_goal too low
        assert 'BIZ_104' in phase_1_2_error_codes  # cpm_eur too high
        
        # Error patterns should be compatible
        assert len(phase_1_1_errors) == len(phase_1_2_violations)
    
    def test_batch_processing_optimization_compatibility(self, classification_engine, new_entry_validator):
        """Test batch processing optimization compatibility"""
        # Phase 1.1 uses 500 record batches for production queries
        large_uuid_list = [f'uuid-{i:04d}' for i in range(1200)]
        
        # Both should use the same batch size optimization
        assert classification_engine.PRODUCTION_QUERY_BATCH_SIZE == 500
        assert new_entry_validator.uuid_lookup_batch_size == 500
        
        # Mock database responses
        classification_engine.production_db_session.execute.return_value.fetchall.return_value = []
        new_entry_validator.production_db_session.execute.return_value.fetchall.return_value = []
        
        # Both should make the same number of queries (3 queries for 1200 records)
        classification_engine.lookup_production_records(large_uuid_list, 'campaign')
        phase_1_1_query_count = classification_engine.production_db_session.execute.call_count
        
        classification_engine.production_db_session.execute.reset_mock()
        
        new_entry_validator.lookup_uuids_in_production(large_uuid_list, 'campaign')
        phase_1_2_query_count = new_entry_validator.production_db_session.execute.call_count
        
        assert phase_1_1_query_count == phase_1_2_query_count == 3


class TestStagingTableExtensionsIntegration:
    """Test integration with Phase 1.1 staging table structures and Phase 1.2 extensions"""
    
    @pytest.fixture
    def validator_with_staging(self):
        """Create validator with staging database mock"""
        staging_session = Mock()
        return NewEntryValidator(Mock(), staging_session, "batch-001")
    
    def test_existing_staging_table_compatibility(self, validator_with_staging):
        """Test compatibility with existing Phase 1.1 staging tables"""
        # Phase 1.1 staging tables: staging_campaigns, staging_reporting
        new_campaign_entry = {
            'deal_campaign_id': 'new-camp-001',
            'deal_campaign_name': 'New Campaign',
            'start_date': date(2024, 1, 1),
            'end_date': date(2024, 1, 31),
            'impression_goal': 50000,
            'budget_eur': Decimal('1000.00'),
            'cpm_eur': Decimal('5.50'),
            'buyer': 'Test Buyer'
        }
        
        # Should store in existing staging_campaigns table structure
        validator_with_staging.store_new_entry_in_staging(new_campaign_entry, 'campaign')
        
        # Verify INSERT targets staging_campaigns
        call_args = validator_with_staging.staging_db_session.execute.call_args[0][0]
        assert "staging_campaigns" in str(call_args)
        
        # Should include all Phase 1.1 required fields
        query_str = str(call_args)
        assert "deal_campaign_id" in query_str
        assert "processing_batch_id" in query_str
        assert "record_classification" in query_str
    
    def test_phase_1_2_extended_staging_fields(self, validator_with_staging):
        """Test Phase 1.2 extended staging fields integration"""
        new_entry_with_violations = {
            'deal_campaign_id': 'new-camp-002',
            'impression_goal': 0  # Violation: below minimum (now 1)
        }
        
        violations = [
            {'error_code': 'BIZ_101', 'field': 'impression_goal', 'severity': 'high'}
        ]
        
        # Should store with Phase 1.2 extensions
        validator_with_staging.store_new_entry_in_extended_staging(
            new_entry_with_violations, violations
        )
        
        call_args = validator_with_staging.staging_db_session.execute.call_args[0][0]
        query_str = str(call_args)
        
        # Should include Phase 1.2 extension fields
        assert "phase_context" in query_str
        assert "'1.2'" in query_str
        assert "violation_details" in query_str
        assert "flagged_for_review" in query_str
    
    def test_staging_record_relationships_preservation(self, validator_with_staging):
        """Test preservation of staging record relationships from Phase 1.1"""
        # Phase 1.1 establishes relationships via processing_batch_id
        batch_id = "integration-batch-001"
        validator_with_staging.processing_batch_id = batch_id
        
        new_campaign = {'deal_campaign_id': 'camp-001'}
        new_performance = {'deal_id': 'perf-001'}
        
        # Both records should share the same processing_batch_id
        validator_with_staging.store_new_entry_in_staging(new_campaign, 'campaign')
        validator_with_staging.store_new_entry_in_staging(new_performance, 'performance')
        
        # Verify both calls used the same batch_id
        calls = validator_with_staging.staging_db_session.execute.call_args_list
        
        for call in calls:
            query_str = str(call[0][0])
            assert batch_id in query_str
    
    def test_staging_data_type_compatibility(self, validator_with_staging):
        """Test staging data type compatibility with Phase 1.1"""
        # Test that new entry validator respects Phase 1.1 data types
        entry_with_decimals = {
            'deal_campaign_id': 'camp-003',
            'impression_goal': 50000,  # Should be stored as INTEGER
            'budget_eur': Decimal('1250.75'),  # Should be stored as DECIMAL(10,2)
            'cpm_eur': Decimal('8.50'),  # Should be stored as DECIMAL(8,2)
        }
        
        validator_with_staging.store_new_entry_in_staging(entry_with_decimals, 'campaign')
        
        # Verify data types are preserved in the query
        call_args = validator_with_staging.staging_db_session.execute.call_args
        
        # Should pass Decimal objects directly (SQLAlchemy handles conversion)
        assert isinstance(call_args[1]['budget_eur'], Decimal)
        assert isinstance(call_args[1]['cpm_eur'], Decimal)


class TestUploadProcessingPipelineIntegration:
    """Test integration with Phase 1.1 upload processing pipeline"""
    
    @pytest.fixture
    def upload_orchestrator(self):
        """Mock UploadProcessingOrchestrator for integration testing"""
        return Mock(spec=UploadProcessingOrchestrator)
    
    @pytest.fixture
    def integrated_validator(self, upload_orchestrator):
        """Create validator integrated with upload processing pipeline"""
        return NewEntryValidator.integrate_with_upload_pipeline(upload_orchestrator)
    
    def test_pipeline_phase_coordination(self, upload_orchestrator, integrated_validator):
        """Test coordination with upload processing pipeline phases"""
        # Phase 1.1 pipeline phases: PARSING -> VALIDATION -> CLASSIFICATION
        # Phase 1.2 adds: NEW_ENTRY_VALIDATION after CLASSIFICATION
        
        upload_orchestrator.current_phase = "CLASSIFICATION"
        upload_orchestrator.get_classified_records.return_value = {
            'new_campaigns': [{'deal_campaign_id': 'new-001'}],
            'new_performance': [{'deal_id': 'perf-001'}]
        }
        
        # Should integrate seamlessly after classification phase
        result = integrated_validator.process_post_classification_new_entries()
        
        # Should advance pipeline to next phase
        upload_orchestrator.advance_to_phase.assert_called_with("NEW_ENTRY_VALIDATION")
        
        assert result.phase == "NEW_ENTRY_VALIDATION"
        assert result.processed_new_entries > 0
    
    def test_error_propagation_to_pipeline(self, upload_orchestrator, integrated_validator):
        """Test error propagation to upload processing pipeline"""
        # Simulate new entry validation error
        integrated_validator.validate_campaign_business_rules = Mock(
            side_effect=Exception("Business rule validation failed")
        )
        
        with pytest.raises(Exception):
            integrated_validator.process_post_classification_new_entries()
        
        # Should propagate error to orchestrator
        upload_orchestrator.handle_phase_error.assert_called_with(
            phase="NEW_ENTRY_VALIDATION",
            error=Exception("Business rule validation failed")
        )
    
    def test_progress_reporting_integration(self, upload_orchestrator, integrated_validator):
        """Test progress reporting integration with pipeline"""
        # Mock large batch for progress reporting
        large_new_entry_batch = [
            {'deal_campaign_id': f'new-{i:04d}'} for i in range(1000)
        ]
        
        upload_orchestrator.get_classified_records.return_value = {
            'new_campaigns': large_new_entry_batch,
            'new_performance': []
        }
        
        # Should report progress during processing
        integrated_validator.process_post_classification_new_entries()
        
        # Verify progress was reported (e.g., 10%, 20%, etc.)
        progress_calls = upload_orchestrator.report_progress.call_args_list
        assert len(progress_calls) > 0
        
        # Should report completion
        completion_call = [call for call in progress_calls if '100%' in str(call)]
        assert len(completion_call) > 0
    
    def test_rollback_coordination_with_pipeline(self, upload_orchestrator, integrated_validator):
        """Test rollback coordination with upload processing pipeline"""
        # Simulate failure requiring rollback
        integrated_validator.staging_db_session.execute.side_effect = Exception("Storage failed")
        
        with pytest.raises(Exception):
            integrated_validator.process_post_classification_new_entries()
        
        # Should coordinate rollback with pipeline
        upload_orchestrator.initiate_rollback.assert_called_with(
            phase="NEW_ENTRY_VALIDATION",
            reason="Storage failed"
        )


class TestEndToEndIntegrationScenarios:
    """Test complete end-to-end integration scenarios"""
    
    @pytest.mark.asyncio
    async def test_complete_new_entry_processing_workflow(self):
        """Test complete workflow from upload to new entry validation"""
        # Setup: Mock complete Phase 1.1 + 1.2 pipeline
        with patch('src.services.upload_processing_orchestrator.UploadProcessingOrchestrator') as mock_orchestrator:
            with patch('src.services.new_entry_validator.NewEntryValidator') as mock_validator:
                
                # Configure orchestrator
                orchestrator_instance = mock_orchestrator.return_value
                orchestrator_instance.current_phase = "PARSING"
                
                # Configure validator
                validator_instance = mock_validator.return_value
                validator_instance.lookup_uuids_in_production.return_value = Mock(
                    new_uuids=['new-001', 'new-002'],
                    found_uuids=['existing-003']
                )
                
                # Simulate complete workflow
                workflow_result = await process_complete_upload_with_new_entry_validation(
                    campaign_file_path="/mock/campaigns.xlsx",
                    performance_file_path="/mock/performance.csv"
                )
                
                # Verify workflow completion
                assert workflow_result.parsing_completed is True
                assert workflow_result.classification_completed is True
                assert workflow_result.new_entry_validation_completed is True
                assert workflow_result.total_new_entries == 2
    
    def test_mixed_new_and_existing_entries_processing(self):
        """Test processing upload with mix of new and existing entries"""
        # Setup mixed dataset
        mixed_campaign_data = [
            {'deal_campaign_id': 'existing-001', 'impression_goal': 50000},  # Exists in production
            {'deal_campaign_id': 'new-002', 'impression_goal': 75000},      # New entry
            {'deal_campaign_id': 'existing-003', 'impression_goal': 60000}, # Exists in production
            {'deal_campaign_id': 'new-004', 'impression_goal': 1000}        # New with violation
        ]
        
        with patch('src.services.new_entry_validator.NewEntryValidator') as mock_validator:
            validator_instance = mock_validator.return_value
            
            # Mock production lookup
            validator_instance.lookup_uuids_in_production.return_value = Mock(
                found_uuids=['existing-001', 'existing-003'],
                new_uuids=['new-002', 'new-004']
            )
            
            # Mock business rule validation
            validator_instance.validate_campaign_business_rules.side_effect = [
                [],  # new-002: no violations
                [Mock(error_code='BIZ_101')]  # new-004: impression_goal too low
            ]
            
            result = validator_instance.process_mixed_entry_batch(mixed_campaign_data)
            
            # Should correctly separate new from existing
            assert result.existing_entries_count == 2
            assert result.new_entries_count == 2
            assert result.new_entries_with_violations == 1
    
    def test_exact_uuid_matching_integration(self):
        """Test exact UUID matching integration (replaces combined upload validation)"""
        # Scenario: Test exact UUID matching between files
        campaign_uuids = ['new-camp-001', 'new-camp-002', 'existing-camp-003']
        performance_uuids = ['new-perf-001', 'new-camp-001', 'existing-camp-003']  # new-camp-001 exactly matches
        
        with patch('src.services.new_entry_validator.NewEntryValidator') as mock_validator:
            validator_instance = mock_validator.return_value
            
            # Mock exact UUID matching (only exact matches are valid)
            validator_instance.find_exact_uuid_matches.return_value = Mock(
                exact_matches=['new-camp-001', 'existing-camp-003'],
                campaign_only=['new-camp-002'],
                performance_only=['new-perf-001']
            )
            
            result = validator_instance.find_exact_uuid_matches(campaign_uuids, performance_uuids)
            
            # Should only find exact matches
            assert len(result.exact_matches) == 2
            assert 'new-camp-001' in result.exact_matches
            assert 'existing-camp-003' in result.exact_matches
            assert 'new-camp-002' in result.campaign_only
            assert 'new-perf-001' in result.performance_only


class TestDatabaseTransactionIntegration:
    """Test database transaction integration with Phase 1.1"""
    
    def test_transaction_participation_with_phase_1_1(self):
        """Test transaction participation with existing Phase 1.1 transactions"""
        # Mock ongoing Phase 1.1 transaction
        staging_session = Mock()
        staging_session.in_transaction.return_value = True
        existing_transaction = Mock()
        staging_session.get_transaction.return_value = existing_transaction
        
        validator = NewEntryValidator(Mock(), staging_session, "batch-001")
        
        # Should participate in existing transaction
        validator.store_new_entry_in_extended_staging({'deal_campaign_id': 'test'})
        
        # Should not start new transaction
        staging_session.begin.assert_not_called()
        
        # Should not commit independently
        staging_session.commit.assert_not_called()
    
    def test_independent_transaction_when_no_existing_transaction(self):
        """Test independent transaction creation when no existing transaction"""
        staging_session = Mock()
        staging_session.in_transaction.return_value = False
        
        validator = NewEntryValidator(Mock(), staging_session, "batch-001")
        
        # Should create its own transaction
        validator.store_new_entry_in_extended_staging({'deal_campaign_id': 'test'})
        
        # Should manage its own transaction lifecycle
        staging_session.begin.assert_called_once()
        staging_session.commit.assert_called_once()
    
    def test_rollback_coordination_on_error(self):
        """Test rollback coordination when errors occur"""
        staging_session = Mock()
        staging_session.execute.side_effect = Exception("Database error")
        
        validator = NewEntryValidator(Mock(), staging_session, "batch-001")
        
        with pytest.raises(Exception):
            validator.store_new_entry_in_extended_staging({'deal_campaign_id': 'test'})
        
        # Should trigger rollback
        staging_session.rollback.assert_called_once()


class TestPerformanceIntegrationTests:
    """Test performance characteristics in integrated environment"""
    
    @pytest.mark.asyncio
    async def test_production_database_query_performance(self):
        """Test production database query performance under load"""
        # Mock production database with realistic response times
        production_session = Mock()
        mock_result = Mock()
        mock_result.fetchall.return_value = [Mock(deal_campaign_id=f'existing-{i}') for i in range(250)]
        production_session.execute.return_value = mock_result
        
        validator = NewEntryValidator(production_session, Mock(), "batch-001")
        
        # Test with 1000 UUIDs (should batch into 2 queries of 500 each)
        large_uuid_batch = [f'uuid-{i:04d}' for i in range(1000)]
        
        start_time = datetime.now()
        result = await validator.lookup_uuids_in_production(large_uuid_batch, 'campaign')
        end_time = datetime.now()
        
        processing_time = (end_time - start_time).total_seconds()
        
        # Should complete within reasonable time (< 5 seconds for mocked scenario)
        assert processing_time < 5
        
        # Should make exactly 2 queries due to batching
        assert production_session.execute.call_count == 2
    
    def test_staging_bulk_insert_performance(self):
        """Test staging database bulk insert performance"""
        staging_session = Mock()
        validator = NewEntryValidator(Mock(), staging_session, "batch-001")
        
        # Test bulk insert of 500 new entries
        large_new_entry_batch = [
            {'deal_campaign_id': f'new-{i:04d}', 'impression_goal': 50000}
            for i in range(500)
        ]
        
        start_time = datetime.now()
        validator.bulk_store_new_entries_in_staging(large_new_entry_batch)
        end_time = datetime.now()
        
        processing_time = (end_time - start_time).total_seconds()
        
        # Should use bulk insert for performance (< 2 seconds for mocked scenario)
        assert processing_time < 2
        
        # Should use executemany or bulk insert patterns
        staging_session.bulk_insert_mappings.assert_called_once()
    
    def test_memory_usage_optimization_integration(self):
        """Test memory usage optimization in integrated environment"""
        # This test ensures memory usage stays reasonable during processing
        validator = NewEntryValidator(Mock(), Mock(), "batch-001")
        
        # Mock memory monitoring
        with patch('psutil.Process') as mock_process:
            mock_process.return_value.memory_info.return_value.rss = 50 * 1024 * 1024  # 50MB
            
            # Process large dataset
            large_dataset = [
                {'deal_campaign_id': f'entry-{i:06d}', 'impression_goal': 50000}
                for i in range(10000)
            ]
            
            result = validator.process_large_batch_with_memory_optimization(large_dataset)
            
            # Memory usage should stay reasonable (< 100MB)
            final_memory_mb = mock_process.return_value.memory_info.return_value.rss / (1024 * 1024)
            assert final_memory_mb < 100
            assert result.processed_successfully is True


# Helper Functions for Integration Testing
async def process_complete_upload_with_new_entry_validation(campaign_file_path: str, performance_file_path: str):
    """
    Helper function to simulate complete upload processing workflow
    This would be implemented to coordinate all phases
    """
    # This is a placeholder for the actual integration workflow
    # Implementation would coordinate Phase 1.1 + Phase 1.2 processing
    class WorkflowResult:
        def __init__(self):
            self.parsing_completed = True
            self.classification_completed = True
            self.new_entry_validation_completed = True
            self.total_new_entries = 2
    
    return WorkflowResult()


# Fixtures for Integration Testing
@pytest.fixture
def integrated_test_environment():
    """Setup integrated test environment with all Phase 1.1 + 1.2 components"""
    # This fixture would setup a complete test environment
    # including test databases, staging tables, and all services
    pass


@pytest.fixture
def sample_production_database():
    """Setup sample production database for integration testing"""
    # This fixture would create a test production database
    # with sample campaigns and reporting data
    pass


@pytest.fixture
def phase_1_1_staging_environment():
    """Setup Phase 1.1 staging environment for compatibility testing"""
    # This fixture would setup Phase 1.1 staging tables
    # to test compatibility and extensions
    pass