"""
Cross-File Validator

Implements cross-file validation that coordinates Campaign and Performance file processing,
enforces combined upload requirements, and validates relationships between files.

Key Features:
1. Combined Upload Enforcement - Both Campaign and Performance files required (BIZ_105)
2. Cross-file Relationship Validation - Deal names, UUIDs must match between files
3. Hierarchical Name Parsing - " > " structure validation and campaign name extraction
4. Phase 1.1 Integration - Reuses existing file upload tracking and batch management

Error Codes:
- BIZ_105: Combined upload incomplete (missing file pairs)
- BIZ_104: Cross-file relationship failure
- BIZ_101: Deal name modification/mismatch not allowed
- BIZ_106: Campaign/Deal ID conflict
- VAL_015: Invalid hierarchical structure
"""
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from uuid import UUID

from src.services.unified_error_codes import UnifiedErrorCodes, get_error_info
from src.database.staging_connection import StagingDatabase
from src.models.staging import CampaignsStaging, ReportingStaging

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class ValidationError:
    """Structured validation error with comprehensive context."""
    error_code: str
    message: str
    source_row_number: Optional[int] = None
    context: Dict[str, Any] = field(default_factory=dict)
    technical_details: str = ""
    suggested_actions: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Enrich error with information from unified error code system."""
        error_info = get_error_info(self.error_code)
        if error_info:
            if not self.suggested_actions and error_info.suggested_action:
                self.suggested_actions.append(error_info.suggested_action)


@dataclass
class ValidationResult:
    """Result of cross-file validation with detailed error information."""
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    batch_id: Optional[str] = None
    validation_timestamp: datetime = field(default_factory=datetime.now)
    context: Dict[str, Any] = field(default_factory=dict)

    def add_error(self, error_code: str, message: str, **kwargs):
        """Add a validation error to the result."""
        error = ValidationError(
            error_code=error_code,
            message=message,
            **kwargs
        )
        self.errors.append(error)
        self.is_valid = False


class CrossFileValidationError(Exception):
    """Exception for cross-file validation errors."""
    
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.context = context or {}


class HierarchicalNameError(CrossFileValidationError):
    """Exception for hierarchical name parsing errors."""
    pass


class CombinedUploadError(CrossFileValidationError):
    """Exception for combined upload requirement errors."""
    pass


class CrossFileValidator:
    """
    Cross-file validator for Campaign and Performance file coordination.
    
    Validates:
    1. Combined upload requirements (both file types present)
    2. Cross-file relationships (Deal names, UUIDs)
    3. Hierarchical name parsing (" > " structure)
    4. Integration with Phase 1.1 batch management
    """
    
    def __init__(self, staging_db_url: Optional[str] = None):
        """
        Initialize cross-file validator.
        
        Args:
            staging_db_url: Optional database URL override for testing
        """
        try:
            self.staging_db = StagingDatabase(staging_db_url)
            logger.info("CrossFileValidator initialized successfully")
        except Exception as e:
            error_msg = f"Failed to initialize CrossFileValidator: {str(e)}"
            logger.error(error_msg)
            raise CrossFileValidationError(error_msg, {"initialization_error": str(e)})
    
    def validate_combined_upload(self, batch_id: str) -> ValidationResult:
        """
        Validate that both Campaign and Performance files are present in the batch.
        
        Enforces combined upload requirement - rejects uploads missing either file type.
        Generates BIZ_105 error for incomplete uploads.
        
        Args:
            batch_id: Processing batch ID to validate
            
        Returns:
            ValidationResult with success/failure and detailed error information
            
        Raises:
            CrossFileValidationError: On database errors or critical failures
        """
        logger.info(f"Starting combined upload validation for batch {batch_id}")
        
        result = ValidationResult(is_valid=True, batch_id=batch_id)
        
        try:
            # Check for Campaign records in batch
            campaign_records = self.staging_db.get_campaign_batch_by_processing_id(batch_id)
            has_campaigns = len(campaign_records) > 0
            
            # Check for Performance records in batch
            reporting_records = self.staging_db.get_reporting_batch_by_processing_id(batch_id)
            has_reporting = len(reporting_records) > 0
            
            # Validate combined upload requirement
            if not has_campaigns and not has_reporting:
                result.add_error(
                    error_code=UnifiedErrorCodes.BIZ_105,
                    message="Combined upload incomplete: both Campaign and Performance files missing",
                    context={
                        "missing_files": ["campaign", "performance"],
                        "batch_id": batch_id,
                        "campaign_count": 0,
                        "reporting_count": 0
                    },
                    technical_details="No records found in either campaigns_staging or reporting_staging for this batch"
                )
            elif not has_campaigns:
                result.add_error(
                    error_code=UnifiedErrorCodes.BIZ_105,
                    message="Combined upload incomplete: Campaign file missing",
                    context={
                        "missing_files": ["campaign"],
                        "batch_id": batch_id,
                        "campaign_count": 0,
                        "reporting_count": len(reporting_records)
                    },
                    technical_details="No records found in campaigns_staging for this batch"
                )
            elif not has_reporting:
                result.add_error(
                    error_code=UnifiedErrorCodes.BIZ_105,
                    message="Combined upload incomplete: Performance file missing",
                    context={
                        "missing_files": ["performance"],
                        "batch_id": batch_id,
                        "campaign_count": len(campaign_records),
                        "reporting_count": 0
                    },
                    technical_details="No records found in reporting_staging for this batch"
                )
            
            # Update result context
            result.context.update({
                "campaign_record_count": len(campaign_records),
                "reporting_record_count": len(reporting_records),
                "validation_type": "combined_upload"
            })
            
            logger.info(f"Combined upload validation completed for batch {batch_id}: "
                       f"campaigns={len(campaign_records)}, reporting={len(reporting_records)}, "
                       f"valid={result.is_valid}")
            
            return result
            
        except Exception as e:
            error_msg = f"Database error during combined upload validation for batch {batch_id}: {str(e)}"
            logger.error(error_msg)
            raise CrossFileValidationError(error_msg, {
                "batch_id": batch_id,
                "database_error": str(e)
            })
    
    def validate_cross_file_relationships(self, campaign_records: List[Dict], performance_records: List[Dict]) -> ValidationResult:
        """
        Validate relationships between Campaign and Performance file data.
        
        Validates:
        1. Deal name exact matching (case-sensitive) between files
        2. UUID relationships between campaign and performance records
        3. Hierarchical name structure consistency
        4. Campaign vs Deal mutual exclusivity
        
        Args:
            campaign_records: List of campaign data dictionaries
            performance_records: List of performance data dictionaries
            
        Returns:
            ValidationResult with detailed relationship validation results
        """
        logger.info(f"Starting cross-file relationship validation: "
                   f"campaigns={len(campaign_records)}, performance={len(performance_records)}")
        
        result = ValidationResult(is_valid=True)
        
        # Validate hierarchical names first
        campaign_name_errors = self.validate_hierarchical_names(campaign_records)
        performance_name_errors = self.validate_hierarchical_names(performance_records)
        
        result.errors.extend(campaign_name_errors)
        result.errors.extend(performance_name_errors)
        
        if campaign_name_errors or performance_name_errors:
            result.is_valid = False
        
        # Build indexes for efficient lookup
        campaign_names = {record.get('deal_campaign_name', ''): record for record in campaign_records}
        campaign_ids = {record.get('deal_campaign_id'): record for record in campaign_records}
        
        # Validate each performance record
        for perf_record in performance_records:
            deal_name = perf_record.get('deal_name', '')
            deal_id = perf_record.get('deal_id')
            source_row = perf_record.get('source_row_number', 'unknown')
            
            # Check exact deal name matching (case-sensitive)
            if deal_name not in campaign_names:
                # Check for case mismatch
                case_insensitive_match = None
                for campaign_name in campaign_names.keys():
                    if campaign_name.lower() == deal_name.lower():
                        case_insensitive_match = campaign_name
                        break
                
                if case_insensitive_match:
                    result.add_error(
                        error_code=UnifiedErrorCodes.BIZ_101,
                        message=f"Deal name case mismatch: expected '{case_insensitive_match}', got '{deal_name}'",
                        source_row_number=source_row,
                        context={
                            "expected_name": case_insensitive_match,
                            "actual_name": deal_name,
                            "validation_type": "case_sensitive_matching"
                        },
                        technical_details="Exact case-sensitive matching required for deal names"
                    )
                else:
                    result.add_error(
                        error_code=UnifiedErrorCodes.BIZ_104,
                        message=f"Deal name not found in Campaign data: '{deal_name}'",
                        source_row_number=source_row,
                        context={
                            "missing_deal_name": deal_name,
                            "available_campaigns": list(campaign_names.keys())[:5],  # First 5 for context
                            "validation_type": "cross_file_relationship"
                        },
                        technical_details="Each performance record must have corresponding campaign data"
                    )
            
            # Check UUID relationships
            if deal_id and deal_id not in campaign_ids:
                # Check if there's a name match but UUID mismatch
                if deal_name in campaign_names:
                    expected_uuid = campaign_names[deal_name].get('deal_campaign_id')
                    result.add_error(
                        error_code=UnifiedErrorCodes.BIZ_106,
                        message=f"UUID mismatch for deal '{deal_name}': expected {expected_uuid}, got {deal_id}",
                        source_row_number=source_row,
                        context={
                            "deal_name": deal_name,
                            "expected_uuid": str(expected_uuid),
                            "actual_uuid": str(deal_id),
                            "validation_type": "uuid_relationship"
                        },
                        technical_details="Campaign IDs must match exactly between files"
                    )
                else:
                    result.add_error(
                        error_code=UnifiedErrorCodes.BIZ_104,
                        message=f"Deal ID not found in Campaign data: {deal_id}",
                        source_row_number=source_row,
                        context={
                            "missing_deal_id": str(deal_id),
                            "deal_name": deal_name,
                            "validation_type": "cross_file_relationship"
                        },
                        technical_details="Performance record references non-existent campaign"
                    )
        
        # Update result context
        result.context.update({
            "campaign_count": len(campaign_records),
            "performance_count": len(performance_records),
            "validation_type": "cross_file_relationships",
            "unique_campaign_names": len(campaign_names),
            "unique_campaign_ids": len(campaign_ids)
        })
        
        logger.info(f"Cross-file relationship validation completed: "
                   f"valid={result.is_valid}, errors={len(result.errors)}")
        
        return result
    
    def validate_hierarchical_names(self, records: List[Dict]) -> List[ValidationError]:
        """
        Validate hierarchical name structure with " > " separators.
        
        Validates:
        1. Proper " > " separator usage
        2. No empty segments
        3. No trailing/leading separators
        4. Campaign name segment extraction (last segment)
        
        Args:
            records: List of records with 'deal_campaign_name' fields
            
        Returns:
            List of ValidationError objects for any invalid structures
        """
        logger.debug(f"Validating hierarchical names for {len(records)} records")
        
        errors = []
        hierarchical_separator = " > "
        
        for record in records:
            name = record.get('deal_campaign_name', '')
            source_row = record.get('source_row_number', 'unknown')
            
            if not name:
                continue  # Skip empty names
            
            # Validate hierarchical structure if name contains any ">" character
            # This catches both valid " > " separators and invalid ">>" patterns
            if '>' in name:
                validation_errors = self._validate_single_hierarchical_name(name, source_row)
                errors.extend(validation_errors)
        
        logger.debug(f"Hierarchical name validation completed: {len(errors)} errors found")
        return errors
    
    def _validate_single_hierarchical_name(self, name: str, source_row: int) -> List[ValidationError]:
        """
        Validate a single hierarchical name structure.
        
        Args:
            name: The hierarchical name to validate
            source_row: Source row number for error context
            
        Returns:
            List of ValidationError objects
        """
        errors = []
        hierarchical_separator = " > "
        
        # Check for invalid patterns
        invalid_patterns = [
            (r'>{2,}', 'Multiple consecutive separators (>>) not allowed'),
            (r'^\s*>\s*', 'Name cannot start with separator'),
            (r'\s*>\s*$', 'Name cannot end with separator'),
            (r'>\s*>', 'Empty segments not allowed'),
        ]
        
        for pattern, error_message in invalid_patterns:
            if re.search(pattern, name):
                errors.append(ValidationError(
                    error_code=UnifiedErrorCodes.VAL_015,
                    message=f"Invalid hierarchical structure in '{name}': {error_message}",
                    source_row_number=source_row,
                    context={
                        "hierarchical_name": name,
                        "invalid_pattern": pattern,
                        "validation_type": "hierarchical_structure"
                    },
                    technical_details=f"Hierarchical names must use ' > ' separators with no empty segments"
                ))
        
        # Validate segments
        if not errors:  # Only if no pattern errors found
            segments = [segment.strip() for segment in name.split(hierarchical_separator)]
            
            # Check for empty segments after splitting
            empty_segments = [i for i, segment in enumerate(segments) if not segment]
            if empty_segments:
                errors.append(ValidationError(
                    error_code=UnifiedErrorCodes.VAL_015,
                    message=f"Empty segments found in hierarchical name '{name}' at positions: {empty_segments}",
                    source_row_number=source_row,
                    context={
                        "hierarchical_name": name,
                        "empty_segment_positions": empty_segments,
                        "segments": segments,
                        "validation_type": "hierarchical_structure"
                    },
                    technical_details="All segments in hierarchical names must contain text"
                ))
        
        return errors
    
    def get_campaign_name_from_hierarchy(self, hierarchical_name: str) -> str:
        """
        Extract the campaign name (last segment) from hierarchical structure.
        
        Args:
            hierarchical_name: Full hierarchical name with " > " separators
            
        Returns:
            Campaign name (last segment) or original name if not hierarchical
        """
        hierarchical_separator = " > "
        
        if hierarchical_separator not in hierarchical_name:
            return hierarchical_name.strip()
        
        segments = [segment.strip() for segment in hierarchical_name.split(hierarchical_separator)]
        return segments[-1] if segments else hierarchical_name.strip()
    
    def validate_batch_cross_file_consistency(self, batch_id: str) -> ValidationResult:
        """
        Comprehensive batch-level cross-file validation.
        
        Combines combined upload validation and cross-file relationship validation
        for a complete batch validation workflow.
        
        Args:
            batch_id: Processing batch ID to validate
            
        Returns:
            ValidationResult with comprehensive validation results
        """
        logger.info(f"Starting comprehensive batch cross-file validation for batch {batch_id}")
        
        # Step 1: Validate combined upload requirement
        combined_result = self.validate_combined_upload(batch_id)
        
        if not combined_result.is_valid:
            logger.warning(f"Combined upload validation failed for batch {batch_id}")
            return combined_result
        
        try:
            # Step 2: Get data for relationship validation
            campaign_records = self.staging_db.get_campaign_batch_by_processing_id(batch_id)
            reporting_records = self.staging_db.get_reporting_batch_by_processing_id(batch_id)
            
            # Convert to dictionaries for validation
            campaign_dicts = [self._staging_record_to_dict(record) for record in campaign_records]
            reporting_dicts = [self._staging_record_to_dict(record) for record in reporting_records]
            
            # Step 3: Validate cross-file relationships
            relationship_result = self.validate_cross_file_relationships(campaign_dicts, reporting_dicts)
            
            # Combine results
            final_result = ValidationResult(
                is_valid=combined_result.is_valid and relationship_result.is_valid,
                batch_id=batch_id
            )
            final_result.errors.extend(combined_result.errors)
            final_result.errors.extend(relationship_result.errors)
            final_result.context.update(combined_result.context)
            final_result.context.update(relationship_result.context)
            
            logger.info(f"Comprehensive batch validation completed for batch {batch_id}: "
                       f"valid={final_result.is_valid}, total_errors={len(final_result.errors)}")
            
            return final_result
            
        except Exception as e:
            error_msg = f"Error during batch cross-file validation for {batch_id}: {str(e)}"
            logger.error(error_msg)
            raise CrossFileValidationError(error_msg, {
                "batch_id": batch_id,
                "validation_error": str(e)
            })
    
    def _staging_record_to_dict(self, record) -> Dict[str, Any]:
        """
        Convert SQLAlchemy staging record to dictionary format.
        
        Args:
            record: CampaignsStaging or ReportingStaging record
            
        Returns:
            Dictionary representation of the record
        """
        if hasattr(record, 'deal_campaign_id'):  # CampaignsStaging
            return {
                'deal_campaign_id': record.deal_campaign_id,
                'deal_campaign_name': record.deal_campaign_name,
                'start_date': record.start_date,
                'end_date': record.end_date,
                'impression_goal': record.impression_goal,
                'budget_eur': record.budget_eur,
                'cpm_eur': record.cpm_eur,
                'buyer': record.buyer,
                'processing_batch_id': record.processing_batch_id,
                'record_classification': record.record_classification,
                'source_row_number': record.source_row_number,
                'validation_errors': record.validation_errors
            }
        else:  # ReportingStaging
            return {
                'deal_id': record.deal_id,
                'date_recorded': record.date_recorded,
                'deal_name': record.deal_name,
                'core_dsp_audience_segment': record.core_dsp_audience_segment,
                'core_dsp_placement': record.core_dsp_placement,
                'core_dsp_creative': record.core_dsp_creative,
                'purchase_type': record.purchase_type,
                'total_impressions': record.total_impressions,
                'processing_batch_id': record.processing_batch_id,
                'record_classification': record.record_classification,
                'source_row_number': record.source_row_number,
                'validation_errors': record.validation_errors
            }
    
    def close(self):
        """Close database connections and cleanup resources."""
        if hasattr(self, 'staging_db') and self.staging_db:
            self.staging_db.close()
            logger.info("CrossFileValidator resources cleaned up")