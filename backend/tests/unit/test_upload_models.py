"""
Tests for upload models - TDD RED phase
These tests MUST fail initially since models don't exist yet.
"""
import pytest
from pydantic import ValidationError
from src.models.upload import DataUploadRequest, DataUploadResponse, FileValidationError


class TestDataUploadRequest:
    
    def test_valid_upload_request(self):
        """Test valid upload request with all required fields"""
        data = {"filename": "test.csv", "file_size": 1024, "file_type": "text/csv"}
        request = DataUploadRequest(**data)
        assert request.filename == "test.csv"
        assert request.file_size == 1024

    def test_invalid_filename_empty(self):
        """Test upload request fails with empty filename"""
        with pytest.raises(ValidationError):
            DataUploadRequest(filename="", file_size=1024, file_type="text/csv")

    def test_invalid_file_size_negative(self):
        """Test upload request fails with negative file size"""
        with pytest.raises(ValidationError):
            DataUploadRequest(filename="test.csv", file_size=-1, file_type="text/csv")

    def test_invalid_file_type_empty(self):
        """Test upload request fails with empty file type"""
        with pytest.raises(ValidationError):
            DataUploadRequest(filename="test.csv", file_size=1024, file_type="")


class TestDataUploadResponse:
    
    def test_upload_response_structure(self):
        """Test upload response contains required metadata fields"""
        response = DataUploadResponse(
            id="123", filename="test.csv", size=1024, 
            file_type="text/csv", status="pending"
        )
        assert response.id == "123"
        assert response.status == "pending"
        assert hasattr(response, 'created_at')

    def test_upload_response_timestamps(self):
        """Test response includes creation timestamp"""
        response = DataUploadResponse(
            id="123", filename="test.csv", size=1024,
            file_type="text/csv", status="pending"
        )
        assert response.created_at is not None


class TestFileValidationError:
    
    def test_file_validation_error_creation(self):
        """Test custom exception can be created with message"""
        error = FileValidationError("Invalid file format")
        assert str(error) == "Invalid file format"

    def test_file_validation_error_inheritance(self):
        """Test FileValidationError inherits from Exception"""
        error = FileValidationError("Test error")
        assert isinstance(error, Exception)