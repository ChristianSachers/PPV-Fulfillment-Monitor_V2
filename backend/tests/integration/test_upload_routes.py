"""
Integration tests for upload API routes.

These tests define the API contract for upload endpoints and will initially FAIL
because the routes don't exist yet (following TDD principles).

Expected responses:
- 404 errors initially (routes not implemented)
- Will pass once routes are implemented correctly
"""

import pytest
from fastapi.testclient import TestClient
from fastapi import UploadFile
from io import BytesIO
from src.main import app

client = TestClient(app)


# Test fixtures for mock file uploads
@pytest.fixture
def csv_file_content():
    """Mock CSV file content."""
    return b"name,value\ntest1,100\ntest2,200"


@pytest.fixture
def excel_file_content():
    """Mock Excel file content (minimal XLSX bytes)."""
    # Minimal XLSX file header
    return b"PK\x03\x04\x14\x00\x00\x08\x08\x00"


@pytest.fixture
def json_file_content():
    """Mock JSON file content."""
    return b'{"data": [{"name": "test", "value": 123}]}'


class TestUploadEndpointPOST:
    """Test cases for POST /api/uploads/ endpoint."""

    def test_upload_csv_file_success(self, csv_file_content):
        """Test successful CSV file upload."""
        files = {"file": ("test.csv", BytesIO(csv_file_content), "text/csv")}
        response = client.post("/api/uploads/", files=files)
        
        # TDD RED phase: Expect success response, will FAIL until route exists
        assert response.status_code == 200
        data = response.json()
        assert "upload_id" in data
        assert "filename" in data
        assert "file_size" in data

    def test_upload_excel_file_success(self, excel_file_content):
        """Test successful Excel file upload."""
        files = {"file": ("test.xlsx", BytesIO(excel_file_content), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        response = client.post("/api/uploads/", files=files)
        
        # TDD RED phase: Expect success response, will FAIL until route exists
        assert response.status_code == 200
        data = response.json()
        assert data["filename"] == "test.xlsx"

    def test_upload_json_file_success(self, json_file_content):
        """Test successful JSON file upload."""
        files = {"file": ("test.json", BytesIO(json_file_content), "application/json")}
        response = client.post("/api/uploads/", files=files)
        
        # TDD RED phase: Expect success response, will FAIL until route exists
        assert response.status_code == 200
        data = response.json()
        assert "upload_id" in data

    def test_upload_file_size_validation(self):
        """Test file size validation (reject >500MB files)."""
        # Create mock large file content
        large_content = b"x" * (500 * 1024 * 1024 + 1)  # Just over 500MB
        files = {"file": ("large.csv", BytesIO(large_content), "text/csv")}
        response = client.post("/api/uploads/", files=files)
        
        # TDD RED phase: Expect validation error, will FAIL until route exists
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_upload_invalid_file_type(self):
        """Test file type validation (reject .txt, .exe files)."""
        files = {"file": ("malicious.exe", BytesIO(b"fake exe"), "application/octet-stream")}
        response = client.post("/api/uploads/", files=files)
        
        # TDD RED phase: Expect validation error, will FAIL until route exists
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_upload_empty_filename(self):
        """Test empty filename handling."""
        files = {"file": ("", BytesIO(b"content"), "text/csv")}
        response = client.post("/api/uploads/", files=files)
        
        # TDD RED phase: Expect validation error, will FAIL until route exists
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data

    def test_upload_malformed_request(self):
        """Test malformed multipart requests."""
        # Send request without file
        response = client.post("/api/uploads/")
        
        # TDD RED phase: Expect validation error, will FAIL until route exists
        assert response.status_code == 422
        data = response.json()
        assert "detail" in data


class TestUploadEndpointGETList:
    """Test cases for GET /api/uploads/ endpoint."""

    def test_list_uploads_empty(self):
        """Test listing uploads when no files uploaded yet."""
        response = client.get("/api/uploads/")
        
        # TDD RED phase: Expect success response, will FAIL until route exists
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_list_uploads_with_pagination(self):
        """Test pagination parameters (skip, limit)."""
        response = client.get("/api/uploads/?skip=0&limit=10")
        
        # TDD RED phase: Expect success response, will FAIL until route exists
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) <= 10

    def test_list_uploads_metadata_format(self):
        """Test response format contains correct metadata."""
        response = client.get("/api/uploads/")
        
        # TDD RED phase: Expect success response, will FAIL until route exists
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Empty list is valid for metadata format test


class TestUploadEndpointGETById:
    """Test cases for GET /api/uploads/{upload_id} endpoint."""

    def test_get_upload_by_id_not_found(self):
        """Test 404 response for non-existent upload ID."""
        fake_id = "nonexistent-upload-id"
        response = client.get(f"/api/uploads/{fake_id}")
        
        # Should always return 404 for non-existent ID
        assert response.status_code == 404

    def test_get_upload_by_id_success(self):
        """Test retrieving specific upload by ID (when ID exists)."""
        # This test will initially fail because route doesn't exist
        response = client.get("/api/uploads/test-upload-id")
        
        # TDD RED phase: Expect success response, will FAIL until route exists
        assert response.status_code == 200
        data = response.json()
        assert "upload_id" in data
        assert "filename" in data
        assert "file_size" in data
        assert "upload_date" in data

    def test_get_upload_metadata_format(self):
        """Test response format with single file metadata."""
        response = client.get("/api/uploads/test-id")
        
        # TDD RED phase: Expect success response, will FAIL until route exists
        assert response.status_code == 200
        data = response.json()
        # Verify single upload object (not array)
        assert isinstance(data, dict)
        assert "upload_id" in data