import pytest
from fastapi.testclient import TestClient
from src.main import app

@pytest.fixture
def client():
    """Test client for FastAPI application."""
    return TestClient(app)

@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return {
        "email": "test@example.com",
        "name": "Test User"
    }

@pytest.fixture
def sample_upload_data():
    """Sample file upload data for testing."""
    return {
        "filename": "test_data.csv",
        "original_filename": "test_data.csv",
        "file_size": 1024,
        "mime_type": "text/csv"
    }