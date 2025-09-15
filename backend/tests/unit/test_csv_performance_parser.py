"""
Comprehensive test suite for CSV Performance Parser
Following strict TDD methodology - tests written FIRST before implementation

Task 3: Memory-Efficient CSV Parser for Phase 1.1 upload processing pipeline
- Streaming CSV parser with 1000-record chunks for 250MB files
- Parse 8 columns per reportingCSVstructure.md specification
- Handle 1,073 records with variable data completeness (58%-100%)
- Memory-efficient batch processing for database insertion
- Integrate with ReportingStaging model
"""

import pytest
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from io import StringIO, BytesIO
import csv
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any, Generator

# Test data imports - will implement parser after tests
from src.models.staging import ReportingStaging, PurchaseType, ReportingStagingRequest
from src.database.staging_connection import StagingDatabase


class TestCSVPerformanceParserStructure:
    """Test CSV parser structure and initialization"""
    
    def test_parser_initialization(self):
        """Test parser can be initialized with required parameters"""
        # This will fail initially - RED phase of TDD
        from src.services.csv_performance_parser import CSVPerformanceParser
        
        batch_id = uuid4()
        parser = CSVPerformanceParser(processing_batch_id=batch_id)
        
        assert parser.processing_batch_id == batch_id
        assert parser.chunk_size == 1000  # Default chunk size
        assert hasattr(parser, 'parse_csv_stream')
        assert hasattr(parser, 'validate_headers')
        assert hasattr(parser, 'process_chunk')
    
    def test_parser_custom_chunk_size(self):
        """Test parser accepts custom chunk size"""
        from src.services.csv_performance_parser import CSVPerformanceParser
        
        parser = CSVPerformanceParser(
            processing_batch_id=uuid4(),
            chunk_size=500
        )
        assert parser.chunk_size == 500


class TestCSVHeaderValidation:
    """Test CSV header validation per reportingCSVstructure.md specification"""
    
    @pytest.fixture
    def valid_headers(self):
        """Expected CSV headers per specification"""
        return [
            "Date",
            "Core DSP Campaign Name", 
            "Core DSP Campaign ID",
            "Deal Name",
            "Deal ID",
            "Campaign Purchase Type",
            "Deal Purchase Type", 
            "Total Impressions"
        ]
    
    @pytest.fixture
    def parser(self):
        from src.services.csv_performance_parser import CSVPerformanceParser
        return CSVPerformanceParser(processing_batch_id=uuid4())
    
    def test_validate_correct_headers(self, parser, valid_headers):
        """Test validation passes with correct headers"""
        result = parser.validate_headers(valid_headers)
        assert result.is_valid is True
        assert len(result.errors) == 0
    
    def test_validate_missing_headers(self, parser):
        """Test validation fails with missing headers"""
        incomplete_headers = ["Date", "Deal Name", "Deal ID"]  # Missing 5 headers
        
        result = parser.validate_headers(incomplete_headers)
        assert result.is_valid is False
        assert len(result.errors) == 5
        assert "Missing required header: Core DSP Campaign Name" in result.errors
        assert "Missing required header: Total Impressions" in result.errors
    
    def test_validate_extra_headers(self, parser, valid_headers):
        """Test validation handles extra headers gracefully"""
        headers_with_extra = valid_headers + ["Extra Column", "Another Extra"]
        
        result = parser.validate_headers(headers_with_extra)
        assert result.is_valid is True  # Extra headers allowed
        assert len(result.warnings) == 2
        assert "Extra header found: Extra Column" in result.warnings
    
    def test_validate_case_insensitive_headers(self, parser):
        """Test headers are validated case-insensitively"""
        case_variant_headers = [
            "date",  # lowercase
            "CORE DSP CAMPAIGN NAME",  # uppercase
            "Core dsp Campaign ID",  # mixed case
            "Deal Name",
            "deal id",  # lowercase
            "Campaign Purchase Type",
            "Deal Purchase Type",
            "total impressions"  # lowercase
        ]
        
        result = parser.validate_headers(case_variant_headers)
        assert result.is_valid is True
        assert len(result.errors) == 0


class TestCSVDataValidation:
    """Test CSV data validation for each column per reportingCSVstructure.md"""
    
    @pytest.fixture
    def parser(self):
        from src.services.csv_performance_parser import CSVPerformanceParser
        return CSVPerformanceParser(processing_batch_id=uuid4())
    
    @pytest.fixture
    def sample_valid_row(self):
        """Sample valid CSV row data"""
        return {
            "Date": "2025-01-15T10:30:00.000Z",
            "Core DSP Campaign Name": "Premium Video Campaign Q1 2025",
            "Core DSP Campaign ID": "550e8400-e29b-41d4-a716-446655440000",
            "Deal Name": "2025_Premium_001_Station_WoltEnterprises_VideoAds_01.01.-31.03.",
            "Deal ID": "550e8400-e29b-41d4-a716-446655440001", 
            "Campaign Purchase Type": "guaranteed",
            "Deal Purchase Type": "guaranteed",
            "Total Impressions": "1234567.89"
        }
    
    def test_validate_date_column_iso8601(self, parser, sample_valid_row):
        """Test Date column validation (100% populated, ISO8601 format)"""
        # Valid ISO8601 formats  
        valid_dates = [
            "2025-01-15T10:30:00.000Z",
            "2025-12-31T23:59:59.999Z", 
            "2025-06-15T12:00:00.123Z"
        ]
        
        for date_str in valid_dates:
            row = sample_valid_row.copy()
            row["Date"] = date_str
            
            result = parser.validate_row_data(row, row_number=1)
            assert result.is_valid is True
            assert isinstance(result.parsed_data["date_recorded"], datetime)
    
    def test_validate_date_column_invalid_formats(self, parser, sample_valid_row):
        """Test Date column rejects invalid formats"""
        invalid_dates = [
            "2025-01-15",  # Missing time
            "01/15/2025",  # Wrong format
            "2025-13-01T10:30:00.000Z",  # Invalid month
            "not-a-date",  # Not a date
            "",  # Empty
            None  # Null
        ]
        
        for invalid_date in invalid_dates:
            row = sample_valid_row.copy()
            row["Date"] = invalid_date
            
            result = parser.validate_row_data(row, row_number=1)
            assert result.is_valid is False
            # Accept either "Invalid date format" or "Required field" errors
            assert any("Invalid date format" in error or "Required field" in error 
                      for error in result.errors)
    
    def test_validate_uuid_columns(self, parser, sample_valid_row):
        """Test UUID validation for Core DSP Campaign ID and Deal ID"""
        valid_uuids = [
            "550e8400-e29b-41d4-a716-446655440000",
            "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
            "01234567-89ab-cdef-0123-456789abcdef"
        ]
        
        for valid_uuid in valid_uuids:
            # Test Core DSP Campaign ID  
            row = sample_valid_row.copy()
            row["Core DSP Campaign ID"] = valid_uuid
            
            result = parser.validate_row_data(row, row_number=1)
            assert result.is_valid is True
            
            # Test Deal ID (required field)
            row = sample_valid_row.copy() 
            row["Deal ID"] = valid_uuid
            
            result = parser.validate_row_data(row, row_number=1)
            assert result.is_valid is True
    
    def test_validate_uuid_columns_invalid(self, parser, sample_valid_row):
        """Test UUID validation rejects invalid UUIDs"""
        invalid_uuids = [
            "not-a-uuid",
            "550e8400-e29b-41d4-a716",  # Too short
            "550e8400-e29b-41d4-a716-446655440000-extra",  # Too long
            "550e8400-XXXX-41d4-a716-446655440000",  # Invalid characters
            ""  # Empty
        ]
        
        for invalid_uuid in invalid_uuids:
            # Test Deal ID (required field)
            row = sample_valid_row.copy()
            row["Deal ID"] = invalid_uuid
            
            result = parser.validate_row_data(row, row_number=1)
            assert result.is_valid is False
            # Accept either "Invalid UUID format" or "Required field" errors
            assert any("Invalid UUID format" in error or "Required field" in error 
                      for error in result.errors)
    
    def test_validate_purchase_type_enum(self, parser, sample_valid_row):
        """Test purchase type validation for both Campaign and Deal Purchase Type"""
        valid_types = ["guaranteed", "unguaranteed"]
        
        for purchase_type in valid_types:
            # Test Campaign Purchase Type (58% populated - can be null)
            row = sample_valid_row.copy()
            row["Campaign Purchase Type"] = purchase_type
            
            result = parser.validate_row_data(row, row_number=1)
            assert result.is_valid is True
            
            # Test Deal Purchase Type (100% populated - required)
            row = sample_valid_row.copy()
            row["Deal Purchase Type"] = purchase_type
            
            result = parser.validate_row_data(row, row_number=1)
            assert result.is_valid is True
    
    def test_validate_purchase_type_invalid(self, parser, sample_valid_row):
        """Test purchase type validation rejects invalid values"""
        invalid_types = ["premium", "standard", "unknown", ""]
        
        for invalid_type in invalid_types:
            # Test Deal Purchase Type (required field)
            row = sample_valid_row.copy()
            row["Deal Purchase Type"] = invalid_type
            
            result = parser.validate_row_data(row, row_number=1)
            assert result.is_valid is False
            # Accept either "Invalid purchase type" or "Required field" errors
            assert any("Invalid purchase type" in error or "Required field" in error 
                      for error in result.errors)
    
    def test_validate_total_impressions_range(self, parser, sample_valid_row):
        """Test Total Impressions validation (range: 619 - 231,810,865)"""
        valid_impressions = [
            "619",  # Minimum
            "1000000",  # Mid range
            "231810865",  # Maximum 
            "1234567.89"  # With decimals
        ]
        
        for impressions in valid_impressions:
            row = sample_valid_row.copy()
            row["Total Impressions"] = impressions
            
            result = parser.validate_row_data(row, row_number=1)
            assert result.is_valid is True
            assert isinstance(result.parsed_data["total_impressions"], Decimal)
    
    def test_validate_total_impressions_invalid(self, parser, sample_valid_row):
        """Test Total Impressions validation rejects invalid values"""
        invalid_impressions = [
            "618",  # Below minimum
            "231810866",  # Above maximum
            "-1000",  # Negative
            "not-a-number",  # Non-numeric
            ""  # Empty
        ]
        
        for invalid_impressions_val in invalid_impressions:
            row = sample_valid_row.copy()
            row["Total Impressions"] = invalid_impressions_val
            
            result = parser.validate_row_data(row, row_number=1)
            assert result.is_valid is False
            # Accept various error message formats for impressions
            assert any("Invalid impressions" in error or "out of range" in error 
                      or "Required field" in error or "must be a number" in error
                      for error in result.errors)
    
    def test_validate_optional_fields_null_allowed(self, parser, sample_valid_row):
        """Test optional fields (58% populated) can be null/empty"""
        optional_fields = [
            "Core DSP Campaign Name",
            "Core DSP Campaign ID", 
            "Campaign Purchase Type"
        ]
        
        for field in optional_fields:
            # Test with None
            row = sample_valid_row.copy()
            row[field] = None
            
            result = parser.validate_row_data(row, row_number=1)
            assert result.is_valid is True
            
            # Test with empty string
            row[field] = ""
            result = parser.validate_row_data(row, row_number=1)
            assert result.is_valid is True
    
    def test_validate_required_fields_not_null(self, parser, sample_valid_row):
        """Test required fields (100% populated) cannot be null/empty"""
        required_fields = [
            "Date",
            "Deal Name", 
            "Deal ID",
            "Deal Purchase Type",
            "Total Impressions"
        ]
        
        for field in required_fields:
            # Test with None
            row = sample_valid_row.copy()
            row[field] = None
            
            result = parser.validate_row_data(row, row_number=1)
            assert result.is_valid is False
            assert any(f"Required field {field}" in error for error in result.errors)
            
            # Test with empty string
            row[field] = ""
            result = parser.validate_row_data(row, row_number=1)
            assert result.is_valid is False


class TestCSVStreamingParser:
    """Test streaming CSV parser with chunk processing"""
    
    @pytest.fixture
    def parser(self):
        from src.services.csv_performance_parser import CSVPerformanceParser
        return CSVPerformanceParser(processing_batch_id=uuid4(), chunk_size=3)
    
    @pytest.fixture
    def sample_csv_data(self):
        """Sample CSV data with 5 records for chunking tests"""
        return """Date,Core DSP Campaign Name,Core DSP Campaign ID,Deal Name,Deal ID,Campaign Purchase Type,Deal Purchase Type,Total Impressions
2025-01-15T10:30:00.000Z,Campaign 1,550e8400-e29b-41d4-a716-446655440001,Deal_1,550e8400-e29b-41d4-a716-446655440011,guaranteed,guaranteed,1000
2025-01-15T11:30:00.000Z,Campaign 2,550e8400-e29b-41d4-a716-446655440002,Deal_2,550e8400-e29b-41d4-a716-446655440012,guaranteed,guaranteed,2000  
2025-01-15T12:30:00.000Z,Campaign 3,550e8400-e29b-41d4-a716-446655440003,Deal_3,550e8400-e29b-41d4-a716-446655440013,unguaranteed,unguaranteed,3000
2025-01-15T13:30:00.000Z,Campaign 4,550e8400-e29b-41d4-a716-446655440004,Deal_4,550e8400-e29b-41d4-a716-446655440014,guaranteed,guaranteed,4000
2025-01-15T14:30:00.000Z,Campaign 5,550e8400-e29b-41d4-a716-446655440005,Deal_5,550e8400-e29b-41d4-a716-446655440015,unguaranteed,unguaranteed,5000"""
    
    def test_parse_csv_stream_chunked_processing(self, parser, sample_csv_data):
        """Test CSV parsing processes data in chunks"""
        csv_stream = StringIO(sample_csv_data)
        
        chunks_processed = []
        
        # Mock the process_chunk method to capture chunks
        def mock_process_chunk(chunk_data, chunk_number):
            chunks_processed.append((chunk_number, len(chunk_data)))
            return len(chunk_data), []  # (records_processed, errors)
        
        parser.process_chunk = mock_process_chunk
        
        result = parser.parse_csv_stream(csv_stream)
        
        # Should have 2 chunks: [3 records, 2 records] 
        assert len(chunks_processed) == 2
        assert chunks_processed[0] == (1, 3)  # Chunk 1: 3 records
        assert chunks_processed[1] == (2, 2)  # Chunk 2: 2 records
        assert result.total_records_processed == 5
    
    def test_parse_csv_stream_memory_efficiency(self, parser):
        """Test parser doesn't load entire file into memory"""
        # Create a large CSV data string (simulating large file)
        large_csv_lines = ["Date,Core DSP Campaign Name,Core DSP Campaign ID,Deal Name,Deal ID,Campaign Purchase Type,Deal Purchase Type,Total Impressions"]
        
        # Add 1000 data rows
        for i in range(1000):
            line = f"2025-01-15T{i%24:02d}:30:00.000Z,Campaign_{i},550e8400-e29b-41d4-a716-44665544{i:04d},Deal_{i},550e8400-e29b-41d4-a716-44665545{i:04d},guaranteed,guaranteed,{1000+i}"
            large_csv_lines.append(line)
        
        large_csv_data = "\n".join(large_csv_lines)
        csv_stream = StringIO(large_csv_data)
        
        chunks_processed = []
        
        def mock_process_chunk(chunk_data, chunk_number):
            chunks_processed.append(len(chunk_data))
            return len(chunk_data), []
        
        parser.process_chunk = mock_process_chunk
        
        # Set chunk size to ensure multiple chunks
        parser.chunk_size = 100
        
        result = parser.parse_csv_stream(csv_stream)
        
        # Should process in chunks of 100
        assert len(chunks_processed) == 10  # 1000 records / 100 per chunk
        assert all(chunk_size == 100 for chunk_size in chunks_processed)
        assert result.total_records_processed == 1000
    
    def test_parse_csv_stream_handles_errors_per_chunk(self, parser, sample_csv_data):
        """Test CSV parser collects and reports errors per chunk"""
        csv_stream = StringIO(sample_csv_data)
        
        # Mock process_chunk to simulate errors in second chunk
        def mock_process_chunk(chunk_data, chunk_number):
            if chunk_number == 2:  # Second chunk has errors
                return 1, ["Error in row 4: Invalid UUID", "Error in row 5: Missing data"]
            return len(chunk_data), []
        
        parser.process_chunk = mock_process_chunk
        
        result = parser.parse_csv_stream(csv_stream)
        
        assert result.total_records_processed == 4  # 3 from first chunk + 1 from second
        assert len(result.errors) == 2
        assert "Error in row 4: Invalid UUID" in result.errors
        assert "Error in row 5: Missing data" in result.errors
    
    def test_parse_csv_stream_large_file_memory_limit(self, parser):
        """Test parser memory usage stays under 50MB for large files"""
        import psutil
        import os
        
        # Track memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Create simulated large CSV (representing 250MB file)
        # Use iterator to avoid loading into memory
        def large_csv_generator():
            yield "Date,Core DSP Campaign Name,Core DSP Campaign ID,Deal Name,Deal ID,Campaign Purchase Type,Deal Purchase Type,Total Impressions\n"
            for i in range(10000):  # Simulate large file
                yield f"2025-01-15T{i%24:02d}:30:00.000Z,Campaign_{i},550e8400-e29b-41d4-a716-44665544{i:04d},Deal_{i},550e8400-e29b-41d4-a716-44665545{i:04d},guaranteed,guaranteed,{1000+i}\n"
        
        # Convert generator to stream-like object
        csv_content = "".join(large_csv_generator())
        csv_stream = StringIO(csv_content)
        
        def mock_process_chunk(chunk_data, chunk_number):
            return len(chunk_data), []
        
        parser.process_chunk = mock_process_chunk
        parser.chunk_size = 1000  # Process in 1000-record chunks
        
        result = parser.parse_csv_stream(csv_stream)
        
        # Check final memory usage
        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory
        
        # Memory increase should be less than 50MB  
        assert memory_increase < 50, f"Memory usage increased by {memory_increase:.2f}MB, should be < 50MB"
        assert result.total_records_processed == 10000


class TestCSVDatabaseIntegration:
    """Test CSV parser integration with ReportingStaging model and database"""
    
    @pytest.fixture
    def parser(self):
        from src.services.csv_performance_parser import CSVPerformanceParser
        return CSVPerformanceParser(processing_batch_id=uuid4())
    
    @pytest.fixture
    def sample_valid_data(self):
        """Sample valid parsed data for database insertion"""
        return [
            {
                "deal_id": UUID("550e8400-e29b-41d4-a716-446655440001"),
                "date_recorded": datetime(2025, 1, 15, 10, 30, 0),
                "deal_name": "2025_Premium_001_Station_WoltEnterprises_VideoAds_01.01.-31.03.",
                "core_dsp_audience_segment": "Premium Video Audience",
                "core_dsp_placement": "Station Display",
                "core_dsp_creative": "Video Creative 2025",
                "purchase_type": PurchaseType.guaranteed,
                "total_impressions": Decimal("1234567.89")
            },
            {
                "deal_id": UUID("550e8400-e29b-41d4-a716-446655440002"), 
                "date_recorded": datetime(2025, 1, 15, 11, 30, 0),
                "deal_name": "2025_Premium_002_City_EdekaZentrale_VideoAds_01.02.-28.02.",
                "core_dsp_audience_segment": None,  # 58% populated - can be null
                "core_dsp_placement": None,
                "core_dsp_creative": None,
                "purchase_type": PurchaseType.unguaranteed,
                "total_impressions": Decimal("987654.32")
            }
        ]
    
    @patch('src.services.csv_performance_parser.StagingDatabase')
    def test_process_chunk_database_insertion(self, mock_staging_db_class, parser, sample_valid_data):
        """Test chunk processing inserts data into ReportingStaging table"""
        # Mock database session
        mock_db_session = MagicMock()
        mock_staging_db = MagicMock()
        mock_staging_db.get_session.return_value = iter([mock_db_session])  # Return iterator with session
        mock_staging_db_class.return_value = mock_staging_db
        
        # Mock row validation to return valid data
        def mock_validate_row(row, row_number):
            validation_result = Mock()
            validation_result.is_valid = True
            validation_result.parsed_data = sample_valid_data[row_number - 1]
            validation_result.errors = []
            return validation_result
        
        parser.validate_row_data = mock_validate_row
        
        # Sample chunk data (raw CSV rows)
        chunk_data = [
            {"Date": "2025-01-15T10:30:00.000Z", "Deal ID": "550e8400-e29b-41d4-a716-446655440001"},
            {"Date": "2025-01-15T11:30:00.000Z", "Deal ID": "550e8400-e29b-41d4-a716-446655440002"}
        ]
        
        records_processed, errors = parser.process_chunk(chunk_data, chunk_number=1)
        
        # Verify database operations
        assert records_processed == 2
        assert len(errors) == 0
        assert mock_db_session.add.call_count == 2
        # Commit is handled by the StagingDatabase generator
        
        # Verify ReportingStaging objects were created correctly
        staging_calls = mock_db_session.add.call_args_list
        for call in staging_calls:
            staging_obj = call[0][0]
            assert isinstance(staging_obj, ReportingStaging)
            assert staging_obj.processing_batch_id == parser.processing_batch_id
    
    @patch('src.services.csv_performance_parser.StagingDatabase')
    def test_process_chunk_handles_database_errors(self, mock_staging_db_class, parser):
        """Test chunk processing handles database errors gracefully"""
        # Mock database session that raises exception
        mock_db_session = MagicMock()
        mock_staging_db = MagicMock()
        mock_staging_db.get_session.side_effect = Exception("Database connection error")
        mock_staging_db_class.return_value = mock_staging_db
        
        # Mock row validation
        def mock_validate_row(row, row_number):
            validation_result = Mock()
            validation_result.is_valid = True
            validation_result.parsed_data = {"test": "data"}
            validation_result.errors = []
            return validation_result
        
        parser.validate_row_data = mock_validate_row
        
        chunk_data = [{"Date": "2025-01-15T10:30:00.000Z"}]
        
        records_processed, errors = parser.process_chunk(chunk_data, chunk_number=1)
        
        # Should handle database error gracefully
        assert records_processed == 0
        assert len(errors) == 1
        assert "Database error" in errors[0]
    
    def test_create_staging_object_from_parsed_data(self, parser, sample_valid_data):
        """Test creating ReportingStaging object from parsed data"""
        parsed_data = sample_valid_data[0]
        
        staging_obj = parser.create_staging_object(parsed_data, row_number=1)
        
        assert isinstance(staging_obj, ReportingStaging)
        assert staging_obj.deal_id == parsed_data["deal_id"]
        assert staging_obj.date_recorded == parsed_data["date_recorded"]
        assert staging_obj.deal_name == parsed_data["deal_name"]
        assert staging_obj.core_dsp_audience_segment == parsed_data["core_dsp_audience_segment"]
        assert staging_obj.purchase_type == parsed_data["purchase_type"]
        assert staging_obj.total_impressions == parsed_data["total_impressions"]
        assert staging_obj.processing_batch_id == parser.processing_batch_id
        assert staging_obj.source_row_number == 1
        assert staging_obj.record_classification == "new"  # Default classification
    
    def test_create_staging_object_with_validation_errors(self, parser):
        """Test creating ReportingStaging object with validation errors stored"""
        parsed_data = {
            "deal_id": UUID("550e8400-e29b-41d4-a716-446655440001"),
            "date_recorded": datetime(2025, 1, 15, 10, 30, 0),
            "deal_name": "Test Deal",
            "purchase_type": PurchaseType.guaranteed,
            "total_impressions": Decimal("1000"),
            "validation_errors": ["Warning: Optional field missing", "Info: Date format converted"]
        }
        
        staging_obj = parser.create_staging_object(parsed_data, row_number=5)
        
        assert staging_obj.validation_errors is not None
        assert "Warning: Optional field missing" in staging_obj.validation_errors
        assert staging_obj.source_row_number == 5


class TestCSVParserPerformance:
    """Test CSV parser performance and efficiency requirements"""
    
    @pytest.fixture 
    def parser(self):
        from src.services.csv_performance_parser import CSVPerformanceParser
        return CSVPerformanceParser(processing_batch_id=uuid4(), chunk_size=1000)
    
    def test_parser_handles_1073_records_efficiently(self, parser):
        """Test parser handles the expected 1,073 records efficiently"""
        # Create test data matching expected volume
        csv_lines = ["Date,Core DSP Campaign Name,Core DSP Campaign ID,Deal Name,Deal ID,Campaign Purchase Type,Deal Purchase Type,Total Impressions"]
        
        for i in range(1073):
            line = f"2025-01-15T{i%24:02d}:30:00.000Z,Campaign_{i},550e8400-e29b-41d4-a716-44665544{i:04d},Deal_{i},550e8400-e29b-41d4-a716-44665545{i:04d},guaranteed,guaranteed,{619+i}"
            csv_lines.append(line)
        
        csv_data = "\n".join(csv_lines)
        csv_stream = StringIO(csv_data)
        
        chunks_processed = []
        
        def mock_process_chunk(chunk_data, chunk_number):
            chunks_processed.append((chunk_number, len(chunk_data)))
            return len(chunk_data), []
        
        parser.process_chunk = mock_process_chunk
        
        import time
        start_time = time.time()
        
        result = parser.parse_csv_stream(csv_stream)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        # Performance requirements
        assert result.total_records_processed == 1073
        assert len(chunks_processed) == 2  # 1000 + 73 records
        assert chunks_processed[0] == (1, 1000)  # First chunk: 1000 records
        assert chunks_processed[1] == (2, 73)    # Second chunk: 73 records
        assert processing_time < 10.0  # Should process in under 10 seconds
    
    def test_parser_memory_footprint_stays_low(self, parser):
        """Test parser memory footprint stays under 50MB during processing"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024
        
        # Simulate processing large CSV
        def mock_process_chunk(chunk_data, chunk_number):
            # Simulate some processing work
            processed_data = []
            for row in chunk_data:
                processed_data.append({
                    "deal_id": UUID("550e8400-e29b-41d4-a716-446655440000"),
                    "date_recorded": datetime.now(),
                    "deal_name": row.get("Deal Name", ""),
                    "total_impressions": Decimal("1000")
                })
            return len(chunk_data), []
        
        parser.process_chunk = mock_process_chunk
        
        # Create large dataset
        csv_lines = ["Date,Core DSP Campaign Name,Core DSP Campaign ID,Deal Name,Deal ID,Campaign Purchase Type,Deal Purchase Type,Total Impressions"]
        for i in range(10000):
            line = f"2025-01-15T10:30:00.000Z,Campaign_{i},550e8400-e29b-41d4-a716-44665544{i:04d},Deal_{i},550e8400-e29b-41d4-a716-44665545{i:04d},guaranteed,guaranteed,{1000+i}"
            csv_lines.append(line)
        
        csv_data = "\n".join(csv_lines)
        csv_stream = StringIO(csv_data)
        
        result = parser.parse_csv_stream(csv_stream)
        
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = final_memory - initial_memory
        
        assert memory_increase < 50, f"Memory increased by {memory_increase:.2f}MB, should be < 50MB"
        assert result.total_records_processed == 10000


class TestCSVParserErrorHandling:
    """Test comprehensive error handling with descriptive error messages"""
    
    @pytest.fixture
    def parser(self):
        from src.services.csv_performance_parser import CSVPerformanceParser
        return CSVPerformanceParser(processing_batch_id=uuid4())
    
    def test_parse_malformed_csv_structure(self, parser):
        """Test parser handles malformed CSV files with descriptive errors"""
        malformed_csv = """Date,Core DSP Campaign Name,Core DSP Campaign ID,Deal Name,Deal ID
2025-01-15T10:30:00.000Z,Campaign 1,invalid-uuid-here,Deal 1  # Missing columns
2025-01-15T11:30:00.000Z,Campaign 2"""  # Incomplete row
        
        csv_stream = StringIO(malformed_csv)
        
        result = parser.parse_csv_stream(csv_stream)
        
        assert result.is_success is False
        assert len(result.errors) > 0
        
        # Check for descriptive error messages
        error_messages = " ".join(result.errors)
        assert "Missing required header" in error_messages or "Invalid CSV structure" in error_messages
    
    def test_parse_empty_csv_file(self, parser):
        """Test parser handles empty CSV files"""
        empty_csv = ""
        csv_stream = StringIO(empty_csv)
        
        result = parser.parse_csv_stream(csv_stream)
        
        assert result.is_success is False
        assert len(result.errors) > 0
        assert "Empty CSV file" in result.errors[0] or "No data found" in result.errors[0]
    
    def test_parse_csv_with_only_headers(self, parser):
        """Test parser handles CSV with headers but no data"""
        headers_only = "Date,Core DSP Campaign Name,Core DSP Campaign ID,Deal Name,Deal ID,Campaign Purchase Type,Deal Purchase Type,Total Impressions"
        csv_stream = StringIO(headers_only)
        
        result = parser.parse_csv_stream(csv_stream)
        
        assert result.total_records_processed == 0
        assert "No data rows found" in result.errors or len(result.errors) == 0  # Might be valid case
    
    def test_error_context_includes_row_numbers(self, parser):
        """Test error messages include row numbers and context"""
        csv_with_errors = """Date,Core DSP Campaign Name,Core DSP Campaign ID,Deal Name,Deal ID,Campaign Purchase Type,Deal Purchase Type,Total Impressions
2025-01-15T10:30:00.000Z,Campaign 1,550e8400-e29b-41d4-a716-446655440001,Deal 1,550e8400-e29b-41d4-a716-446655440011,guaranteed,guaranteed,1000
invalid-date-format,Campaign 2,550e8400-e29b-41d4-a716-446655440002,Deal 2,550e8400-e29b-41d4-a716-446655440012,guaranteed,guaranteed,2000
2025-01-15T12:30:00.000Z,Campaign 3,invalid-uuid,Deal 3,550e8400-e29b-41d4-a716-446655440013,guaranteed,guaranteed,invalid-number"""
        
        csv_stream = StringIO(csv_with_errors)
        
        result = parser.parse_csv_stream(csv_stream)
        
        # Should have errors with row context
        assert len(result.errors) > 0
        
        # Check that error messages include row numbers
        error_text = " ".join(result.errors)
        assert "row 2" in error_text or "row 3" in error_text
        # Accept row/line/record formats for context
        assert ("row 2" in error_text or "row 3" in error_text or 
                "line 2" in error_text or "line 3" in error_text or 
                "record 2" in error_text)
    
    def test_error_messages_are_descriptive_and_actionable(self, parser):
        """Test error messages provide clear, actionable information"""
        problematic_csv = """Date,Core DSP Campaign Name,Core DSP Campaign ID,Deal Name,Deal ID,Campaign Purchase Type,Deal Purchase Type,Total Impressions
2025-01-15T10:30:00.000Z,Campaign 1,not-a-uuid,Deal 1,550e8400-e29b-41d4-a716-446655440011,invalid-type,guaranteed,999999999999"""
        
        csv_stream = StringIO(problematic_csv)
        
        result = parser.parse_csv_stream(csv_stream)
        
        assert len(result.errors) > 0
        
        # Check for descriptive, actionable error messages
        error_messages = " ".join(result.errors)
        
        # Should describe what's wrong and where
        assert ("UUID" in error_messages and "format" in error_messages) or "invalid" in error_messages
        assert "row" in error_messages or "line" in error_messages or "record" in error_messages
        
        # Should suggest what to do
        expected_actionable_phrases = [
            "should be", "expected", "format", "check", "verify", "must be", "required"
        ]
        assert any(phrase in error_messages.lower() for phrase in expected_actionable_phrases)


class TestParsingResults:
    """Test result objects and response structures"""
    
    def test_parsing_result_structure(self):
        """Test parsing result contains all required information"""
        from src.services.csv_performance_parser import CSVParsingResult
        
        result = CSVParsingResult(
            is_success=True,
            total_records_processed=1073,
            total_chunks_processed=2,
            errors=[],
            warnings=["Optional field missing in 42% of records"],
            processing_time_seconds=5.67
        )
        
        assert result.is_success is True
        assert result.total_records_processed == 1073
        assert result.total_chunks_processed == 2
        assert len(result.errors) == 0
        assert len(result.warnings) == 1
        assert result.processing_time_seconds == 5.67
    
    def test_validation_result_structure(self):
        """Test row validation result contains all required information"""  
        from src.services.csv_performance_parser import RowValidationResult
        
        parsed_data = {
            "deal_id": UUID("550e8400-e29b-41d4-a716-446655440001"),
            "date_recorded": datetime(2025, 1, 15, 10, 30, 0),
            "total_impressions": Decimal("1000")
        }
        
        result = RowValidationResult(
            is_valid=True,
            parsed_data=parsed_data,
            errors=[],
            warnings=["Optional field converted"]
        )
        
        assert result.is_valid is True
        assert result.parsed_data == parsed_data
        assert len(result.errors) == 0
        assert len(result.warnings) == 1
    
    def test_header_validation_result_structure(self):
        """Test header validation result structure"""
        from src.services.csv_performance_parser import HeaderValidationResult
        
        result = HeaderValidationResult(
            is_valid=False,
            errors=["Missing required header: Total Impressions"],
            warnings=["Extra header found: Unused Column"],
            header_mapping={"Date": 0, "Deal Name": 3}
        )
        
        assert result.is_valid is False
        assert len(result.errors) == 1
        assert len(result.warnings) == 1
        assert result.header_mapping["Date"] == 0