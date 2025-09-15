"""Database connection utilities for staging operations."""
import os
from typing import Generator
from sqlalchemy import create_engine, Engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError

from src.models.staging import Base, CampaignsStaging, ReportingStaging


def get_staging_database_url() -> str:
    """Get the staging database URL from environment or default configuration."""
    # Check for environment variables first (production)
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    db_name = os.getenv('DB_NAME', 'ppv_fulfillment_dev')
    db_user = os.getenv('DB_USER', '')
    db_password = os.getenv('DB_PASSWORD', '')
    
    # Build connection URL
    if db_user and db_password:
        url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    else:
        # For local development without authentication
        url = f"postgresql://{db_host}:{db_port}/{db_name}"
    
    return url


def create_staging_engine(database_url: str = None) -> Engine:
    """Create SQLAlchemy engine for staging database operations."""
    if database_url is None:
        database_url = get_staging_database_url()
    
    # Engine configuration for staging operations
    engine = create_engine(
        database_url,
        echo=False,  # Set to True for SQL debugging
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,  # Verify connections before use
        pool_recycle=3600,   # Recycle connections after 1 hour
    )
    
    return engine


def get_staging_session(engine: Engine = None) -> Generator[Session, None, None]:
    """Get a staging database session with proper cleanup."""
    if engine is None:
        engine = create_staging_engine()
    
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )
    
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_staging_tables(engine: Engine = None) -> None:
    """Initialize staging tables in the database."""
    if engine is None:
        engine = create_staging_engine()
    
    try:
        # Create all staging tables
        Base.metadata.create_all(bind=engine)
        
        # Verify tables were created
        with engine.connect() as connection:
            # Check if campaigns_staging exists
            result = connection.execute(
                text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'campaigns_staging')")
            )
            campaigns_exists = result.fetchone()[0]
            
            # Check if reporting_staging exists
            result = connection.execute(
                text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'reporting_staging')")
            )
            reporting_exists = result.fetchone()[0]
            
            if not campaigns_exists or not reporting_exists:
                raise OperationalError(
                    "Failed to create staging tables",
                    params=None,
                    orig=None
                )
                
    except OperationalError as e:
        raise OperationalError(
            f"Failed to initialize staging tables: {str(e)}",
            params=None,
            orig=e
        )


def drop_staging_tables(engine: Engine = None) -> None:
    """Drop staging tables from the database (for testing/cleanup)."""
    if engine is None:
        engine = create_staging_engine()
    
    try:
        # Drop all staging tables
        Base.metadata.drop_all(bind=engine)
    except OperationalError as e:
        raise OperationalError(
            f"Failed to drop staging tables: {str(e)}",
            params=None,
            orig=e
        )


def test_staging_connection(database_url: str = None) -> bool:
    """Test the staging database connection."""
    try:
        engine = create_staging_engine(database_url)
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            return result.fetchone()[0] == 1
    except Exception:
        return False
    finally:
        if 'engine' in locals():
            engine.dispose()


class StagingDatabase:
    """Database operations manager for staging data processing."""
    
    def __init__(self, database_url: str = None):
        """Initialize staging database manager.
        
        Args:
            database_url: Optional database URL override
        """
        self.engine = create_staging_engine(database_url)
        self.SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=self.engine
        )
    
    def get_session(self):
        """Get a database session with proper cleanup."""
        from contextlib import contextmanager
        
        @contextmanager
        def session_context():
            session = self.SessionLocal()
            try:
                yield session
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
        
        return session_context()
    
    def save_campaigns_batch(self, campaigns_data: list) -> None:
        """Save a batch of campaign records to staging table.
        
        Args:
            campaigns_data: List of campaign data dictionaries
        """
        with self.get_session() as session:
            for campaign_data in campaigns_data:
                # Create CampaignsStaging instance
                staging_record = CampaignsStaging(
                    deal_campaign_id=campaign_data['deal_campaign_id'],
                    deal_campaign_name=campaign_data['deal_campaign_name'],
                    start_date=campaign_data['start_date'],
                    end_date=campaign_data['end_date'],
                    impression_goal=campaign_data['impression_goal'],
                    budget_eur=campaign_data['budget_eur'],
                    cpm_eur=campaign_data['cpm_eur'],
                    buyer=campaign_data['buyer'],
                    processing_batch_id=campaign_data['processing_batch_id'],
                    record_classification=campaign_data['record_classification'],
                    source_row_number=campaign_data['source_row_number'],
                    validation_errors=campaign_data.get('validation_errors'),
                    # Phase 1.2 extensions (optional)
                    phase_context=campaign_data.get('phase_context'),
                    violation_details=campaign_data.get('violation_details'),
                    flagged_for_review=campaign_data.get('flagged_for_review'),
                    variance_detected=campaign_data.get('variance_detected')
                )
                session.add(staging_record)
    
    def update_campaign_classification(self, campaign_id: str, classification_result) -> None:
        """
        Update campaign staging record with classification result.
        
        Args:
            campaign_id: UUID of the campaign record
            classification_result: ClassificationResult object
        """
        with self.get_session() as session:
            campaign = session.query(CampaignsStaging).filter(
                CampaignsStaging.deal_campaign_id == campaign_id
            ).first()
            
            if campaign:
                campaign.record_classification = classification_result.category.value
                if classification_result.validation_errors:
                    campaign.validation_errors = '; '.join(classification_result.validation_errors)
    
    def update_reporting_classification(self, deal_id: str, date_recorded, classification_result) -> None:
        """
        Update reporting staging record with classification result.
        
        Args:
            deal_id: UUID of the deal record
            date_recorded: Date recorded for the report
            classification_result: ClassificationResult object
        """
        with self.get_session() as session:
            reporting = session.query(ReportingStaging).filter(
                ReportingStaging.deal_id == deal_id,
                ReportingStaging.date_recorded == date_recorded
            ).first()
            
            if reporting:
                reporting.record_classification = classification_result.category.value
                if classification_result.validation_errors:
                    reporting.validation_errors = '; '.join(classification_result.validation_errors)
    
    def get_campaign_batch_by_processing_id(self, processing_batch_id: str):
        """
        Get all campaign staging records for a processing batch.
        
        Args:
            processing_batch_id: UUID of the processing batch
            
        Returns:
            List of CampaignsStaging records
        """
        with self.get_session() as session:
            return session.query(CampaignsStaging).filter(
                CampaignsStaging.processing_batch_id == processing_batch_id
            ).all()
    
    def get_reporting_batch_by_processing_id(self, processing_batch_id: str):
        """
        Get all reporting staging records for a processing batch.
        
        Args:
            processing_batch_id: UUID of the processing batch
            
        Returns:
            List of ReportingStaging records
        """
        with self.get_session() as session:
            return session.query(ReportingStaging).filter(
                ReportingStaging.processing_batch_id == processing_batch_id
            ).all()
    
    def cleanup_batch_records(self, processing_batch_id: str) -> None:
        """
        Clean up all staging records for a processing batch.
        
        Args:
            processing_batch_id: UUID of the processing batch to clean up
        """
        try:
            with self.get_session() as session:
                # Delete campaign staging records
                campaign_delete_count = session.query(CampaignsStaging).filter(
                    CampaignsStaging.processing_batch_id == processing_batch_id
                ).delete()
                
                # Delete reporting staging records
                reporting_delete_count = session.query(ReportingStaging).filter(
                    ReportingStaging.processing_batch_id == processing_batch_id
                ).delete()
                
                # Log cleanup results
                total_deleted = campaign_delete_count + reporting_delete_count
                if total_deleted > 0:
                    print(f"Batch {processing_batch_id}: Cleaned up {campaign_delete_count} campaign records and {reporting_delete_count} reporting records")
                else:
                    print(f"Batch {processing_batch_id}: No records found to clean up")
                    
        except Exception as e:
            raise Exception(f"Failed to cleanup batch records for {processing_batch_id}: {str(e)}")
    
    def get_batch_record_counts(self, processing_batch_id: str) -> dict:
        """
        Get record counts for a processing batch.
        
        Args:
            processing_batch_id: UUID of the processing batch
            
        Returns:
            Dictionary with campaign and reporting record counts
        """
        try:
            with self.get_session() as session:
                campaign_count = session.query(CampaignsStaging).filter(
                    CampaignsStaging.processing_batch_id == processing_batch_id
                ).count()
                
                reporting_count = session.query(ReportingStaging).filter(
                    ReportingStaging.processing_batch_id == processing_batch_id
                ).count()
                
                return {
                    "campaign_records": campaign_count,
                    "reporting_records": reporting_count,
                    "total_records": campaign_count + reporting_count
                }
        except Exception as e:
            raise Exception(f"Failed to get batch record counts for {processing_batch_id}: {str(e)}")
    
    def validate_batch_data_integrity(self, processing_batch_id: str) -> dict:
        """
        Validate data integrity for a processing batch.
        
        Args:
            processing_batch_id: UUID of the processing batch
            
        Returns:
            Dictionary with validation results
        """
        try:
            with self.get_session() as session:
                # Check for duplicate records
                campaign_duplicates = session.query(CampaignsStaging.deal_campaign_id).filter(
                    CampaignsStaging.processing_batch_id == processing_batch_id
                ).group_by(CampaignsStaging.deal_campaign_id).having(
                    session.query(CampaignsStaging.deal_campaign_id).filter(
                        CampaignsStaging.processing_batch_id == processing_batch_id
                    ).count() > 1
                ).count()
                
                # Check for null critical fields
                campaign_null_ids = session.query(CampaignsStaging).filter(
                    CampaignsStaging.processing_batch_id == processing_batch_id,
                    CampaignsStaging.deal_campaign_id.is_(None)
                ).count()
                
                reporting_null_ids = session.query(ReportingStaging).filter(
                    ReportingStaging.processing_batch_id == processing_batch_id,
                    ReportingStaging.deal_id.is_(None)
                ).count()
                
                return {
                    "has_duplicates": campaign_duplicates > 0,
                    "duplicate_count": campaign_duplicates,
                    "has_null_ids": (campaign_null_ids + reporting_null_ids) > 0,
                    "null_campaign_ids": campaign_null_ids,
                    "null_reporting_ids": reporting_null_ids,
                    "integrity_valid": campaign_duplicates == 0 and campaign_null_ids == 0 and reporting_null_ids == 0
                }
        except Exception as e:
            raise Exception(f"Failed to validate batch data integrity for {processing_batch_id}: {str(e)}")
    
    def backup_batch_data(self, processing_batch_id: str) -> dict:
        """
        Create a backup of batch data before cleanup (for error investigation).
        
        Args:
            processing_batch_id: UUID of the processing batch
            
        Returns:
            Dictionary with backup information
        """
        try:
            with self.get_session() as session:
                # Get campaign data
                campaign_records = session.query(CampaignsStaging).filter(
                    CampaignsStaging.processing_batch_id == processing_batch_id
                ).all()
                
                # Get reporting data  
                reporting_records = session.query(ReportingStaging).filter(
                    ReportingStaging.processing_batch_id == processing_batch_id
                ).all()
                
                # Convert to dictionaries for JSON serialization
                campaign_backup = []
                for record in campaign_records:
                    campaign_backup.append({
                        'deal_campaign_id': str(record.deal_campaign_id),
                        'deal_campaign_name': record.deal_campaign_name,
                        'start_date': record.start_date.isoformat() if record.start_date else None,
                        'end_date': record.end_date.isoformat() if record.end_date else None,
                        'impression_goal': record.impression_goal,
                        'budget_eur': float(record.budget_eur) if record.budget_eur else None,
                        'cpm_eur': float(record.cpm_eur) if record.cpm_eur else None,
                        'buyer': record.buyer,
                        'processing_batch_id': record.processing_batch_id,
                        'record_classification': record.record_classification,
                        'source_row_number': record.source_row_number,
                        'validation_errors': record.validation_errors
                    })
                
                reporting_backup = []
                for record in reporting_records:
                    reporting_backup.append({
                        'deal_id': str(record.deal_id),
                        'date_recorded': record.date_recorded.isoformat() if record.date_recorded else None,
                        'total_impressions': float(record.total_impressions) if record.total_impressions else None,
                        'purchase_type': record.purchase_type.value if record.purchase_type else None,
                        'buyer': record.buyer,
                        'core_dsp_campaign_name': record.core_dsp_campaign_name,
                        'deal_name': record.deal_name,
                        'campaign_deal_purchase_type': record.campaign_deal_purchase_type.value if record.campaign_deal_purchase_type else None,
                        'processing_batch_id': record.processing_batch_id,
                        'record_classification': record.record_classification,
                        'source_row_number': record.source_row_number,
                        'validation_errors': record.validation_errors
                    })
                
                return {
                    "processing_batch_id": processing_batch_id,
                    "backup_timestamp": "placeholder_timestamp",  # Would implement with actual timestamp
                    "campaign_records": campaign_backup,
                    "reporting_records": reporting_backup,
                    "record_counts": {
                        "campaigns": len(campaign_backup),
                        "reporting": len(reporting_backup),
                        "total": len(campaign_backup) + len(reporting_backup)
                    }
                }
        except Exception as e:
            raise Exception(f"Failed to backup batch data for {processing_batch_id}: {str(e)}")
    
    def execute_transaction(self, operations: list) -> None:
        """
        Execute multiple database operations in a single transaction.
        
        Args:
            operations: List of functions to execute in transaction
        """
        with self.get_session() as session:
            try:
                for operation in operations:
                    operation(session)
                # Session will be committed automatically if no exceptions
            except Exception as e:
                # Session will be rolled back automatically
                raise Exception(f"Transaction failed: {str(e)}")
    
    def create_phase_1_2_extensions(self) -> dict:
        """Create Phase 1.2 staging table extensions.
        
        Returns:
            Dictionary with creation results
        """
        try:
            with self.get_session() as session:
                # Phase 1.2 extensions are already defined in models
                # Just need to create/update the tables
                Base.metadata.create_all(bind=self.engine)
                
                # Verify extensions were created
                result = self.verify_phase_1_2_extensions()
                
                return {
                    "success": True,
                    "message": "Phase 1.2 extensions created successfully",
                    "verification": result
                }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to create Phase 1.2 extensions: {str(e)}",
                "error": str(e)
            }
    
    def verify_phase_1_2_extensions(self) -> dict:
        """Verify Phase 1.2 staging table extensions exist.
        
        Returns:
            Dictionary with verification results
        """
        try:
            with self.engine.connect() as connection:
                # Check campaigns_staging extensions
                campaigns_result = connection.execute(
                    text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'campaigns_staging' 
                    AND column_name IN ('phase_context', 'violation_details', 'flagged_for_review', 'variance_detected')
                    """)
                )
                campaigns_columns = {row[0] for row in campaigns_result.fetchall()}
                
                # Check reporting_staging extensions
                reporting_result = connection.execute(
                    text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'reporting_staging' 
                    AND column_name IN ('phase_context', 'violation_details', 'flagged_for_review', 'variance_detected')
                    """)
                )
                reporting_columns = {row[0] for row in reporting_result.fetchall()}
                
                # Check indexes
                index_result = connection.execute(
                    text("""
                    SELECT indexname 
                    FROM pg_indexes 
                    WHERE indexname IN ('idx_campaigns_staging_phase_context', 'idx_reporting_staging_phase_context')
                    """)
                )
                indexes = {row[0] for row in index_result.fetchall()}
                
                expected_columns = {'phase_context', 'violation_details', 'flagged_for_review', 'variance_detected'}
                expected_indexes = {'idx_campaigns_staging_phase_context', 'idx_reporting_staging_phase_context'}
                
                return {
                    "campaigns_extended": campaigns_columns == expected_columns,
                    "reporting_extended": reporting_columns == expected_columns,
                    "indexes_created": indexes == expected_indexes,
                    "backward_compatible": True,  # All new columns are nullable
                    "campaigns_missing_columns": list(expected_columns - campaigns_columns),
                    "reporting_missing_columns": list(expected_columns - reporting_columns),
                    "missing_indexes": list(expected_indexes - indexes)
                }
        except Exception as e:
            return {
                "campaigns_extended": False,
                "reporting_extended": False,
                "indexes_created": False,
                "backward_compatible": False,
                "error": str(e)
            }
    
    def close(self):
        """Close database connections."""
        if hasattr(self, 'engine'):
            self.engine.dispose()