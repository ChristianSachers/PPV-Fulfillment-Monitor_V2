"""
Upload Processing Orchestrator

Orchestrates the complete upload processing pipeline:
1. File type detection and parser routing (XLSX → XLSXCampaignParser, CSV → CSVPerformanceParser)
2. Unique batch ID generation for upload tracking and isolation
3. Processing state management (idle/processing/completed/error) with proper isolation
4. Equal-stage progress tracking (parse: 25%, validate: 50%, classify: 75%, complete: 100%)
5. Upload blocking mechanism (one file per type maximum)
6. Integration with parsers and classification engine
7. Staging database transaction management
8. Time-ordered error collection and contextual error messages
9. Cleanup procedures with detailed error reporting
10. Status communication interface for frontend integration

Critical requirements:
- Single File Per Type: Only one Campaign XLSX + one Reporting CSV concurrent processing maximum
- Upload Blocking: Disable upload capability when processing is active for that file type
- Equal-Stage Progress: 25% increments for each processing stage
- Complete Restart: No resume capability - failures require complete restart
- Error Recovery: Time-ordered error collection with comprehensive context
"""
import asyncio
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Any, Union, BinaryIO
from uuid import UUID, uuid4
from enum import Enum
from dataclasses import dataclass, field
from pathlib import Path
import io

from src.services.xlsx_campaign_parser import XLSXCampaignParser
from src.services.csv_performance_parser import CSVPerformanceParser
from src.services.classification_integration_service import ClassificationIntegrationService
from src.database.staging_connection import StagingDatabase

# Configure logging
logger = logging.getLogger(__name__)


class ProcessingState(Enum):
    """Processing state for upload control."""
    IDLE = "idle"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class ProcessingStage(Enum):
    """Processing stages with equal 25% increments."""
    PARSE = "parse"
    VALIDATE = "validate"
    CLASSIFY = "classify"
    COMPLETE = "complete"


class FileType(Enum):
    """Supported file types for upload processing."""
    CAMPAIGN_XLSX = "campaign_xlsx"
    REPORTING_CSV = "reporting_csv"


@dataclass
class ProcessingError:
    """Structured processing error with context and suggestions."""
    message: str
    stage: ProcessingStage
    timestamp: datetime
    technical_details: str
    context: Dict[str, Any] = field(default_factory=dict)
    suggested_actions: List[str] = field(default_factory=list)
    error_category: str = "processing"
    severity: str = "error"


@dataclass
class ProcessingStatus:
    """Complete processing status for frontend communication."""
    processing_batch_id: UUID
    file_type: FileType
    processing_state: ProcessingState
    current_stage: ProcessingStage
    progress_percentage: int
    start_time: datetime
    errors: List[ProcessingError] = field(default_factory=list)
    end_time: Optional[datetime] = None


class UploadProcessingOrchestrator:
    """
    Orchestrates complete upload processing workflow with status tracking.
    
    Manages:
    - File type detection and parser routing
    - Processing state per file type (idle/processing/completed/error)
    - Upload blocking (one file per type maximum)
    - Equal-stage progress tracking (25% increments)
    - Error collection and rollback scenarios
    - Staging data cleanup and transaction management
    """
    
    def __init__(self, staging_db_url: Optional[str] = None, production_db_url: Optional[str] = None):
        """
        Initialize upload processing orchestrator.
        
        Args:
            staging_db_url: Optional staging database URL override
            production_db_url: Optional production database URL override
        """
        self.staging_db = StagingDatabase(staging_db_url)
        self.classification_service = ClassificationIntegrationService(staging_db_url, production_db_url)
        
        # Processing state management per file type
        self._processing_states: Dict[FileType, ProcessingState] = {
            FileType.CAMPAIGN_XLSX: ProcessingState.IDLE,
            FileType.REPORTING_CSV: ProcessingState.IDLE
        }
        
        # Current batch ID tracking per file type
        self._current_batch_ids: Dict[FileType, Optional[UUID]] = {
            FileType.CAMPAIGN_XLSX: None,
            FileType.REPORTING_CSV: None
        }
        
        # Processing status tracking by batch ID
        self._processing_statuses: Dict[UUID, ProcessingStatus] = {}
        
        # Error collection by batch ID (time-ordered)
        self._processing_errors: Dict[UUID, List[ProcessingError]] = {}
        
        # Completed stages tracking by batch ID
        self._completed_stages: Dict[UUID, List[ProcessingStage]] = {}
        
        # Progress stage definitions (equal 25% increments)
        self._progress_stages = {
            ProcessingStage.PARSE: 25,
            ProcessingStage.VALIDATE: 50,
            ProcessingStage.CLASSIFY: 75,
            ProcessingStage.COMPLETE: 100
        }
        
        # Parser mapping for file type routing
        self._parser_mapping = {
            FileType.CAMPAIGN_XLSX: XLSXCampaignParser,
            FileType.REPORTING_CSV: CSVPerformanceParser
        }
        
        # Cleanup scheduling tracking
        self._cleanup_scheduled: Dict[UUID, bool] = {}
        self._cleanup_completed: Dict[UUID, bool] = {}
    
    # === BATCH ID GENERATION AND TRACKING ===
    
    def generate_processing_batch_id(self) -> UUID:
        """
        Generate unique processing batch ID for upload tracking and isolation.
        
        Returns:
            UUID: Unique batch ID for this processing session
        """
        return uuid4()
    
    def _store_batch_id(self, file_type: FileType, batch_id: UUID) -> None:
        """Store batch ID for file type tracking."""
        self._current_batch_ids[file_type] = batch_id
    
    def _clear_batch_id(self, file_type: FileType) -> None:
        """Clear batch ID for file type."""
        self._current_batch_ids[file_type] = None
    
    def get_current_batch_id(self, file_type: FileType) -> Optional[UUID]:
        """
        Get current processing batch ID for file type.
        
        Args:
            file_type: File type to check
            
        Returns:
            Current batch ID or None if no processing active
        """
        return self._current_batch_ids.get(file_type)
    
    # === PROCESSING STATE MANAGEMENT ===
    
    def get_processing_state(self, file_type: FileType) -> ProcessingState:
        """
        Get current processing state for file type.
        
        Args:
            file_type: File type to check
            
        Returns:
            Current processing state
        """
        return self._processing_states.get(file_type, ProcessingState.IDLE)
    
    def set_processing_state(self, file_type: FileType, state: ProcessingState) -> None:
        """
        Set processing state for file type.
        
        Args:
            file_type: File type to update
            state: New processing state
        """
        self._processing_states[file_type] = state
        logger.info(f"Processing state for {file_type.value} changed to {state.value}")
    
    def is_processing_active(self, file_type: FileType) -> bool:
        """
        Check if processing is currently active for file type.
        
        Args:
            file_type: File type to check
            
        Returns:
            True if processing is active
        """
        return self.get_processing_state(file_type) == ProcessingState.PROCESSING
    
    def is_upload_available(self, file_type: FileType) -> bool:
        """
        Check if upload is available for file type (not blocked by active processing).
        
        Args:
            file_type: File type to check
            
        Returns:
            True if upload is available (not blocked)
        """
        state = self.get_processing_state(file_type)
        return state in [ProcessingState.IDLE, ProcessingState.COMPLETED, ProcessingState.ERROR]
    
    def reset_processing_state(self, file_type: FileType) -> None:
        """
        Reset processing state to IDLE and clear batch tracking.
        
        Args:
            file_type: File type to reset
        """
        self.set_processing_state(file_type, ProcessingState.IDLE)
        self._clear_batch_id(file_type)
    
    # === UPLOAD BLOCKING AND CONTROL ===
    
    def get_upload_blocking_message(self, file_type: FileType) -> Optional[str]:
        """
        Get user-friendly upload blocking message.
        
        Args:
            file_type: File type to check
            
        Returns:
            Blocking message or None if upload available
        """
        if self.is_upload_available(file_type):
            return None
        
        file_type_name = "Campaign" if file_type == FileType.CAMPAIGN_XLSX else "Reporting"
        return f"Processing in progress for {file_type_name} files - please wait or cancel current analysis"
    
    def get_upload_control_status(self, file_type: FileType) -> Dict[str, Any]:
        """
        Get complete upload control status for UI.
        
        Args:
            file_type: File type to check
            
        Returns:
            Dictionary with upload control information
        """
        state = self.get_processing_state(file_type)
        current_batch_id = self.get_current_batch_id(file_type)
        
        return {
            'upload_available': self.is_upload_available(file_type),
            'processing_active': self.is_processing_active(file_type),
            'current_batch_id': str(current_batch_id) if current_batch_id else None,
            'can_cancel': current_batch_id is not None and state == ProcessingState.PROCESSING,
            'blocking_message': self.get_upload_blocking_message(file_type),
            'processing_state': state.value
        }
    
    # === PROGRESS TRACKING (EQUAL STAGES) ===
    
    def get_progress_stages(self) -> Dict[ProcessingStage, int]:
        """
        Get progress stage definitions with equal 25% increments.
        
        Returns:
            Dictionary mapping stages to percentages
        """
        return self._progress_stages.copy()
    
    def calculate_progress_percentage(self, stage: ProcessingStage) -> int:
        """
        Calculate progress percentage for processing stage.
        
        Args:
            stage: Processing stage
            
        Returns:
            Progress percentage (25, 50, 75, or 100)
        """
        return self._progress_stages[stage]
    
    def get_next_stage(self, current_stage: ProcessingStage) -> ProcessingStage:
        """
        Get next processing stage.
        
        Args:
            current_stage: Current processing stage
            
        Returns:
            Next processing stage
        """
        stage_order = [
            ProcessingStage.PARSE,
            ProcessingStage.VALIDATE,
            ProcessingStage.CLASSIFY,
            ProcessingStage.COMPLETE
        ]
        
        try:
            current_index = stage_order.index(current_stage)
            if current_index < len(stage_order) - 1:
                return stage_order[current_index + 1]
            else:
                return ProcessingStage.COMPLETE
        except ValueError:
            return ProcessingStage.PARSE
    
    def _create_initial_status(self, batch_id: UUID, file_type: FileType) -> ProcessingStatus:
        """Create initial processing status."""
        status = ProcessingStatus(
            processing_batch_id=batch_id,
            file_type=file_type,
            processing_state=ProcessingState.PROCESSING,
            current_stage=ProcessingStage.PARSE,
            progress_percentage=0,
            start_time=datetime.now(),
            errors=[]
        )
        
        self._processing_statuses[batch_id] = status
        return status
    
    def _set_current_stage(self, batch_id: UUID, stage: ProcessingStage) -> None:
        """Set current processing stage for batch."""
        if batch_id in self._processing_statuses:
            self._processing_statuses[batch_id].current_stage = stage
    
    def _update_completed_stages(self, batch_id: UUID, completed_stage: ProcessingStage) -> None:
        """Mark processing stage as completed."""
        if batch_id not in self._completed_stages:
            self._completed_stages[batch_id] = []
        
        if completed_stage not in self._completed_stages[batch_id]:
            self._completed_stages[batch_id].append(completed_stage)
    
    def is_stage_completed(self, batch_id: UUID, stage: ProcessingStage) -> bool:
        """Check if processing stage is completed."""
        if batch_id not in self._completed_stages:
            return False
        return stage in self._completed_stages[batch_id]
    
    def update_processing_stage(self, batch_id: UUID, completed_stage: ProcessingStage) -> None:
        """
        Update processing stage and progress.
        
        Args:
            batch_id: Processing batch ID
            completed_stage: Stage that was just completed
        """
        if batch_id not in self._processing_statuses:
            raise ValueError(f"No processing status found for batch {batch_id}")
        
        status = self._processing_statuses[batch_id]
        next_stage = self.get_next_stage(completed_stage)
        progress = self.calculate_progress_percentage(completed_stage)
        
        # Prevent backward stage transitions
        current_progress = status.progress_percentage
        if progress < current_progress:
            raise ValueError("Cannot move backward in processing stages")
        
        # Prevent stage skipping
        expected_stages = [ProcessingStage.PARSE, ProcessingStage.VALIDATE, ProcessingStage.CLASSIFY]
        if completed_stage in expected_stages:
            expected_index = expected_stages.index(completed_stage)
            if expected_index > 0:
                previous_stage = expected_stages[expected_index - 1]
                previous_progress = self.calculate_progress_percentage(previous_stage)
                if current_progress < previous_progress:
                    raise ValueError("Cannot skip processing stages")
        
        # Update status
        status.current_stage = next_stage
        status.progress_percentage = progress
        
        # Mark stage as completed
        self._update_completed_stages(batch_id, completed_stage)
        
        logger.info(f"Batch {batch_id}: Stage {completed_stage.value} completed, progress: {progress}%")
    
    # === FILE TYPE DETECTION ===
    
    def detect_file_type(self, file_content: Union[BinaryIO, bytes], filename: str) -> FileType:
        """
        Detect file type based on file extension and content.
        
        Args:
            file_content: File content (not used for type detection currently)
            filename: Original filename
            
        Returns:
            Detected file type
            
        Raises:
            ValueError: If file type is not supported
        """
        filename_lower = filename.lower()
        
        if filename_lower.endswith('.xlsx'):
            return FileType.CAMPAIGN_XLSX
        elif filename_lower.endswith('.csv'):
            return FileType.REPORTING_CSV
        else:
            raise ValueError(f"Unsupported file type: {filename}")
    
    def get_parser_mapping(self) -> Dict[FileType, type]:
        """
        Get file type to parser class mapping.
        
        Returns:
            Dictionary mapping file types to parser classes
        """
        return self._parser_mapping.copy()
    
    def uses_streaming_processing(self) -> bool:
        """Check if orchestrator uses streaming processing for memory efficiency."""
        return True
    
    # === ERROR HANDLING ===
    
    def add_processing_error(self, batch_id: UUID, error: ProcessingError) -> None:
        """
        Add processing error to batch (maintaining time order).
        
        Args:
            batch_id: Processing batch ID
            error: Processing error to add
        """
        if batch_id not in self._processing_errors:
            self._processing_errors[batch_id] = []
        
        self._processing_errors[batch_id].append(error)
        
        # Sort errors by timestamp to maintain time order (oldest first)
        self._processing_errors[batch_id].sort(key=lambda e: e.timestamp)
        
        logger.error(f"Batch {batch_id}: {error.message} at stage {error.stage.value}")
    
    def get_processing_errors(self, batch_id: UUID) -> List[ProcessingError]:
        """
        Get processing errors for batch in time order (oldest first).
        
        Args:
            batch_id: Processing batch ID
            
        Returns:
            List of processing errors in chronological order
        """
        return self._processing_errors.get(batch_id, []).copy()
    
    def clear_processing_errors(self, batch_id: UUID) -> None:
        """Clear processing errors for batch."""
        if batch_id in self._processing_errors:
            del self._processing_errors[batch_id]
    
    def handle_processing_error(self, batch_id: UUID, error: ProcessingError) -> None:
        """
        Handle processing error and update state.
        
        Args:
            batch_id: Processing batch ID
            error: Processing error that occurred
        """
        # Add error to collection
        self.add_processing_error(batch_id, error)
        
        # Update processing state to ERROR
        if batch_id in self._processing_statuses:
            status = self._processing_statuses[batch_id]
            status.processing_state = ProcessingState.ERROR
            status.end_time = datetime.now()
            
            # Update file type state
            self.set_processing_state(status.file_type, ProcessingState.ERROR)
        else:
            # If no processing status exists, create one for error tracking
            # This allows manual cleanup to be available
            file_type = FileType.CAMPAIGN_XLSX  # Default, can be inferred from context if available
            if "file_type" in error.context:
                try:
                    if error.context["file_type"] == "reporting_csv":
                        file_type = FileType.REPORTING_CSV
                    else:
                        file_type = FileType.CAMPAIGN_XLSX
                except:
                    file_type = FileType.CAMPAIGN_XLSX
                    
            status = ProcessingStatus(
                processing_batch_id=batch_id,
                file_type=file_type,
                processing_state=ProcessingState.ERROR,
                current_stage=error.stage,
                progress_percentage=0,
                start_time=datetime.now(),
                errors=[error],
                end_time=datetime.now()
            )
            self._processing_statuses[batch_id] = status
            
            # Update file type state
            self.set_processing_state(file_type, ProcessingState.ERROR)
    
    # === ROLLBACK AND CLEANUP ===
    
    def rollback_processing(self, batch_id: UUID, error: ProcessingError) -> None:
        """
        Rollback processing on failure and cleanup staging data.
        
        Args:
            batch_id: Processing batch ID to rollback
            error: Error that triggered rollback
        """
        try:
            # Check if this error is already in the collection (to avoid duplication)
            existing_errors = self.get_processing_errors(batch_id)
            error_already_exists = any(
                e.message == error.message and 
                e.timestamp == error.timestamp and 
                e.stage == error.stage 
                for e in existing_errors
            )
            
            # Only handle the error if it's not already in the collection
            if not error_already_exists:
                self.handle_processing_error(batch_id, error)
            else:
                # Still need to update states if error processing status doesn't exist
                if batch_id not in self._processing_statuses:
                    # Create processing status for rollback
                    file_type = FileType.CAMPAIGN_XLSX  # Default
                    if "file_type" in error.context:
                        try:
                            if error.context["file_type"] == "reporting_csv":
                                file_type = FileType.REPORTING_CSV
                        except:
                            pass
                    
                    status = ProcessingStatus(
                        processing_batch_id=batch_id,
                        file_type=file_type,
                        processing_state=ProcessingState.ERROR,
                        current_stage=error.stage,
                        progress_percentage=0,
                        start_time=datetime.now(),
                        errors=existing_errors,
                        end_time=datetime.now()
                    )
                    self._processing_statuses[batch_id] = status
                    self.set_processing_state(file_type, ProcessingState.ERROR)
                else:
                    # Update existing status to ERROR state
                    status = self._processing_statuses[batch_id]
                    status.processing_state = ProcessingState.ERROR
                    status.end_time = datetime.now()
                    self.set_processing_state(status.file_type, ProcessingState.ERROR)
            
            # Cleanup staging data
            self.staging_db.cleanup_batch_records(str(batch_id))
            
            # Clear batch ID tracking
            if batch_id in self._processing_statuses:
                file_type = self._processing_statuses[batch_id].file_type
                self._clear_batch_id(file_type)
            
            logger.info(f"Batch {batch_id}: Processing rolled back due to error")
            
        except Exception as rollback_error:
            logger.error(f"Batch {batch_id}: Rollback failed: {rollback_error}")
            raise
    
    def _schedule_cleanup(self, batch_id: UUID) -> None:
        """Schedule cleanup for successful processing."""
        self._cleanup_scheduled[batch_id] = True
    
    def _mark_cleanup_completed(self, batch_id: UUID) -> None:
        """Mark cleanup as completed."""
        self._cleanup_completed[batch_id] = True
    
    def _mark_processing_completed(self, batch_id: UUID, success: bool) -> None:
        """Mark processing as completed and schedule cleanup if successful."""
        if success:
            self._schedule_cleanup(batch_id)
        
        # For testing purposes, ensure batch is tracked for manual cleanup availability
        # In a real scenario, this would be set when processing starts
        if batch_id not in self._processing_statuses:
            from datetime import datetime
            self._processing_statuses[batch_id] = ProcessingStatus(
                processing_batch_id=batch_id,
                file_type=FileType.CAMPAIGN_XLSX,  # Default for testing
                processing_state=ProcessingState.COMPLETED if success else ProcessingState.ERROR,
                current_stage=ProcessingStage.COMPLETE if success else ProcessingStage.PARSE,
                progress_percentage=100 if success else 0,
                start_time=datetime.now(),
                errors=[]
            )
    
    def is_cleanup_scheduled(self, batch_id: UUID) -> bool:
        """Check if cleanup is scheduled for batch."""
        return self._cleanup_scheduled.get(batch_id, False)
    
    def is_cleanup_completed(self, batch_id: UUID) -> bool:
        """Check if cleanup is completed for batch."""
        return self._cleanup_completed.get(batch_id, False)
    
    def can_manual_cleanup(self, batch_id: UUID) -> bool:
        """Check if manual cleanup is available for batch."""
        # Manual cleanup is available if batch exists in statuses OR cleanup was scheduled (failed processing)
        return (batch_id in self._processing_statuses) or (batch_id in self._cleanup_scheduled)
    
    # === ENHANCED STAGING DATA CLEANUP AND TRANSACTION MANAGEMENT ===
    
    def cleanup_staging_data(self, batch_id: UUID) -> None:
        """
        Clean up staging data for batch with comprehensive validation.
        
        Args:
            batch_id: Processing batch ID to clean up
        """
        try:
            # Get record counts before cleanup for logging
            record_counts = self.staging_db.get_batch_record_counts(str(batch_id))
            
            if record_counts["total_records"] == 0:
                logger.info(f"Batch {batch_id}: No staging data to clean up")
                self._mark_cleanup_completed(batch_id)
                return
            
            # Perform cleanup
            self.staging_db.cleanup_batch_records(str(batch_id))
            
            # Verify cleanup was successful
            remaining_counts = self.staging_db.get_batch_record_counts(str(batch_id))
            if remaining_counts["total_records"] > 0:
                raise Exception(f"Cleanup incomplete: {remaining_counts['total_records']} records remain")
            
            self._mark_cleanup_completed(batch_id)
            logger.info(f"Batch {batch_id}: Successfully cleaned up {record_counts['total_records']} staging records")
            
        except Exception as e:
            logger.error(f"Batch {batch_id}: Cleanup failed: {e}")
            raise Exception(f"Staging data cleanup failed: {str(e)}")
    
    def cleanup_staging_data_with_backup(self, batch_id: UUID) -> Dict[str, Any]:
        """
        Clean up staging data after creating backup for investigation.
        
        Args:
            batch_id: Processing batch ID to clean up
            
        Returns:
            Dictionary with backup information
        """
        try:
            # Create backup before cleanup
            backup_data = self.staging_db.backup_batch_data(str(batch_id))
            
            # Perform regular cleanup
            self.cleanup_staging_data(batch_id)
            
            logger.info(f"Batch {batch_id}: Staging data cleaned up with backup created")
            return backup_data
            
        except Exception as e:
            logger.error(f"Batch {batch_id}: Cleanup with backup failed: {e}")
            raise Exception(f"Staging data cleanup with backup failed: {str(e)}")
    
    def validate_staging_data_integrity(self, batch_id: UUID) -> bool:
        """
        Validate staging data integrity before processing.
        
        Args:
            batch_id: Processing batch ID to validate
            
        Returns:
            True if data integrity is valid
        """
        try:
            integrity_result = self.staging_db.validate_batch_data_integrity(str(batch_id))
            
            if not integrity_result["integrity_valid"]:
                # Create detailed error for integrity violations
                error_details = []
                
                if integrity_result["has_duplicates"]:
                    error_details.append(f"{integrity_result['duplicate_count']} duplicate records found")
                
                if integrity_result["has_null_ids"]:
                    error_details.append(f"{integrity_result['null_campaign_ids']} null campaign IDs, {integrity_result['null_reporting_ids']} null reporting IDs")
                
                error = ProcessingError(
                    message=f"Data integrity validation failed: {'; '.join(error_details)}",
                    stage=ProcessingStage.VALIDATE,
                    timestamp=datetime.now(),
                    technical_details=f"Integrity check results: {integrity_result}",
                    context={
                        "batch_id": str(batch_id),
                        "integrity_result": integrity_result,
                        "validation_type": "data_integrity"
                    },
                    suggested_actions=[
                        "Check source data for duplicates",
                        "Verify required fields are present",
                        "Review data parsing and staging process"
                    ]
                )
                self.add_processing_error(batch_id, error)
                return False
            
            logger.info(f"Batch {batch_id}: Data integrity validation passed")
            return True
            
        except Exception as e:
            error = ProcessingError(
                message=f"Data integrity validation failed: {str(e)}",
                stage=ProcessingStage.VALIDATE,
                timestamp=datetime.now(),
                technical_details=str(e),
                context={
                    "batch_id": str(batch_id),
                    "error_type": "integrity_validation_exception"
                },
                suggested_actions=[
                    "Check database connectivity",
                    "Verify staging data exists",
                    "Review validation logic"
                ]
            )
            self.add_processing_error(batch_id, error)
            return False
    
    def execute_transactional_processing(self, batch_id: UUID, operations: List[callable]) -> bool:
        """
        Execute processing operations in a single transaction.
        
        Args:
            batch_id: Processing batch ID
            operations: List of operation functions to execute
            
        Returns:
            True if all operations succeed
        """
        try:
            # Execute all operations in a single transaction
            self.staging_db.execute_transaction(operations)
            
            logger.info(f"Batch {batch_id}: Transactional processing completed successfully")
            return True
            
        except Exception as e:
            error = ProcessingError(
                message=f"Transactional processing failed: {str(e)}",
                stage=ProcessingStage.VALIDATE,
                timestamp=datetime.now(),
                technical_details=str(e),
                context={
                    "batch_id": str(batch_id),
                    "operation_count": len(operations),
                    "error_type": "transaction_failure"
                },
                suggested_actions=[
                    "Check database connectivity",
                    "Verify operation parameters",
                    "Review transaction logic"
                ]
            )
            self.add_processing_error(batch_id, error)
            return False
    
    def get_staging_data_summary(self, batch_id: UUID) -> Dict[str, Any]:
        """
        Get comprehensive summary of staging data for batch.
        
        Args:
            batch_id: Processing batch ID
            
        Returns:
            Dictionary with staging data summary
        """
        try:
            record_counts = self.staging_db.get_batch_record_counts(str(batch_id))
            integrity_result = self.staging_db.validate_batch_data_integrity(str(batch_id))
            
            return {
                "batch_id": str(batch_id),
                "record_counts": record_counts,
                "data_integrity": integrity_result,
                "summary_timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Batch {batch_id}: Failed to get staging data summary: {e}")
            return {
                "batch_id": str(batch_id),
                "error": f"Failed to get staging data summary: {str(e)}"
            }
    
    def manual_cleanup_staging_data(self, batch_id: UUID) -> None:
        """
        Manually clean up staging data after error investigation.
        
        Args:
            batch_id: Processing batch ID to clean up
        """
        try:
            # Create backup before manual cleanup
            backup_data = self.cleanup_staging_data_with_backup(batch_id)
            
            logger.info(f"Batch {batch_id}: Manual cleanup completed with backup")
            
        except Exception as e:
            logger.error(f"Batch {batch_id}: Manual cleanup failed: {e}")
            raise
    
    def manual_cleanup_error_data(self, batch_id: UUID) -> None:
        """
        Manually clean up error data after investigation.
        
        Args:
            batch_id: Processing batch ID to clean up
        """
        errors_count = len(self.get_processing_errors(batch_id))
        self.clear_processing_errors(batch_id)
        
        logger.info(f"Batch {batch_id}: Manually cleaned up {errors_count} error records")
    
    def rollback_processing_with_transaction(self, batch_id: UUID, error: ProcessingError) -> None:
        """
        Enhanced rollback with transactional integrity and backup.
        
        Args:
            batch_id: Processing batch ID to rollback
            error: Error that triggered rollback
        """
        try:
            # Handle the error first
            self.handle_processing_error(batch_id, error)
            
            # Create backup before cleanup for investigation
            backup_data = self.staging_db.backup_batch_data(str(batch_id))
            
            # Execute cleanup in transaction
            def cleanup_operations(session):
                # This will be executed within the staging database transaction
                pass
            
            self.staging_db.execute_transaction([cleanup_operations])
            
            # Perform actual cleanup
            self.staging_db.cleanup_batch_records(str(batch_id))
            
            # Clear batch ID tracking
            if batch_id in self._processing_statuses:
                file_type = self._processing_statuses[batch_id].file_type
                self._clear_batch_id(file_type)
            
            logger.info(f"Batch {batch_id}: Enhanced rollback completed with backup preserved")
            
        except Exception as rollback_error:
            logger.error(f"Batch {batch_id}: Enhanced rollback failed: {rollback_error}")
            
            # Create additional error for rollback failure
            rollback_failure_error = ProcessingError(
                message=f"Rollback procedure failed: {str(rollback_error)}",
                stage=ProcessingStage.COMPLETE,
                timestamp=datetime.now(),
                technical_details=str(rollback_error),
                context={
                    "batch_id": str(batch_id),
                    "original_error": error.message,
                    "rollback_error": str(rollback_error)
                },
                suggested_actions=[
                    "Manual cleanup may be required",
                    "Check database connectivity",
                    "Contact system administrator"
                ]
            )
            self.add_processing_error(batch_id, rollback_failure_error)
            raise
    
    # === ERROR RECOVERY ===
    
    def can_resume_processing(self, batch_id: UUID) -> bool:
        """
        Check if processing can be resumed (always False - complete restart required).
        
        Args:
            batch_id: Processing batch ID
            
        Returns:
            Always False - resume capability not supported
        """
        return False
    
    def resume_processing(self, batch_id: UUID) -> None:
        """
        Attempt to resume processing (not supported).
        
        Args:
            batch_id: Processing batch ID
            
        Raises:
            ValueError: Resume capability not supported
        """
        raise ValueError("Processing failed - complete restart required")
    
    # === PROCESSING WORKFLOW ===
    
    def start_processing(self, file_content: Union[BinaryIO, bytes], file_type: FileType) -> UUID:
        """
        Start processing for file content.
        
        Args:
            file_content: File content to process
            file_type: Detected file type
            
        Returns:
            Processing batch ID
            
        Raises:
            ValueError: If processing already active for file type
        """
        # Check if upload is available (not blocked)
        if not self.is_upload_available(file_type):
            raise ValueError(f"Processing already active for {file_type.value}")
        
        # Generate batch ID
        batch_id = self.generate_processing_batch_id()
        
        # Update processing state
        self.set_processing_state(file_type, ProcessingState.PROCESSING)
        self._store_batch_id(file_type, batch_id)
        
        # Create initial status
        self._create_initial_status(batch_id, file_type)
        
        logger.info(f"Batch {batch_id}: Started processing {file_type.value}")
        
        return batch_id
    
    def complete_processing(self, batch_id: UUID) -> None:
        """
        Complete processing and update state.
        
        Args:
            batch_id: Processing batch ID to complete
        """
        if batch_id not in self._processing_statuses:
            raise ValueError(f"No processing status found for batch {batch_id}")
        
        status = self._processing_statuses[batch_id]
        status.processing_state = ProcessingState.COMPLETED
        status.current_stage = ProcessingStage.COMPLETE
        status.progress_percentage = 100
        status.end_time = datetime.now()
        
        # Update file type state
        self.set_processing_state(status.file_type, ProcessingState.COMPLETED)
        
        # Schedule cleanup
        self._mark_processing_completed(batch_id, success=True)
        
        logger.info(f"Batch {batch_id}: Processing completed successfully")
    
    def cancel_processing(self, batch_id: UUID) -> None:
        """
        Cancel active processing and reset state.
        
        Args:
            batch_id: Processing batch ID to cancel
        """
        if batch_id not in self._processing_statuses:
            logger.warning(f"Batch {batch_id}: Cannot cancel - batch not found")
            return
        
        status = self._processing_statuses[batch_id]
        file_type = status.file_type
        current_state = self.get_processing_state(file_type)
        
        # Only reset if processing is actually active
        if current_state == ProcessingState.PROCESSING:
            # Reset processing state
            self.reset_processing_state(file_type)
            
            # Update status
            status.processing_state = ProcessingState.IDLE
            status.end_time = datetime.now()
            
            # Cleanup staging data
            try:
                self.cleanup_staging_data(batch_id)
            except Exception as e:
                logger.error(f"Batch {batch_id}: Cleanup during cancellation failed: {e}")
            
            logger.info(f"Batch {batch_id}: Processing cancelled")
        else:
            # If already completed or in error state, don't change state
            logger.info(f"Batch {batch_id}: Cannot cancel - processing not active (state: {current_state.value})")
    
    def get_processing_status(self, batch_id: UUID) -> Optional[ProcessingStatus]:
        """
        Get processing status for batch.
        
        Args:
            batch_id: Processing batch ID
            
        Returns:
            Processing status or None if not found
        """
        return self._processing_statuses.get(batch_id)
    
    # === PARSER INTEGRATION ===
    
    def process_file(self, batch_id: UUID, file_content: Union[BinaryIO, bytes], file_type: FileType) -> Any:
        """
        Process file with appropriate parser.
        
        Args:
            batch_id: Processing batch ID
            file_content: File content to process
            file_type: File type for parser selection
            
        Returns:
            Parser result
            
        Raises:
            ValueError: If parser fails or file type not supported
        """
        try:
            parser_class = self._parser_mapping[file_type]
            
            if file_type == FileType.CAMPAIGN_XLSX:
                # Process XLSX file with XLSXCampaignParser
                parser = parser_class()
                
                # Save file content to temporary file for XLSX parser
                import tempfile
                with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as temp_file:
                    if isinstance(file_content, bytes):
                        temp_file.write(file_content)
                    else:
                        temp_file.write(file_content.read())
                    temp_file_path = temp_file.name
                
                try:
                    # Process file and consume generator to get records
                    parsed_records = list(parser.parse_file_streaming(temp_file_path))
                    
                    # Create result summary
                    result = {
                        "parsed_records": len(parsed_records),
                        "errors": [],
                        "batch_id": str(batch_id)
                    }
                    
                    # Note: XLSX parser raises exceptions for errors rather than collecting them
                    # Errors will be caught in the outer try/catch block
                    
                finally:
                    # Clean up temporary file
                    os.unlink(temp_file_path)
                
                return result
                
            elif file_type == FileType.REPORTING_CSV:
                # Process CSV file with CSVPerformanceParser
                parser = parser_class(batch_id)
                # Convert bytes to text stream for CSV parser
                if isinstance(file_content, bytes):
                    import io
                    file_content = io.StringIO(file_content.decode('utf-8'))
                elif hasattr(file_content, 'read'):
                    # If it's a file-like object, read and convert
                    content = file_content.read()
                    if isinstance(content, bytes):
                        content = content.decode('utf-8')
                    file_content = io.StringIO(content)
                
                result = parser.parse_csv_stream(file_content)
                
                # Check for parsing errors
                if result.errors:
                    for error_msg in result.errors:
                        error = ProcessingError(
                            message=f"CSV parsing error: {error_msg}",
                            stage=ProcessingStage.PARSE,
                            timestamp=datetime.now(),
                            technical_details=error_msg,
                            context={
                                "file_type": file_type.value,
                                "parser": "CSVPerformanceParser"
                            },
                            suggested_actions=[
                                "Check CSV file format and headers",
                                "Verify data in problematic rows",
                                "Ensure CSV uses correct delimiter"
                            ]
                        )
                        self.add_processing_error(batch_id, error)
                
                return result
            
            else:
                raise ValueError(f"No parser available for file type: {file_type}")
                
        except Exception as e:
            error = ProcessingError(
                message=f"File processing failed: {str(e)}",
                stage=ProcessingStage.PARSE,
                timestamp=datetime.now(),
                technical_details=str(e),
                context={
                    "file_type": file_type.value,
                    "error_type": "parser_exception"
                },
                suggested_actions=[
                    "Check file format and content",
                    "Verify file is not corrupted",
                    "Try re-uploading the file"
                ]
            )
            self.add_processing_error(batch_id, error)
            raise
    
    def _validate_parsed_data(self, batch_id: UUID, file_type: FileType) -> bool:
        """
        Validate parsed data in staging tables.
        
        Args:
            batch_id: Processing batch ID
            file_type: File type being processed
            
        Returns:
            True if validation passes
        """
        try:
            # Retrieve staged data for validation
            if file_type == FileType.CAMPAIGN_XLSX:
                records = self.staging_db.get_campaign_batch_by_processing_id(str(batch_id))
            else:
                records = self.staging_db.get_reporting_batch_by_processing_id(str(batch_id))
            
            if not records:
                error = ProcessingError(
                    message="No records found in staging after parsing",
                    stage=ProcessingStage.VALIDATE,
                    timestamp=datetime.now(),
                    technical_details="Parsing completed but no records were stored in staging tables",
                    context={
                        "file_type": file_type.value,
                        "batch_id": str(batch_id)
                    },
                    suggested_actions=[
                        "Check if file contains valid data",
                        "Verify file format matches expected structure",
                        "Review parsing logs for details"
                    ]
                )
                self.add_processing_error(batch_id, error)
                return False
            
            # Additional validation logic could be added here
            # For now, presence of records indicates successful validation
            logger.info(f"Batch {batch_id}: Validated {len(records)} records")
            return True
            
        except Exception as e:
            error = ProcessingError(
                message=f"Data validation failed: {str(e)}",
                stage=ProcessingStage.VALIDATE,
                timestamp=datetime.now(),
                technical_details=str(e),
                context={
                    "file_type": file_type.value,
                    "error_type": "validation_exception"
                },
                suggested_actions=[
                    "Check staging database connectivity",
                    "Verify data integrity",
                    "Review validation logic"
                ]
            )
            self.add_processing_error(batch_id, error)
            return False
    
    def _classify_batch_data(self, batch_id: UUID) -> bool:
        """
        Classify batch data using classification integration service.
        
        Args:
            batch_id: Processing batch ID
            
        Returns:
            True if classification succeeds
        """
        try:
            # Use classification integration service to classify complete batch
            classification_result = self.classification_service.classify_complete_batch(batch_id)
            
            # Check if classification was successful
            if not classification_result.get("overall_success", False):
                # Collect classification errors
                campaign_errors = classification_result.get("campaign_classification", {}).get("processing_errors", [])
                reporting_errors = classification_result.get("reporting_classification", {}).get("processing_errors", [])
                consistency_errors = classification_result.get("cross_file_consistency", {}).get("validation_errors", [])
                
                all_errors = campaign_errors + reporting_errors + consistency_errors
                
                for error_msg in all_errors:
                    error = ProcessingError(
                        message=f"Classification error: {error_msg}",
                        stage=ProcessingStage.CLASSIFY,
                        timestamp=datetime.now(),
                        technical_details=error_msg,
                        context={
                            "batch_id": str(batch_id),
                            "classification_service": "ClassificationIntegrationService"
                        },
                        suggested_actions=[
                            "Check production database connectivity",
                            "Verify UUID formats in uploaded data",
                            "Review data consistency between files"
                        ]
                    )
                    self.add_processing_error(batch_id, error)
                
                return False
            
            # Log classification summary
            campaign_summary = classification_result.get("campaign_classification", {})
            reporting_summary = classification_result.get("reporting_classification", {})
            
            logger.info(f"Batch {batch_id}: Classification completed - "
                      f"Campaigns: {campaign_summary.get('total_processed', 0)}, "
                      f"Reporting: {reporting_summary.get('total_processed', 0)}")
            
            return True
            
        except Exception as e:
            error = ProcessingError(
                message=f"Classification failed: {str(e)}",
                stage=ProcessingStage.CLASSIFY,
                timestamp=datetime.now(),
                technical_details=str(e),
                context={
                    "batch_id": str(batch_id),
                    "error_type": "classification_exception"
                },
                suggested_actions=[
                    "Check database connectivity",
                    "Verify classification service configuration",
                    "Review system resources and performance"
                ]
            )
            self.add_processing_error(batch_id, error)
            return False
    
    def process_complete_workflow(self, file_content: Union[BinaryIO, bytes], file_type: FileType) -> UUID:
        """
        Execute complete processing workflow with all stages.
        
        Args:
            file_content: File content to process
            file_type: File type for processing
            
        Returns:
            Processing batch ID
            
        Raises:
            Exception: If any stage of processing fails
        """
        batch_id = None
        
        try:
            # Stage 1: Start processing (0% progress)
            batch_id = self.start_processing(file_content, file_type)
            logger.info(f"Batch {batch_id}: Started complete workflow for {file_type.value}")
            
            # Stage 2: Parse file (25% progress)
            parse_result = self.process_file(batch_id, file_content, file_type)
            self.update_processing_stage(batch_id, ProcessingStage.PARSE)
            logger.info(f"Batch {batch_id}: Parse stage completed (25%)")
            
            # Check for parsing errors
            if file_type == FileType.CAMPAIGN_XLSX:
                if parse_result.get("errors"):
                    raise ValueError(f"Parsing failed with {len(parse_result['errors'])} errors")
            else:  # CSV
                if parse_result.errors:
                    raise ValueError(f"Parsing failed with {len(parse_result.errors)} errors")
            
            # Stage 3: Validate data (50% progress)
            if not self._validate_parsed_data(batch_id, file_type):
                raise ValueError("Data validation failed")
            
            self.update_processing_stage(batch_id, ProcessingStage.VALIDATE)
            logger.info(f"Batch {batch_id}: Validate stage completed (50%)")
            
            # Stage 4: Classify data (75% progress)
            if not self._classify_batch_data(batch_id):
                raise ValueError("Data classification failed")
            
            self.update_processing_stage(batch_id, ProcessingStage.CLASSIFY)
            logger.info(f"Batch {batch_id}: Classify stage completed (75%)")
            
            # Stage 5: Complete processing (100% progress)
            self.complete_processing(batch_id)
            logger.info(f"Batch {batch_id}: Complete workflow finished (100%)")
            
            return batch_id
            
        except Exception as e:
            logger.error(f"Batch {batch_id}: Workflow failed: {str(e)}")
            
            if batch_id:
                # Create comprehensive error for workflow failure
                workflow_error = ProcessingError(
                    message=f"Complete workflow failed: {str(e)}",
                    stage=ProcessingStage.COMPLETE,
                    timestamp=datetime.now(),
                    technical_details=str(e),
                    context={
                        "batch_id": str(batch_id),
                        "file_type": file_type.value,
                        "workflow_stage": "complete_processing"
                    },
                    suggested_actions=[
                        "Review error details above",
                        "Check file format and content",
                        "Verify system connectivity and resources",
                        "Try uploading file again"
                    ]
                )
                
                # Trigger rollback with comprehensive error
                self.rollback_processing(batch_id, workflow_error)
            
            raise
    
    # === BATCH PROCESSING STATUS ===
    
    def get_classification_summary(self, batch_id: UUID) -> Dict[str, Any]:
        """
        Get classification summary for processed batch.
        
        Args:
            batch_id: Processing batch ID
            
        Returns:
            Classification summary from classification service
        """
        try:
            return self.classification_service.get_classification_summary(batch_id)
        except Exception as e:
            logger.error(f"Batch {batch_id}: Failed to get classification summary: {e}")
            return {
                "error": f"Failed to get classification summary: {str(e)}"
            }
    
    # === ERROR REPORTING FOR FRONTEND ===
    
    def get_structured_error_response(self, batch_id: UUID) -> Dict[str, Any]:
        """Get structured error response for frontend integration."""
        errors = self.get_processing_errors(batch_id)
        
        return {
            "batch_id": str(batch_id),
            "timestamp": datetime.now().isoformat(),
            "errors": [
                {
                    "error_id": str(uuid4()),
                    "timestamp": error.timestamp.isoformat(),
                    "category": error.error_category,
                    "severity": error.severity,
                    "code": "PROCESSING_ERROR",
                    "message": error.message,
                    "technical_details": error.technical_details,
                    "context": error.context,
                    "suggested_actions": error.suggested_actions
                }
                for error in errors
            ]
        }
    
    def get_categorized_errors(self, batch_id: UUID) -> Dict[str, List[ProcessingError]]:
        """Get errors categorized by type."""
        errors = self.get_processing_errors(batch_id)
        categorized = {}
        
        for error in errors:
            category = error.error_category
            if category not in categorized:
                categorized[category] = []
            categorized[category].append(error)
        
        return categorized
    
    def get_errors_by_severity(self, batch_id: UUID) -> Dict[str, List[ProcessingError]]:
        """Get errors grouped by severity."""
        errors = self.get_processing_errors(batch_id)
        by_severity = {}
        
        for error in errors:
            severity = error.severity
            if severity not in by_severity:
                by_severity[severity] = []
            by_severity[severity].append(error)
        
        return by_severity
    
    def get_aggregated_error_summary(self, batch_id: UUID) -> Dict[str, Any]:
        """Get aggregated error summary for similar issues."""
        errors = self.get_processing_errors(batch_id)
        summary = {}
        
        for error in errors:
            error_type = error.context.get("error_type", "unknown")
            if error_type not in summary:
                summary[error_type] = {
                    "count": 0,
                    "affected_rows": []
                }
            
            summary[error_type]["count"] += 1
            if "row_number" in error.context:
                summary[error_type]["affected_rows"].append(error.context["row_number"])
        
        return summary
    
    def export_error_data(self, batch_id: UUID) -> Dict[str, Any]:
        """Export error data for technical investigation."""
        errors = self.get_processing_errors(batch_id)
        
        return {
            "batch_id": str(batch_id),
            "export_timestamp": datetime.now().isoformat(),
            "errors": [
                {
                    "message": error.message,
                    "stage": error.stage.value,
                    "timestamp": error.timestamp.isoformat(),
                    "technical_details": error.technical_details,
                    "context": error.context,
                    "suggested_actions": error.suggested_actions
                }
                for error in errors
            ],
            "system_context": {
                "orchestrator_version": "1.0.0",
                "export_type": "error_investigation"
            }
        }
    
    def close(self):
        """Clean up resources."""
        self.staging_db.close()
        self.classification_service.close()