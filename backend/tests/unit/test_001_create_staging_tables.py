"""
Test migration script - SQLite compatible version for unit testing.
This is a simplified version of the PostgreSQL migration for testing purposes.
"""

from datetime import datetime
from sqlalchemy import text, Engine
from typing import Dict, Any


def run_forward_migration(engine: Engine) -> Dict[str, Any]:
    """Execute forward migration (SQLite compatible)."""
    migration_start = datetime.utcnow()
    
    try:
        with engine.connect() as connection:
            # Create campaigns_staging table (SQLite compatible)
            connection.execute(text("""
                CREATE TABLE campaigns_staging (
                    deal_campaign_id TEXT PRIMARY KEY,
                    deal_campaign_name TEXT NOT NULL,
                    start_date TEXT NOT NULL,
                    end_date TEXT NOT NULL,
                    impression_goal INTEGER NOT NULL,
                    budget_eur REAL,
                    cpm_eur REAL NOT NULL,
                    buyer TEXT NOT NULL,
                    processing_batch_id TEXT NOT NULL,
                    record_classification TEXT NOT NULL,
                    source_row_number INTEGER NOT NULL,
                    validation_errors TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT
                )
            """))
            
            # Create reporting_staging table (SQLite compatible)
            connection.execute(text("""
                CREATE TABLE reporting_staging (
                    deal_id TEXT NOT NULL,
                    date_recorded TEXT NOT NULL,
                    deal_name TEXT NOT NULL,
                    core_dsp_audience_segment TEXT,
                    core_dsp_placement TEXT,
                    core_dsp_creative TEXT,
                    purchase_type TEXT NOT NULL,
                    total_impressions REAL NOT NULL,
                    processing_batch_id TEXT NOT NULL,
                    record_classification TEXT NOT NULL,
                    source_row_number INTEGER NOT NULL,
                    validation_errors TEXT,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT,
                    PRIMARY KEY (deal_id, date_recorded)
                )
            """))
            
            # Create indexes (SQLite compatible)
            connection.execute(text("CREATE INDEX idx_campaigns_staging_batch_id ON campaigns_staging (processing_batch_id)"))
            connection.execute(text("CREATE INDEX idx_campaigns_staging_buyer ON campaigns_staging (buyer)"))
            connection.execute(text("CREATE INDEX idx_campaigns_staging_runtime_dates ON campaigns_staging (start_date, end_date)"))
            connection.execute(text("CREATE INDEX idx_campaigns_staging_classification ON campaigns_staging (record_classification)"))
            
            connection.execute(text("CREATE INDEX idx_reporting_staging_batch_id ON reporting_staging (processing_batch_id)"))
            connection.execute(text("CREATE INDEX idx_reporting_staging_purchase_type ON reporting_staging (purchase_type)"))
            connection.execute(text("CREATE INDEX idx_reporting_staging_date_recorded ON reporting_staging (date_recorded)"))
            
            connection.commit()
            
            migration_end = datetime.utcnow()
            
            return {
                'success': True,
                'migration_id': '001',
                'migration_name': 'create_staging_tables',
                'schema_version_from': '0',
                'schema_version_to': '001',
                'tables_created': ['campaigns_staging', 'reporting_staging'],
                'indexes_created': 7,
                'enums_created': [],
                'execution_time_seconds': (migration_end - migration_start).total_seconds(),
                'executed_at': migration_start.isoformat(),
                'error_message': None
            }
            
    except Exception as e:
        migration_end = datetime.utcnow()
        
        return {
            'success': False,
            'migration_id': '001',
            'migration_name': 'create_staging_tables',
            'schema_version_from': '0',
            'schema_version_to': '001',
            'tables_created': [],
            'indexes_created': 0,
            'enums_created': [],
            'execution_time_seconds': (migration_end - migration_start).total_seconds(),
            'executed_at': migration_start.isoformat(),
            'error_message': str(e)
        }


def run_rollback_migration(engine: Engine) -> Dict[str, Any]:
    """Execute rollback migration (SQLite compatible)."""
    migration_start = datetime.utcnow()
    
    try:
        with engine.connect() as connection:
            # Drop indexes first
            connection.execute(text("DROP INDEX IF EXISTS idx_campaigns_staging_batch_id"))
            connection.execute(text("DROP INDEX IF EXISTS idx_campaigns_staging_buyer"))
            connection.execute(text("DROP INDEX IF EXISTS idx_campaigns_staging_runtime_dates"))
            connection.execute(text("DROP INDEX IF EXISTS idx_campaigns_staging_classification"))
            connection.execute(text("DROP INDEX IF EXISTS idx_reporting_staging_batch_id"))
            connection.execute(text("DROP INDEX IF EXISTS idx_reporting_staging_purchase_type"))
            connection.execute(text("DROP INDEX IF EXISTS idx_reporting_staging_date_recorded"))
            
            # Drop tables
            connection.execute(text("DROP TABLE IF EXISTS reporting_staging"))
            connection.execute(text("DROP TABLE IF EXISTS campaigns_staging"))
            
            connection.commit()
            
            migration_end = datetime.utcnow()
            
            return {
                'success': True,
                'migration_id': '001_rollback',
                'migration_name': 'rollback_staging_tables',
                'schema_version_from': '001',
                'schema_version_to': '0',
                'tables_dropped': ['campaigns_staging', 'reporting_staging'],
                'indexes_dropped': 7,
                'enums_dropped': [],
                'execution_time_seconds': (migration_end - migration_start).total_seconds(),
                'executed_at': migration_start.isoformat(),
                'error_message': None
            }
            
    except Exception as e:
        migration_end = datetime.utcnow()
        
        return {
            'success': False,
            'migration_id': '001_rollback',
            'migration_name': 'rollback_staging_tables',  
            'schema_version_from': '001',
            'schema_version_to': '0',
            'tables_dropped': [],
            'indexes_dropped': 0,
            'enums_dropped': [],
            'execution_time_seconds': (migration_end - migration_start).total_seconds(),
            'executed_at': migration_start.isoformat(),
            'error_message': str(e)
        }