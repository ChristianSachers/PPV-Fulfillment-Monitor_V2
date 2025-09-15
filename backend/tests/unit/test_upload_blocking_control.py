"""
Unit tests for Upload Blocking and Processing Control

Critical requirements from Phase 1.1:
- Single File Per Type: Only one Campaign XLSX + one Reporting CSV concurrent processing maximum
- Upload Blocking: Disable upload capability when processing is active for that file type
- State Management: Processing state per file type (idle/processing/completed/error)
- Upload Control: Prevent resource conflicts and simplify system architecture

Tests upload availability, blocking mechanisms, and processing control logic.
"""
import pytest
from datetime import datetime
from uuid import UUID, uuid4
from unittest.mock import Mock, patch, MagicMock
import io

from src.services.upload_processing_orchestrator import (
    UploadProcessingOrchestrator,
    ProcessingState,
    ProcessingStage,
    FileType,
    ProcessingStatus,
    ProcessingError
)


# Global fixtures available to all test classes
@pytest.fixture
def orchestrator():
    """Create orchestrator for testing."""
    return UploadProcessingOrchestrator()

@pytest.fixture
def sample_xlsx_file():
    """Create sample XLSX file for testing."""
    return io.BytesIO(b"mock xlsx content")

@pytest.fixture
def sample_csv_file():
    """Create sample CSV file for testing."""
    return io.BytesIO(b"mock csv content")


class TestSingleFilePerTypeEnforcement:
    """Test enforcement of single file per type processing limit."""
    
    def test_single_xlsx_processing_allowed(self, orchestrator, sample_xlsx_file):
        """Test that single XLSX file processing is allowed."""
        # First XLSX upload should be allowed
        batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        
        assert batch_id is not None
        assert isinstance(batch_id, UUID)
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.PROCESSING
    
    def test_second_xlsx_processing_blocked(self, orchestrator, sample_xlsx_file):
        """Test that second XLSX file processing is blocked."""
        # First XLSX upload
        batch_id_1 = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        assert batch_id_1 is not None
        
        # Second XLSX upload should be blocked
        with pytest.raises(ValueError, match="Processing already active for campaign_xlsx"):
            orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        
        # Processing state should remain unchanged
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.PROCESSING
    
    def test_single_csv_processing_allowed(self, orchestrator, sample_csv_file):
        """Test that single CSV file processing is allowed."""
        # First CSV upload should be allowed
        batch_id = orchestrator.start_processing(sample_csv_file, FileType.REPORTING_CSV)
        
        assert batch_id is not None
        assert isinstance(batch_id, UUID)
        assert orchestrator.get_processing_state(FileType.REPORTING_CSV) == ProcessingState.PROCESSING
    
    def test_second_csv_processing_blocked(self, orchestrator, sample_csv_file):
        """Test that second CSV file processing is blocked."""
        # First CSV upload
        batch_id_1 = orchestrator.start_processing(sample_csv_file, FileType.REPORTING_CSV)
        assert batch_id_1 is not None
        
        # Second CSV upload should be blocked
        with pytest.raises(ValueError, match="Processing already active for reporting_csv"):
            orchestrator.start_processing(sample_csv_file, FileType.REPORTING_CSV)
        
        # Processing state should remain unchanged
        assert orchestrator.get_processing_state(FileType.REPORTING_CSV) == ProcessingState.PROCESSING
    
    def test_concurrent_different_file_types_allowed(self, orchestrator, sample_xlsx_file, sample_csv_file):
        """Test that one file of each type can be processed concurrently."""
        # Both file types should be allowed concurrently
        xlsx_batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        csv_batch_id = orchestrator.start_processing(sample_csv_file, FileType.REPORTING_CSV)
        
        assert xlsx_batch_id is not None
        assert csv_batch_id is not None
        assert xlsx_batch_id != csv_batch_id
        
        # Both should be in processing state
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.PROCESSING
        assert orchestrator.get_processing_state(FileType.REPORTING_CSV) == ProcessingState.PROCESSING
    
    def test_processing_limit_per_file_type_independence(self, orchestrator, sample_xlsx_file, sample_csv_file):
        """Test that processing limits are independent per file type."""
        # Start processing both file types
        xlsx_batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX) 
        csv_batch_id = orchestrator.start_processing(sample_csv_file, FileType.REPORTING_CSV)
        
        # Additional XLSX should be blocked, but CSV state should not affect this
        with pytest.raises(ValueError, match="Processing already active for campaign_xlsx"):
            orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        
        # Additional CSV should be blocked, but XLSX state should not affect this
        with pytest.raises(ValueError, match="Processing already active for reporting_csv"):
            orchestrator.start_processing(sample_csv_file, FileType.REPORTING_CSV)
        
        # Original processing should continue normally
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.PROCESSING
        assert orchestrator.get_processing_state(FileType.REPORTING_CSV) == ProcessingState.PROCESSING


class TestUploadAvailabilityChecking:
    """Test upload availability checking logic."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for testing."""
        return UploadProcessingOrchestrator()
    
    @pytest.fixture
    def sample_xlsx_file(self):
        """Create sample XLSX file for testing."""
        return io.BytesIO(b"mock xlsx content")
    
    @pytest.fixture
    def sample_csv_file(self):
        """Create sample CSV file for testing."""
        return io.BytesIO(b"mock csv content")
    
    def test_initial_upload_availability(self, orchestrator):
        """Test that uploads are initially available for both file types."""
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == True
        assert orchestrator.is_upload_available(FileType.REPORTING_CSV) == True
    
    def test_upload_availability_during_processing(self, orchestrator, sample_xlsx_file):
        """Test upload availability during active processing."""
        # Start processing XLSX
        orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        
        # XLSX uploads should not be available
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == False
        
        # CSV uploads should still be available
        assert orchestrator.is_upload_available(FileType.REPORTING_CSV) == True
    
    def test_upload_availability_after_completion(self, orchestrator, sample_xlsx_file):
        """Test upload availability after processing completion."""
        # Process and complete
        batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        orchestrator.complete_processing(batch_id)
        
        # Upload should be available again
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == True
        assert orchestrator.is_upload_available(FileType.REPORTING_CSV) == True
    
    def test_upload_availability_after_error(self, orchestrator, sample_xlsx_file):
        """Test upload availability after processing error."""
        # Start processing and simulate error
        batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        
        error = ProcessingError(
            message="Processing failed",
            stage=ProcessingStage.PARSE,
            timestamp=datetime.now(),
            technical_details="Mock processing error"
        )
        orchestrator.handle_processing_error(batch_id, error)
        
        # Upload should be available again for retry
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == True
        assert orchestrator.is_upload_available(FileType.REPORTING_CSV) == True
    
    def test_upload_availability_concurrent_file_types(self, orchestrator, sample_xlsx_file, sample_csv_file):
        """Test upload availability with concurrent processing of different file types."""
        # Start processing XLSX only
        orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        
        # XLSX should not be available, CSV should be available
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == False
        assert orchestrator.is_upload_available(FileType.REPORTING_CSV) == True
        
        # Start processing CSV
        orchestrator.start_processing(sample_csv_file, FileType.REPORTING_CSV)
        
        # Both should not be available
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == False
        assert orchestrator.is_upload_available(FileType.REPORTING_CSV) == False
    
    def test_upload_availability_check_performance(self, orchestrator):
        """Test that upload availability checks are fast for frequent polling."""
        start_time = datetime.now()
        
        # Perform many availability checks (simulating frequent UI updates)
        for _ in range(100):
            orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX)
            orchestrator.is_upload_available(FileType.REPORTING_CSV)
        
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        
        # 200 availability checks should complete very quickly (under 0.1 seconds)
        assert total_time < 0.1


class TestProcessingStateBasedControl:
    """Test processing control based on processing states."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for testing."""
        return UploadProcessingOrchestrator()
    
    @pytest.fixture
    def sample_xlsx_file(self):
        """Create sample XLSX file for testing."""
        return io.BytesIO(b"mock xlsx content")
    
    def test_idle_state_allows_uploads(self, orchestrator):
        """Test that IDLE state allows new uploads."""
        # Ensure state is IDLE
        orchestrator.set_processing_state(FileType.CAMPAIGN_XLSX, ProcessingState.IDLE)
        
        # Upload should be allowed
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == True
        
        # Should be able to start processing
        batch_id = orchestrator.start_processing(io.BytesIO(b"test"), FileType.CAMPAIGN_XLSX)
        assert batch_id is not None
    
    def test_processing_state_blocks_uploads(self, orchestrator, sample_xlsx_file):
        """Test that PROCESSING state blocks new uploads."""
        # Start processing to set PROCESSING state
        orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        
        # Upload should be blocked
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == False
        
        # Attempt to start new processing should fail
        with pytest.raises(ValueError, match="Processing already active"):
            orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
    
    def test_completed_state_allows_uploads(self, orchestrator, sample_xlsx_file):
        """Test that COMPLETED state allows new uploads."""
        # Process and complete
        batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        orchestrator.complete_processing(batch_id)
        
        # Upload should be allowed
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == True
        
        # Should be able to start new processing
        new_batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        assert new_batch_id is not None
        assert new_batch_id != batch_id
    
    def test_error_state_allows_uploads(self, orchestrator, sample_xlsx_file):
        """Test that ERROR state allows new uploads (for retry)."""
        # Start processing and trigger error
        batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        
        error = ProcessingError(
            message="Test error",
            stage=ProcessingStage.PARSE,
            timestamp=datetime.now(),
            technical_details="Mock error"
        )
        orchestrator.handle_processing_error(batch_id, error)
        
        # Upload should be allowed for retry
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == True
        
        # Should be able to start new processing
        retry_batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        assert retry_batch_id is not None
        assert retry_batch_id != batch_id
    
    def test_processing_state_isolation_between_file_types(self, orchestrator, sample_xlsx_file):
        """Test that processing states are isolated between file types."""
        # Set different states for different file types
        orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)  # PROCESSING
        orchestrator.set_processing_state(FileType.REPORTING_CSV, ProcessingState.COMPLETED)
        
        # XLSX should be blocked, CSV should be available
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == False
        assert orchestrator.is_upload_available(FileType.REPORTING_CSV) == True
    
    def test_state_transition_affects_upload_availability(self, orchestrator, sample_xlsx_file):
        """Test that state transitions properly affect upload availability."""
        # Start with IDLE (available)
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == True
        
        # Start processing -> PROCESSING (not available)
        batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == False
        
        # Complete processing -> COMPLETED (available)
        orchestrator.complete_processing(batch_id)
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == True
        
        # Reset to IDLE (available)
        orchestrator.reset_processing_state(FileType.CAMPAIGN_XLSX)
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == True


class TestProcessingCancellationAndReset:
    """Test processing cancellation and state reset functionality."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for testing."""
        return UploadProcessingOrchestrator()
    
    @pytest.fixture
    def sample_xlsx_file(self):
        """Create sample XLSX file for testing."""
        return io.BytesIO(b"mock xlsx content")
    
    def test_processing_cancellation_resets_state(self, orchestrator, sample_xlsx_file):
        """Test that cancelling processing resets state to allow new uploads."""
        # Start processing
        batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == False
        
        # Cancel processing
        orchestrator.cancel_processing(batch_id)
        
        # Upload should be available again
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == True
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.IDLE
    
    def test_processing_reset_clears_batch_tracking(self, orchestrator, sample_xlsx_file):
        """Test that reset clears batch ID tracking."""
        # Start processing
        batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        assert orchestrator.get_current_batch_id(FileType.CAMPAIGN_XLSX) == batch_id
        
        # Reset processing state
        orchestrator.reset_processing_state(FileType.CAMPAIGN_XLSX)
        
        # Batch ID should be cleared
        assert orchestrator.get_current_batch_id(FileType.CAMPAIGN_XLSX) is None
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.IDLE
    
    def test_cancellation_isolation_between_file_types(self, orchestrator, sample_xlsx_file, sample_csv_file):
        """Test that cancellation only affects the specific file type."""
        # Start processing both file types
        xlsx_batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        csv_batch_id = orchestrator.start_processing(sample_csv_file, FileType.REPORTING_CSV)
        
        # Both should be unavailable
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == False
        assert orchestrator.is_upload_available(FileType.REPORTING_CSV) == False
        
        # Cancel only XLSX processing
        orchestrator.cancel_processing(xlsx_batch_id)
        
        # XLSX should be available, CSV should remain unavailable
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == True
        assert orchestrator.is_upload_available(FileType.REPORTING_CSV) == False
    
    def test_cancel_non_existent_processing(self, orchestrator):
        """Test cancelling non-existent processing batch."""
        invalid_batch_id = uuid4()
        
        # Should handle gracefully without affecting system state
        orchestrator.cancel_processing(invalid_batch_id)
        
        # System should remain in normal state
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == True
        assert orchestrator.is_upload_available(FileType.REPORTING_CSV) == True
    
    def test_cancel_already_completed_processing(self, orchestrator, sample_xlsx_file):
        """Test cancelling already completed processing."""
        # Complete processing
        batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        orchestrator.complete_processing(batch_id)
        
        # Attempt to cancel completed processing
        orchestrator.cancel_processing(batch_id)
        
        # Should remain in completed state
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.COMPLETED
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == True


class TestUploadBlockingUserExperience:
    """Test upload blocking from user experience perspective."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for testing."""
        return UploadProcessingOrchestrator()
    
    def test_upload_blocking_message_generation(self, orchestrator):
        """Test generation of user-friendly upload blocking messages."""
        # Start processing XLSX
        orchestrator.start_processing(io.BytesIO(b"test"), FileType.CAMPAIGN_XLSX)
        
        # Should provide clear blocking message
        blocking_message = orchestrator.get_upload_blocking_message(FileType.CAMPAIGN_XLSX)
        
        assert "Processing in progress" in blocking_message
        assert "CAMPAIGN_XLSX" in blocking_message or "Campaign" in blocking_message
        assert "wait" in blocking_message.lower() or "cancel" in blocking_message.lower()
    
    def test_different_blocking_messages_for_file_types(self, orchestrator):
        """Test that different file types get appropriate blocking messages."""
        # Block both file types
        orchestrator.start_processing(io.BytesIO(b"xlsx"), FileType.CAMPAIGN_XLSX)
        orchestrator.start_processing(io.BytesIO(b"csv"), FileType.REPORTING_CSV)
        
        xlsx_message = orchestrator.get_upload_blocking_message(FileType.CAMPAIGN_XLSX)
        csv_message = orchestrator.get_upload_blocking_message(FileType.REPORTING_CSV)
        
        # Messages should be different and file-type specific
        assert xlsx_message != csv_message
        assert "Campaign" in xlsx_message or "XLSX" in xlsx_message
        assert "Reporting" in csv_message or "CSV" in csv_message
    
    def test_no_blocking_message_when_available(self, orchestrator):
        """Test that no blocking message is shown when uploads are available."""
        # Ensure uploads are available
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == True
        
        # Should return None or empty message
        blocking_message = orchestrator.get_upload_blocking_message(FileType.CAMPAIGN_XLSX)
        assert blocking_message is None or blocking_message == ""
    
    def test_processing_status_for_upload_control_ui(self, orchestrator, sample_xlsx_file):
        """Test processing status information for upload control UI."""
        # Start processing
        batch_id = orchestrator.start_processing(sample_xlsx_file, FileType.CAMPAIGN_XLSX)
        
        # Should provide status for UI control
        ui_status = orchestrator.get_upload_control_status(FileType.CAMPAIGN_XLSX)
        
        assert ui_status['upload_available'] == False
        assert ui_status['processing_active'] == True
        assert ui_status['current_batch_id'] == str(batch_id)
        assert ui_status['can_cancel'] == True
        assert 'blocking_message' in ui_status
    
    def test_upload_control_status_consistency(self, orchestrator):
        """Test that upload control status is consistent across calls."""
        # Multiple status checks should return consistent results
        status_checks = [
            orchestrator.get_upload_control_status(FileType.CAMPAIGN_XLSX)
            for _ in range(5)
        ]
        
        # All status checks should be identical
        first_status = status_checks[0]
        for status in status_checks[1:]:
            assert status == first_status


class TestResourceConflictPrevention:
    """Test resource conflict prevention through upload control."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for testing."""
        return UploadProcessingOrchestrator()
    
    def test_memory_resource_protection(self, orchestrator):
        """Test that upload blocking prevents memory resource conflicts."""
        large_file_1 = io.BytesIO(b"0" * (100 * 1024 * 1024))  # 100MB
        large_file_2 = io.BytesIO(b"1" * (100 * 1024 * 1024))  # 100MB
        
        # First large file should be accepted
        batch_id_1 = orchestrator.start_processing(large_file_1, FileType.CAMPAIGN_XLSX)
        assert batch_id_1 is not None
        
        # Second large file should be blocked to prevent memory conflict
        with pytest.raises(ValueError, match="Processing already active"):
            orchestrator.start_processing(large_file_2, FileType.CAMPAIGN_XLSX)
    
    def test_database_connection_resource_protection(self, orchestrator):
        """Test that upload blocking prevents database connection conflicts."""
        # Mock database-intensive processing
        with patch('src.services.xlsx_campaign_parser.XLSXCampaignParser') as mock_parser:
            mock_parser.return_value.parse_to_staging.return_value = {"parsed_records": 10000, "errors": []}
            
            # First processing should be allowed
            batch_id_1 = orchestrator.start_processing(io.BytesIO(b"xlsx1"), FileType.CAMPAIGN_XLSX)
            assert batch_id_1 is not None
            
            # Second processing should be blocked to prevent connection conflicts
            with pytest.raises(ValueError, match="Processing already active"):
                orchestrator.start_processing(io.BytesIO(b"xlsx2"), FileType.CAMPAIGN_XLSX)
    
    def test_staging_table_isolation(self, orchestrator):
        """Test that upload blocking ensures staging table isolation."""
        # Start processing first file
        batch_id_1 = orchestrator.start_processing(io.BytesIO(b"file1"), FileType.CAMPAIGN_XLSX)
        
        # Verify that staging operations are isolated by batch ID
        assert orchestrator.get_current_batch_id(FileType.CAMPAIGN_XLSX) == batch_id_1
        
        # Second file should be blocked to maintain staging isolation
        with pytest.raises(ValueError, match="Processing already active"):
            orchestrator.start_processing(io.BytesIO(b"file2"), FileType.CAMPAIGN_XLSX)
        
        # Batch ID should remain unchanged
        assert orchestrator.get_current_batch_id(FileType.CAMPAIGN_XLSX) == batch_id_1
    
    def test_processing_pipeline_serialization(self, orchestrator):
        """Test that upload blocking enforces processing pipeline serialization."""
        # Start processing with mock pipeline stages
        batch_id = orchestrator.start_processing(io.BytesIO(b"test"), FileType.CAMPAIGN_XLSX)
        
        # Advance through pipeline stages
        orchestrator.update_processing_stage(batch_id, ProcessingStage.PARSE)
        orchestrator.update_processing_stage(batch_id, ProcessingStage.VALIDATE)
        
        # Upload should remain blocked throughout pipeline
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == False
        
        # Only after completion should upload be available
        orchestrator.complete_processing(batch_id)
        assert orchestrator.is_upload_available(FileType.CAMPAIGN_XLSX) == True