"""
Unit tests for Equal-Stage Progress Tracking

Critical requirement testing for Phase 1.1:
- Parse Stage: 25% (after file parsing completes)
- Validate Stage: 50% (after data validation completes)  
- Classify Stage: 75% (after classification completes)
- Complete Stage: 100% (after full processing completes)

Tests progress tracking accuracy, consistency, and frontend integration.
"""
import pytest
from datetime import datetime, timedelta
from uuid import UUID, uuid4
from unittest.mock import Mock, patch, MagicMock
from decimal import Decimal

from src.services.upload_processing_orchestrator import (
    UploadProcessingOrchestrator,
    ProcessingStage,
    ProcessingStatus,
    ProcessingState,
    FileType
)


class TestEqualStageProgressDefinition:
    """Test that equal-stage progress is defined correctly."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for testing."""
        return UploadProcessingOrchestrator()
    
    def test_progress_stages_exact_percentages(self, orchestrator):
        """Test that progress stages have exact 25% increments."""
        stages = orchestrator.get_progress_stages()
        
        # Critical requirement: equal 25% increments
        assert stages[ProcessingStage.PARSE] == 25
        assert stages[ProcessingStage.VALIDATE] == 50
        assert stages[ProcessingStage.CLASSIFY] == 75
        assert stages[ProcessingStage.COMPLETE] == 100
    
    def test_progress_stage_completeness(self, orchestrator):
        """Test that all required processing stages are defined."""
        stages = orchestrator.get_progress_stages()
        
        required_stages = [
            ProcessingStage.PARSE,
            ProcessingStage.VALIDATE,
            ProcessingStage.CLASSIFY,
            ProcessingStage.COMPLETE
        ]
        
        for stage in required_stages:
            assert stage in stages
            assert isinstance(stages[stage], int)
            assert 0 < stages[stage] <= 100
    
    def test_progress_stage_ordering(self, orchestrator):
        """Test that progress stages are in ascending order."""
        stages = orchestrator.get_progress_stages()
        
        stage_values = [
            stages[ProcessingStage.PARSE],
            stages[ProcessingStage.VALIDATE], 
            stages[ProcessingStage.CLASSIFY],
            stages[ProcessingStage.COMPLETE]
        ]
        
        # Values should be in ascending order
        assert stage_values == sorted(stage_values)
        
        # Should be exactly [25, 50, 75, 100]
        assert stage_values == [25, 50, 75, 100]
    
    def test_progress_stage_immutability(self, orchestrator):
        """Test that progress stage definitions are immutable."""
        stages_1 = orchestrator.get_progress_stages()
        stages_2 = orchestrator.get_progress_stages()
        
        # Should return same values on multiple calls
        assert stages_1 == stages_2
        
        # Modifying returned dict should not affect internal state
        stages_1[ProcessingStage.PARSE] = 30
        stages_3 = orchestrator.get_progress_stages()
        
        assert stages_3[ProcessingStage.PARSE] == 25  # Original value preserved


class TestProgressCalculationAccuracy:
    """Test progress calculation accuracy for each stage."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for testing.""" 
        return UploadProcessingOrchestrator()
    
    def test_parse_stage_progress_calculation(self, orchestrator):
        """Test progress calculation for parse stage (25%)."""
        progress = orchestrator.calculate_progress_percentage(ProcessingStage.PARSE)
        
        assert progress == 25
        assert isinstance(progress, int)
    
    def test_validate_stage_progress_calculation(self, orchestrator):
        """Test progress calculation for validate stage (50%)."""
        progress = orchestrator.calculate_progress_percentage(ProcessingStage.VALIDATE)
        
        assert progress == 50
        assert isinstance(progress, int)
    
    def test_classify_stage_progress_calculation(self, orchestrator):
        """Test progress calculation for classify stage (75%).""" 
        progress = orchestrator.calculate_progress_percentage(ProcessingStage.CLASSIFY)
        
        assert progress == 75
        assert isinstance(progress, int)
    
    def test_complete_stage_progress_calculation(self, orchestrator):
        """Test progress calculation for complete stage (100%)."""
        progress = orchestrator.calculate_progress_percentage(ProcessingStage.COMPLETE)
        
        assert progress == 100
        assert isinstance(progress, int)
    
    def test_progress_calculation_consistency(self, orchestrator):
        """Test that progress calculations are consistent across calls."""
        # Multiple calls should return same results
        for _ in range(10):
            assert orchestrator.calculate_progress_percentage(ProcessingStage.PARSE) == 25
            assert orchestrator.calculate_progress_percentage(ProcessingStage.VALIDATE) == 50
            assert orchestrator.calculate_progress_percentage(ProcessingStage.CLASSIFY) == 75
            assert orchestrator.calculate_progress_percentage(ProcessingStage.COMPLETE) == 100
    
    def test_progress_no_fractional_percentages(self, orchestrator):
        """Test that progress percentages are always integers (no fractions)."""
        stages = [
            ProcessingStage.PARSE,
            ProcessingStage.VALIDATE,
            ProcessingStage.CLASSIFY,
            ProcessingStage.COMPLETE
        ]
        
        for stage in stages:
            progress = orchestrator.calculate_progress_percentage(stage)
            assert isinstance(progress, int)
            assert progress == int(progress)  # No fractional part


class TestProgressTrackingThroughWorkflow:
    """Test progress tracking throughout complete processing workflow."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for testing."""
        return UploadProcessingOrchestrator()
    
    @pytest.fixture
    def batch_id(self):
        """Create batch ID for testing."""
        return uuid4()
    
    def test_initial_progress_is_zero(self, orchestrator, batch_id):
        """Test that initial progress is 0% before processing starts."""
        # Create initial status
        status = orchestrator._create_initial_status(batch_id, FileType.CAMPAIGN_XLSX)
        
        assert status.progress_percentage == 0
        assert status.current_stage == ProcessingStage.PARSE
    
    def test_progress_after_parse_completion(self, orchestrator, batch_id):
        """Test progress is 25% after parse stage completion."""
        # Initialize processing
        orchestrator._create_initial_status(batch_id, FileType.CAMPAIGN_XLSX)
        
        # Complete parse stage
        orchestrator.update_processing_stage(batch_id, ProcessingStage.PARSE)
        
        status = orchestrator.get_processing_status(batch_id)
        assert status.progress_percentage == 25
        assert status.current_stage == ProcessingStage.VALIDATE
    
    def test_progress_after_validate_completion(self, orchestrator, batch_id):
        """Test progress is 50% after validate stage completion."""
        # Initialize and complete parse
        orchestrator._create_initial_status(batch_id, FileType.CAMPAIGN_XLSX)
        orchestrator.update_processing_stage(batch_id, ProcessingStage.PARSE)
        
        # Complete validate stage
        orchestrator.update_processing_stage(batch_id, ProcessingStage.VALIDATE)
        
        status = orchestrator.get_processing_status(batch_id)
        assert status.progress_percentage == 50
        assert status.current_stage == ProcessingStage.CLASSIFY
    
    def test_progress_after_classify_completion(self, orchestrator, batch_id):
        """Test progress is 75% after classify stage completion."""
        # Initialize and complete parse, validate
        orchestrator._create_initial_status(batch_id, FileType.CAMPAIGN_XLSX)
        orchestrator.update_processing_stage(batch_id, ProcessingStage.PARSE)
        orchestrator.update_processing_stage(batch_id, ProcessingStage.VALIDATE)
        
        # Complete classify stage
        orchestrator.update_processing_stage(batch_id, ProcessingStage.CLASSIFY)
        
        status = orchestrator.get_processing_status(batch_id)
        assert status.progress_percentage == 75
        assert status.current_stage == ProcessingStage.COMPLETE
    
    def test_progress_after_complete_processing(self, orchestrator, batch_id):
        """Test progress is 100% after complete processing."""
        # Initialize and complete all stages
        orchestrator._create_initial_status(batch_id, FileType.CAMPAIGN_XLSX)
        orchestrator.update_processing_stage(batch_id, ProcessingStage.PARSE)
        orchestrator.update_processing_stage(batch_id, ProcessingStage.VALIDATE)
        orchestrator.update_processing_stage(batch_id, ProcessingStage.CLASSIFY)
        
        # Complete processing
        orchestrator.complete_processing(batch_id)
        
        status = orchestrator.get_processing_status(batch_id)
        assert status.progress_percentage == 100
        assert status.current_stage == ProcessingStage.COMPLETE
    
    def test_progress_monotonic_increase(self, orchestrator, batch_id):
        """Test that progress only increases monotonically (never decreases)."""
        orchestrator._create_initial_status(batch_id, FileType.CAMPAIGN_XLSX)
        
        progress_values = []
        
        # Track progress through all stages
        progress_values.append(orchestrator.get_processing_status(batch_id).progress_percentage)
        
        orchestrator.update_processing_stage(batch_id, ProcessingStage.PARSE)
        progress_values.append(orchestrator.get_processing_status(batch_id).progress_percentage)
        
        orchestrator.update_processing_stage(batch_id, ProcessingStage.VALIDATE)
        progress_values.append(orchestrator.get_processing_status(batch_id).progress_percentage)
        
        orchestrator.update_processing_stage(batch_id, ProcessingStage.CLASSIFY)
        progress_values.append(orchestrator.get_processing_status(batch_id).progress_percentage)
        
        orchestrator.complete_processing(batch_id)
        progress_values.append(orchestrator.get_processing_status(batch_id).progress_percentage)
        
        # Progress should be monotonic: [0, 25, 50, 75, 100]
        assert progress_values == [0, 25, 50, 75, 100]
        assert progress_values == sorted(progress_values)


class TestProgressPersistenceAndConsistency:
    """Test progress tracking persistence and consistency."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for testing."""
        return UploadProcessingOrchestrator()
    
    @pytest.fixture
    def batch_id(self):
        """Create batch ID for testing."""
        return uuid4()
    
    def test_progress_persistence_across_status_checks(self, orchestrator, batch_id):
        """Test that progress persists across multiple status checks."""
        orchestrator._create_initial_status(batch_id, FileType.CAMPAIGN_XLSX)
        orchestrator.update_processing_stage(batch_id, ProcessingStage.PARSE)
        
        # Multiple status checks should return consistent progress
        status_checks = [
            orchestrator.get_processing_status(batch_id).progress_percentage
            for _ in range(5)
        ]
        
        # All checks should return 25%
        assert all(progress == 25 for progress in status_checks)
    
    def test_progress_isolation_between_batches(self, orchestrator):
        """Test that progress tracking is isolated between different batches."""
        batch_id_1 = uuid4()
        batch_id_2 = uuid4()
        
        # Initialize both batches
        orchestrator._create_initial_status(batch_id_1, FileType.CAMPAIGN_XLSX)
        orchestrator._create_initial_status(batch_id_2, FileType.REPORTING_CSV)
        
        # Advance first batch to validate stage (50%)
        orchestrator.update_processing_stage(batch_id_1, ProcessingStage.PARSE)
        orchestrator.update_processing_stage(batch_id_1, ProcessingStage.VALIDATE)
        
        # Second batch should still be at 0%
        status_1 = orchestrator.get_processing_status(batch_id_1)
        status_2 = orchestrator.get_processing_status(batch_id_2)
        
        assert status_1.progress_percentage == 50
        assert status_2.progress_percentage == 0
    
    def test_progress_consistency_during_concurrent_processing(self, orchestrator):
        """Test progress consistency during concurrent file type processing."""
        xlsx_batch_id = uuid4()
        csv_batch_id = uuid4()
        
        # Initialize concurrent processing
        orchestrator._create_initial_status(xlsx_batch_id, FileType.CAMPAIGN_XLSX)
        orchestrator._create_initial_status(csv_batch_id, FileType.REPORTING_CSV)
        
        # Advance both to different stages
        orchestrator.update_processing_stage(xlsx_batch_id, ProcessingStage.PARSE)  # 25%
        orchestrator.update_processing_stage(csv_batch_id, ProcessingStage.PARSE)
        orchestrator.update_processing_stage(csv_batch_id, ProcessingStage.VALIDATE)
        orchestrator.update_processing_stage(csv_batch_id, ProcessingStage.CLASSIFY)  # 75%
        
        # Check progress is independent
        xlsx_status = orchestrator.get_processing_status(xlsx_batch_id)
        csv_status = orchestrator.get_processing_status(csv_batch_id)
        
        assert xlsx_status.progress_percentage == 25
        assert csv_status.progress_percentage == 75
    
    def test_progress_state_after_processing_error(self, orchestrator, batch_id):
        """Test that progress state is preserved after processing error."""
        orchestrator._create_initial_status(batch_id, FileType.CAMPAIGN_XLSX)
        orchestrator.update_processing_stage(batch_id, ProcessingStage.PARSE)
        orchestrator.update_processing_stage(batch_id, ProcessingStage.VALIDATE)
        
        # Simulate error at classify stage
        from src.services.upload_processing_orchestrator import ProcessingError
        error = ProcessingError(
            message="Classification failed",
            stage=ProcessingStage.CLASSIFY,
            timestamp=datetime.now(),
            technical_details="Mock classification error"
        )
        
        orchestrator.handle_processing_error(batch_id, error)
        
        # Progress should be preserved at last successful stage (50%)
        status = orchestrator.get_processing_status(batch_id)
        assert status.progress_percentage == 50
        assert status.processing_state == ProcessingState.ERROR


class TestProgressTrackingForFrontendIntegration:
    """Test progress tracking specifically for frontend integration requirements."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for testing."""
        return UploadProcessingOrchestrator()
    
    def test_progress_status_response_format(self, orchestrator):
        """Test that progress status response matches frontend expectations."""
        batch_id = uuid4()
        orchestrator._create_initial_status(batch_id, FileType.CAMPAIGN_XLSX)
        
        status = orchestrator.get_processing_status(batch_id)
        
        # Required fields for frontend progress tracking
        assert hasattr(status, 'progress_percentage')
        assert hasattr(status, 'current_stage')
        assert hasattr(status, 'processing_state')
        
        # Data types should be frontend-friendly
        assert isinstance(status.progress_percentage, int)
        assert isinstance(status.current_stage, ProcessingStage)
        assert isinstance(status.processing_state, ProcessingState)
    
    def test_progress_percentage_range_validation(self, orchestrator):
        """Test that progress percentages are always in valid range (0-100)."""
        batch_id = uuid4()
        orchestrator._create_initial_status(batch_id, FileType.CAMPAIGN_XLSX)
        
        # Test all stages
        stages_to_test = [
            (ProcessingStage.PARSE, 0),      # Before completion
            (ProcessingStage.PARSE, 25),     # After completion
            (ProcessingStage.VALIDATE, 50),  # After completion
            (ProcessingStage.CLASSIFY, 75),  # After completion
            (ProcessingStage.COMPLETE, 100)  # After completion
        ]
        
        current_progress = 0
        for stage, expected_progress in stages_to_test:
            if expected_progress > current_progress:
                orchestrator.update_processing_stage(batch_id, stage)
                current_progress = expected_progress
            
            status = orchestrator.get_processing_status(batch_id)
            
            # Progress should be in valid range
            assert 0 <= status.progress_percentage <= 100
            assert status.progress_percentage == expected_progress
    
    def test_progress_serialization_for_json_response(self, orchestrator):
        """Test that progress status can be serialized for JSON API responses."""
        batch_id = uuid4()
        orchestrator._create_initial_status(batch_id, FileType.CAMPAIGN_XLSX)
        orchestrator.update_processing_stage(batch_id, ProcessingStage.PARSE)
        
        status = orchestrator.get_processing_status(batch_id)
        
        # Should be serializable to dict for JSON response
        status_dict = {
            'processing_batch_id': str(status.processing_batch_id),
            'file_type': status.file_type.value,
            'processing_state': status.processing_state.value,
            'current_stage': status.current_stage.value,
            'progress_percentage': status.progress_percentage,
            'start_time': status.start_time.isoformat()
        }
        
        # Verify serialization
        assert status_dict['progress_percentage'] == 25
        assert status_dict['current_stage'] == 'validate'
        assert isinstance(status_dict['progress_percentage'], int)
    
    def test_progress_polling_optimization(self, orchestrator):
        """Test that progress status checks are optimized for 2-second polling."""
        batch_id = uuid4()
        orchestrator._create_initial_status(batch_id, FileType.CAMPAIGN_XLSX)
        
        # Measure time for multiple status checks (simulating frontend polling)
        start_time = datetime.now()
        
        for _ in range(20):  # Simulate 40 seconds of 2-second polling
            status = orchestrator.get_processing_status(batch_id)
            assert status.progress_percentage is not None
        
        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()
        
        # 20 status checks should complete very quickly (under 0.5 seconds)
        assert total_time < 0.5
    
    def test_progress_stage_transition_notifications(self, orchestrator):
        """Test that progress stage transitions can be detected for frontend notifications."""
        batch_id = uuid4()
        orchestrator._create_initial_status(batch_id, FileType.CAMPAIGN_XLSX)
        
        # Track stage transitions
        previous_stage = ProcessingStage.PARSE
        previous_progress = 0
        
        stages_to_complete = [
            ProcessingStage.PARSE,
            ProcessingStage.VALIDATE,
            ProcessingStage.CLASSIFY
        ]
        
        for stage in stages_to_complete:
            orchestrator.update_processing_stage(batch_id, stage)
            status = orchestrator.get_processing_status(batch_id)
            
            # Should be able to detect stage transition
            stage_changed = status.current_stage != previous_stage
            progress_changed = status.progress_percentage != previous_progress
            
            # At least one should have changed
            assert stage_changed or progress_changed
            
            previous_stage = status.current_stage
            previous_progress = status.progress_percentage


class TestProgressTrackingEdgeCases:
    """Test edge cases in progress tracking."""
    
    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator for testing."""
        return UploadProcessingOrchestrator()
    
    def test_progress_with_invalid_batch_id(self, orchestrator):
        """Test progress tracking with invalid batch ID."""
        invalid_batch_id = uuid4()
        
        # Should handle invalid batch ID gracefully
        status = orchestrator.get_processing_status(invalid_batch_id)
        assert status is None or status.progress_percentage == 0
    
    def test_progress_stage_skip_prevention(self, orchestrator):
        """Test that progress stages cannot be skipped."""
        batch_id = uuid4()
        orchestrator._create_initial_status(batch_id, FileType.CAMPAIGN_XLSX)
        
        # Attempt to skip directly to classify stage
        with pytest.raises(ValueError, match="Cannot skip processing stages"):
            orchestrator.update_processing_stage(batch_id, ProcessingStage.CLASSIFY)
        
        # Should still be at initial state
        status = orchestrator.get_processing_status(batch_id)
        assert status.progress_percentage == 0
        assert status.current_stage == ProcessingStage.PARSE
    
    def test_progress_backward_transition_prevention(self, orchestrator):
        """Test that progress cannot go backward."""
        batch_id = uuid4()
        orchestrator._create_initial_status(batch_id, FileType.CAMPAIGN_XLSX)
        orchestrator.update_processing_stage(batch_id, ProcessingStage.PARSE)
        orchestrator.update_processing_stage(batch_id, ProcessingStage.VALIDATE)
        
        # Attempt to go backward should fail
        with pytest.raises(ValueError, match="Cannot move backward in processing stages"):
            orchestrator.update_processing_stage(batch_id, ProcessingStage.PARSE)
        
        # Should remain at validate (50%)
        status = orchestrator.get_processing_status(batch_id)
        assert status.progress_percentage == 50
        assert status.current_stage == ProcessingStage.CLASSIFY
    
    def test_progress_completion_idempotency(self, orchestrator):
        """Test that completing processing multiple times is idempotent."""
        batch_id = uuid4()
        orchestrator._create_initial_status(batch_id, FileType.CAMPAIGN_XLSX)
        
        # Complete all stages
        orchestrator.update_processing_stage(batch_id, ProcessingStage.PARSE)
        orchestrator.update_processing_stage(batch_id, ProcessingStage.VALIDATE)
        orchestrator.update_processing_stage(batch_id, ProcessingStage.CLASSIFY)
        orchestrator.complete_processing(batch_id)
        
        # Complete again should be idempotent
        orchestrator.complete_processing(batch_id)
        orchestrator.complete_processing(batch_id)
        
        status = orchestrator.get_processing_status(batch_id)
        assert status.progress_percentage == 100
        assert status.current_stage == ProcessingStage.COMPLETE