"""Tests for upload service - TDD RED phase. MUST fail initially."""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi import UploadFile
from src.services.upload_service import save_uploaded_file, store_file_metadata, generate_unique_filename, get_upload_status
from src.models.upload import DataUpload

@pytest.fixture
def mock_upload_file():
    mock_file = Mock(spec=UploadFile)
    mock_file.filename = "test.csv"
    mock_file.read = AsyncMock(return_value=b"test,data\n1,2")
    return mock_file

@pytest.fixture
def mock_db_session():
    return Mock()

class TestSaveUploadedFile:
    @pytest.mark.asyncio
    @patch('os.makedirs')
    @patch('aiofiles.open', new_callable=AsyncMock)
    async def test_saves_file_with_unique_name(self, mock_file_open, mock_makedirs, mock_upload_file):
        result = await save_uploaded_file(mock_upload_file, "uploads/")
        assert result.startswith("uploads/")
        assert "test.csv" in result
        assert len(result.split("/")[-1]) > len("test.csv")
        mock_makedirs.assert_called_once()

    @pytest.mark.asyncio
    async def test_creates_upload_directory(self, mock_upload_file):
        with patch('aiofiles.open', new_callable=AsyncMock), patch('os.makedirs') as mock_makedirs:
            await save_uploaded_file(mock_upload_file, "new_dir/")
            mock_makedirs.assert_called_with("new_dir/", exist_ok=True)

class TestStoreFileMetadata:
    @pytest.mark.asyncio
    async def test_creates_database_record(self, mock_db_session):
        file_info = {"filename": "test.csv", "file_size": 1024, "file_type": "text/csv"}
        result = await store_file_metadata(file_info, mock_db_session)
        assert isinstance(result, DataUpload)
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_database_error(self, mock_db_session):
        mock_db_session.commit.side_effect = Exception("DB Error")
        with pytest.raises(Exception):
            await store_file_metadata({"filename": "test.csv", "file_size": 1024, "file_type": "text/csv"}, mock_db_session)

class TestGenerateUniqueFilename:
    def test_adds_uuid_prefix_and_preserves_extension(self):
        result = generate_unique_filename("test.csv")
        assert result.endswith("_test.csv") and len(result) > len("test.csv")
        
        result_pdf = generate_unique_filename("document.pdf")
        assert result_pdf.endswith(".pdf")

    def test_uniqueness(self):
        result1 = generate_unique_filename("test.csv")
        result2 = generate_unique_filename("test.csv")
        assert result1 != result2

class TestGetUploadStatus:
    @pytest.mark.asyncio
    async def test_retrieves_upload_status(self, mock_db_session):
        mock_upload = Mock()
        mock_upload.status = "completed"
        mock_upload.filename = "test.csv"
        mock_db_session.query().filter().first.return_value = mock_upload
        result = await get_upload_status("123", mock_db_session)
        assert result["status"] == "completed"

    @pytest.mark.asyncio
    async def test_handles_nonexistent_upload(self, mock_db_session):
        mock_db_session.query().filter().first.return_value = None
        result = await get_upload_status("999", mock_db_session)
        assert result is None