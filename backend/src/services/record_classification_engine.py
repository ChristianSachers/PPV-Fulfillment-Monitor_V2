"""
Record Classification Engine for categorizing staging data against production database.

Implements 4-category classification system:
- New Entries: UUID not found in production database
- Updated Entries: UUID exists with acceptable changes (Total Impressions only)
- Unchanged Records: Identical data to production
- Inconsistent Data: Changes to restricted fields

Production Database Optimization:
- Batch UUID lookups (500 records per query maximum)
- Connection pooling with read-only transactions
- Single SELECT query per batch using WHERE uuid IN (...) pattern
- Query result caching for duplicate UUID lookups within same batch
"""
import os
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import List, Dict, Any, Optional, Set, Tuple
from uuid import UUID
from dataclasses import dataclass, field

from sqlalchemy import create_engine, Engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from src.models.staging import CampaignsStaging, ReportingStaging, PurchaseType


class ClassificationCategory(str, Enum):
    """Classification categories for staging records."""
    NEW = "new"
    UPDATED = "updated"
    UNCHANGED = "unchanged"
    INCONSISTENT = "inconsistent"


@dataclass
class ProductionRecord:
    """Represents a production database record."""
    uuid: UUID
    data: Dict[str, Any]


@dataclass
class FieldChange:
    """Represents a change between staging and production data."""
    field: str
    old_value: Any
    new_value: Any
    is_restricted: bool = False


@dataclass
class ClassificationResult:
    """Result of classifying a single staging record."""
    uuid: UUID
    category: ClassificationCategory
    reason: str
    changes: List[Dict[str, Any]] = field(default_factory=list)
    validation_errors: List[str] = field(default_factory=list)
    source_row_number: Optional[int] = None


@dataclass
class BatchClassificationResult:
    """Result of classifying a batch of staging records."""
    results: List[ClassificationResult]
    total_processed: int
    categories_summary: Dict[ClassificationCategory, int] = field(default_factory=dict)
    processing_errors: List[str] = field(default_factory=list)


@dataclass
class CrossFileConsistencyResult:
    """Result of cross-file consistency validation."""
    validation_errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class RecordClassificationEngine:
    """
    Engine for classifying staging records against production database.
    
    Features:
    - Batch processing with optimized database queries
    - 4-category classification system
    - Production database optimization (500 records per query max)
    - Connection pooling with read-only transactions
    - Cross-file consistency validation
    - Business rule validation integration
    """
    
    # Restricted fields that cannot be changed (trigger INCONSISTENT classification)
    CAMPAIGN_RESTRICTED_FIELDS = {
        'deal_campaign_name', 'start_date', 'end_date', 'budget_eur', 
        'cpm_eur', 'buyer'
    }
    
    REPORTING_RESTRICTED_FIELDS = {
        'deal_name', 'purchase_type', 'date_recorded', 'core_dsp_audience_segment',
        'core_dsp_placement', 'core_dsp_creative'
    }
    
    # Acceptable fields that can be changed (trigger UPDATED classification)
    CAMPAIGN_ACCEPTABLE_FIELDS = {'impression_goal'}
    REPORTING_ACCEPTABLE_FIELDS = {'total_impressions'}
    
    # Maximum batch size for production queries (optimization requirement)
    MAX_BATCH_SIZE = 500
    
    def __init__(self, production_database_url: Optional[str] = None):
        """
        Initialize classification engine.
        
        Args:
            production_database_url: Optional production database URL override
        """
        self.production_database_url = production_database_url or self._get_production_database_url()
        self._production_engine: Optional[Engine] = None
        self._production_session_maker = None
    
    def _get_production_database_url(self) -> str:
        """Get production database URL from environment or configuration."""
        # Check for production-specific environment variables
        db_host = os.getenv('PROD_DB_HOST', os.getenv('DB_HOST', 'localhost'))
        db_port = os.getenv('PROD_DB_PORT', os.getenv('DB_PORT', '5432'))
        db_name = os.getenv('PROD_DB_NAME', os.getenv('DB_NAME', 'ppv_fulfillment_dev'))
        db_user = os.getenv('PROD_DB_USER', os.getenv('DB_USER', ''))
        db_password = os.getenv('PROD_DB_PASSWORD', os.getenv('DB_PASSWORD', ''))
        
        # Build connection URL
        if db_user and db_password:
            return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        else:
            return f"postgresql://{db_host}:{db_port}/{db_name}"
    
    def _get_production_engine(self) -> Engine:
        """Get production database engine with connection pooling optimization."""
        if self._production_engine is None:
            self._production_engine = create_engine(
                self.production_database_url,
                echo=False,
                pool_size=5,  # Smaller pool size for read-only operations
                max_overflow=10,
                pool_pre_ping=True,
                pool_recycle=3600,
                # Read-only connection optimization
                connect_args={
                    "application_name": "classification_engine_readonly",
                    "options": "-c default_transaction_isolation=read_committed -c default_transaction_read_only=on"
                }
            )
        return self._production_engine
    
    def _batch_lookup_production_records(self, uuids: List[UUID], table_type: str) -> Dict[UUID, ProductionRecord]:
        """
        Perform optimized batch lookup of production records.
        
        Production Database Optimization:
        - Batch queries with max 500 records per query
        - Connection pooling with read-only transactions
        - Single SELECT with WHERE uuid IN (...) pattern
        - Result caching for duplicate UUIDs within batch
        
        Args:
            uuids: List of UUIDs to lookup
            table_type: Type of table ('campaigns' or 'reporting')
            
        Returns:
            Dict mapping UUID to ProductionRecord
        """
        if not uuids:
            return {}
        
        # Remove duplicates and preserve order for caching
        unique_uuids = list(dict.fromkeys(uuids))
        results = {}
        
        # Process in batches of MAX_BATCH_SIZE (500)
        for i in range(0, len(unique_uuids), self.MAX_BATCH_SIZE):
            batch_uuids = unique_uuids[i:i + self.MAX_BATCH_SIZE]
            
            # Create SQL query with WHERE IN pattern
            if table_type == 'campaigns':
                query_sql = """
                    SELECT deal_campaign_id, deal_campaign_name, start_date, end_date,
                           impression_goal, budget_eur, cpm_eur, buyer
                    FROM campaigns WHERE deal_campaign_id IN :uuids
                """
            else:
                query_sql = """
                    SELECT deal_id, date_recorded, deal_name, core_dsp_audience_segment,
                           core_dsp_placement, core_dsp_creative, purchase_type, total_impressions
                    FROM reporting WHERE deal_id IN :uuids
                """
            
            batch_results = self._execute_production_query(batch_uuids, query_sql)
            results.update({record.uuid: record for record in batch_results})
        
        return results
    
    def _execute_production_query(self, uuids: List[UUID], query_sql: str) -> List[ProductionRecord]:
        """
        Execute optimized production database query.
        
        Args:
            uuids: Batch of UUIDs to query
            query_sql: SQL query string with WHERE IN pattern
            
        Returns:
            List of ProductionRecord objects
        """
        # Determine table type from query
        if 'campaigns' in query_sql.lower():
            return self._query_production_campaigns(uuids)
        elif 'reporting' in query_sql.lower():
            return self._query_production_reporting(uuids)
        else:
            raise ValueError(f"Cannot determine table type from query: {query_sql}")
    
    def _query_production_campaigns(self, uuids: List[UUID]) -> List[ProductionRecord]:
        """Query production campaigns table with WHERE IN optimization."""
        # Note: This assumes production tables exist with similar structure to staging
        # In real implementation, these would reference actual production table names
        query = text("""
            SELECT deal_campaign_id, deal_campaign_name, start_date, end_date,
                   impression_goal, budget_eur, cpm_eur, buyer
            FROM campaigns  -- Production campaigns table
            WHERE deal_campaign_id = ANY(:uuids)
        """)
        
        engine = self._get_production_engine()
        
        try:
            with engine.connect() as connection:
                result = connection.execute(query, {"uuids": [str(uuid) for uuid in uuids]})
                rows = result.fetchall()
                
                production_records = []
                for row in rows:
                    record = ProductionRecord(
                        uuid=UUID(str(row.deal_campaign_id)),
                        data={
                            'deal_campaign_name': row.deal_campaign_name,
                            'start_date': row.start_date,
                            'end_date': row.end_date,
                            'impression_goal': row.impression_goal,
                            'budget_eur': row.budget_eur,
                            'cpm_eur': row.cpm_eur,
                            'buyer': row.buyer
                        }
                    )
                    production_records.append(record)
                
                return production_records
                
        except SQLAlchemyError as e:
            raise Exception(f"Production database query failed: {str(e)}")
    
    def _query_production_reporting(self, uuids: List[UUID]) -> List[ProductionRecord]:
        """Query production reporting table with WHERE IN optimization."""
        query = text("""
            SELECT deal_id, date_recorded, deal_name, core_dsp_audience_segment,
                   core_dsp_placement, core_dsp_creative, purchase_type, total_impressions
            FROM reporting  -- Production reporting table
            WHERE deal_id = ANY(:uuids)
        """)
        
        engine = self._get_production_engine()
        
        try:
            with engine.connect() as connection:
                result = connection.execute(query, {"uuids": [str(uuid) for uuid in uuids]})
                rows = result.fetchall()
                
                production_records = []
                for row in rows:
                    # Handle composite key by combining deal_id and date_recorded
                    composite_key = f"{row.deal_id}_{row.date_recorded}"
                    record = ProductionRecord(
                        uuid=UUID(str(row.deal_id)),  # Use deal_id as primary identifier
                        data={
                            'date_recorded': row.date_recorded,
                            'deal_name': row.deal_name,
                            'core_dsp_audience_segment': row.core_dsp_audience_segment,
                            'core_dsp_placement': row.core_dsp_placement,
                            'core_dsp_creative': row.core_dsp_creative,
                            'purchase_type': PurchaseType(row.purchase_type),
                            'total_impressions': row.total_impressions
                        }
                    )
                    production_records.append(record)
                
                return production_records
                
        except SQLAlchemyError as e:
            raise Exception(f"Production database query failed: {str(e)}")
    
    def classify_campaign_record(self, staging_record: CampaignsStaging) -> ClassificationResult:
        """
        Classify a single campaign staging record.
        
        Args:
            staging_record: Campaign staging record to classify
            
        Returns:
            ClassificationResult with category and details
        """
        # Validate business rules first
        validation_errors = self._validate_campaign_business_rules(staging_record)
        
        # Lookup production record
        production_records = self._batch_lookup_production_records(
            [staging_record.deal_campaign_id], 'campaigns'
        )
        
        production_record = production_records.get(staging_record.deal_campaign_id)
        
        if production_record is None:
            # Category 1: New Entry
            return ClassificationResult(
                uuid=staging_record.deal_campaign_id,
                category=ClassificationCategory.NEW,
                reason="UUID not found in production database",
                validation_errors=validation_errors,
                source_row_number=staging_record.source_row_number
            )
        
        # Validate production data completeness and add any issues to validation errors
        production_validation_errors = self._validate_production_data_completeness(production_record, 'campaign')
        validation_errors.extend(production_validation_errors)
        
        # Compare staging vs production data
        changes = self._compare_campaign_data(staging_record, production_record)
        
        if not changes:
            # Category 3: Unchanged
            return ClassificationResult(
                uuid=staging_record.deal_campaign_id,
                category=ClassificationCategory.UNCHANGED,
                reason="Record is identical to production data",
                validation_errors=validation_errors,
                source_row_number=staging_record.source_row_number
            )
        
        # Check if changes are restricted
        restricted_changes = [c for c in changes if c.field in self.CAMPAIGN_RESTRICTED_FIELDS]
        acceptable_changes = [c for c in changes if c.field in self.CAMPAIGN_ACCEPTABLE_FIELDS]
        
        if restricted_changes:
            # Category 4: Inconsistent
            return ClassificationResult(
                uuid=staging_record.deal_campaign_id,
                category=ClassificationCategory.INCONSISTENT,
                reason=f"Changes to restricted fields: {', '.join(c.field for c in restricted_changes)}",
                changes=[self._change_to_dict(c) for c in changes],
                validation_errors=validation_errors,
                source_row_number=staging_record.source_row_number
            )
        
        if acceptable_changes:
            # Category 2: Updated
            return ClassificationResult(
                uuid=staging_record.deal_campaign_id,
                category=ClassificationCategory.UPDATED,
                reason=f"Acceptable changes to: {', '.join(c.field for c in acceptable_changes)}",
                changes=[self._change_to_dict(c) for c in changes],
                validation_errors=validation_errors,
                source_row_number=staging_record.source_row_number
            )
        
        # Fallback: should not reach here with current logic
        return ClassificationResult(
            uuid=staging_record.deal_campaign_id,
            category=ClassificationCategory.INCONSISTENT,
            reason="Unclassified changes detected",
            changes=[self._change_to_dict(c) for c in changes],
            validation_errors=validation_errors,
            source_row_number=staging_record.source_row_number
        )
    
    def classify_reporting_record(self, staging_record: ReportingStaging) -> ClassificationResult:
        """
        Classify a single reporting staging record.
        
        Args:
            staging_record: Reporting staging record to classify
            
        Returns:
            ClassificationResult with category and details
        """
        # Validate business rules first
        validation_errors = self._validate_reporting_business_rules(staging_record)
        
        # Lookup production record
        production_records = self._batch_lookup_production_records(
            [staging_record.deal_id], 'reporting'
        )
        
        production_record = production_records.get(staging_record.deal_id)
        
        if production_record is None:
            # Category 1: New Entry
            return ClassificationResult(
                uuid=staging_record.deal_id,
                category=ClassificationCategory.NEW,
                reason="UUID not found in production database",
                validation_errors=validation_errors,
                source_row_number=staging_record.source_row_number
            )
        
        # Validate production data completeness and add any issues to validation errors
        production_validation_errors = self._validate_production_data_completeness(production_record, 'reporting')
        validation_errors.extend(production_validation_errors)
        
        # Compare staging vs production data
        changes = self._compare_reporting_data(staging_record, production_record)
        
        if not changes:
            # Category 3: Unchanged
            return ClassificationResult(
                uuid=staging_record.deal_id,
                category=ClassificationCategory.UNCHANGED,
                reason="Record is identical to production data",
                validation_errors=validation_errors,
                source_row_number=staging_record.source_row_number
            )
        
        # Check if changes are restricted
        restricted_changes = [c for c in changes if c.field in self.REPORTING_RESTRICTED_FIELDS]
        acceptable_changes = [c for c in changes if c.field in self.REPORTING_ACCEPTABLE_FIELDS]
        
        if restricted_changes:
            # Category 4: Inconsistent
            return ClassificationResult(
                uuid=staging_record.deal_id,
                category=ClassificationCategory.INCONSISTENT,
                reason=f"Changes to restricted fields: {', '.join(c.field for c in restricted_changes)}",
                changes=[self._change_to_dict(c) for c in changes],
                validation_errors=validation_errors,
                source_row_number=staging_record.source_row_number
            )
        
        if acceptable_changes:
            # Category 2: Updated
            return ClassificationResult(
                uuid=staging_record.deal_id,
                category=ClassificationCategory.UPDATED,
                reason=f"Acceptable changes to: {', '.join(c.field for c in acceptable_changes)}",
                changes=[self._change_to_dict(c) for c in changes],
                validation_errors=validation_errors,
                source_row_number=staging_record.source_row_number
            )
        
        # Fallback
        return ClassificationResult(
            uuid=staging_record.deal_id,
            category=ClassificationCategory.INCONSISTENT,
            reason="Unclassified changes detected",
            changes=[self._change_to_dict(c) for c in changes],
            validation_errors=validation_errors,
            source_row_number=staging_record.source_row_number
        )
    
    def classify_campaign_batch(self, staging_records: List[CampaignsStaging]) -> BatchClassificationResult:
        """
        Classify a batch of campaign staging records with optimized database access.
        
        Args:
            staging_records: List of campaign staging records
            
        Returns:
            BatchClassificationResult with all classifications
        """
        if not staging_records:
            return BatchClassificationResult(results=[], total_processed=0)
        
        # Extract UUIDs for batch lookup
        uuids = [record.deal_campaign_id for record in staging_records]
        
        try:
            # Perform optimized batch lookup
            production_records = self._batch_lookup_production_records(uuids, 'campaigns')
            
            # Classify each record
            results = []
            for staging_record in staging_records:
                try:
                    # Use cached production record if available
                    production_record = production_records.get(staging_record.deal_campaign_id)
                    result = self._classify_single_campaign(staging_record, production_record)
                    results.append(result)
                except Exception as e:
                    # Handle individual record errors
                    error_result = ClassificationResult(
                        uuid=staging_record.deal_campaign_id,
                        category=ClassificationCategory.INCONSISTENT,
                        reason=f"Classification error: {str(e)}",
                        validation_errors=[str(e)],
                        source_row_number=staging_record.source_row_number
                    )
                    results.append(error_result)
            
            # Calculate summary statistics
            categories_summary = {}
            for result in results:
                categories_summary[result.category] = categories_summary.get(result.category, 0) + 1
            
            return BatchClassificationResult(
                results=results,
                total_processed=len(results),
                categories_summary=categories_summary,
                processing_errors=[]
            )
            
        except Exception as e:
            return BatchClassificationResult(
                results=[],
                total_processed=0,
                processing_errors=[f"Batch processing failed: {str(e)}"]
            )
    
    def _classify_single_campaign(self, staging_record: CampaignsStaging, production_record: Optional[ProductionRecord]) -> ClassificationResult:
        """Helper method to classify a single campaign with optional production record."""
        validation_errors = self._validate_campaign_business_rules(staging_record)
        
        if production_record is None:
            return ClassificationResult(
                uuid=staging_record.deal_campaign_id,
                category=ClassificationCategory.NEW,
                reason="UUID not found in production database",
                validation_errors=validation_errors,
                source_row_number=staging_record.source_row_number
            )
        
        changes = self._compare_campaign_data(staging_record, production_record)
        
        if not changes:
            return ClassificationResult(
                uuid=staging_record.deal_campaign_id,
                category=ClassificationCategory.UNCHANGED,
                reason="Record is identical to production data",
                validation_errors=validation_errors,
                source_row_number=staging_record.source_row_number
            )
        
        restricted_changes = [c for c in changes if c.field in self.CAMPAIGN_RESTRICTED_FIELDS]
        acceptable_changes = [c for c in changes if c.field in self.CAMPAIGN_ACCEPTABLE_FIELDS]
        
        if restricted_changes:
            return ClassificationResult(
                uuid=staging_record.deal_campaign_id,
                category=ClassificationCategory.INCONSISTENT,
                reason=f"Changes to restricted fields: {', '.join(c.field for c in restricted_changes)}",
                changes=[self._change_to_dict(c) for c in changes],
                validation_errors=validation_errors,
                source_row_number=staging_record.source_row_number
            )
        
        if acceptable_changes:
            return ClassificationResult(
                uuid=staging_record.deal_campaign_id,
                category=ClassificationCategory.UPDATED,
                reason=f"Acceptable changes to: {', '.join(c.field for c in acceptable_changes)}",
                changes=[self._change_to_dict(c) for c in changes],
                validation_errors=validation_errors,
                source_row_number=staging_record.source_row_number
            )
        
        return ClassificationResult(
            uuid=staging_record.deal_campaign_id,
            category=ClassificationCategory.INCONSISTENT,
            reason="Unclassified changes detected",
            changes=[self._change_to_dict(c) for c in changes],
            validation_errors=validation_errors,
            source_row_number=staging_record.source_row_number
        )
    
    def _compare_campaign_data(self, staging: CampaignsStaging, production: ProductionRecord) -> List[FieldChange]:
        """Compare campaign staging data with production data."""
        changes = []
        
        # Define field mappings
        field_mappings = {
            'deal_campaign_name': staging.deal_campaign_name,
            'start_date': staging.start_date,
            'end_date': staging.end_date,
            'impression_goal': staging.impression_goal,
            'budget_eur': staging.budget_eur,
            'cpm_eur': staging.cpm_eur,
            'buyer': staging.buyer
        }
        
        for field_name, staging_value in field_mappings.items():
            production_value = production.data.get(field_name)
            
            if staging_value != production_value:
                change = FieldChange(
                    field=field_name,
                    old_value=production_value,
                    new_value=staging_value,
                    is_restricted=field_name in self.CAMPAIGN_RESTRICTED_FIELDS
                )
                changes.append(change)
        
        return changes
    
    def _compare_reporting_data(self, staging: ReportingStaging, production: ProductionRecord) -> List[FieldChange]:
        """Compare reporting staging data with production data."""
        changes = []
        
        # Define field mappings
        field_mappings = {
            'date_recorded': staging.date_recorded,
            'deal_name': staging.deal_name,
            'core_dsp_audience_segment': staging.core_dsp_audience_segment,
            'core_dsp_placement': staging.core_dsp_placement,
            'core_dsp_creative': staging.core_dsp_creative,
            'purchase_type': staging.purchase_type,
            'total_impressions': staging.total_impressions
        }
        
        for field_name, staging_value in field_mappings.items():
            production_value = production.data.get(field_name)
            
            if staging_value != production_value:
                change = FieldChange(
                    field=field_name,
                    old_value=production_value,
                    new_value=staging_value,
                    is_restricted=field_name in self.REPORTING_RESTRICTED_FIELDS
                )
                changes.append(change)
        
        return changes
    
    def _change_to_dict(self, change: FieldChange) -> Dict[str, Any]:
        """Convert FieldChange to dictionary for serialization."""
        return {
            'field': change.field,
            'old_value': change.old_value,
            'new_value': change.new_value,
            'is_restricted': change.is_restricted
        }
    
    def _validate_campaign_business_rules(self, record: CampaignsStaging) -> List[str]:
        """Validate campaign business rules and return list of errors."""
        errors = []
        
        # Validate impression goal range
        if record.impression_goal < 3000:
            errors.append(f"impression_goal {record.impression_goal} below minimum 3,000")
        elif record.impression_goal > 720000:
            errors.append(f"impression_goal {record.impression_goal} above maximum 720,000")
        
        # Validate CPM range
        if record.cpm_eur < Decimal('0.01'):
            errors.append(f"cpm_eur {record.cpm_eur} below minimum €0.01")
        elif record.cpm_eur > Decimal('45.00'):
            errors.append(f"cpm_eur {record.cpm_eur} above maximum €45.00")
        
        # Validate budget if provided
        if record.budget_eur is not None and record.budget_eur < 0:
            errors.append(f"budget_eur {record.budget_eur} cannot be negative")
        
        return errors
    
    def _validate_reporting_business_rules(self, record: ReportingStaging) -> List[str]:
        """Validate reporting business rules and return list of errors."""
        errors = []
        
        # Validate total impressions range
        if record.total_impressions < 619:
            errors.append(f"total_impressions {record.total_impressions} below minimum 619")
        elif record.total_impressions > 231000000:
            errors.append(f"total_impressions {record.total_impressions} above maximum 231,000,000")
        
        return errors
    
    def _validate_production_data_completeness(self, production_record: ProductionRecord, record_type: str) -> List[str]:
        """
        Validate production data completeness and return list of errors.
        
        Args:
            production_record: Production record to validate
            record_type: Type of record ('campaign' or 'reporting')
            
        Returns:
            List of validation error messages
        """
        errors = []
        
        if record_type == 'campaign':
            required_fields = [
                'deal_campaign_name', 'start_date', 'end_date', 'impression_goal',
                'budget_eur', 'cpm_eur', 'buyer'
            ]
        else:  # reporting
            required_fields = [
                'date_recorded', 'deal_name', 'purchase_type', 'total_impressions'
            ]
        
        for field in required_fields:
            if field not in production_record.data or production_record.data[field] is None:
                errors.append(f"Production record missing required field: {field}")
        
        return errors
    
    def validate_cross_file_consistency(self, campaign_records: List[CampaignsStaging], 
                                       reporting_records: List[ReportingStaging]) -> CrossFileConsistencyResult:
        """
        Validate consistency between campaign and reporting files.
        
        Args:
            campaign_records: List of campaign staging records
            reporting_records: List of reporting staging records
            
        Returns:
            CrossFileConsistencyResult with validation errors and warnings
        """
        result = CrossFileConsistencyResult()
        
        # Create lookup dictionaries
        campaign_lookup = {record.deal_campaign_id: record for record in campaign_records}
        reporting_lookup = {record.deal_id: record for record in reporting_records}
        
        # Check for matching UUIDs with inconsistent names
        for deal_id, reporting_record in reporting_lookup.items():
            campaign_record = campaign_lookup.get(deal_id)
            if campaign_record:
                # Check if deal name matches campaign name
                if reporting_record.deal_name != campaign_record.deal_campaign_name:
                    result.validation_errors.append(
                        f"Deal name mismatch for UUID {deal_id}: "
                        f"Campaign='{campaign_record.deal_campaign_name}' vs "
                        f"Reporting='{reporting_record.deal_name}'"
                    )
        
        # Check for reporting records without corresponding campaigns
        campaign_uuids = set(campaign_lookup.keys())
        reporting_uuids = set(reporting_lookup.keys())
        
        orphaned_reporting = reporting_uuids - campaign_uuids
        if orphaned_reporting:
            result.warnings.append(
                f"Found {len(orphaned_reporting)} reporting records without corresponding campaigns"
            )
        
        return result
    
    def close(self):
        """Clean up database connections."""
        if self._production_engine:
            self._production_engine.dispose()
            self._production_engine = None