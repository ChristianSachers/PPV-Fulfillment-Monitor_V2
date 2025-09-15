"""
Unit tests for Upload Processing Orchestrator

Focused unit tests for individual components:
1. Batch ID generation and validation
2. Processing state management and transitions
3. Progress tracking calculations
4. File type detection logic
5. Error collection and formatting
6. Cleanup scheduling logic
"""
import pytest
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from unittest.mock import Mock, patch, MagicMock
from enum import Enum
import io

from src.services.upload_processing_orchestrator import (
    UploadProcessingOrchestrator,
    ProcessingState,
    ProcessingStage,
    FileType,
    ProcessingStatus,
    ProcessingError
)


class TestBatchIDGeneration:
    """Unit tests for processing batch ID generation."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for testing."""
        return UploadProcessingOrchestrator()
    
    def test_generate_batch_id_returns_uuid(self, orchestrator):
        """Test that generate_processing_batch_id returns a valid UUID."""
        batch_id = orchestrator.generate_processing_batch_id()
        
        assert isinstance(batch_id, UUID)
        assert str(batch_id) != "00000000-0000-0000-0000-000000000000"  # Not null UUID
    
    def test_generate_batch_id_uniqueness(self, orchestrator):
        """Test that consecutive batch ID generations are unique."""
        batch_ids = [orchestrator.generate_processing_batch_id() for _ in range(100)]
        
        # All batch IDs should be unique
        assert len(set(batch_ids)) == 100
    
    def test_batch_id_format_validation(self, orchestrator):
        """Test that generated batch IDs follow UUID4 format."""
        batch_id = orchestrator.generate_processing_batch_id()
        uuid_str = str(batch_id)
        
        # UUID4 format: 8-4-4-4-12 characters separated by hyphens
        parts = uuid_str.split('-')
        assert len(parts) == 5
        assert len(parts[0]) == 8
        assert len(parts[1]) == 4
        assert len(parts[2]) == 4
        assert len(parts[3]) == 4
        assert len(parts[4]) == 12
        
        # All characters should be hexadecimal
        for part in parts:
            assert all(c in '0123456789abcdef-' for c in part.lower())
    
    def test_batch_id_storage_and_retrieval(self, orchestrator):
        """Test that batch IDs are properly stored and retrieved."""
        batch_id = orchestrator.generate_processing_batch_id()
        
        # Store batch ID for file type
        orchestrator._store_batch_id(FileType.CAMPAIGN_XLSX, batch_id)
        
        # Retrieve batch ID
        retrieved_id = orchestrator.get_current_batch_id(FileType.CAMPAIGN_XLSX)
        
        assert retrieved_id == batch_id
    
    def test_batch_id_isolation_between_file_types(self, orchestrator):
        """Test that batch IDs are isolated between different file types."""
        xlsx_batch_id = orchestrator.generate_processing_batch_id()
        csv_batch_id = orchestrator.generate_processing_batch_id()
        
        orchestrator._store_batch_id(FileType.CAMPAIGN_XLSX, xlsx_batch_id)
        orchestrator._store_batch_id(FileType.REPORTING_CSV, csv_batch_id)
        
        assert orchestrator.get_current_batch_id(FileType.CAMPAIGN_XLSX) == xlsx_batch_id
        assert orchestrator.get_current_batch_id(FileType.REPORTING_CSV) == csv_batch_id
        assert xlsx_batch_id != csv_batch_id
    
    def test_batch_id_cleanup_on_completion(self, orchestrator):
        """Test that batch IDs are cleaned up on processing completion."""
        batch_id = orchestrator.generate_processing_batch_id()
        orchestrator._store_batch_id(FileType.CAMPAIGN_XLSX, batch_id)
        
        # Complete processing should clear batch ID
        orchestrator._clear_batch_id(FileType.CAMPAIGN_XLSX)
        
        retrieved_id = orchestrator.get_current_batch_id(FileType.CAMPAIGN_XLSX)
        assert retrieved_id is None


class TestProcessingStateManagement:
    """Unit tests for processing state management."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for testing."""
        return UploadProcessingOrchestrator()
    
    def test_initial_processing_state(self, orchestrator):
        """Test that initial processing state is IDLE for all file types."""
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.IDLE
        assert orchestrator.get_processing_state(FileType.REPORTING_CSV) == ProcessingState.IDLE
    
    def test_processing_state_enum_values(self):
        """Test that ProcessingState enum has required values."""
        expected_states = ['IDLE', 'PROCESSING', 'COMPLETED', 'ERROR']
        actual_states = [state.name for state in ProcessingState]
        
        for expected in expected_states:
            assert expected in actual_states
    
    def test_set_processing_state(self, orchestrator):
        """Test setting processing state for specific file type."""
        orchestrator.set_processing_state(FileType.CAMPAIGN_XLSX, ProcessingState.PROCESSING)
        
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.PROCESSING
        # Other file type should remain unchanged
        assert orchestrator.get_processing_state(FileType.REPORTING_CSV) == ProcessingState.IDLE
    
    def test_processing_state_transitions(self, orchestrator):
        """Test valid processing state transitions."""
        # IDLE -> PROCESSING
        orchestrator.set_processing_state(FileType.CAMPAIGN_XLSX, ProcessingState.PROCESSING)
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.PROCESSING
        
        # PROCESSING -> COMPLETED
        orchestrator.set_processing_state(FileType.CAMPAIGN_XLSX, ProcessingState.COMPLETED)
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.COMPLETED
        
        # COMPLETED -> IDLE (reset)
        orchestrator.set_processing_state(FileType.CAMPAIGN_XLSX, ProcessingState.IDLE)
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.IDLE
    
    def test_error_state_transitions(self, orchestrator):
        """Test error state transitions."""
        # Start processing
        orchestrator.set_processing_state(FileType.CAMPAIGN_XLSX, ProcessingState.PROCESSING)
        
        # Transition to error
        orchestrator.set_processing_state(FileType.CAMPAIGN_XLSX, ProcessingState.ERROR)
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.ERROR
        
        # Can reset from error to idle
        orchestrator.set_processing_state(FileType.CAMPAIGN_XLSX, ProcessingState.IDLE)
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.IDLE
    
    def test_concurrent_state_management(self, orchestrator):
        """Test that states are managed independently for different file types."""
        # Set different states for different file types
        orchestrator.set_processing_state(FileType.CAMPAIGN_XLSX, ProcessingState.PROCESSING)
        orchestrator.set_processing_state(FileType.REPORTING_CSV, ProcessingState.COMPLETED)
        
        # Verify independent state management
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.PROCESSING
        assert orchestrator.get_processing_state(FileType.REPORTING_CSV) == ProcessingState.COMPLETED
        
        # Change one state, other should remain unchanged
        orchestrator.set_processing_state(FileType.CAMPAIGN_XLSX, ProcessingState.ERROR)
        
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.ERROR
        assert orchestrator.get_processing_state(FileType.REPORTING_CSV) == ProcessingState.COMPLETED
    
    def test_is_processing_active(self, orchestrator):
        """Test is_processing_active method."""
        # Initially not active
        assert orchestrator.is_processing_active(FileType.CAMPAIGN_XLSX) == False
        
        # Active when processing
        orchestrator.set_processing_state(FileType.CAMPAIGN_XLSX, ProcessingState.PROCESSING)
        assert orchestrator.is_processing_active(FileType.CAMPAIGN_XLSX) == True
        
        # Not active when completed
        orchestrator.set_processing_state(FileType.CAMPAIGN_XLSX, ProcessingState.COMPLETED)
        assert orchestrator.is_processing_active(FileType.CAMPAIGN_XLSX) == False
        
        # Not active when error
        orchestrator.set_processing_state(FileType.CAMPAIGN_XLSX, ProcessingState.ERROR)
        assert orchestrator.is_processing_active(FileType.CAMPAIGN_XLSX) == False
        
        # Not active when idle
        orchestrator.set_processing_state(FileType.CAMPAIGN_XLSX, ProcessingState.IDLE)
        assert orchestrator.is_processing_active(FileType.CAMPAIGN_XLSX) == False
    
    def test_upload_availability_based_on_state(self, orchestrator):
        """Test upload availability based on processing state."""
        # Available when idle
        orchestrator.set_processing_state(FileType.CAMPAIGN_XLSX, ProcessingState.IDLE)
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == True
        
        # Not available when processing
        orchestrator.set_processing_state(FileType.CAMPAIGN_XLSX, ProcessingState.PROCESSING)
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == False
        
        # Available when completed
        orchestrator.set_processing_state(FileType.CAMPAIGN_XLSX, ProcessingState.COMPLETED)
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == True
        
        # Available when error (for retry)
        orchestrator.set_processing_state(FileType.CAMPAIGN_XLSX, ProcessingState.ERROR)
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == True


class TestProgressCalculations:
    """Unit tests for progress tracking calculations."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for testing."""
        return UploadProcessingOrchestrator()
    
    def test_progress_stage_percentages(self, orchestrator):
        """Test that progress stages have correct percentages."""
        stages = orchestrator.get_progress_stages()
        
        expected_stages = {
            ProcessingStage.PARSE: 25,
            ProcessingStage.VALIDATE: 50,
            ProcessingStage.CLASSIFY: 75,
            ProcessingStage.COMPLETE: 100
        }
        
        assert stages == expected_stages
    
    def test_calculate_progress_percentage(self, orchestrator):
        """Test progress percentage calculation for each stage."""
        assert orchestrator.calculate_progress_percentage(ProcessingStage.PARSE) == 25
        assert orchestrator.calculate_progress_percentage(ProcessingStage.VALIDATE) == 50
        assert orchestrator.calculate_progress_percentage(ProcessingStage.CLASSIFY) == 75
        assert orchestrator.calculate_progress_percentage(ProcessingStage.COMPLETE) == 100
    
    def test_get_next_stage(self, orchestrator):
        """Test getting next processing stage."""
        assert orchestrator.get_next_stage(ProcessingStage.PARSE) == ProcessingStage.VALIDATE
        assert orchestrator.get_next_stage(ProcessingStage.VALIDATE) == ProcessingStage.CLASSIFY
        assert orchestrator.get_next_stage(ProcessingStage.CLASSIFY) == ProcessingStage.COMPLETE
        assert orchestrator.get_next_stage(ProcessingStage.COMPLETE) == ProcessingStage.COMPLETE  # Stay at complete
    
    def test_is_stage_completed(self, orchestrator):
        """Test checking if a processing stage is completed."""
        # Create mock status
        batch_id = uuid4()
        
        # Initially no stages completed
        assert orchestrator.is_stage_completed(batch_id, ProcessingStage.PARSE) == False
        
        # Mark parse stage as completed
        orchestrator._update_completed_stages(batch_id, ProcessingStage.PARSE)
        
        assert orchestrator.is_stage_completed(batch_id, ProcessingStage.PARSE) == True
        assert orchestrator.is_stage_completed(batch_id, ProcessingStage.VALIDATE) == False
    
    def test_progress_tracking_consistency(self, orchestrator):
        """Test that progress tracking is consistent across multiple calls."""
        batch_id = uuid4()
        
        # Set current stage
        orchestrator._set_current_stage(batch_id, ProcessingStage.VALIDATE)
        
        # Multiple calls should return consistent results
        progress_1 = orchestrator.calculate_progress_percentage(ProcessingStage.VALIDATE)
        progress_2 = orchestrator.calculate_progress_percentage(ProcessingStage.VALIDATE)
        
        assert progress_1 == progress_2 == 50


class TestFileTypeDetection:
    """Unit tests for file type detection logic."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for testing."""
        return UploadProcessingOrchestrator()
    
    def test_xlsx_file_detection_by_extension(self, orchestrator):
        """Test XLSX file detection by file extension."""
        mock_file = io.BytesIO(b"mock xlsx content")
        
        file_type = orchestrator.detect_file_type(mock_file, "campaign_data.xlsx")
        assert file_type == FileType.CAMPAIGN_XLSX
        
        file_type = orchestrator.detect_file_type(mock_file, "CAMPAIGN_DATA.XLSX")
        assert file_type == FileType.CAMPAIGN_XLSX
    
    def test_csv_file_detection_by_extension(self, orchestrator):
        """Test CSV file detection by file extension."""
        mock_file = io.BytesIO(b"mock csv content")
        
        file_type = orchestrator.detect_file_type(mock_file, "reporting_data.csv")
        assert file_type == FileType.REPORTING_CSV
        
        file_type = orchestrator.detect_file_type(mock_file, "REPORTING_DATA.CSV")
        assert file_type == FileType.REPORTING_CSV
    
    def test_unsupported_file_extension(self, orchestrator):
        """Test handling of unsupported file extensions."""
        mock_file = io.BytesIO(b"mock content")
        
        with pytest.raises(ValueError, match="Unsupported file type"):
            orchestrator.detect_file_type(mock_file, "document.txt")
        
        with pytest.raises(ValueError, match="Unsupported file type"):
            orchestrator.detect_file_type(mock_file, "data.pdf")
    
    def test_file_type_enum_values(self):
        """Test that FileType enum has required values."""
        expected_types = ['CAMPAIGN_XLSX', 'REPORTING_CSV']
        actual_types = [file_type.name for file_type in FileType]
        
        for expected in expected_types:
            assert expected in actual_types
    
    def test_file_type_to_parser_mapping(self, orchestrator):
        """Test that file types map to correct parsers."""
        parser_mapping = orchestrator.get_parser_mapping()
        
        assert FileType.CAMPAIGN_XLSX in parser_mapping
        assert FileType.REPORTING_CSV in parser_mapping
        
        # Should return parser class references
        assert parser_mapping[FileType.CAMPAIGN_XLSX].__name__ == "XLSXCampaignParser"
        assert parser_mapping[FileType.REPORTING_CSV].__name__ == "CSVPerformanceParser"
    
    def test_case_insensitive_file_detection(self, orchestrator):
        """Test that file detection is case insensitive."""
        mock_file = io.BytesIO(b"mock content")
        
        # Test various case combinations
        test_cases = [
            ("file.xlsx", FileType.CAMPAIGN_XLSX),
            ("FILE.XLSX", FileType.CAMPAIGN_XLSX),
            ("File.Xlsx", FileType.CAMPAIGN_XLSX),
            ("data.csv", FileType.REPORTING_CSV),
            ("DATA.CSV", FileType.REPORTING_CSV),
            ("Data.Csv", FileType.REPORTING_CSV)
        ]
        
        for filename, expected_type in test_cases:
            detected_type = orchestrator.detect_file_type(mock_file, filename)
            assert detected_type == expected_type


class TestErrorCollectionAndFormatting:
    """Unit tests for error collection and formatting."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for testing."""
        return UploadProcessingOrchestrator()
    
    @pytest.fixture
    def sample_error(self):
        """Create sample processing error."""
        return ProcessingError(
            message="Test error message",
            stage=ProcessingStage.PARSE,
            timestamp=datetime.now(),
            technical_details="Technical details about the error",
            context={
                "file_type": "campaign_xlsx",
                "row_number": 123,
                "column_name": "Deal ID"
            },
            suggested_actions=["Check data format", "Verify source file"]
        )
    
    def test_error_object_creation(self, sample_error):
        """Test ProcessingError object creation and attributes."""
        assert isinstance(sample_error, ProcessingError)
        assert sample_error.message == "Test error message"
        assert sample_error.stage == ProcessingStage.PARSE
        assert isinstance(sample_error.timestamp, datetime)
        assert sample_error.technical_details == "Technical details about the error"
        assert isinstance(sample_error.context, dict)
        assert isinstance(sample_error.suggested_actions, list)
    
    def test_add_processing_error(self, orchestrator, sample_error):
        """Test adding processing errors to batch."""
        batch_id = uuid4()
        
        # Initially no errors
        errors = orchestrator.get_processing_errors(batch_id)
        assert len(errors) == 0
        
        # Add error
        orchestrator.add_processing_error(batch_id, sample_error)
        
        # Should have one error
        errors = orchestrator.get_processing_errors(batch_id)
        assert len(errors) == 1
        assert errors[0] == sample_error
    
    def test_time_ordered_error_collection(self, orchestrator):
        """Test that errors are collected in time order."""
        batch_id = uuid4()
        
        # Create errors with different timestamps
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
        
        error_3 = ProcessingError(
            message="Third error",
            stage=ProcessingStage.CLASSIFY,
            timestamp=datetime(2024, 1, 1, 10, 0, 15),
            technical_details="Third error details"
        )
        
        # Add errors in non-chronological order
        orchestrator.add_processing_error(batch_id, error_2)
        orchestrator.add_processing_error(batch_id, error_1)
        orchestrator.add_processing_error(batch_id, error_3)
        
        # Errors should be returned in chronological order (oldest first)
        errors = orchestrator.get_processing_errors(batch_id)
        assert len(errors) == 3
        assert errors[0].timestamp == datetime(2024, 1, 1, 10, 0, 0)  # error_1
        assert errors[1].timestamp == datetime(2024, 1, 1, 10, 0, 15)  # error_3
        assert errors[2].timestamp == datetime(2024, 1, 1, 10, 0, 30)  # error_2
    
    def test_error_context_preservation(self, orchestrator):
        """Test that error context is preserved correctly."""
        batch_id = uuid4()
        
        error = ProcessingError(
            message="UUID validation failed",
            stage=ProcessingStage.PARSE,
            timestamp=datetime.now(),
            technical_details="Invalid UUID format",
            context={
                "file_type": "campaign_xlsx",
                "row_number": 1234,
                "column_name": "Deal/Campaign ID",
                "invalid_value": "abc123",
                "expected_format": "UUID4"
            },
            suggested_actions=[
                "Check UUID format in source data",
                "Verify data export process"
            ]
        )
        
        orchestrator.add_processing_error(batch_id, error)
        
        retrieved_errors = orchestrator.get_processing_errors(batch_id)
        retrieved_error = retrieved_errors[0]
        
        assert retrieved_error.context["file_type"] == "campaign_xlsx"
        assert retrieved_error.context["row_number"] == 1234
        assert retrieved_error.context["column_name"] == "Deal/Campaign ID"
        assert retrieved_error.context["invalid_value"] == "abc123"
        assert len(retrieved_error.suggested_actions) == 2
    
    def test_error_isolation_between_batches(self, orchestrator, sample_error):
        """Test that errors are isolated between different processing batches."""
        batch_id_1 = uuid4()
        batch_id_2 = uuid4()
        
        # Add error to first batch
        orchestrator.add_processing_error(batch_id_1, sample_error)
        
        # First batch should have error, second should not
        errors_1 = orchestrator.get_processing_errors(batch_id_1)
        errors_2 = orchestrator.get_processing_errors(batch_id_2)
        
        assert len(errors_1) == 1
        assert len(errors_2) == 0
    
    def test_clear_errors_for_batch(self, orchestrator, sample_error):
        """Test clearing errors for specific batch."""
        batch_id = uuid4()
        
        # Add multiple errors
        orchestrator.add_processing_error(batch_id, sample_error)
        orchestrator.add_processing_error(batch_id, sample_error)
        
        # Should have errors
        assert len(orchestrator.get_processing_errors(batch_id)) == 2
        
        # Clear errors
        orchestrator.clear_processing_errors(batch_id)
        
        # Should have no errors
        assert len(orchestrator.get_processing_errors(batch_id)) == 0


class TestCleanupScheduling:
    """Unit tests for cleanup scheduling logic."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for testing."""
        return UploadProcessingOrchestrator()
    
    def test_cleanup_scheduling_on_success(self, orchestrator):
        """Test that cleanup is scheduled on successful processing."""
        batch_id = uuid4()
        
        # Complete processing successfully
        orchestrator._mark_processing_completed(batch_id, success=True)
        
        # Cleanup should be scheduled
        assert orchestrator.is_cleanup_scheduled(batch_id) == True
    
    def test_cleanup_not_scheduled_on_failure(self, orchestrator):
        """Test that cleanup is not scheduled on processing failure."""
        batch_id = uuid4()
        
        # Complete processing with failure
        orchestrator._mark_processing_completed(batch_id, success=False)
        
        # Cleanup should not be scheduled
        assert orchestrator.is_cleanup_scheduled(batch_id) == False
    
    def test_manual_cleanup_availability(self, orchestrator):
        """Test manual cleanup availability after processing."""
        batch_id = uuid4()
        
        # Initially manual cleanup not available
        assert orchestrator.can_manual_cleanup(batch_id) == False
        
        # After processing failure, manual cleanup should be available
        orchestrator._mark_processing_completed(batch_id, success=False)
        assert orchestrator.can_manual_cleanup(batch_id) == True
        
        # After successful processing, manual cleanup should also be available
        orchestrator._mark_processing_completed(batch_id, success=True)
        assert orchestrator.can_manual_cleanup(batch_id) == True
    
    def test_cleanup_status_tracking(self, orchestrator):
        """Test cleanup status tracking."""
        batch_id = uuid4()
        
        # Initially not cleaned up
        assert orchestrator.is_cleanup_completed(batch_id) == False
        
        # Schedule cleanup
        orchestrator._schedule_cleanup(batch_id)
        assert orchestrator.is_cleanup_scheduled(batch_id) == True
        assert orchestrator.is_cleanup_completed(batch_id) == False
        
        # Complete cleanup
        orchestrator._mark_cleanup_completed(batch_id)
        assert orchestrator.is_cleanup_completed(batch_id) == True
    
    def test_cleanup_batch_isolation(self, orchestrator):
        """Test that cleanup scheduling is isolated between batches."""
        batch_id_1 = uuid4()
        batch_id_2 = uuid4()
        
        # Schedule cleanup for first batch only
        orchestrator._schedule_cleanup(batch_id_1)
        
        # Only first batch should have cleanup scheduled
        assert orchestrator.is_cleanup_scheduled(batch_id_1) == True
        assert orchestrator.is_cleanup_scheduled(batch_id_2) == False


class TestProcessingStatusObject:
    """Unit tests for ProcessingStatus object structure."""
    
    def test_processing_status_creation(self):
        """Test ProcessingStatus object creation."""
        batch_id = uuid4()
        start_time = datetime.now()
        
        status = ProcessingStatus(
            processing_batch_id=batch_id,
            file_type=FileType.CAMPAIGN_XLSX,
            processing_state=ProcessingState.PROCESSING,
            current_stage=ProcessingStage.VALIDATE,
            progress_percentage=50,
            start_time=start_time,
            errors=[]
        )
        
        assert status.processing_batch_id == batch_id
        assert status.file_type == FileType.CAMPAIGN_XLSX
        assert status.processing_state == ProcessingState.PROCESSING
        assert status.current_stage == ProcessingStage.VALIDATE
        assert status.progress_percentage == 50
        assert status.start_time == start_time
        assert status.errors == []
    
    def test_processing_status_with_errors(self):
        """Test ProcessingStatus with errors."""
        batch_id = uuid4()
        error = ProcessingError(
            message="Test error",
            stage=ProcessingStage.PARSE,
            timestamp=datetime.now(),
            technical_details="Test error details"
        )
        
        status = ProcessingStatus(
            processing_batch_id=batch_id,
            file_type=FileType.CAMPAIGN_XLSX,
            processing_state=ProcessingState.ERROR,
            current_stage=ProcessingStage.PARSE,
            progress_percentage=25,
            start_time=datetime.now(),
            errors=[error]
        )
        
        assert len(status.errors) == 1
        assert status.errors[0] == error
        assert status.processing_state == ProcessingState.ERROR
    
    def test_processing_status_serialization(self):
        """Test ProcessingStatus can be serialized for API responses."""
        batch_id = uuid4()
        start_time = datetime.now()
        
        status = ProcessingStatus(
            processing_batch_id=batch_id,
            file_type=FileType.CAMPAIGN_XLSX,
            processing_state=ProcessingState.COMPLETED,
            current_stage=ProcessingStage.COMPLETE,
            progress_percentage=100,
            start_time=start_time,
            errors=[]
        )
        
        # Should be able to convert to dict for JSON serialization
        status_dict = {
            'processing_batch_id': str(status.processing_batch_id),
            'file_type': status.file_type.value,
            'processing_state': status.processing_state.value,
            'current_stage': status.current_stage.value,
            'progress_percentage': status.progress_percentage,
            'start_time': status.start_time.isoformat(),
            'errors': []
        }
        
        assert status_dict['processing_batch_id'] == str(batch_id)
        assert status_dict['file_type'] == 'campaign_xlsx'
        assert status_dict['processing_state'] == 'completed'
        assert status_dict['current_stage'] == 'complete'
        assert status_dict['progress_percentage'] == 100