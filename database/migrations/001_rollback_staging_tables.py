"""
Rollback migration script: Drop staging tables infrastructure.

Migration: 001_rollback_staging_tables
Purpose: Clean rollback of campaigns_staging and reporting_staging tables
Date: 2024-09-09
Schema Version: 001 → 0

Tables Dropped:
- campaigns_staging: Campaign data staging table
- reporting_staging: Reporting data staging table
- purchase_type: Enum type cleanup

Features:
- Safe dependency handling with CASCADE
- Existence checks for idempotent operations
- PostgreSQL enum type cleanup
- Trigger and function cleanup
- Complete infrastructure removal
"""

from datetime import datetime
from sqlalchemy import text, Engine
from typing import Dict, Any

# Migration metadata
MIGRATION_ID = "001_rollback"
MIGRATION_NAME = "rollback_staging_tables"
MIGRATION_DESCRIPTION = "Drop staging tables infrastructure"
SCHEMA_VERSION_FROM = "001"
SCHEMA_VERSION_TO = "0"


def get_rollback_migration_sql() -> str:
    """Get the complete rollback migration SQL."""
    return """
-- =====================================================
-- Rollback Migration: Drop Staging Tables
-- Migration ID: 001_rollback
-- Schema Version: 001 → 0
-- =====================================================

-- Drop triggers first (dependency handling)
DROP TRIGGER IF EXISTS update_campaigns_staging_updated_at ON campaigns_staging;
DROP TRIGGER IF EXISTS update_reporting_staging_updated_at ON reporting_staging;

-- Drop the trigger function (only if no other triggers use it)
DROP FUNCTION IF EXISTS update_updated_at_column() CASCADE;

-- =====================================================
-- Drop Performance Indexes (7 total)
-- Safe with IF EXISTS for idempotent operations
-- =====================================================

-- Campaigns staging indexes (4 indexes)
DROP INDEX IF EXISTS idx_campaigns_staging_batch_id;
DROP INDEX IF EXISTS idx_campaigns_staging_buyer;
DROP INDEX IF EXISTS idx_campaigns_staging_runtime_dates;
DROP INDEX IF EXISTS idx_campaigns_staging_classification;

-- Reporting staging indexes (3 indexes)
DROP INDEX IF EXISTS idx_reporting_staging_batch_id;
DROP INDEX IF EXISTS idx_reporting_staging_purchase_type;
DROP INDEX IF EXISTS idx_reporting_staging_date_recorded;

-- =====================================================
-- Drop Tables with CASCADE for Safety
-- =====================================================

-- Drop reporting_staging table first (references enum)
DROP TABLE IF EXISTS reporting_staging CASCADE;

-- Drop campaigns_staging table
DROP TABLE IF EXISTS campaigns_staging CASCADE;

-- =====================================================
-- Drop PostgreSQL Enum Types
-- Must be done after tables that reference them
-- =====================================================

-- Drop purchase_type enum (safe with IF EXISTS)
DROP TYPE IF EXISTS purchase_type CASCADE;

-- =====================================================
-- Validation: Verify complete cleanup
-- =====================================================

-- Verify campaigns_staging table is dropped
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'campaigns_staging') THEN
        RAISE EXCEPTION 'Rollback failed: campaigns_staging table still exists';
    END IF;
END $$;

-- Verify reporting_staging table is dropped
DO $$
BEGIN
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'reporting_staging') THEN
        RAISE EXCEPTION 'Rollback failed: reporting_staging table still exists';
    END IF;
END $$;

-- Verify purchase_type enum is dropped
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_type WHERE typname = 'purchase_type') THEN
        RAISE EXCEPTION 'Rollback failed: purchase_type enum still exists';
    END IF;
END $$;

-- Verify all indexes are dropped
DO $$
DECLARE
    remaining_indexes INTEGER;
BEGIN
    SELECT COUNT(*) INTO remaining_indexes
    FROM pg_indexes 
    WHERE indexname IN (
        'idx_campaigns_staging_batch_id',
        'idx_campaigns_staging_buyer', 
        'idx_campaigns_staging_runtime_dates',
        'idx_campaigns_staging_classification',
        'idx_reporting_staging_batch_id',
        'idx_reporting_staging_purchase_type',
        'idx_reporting_staging_date_recorded'
    );
    
    IF remaining_indexes > 0 THEN
        RAISE EXCEPTION 'Rollback failed: % staging indexes still exist', remaining_indexes;
    END IF;
END $$;

-- =====================================================
-- Additional Cleanup: Remove any orphaned objects
-- =====================================================

-- Clean up any remaining constraints that might reference staging tables
DO $$
DECLARE
    constraint_record RECORD;
BEGIN
    FOR constraint_record IN 
        SELECT constraint_name, table_name
        FROM information_schema.table_constraints 
        WHERE constraint_name LIKE '%staging%'
    LOOP
        EXECUTE format('DROP CONSTRAINT IF EXISTS %I ON %I CASCADE', 
                      constraint_record.constraint_name, 
                      constraint_record.table_name);
    END LOOP;
END $$;

-- Clean up any remaining sequences related to staging tables
DROP SEQUENCE IF EXISTS campaigns_staging_id_seq CASCADE;
DROP SEQUENCE IF EXISTS reporting_staging_id_seq CASCADE;

-- =====================================================
-- Final Validation: Database State Clean
-- =====================================================

-- Ensure no staging-related objects remain
DO $$
DECLARE
    staging_objects INTEGER;
BEGIN
    -- Count any remaining staging-related objects
    SELECT COUNT(*) INTO staging_objects
    FROM (
        -- Check for tables
        SELECT table_name FROM information_schema.tables 
        WHERE table_name LIKE '%staging%'
        
        UNION ALL
        
        -- Check for indexes
        SELECT indexname FROM pg_indexes 
        WHERE indexname LIKE '%staging%'
        
        UNION ALL
        
        -- Check for types
        SELECT typname FROM pg_type 
        WHERE typname LIKE '%staging%' OR typname = 'purchase_type'
        
        UNION ALL
        
        -- Check for constraints
        SELECT constraint_name FROM information_schema.table_constraints 
        WHERE constraint_name LIKE '%staging%'
    ) AS staging_check;
    
    IF staging_objects > 0 THEN
        RAISE WARNING 'Rollback completed but % staging-related objects may still exist', staging_objects;
    END IF;
END $$;

-- Rollback completed successfully
SELECT 'Migration rollback 001_rollback_staging_tables completed successfully' AS rollback_result;
"""


def run_rollback_migration(engine: Engine) -> Dict[str, Any]:
    """
    Execute the rollback migration.
    
    Args:
        engine: SQLAlchemy engine for database connection
        
    Returns:
        Dict containing migration result and metadata
    """
    migration_start = datetime.utcnow()
    
    try:
        with engine.connect() as connection:
            # Execute the complete rollback SQL
            connection.execute(text(get_rollback_migration_sql()))
            connection.commit()
            
            # Verify rollback success - ensure tables are gone
            result = connection.execute(
                text("SELECT COUNT(*) FROM information_schema.tables WHERE table_name IN ('campaigns_staging', 'reporting_staging')")
            )
            remaining_tables = result.fetchone()[0]
            
            if remaining_tables > 0:
                raise Exception(f"Rollback incomplete: {remaining_tables} staging tables still exist")
            
            # Verify enum cleanup
            result = connection.execute(
                text("SELECT COUNT(*) FROM pg_type WHERE typname = 'purchase_type'")
            )
            remaining_enums = result.fetchone()[0]
            
            if remaining_enums > 0:
                raise Exception("Rollback incomplete: purchase_type enum still exists")
            
            # Verify index cleanup
            result = connection.execute(
                text("""
                    SELECT COUNT(*) FROM pg_indexes 
                    WHERE indexname IN (
                        'idx_campaigns_staging_batch_id',
                        'idx_campaigns_staging_buyer', 
                        'idx_campaigns_staging_runtime_dates',
                        'idx_campaigns_staging_classification',
                        'idx_reporting_staging_batch_id',
                        'idx_reporting_staging_purchase_type',
                        'idx_reporting_staging_date_recorded'
                    )
                """)
            )
            remaining_indexes = result.fetchone()[0]
            
            if remaining_indexes > 0:
                raise Exception(f"Rollback incomplete: {remaining_indexes} staging indexes still exist")
            
            migration_end = datetime.utcnow()
            
            return {
                'success': True,
                'migration_id': MIGRATION_ID,
                'migration_name': MIGRATION_NAME,
                'schema_version_from': SCHEMA_VERSION_FROM,
                'schema_version_to': SCHEMA_VERSION_TO,
                'tables_dropped': ['campaigns_staging', 'reporting_staging'],
                'indexes_dropped': 7,
                'enums_dropped': ['purchase_type'],
                'triggers_dropped': ['update_campaigns_staging_updated_at', 'update_reporting_staging_updated_at'],
                'functions_dropped': ['update_updated_at_column'],
                'execution_time_seconds': (migration_end - migration_start).total_seconds(),
                'executed_at': migration_start.isoformat(),
                'error_message': None
            }
            
    except Exception as e:
        migration_end = datetime.utcnow()
        
        return {
            'success': False,
            'migration_id': MIGRATION_ID,
            'migration_name': MIGRATION_NAME,
            'schema_version_from': SCHEMA_VERSION_FROM,
            'schema_version_to': SCHEMA_VERSION_TO,
            'tables_dropped': [],
            'indexes_dropped': 0,
            'enums_dropped': [],
            'triggers_dropped': [],
            'functions_dropped': [],
            'execution_time_seconds': (migration_end - migration_start).total_seconds(),
            'executed_at': migration_start.isoformat(),
            'error_message': str(e)
        }


def validate_rollback_complete(engine: Engine) -> bool:
    """
    Validate that rollback migration completed successfully.
    
    Args:
        engine: SQLAlchemy engine for database connection
        
    Returns:
        bool: True if rollback is complete, False otherwise
    """
    with engine.connect() as connection:
        # Check no staging tables remain
        result = connection.execute(text("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_name IN ('campaigns_staging', 'reporting_staging')
        """))
        
        if result.fetchone()[0] > 0:
            return False
        
        # Check no staging indexes remain
        result = connection.execute(text("""
            SELECT COUNT(*) FROM pg_indexes 
            WHERE indexname LIKE '%staging%'
        """))
        
        if result.fetchone()[0] > 0:
            return False
        
        # Check purchase_type enum is dropped
        result = connection.execute(text("""
            SELECT COUNT(*) FROM pg_type 
            WHERE typname = 'purchase_type'
        """))
        
        if result.fetchone()[0] > 0:
            return False
        
        # Check no staging triggers remain
        result = connection.execute(text("""
            SELECT COUNT(*) FROM information_schema.triggers 
            WHERE trigger_name LIKE '%staging%'
        """))
        
        if result.fetchone()[0] > 0:
            return False
        
        return True


def get_staging_objects_summary(engine: Engine) -> Dict[str, int]:
    """
    Get summary of remaining staging-related objects (for debugging).
    
    Args:
        engine: SQLAlchemy engine for database connection
        
    Returns:
        Dict with counts of different object types
    """
    with engine.connect() as connection:
        summary = {}
        
        # Count tables
        result = connection.execute(text("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_name LIKE '%staging%'
        """))
        summary['tables'] = result.fetchone()[0]
        
        # Count indexes
        result = connection.execute(text("""
            SELECT COUNT(*) FROM pg_indexes 
            WHERE indexname LIKE '%staging%'
        """))
        summary['indexes'] = result.fetchone()[0]
        
        # Count enums
        result = connection.execute(text("""
            SELECT COUNT(*) FROM pg_type 
            WHERE typname IN ('purchase_type') OR typname LIKE '%staging%'
        """))
        summary['enums'] = result.fetchone()[0]
        
        # Count triggers
        result = connection.execute(text("""
            SELECT COUNT(*) FROM information_schema.triggers 
            WHERE trigger_name LIKE '%staging%'
        """))
        summary['triggers'] = result.fetchone()[0]
        
        # Count constraints
        result = connection.execute(text("""
            SELECT COUNT(*) FROM information_schema.table_constraints 
            WHERE constraint_name LIKE '%staging%'
        """))
        summary['constraints'] = result.fetchone()[0]
        
        return summary


# Utility functions for safe rollback operations
def safe_drop_table(engine: Engine, table_name: str) -> bool:
    """Safely drop a table if it exists."""
    try:
        with engine.connect() as connection:
            connection.execute(text(f"DROP TABLE IF EXISTS {table_name} CASCADE"))
            connection.commit()
            return True
    except Exception:
        return False


def safe_drop_enum(engine: Engine, enum_name: str) -> bool:
    """Safely drop an enum type if it exists."""
    try:
        with engine.connect() as connection:
            connection.execute(text(f"DROP TYPE IF EXISTS {enum_name} CASCADE"))
            connection.commit()
            return True
    except Exception:
        return False