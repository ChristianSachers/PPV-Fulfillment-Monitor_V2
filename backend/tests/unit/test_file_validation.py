"""
Tests for file validation utilities - TDD RED phase
These tests MUST fail initially since utils don't exist yet.
"""
import pytest
from src.utils.file_validation import validate_file_type, validate_file_size, sanitize_filename, get_file_extension


class TestValidateFileType:
    
    def test_csv_files_accepted(self):
        """Test CSV files are accepted"""
        assert validate_file_type("data.csv", ["csv", "xlsx", "json"]) is True
        
    def test_excel_files_accepted(self):
        """Test Excel files (.xlsx, .xls) are accepted"""
        assert validate_file_type("report.xlsx", ["csv", "xlsx", "xls"]) is True
        assert validate_file_type("legacy.xls", ["csv", "xlsx", "xls"]) is True
        
    def test_json_files_accepted(self):
        """Test JSON files are accepted"""
        assert validate_file_type("config.json", ["csv", "json"]) is True
        
    def test_invalid_extensions_rejected(self):
        """Test invalid extensions (.txt, .exe, .pdf) are rejected"""
        assert validate_file_type("doc.txt", ["csv", "xlsx"]) is False
        assert validate_file_type("virus.exe", ["csv", "json"]) is False
        assert validate_file_type("manual.pdf", ["csv", "xlsx"]) is False
        
    def test_case_insensitive_validation(self):
        """Test case-insensitive validation"""
        assert validate_file_type("DATA.CSV", ["csv", "xlsx"]) is True
        assert validate_file_type("report.XLSX", ["csv", "xlsx"]) is True
        
    def test_empty_filename_handling(self):
        """Test empty filename handling"""
        assert validate_file_type("", ["csv", "xlsx"]) is False


class TestValidateFileSize:
    
    def test_files_under_limit_accepted(self):
        """Test files under 500MB limit are accepted"""
        assert validate_file_size(100 * 1024 * 1024, 500) is True  # 100MB
        
    def test_files_at_limit_accepted(self):
        """Test files exactly at 500MB limit are accepted"""
        assert validate_file_size(500 * 1024 * 1024, 500) is True  # 500MB
        
    def test_files_over_limit_rejected(self):
        """Test files over 500MB limit are rejected"""
        assert validate_file_size(600 * 1024 * 1024, 500) is False  # 600MB
        
    def test_negative_file_sizes_rejected(self):
        """Test negative file sizes are rejected"""
        assert validate_file_size(-1, 500) is False
        
    def test_zero_file_size_handling(self):
        """Test zero file size handling"""
        assert validate_file_size(0, 500) is False


class TestSanitizeFilename:
    
    def test_dangerous_characters_removed(self):
        """Test dangerous characters are removed"""
        result = sanitize_filename("../../../etc/passwd")
        assert "../" not in result
        assert result == "etcpasswd"
        
    def test_path_traversal_prevention(self):
        """Test path traversal prevention"""
        result = sanitize_filename("..\\windows\\system32\\file.txt")
        assert ".." not in result and "\\" not in result
        
    def test_special_characters_removed(self):
        """Test special characters (<, >, |, :, *, ?, ") are removed"""
        result = sanitize_filename('file<>|:*?"name.csv')
        assert all(char not in result for char in '<>|:*?"')
        
    def test_unicode_filename_handling(self):
        """Test unicode filename handling"""
        result = sanitize_filename("файл.csv")
        assert len(result) > 0
        
    def test_long_filename_truncation(self):
        """Test very long filename truncation"""
        long_name = "a" * 300 + ".csv"
        result = sanitize_filename(long_name)
        assert len(result) <= 255


class TestGetFileExtension:
    
    def test_standard_extensions_extracted(self):
        """Test extraction of .csv, .xlsx, .xls, .json extensions"""
        assert get_file_extension("data.csv") == "csv"
        assert get_file_extension("report.xlsx") == "xlsx"
        assert get_file_extension("config.json") == "json"
        
    def test_multiple_dots_handled(self):
        """Test files with multiple dots (file.backup.csv)"""
        assert get_file_extension("file.backup.csv") == "csv"
        
    def test_files_without_extensions(self):
        """Test files without extensions"""
        assert get_file_extension("README") == ""
        
    def test_case_handling(self):
        """Test case handling in extensions"""
        assert get_file_extension("DATA.CSV").lower() == "csv"