"""
Integration tests for Upload Processing Orchestrator

Tests the complete workflow:
1. End-to-end upload processing for both XLSX and CSV files
2. Processing batch ID generation and tracking
3. Upload blocking when processing is active (one file per type)
4. Processing state management (idle, processing, completed, error)
5. Error handling and rollback scenarios with time-ordered error collection
6. Staging data cleanup after processing
7. Progress tracking with equal stage percentages (25% each)
8. Integration with parsers and classification engine
"""
import pytest
import tempfile
import os
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from unittest.mock import patch, Mock, MagicMock
from pathlib import Path
import io

from src.services.upload_processing_orchestrator import (
    UploadProcessingOrchestrator,
    ProcessingState,
    ProcessingStage,
    FileType,
    ProcessingStatus,
    ProcessingError
)
from src.services.xlsx_campaign_parser import XLSXCampaignParser
from src.services.csv_performance_parser import CSVPerformanceParser
from src.services.classification_integration_service import ClassificationIntegrationService
from src.database.staging_connection import StagingDatabase
from src.models.staging import CampaignsStaging, ReportingStaging, PurchaseType


# Module-level fixtures that all test classes can use
@pytest.fixture
def orchestrator():
    """Create upload processing orchestrator for testing."""
    return UploadProcessingOrchestrator()

@pytest.fixture  
def sample_xlsx_file():
    """Create a sample XLSX file for testing."""
    # Create temporary XLSX file with campaign data
    content = io.BytesIO()
    # Mock XLSX content would be created here
    content.seek(0)
    return content

@pytest.fixture
def sample_csv_file():
    """Create a sample CSV file for testing."""
    # Create temporary CSV file with reporting data
    content = io.StringIO()
    content.write("Deal ID,Date,Total Impressions,Purchase Type,Buyer,Core DSP Campaign Name,Deal Name,Campaign/Deal Purchase Type\n")
    content.write("123e4567-e89b-12d3-a456-426614174000,2024-01-15,10000,guaranteed,Test Buyer,Test DSP Campaign,Test Deal,guaranteed\n")
    content.seek(0)
    return content.getvalue().encode('utf-8')

@pytest.fixture
def large_xlsx_file():
    """Create a large XLSX file (250MB) for memory testing."""
    # Mock large file for memory efficiency testing
    return io.BytesIO(b"0" * (250 * 1024 * 1024))  # 250MB

@pytest.fixture
def large_csv_file():
    """Create a large CSV file (250MB) for memory testing."""
    # Mock large CSV file for memory efficiency testing
    return b"0" * (250 * 1024 * 1024)  # 250MB


class TestUploadProcessingOrchestrator:
    """Integration tests for upload processing orchestrator."""


class TestProcessingBatchIDGeneration:
    """Test processing batch ID generation and tracking."""
    
    def test_unique_batch_id_generation(self, orchestrator):
        """Test that each processing session gets a unique batch ID."""
        batch_id_1 = orchestrator.generate_processing_batch_id()
        batch_id_2 = orchestrator.generate_processing_batch_id() 
        
        assert isinstance(batch_id_1, UUID)
        assert isinstance(batch_id_2, UUID)
        assert batch_id_1 != batch_id_2
    
    def test_batch_id_tracking_throughout_workflow(self, orchestrator, sample_xlsx_file):
        """Test that batch ID is consistently tracked throughout processing."""
        # Start processing and get batch ID
        batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        
        # Verify batch ID is tracked in status
        status = orchestrator.get_processing_status(batch_id)
        assert status.processing_batch_id == batch_id
        
        # Verify batch ID persists through all processing stages
        assert orchestrator.get_current_batch_id(FileType.CAMPAIGN_XLSX) == batch_id
    
    def test_batch_isolation_between_file_types(self, orchestrator, sample_xlsx_file, sample_csv_file):
        """Test that different file types get different batch IDs."""
        xlsx_batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        csv_batch_id = orchestrator.start_processing(sample_csv_file, FileType.REPORTING_CSV)
        
        assert xlsx_batch_id != csv_batch_id
        assert orchestrator.get_current_batch_id(FileType.CAMPAIGN_XLSX) == xlsx_batch_id
        assert orchestrator.get_current_batch_id(FileType.REPORTING_CSV) == csv_batch_id


class TestProcessingStateManagement:
    """Test processing state management for upload control."""
    
    def test_initial_state_is_idle(self, orchestrator):
        """Test that initial processing state is idle for both file types."""
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.IDLE
        assert orchestrator.get_processing_state(FileType.REPORTING_CSV) == ProcessingState.IDLE
    
    def test_processing_state_transitions(self, orchestrator, sample_xlsx_file):
        """Test processing state transitions during workflow."""
        # Initial state should be idle
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.IDLE
        
        # Start processing - should transition to processing
        batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.PROCESSING
        
        # Complete processing - should transition to completed
        orchestrator.complete_processing(batch_id)
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.COMPLETED
        
        # Reset state - should return to idle
        orchestrator.reset_processing_state(FileType.CAMPAIGN_XLSX)
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.IDLE
    
    def test_error_state_handling(self, orchestrator, sample_xlsx_file):
        """Test processing state transitions on error."""
        batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        
        # Simulate processing error
        error = ProcessingError(
            message="Test error",
            stage=ProcessingStage.PARSE,
            timestamp=datetime.now(),
            technical_details="Mock error for testing"
        )
        orchestrator.handle_processing_error(batch_id, error)
        
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.ERROR
    
    def test_concurrent_processing_isolation(self, orchestrator, sample_xlsx_file, sample_csv_file):
        """Test that processing states are isolated between file types."""
        # Start processing both file types
        xlsx_batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        csv_batch_id = orchestrator.start_processing(sample_csv_file, FileType.REPORTING_CSV)
        
        # Both should be in processing state
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.PROCESSING
        assert orchestrator.get_processing_state(FileType.REPORTING_CSV) == ProcessingState.PROCESSING
        
        # Complete XLSX processing
        orchestrator.complete_processing(xlsx_batch_id)
        
        # Only XLSX should be completed, CSV should still be processing
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.COMPLETED
        assert orchestrator.get_processing_state(FileType.REPORTING_CSV) == ProcessingState.PROCESSING


class TestUploadBlocking:
    """Test upload blocking when processing is active."""
    
    def test_upload_blocking_single_file_type(self, orchestrator, sample_xlsx_file):
        """Test that uploads are blocked when processing is active for same file type."""
        # Start initial processing
        batch_id_1 = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        
        # Attempt second upload of same file type should be blocked
        with pytest.raises(ValueError, match="Processing already active for campaign_xlsx"):
            orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        
        # Complete first processing
        orchestrator.complete_processing(batch_id_1)
        
        # Now second upload should be allowed
        batch_id_2 = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        assert batch_id_2 is not None
        assert batch_id_2 != batch_id_1
    
    def test_upload_blocking_different_file_types_allowed(self, orchestrator, sample_xlsx_file, sample_csv_file):
        """Test that one file of each type can be processed concurrently."""
        # Start processing both file types should be allowed
        xlsx_batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        csv_batch_id = orchestrator.start_processing(sample_csv_file, FileType.REPORTING_CSV)
        
        assert xlsx_batch_id is not None
        assert csv_batch_id is not None
        assert xlsx_batch_id != csv_batch_id
        
        # Both should be in processing state
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.PROCESSING
        assert orchestrator.get_processing_state(FileType.REPORTING_CSV) == ProcessingState.PROCESSING
    
    def test_upload_availability_check(self, orchestrator, sample_xlsx_file):
        """Test upload availability checking."""
        # Initially both file types should be available for upload
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == True
        assert orchestrator.is_upload_available(FileType.REPORTING_CSV) == True
        
        # Start processing XLSX
        orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        
        # XLSX should not be available, CSV should still be available
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == False
        assert orchestrator.is_upload_available(FileType.REPORTING_CSV) == True


class TestEqualStageProgressTracking:
    """Test equal-stage progress tracking (25% increments)."""
    
    def test_progress_stages_definition(self, orchestrator):
        """Test that progress stages are correctly defined with equal percentages."""
        stages = orchestrator.get_progress_stages()
        
        expected_stages = {
            ProcessingStage.PARSE: 25,
            ProcessingStage.VALIDATE: 50, 
            ProcessingStage.CLASSIFY: 75,
            ProcessingStage.COMPLETE: 100
        }
        
        assert stages == expected_stages
    
    def test_progress_tracking_throughout_workflow(self, orchestrator, sample_xlsx_file):
        """Test progress tracking through complete workflow."""
        batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        
        # Initial progress should be 0%
        status = orchestrator.get_processing_status(batch_id)
        assert status.progress_percentage == 0
        assert status.current_stage == ProcessingStage.PARSE
        
        # Complete parse stage - should be 25%
        orchestrator.update_processing_stage(batch_id, ProcessingStage.PARSE)
        status = orchestrator.get_processing_status(batch_id)
        assert status.progress_percentage == 25
        assert status.current_stage == ProcessingStage.VALIDATE
        
        # Complete validate stage - should be 50%
        orchestrator.update_processing_stage(batch_id, ProcessingStage.VALIDATE)
        status = orchestrator.get_processing_status(batch_id)
        assert status.progress_percentage == 50
        assert status.current_stage == ProcessingStage.CLASSIFY
        
        # Complete classify stage - should be 75%
        orchestrator.update_processing_stage(batch_id, ProcessingStage.CLASSIFY)
        status = orchestrator.get_processing_status(batch_id)
        assert status.progress_percentage == 75
        assert status.current_stage == ProcessingStage.COMPLETE
        
        # Complete all processing - should be 100%
        orchestrator.complete_processing(batch_id)
        status = orchestrator.get_processing_status(batch_id)
        assert status.progress_percentage == 100
        assert status.current_stage == ProcessingStage.COMPLETE
    
    def test_progress_persistence_across_status_checks(self, orchestrator, sample_xlsx_file):
        """Test that progress persists across multiple status checks."""
        batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        
        # Update to validate stage
        orchestrator.update_processing_stage(batch_id, ProcessingStage.PARSE)
        
        # Multiple status checks should return consistent progress
        status_1 = orchestrator.get_processing_status(batch_id)
        status_2 = orchestrator.get_processing_status(batch_id)
        
        assert status_1.progress_percentage == status_2.progress_percentage == 25
        assert status_1.current_stage == status_2.current_stage == ProcessingStage.VALIDATE


class TestFileTypeDetectionAndParserRouting:
    """Test file type detection and parser routing."""
    
    def test_xlsx_file_type_detection(self, orchestrator, sample_xlsx_file):
        """Test XLSX file type detection."""
        file_type = orchestrator.detect_file_type(sample_xlsx_file, "campaign_data.xlsx")
        assert file_type == FileType.CAMPAIGN_XLSX
    
    def test_csv_file_type_detection(self, orchestrator, sample_csv_file):
        """Test CSV file type detection.""" 
        file_type = orchestrator.detect_file_type(sample_csv_file, "reporting_data.csv")
        assert file_type == FileType.REPORTING_CSV
    
    def test_unsupported_file_type_handling(self, orchestrator):
        """Test handling of unsupported file types."""
        unsupported_file = io.BytesIO(b"unsupported content")
        
        with pytest.raises(ValueError, match="Unsupported file type"):
            orchestrator.detect_file_type(unsupported_file, "document.txt")
    
    @patch('src.services.xlsx_campaign_parser.XLSXCampaignParser.parse_file_streaming')
    def test_xlsx_parser_routing(self, mock_xlsx_parser, orchestrator, sample_xlsx_file):
        """Test that XLSX files are routed to XLSX parser."""
        mock_xlsx_parser.return_value = {"parsed_records": 10, "errors": []}
        
        batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        orchestrator.process_file(batch_id, sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        
        mock_xlsx_parser.assert_called_once()
    
    @patch('src.services.csv_performance_parser.CSVPerformanceParser.parse_csv_stream')
    def test_csv_parser_routing(self, mock_csv_parser, orchestrator, sample_csv_file):
        """Test that CSV files are routed to CSV parser."""
        mock_csv_parser.return_value = Mock(total_parsed=10, errors=[])
        
        batch_id = orchestrator.start_processing(sample_csv_file, FileType.REPORTING_CSV)
        orchestrator.process_file(batch_id, sample_csv_file, FileType.REPORTING_CSV)
        
        mock_csv_parser.assert_called_once()


class TestErrorHandlingAndRollback:
    """Test error handling and rollback scenarios."""
    
    def test_time_ordered_error_collection(self, orchestrator, sample_xlsx_file):
        """Test that errors are collected in time order."""
        batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        
        # Add multiple errors at different times
        error_1 = ProcessingError(
            message="First error",
            stage=ProcessingStage.PARSE,
            timestamp=datetime(2024, 1, 1, 10, 0, 0),
            technical_details="First error details"
        )
        
        error_2 = ProcessingError(
            message="Second error", 
            stage=ProcessingStage.VALIDATE,
            timestamp=datetime(2024, 1, 1, 10, 0, 30),
            technical_details="Second error details"
        )
        
        orchestrator.add_processing_error(batch_id, error_1)
        orchestrator.add_processing_error(batch_id, error_2)
        
        # Errors should be returned in time order (oldest first)
        errors = orchestrator.get_processing_errors(batch_id)
        assert len(errors) == 2
        assert errors[0].timestamp < errors[1].timestamp
        assert errors[0].message == "First error"
        assert errors[1].message == "Second error"
    
    def test_contextual_error_messages(self, orchestrator, sample_xlsx_file):
        """Test that error messages include context."""
        batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        
        error = ProcessingError(
            message="Invalid UUID format",
            stage=ProcessingStage.PARSE,
            timestamp=datetime.now(),
            technical_details="UUID 'abc123' does not match required pattern",
            context={
                "file_type": "campaign_xlsx",
                "row_number": 1234,
                "column_name": "Deal/Campaign ID",
                "invalid_value": "abc123"
            }
        )
        
        orchestrator.add_processing_error(batch_id, error)
        
        errors = orchestrator.get_processing_errors(batch_id)
        assert len(errors) == 1
        assert errors[0].context["row_number"] == 1234
        assert errors[0].context["column_name"] == "Deal/Campaign ID"
    
    def test_rollback_on_processing_failure(self, orchestrator, sample_xlsx_file):
        """Test staging data rollback on processing failure."""
        batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        
        # Simulate processing failure
        error = ProcessingError(
            message="Critical processing error",
            stage=ProcessingStage.VALIDATE,
            timestamp=datetime.now(),
            technical_details="Mock critical error"
        )
        
        # Trigger rollback
        orchestrator.rollback_processing(batch_id, error)
        
        # Verify processing state is error
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.ERROR
        
        # Verify staging data is cleaned up
        # This would check that staging tables are empty for this batch_id
        staging_db = StagingDatabase()
        campaign_records = staging_db.get_campaign_batch_by_processing_id(str(batch_id))
        assert len(campaign_records) == 0
    
    def test_partial_processing_recovery_not_supported(self, orchestrator, sample_xlsx_file):
        """Test that partial processing recovery is not supported (complete restart required)."""
        batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        
        # Progress to validate stage
        orchestrator.update_processing_stage(batch_id, ProcessingStage.PARSE)
        
        # Simulate error in validate stage
        error = ProcessingError(
            message="Validation error",
            stage=ProcessingStage.VALIDATE,
            timestamp=datetime.now(),
            technical_details="Mock validation error"
        )
        
        orchestrator.handle_processing_error(batch_id, error)
        
        # Verify there's no resume capability - complete restart required
        assert orchestrator.can_resume_processing(batch_id) == False
        
        # Verify processing must be restarted from beginning
        with pytest.raises(ValueError, match="Processing failed - complete restart required"):
            orchestrator.resume_processing(batch_id)


class TestStagingDataCleanup:
    """Test staging data cleanup after processing."""
    
    def test_cleanup_after_successful_processing(self, orchestrator, sample_xlsx_file):
        """Test staging data cleanup after successful processing."""
        batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        
        # Complete processing successfully
        orchestrator.complete_processing(batch_id)
        
        # Verify cleanup is scheduled/performed
        cleanup_scheduled = orchestrator.is_cleanup_scheduled(batch_id)
        assert cleanup_scheduled == True
        
        # Perform cleanup
        orchestrator.cleanup_staging_data(batch_id)
        
        # Verify staging data is removed
        staging_db = StagingDatabase()
        campaign_records = staging_db.get_campaign_batch_by_processing_id(str(batch_id))
        assert len(campaign_records) == 0
    
    def test_cleanup_retention_on_processing_failure(self, orchestrator, sample_xlsx_file):
        """Test that staging data is retained on processing failure for investigation."""
        batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        
        # Simulate processing failure
        error = ProcessingError(
            message="Processing failed",
            stage=ProcessingStage.CLASSIFY,
            timestamp=datetime.now(),
            technical_details="Mock processing failure"
        )
        
        orchestrator.handle_processing_error(batch_id, error)
        
        # Verify cleanup is NOT scheduled on failure
        cleanup_scheduled = orchestrator.is_cleanup_scheduled(batch_id)
        assert cleanup_scheduled == False
    
    def test_manual_cleanup_after_error_investigation(self, orchestrator, sample_xlsx_file):
        """Test manual cleanup capability after error investigation."""
        batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        
        # Simulate error
        error = ProcessingError(
            message="Test error",
            stage=ProcessingStage.PARSE,
            timestamp=datetime.now(),
            technical_details="Mock error"
        )
        
        orchestrator.handle_processing_error(batch_id, error)
        
        # Manual cleanup should be available
        assert orchestrator.can_manual_cleanup(batch_id) == True
        
        # Perform manual cleanup
        orchestrator.manual_cleanup_staging_data(batch_id)
        
        # Verify data is cleaned up
        staging_db = StagingDatabase()
        campaign_records = staging_db.get_campaign_batch_by_processing_id(str(batch_id))
        assert len(campaign_records) == 0


class TestIntegrationWithParsersAndClassification:
    """Test integration with existing parsers and classification engine."""
    
    @patch.object(UploadProcessingOrchestrator, 'process_file')
    @patch('src.services.classification_integration_service.ClassificationIntegrationService')
    def test_end_to_end_xlsx_processing_workflow(self, mock_classification, mock_process_file, orchestrator, sample_xlsx_file):
        """Test complete end-to-end XLSX processing workflow."""
        # Setup mocks
        mock_process_file.return_value = {"parsed_records": 100, "errors": []}
        
        mock_classification_instance = Mock()
        mock_classification_instance.classify_complete_batch.return_value = {
            'overall_success': True,
            'campaign_classification': {'total_processed': 100, 'processing_errors': []},
            'reporting_classification': {'total_processed': 0, 'processing_errors': []},
            'cross_file_consistency': {'validation_errors': [], 'warnings': []}
        }
        mock_classification.return_value = mock_classification_instance
        
        # Mock staging database methods and classification
        with patch.object(orchestrator.staging_db, 'get_campaign_batch_by_processing_id') as mock_get_campaigns, \
             patch.object(orchestrator.classification_service, 'classify_complete_batch') as mock_classify:
            
            mock_get_campaigns.return_value = [Mock() for _ in range(100)]  # 100 mock records
            mock_classify.return_value = {
                'overall_success': True,
                'campaign_classification': {'total_processed': 100, 'processing_errors': []},
                'reporting_classification': {'total_processed': 0, 'processing_errors': []},
                'cross_file_consistency': {'validation_errors': [], 'warnings': []}
            }
            
            # Execute complete workflow
            batch_id = orchestrator.process_complete_workflow(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        
        # Verify workflow completion
        status = orchestrator.get_processing_status(batch_id)
        assert status.progress_percentage == 100
        assert status.current_stage == ProcessingStage.COMPLETE
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.COMPLETED
        
        # Verify process_file was called
        mock_process_file.assert_called_once_with(batch_id, sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        
        # Verify classification was called
        mock_classify.assert_called_once_with(batch_id)
    
    @patch.object(UploadProcessingOrchestrator, 'process_file')
    @patch('src.services.classification_integration_service.ClassificationIntegrationService')
    def test_end_to_end_csv_processing_workflow(self, mock_classification, mock_process_file, orchestrator, sample_csv_file):
        """Test complete end-to-end CSV processing workflow."""
        # Setup mocks - create CSVParsingResult mock
        mock_csv_result = Mock()
        mock_csv_result.errors = []  # No parsing errors
        mock_csv_result.total_records_processed = 50
        mock_process_file.return_value = mock_csv_result
        
        mock_classification_instance = Mock()
        mock_classification_instance.classify_complete_batch.return_value = {
            'overall_success': True,
            'campaign_classification': {'total_processed': 0, 'processing_errors': []},
            'reporting_classification': {'total_processed': 50, 'processing_errors': []},
            'cross_file_consistency': {'validation_errors': [], 'warnings': []}
        }
        mock_classification.return_value = mock_classification_instance
        
        # Mock staging database methods and classification
        with patch.object(orchestrator.staging_db, 'get_reporting_batch_by_processing_id') as mock_get_reporting, \
             patch.object(orchestrator.classification_service, 'classify_complete_batch') as mock_classify:
            
            mock_get_reporting.return_value = [Mock() for _ in range(50)]  # 50 mock records
            mock_classify.return_value = {
                'overall_success': True,
                'campaign_classification': {'total_processed': 0, 'processing_errors': []},
                'reporting_classification': {'total_processed': 50, 'processing_errors': []},
                'cross_file_consistency': {'validation_errors': [], 'warnings': []}
            }
            
            # Execute complete workflow
            batch_id = orchestrator.process_complete_workflow(sample_csv_file, FileType.REPORTING_CSV)
        
        # Verify workflow completion
        status = orchestrator.get_processing_status(batch_id)
        assert status.progress_percentage == 100
        assert status.current_stage == ProcessingStage.COMPLETE
        assert orchestrator.get_processing_state(FileType.REPORTING_CSV) == ProcessingState.COMPLETED
        
        # Verify process_file was called
        mock_process_file.assert_called_once_with(batch_id, sample_csv_file, FileType.REPORTING_CSV)
        
        # Verify classification was called
        mock_classify.assert_called_once_with(batch_id)
    
    def test_memory_efficiency_with_large_files(self, orchestrator, large_xlsx_file):
        """Test memory efficiency with 250MB files."""
        # This test would verify memory usage remains under limits
        # Using memory profiling or mock verification
        
        with patch('src.services.xlsx_campaign_parser.XLSXCampaignParser') as mock_parser:
            mock_parser_instance = Mock()
            mock_parser_instance.parse_to_staging.return_value = {"parsed_records": 10000, "errors": []}
            mock_parser.return_value = mock_parser_instance
            
            # Process large file
            batch_id = orchestrator.start_processing(large_xlsx_file, FileType.CAMPAIGN_XLSX)
            
            # Verify streaming/chunked processing is used
            assert orchestrator.uses_streaming_processing() == True
    
    def test_concurrent_file_type_processing(self, orchestrator, sample_xlsx_file, sample_csv_file):
        """Test concurrent processing of different file types."""
        with patch('src.services.xlsx_campaign_parser.XLSXCampaignParser') as mock_xlsx, \
             patch('src.services.csv_performance_parser.CSVPerformanceParser') as mock_csv, \
             patch('src.services.classification_integration_service.ClassificationIntegrationService') as mock_classification:
            
            # Setup mocks
            mock_xlsx.return_value.parse_to_staging.return_value = {"parsed_records": 100, "errors": []}
            mock_csv.return_value.parse_to_staging.return_value = Mock(total_parsed=50, parsing_errors=[])
            mock_classification.return_value.classify_complete_batch.return_value = {'overall_success': True}
            
            # Start concurrent processing
            xlsx_batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
            csv_batch_id = orchestrator.start_processing(sample_csv_file, FileType.REPORTING_CSV)
            
            # Both should be processing concurrently
            assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.PROCESSING
            assert orchestrator.get_processing_state(FileType.REPORTING_CSV) == ProcessingState.PROCESSING
            
            # Both should have different batch IDs
            assert xlsx_batch_id != csv_batch_id


class TestProcessingStatusCommunication:
    """Test processing status communication for frontend integration."""
    
    def test_status_response_format(self, orchestrator, sample_xlsx_file):
        """Test that status responses match expected format for frontend."""
        batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        
        status = orchestrator.get_processing_status(batch_id)
        
        # Verify status response structure
        assert hasattr(status, 'processing_batch_id')
        assert hasattr(status, 'file_type')
        assert hasattr(status, 'processing_state')
        assert hasattr(status, 'current_stage')
        assert hasattr(status, 'progress_percentage')
        assert hasattr(status, 'start_time')
        assert hasattr(status, 'errors')
        
        # Verify data types
        assert isinstance(status.processing_batch_id, UUID)
        assert isinstance(status.file_type, FileType)
        assert isinstance(status.processing_state, ProcessingState)
        assert isinstance(status.current_stage, ProcessingStage)
        assert isinstance(status.progress_percentage, int)
        assert isinstance(status.errors, list)
    
    def test_polling_optimization_for_2_second_intervals(self, orchestrator, sample_xlsx_file):
        """Test that status polling is optimized for 2-second intervals."""
        batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        
        # Multiple status checks should be efficient
        start_time = datetime.now()
        
        for _ in range(10):
            status = orchestrator.get_processing_status(batch_id)
            assert status is not None
        
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        
        # 10 status checks should complete quickly (under 1 second)
        assert total_time < 1.0
    
    def test_error_response_structure_for_frontend(self, orchestrator, sample_xlsx_file):
        """Test error response structure matches frontend expectations."""
        batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        
        # Add structured error
        error = ProcessingError(
            message="Invalid UUID format in row 1,234",
            stage=ProcessingStage.PARSE,
            timestamp=datetime.now(),
            technical_details="UUID 'abc123' does not match pattern",
            context={
                "file_type": "campaign_xlsx",
                "row_number": 1234,
                "column_name": "Deal/Campaign ID",
                "invalid_value": "abc123"
            },
            suggested_actions=[
                "Verify Deal UUID format in source system",
                "Check row 1,234 in uploaded file"
            ]
        )
        
        orchestrator.add_processing_error(batch_id, error)
        
        # Get error response
        errors = orchestrator.get_processing_errors(batch_id)
        assert len(errors) == 1
        
        error_response = errors[0]
        
        # Verify error structure for frontend consumption
        assert hasattr(error_response, 'message')
        assert hasattr(error_response, 'stage')
        assert hasattr(error_response, 'timestamp')
        assert hasattr(error_response, 'technical_details')
        assert hasattr(error_response, 'context')
        assert hasattr(error_response, 'suggested_actions')
        
        # Verify context includes required fields
        assert error_response.context["row_number"] == 1234
        assert error_response.context["column_name"] == "Deal/Campaign ID"
        assert error_response.suggested_actions is not None
        assert len(error_response.suggested_actions) > 0