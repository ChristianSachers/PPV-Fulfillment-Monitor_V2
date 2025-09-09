"""
Test rollback migration script - SQLite compatible version for unit testing.
This is a simplified version of the PostgreSQL rollback migration for testing purposes.
"""

from datetime import datetime
from sqlalchemy import text, Engine
from typing import Dict, Any


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
                'triggers_dropped': [],
                'functions_dropped': [],
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
            'triggers_dropped': [],
            'functions_dropped': [],
            'execution_time_seconds': (migration_end - migration_start).total_seconds(),
            'executed_at': migration_start.isoformat(),
            'error_message': str(e)
        }


def run_forward_migration(engine: Engine) -> Dict[str, Any]:
    """Dummy forward migration for testing."""
    return {
        'success': False,
        'migration_id': '001_rollback',
        'migration_name': 'rollback_staging_tables',
        'schema_version_from': '0',
        'schema_version_to': '001',
        'tables_created': [],
        'indexes_created': 0,
        'enums_created': [],
        'execution_time_seconds': 0.0,
        'executed_at': datetime.utcnow().isoformat(),
        'error_message': 'This is a rollback migration file'
    }