"""
Integration tests for Upload Processing API Endpoints

Testing all 6 API endpoints with comprehensive scenarios:
1. POST /api/upload/process - File upload with processing state check
2. GET /api/upload/status/{batch_id} - Processing status polling (2s intervals)
3. GET /api/upload/progress/{batch_id} - Detailed progress tracking (25% increments)
4. GET /api/upload/processing-state/{file_type} - Current processing state per file type
5. POST /api/upload/cancel/{batch_id} - Cancel active processing
6. GET /api/upload/errors/{batch_id} - Time-ordered error list

Following TDD RED-GREEN-REFACTOR approach:
- RED: Write failing tests first (this file)
- GREEN: Implement minimal code to pass tests
- REFACTOR: Optimize and improve code quality
"""
import pytest
import json
import io
from datetime import datetime
from uuid import uuid4
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock

from src.main import app
from src.services.upload_processing_orchestrator import (
    UploadProcessingOrchestrator,
    ProcessingState,
    ProcessingStage,
    FileType,
    ProcessingStatus,
    ProcessingError
)


@pytest.fixture
def client():
    """Create test client for API testing."""
    return TestClient(app)


@pytest.fixture
def mock_orchestrator():
    """Create mock upload processing orchestrator."""
    orchestrator = Mock(spec=UploadProcessingOrchestrator)
    
    # Default mock behavior
    orchestrator.detect_file_type.return_value = FileType.CAMPAIGN_XLSX
    orchestrator.is_upload_available.return_value = True
    orchestrator.generate_processing_batch_id.return_value = uuid4()
    orchestrator.get_processing_state.return_value = ProcessingState.IDLE
    
    return orchestrator


@pytest.fixture
def valid_xlsx_file():
    """Create valid XLSX file content for testing."""
    # Create mock XLSX content (simplified for testing)
    content = b"PK\x03\x04"  # XLSX file signature
    content += b"Mock XLSX content for testing" * 100  # Make it reasonably sized
    return io.BytesIO(content)


@pytest.fixture
def valid_csv_file():
    """Create valid CSV file content for testing."""
    csv_content = """Deal ID,Date Recorded,Total Impressions,Purchase Type,Buyer,Core DSP Campaign Name,Deal Name,Campaign/Deal Purchase Type
00000000-0000-0000-0000-000000000001,2024-01-15T10:30:00Z,1000000,guaranteed,TestBuyer,TestCampaign,TestDeal,guaranteed
00000000-0000-0000-0000-000000000002,2024-01-15T11:30:00Z,2000000,unguaranteed,TestBuyer2,TestCampaign2,TestDeal2,unguaranteed
"""
    return io.BytesIO(csv_content.encode('utf-8'))


@pytest.fixture
def oversized_file():
    """Create file exceeding 250MB limit for testing."""
    # Create 251MB of content
    content = b"x" * (251 * 1024 * 1024)
    return io.BytesIO(content)


class TestUploadProcessEndpoint:
    """Test POST /api/upload/process endpoint."""
    
    @patch('src.routes.upload_processing.get_orchestrator')
    def test_upload_xlsx_file_success(self, mock_get_orchestrator, client, mock_orchestrator, valid_xlsx_file):
        """Test successful XLSX file upload with processing initiation."""
        # Setup mock
        batch_id = uuid4()
        mock_orchestrator.is_upload_available.return_value = True
        mock_orchestrator.start_processing.return_value = batch_id
        mock_orchestrator.generate_processing_batch_id.return_value = batch_id
        
        # Mock process_file to return proper structure
        mock_orchestrator.process_file.return_value = {"errors": []}
        mock_orchestrator._validate_parsed_data.return_value = True
        mock_orchestrator._classify_batch_data.return_value = True
        
        mock_get_orchestrator.return_value = mock_orchestrator
        
        # Make request
        response = client.post(
            "/api/upload/process",
            files={"file": ("test_campaign.xlsx", valid_xlsx_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "processing_batch_id" in data
        assert data["file_type"] == "campaign_xlsx"
        assert data["processing_started"] is True
        assert "estimated_completion_time" in data
        
        # Verify orchestrator calls (content type detection works, so detect_file_type not called)
        mock_orchestrator.is_upload_available.assert_called_once_with(FileType.CAMPAIGN_XLSX)
        mock_orchestrator.start_processing.assert_called_once()
    
    @patch('src.routes.upload_processing.get_orchestrator')
    def test_upload_csv_file_success(self, mock_get_orchestrator, client, mock_orchestrator, valid_csv_file):
        """Test successful CSV file upload with processing initiation."""
        # Setup mock
        batch_id = uuid4()
        mock_orchestrator.is_upload_available.return_value = True
        mock_orchestrator.start_processing.return_value = batch_id
        
        # Mock process_file to return proper CSV structure
        mock_result = Mock()
        mock_result.parsing_errors = []
        mock_orchestrator.process_file.return_value = mock_result
        mock_orchestrator._validate_parsed_data.return_value = True
        mock_orchestrator._classify_batch_data.return_value = True
        
        mock_get_orchestrator.return_value = mock_orchestrator
        
        # Make request
        response = client.post(
            "/api/upload/process",
            files={"file": ("test_reporting.csv", valid_csv_file, "text/csv")}
        )
        
        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "processing_batch_id" in data
        assert data["file_type"] == "reporting_csv"
        assert data["processing_started"] is True
    
    def test_upload_file_size_exceeds_limit(self, client, oversized_file):
        """Test file upload rejection when size exceeds 250MB limit."""
        response = client.post(
            "/api/upload/process",
            files={"file": ("oversized.xlsx", oversized_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert "250MB" in data["detail"]
    
    @patch('src.routes.upload_processing.get_orchestrator')
    def test_upload_blocked_when_processing_active(self, mock_get_orchestrator, client, mock_orchestrator, valid_xlsx_file):
        """Test upload blocking when processing is already active for file type."""
        # Setup mock to simulate active processing
        mock_orchestrator.detect_file_type.return_value = FileType.CAMPAIGN_XLSX
        mock_orchestrator.is_upload_available.return_value = False
        mock_orchestrator.get_upload_blocking_message.return_value = "Processing in progress for Campaign files - please wait or cancel current analysis"
        mock_get_orchestrator.return_value = mock_orchestrator
        
        response = client.post(
            "/api/upload/process",
            files={"file": ("test_campaign.xlsx", valid_xlsx_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )
        
        assert response.status_code == 409  # Conflict - processing active
        data = response.json()
        assert "detail" in data
        assert "Processing in progress" in data["detail"]
    
    def test_upload_invalid_file_type(self, client):
        """Test upload rejection for unsupported file types."""
        invalid_file = io.BytesIO(b"Invalid file content")
        
        response = client.post(
            "/api/upload/process",
            files={"file": ("test.txt", invalid_file, "text/plain")}
        )
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        assert "Unsupported file type" in data["detail"]
    
    def test_upload_missing_file(self, client):
        """Test upload endpoint with missing file parameter."""
        response = client.post("/api/upload/process")
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data


class TestUploadStatusEndpoint:
    """Test GET /api/upload/status/{batch_id} endpoint."""
    
    @patch('src.routes.upload_processing.get_orchestrator')
    def test_get_status_processing_active(self, mock_get_orchestrator, client, mock_orchestrator):
        """Test status retrieval for active processing."""
        batch_id = uuid4()
        
        # Setup mock processing status
        mock_status = ProcessingStatus(
            processing_batch_id=batch_id,
            file_type=FileType.CAMPAIGN_XLSX,
            processing_state=ProcessingState.PROCESSING,
            current_stage=ProcessingStage.VALIDATE,
            progress_percentage=50,
            start_time=datetime.now()
        )
        mock_orchestrator.get_processing_status.return_value = mock_status
        mock_orchestrator.get_processing_errors.return_value = []  # Empty error list
        mock_get_orchestrator.return_value = mock_orchestrator
        
        response = client.get(f"/api/upload/status/{batch_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["processing_batch_id"] == str(batch_id)
        assert data["processing_state"] == "processing"
        assert data["current_stage"] == "validate"
        assert data["progress_percentage"] == 50
        assert data["file_type"] == "campaign_xlsx"
        assert "start_time" in data
    
    @patch('src.routes.upload_processing.get_orchestrator')
    def test_get_status_completed(self, mock_get_orchestrator, client, mock_orchestrator):
        """Test status retrieval for completed processing."""
        batch_id = uuid4()
        
        mock_status = ProcessingStatus(
            processing_batch_id=batch_id,
            file_type=FileType.REPORTING_CSV,
            processing_state=ProcessingState.COMPLETED,
            current_stage=ProcessingStage.COMPLETE,
            progress_percentage=100,
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        mock_orchestrator.get_processing_status.return_value = mock_status
        mock_orchestrator.get_processing_errors.return_value = []  # Empty error list
        mock_get_orchestrator.return_value = mock_orchestrator
        
        response = client.get(f"/api/upload/status/{batch_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["processing_state"] == "completed"
        assert data["progress_percentage"] == 100
        assert data["end_time"] is not None
    
    @patch('src.routes.upload_processing.get_orchestrator')
    def test_get_status_error_state(self, mock_get_orchestrator, client, mock_orchestrator):
        """Test status retrieval for error state."""
        batch_id = uuid4()
        
        mock_error = ProcessingError(
            message="Test error",
            stage=ProcessingStage.PARSE,
            timestamp=datetime.now(),
            technical_details="Test error details"
        )
        
        mock_status = ProcessingStatus(
            processing_batch_id=batch_id,
            file_type=FileType.CAMPAIGN_XLSX,
            processing_state=ProcessingState.ERROR,
            current_stage=ProcessingStage.PARSE,
            progress_percentage=25,
            start_time=datetime.now(),
            end_time=datetime.now(),
            errors=[mock_error]
        )
        mock_orchestrator.get_processing_status.return_value = mock_status
        mock_orchestrator.get_processing_errors.return_value = [mock_error]  # List with one error
        mock_get_orchestrator.return_value = mock_orchestrator
        
        response = client.get(f"/api/upload/status/{batch_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["processing_state"] == "error"
        assert data["has_errors"] is True
        assert data["error_count"] == 1
    
    @patch('src.routes.upload_processing.get_orchestrator')
    def test_get_status_batch_not_found(self, mock_get_orchestrator, client, mock_orchestrator):
        """Test status retrieval for non-existent batch ID."""
        batch_id = uuid4()
        mock_orchestrator.get_processing_status.return_value = None
        mock_get_orchestrator.return_value = mock_orchestrator
        
        response = client.get(f"/api/upload/status/{batch_id}")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()
    
    def test_get_status_invalid_batch_id(self, client):
        """Test status retrieval with invalid batch ID format."""
        response = client.get("/api/upload/status/invalid-uuid")
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data


class TestUploadProgressEndpoint:
    """Test GET /api/upload/progress/{batch_id} endpoint."""
    
    @patch('src.routes.upload_processing.get_orchestrator')
    def test_get_progress_detailed_tracking(self, mock_get_orchestrator, client, mock_orchestrator):
        """Test detailed progress tracking with equal stage percentages."""
        batch_id = uuid4()
        
        # Mock progress stages
        mock_orchestrator.get_progress_stages.return_value = {
            ProcessingStage.PARSE: 25,
            ProcessingStage.VALIDATE: 50,
            ProcessingStage.CLASSIFY: 75,
            ProcessingStage.COMPLETE: 100
        }
        
        mock_status = ProcessingStatus(
            processing_batch_id=batch_id,
            file_type=FileType.CAMPAIGN_XLSX,
            processing_state=ProcessingState.PROCESSING,
            current_stage=ProcessingStage.CLASSIFY,
            progress_percentage=75,
            start_time=datetime.now()
        )
        mock_orchestrator.get_processing_status.return_value = mock_status
        mock_get_orchestrator.return_value = mock_orchestrator
        
        response = client.get(f"/api/upload/progress/{batch_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["processing_batch_id"] == str(batch_id)
        assert data["current_stage"] == "classify"
        assert data["progress_percentage"] == 75
        assert "stage_progress" in data
        assert data["stage_progress"]["parse"] == 25
        assert data["stage_progress"]["validate"] == 50
        assert data["stage_progress"]["classify"] == 75
        assert data["stage_progress"]["complete"] == 100
    
    @patch('src.routes.upload_processing.get_orchestrator')
    def test_get_progress_with_estimated_completion(self, mock_get_orchestrator, client, mock_orchestrator):
        """Test progress tracking with estimated completion time."""
        batch_id = uuid4()
        start_time = datetime.now()
        
        mock_status = ProcessingStatus(
            processing_batch_id=batch_id,
            file_type=FileType.REPORTING_CSV,
            processing_state=ProcessingState.PROCESSING,
            current_stage=ProcessingStage.VALIDATE,
            progress_percentage=50,
            start_time=start_time
        )
        mock_orchestrator.get_processing_status.return_value = mock_status
        mock_orchestrator.get_progress_stages.return_value = {
            ProcessingStage.PARSE: 25,
            ProcessingStage.VALIDATE: 50,
            ProcessingStage.CLASSIFY: 75,
            ProcessingStage.COMPLETE: 100
        }
        mock_get_orchestrator.return_value = mock_orchestrator
        
        response = client.get(f"/api/upload/progress/{batch_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert "estimated_completion_time" in data
        assert "elapsed_time_seconds" in data
        assert data["progress_percentage"] == 50


class TestProcessingStateEndpoint:
    """Test GET /api/upload/processing-state/{file_type} endpoint."""
    
    @patch('src.routes.upload_processing.get_orchestrator')
    def test_get_processing_state_idle(self, mock_get_orchestrator, client, mock_orchestrator):
        """Test processing state retrieval when idle."""
        mock_orchestrator.get_upload_control_status.return_value = {
            'upload_available': True,
            'processing_active': False,
            'current_batch_id': None,
            'can_cancel': False,
            'blocking_message': None,
            'processing_state': 'idle'
        }
        mock_get_orchestrator.return_value = mock_orchestrator
        
        response = client.get("/api/upload/processing-state/campaign_xlsx")
        
        assert response.status_code == 200
        data = response.json()
        assert data["file_type"] == "campaign_xlsx"
        assert data["upload_available"] is True
        assert data["processing_active"] is False
        assert data["processing_state"] == "idle"
        assert data["current_batch_id"] is None
    
    @patch('src.routes.upload_processing.get_orchestrator')
    def test_get_processing_state_active(self, mock_get_orchestrator, client, mock_orchestrator):
        """Test processing state retrieval when processing is active."""
        batch_id = uuid4()
        mock_orchestrator.get_upload_control_status.return_value = {
            'upload_available': False,
            'processing_active': True,
            'current_batch_id': str(batch_id),
            'can_cancel': True,
            'blocking_message': 'Processing in progress for Campaign files - please wait or cancel current analysis',
            'processing_state': 'processing'
        }
        mock_get_orchestrator.return_value = mock_orchestrator
        
        response = client.get("/api/upload/processing-state/campaign_xlsx")
        
        assert response.status_code == 200
        data = response.json()
        assert data["upload_available"] is False
        assert data["processing_active"] is True
        assert data["current_batch_id"] == str(batch_id)
        assert data["can_cancel"] is True
        assert "Processing in progress" in data["blocking_message"]
    
    def test_get_processing_state_invalid_file_type(self, client):
        """Test processing state retrieval with invalid file type."""
        response = client.get("/api/upload/processing-state/invalid_type")
        
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data
        # FastAPI returns structured validation errors for enum types
        assert isinstance(data["detail"], list)
        assert len(data["detail"]) > 0
        assert data["detail"][0]["type"] == "enum"
        assert "campaign_xlsx" in data["detail"][0]["msg"]
        assert "reporting_csv" in data["detail"][0]["msg"]


class TestCancelProcessingEndpoint:
    """Test POST /api/upload/cancel/{batch_id} endpoint."""
    
    @patch('src.routes.upload_processing.get_orchestrator')
    def test_cancel_processing_success(self, mock_get_orchestrator, client, mock_orchestrator):
        """Test successful processing cancellation."""
        batch_id = uuid4()
        
        # Mock that batch exists and can be cancelled
        mock_status = ProcessingStatus(
            processing_batch_id=batch_id,
            file_type=FileType.CAMPAIGN_XLSX,
            processing_state=ProcessingState.PROCESSING,
            current_stage=ProcessingStage.VALIDATE,
            progress_percentage=50,
            start_time=datetime.now()
        )
        mock_orchestrator.get_processing_status.return_value = mock_status
        mock_get_orchestrator.return_value = mock_orchestrator
        
        response = client.post(f"/api/upload/cancel/{batch_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["processing_batch_id"] == str(batch_id)
        assert data["cancelled"] is True
        assert data["message"] == "Processing cancelled successfully"
        
        # Verify cancellation was called
        mock_orchestrator.cancel_processing.assert_called_once_with(batch_id)
    
    @patch('src.routes.upload_processing.get_orchestrator')
    def test_cancel_processing_not_found(self, mock_get_orchestrator, client, mock_orchestrator):
        """Test cancellation attempt for non-existent batch."""
        batch_id = uuid4()
        mock_orchestrator.get_processing_status.return_value = None
        mock_get_orchestrator.return_value = mock_orchestrator
        
        response = client.post(f"/api/upload/cancel/{batch_id}")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()
    
    @patch('src.routes.upload_processing.get_orchestrator')
    def test_cancel_processing_already_completed(self, mock_get_orchestrator, client, mock_orchestrator):
        """Test cancellation attempt for already completed processing."""
        batch_id = uuid4()
        
        mock_status = ProcessingStatus(
            processing_batch_id=batch_id,
            file_type=FileType.CAMPAIGN_XLSX,
            processing_state=ProcessingState.COMPLETED,
            current_stage=ProcessingStage.COMPLETE,
            progress_percentage=100,
            start_time=datetime.now(),
            end_time=datetime.now()
        )
        mock_orchestrator.get_processing_status.return_value = mock_status
        mock_get_orchestrator.return_value = mock_orchestrator
        
        response = client.post(f"/api/upload/cancel/{batch_id}")
        
        assert response.status_code == 409  # Conflict - cannot cancel completed processing
        data = response.json()
        assert "detail" in data
        assert "cannot be cancelled" in data["detail"].lower()


class TestUploadErrorsEndpoint:
    """Test GET /api/upload/errors/{batch_id} endpoint."""
    
    @patch('src.routes.upload_processing.get_orchestrator')
    def test_get_errors_structured_response(self, mock_get_orchestrator, client, mock_orchestrator):
        """Test structured error response with time-ordered errors."""
        batch_id = uuid4()
        
        # Mock structured error response
        mock_orchestrator.get_structured_error_response.return_value = {
            "batch_id": str(batch_id),
            "timestamp": "2024-01-15T10:30:00Z",
            "errors": [
                {
                    "error_id": str(uuid4()),
                    "timestamp": "2024-01-15T10:30:15Z",
                    "category": "validation",
                    "severity": "error",
                    "code": "INVALID_UUID",
                    "message": "Invalid Deal UUID format in row 1,234",
                    "technical_details": "UUID 'abc123' does not match expected pattern",
                    "context": {
                        "file_type": "campaign_xlsx",
                        "row_number": 1234,
                        "column_name": "Deal/Campaign ID",
                        "invalid_value": "abc123"
                    },
                    "suggested_actions": [
                        "Verify Deal UUID format in source system",
                        "Check row 1,234 in uploaded file",
                        "Contact data administrator if UUID should be valid"
                    ]
                }
            ]
        }
        mock_get_orchestrator.return_value = mock_orchestrator
        
        response = client.get(f"/api/upload/errors/{batch_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["batch_id"] == str(batch_id)
        assert "timestamp" in data
        assert len(data["errors"]) == 1
        
        error = data["errors"][0]
        assert error["category"] == "validation"
        assert error["severity"] == "error"
        assert error["code"] == "INVALID_UUID"
        assert "Invalid Deal UUID format" in error["message"]
        assert "context" in error
        assert "suggested_actions" in error
    
    @patch('src.routes.upload_processing.get_orchestrator')
    def test_get_errors_multiple_time_ordered(self, mock_get_orchestrator, client, mock_orchestrator):
        """Test multiple errors in time-ordered sequence (oldest first)."""
        batch_id = uuid4()
        
        mock_orchestrator.get_structured_error_response.return_value = {
            "batch_id": str(batch_id),
            "timestamp": "2024-01-15T10:30:00Z",
            "errors": [
                {
                    "error_id": str(uuid4()),
                    "timestamp": "2024-01-15T10:30:10Z",  # First error (oldest)
                    "category": "parsing",
                    "severity": "error",
                    "code": "PARSE_ERROR",
                    "message": "File parsing failed at row 500",
                    "technical_details": "Invalid data format",
                    "context": {"row_number": 500},
                    "suggested_actions": ["Check file format"]
                },
                {
                    "error_id": str(uuid4()),
                    "timestamp": "2024-01-15T10:30:15Z",  # Second error
                    "category": "validation",
                    "severity": "warning",
                    "code": "VALIDATION_WARNING",
                    "message": "Missing budget data in row 750",
                    "technical_details": "Budget field is null",
                    "context": {"row_number": 750},
                    "suggested_actions": ["Verify budget data"]
                }
            ]
        }
        mock_get_orchestrator.return_value = mock_orchestrator
        
        response = client.get(f"/api/upload/errors/{batch_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["errors"]) == 2
        
        # Verify time ordering (oldest first)
        first_error_time = data["errors"][0]["timestamp"]
        second_error_time = data["errors"][1]["timestamp"]
        assert first_error_time < second_error_time
    
    @patch('src.routes.upload_processing.get_orchestrator')
    def test_get_errors_no_errors(self, mock_get_orchestrator, client, mock_orchestrator):
        """Test error retrieval when no errors exist."""
        batch_id = uuid4()
        
        mock_orchestrator.get_structured_error_response.return_value = {
            "batch_id": str(batch_id),
            "timestamp": "2024-01-15T10:30:00Z",
            "errors": []
        }
        mock_get_orchestrator.return_value = mock_orchestrator
        
        response = client.get(f"/api/upload/errors/{batch_id}")
        
        assert response.status_code == 200
        data = response.json()
        assert data["batch_id"] == str(batch_id)
        assert len(data["errors"]) == 0
    
    @patch('src.routes.upload_processing.get_orchestrator')
    def test_get_errors_batch_not_found(self, mock_get_orchestrator, client, mock_orchestrator):
        """Test error retrieval for non-existent batch."""
        batch_id = uuid4()
        mock_orchestrator.get_structured_error_response.return_value = {
            "batch_id": str(batch_id),
            "timestamp": "2024-01-15T10:30:00Z",
            "errors": []
        }
        mock_orchestrator.get_processing_status.return_value = None
        mock_get_orchestrator.return_value = mock_orchestrator
        
        response = client.get(f"/api/upload/errors/{batch_id}")
        
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data


class TestHTTPPollingOptimization:
    """Test HTTP polling optimization for 2-second intervals."""
    
    @patch('src.routes.upload_processing.get_orchestrator')
    def test_status_endpoint_optimized_response(self, mock_get_orchestrator, client, mock_orchestrator):
        """Test status endpoint returns optimized response for HTTP polling."""
        batch_id = uuid4()
        
        mock_status = ProcessingStatus(
            processing_batch_id=batch_id,
            file_type=FileType.CAMPAIGN_XLSX,
            processing_state=ProcessingState.PROCESSING,
            current_stage=ProcessingStage.VALIDATE,
            progress_percentage=50,
            start_time=datetime.now()
        )
        mock_orchestrator.get_processing_status.return_value = mock_status
        mock_orchestrator.get_processing_errors.return_value = []  # Empty error list
        mock_get_orchestrator.return_value = mock_orchestrator
        
        response = client.get(f"/api/upload/status/{batch_id}")
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify response contains only essential fields for polling
        essential_fields = [
            "processing_batch_id", "processing_state", "progress_percentage",
            "current_stage", "file_type", "has_errors"
        ]
        for field in essential_fields:
            assert field in data
        
        # Verify response is compact for efficient polling
        assert isinstance(data["processing_state"], str)
        assert isinstance(data["progress_percentage"], int)
        assert isinstance(data["has_errors"], bool)
    
    @patch('src.routes.upload_processing.get_orchestrator')
    def test_multiple_polling_requests_performance(self, mock_get_orchestrator, client, mock_orchestrator):
        """Test performance of multiple rapid polling requests."""
        batch_id = uuid4()
        
        mock_status = ProcessingStatus(
            processing_batch_id=batch_id,
            file_type=FileType.CAMPAIGN_XLSX,
            processing_state=ProcessingState.PROCESSING,
            current_stage=ProcessingStage.VALIDATE,
            progress_percentage=50,
            start_time=datetime.now()
        )
        mock_orchestrator.get_processing_status.return_value = mock_status
        mock_orchestrator.get_processing_errors.return_value = []  # Empty error list
        mock_get_orchestrator.return_value = mock_orchestrator
        
        # Simulate rapid polling (2-second intervals)
        for i in range(5):
            response = client.get(f"/api/upload/status/{batch_id}")
            assert response.status_code == 200
            
            # Each response should be consistent and fast
            data = response.json()
            assert data["processing_batch_id"] == str(batch_id)
            assert data["progress_percentage"] == 50


class TestIntegrationWithOrchestrator:
    """Test integration with UploadProcessingOrchestrator."""
    
    @patch('src.routes.upload_processing.get_orchestrator')
    def test_orchestrator_integration_complete_workflow(self, mock_get_orchestrator, client, mock_orchestrator, valid_xlsx_file):
        """Test complete workflow integration with orchestrator."""
        batch_id = uuid4()
        
        # Setup mock orchestrator for current API implementation (using start_processing + background tasks)
        mock_orchestrator.is_upload_available.return_value = True
        mock_orchestrator.start_processing.return_value = batch_id
        
        # Mock background processing methods to avoid "'Mock' object is not subscriptable" error
        mock_orchestrator.process_file.return_value = {"errors": []}  # Empty errors for XLSX
        mock_orchestrator._validate_parsed_data.return_value = True
        mock_orchestrator._classify_batch_data.return_value = True
        mock_orchestrator.update_processing_stage.return_value = True
        mock_orchestrator.complete_processing.return_value = True
        
        # Setup status progression
        initial_status = ProcessingStatus(
            processing_batch_id=batch_id,
            file_type=FileType.CAMPAIGN_XLSX,
            processing_state=ProcessingState.PROCESSING,
            current_stage=ProcessingStage.PARSE,
            progress_percentage=25,
            start_time=datetime.now()
        )
        mock_orchestrator.get_processing_status.return_value = initial_status
        mock_orchestrator.get_processing_errors.return_value = []  # Empty error list  
        
        mock_get_orchestrator.return_value = mock_orchestrator
        
        # Test upload initiation
        upload_response = client.post(
            "/api/upload/process",
            files={"file": ("test_campaign.xlsx", valid_xlsx_file, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )
        
        assert upload_response.status_code == 200
        upload_data = upload_response.json()
        returned_batch_id = upload_data["processing_batch_id"]
        
        # Test status polling
        status_response = client.get(f"/api/upload/status/{returned_batch_id}")
        assert status_response.status_code == 200
        status_data = status_response.json()
        assert status_data["current_stage"] == "parse"
        assert status_data["progress_percentage"] == 25
        
        # Verify orchestrator methods were called correctly (based on current API implementation)
        # Note: detect_file_type is not called because content type detection succeeds
        mock_orchestrator.is_upload_available.assert_called_once()
        mock_orchestrator.start_processing.assert_called_once()
    
    @patch('src.routes.upload_processing.get_orchestrator')
    def test_error_handling_integration(self, mock_get_orchestrator, client, mock_orchestrator):
        """Test error handling integration with orchestrator."""
        batch_id = uuid4()
        
        # Simulate orchestrator throwing exception
        mock_orchestrator.get_processing_status.side_effect = Exception("Database connection failed")
        mock_get_orchestrator.return_value = mock_orchestrator
        
        response = client.get(f"/api/upload/status/{batch_id}")
        
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data
        assert "internal error" in data["detail"].lower()


# Test data fixtures for edge cases
class TestEdgeCases:
    """Test edge cases and error scenarios."""
    
    def test_concurrent_upload_attempts(self, client):
        """Test handling of concurrent upload attempts for same file type."""
        # This test would require more complex setup with actual concurrency
        # For now, test the basic conflict response
        pass
    
    def test_batch_id_uuid_validation(self, client):
        """Test UUID validation for batch ID parameters."""
        # Test invalid UUID formats (excluding empty string which gives 404)
        invalid_uuids = [
            "not-a-uuid",
            "123456789",
            "abcd-efgh-ijkl-mnop"
        ]
        
        for invalid_uuid in invalid_uuids:
            response = client.get(f"/api/upload/status/{invalid_uuid}")
            assert response.status_code == 422
            data = response.json()
            assert "detail" in data
            # FastAPI returns structured validation errors for UUID types
            assert isinstance(data["detail"], list)
            assert len(data["detail"]) > 0
            assert data["detail"][0]["type"] == "uuid_parsing"
    
    def test_file_type_enum_validation(self, client):
        """Test file type enumeration validation."""
        # Test invalid file types (excluding empty string which gives 404)
        invalid_file_types = [
            "invalid_type",
            "xlsx",
            "csv",
            "campaign",
            "reporting"
        ]
        
        for invalid_type in invalid_file_types:
            response = client.get(f"/api/upload/processing-state/{invalid_type}")
            assert response.status_code == 422
            data = response.json()
            assert "detail" in data
            # FastAPI returns structured validation errors for enum types
            assert isinstance(data["detail"], list)
            assert len(data["detail"]) > 0
            assert data["detail"][0]["type"] == "enum"