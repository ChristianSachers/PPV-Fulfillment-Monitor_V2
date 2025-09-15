"""Test suite for XLSX Campaign Parser with memory efficiency validation.

This test suite follows TDD principles and validates:
- Parsing of 7 columns according to campaignXLSXstructure.md
- German date format parsing (DD.MM.YYYY-DD.MM.YYYY)
- UUID validation and format compliance
- Null value handling for Budget field (8.7% rate)
- Streaming processing with 1000-record chunks
- Memory efficiency for large files (<100MB usage)
- Integration with CampaignsStaging model
- Error handling with descriptive messages
- Large file processing (7,057 records)
"""

import pytest
from unittest.mock import Mock, patch, mock_open
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4
from io import BytesIO
import tempfile
import os
from typing import List, Dict, Any, Optional

# Import the service we're testing 
from src.services.xlsx_campaign_parser import XLSXCampaignParser, XLSXParsingError
from src.models.staging import CampaignsStaging, CampaignStagingRequest


@pytest.fixture
def parser():
    """Create parser instance for testing."""
    return XLSXCampaignParser()


@pytest.fixture
def sample_xlsx_data():
    """Sample XLSX data matching campaignXLSXstructure.md format."""
    return [
        # Header row
        ["Deal/Campaign name", "Runtime", "Impression goal", "Budget €", "CPM €", "Deal/Campaign ID", "Buyer"],
        # Sample data rows
        [
            "2025_11573_0006_3_Infoscreen_Sierra Germany GmbH_PPV Sonae Sierra PV Berlin_04-06.09._",
            "04.09.2025-06.09.2025",
            720000,
            5464.8,
            7.59,
            "089552b0-a53c-41a7-8299-c499310af484",
            "WEISCHER_JVB_GMBH < Displayce_rtb (Seat 4227)"
        ],
        [
            "2025_11574_0007_3_Digital_Test Client_Campaign Two_07-09.09._",
            "07.09.2025-09.09.2025",
            15000,
            None,  # 8.7% null rate for budget
            2.50,
            "189552b0-a53c-41a7-8299-c499310af485",
            "TEST_BUYER_AGENCY < Platform_rtb (Seat 1234)"
        ]
    ]


@pytest.fixture
def large_xlsx_data():
    """Generate large dataset for memory efficiency testing."""
    header = ["Deal/Campaign name", "Runtime", "Impression goal", "Budget €", "CPM €", "Deal/Campaign ID", "Buyer"]
    data = [header]
    
    # Generate 7,057 records as per specification
    for i in range(7057):
        # Simulate 8.7% null rate for budget
        budget = None if i % 12 == 0 else round(1000 + (i * 0.5), 2)
        
        data.append([
            f"2025_{11000+i}_0006_3_Infoscreen_Client_{i}_Campaign_{i}_04-06.09._",
            "04.09.2025-06.09.2025",
            3000 + (i * 100),  # Range 3,000-720,000
            budget,
            round(1.0 + (i * 0.01), 2),  # CPM range €0.01-€45.00
            str(uuid4()),
            f"BUYER_{i % 68}_AGENCY < Platform_rtb (Seat {1000+i})"
        ])
    
    return data


class TestXLSXCampaignParser:
    """Test suite for XLSXCampaignParser class."""
    pass


class TestColumnParsing:
    """Test parsing of individual columns according to specification."""
    
    def test_deal_campaign_name_parsing(self, parser):
        """Test parsing of Deal/Campaign name column (VARCHAR(500), 100% populated)."""
        test_name = "2025_11573_0006_3_Infoscreen_Sierra Germany GmbH_PPV Sonae Sierra PV Berlin_04-06.09._"
        
        # This should not raise an exception
        parsed_data = parser.parse_campaign_name(test_name)
        assert parsed_data == test_name
        assert len(parsed_data) <= 500
        
        # Test empty name (should raise error)
        with pytest.raises(XLSXParsingError, match="Deal/Campaign name cannot be empty"):
            parser.parse_campaign_name("")
        
        # Test too long name (should raise error)
        long_name = "x" * 501
        with pytest.raises(XLSXParsingError, match="Deal/Campaign name exceeds 500 characters"):
            parser.parse_campaign_name(long_name)
    
    def test_runtime_parsing(self, parser):
        """Test parsing of Runtime column (German date format DD.MM.YYYY-DD.MM.YYYY)."""
        runtime_str = "04.09.2025-06.09.2025"
        
        start_date, end_date = parser.parse_runtime(runtime_str)
        
        assert isinstance(start_date, datetime)
        assert isinstance(end_date, datetime)
        assert start_date == datetime(2025, 9, 4)
        assert end_date == datetime(2025, 9, 6)
        assert start_date < end_date
        
        # Test invalid formats
        invalid_formats = [
            "2025-09-04-2025-09-06",  # Wrong format
            "04.09.2025",  # Missing end date
            "04/09/2025-06/09/2025",  # Wrong separator
            "32.13.2025-06.09.2025",  # Invalid date
            "06.09.2025-04.09.2025",  # End before start
        ]
        
        for invalid_runtime in invalid_formats:
            with pytest.raises(XLSXParsingError, match="Invalid runtime format"):
                parser.parse_runtime(invalid_runtime)
    
    def test_impression_goal_parsing(self, parser):
        """Test parsing of Impression goal column (INTEGER, range 3,000-720,000)."""
        # Valid ranges
        valid_goals = [3000, 15000, 720000, 500000]
        for goal in valid_goals:
            parsed_goal = parser.parse_impression_goal(goal)
            assert isinstance(parsed_goal, int)
            assert parsed_goal == goal
        
        # String conversion
        assert parser.parse_impression_goal("15000") == 15000
        assert parser.parse_impression_goal("720000") == 720000
        
        # Invalid values
        invalid_goals = [2999, 720001, -1000, 0, "invalid", None]
        for invalid_goal in invalid_goals:
            with pytest.raises(XLSXParsingError, match="Invalid impression goal"):
                parser.parse_impression_goal(invalid_goal)
    
    def test_budget_parsing(self, parser):
        """Test parsing of Budget column (DECIMAL(12,2), 8.7% null rate, nullable)."""
        # Valid budgets
        valid_budgets = [0.15, 5464.8, 1000.00, 999.99]
        for budget in valid_budgets:
            parsed_budget = parser.parse_budget(budget)
            assert isinstance(parsed_budget, Decimal)
            assert parsed_budget == Decimal(str(budget))
        
        # String conversion
        assert parser.parse_budget("5464.8") == Decimal("5464.8")
        
        # Null handling (should be allowed)
        assert parser.parse_budget(None) is None
        assert parser.parse_budget("") is None
        
        # Invalid values
        invalid_budgets = [-0.01, "invalid", 99999999999.99]  # Negative, invalid string, too large
        for invalid_budget in invalid_budgets:
            with pytest.raises(XLSXParsingError, match="Invalid budget"):
                parser.parse_budget(invalid_budget)
    
    def test_cpm_parsing(self, parser):
        """Test parsing of CPM column (DECIMAL(8,2), range €0.01-€45.00, 100% populated)."""
        # Valid CPM values
        valid_cpms = [0.01, 7.59, 45.00, 25.50]
        for cpm in valid_cpms:
            parsed_cpm = parser.parse_cpm(cpm)
            assert isinstance(parsed_cpm, Decimal)
            assert parsed_cpm == Decimal(str(cpm))
        
        # String conversion
        assert parser.parse_cpm("7.59") == Decimal("7.59")
        
        # Invalid values
        invalid_cpms = [0.00, 45.01, -1.00, None, "invalid"]
        for invalid_cpm in invalid_cpms:
            with pytest.raises(XLSXParsingError, match="Invalid CPM"):
                parser.parse_cpm(invalid_cpm)
    
    def test_deal_id_parsing(self, parser):
        """Test parsing of Deal/Campaign ID column (UUID format, 100% unique)."""
        valid_uuid = "089552b0-a53c-41a7-8299-c499310af484"
        parsed_uuid = parser.parse_deal_id(valid_uuid)
        
        assert isinstance(parsed_uuid, UUID)
        assert str(parsed_uuid) == valid_uuid
        
        # Test UUID object input
        uuid_obj = UUID(valid_uuid)
        assert parser.parse_deal_id(uuid_obj) == uuid_obj
        
        # Invalid UUIDs
        invalid_uuids = [
            "invalid-uuid",
            "089552b0-a53c-41a7-8299",  # Too short
            "089552b0-a53c-41a7-8299-c499310af484-extra",  # Too long
            None,
            "",
            123456
        ]
        
        for invalid_uuid in invalid_uuids:
            with pytest.raises(XLSXParsingError, match="Invalid Deal UUID format"):
                parser.parse_deal_id(invalid_uuid)
    
    def test_buyer_parsing(self, parser):
        """Test parsing of Buyer column (VARCHAR(100), 100% populated)."""
        valid_buyer = "WEISCHER_JVB_GMBH < Displayce_rtb (Seat 4227)"
        parsed_buyer = parser.parse_buyer(valid_buyer)
        
        assert parsed_buyer == valid_buyer
        assert len(parsed_buyer) <= 100
        
        # Test edge cases
        assert parser.parse_buyer("Not set") == "Not set"
        
        # Invalid buyers
        with pytest.raises(XLSXParsingError, match="Buyer cannot be empty"):
            parser.parse_buyer("")
        
        with pytest.raises(XLSXParsingError, match="Buyer name exceeds 100 characters"):
            parser.parse_buyer("x" * 101)
        
        with pytest.raises(XLSXParsingError, match="Buyer cannot be empty"):
            parser.parse_buyer(None)


class TestStreamingProcessing:
    """Test streaming processing and memory efficiency."""
    
    @patch('openpyxl.load_workbook')
    def test_chunk_processing(self, mock_load_workbook, parser, sample_xlsx_data):
        """Test processing data in 1000-record chunks."""
        # Mock Excel workbook
        mock_ws = Mock()
        mock_ws.iter_rows.return_value = [
            [Mock(value=cell) for cell in row] for row in sample_xlsx_data
        ]
        mock_workbook = Mock()
        mock_workbook.active = mock_ws
        mock_load_workbook.return_value = mock_workbook
        
        # Mock database operations
        with patch.object(parser, '_save_chunk_to_database') as mock_save:
            results = list(parser.parse_file_streaming("test.xlsx", chunk_size=1000))
            
            # Should process in chunks
            assert len(results) > 0
            mock_save.assert_called()
    
    @patch('openpyxl.load_workbook')
    def test_memory_efficient_loading(self, mock_load_workbook, parser):
        """Test that workbook is opened in read-only mode for memory efficiency."""
        mock_workbook = Mock()
        mock_load_workbook.return_value = mock_workbook
        
        parser.parse_file_streaming("test.xlsx")
        
        # Verify read-only mode is used
        mock_load_workbook.assert_called_with("test.xlsx", read_only=True)
    
    def test_large_file_processing(self, parser, large_xlsx_data):
        """Test processing of large files (7,057 records) with memory monitoring."""
        import psutil
        import os
        
        # Create temporary XLSX file with large dataset
        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp_file:
            # Mock the file content - in real implementation would use openpyxl to write
            tmp_file_path = tmp_file.name
        
        try:
            # Monitor memory usage during processing
            process = psutil.Process(os.getpid())
            initial_memory = process.memory_info().rss / 1024 / 1024  # MB
            
            with patch('openpyxl.load_workbook') as mock_load_workbook:
                # Mock large dataset
                mock_ws = Mock()
                mock_ws.iter_rows.return_value = [
                    [Mock(value=cell) for cell in row] for row in large_xlsx_data
                ]
                mock_workbook = Mock()
                mock_workbook.active = mock_ws
                mock_load_workbook.return_value = mock_workbook
                
                # Process file
                with patch.object(parser, '_save_chunk_to_database'):
                    results = list(parser.parse_file_streaming(tmp_file_path, chunk_size=1000))
                
                # Check memory usage
                peak_memory = process.memory_info().rss / 1024 / 1024  # MB
                memory_increase = peak_memory - initial_memory
                
                # Memory increase should be less than 100MB
                assert memory_increase < 100, f"Memory usage exceeded limit: {memory_increase}MB"
                
                # Should process all records
                assert len(results) > 0
        
        finally:
            os.unlink(tmp_file_path)


class TestDatabaseIntegration:
    """Test integration with CampaignsStaging model."""
    
    def test_staging_model_integration(self, parser, sample_xlsx_data):
        """Test that parsed data integrates correctly with CampaignsStaging model."""
        # Parse sample row
        row_data = sample_xlsx_data[1]  # First data row
        
        parsed_record = parser.parse_row(row_data, row_number=2)
        
        # Verify all required fields are present
        required_fields = [
            'deal_campaign_name', 'start_date', 'end_date', 'impression_goal',
            'budget_eur', 'cpm_eur', 'deal_campaign_id', 'buyer'
        ]
        
        for field in required_fields:
            assert field in parsed_record
        
        # Test CampaignStagingRequest validation
        staging_request = CampaignStagingRequest(
            deal_campaign_name=parsed_record['deal_campaign_name'],
            runtime=parsed_record['runtime'],
            impression_goal=parsed_record['impression_goal'],
            budget_eur=parsed_record['budget_eur'],
            cpm_eur=parsed_record['cpm_eur'],
            buyer=parsed_record['buyer']
        )
        
        assert staging_request.deal_campaign_name == row_data[0]
        assert staging_request.start_date == datetime(2025, 9, 4)
        assert staging_request.end_date == datetime(2025, 9, 6)
    
    def test_batch_processing_metadata(self, parser):
        """Test that batch processing metadata is correctly generated."""
        batch_id = parser.generate_batch_id()
        
        assert isinstance(batch_id, UUID)
        
        # Test metadata assignment
        metadata = parser.create_processing_metadata(batch_id, "valid", 1)
        
        assert metadata['processing_batch_id'] == batch_id
        assert metadata['record_classification'] == "valid"
        assert metadata['source_row_number'] == 1


class TestErrorHandling:
    """Test comprehensive error handling with descriptive messages."""
    
    def test_file_not_found_error(self, parser):
        """Test handling of missing files."""
        with pytest.raises(XLSXParsingError, match="File not found"):
            parser.parse_file_streaming("nonexistent.xlsx")
    
    def test_invalid_file_format_error(self, parser):
        """Test handling of non-XLSX files."""
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as tmp_file:
            tmp_file.write(b"This is not an Excel file")
            tmp_file_path = tmp_file.name
        
        try:
            with pytest.raises(XLSXParsingError, match="Invalid XLSX file format"):
                parser.parse_file_streaming(tmp_file_path)
        finally:
            os.unlink(tmp_file_path)
    
    def test_header_validation_error(self, parser):
        """Test validation of expected column headers."""
        invalid_headers = [
            ["Wrong", "Header", "Names", "Here", "Invalid", "Headers", "Test"]
        ]
        
        with patch('openpyxl.load_workbook') as mock_load_workbook:
            mock_ws = Mock()
            mock_ws.iter_rows.return_value = [
                [Mock(value=cell) for cell in row] for row in invalid_headers
            ]
            mock_workbook = Mock()
            mock_workbook.active = mock_ws
            mock_load_workbook.return_value = mock_workbook
            
            with pytest.raises(XLSXParsingError, match="Invalid XLSX structure"):
                list(parser.parse_file_streaming("test.xlsx"))
    
    def test_row_level_error_handling(self, parser):
        """Test handling of individual row parsing errors with context."""
        invalid_row_data = [
            ["Valid Campaign Name", "invalid-date-format", "not-a-number", "invalid-budget", "invalid-cpm", "invalid-uuid", ""]
        ]
        
        with pytest.raises(XLSXParsingError) as exc_info:
            parser.parse_row(invalid_row_data[0], row_number=2)
        
        # Error should include row number and context
        assert "row 2" in str(exc_info.value)
    
    def test_validation_error_aggregation(self, parser):
        """Test that validation errors are properly aggregated for batch processing."""
        # Test with mixed valid and invalid data
        mixed_data = [
            # Header
            ["Deal/Campaign name", "Runtime", "Impression goal", "Budget €", "CPM €", "Deal/Campaign ID", "Buyer"],
            # Valid row
            ["Valid Campaign", "04.09.2025-06.09.2025", 15000, 1000.0, 5.0, str(uuid4()), "Valid Buyer"],
            # Invalid row
            ["", "invalid-date", "not-number", "invalid", "invalid", "invalid-uuid", ""]
        ]
        
        with patch('openpyxl.load_workbook') as mock_load_workbook:
            mock_ws = Mock()
            mock_ws.iter_rows.return_value = [
                [Mock(value=cell) for cell in row] for row in mixed_data
            ]
            mock_workbook = Mock()
            mock_workbook.active = mock_ws
            mock_load_workbook.return_value = mock_workbook
            
            # Should handle errors gracefully and continue processing
            with patch.object(parser, '_save_chunk_to_database'):
                results = list(parser.parse_file_streaming("test.xlsx", skip_invalid=True))
                
                # Should have processed valid rows and logged errors for invalid ones
                assert len(results) > 0


class TestPerformanceRequirements:
    """Test performance and scalability requirements."""
    
    def test_chunk_size_configuration(self, parser):
        """Test that chunk size can be configured for optimal performance."""
        assert parser.get_default_chunk_size() == 1000
        
        # Should be able to override chunk size
        custom_chunk_size = 500
        parser.set_chunk_size(custom_chunk_size)
        assert parser.get_chunk_size() == custom_chunk_size
    
    def test_processing_progress_reporting(self, parser):
        """Test that processing progress is reported for large files."""
        progress_reports = []
        
        def progress_callback(processed, total):
            progress_reports.append((processed, total))
        
        # Mock large dataset processing
        with patch('openpyxl.load_workbook') as mock_load_workbook:
            large_dataset = [["Header"]] + [["data"] * 7 for _ in range(5000)]
            mock_ws = Mock()
            mock_ws.iter_rows.return_value = [
                [Mock(value=cell) for cell in row] for row in large_dataset
            ]
            mock_workbook = Mock()
            mock_workbook.active = mock_ws
            mock_load_workbook.return_value = mock_workbook
            
            with patch.object(parser, '_save_chunk_to_database'):
                list(parser.parse_file_streaming("test.xlsx", progress_callback=progress_callback))
        
        # Should have reported progress
        assert len(progress_reports) > 0
        assert progress_reports[-1][0] <= progress_reports[-1][1]  # processed <= total


# XLSXParsingError is imported from the parser module


if __name__ == "__main__":
    # Run tests with coverage
    pytest.main([
        __file__,
        "-v",
        "--cov=src.services.xlsx_campaign_parser",
        "--cov-report=term-missing",
        "--cov-fail-under=95"
    ])