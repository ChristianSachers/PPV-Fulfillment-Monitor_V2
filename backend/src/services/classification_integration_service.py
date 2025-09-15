"""
Classification Integration Service

Orchestrates the complete classification process:
- Retrieves staging records by processing batch ID
- Performs optimized batch classification against production database
- Updates staging records with classification results
- Provides cross-file consistency validation
"""
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID

from src.services.record_classification_engine import (
    RecordClassificationEngine, 
    ClassificationResult,
    BatchClassificationResult,
    CrossFileConsistencyResult
)
from src.database.staging_connection import StagingDatabase
from src.models.staging import CampaignsStaging, ReportingStaging


class ClassificationIntegrationService:
    """
    Service for integrating classification engine with staging database operations.
    
    Orchestrates the complete classification workflow:
    1. Retrieve staging records by processing batch ID
    2. Perform batch classification with production database optimization
    3. Update staging records with classification results
    4. Validate cross-file consistency
    """
    
    def __init__(self, staging_db_url: Optional[str] = None, production_db_url: Optional[str] = None):
        """
        Initialize classification integration service.
        
        Args:
            staging_db_url: Optional staging database URL override
            production_db_url: Optional production database URL override
        """
        self.staging_db = StagingDatabase(staging_db_url)
        self.classification_engine = RecordClassificationEngine(production_db_url)
    
    def classify_campaign_batch(self, processing_batch_id: UUID) -> BatchClassificationResult:
        """
        Classify all campaign records in a processing batch.
        
        Args:
            processing_batch_id: UUID of the processing batch
            
        Returns:
            BatchClassificationResult with classification summary
        """
        try:
            # Retrieve campaign staging records
            campaign_records = self.staging_db.get_campaign_batch_by_processing_id(str(processing_batch_id))
            
            if not campaign_records:
                return BatchClassificationResult(
                    results=[],
                    total_processed=0,
                    processing_errors=[f"No campaign records found for batch {processing_batch_id}"]
                )
            
            # Perform batch classification with production database optimization
            batch_result = self.classification_engine.classify_campaign_batch(campaign_records)
            
            # Update staging records with classification results
            for result in batch_result.results:
                self.staging_db.update_campaign_classification(str(result.uuid), result)
            
            return batch_result
            
        except Exception as e:
            return BatchClassificationResult(
                results=[],
                total_processed=0,
                processing_errors=[f"Campaign batch classification failed: {str(e)}"]
            )
    
    def classify_reporting_batch(self, processing_batch_id: UUID) -> BatchClassificationResult:
        """
        Classify all reporting records in a processing batch.
        
        Args:
            processing_batch_id: UUID of the processing batch
            
        Returns:
            BatchClassificationResult with classification summary
        """
        try:
            # Retrieve reporting staging records
            reporting_records = self.staging_db.get_reporting_batch_by_processing_id(str(processing_batch_id))
            
            if not reporting_records:
                return BatchClassificationResult(
                    results=[],
                    total_processed=0,
                    processing_errors=[f"No reporting records found for batch {processing_batch_id}"]
                )
            
            # Classify each reporting record (reporting doesn't have batch method due to composite key complexity)
            results = []
            processing_errors = []
            
            for record in reporting_records:
                try:
                    result = self.classification_engine.classify_reporting_record(record)
                    results.append(result)
                    
                    # Update staging record with classification result
                    self.staging_db.update_reporting_classification(
                        str(record.deal_id), 
                        record.date_recorded, 
                        result
                    )
                    
                except Exception as e:
                    processing_errors.append(f"Failed to classify reporting record {record.deal_id}: {str(e)}")
            
            # Calculate summary statistics
            categories_summary = {}
            for result in results:
                categories_summary[result.category] = categories_summary.get(result.category, 0) + 1
            
            return BatchClassificationResult(
                results=results,
                total_processed=len(results),
                categories_summary=categories_summary,
                processing_errors=processing_errors
            )
            
        except Exception as e:
            return BatchClassificationResult(
                results=[],
                total_processed=0,
                processing_errors=[f"Reporting batch classification failed: {str(e)}"]
            )
    
    def classify_complete_batch(self, processing_batch_id: UUID) -> Dict[str, Any]:
        """
        Classify both campaign and reporting records in a processing batch.
        
        Args:
            processing_batch_id: UUID of the processing batch
            
        Returns:
            Dictionary with campaign and reporting classification results plus consistency validation
        """
        # Classify campaigns
        campaign_result = self.classify_campaign_batch(processing_batch_id)
        
        # Classify reporting
        reporting_result = self.classify_reporting_batch(processing_batch_id)
        
        # Perform cross-file consistency validation
        campaign_records = self.staging_db.get_campaign_batch_by_processing_id(str(processing_batch_id))
        reporting_records = self.staging_db.get_reporting_batch_by_processing_id(str(processing_batch_id))
        
        consistency_result = self.classification_engine.validate_cross_file_consistency(
            campaign_records, reporting_records
        )
        
        return {
            'processing_batch_id': str(processing_batch_id),
            'campaign_classification': {
                'total_processed': campaign_result.total_processed,
                'categories_summary': campaign_result.categories_summary,
                'processing_errors': campaign_result.processing_errors
            },
            'reporting_classification': {
                'total_processed': reporting_result.total_processed,
                'categories_summary': reporting_result.categories_summary,
                'processing_errors': reporting_result.processing_errors
            },
            'cross_file_consistency': {
                'validation_errors': consistency_result.validation_errors,
                'warnings': consistency_result.warnings
            },
            'overall_success': (
                len(campaign_result.processing_errors) == 0 and 
                len(reporting_result.processing_errors) == 0
            )
        }
    
    def get_classification_summary(self, processing_batch_id: UUID) -> Dict[str, Any]:
        """
        Get classification summary for a processing batch.
        
        Args:
            processing_batch_id: UUID of the processing batch
            
        Returns:
            Dictionary with classification summary statistics
        """
        try:
            campaign_records = self.staging_db.get_campaign_batch_by_processing_id(str(processing_batch_id))
            reporting_records = self.staging_db.get_reporting_batch_by_processing_id(str(processing_batch_id))
            
            # Count classifications for campaigns
            campaign_categories = {}
            for record in campaign_records:
                category = record.record_classification
                campaign_categories[category] = campaign_categories.get(category, 0) + 1
            
            # Count classifications for reporting
            reporting_categories = {}
            for record in reporting_records:
                category = record.record_classification
                reporting_categories[category] = reporting_categories.get(category, 0) + 1
            
            return {
                'processing_batch_id': str(processing_batch_id),
                'campaign_records': {
                    'total': len(campaign_records),
                    'categories': campaign_categories
                },
                'reporting_records': {
                    'total': len(reporting_records),
                    'categories': reporting_categories
                }
            }
            
        except Exception as e:
            return {
                'processing_batch_id': str(processing_batch_id),
                'error': f"Failed to get classification summary: {str(e)}"
            }
    
    def close(self):
        """Clean up database connections."""
        self.staging_db.close()
        self.classification_engine.close()