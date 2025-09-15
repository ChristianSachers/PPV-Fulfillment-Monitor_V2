"""
Unit tests for Error Handling and Rollback Scenarios

Critical requirements from Phase 1.1:
- Time-ordered error collection with contextual error messages
- Rollback scenarios with staging data cleanup on failure
- Error recovery requires complete restart (no resume capability) 
- Staging data retention on failure for investigation
- Comprehensive error reporting with technical details and suggested actions
- Error response structure for frontend integration

Tests error collection, rollback mechanisms, and recovery workflows.
"""
import pytest
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from unittest.mock import Mock, patch, MagicMock
import io
from decimal import Decimal

from src.services.upload_processing_orchestrator import (
    UploadProcessingOrchestrator,
    ProcessingError,
    ProcessingStage,
    ProcessingState,
    FileType,
    ProcessingStatus
)
from src.database.staging_connection import StagingDatabase


class TestTimeOrderedErrorCollection:
    """Test time-ordered error collection and management."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for testing."""
        return UploadProcessingOrchestrator()
    
    @pytest.fixture
    def batch_id(self):
        """Create batch ID for testing."""
        return uuid4()
    
    def test_error_chronological_ordering(self, orchestrator, batch_id):
        """Test that errors are stored and retrieved in chronological order (oldest first)."""
        # Create errors with different timestamps
        error_3 = ProcessingError(
            message="Third error (latest)",
            stage=ProcessingStage.CLASSIFY,
            timestamp=datetime(2024, 1, 1, 10, 2, 0),
            technical_details="Third error details"
        )
        
        error_1 = ProcessingError(
            message="First error (earliest)",
            stage=ProcessingStage.PARSE,
            timestamp=datetime(2024, 1, 1, 10, 0, 0),
            technical_details="First error details"
        )
        
        error_2 = ProcessingError(
            message="Second error (middle)",
            stage=ProcessingStage.VALIDATE,
            timestamp=datetime(2024, 1, 1, 10, 1, 0),
            technical_details="Second error details"
        )
        
        # Add errors in non-chronological order
        orchestrator.add_processing_error(batch_id, error_3)
        orchestrator.add_processing_error(batch_id, error_1)
        orchestrator.add_processing_error(batch_id, error_2)
        
        # Retrieve errors - should be in chronological order
        errors = orchestrator.get_processing_errors(batch_id)
        
        assert len(errors) == 3
        assert errors[0].message == "First error (earliest)"
        assert errors[1].message == "Second error (middle)"
        assert errors[2].message == "Third error (latest)"
        
        # Verify timestamps are in ascending order
        for i in range(len(errors) - 1):
            assert errors[i].timestamp <= errors[i + 1].timestamp
    
    def test_error_context_preservation(self, orchestrator, batch_id):
        """Test that error context is preserved with all required fields."""
        error = ProcessingError(
            message="UUID validation failed in campaign data",
            stage=ProcessingStage.PARSE,
            timestamp=datetime.now(),
            technical_details="UUID 'invalid-uuid-123' does not match UUID4 pattern",
            context={
                "file_type": "campaign_xlsx",
                "row_number": 1234,
                "column_name": "Deal/Campaign ID",
                "invalid_value": "invalid-uuid-123",
                "expected_format": "UUID4",
                "file_name": "campaign_data.xlsx"
            },
            suggested_actions=[
                "Verify Deal UUID format in source system",
                "Check row 1,234 in uploaded file",
                "Contact data administrator if UUID should be valid"
            ]
        )
        
        orchestrator.add_processing_error(batch_id, error)
        
        retrieved_errors = orchestrator.get_processing_errors(batch_id)
        retrieved_error = retrieved_errors[0]
        
        # Verify all context fields are preserved
        assert retrieved_error.context["file_type"] == "campaign_xlsx"
        assert retrieved_error.context["row_number"] == 1234
        assert retrieved_error.context["column_name"] == "Deal/Campaign ID"
        assert retrieved_error.context["invalid_value"] == "invalid-uuid-123"
        assert retrieved_error.context["expected_format"] == "UUID4"
        assert retrieved_error.context["file_name"] == "campaign_data.xlsx"
        
        # Verify suggested actions are preserved
        assert len(retrieved_error.suggested_actions) == 3
        assert "Verify Deal UUID format" in retrieved_error.suggested_actions[0]
        assert "Check row 1,234" in retrieved_error.suggested_actions[1]
        assert "Contact data administrator" in retrieved_error.suggested_actions[2] 
    
    def test_multiple_errors_same_stage(self, orchestrator, batch_id):
        """Test handling multiple errors in the same processing stage."""
        base_time = datetime(2024, 1, 1, 10, 0, 0)
        
        # Create multiple parse errors
        errors = []
        for i in range(5):
            error = ProcessingError(
                message=f"Parse error {i + 1}",
                stage=ProcessingStage.PARSE,
                timestamp=base_time + timedelta(seconds=i * 10),
                technical_details=f"Parse error details {i + 1}",
                context={"row_number": (i + 1) * 100}
            )
            errors.append(error)
            orchestrator.add_processing_error(batch_id, error)
        
        retrieved_errors = orchestrator.get_processing_errors(batch_id)
        
        # Should have all errors in chronological order
        assert len(retrieved_errors) == 5
        for i, error in enumerate(retrieved_errors):
            assert error.message == f"Parse error {i + 1}"
            assert error.context["row_number"] == (i + 1) * 100
    
    def test_error_isolation_between_batches(self, orchestrator):
        """Test that errors are isolated between different processing batches."""
        batch_id_1 = uuid4()
        batch_id_2 = uuid4()
        
        error_1 = ProcessingError(
            message="Error for batch 1",
            stage=ProcessingStage.PARSE,
            timestamp=datetime.now(),
            technical_details="Batch 1 error details"
        )
        
        error_2 = ProcessingError(
            message="Error for batch 2", 
            stage=ProcessingStage.VALIDATE,
            timestamp=datetime.now(),
            technical_details="Batch 2 error details"
        )
        
        # Add errors to different batches
        orchestrator.add_processing_error(batch_id_1, error_1)
        orchestrator.add_processing_error(batch_id_2, error_2)
        
        # Verify isolation
        errors_1 = orchestrator.get_processing_errors(batch_id_1)
        errors_2 = orchestrator.get_processing_errors(batch_id_2)
        
        assert len(errors_1) == 1
        assert len(errors_2) == 1
        assert errors_1[0].message == "Error for batch 1"
        assert errors_2[0].message == "Error for batch 2"
    
    def test_error_limit_prevention(self, orchestrator, batch_id):
        """Test that error collection doesn't consume excessive memory."""
        # Add many errors to test memory management
        for i in range(1000):
            error = ProcessingError(
                message=f"Error {i}",
                stage=ProcessingStage.PARSE,
                timestamp=datetime.now() + timedelta(microseconds=i),
                technical_details=f"Error details {i}"
            )
            orchestrator.add_processing_error(batch_id, error)
        
        errors = orchestrator.get_processing_errors(batch_id)
        
        # Should handle large error collections efficiently
        assert len(errors) <= 1000  # May implement truncation
        # If truncation is implemented, newest errors should be preserved
        if len(errors) < 1000:
            assert "Error 999" in errors[-1].message


class TestRollbackScenarios:
    """Test rollback scenarios and staging data cleanup on failure."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for testing."""
        return UploadProcessingOrchestrator()
    
    @pytest.fixture
    def batch_id(self):
        """Create batch ID for testing."""
        return uuid4()
    
    @pytest.fixture
    def staging_db(self):
        """Create staging database for testing."""
        return StagingDatabase()
    
    def test_rollback_on_parse_failure(self, orchestrator, batch_id, staging_db):
        """Test rollback when parsing fails."""
        # Simulate parse failure
        parse_error = ProcessingError(
            message="File parsing failed",
            stage=ProcessingStage.PARSE,
            timestamp=datetime.now(),
            technical_details="Invalid file format or corrupted data",
            context={
                "file_type": "campaign_xlsx",
                "error_location": "Row 500",
                "bytes_processed": 1024000
            }
        )
        
        # Trigger rollback
        orchestrator.rollback_processing(batch_id, parse_error)
        
        # Verify processing state is set to ERROR
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.ERROR
        
        # Verify staging data is cleaned up
        campaign_records = staging_db.get_campaign_batch_by_processing_id(str(batch_id))
        assert len(campaign_records) == 0
        
        # Verify error is recorded
        errors = orchestrator.get_processing_errors(batch_id)
        assert len(errors) == 1
        assert errors[0].message == "File parsing failed"
    
    def test_rollback_on_validation_failure(self, orchestrator, batch_id, staging_db):
        """Test rollback when validation fails."""
        # Simulate validation failure after successful parsing
        validation_error = ProcessingError(
            message="Data validation failed",
            stage=ProcessingStage.VALIDATE,
            timestamp=datetime.now(),
            technical_details="Multiple UUID format violations detected",
            context={
                "file_type": "campaign_xlsx",
                "records_parsed": 1000,
                "validation_failures": 25
            }
        )
        
        # Trigger rollback
        orchestrator.rollback_processing(batch_id, validation_error)
        
        # Verify processing state is ERROR
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.ERROR
        
        # Verify staging data is cleaned up
        campaign_records = staging_db.get_campaign_batch_by_processing_id(str(batch_id))
        reporting_records = staging_db.get_reporting_batch_by_processing_id(str(batch_id))
        
        assert len(campaign_records) == 0
        assert len(reporting_records) == 0
    
    def test_rollback_on_classification_failure(self, orchestrator, batch_id, staging_db):
        """Test rollback when classification fails."""
        # Simulate classification failure
        classification_error = ProcessingError(
            message="Record classification failed",
            stage=ProcessingStage.CLASSIFY,
            timestamp=datetime.now(),
            technical_details="Production database connection timeout during classification",
            context={
                "file_type": "campaign_xlsx",
                "records_processed": 800,
                "records_remaining": 200,
                "classification_errors": 5
            }
        )
        
        # Trigger rollback
        orchestrator.rollback_processing(batch_id, classification_error)
        
        # Verify state and cleanup
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.ERROR
        
        # Staging data should be cleaned up
        campaign_records = staging_db.get_campaign_batch_by_processing_id(str(batch_id))
        assert len(campaign_records) == 0
    
    def test_partial_rollback_cleanup(self, orchestrator, batch_id):
        """Test that rollback cleans up partial processing artifacts."""
        # Simulate partial processing with multiple stages completed
        orchestrator._create_initial_status(batch_id, FileType.CAMPAIGN_XLSX)
        orchestrator.update_processing_stage(batch_id, ProcessingStage.PARSE)
        orchestrator.update_processing_stage(batch_id, ProcessingStage.VALIDATE)
        
        # Create error at classify stage
        error = ProcessingError(
            message="Classification timeout",
            stage=ProcessingStage.CLASSIFY,
            timestamp=datetime.now(),
            technical_details="Database connection timeout"
        )
        
        # Trigger rollback
        orchestrator.rollback_processing(batch_id, error)
        
        # Verify complete cleanup
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.ERROR
        assert orchestrator.get_current_batch_id(FileType.CAMPAIGN_XLSX) is None
        
        # Progress should be reset
        status = orchestrator.get_processing_status(batch_id)
        assert status.processing_state == ProcessingState.ERROR
    
    def test_rollback_transaction_integrity(self, orchestrator, batch_id):
        """Test that rollback maintains transaction integrity."""
        with patch.object(orchestrator.staging_db, 'cleanup_batch_records') as mock_cleanup:
            # Simulate rollback
            error = ProcessingError(
                message="Transaction integrity test",
                stage=ProcessingStage.VALIDATE,
                timestamp=datetime.now(),
                technical_details="Mock transaction error"
            )
            
            orchestrator.rollback_processing(batch_id, error)
            
            # Verify cleanup methods are called
            mock_cleanup.assert_called_once_with(str(batch_id))
    
    def test_rollback_preserves_error_history(self, orchestrator, batch_id):
        """Test that rollback preserves error history for investigation."""
        # Add multiple errors during processing
        error_1 = ProcessingError(
            message="Warning during parse",
            stage=ProcessingStage.PARSE,
            timestamp=datetime.now() - timedelta(minutes=2),
            technical_details="Non-critical parse warning"
        )
        
        error_2 = ProcessingError(
            message="Critical validation failure",
            stage=ProcessingStage.VALIDATE,
            timestamp=datetime.now(),
            technical_details="Multiple validation failures detected"
        )
        
        orchestrator.add_processing_error(batch_id, error_1)
        orchestrator.add_processing_error(batch_id, error_2)
        
        # Trigger rollback
        orchestrator.rollback_processing(batch_id, error_2)
        
        # Error history should be preserved
        errors = orchestrator.get_processing_errors(batch_id)
        assert len(errors) == 2
        assert errors[0].message == "Warning during parse"
        assert errors[1].message == "Critical validation failure"


class TestErrorRecoveryAndRestart:
    """Test error recovery requiring complete restart (no resume capability)."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for testing."""
        return UploadProcessingOrchestrator()
    
    def test_no_resume_capability_after_error(self, orchestrator):
        """Test that processing cannot be resumed after error (complete restart required)."""
        batch_id = uuid4()
        
        # Simulate processing with error
        orchestrator._create_initial_status(batch_id, FileType.CAMPAIGN_XLSX)
        orchestrator.update_processing_stage(batch_id, ProcessingStage.PARSE)
        
        error = ProcessingError(
            message="Processing failed",
            stage=ProcessingStage.VALIDATE,
            timestamp=datetime.now(),
            technical_details="Mock validation error"
        )
        
        orchestrator.handle_processing_error(batch_id, error)
        
        # Verify resume is not supported
        assert orchestrator.can_resume_processing(batch_id) == False
        
        # Attempt to resume should fail
        with pytest.raises(ValueError, match="Processing failed - complete restart required"):
            orchestrator.resume_processing(batch_id)
    
    def test_complete_restart_after_error(self, orchestrator):
        """Test that complete restart is required after processing error."""
        # First processing attempt with error
        file_content = io.BytesIO(b"test content")
        batch_id_1 = orchestrator.start_processing(file_content, FileType.CAMPAIGN_XLSX)
        
        error = ProcessingError(
            message="Processing failed",
            stage=ProcessingStage.PARSE,
            timestamp=datetime.now(),
            technical_details="Mock parse error"
        )
        
        orchestrator.handle_processing_error(batch_id_1, error)
        
        # Should be able to start completely new processing
        file_content_2 = io.BytesIO(b"test content 2")
        batch_id_2 = orchestrator.start_processing(file_content_2, FileType.CAMPAIGN_XLSX)
        
        # New processing should have different batch ID
        assert batch_id_2 != batch_id_1
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.PROCESSING
    
    def test_error_state_reset_on_new_upload(self, orchestrator):
        """Test that error state is reset when starting new upload."""
        # Process and trigger error
        batch_id_1 = orchestrator.start_processing(io.BytesIO(b"content"), FileType.CAMPAIGN_XLSX)
        
        error = ProcessingError(
            message="Processing error", 
            stage=ProcessingStage.CLASSIFY,
            timestamp=datetime.now(),
            technical_details="Mock classification error"
        )
        
        orchestrator.handle_processing_error(batch_id_1, error)
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.ERROR
        
        # Start new upload should reset state
        batch_id_2 = orchestrator.start_processing(io.BytesIO(b"new content"), FileType.CAMPAIGN_XLSX)
        
        assert orchestrator.get_processing_state(FileType.CAMPAIGN_XLSX) == ProcessingState.PROCESSING
        assert batch_id_2 != batch_id_1
    
    def test_error_investigation_data_retention(self, orchestrator):
        """Test that error data is retained for investigation until manual cleanup."""
        batch_id = uuid4()
        
        # Create error with context
        error = ProcessingError(
            message="Critical processing failure",
            stage=ProcessingStage.CLASSIFY,
            timestamp=datetime.now(),
            technical_details="Database connection lost during classification",
            context={
                "records_processed": 850,
                "connection_timeout": "30 seconds",
                "retry_attempts": 3
            }
        )
        
        orchestrator.handle_processing_error(batch_id, error)
        
        # Error data should be retained
        errors = orchestrator.get_processing_errors(batch_id)
        assert len(errors) == 1
        assert errors[0].context["records_processed"] == 850
        
        # Manual cleanup should be available
        assert orchestrator.can_manual_cleanup(batch_id) == True
        
        # After manual cleanup, data should be removed
        orchestrator.manual_cleanup_error_data(batch_id)
        errors_after_cleanup = orchestrator.get_processing_errors(batch_id)
        assert len(errors_after_cleanup) == 0
    
    def test_restart_workflow_independence(self, orchestrator):
        """Test that restarted processing is completely independent from failed processing."""
        # First attempt
        batch_id_1 = orchestrator.start_processing(io.BytesIO(b"attempt1"), FileType.CAMPAIGN_XLSX)
        orchestrator.update_processing_stage(batch_id_1, ProcessingStage.PARSE)
        
        error_1 = ProcessingError(
            message="First attempt failed",
            stage=ProcessingStage.VALIDATE,
            timestamp=datetime.now(),
            technical_details="First attempt error"
        )
        
        orchestrator.handle_processing_error(batch_id_1, error_1)
        
        # Second attempt (restart)
        batch_id_2 = orchestrator.start_processing(io.BytesIO(b"attempt2"), FileType.CAMPAIGN_XLSX)
        orchestrator.update_processing_stage(batch_id_2, ProcessingStage.PARSE)
        orchestrator.update_processing_stage(batch_id_2, ProcessingStage.VALIDATE)
        
        # Progress should be independent
        status_1 = orchestrator.get_processing_status(batch_id_1)
        status_2 = orchestrator.get_processing_status(batch_id_2)
        
        assert status_1.processing_state == ProcessingState.ERROR
        assert status_2.processing_state == ProcessingState.PROCESSING
        assert status_1.progress_percentage != status_2.progress_percentage
        
        # Errors should be isolated
        errors_1 = orchestrator.get_processing_errors(batch_id_1)  
        errors_2 = orchestrator.get_processing_errors(batch_id_2)
        
        assert len(errors_1) == 1
        assert len(errors_2) == 0


class TestComprehensiveErrorReporting:
    """Test comprehensive error reporting for frontend integration."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for testing."""
        return UploadProcessingOrchestrator()
    
    def test_structured_error_response_format(self, orchestrator):
        """Test that error responses match expected structure for frontend."""
        batch_id = uuid4()
        
        error = ProcessingError(
            message="UUID validation failed in row 1,234",
            stage=ProcessingStage.PARSE,
            timestamp=datetime.now(),
            technical_details="UUID 'abc123' does not match pattern [0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            context={
                "file_type": "campaign_xlsx",
                "row_number": 1234,
                "column_name": "Deal/Campaign ID",
                "invalid_value": "abc123"
            },
            suggested_actions=[
                "Verify Deal UUID format in source system",
                "Check row 1,234 in uploaded file",
                "Contact data administrator if UUID should be valid"
            ]
        )
        
        orchestrator.add_processing_error(batch_id, error)
        
        # Get structured error response for frontend
        error_response = orchestrator.get_structured_error_response(batch_id)
        
        # Verify response structure
        assert "batch_id" in error_response
        assert "timestamp" in error_response
        assert "errors" in error_response
        
        error_detail = error_response["errors"][0]
        assert "error_id" in error_detail
        assert "timestamp" in error_detail
        assert "category" in error_detail
        assert "severity" in error_detail
        assert "code" in error_detail
        assert "message" in error_detail
        assert "technical_details" in error_detail
        assert "context" in error_detail
        assert "suggested_actions" in error_detail
    
    def test_error_categorization(self, orchestrator):
        """Test that errors are properly categorized for frontend display."""
        batch_id = uuid4()
        
        errors = [
            ProcessingError(
                message="Invalid file format",
                stage=ProcessingStage.PARSE,
                timestamp=datetime.now(),
                technical_details="File is not valid XLSX format",
                error_category="parsing"
            ),
            ProcessingError(
                message="UUID validation failed",
                stage=ProcessingStage.VALIDATE,
                timestamp=datetime.now(),
                technical_details="Invalid UUID format detected",
                error_category="validation"
            ),
            ProcessingError(
                message="Database connection timeout",
                stage=ProcessingStage.CLASSIFY,
                timestamp=datetime.now(),
                technical_details="Cannot connect to production database",
                error_category="system"
            )
        ]
        
        for error in errors:
            orchestrator.add_processing_error(batch_id, error)
        
        # Get categorized errors
        categorized_errors = orchestrator.get_categorized_errors(batch_id)
        
        assert "parsing" in categorized_errors
        assert "validation" in categorized_errors
        assert "system" in categorized_errors
        
        assert len(categorized_errors["parsing"]) == 1
        assert len(categorized_errors["validation"]) == 1
        assert len(categorized_errors["system"]) == 1
    
    def test_error_severity_classification(self, orchestrator):
        """Test error severity classification for user priority."""
        batch_id = uuid4()
        
        # Add errors with different severities
        critical_error = ProcessingError(
            message="Critical processing failure",
            stage=ProcessingStage.CLASSIFY,
            timestamp=datetime.now(),
            technical_details="Cannot proceed with processing",
            severity="error"
        )
        
        warning = ProcessingError(
            message="Data quality warning",
            stage=ProcessingStage.VALIDATE,
            timestamp=datetime.now(),
            technical_details="Some data may be incomplete",
            severity="warning"
        )
        
        info = ProcessingError(
            message="Processing information",
            stage=ProcessingStage.PARSE,
            timestamp=datetime.now(),
            technical_details="Large file being processed",
            severity="info"
        )
        
        orchestrator.add_processing_error(batch_id, critical_error)
        orchestrator.add_processing_error(batch_id, warning)
        orchestrator.add_processing_error(batch_id, info)
        
        # Get errors by severity
        errors_by_severity = orchestrator.get_errors_by_severity(batch_id)
        
        assert len(errors_by_severity["error"]) == 1
        assert len(errors_by_severity["warning"]) == 1
        assert len(errors_by_severity["info"]) == 1
    
    def test_actionable_error_suggestions(self, orchestrator):
        """Test that errors include actionable suggestions for users."""
        batch_id = uuid4()
        
        error = ProcessingError(
            message="File size exceeds limit",
            stage=ProcessingStage.PARSE,
            timestamp=datetime.now(),
            technical_details="File size is 300MB, limit is 250MB",
            context={
                "file_size_mb": 300,
                "limit_mb": 250
            },
            suggested_actions=[
                "Reduce file size by removing unnecessary data",
                "Split large file into smaller segments",
                "Compress file using ZIP format",
                "Contact administrator to increase size limit"
            ]
        )
        
        orchestrator.add_processing_error(batch_id, error)
        
        errors = orchestrator.get_processing_errors(batch_id)
        retrieved_error = errors[0]
        
        # Verify actionable suggestions
        assert len(retrieved_error.suggested_actions) == 4
        assert "Reduce file size" in retrieved_error.suggested_actions[0]
        assert "Split large file" in retrieved_error.suggested_actions[1]
        assert "Compress file" in retrieved_error.suggested_actions[2]
        assert "Contact administrator" in retrieved_error.suggested_actions[3]
    
    def test_error_aggregation_for_similar_issues(self, orchestrator):
        """Test aggregation of similar errors for cleaner reporting."""
        batch_id = uuid4()
        
        # Add multiple similar UUID validation errors
        for i in range(5):
            error = ProcessingError(
                message=f"Invalid UUID in row {1000 + i * 100}",
                stage=ProcessingStage.VALIDATE,
                timestamp=datetime.now() + timedelta(seconds=i),
                technical_details=f"UUID validation failed for row {1000 + i * 100}",
                context={
                    "row_number": 1000 + i * 100,
                    "error_type": "uuid_validation"
                }
            )
            orchestrator.add_processing_error(batch_id, error)
        
        # Get aggregated error summary
        error_summary = orchestrator.get_aggregated_error_summary(batch_id)
        
        # Should aggregate similar errors
        assert "uuid_validation" in error_summary
        assert error_summary["uuid_validation"]["count"] == 5
        assert error_summary["uuid_validation"]["affected_rows"] == [1000, 1100, 1200, 1300, 1400]
    
    def test_error_export_for_investigation(self, orchestrator):
        """Test error data export capability for technical investigation."""
        batch_id = uuid4()
        
        error = ProcessingError(
            message="Complex processing error",
            stage=ProcessingStage.CLASSIFY,
            timestamp=datetime.now(),
            technical_details="Detailed technical information for investigation",
            context={
                "database_query": "SELECT * FROM campaigns WHERE uuid IN (...)",
                "connection_pool_size": 10,
                "active_connections": 8,
                "query_timeout": 30,
                "memory_usage_mb": 245
            }
        )
        
        orchestrator.add_processing_error(batch_id, error)
        
        # Export error data for investigation
        exported_data = orchestrator.export_error_data(batch_id)
        
        assert "batch_id" in exported_data
        assert "export_timestamp" in exported_data
        assert "errors" in exported_data
        assert "system_context" in exported_data
        
        # Verify detailed context is preserved
        error_data = exported_data["errors"][0]
        assert error_data["context"]["database_query"] is not None
        assert error_data["context"]["memory_usage_mb"] == 245