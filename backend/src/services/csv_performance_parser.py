"""
Memory-Efficient CSV Performance Parser for Phase 1.1 Upload Processing Pipeline

Task 3: Memory-Efficient CSV Parser with streaming functionality
- Streaming CSV parser with 1000-record chunks for 250MB files
- Parse 8 columns per reportingCSVstructure.md specification  
- Handle 1,073 records with variable data completeness (58%-100%)
- ISO8601 date format parsing, UUID validation for Deal IDs
- Memory-efficient batch processing for database insertion
- Integrate with ReportingStaging model
"""

import csv
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Any, Optional, Generator, TextIO
from uuid import UUID, uuid4
from io import StringIO
import re

from pydantic import BaseModel
from src.models.staging import ReportingStaging, PurchaseType, ReportingStagingRequest
from src.database.staging_connection import StagingDatabase


class HeaderValidationResult(BaseModel):
    """Result of CSV header validation"""
    is_valid: bool
    errors: List[str] = []
    warnings: List[str] = []
    header_mapping: Dict[str, int] = {}


class RowValidationResult(BaseModel):
    """Result of individual row validation"""
    is_valid: bool
    parsed_data: Dict[str, Any] = {}
    errors: List[str] = []
    warnings: List[str] = []


class CSVParsingResult(BaseModel):
    """Result of complete CSV parsing operation"""
    is_success: bool
    total_records_processed: int = 0
    total_chunks_processed: int = 0
    errors: List[str] = []
    warnings: List[str] = []
    processing_time_seconds: float = 0.0


class CSVPerformanceParser:
    """
    Memory-efficient CSV parser for performance reporting data.
    
    Features:
    - Streaming processing with configurable chunk sizes
    - Memory usage under 50MB for 250MB files
    - Comprehensive data validation per reportingCSVstructure.md
    - Integration with ReportingStaging database model
    - Descriptive error handling with row context
    """
    
    # Expected CSV headers per reportingCSVstructure.md
    REQUIRED_HEADERS = [
        "Date",
        "Core DSP Campaign Name", 
        "Core DSP Campaign ID",
        "Deal Name",
        "Deal ID",
        "Campaign Purchase Type",
        "Deal Purchase Type", 
        "Total Impressions"
    ]
    
    # Optional fields (58% populated)
    OPTIONAL_FIELDS = {
        "Core DSP Campaign Name",
        "Core DSP Campaign ID", 
        "Campaign Purchase Type"
    }
    
    # Required fields (100% populated)
    REQUIRED_FIELDS = {
        "Date",
        "Deal Name", 
        "Deal ID",
        "Deal Purchase Type",
        "Total Impressions"
    }
    
    # UUID validation pattern
    UUID_PATTERN = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', re.IGNORECASE)
    
    # ISO8601 date validation pattern
    ISO8601_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$')
    
    def __init__(self, processing_batch_id: UUID, chunk_size: int = 1000):
        """
        Initialize CSV Performance Parser.
        
        Args:
            processing_batch_id: UUID for tracking this processing batch
            chunk_size: Number of records to process per chunk (default 1000)
        """
        self.processing_batch_id = processing_batch_id
        self.chunk_size = chunk_size
        self.total_records_processed = 0
        self.total_chunks_processed = 0
    
    def validate_headers(self, headers: List[str]) -> HeaderValidationResult:
        """
        Validate CSV headers against required specification.
        
        Args:
            headers: List of header strings from CSV
            
        Returns:
            HeaderValidationResult with validation status and errors
        """
        result = HeaderValidationResult(is_valid=True)
        
        # Normalize headers for case-insensitive comparison
        normalized_headers = [h.strip().lower() for h in headers]
        required_normalized = [h.lower() for h in self.REQUIRED_HEADERS]
        
        # Check for missing required headers
        missing_headers = []
        header_mapping = {}
        
        for i, required_header in enumerate(self.REQUIRED_HEADERS):
            required_lower = required_header.lower()
            
            # Find matching header (case insensitive)
            found_index = None
            for j, normalized_header in enumerate(normalized_headers):
                if normalized_header == required_lower:
                    found_index = j
                    header_mapping[required_header] = j
                    break
            
            if found_index is None:
                missing_headers.append(required_header)
                result.is_valid = False
        
        # Add missing header errors
        for missing in missing_headers:
            result.errors.append(f"Missing required header: {missing}")
        
        # Check for extra headers (warnings only)
        for i, header in enumerate(headers):
            header_lower = header.strip().lower()
            if header_lower not in required_normalized:
                result.warnings.append(f"Extra header found: {header}")
        
        result.header_mapping = header_mapping
        return result
    
    def validate_row_data(self, row: Dict[str, Any], row_number: int) -> RowValidationResult:
        """
        Validate and parse individual CSV row data.
        
        Args:
            row: Dictionary of row data (header -> value)
            row_number: Row number for error context
            
        Returns:
            RowValidationResult with parsed data and validation errors
        """
        result = RowValidationResult(is_valid=True)
        parsed_data = {}
        
        try:
            # Validate and parse Date (required, ISO8601 format)
            date_value = row.get("Date")
            if not date_value or date_value == "":
                result.errors.append(f"Required field Date is missing or empty in row {row_number}")
                result.is_valid = False
            else:
                try:
                    if self.ISO8601_PATTERN.match(str(date_value)):
                        # Parse ISO8601 format: 2025-01-15T10:30:00.000Z
                        parsed_date = datetime.fromisoformat(str(date_value).replace('Z', '+00:00'))
                        parsed_data["date_recorded"] = parsed_date.replace(tzinfo=None)  # Remove timezone for database
                    else:
                        result.errors.append(f"Invalid date format in row {row_number}: expected ISO8601 format (YYYY-MM-DDTHH:MM:SS.sssZ), got '{date_value}'")
                        result.is_valid = False
                except (ValueError, TypeError) as e:
                    result.errors.append(f"Invalid date format in row {row_number}: {str(e)}")
                    result.is_valid = False
            
            # Validate Deal ID (required, UUID format)
            deal_id_value = row.get("Deal ID")
            if not deal_id_value or deal_id_value == "":
                result.errors.append(f"Required field Deal ID is missing or empty in row {row_number}")
                result.is_valid = False
            else:
                try:
                    if self.UUID_PATTERN.match(str(deal_id_value)):
                        parsed_data["deal_id"] = UUID(str(deal_id_value))
                    else:
                        result.errors.append(f"Invalid UUID format for Deal ID in row {row_number}: '{deal_id_value}'")
                        result.is_valid = False
                except (ValueError, TypeError) as e:
                    result.errors.append(f"Invalid UUID format for Deal ID in row {row_number}: {str(e)}")
                    result.is_valid = False
            
            # Validate Core DSP Campaign ID (optional, UUID format when present)
            core_dsp_id_value = row.get("Core DSP Campaign ID")
            if core_dsp_id_value and core_dsp_id_value != "":
                try:
                    if self.UUID_PATTERN.match(str(core_dsp_id_value)):
                        parsed_data["core_dsp_campaign_id"] = UUID(str(core_dsp_id_value))
                    else:
                        result.errors.append(f"Invalid UUID format for Core DSP Campaign ID in row {row_number}: '{core_dsp_id_value}'")
                        result.is_valid = False
                except (ValueError, TypeError) as e:
                    result.errors.append(f"Invalid UUID format for Core DSP Campaign ID in row {row_number}: {str(e)}")
                    result.is_valid = False
            else:
                parsed_data["core_dsp_campaign_id"] = None
            
            # Validate Deal Name (required)
            deal_name_value = row.get("Deal Name")
            if not deal_name_value or deal_name_value == "":
                result.errors.append(f"Required field Deal Name is missing or empty in row {row_number}")
                result.is_valid = False
            else:
                parsed_data["deal_name"] = str(deal_name_value).strip()
            
            # Validate Core DSP Campaign Name (optional)
            core_dsp_name_value = row.get("Core DSP Campaign Name")
            if core_dsp_name_value and core_dsp_name_value != "":
                parsed_data["core_dsp_audience_segment"] = str(core_dsp_name_value).strip()
            else:
                parsed_data["core_dsp_audience_segment"] = None
            
            # Set other Core DSP fields to None (not in current CSV structure but required by model)
            parsed_data["core_dsp_placement"] = None
            parsed_data["core_dsp_creative"] = None
            
            # Validate Purchase Types
            campaign_purchase_type = row.get("Campaign Purchase Type")
            if campaign_purchase_type and campaign_purchase_type != "":
                if str(campaign_purchase_type).lower() in ["guaranteed", "unguaranteed"]:
                    # Not used in current model structure, but validated
                    pass
                else:
                    result.errors.append(f"Invalid purchase type for Campaign Purchase Type in row {row_number}: must be 'guaranteed' or 'unguaranteed', got '{campaign_purchase_type}'")
                    result.is_valid = False
            
            # Validate Deal Purchase Type (required)
            deal_purchase_type = row.get("Deal Purchase Type")
            if not deal_purchase_type or deal_purchase_type == "":
                result.errors.append(f"Required field Deal Purchase Type is missing or empty in row {row_number}")
                result.is_valid = False
            else:
                if str(deal_purchase_type).lower() == "guaranteed":
                    parsed_data["purchase_type"] = PurchaseType.guaranteed
                elif str(deal_purchase_type).lower() == "unguaranteed":
                    parsed_data["purchase_type"] = PurchaseType.unguaranteed
                else:
                    result.errors.append(f"Invalid purchase type for Deal Purchase Type in row {row_number}: must be 'guaranteed' or 'unguaranteed', got '{deal_purchase_type}'")
                    result.is_valid = False
            
            # Validate Total Impressions (required, decimal, range 619 - 231,810,865)
            impressions_value = row.get("Total Impressions")
            if not impressions_value or impressions_value == "":
                result.errors.append(f"Required field Total Impressions is missing or empty in row {row_number}")
                result.is_valid = False
            else:
                try:
                    impressions_decimal = Decimal(str(impressions_value))
                    if impressions_decimal < 619:
                        result.errors.append(f"Total Impressions out of range in row {row_number}: minimum is 619, got {impressions_decimal}")
                        result.is_valid = False
                    elif impressions_decimal > 231810865:
                        result.errors.append(f"Total Impressions out of range in row {row_number}: maximum is 231,810,865, got {impressions_decimal}")
                        result.is_valid = False
                    else:
                        parsed_data["total_impressions"] = impressions_decimal
                except (InvalidOperation, ValueError, TypeError) as e:
                    result.errors.append(f"Invalid impressions format in row {row_number}: must be a number, got '{impressions_value}'")
                    result.is_valid = False
        
        except Exception as e:
            result.errors.append(f"Unexpected error validating row {row_number}: {str(e)}")
            result.is_valid = False
        
        result.parsed_data = parsed_data
        return result
    
    def create_staging_object(self, parsed_data: Dict[str, Any], row_number: int) -> ReportingStaging:
        """
        Create ReportingStaging object from parsed data.
        
        Args:
            parsed_data: Validated and parsed row data
            row_number: Source row number
            
        Returns:
            ReportingStaging object ready for database insertion
        """
        validation_errors = parsed_data.get("validation_errors")
        if validation_errors:
            validation_errors_str = "; ".join(validation_errors)
        else:
            validation_errors_str = None
        
        return ReportingStaging(
            deal_id=parsed_data["deal_id"],
            date_recorded=parsed_data["date_recorded"],
            deal_name=parsed_data["deal_name"],
            core_dsp_audience_segment=parsed_data.get("core_dsp_audience_segment"),
            core_dsp_placement=parsed_data.get("core_dsp_placement"),
            core_dsp_creative=parsed_data.get("core_dsp_creative"),
            purchase_type=parsed_data["purchase_type"],
            total_impressions=parsed_data["total_impressions"],
            processing_batch_id=self.processing_batch_id,
            record_classification="new",  # Default classification
            source_row_number=row_number,
            validation_errors=validation_errors_str
        )
    
    def process_chunk(self, chunk_data: List[Dict[str, Any]], chunk_number: int) -> tuple[int, List[str]]:
        """
        Process a chunk of CSV data with database insertion.
        
        Args:
            chunk_data: List of row dictionaries to process
            chunk_number: Chunk number for error context
            
        Returns:
            Tuple of (records_processed, errors)
        """
        records_processed = 0
        errors = []
        
        try:
            # Use StagingDatabase for cleaner session management
            staging_db = StagingDatabase()
            
            # Use the generator pattern
            for session in staging_db.get_session():
                for i, row in enumerate(chunk_data):
                    row_number = ((chunk_number - 1) * self.chunk_size) + i + 1
                    
                    # Validate row data
                    validation_result = self.validate_row_data(row, row_number)
                    
                    if validation_result.is_valid:
                        try:
                            # Create staging object
                            staging_obj = self.create_staging_object(validation_result.parsed_data, row_number)
                            
                            # Add to session
                            session.add(staging_obj)
                            records_processed += 1
                            
                        except Exception as e:
                            errors.append(f"Error creating staging object for row {row_number}: {str(e)}")
                    else:
                        # Collect validation errors
                        for error in validation_result.errors:
                            errors.append(error)
                
                # Session commit/rollback is handled by the generator
                break  # Only iterate once
                
        except Exception as e:
            errors.append(f"Database error processing chunk {chunk_number}: {str(e)}")
            records_processed = 0  # Reset if transaction failed
        
        return records_processed, errors
    
    def parse_csv_stream(self, csv_stream: TextIO) -> CSVParsingResult:
        """
        Parse CSV stream with chunked processing for memory efficiency.
        
        Args:
            csv_stream: Text stream containing CSV data
            
        Returns:
            CSVParsingResult with processing statistics and errors
        """
        start_time = time.time()
        result = CSVParsingResult(is_success=True)
        
        try:
            # Create CSV reader
            csv_reader = csv.DictReader(csv_stream)
            
            # Validate headers
            if not csv_reader.fieldnames:
                result.errors.append("Empty CSV file or no headers found")
                result.is_success = False
                return result
            
            header_validation = self.validate_headers(csv_reader.fieldnames)
            if not header_validation.is_valid:
                result.errors.extend(header_validation.errors)
                result.is_success = False
                return result
            
            # Add header warnings
            result.warnings.extend(header_validation.warnings)
            
            # Process CSV in chunks
            chunk_data = []
            chunk_number = 0
            total_records_processed = 0
            
            for row in csv_reader:
                chunk_data.append(row)
                
                # Process chunk when it reaches the configured size
                if len(chunk_data) >= self.chunk_size:
                    chunk_number += 1
                    records_processed, chunk_errors = self.process_chunk(chunk_data, chunk_number)
                    
                    total_records_processed += records_processed
                    result.errors.extend(chunk_errors)
                    
                    # Clear chunk data to maintain low memory usage
                    chunk_data = []
            
            # Process remaining records in final chunk
            if chunk_data:
                chunk_number += 1
                records_processed, chunk_errors = self.process_chunk(chunk_data, chunk_number)
                
                total_records_processed += records_processed
                result.errors.extend(chunk_errors)
            
            # Check if any data was processed
            if chunk_number == 0:
                result.errors.append("No data rows found")
            
            # Update result statistics
            result.total_records_processed = total_records_processed
            result.total_chunks_processed = chunk_number
            
            # Determine overall success
            if result.errors and total_records_processed == 0:
                result.is_success = False
        
        except Exception as e:
            result.errors.append(f"Unexpected error parsing CSV: {str(e)}")
            result.is_success = False
        
        finally:
            end_time = time.time()
            result.processing_time_seconds = end_time - start_time
        
        return result