"""
Forward migration script: Create staging tables infrastructure.

Migration: 001_create_staging_tables
Purpose: Create campaigns_staging and reporting_staging tables with full PostgreSQL optimization
Date: 2024-09-09
Schema Version: 0 → 001

Tables Created:
- campaigns_staging: Campaign data staging with UUID primary key
- reporting_staging: Reporting data staging with composite primary key (deal_id, date_recorded)

Features:
- PostgreSQL UUID, DECIMAL, TIMESTAMP types
- PurchaseType enum type
- 7 performance indexes (4 campaigns + 3 reporting)
- Audit timestamps with triggers
- Proper constraints and nullability
"""

from datetime import datetime
from sqlalchemy import text, Engine
from typing import Dict, Any

# Migration metadata
MIGRATION_ID = "001"
MIGRATION_NAME = "create_staging_tables"
MIGRATION_DESCRIPTION = "Create staging tables infrastructure"
SCHEMA_VERSION_FROM = "0"
SCHEMA_VERSION_TO = "001"


def get_forward_migration_sql() -> str:
    """Get the complete forward migration SQL."""
    return """
-- =====================================================
-- Forward Migration: Create Staging Tables
-- Migration ID: 001
-- Schema Version: 0 → 001
-- =====================================================

-- Create PurchaseType enum for reporting_staging
CREATE TYPE purchase_type AS ENUM ('guaranteed', 'unguaranteed');

-- Create campaigns_staging table
CREATE TABLE campaigns_staging (
    -- Primary key
    deal_campaign_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Campaign data fields
    deal_campaign_name VARCHAR(500) NOT NULL,
    start_date TIMESTAMP NOT NULL,
    end_date TIMESTAMP NOT NULL,
    impression_goal BIGINT NOT NULL,
    budget_eur DECIMAL(12, 2) NULL,  -- 8.7% null rate
    cpm_eur DECIMAL(8, 2) NOT NULL,
    buyer VARCHAR(100) NOT NULL,
    
    -- Staging metadata
    processing_batch_id UUID NOT NULL,
    record_classification VARCHAR(50) NOT NULL,
    source_row_number INTEGER NOT NULL,
    validation_errors TEXT NULL,
    
    -- Audit timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL
);

-- Create reporting_staging table with composite primary key
CREATE TABLE reporting_staging (
    -- Composite primary key
    deal_id UUID NOT NULL,
    date_recorded TIMESTAMP NOT NULL,
    PRIMARY KEY (deal_id, date_recorded),
    
    -- Reporting data fields
    deal_name VARCHAR(500) NOT NULL,
    core_dsp_audience_segment TEXT NULL,  -- 58% population rate
    core_dsp_placement TEXT NULL,
    core_dsp_creative TEXT NULL,
    purchase_type purchase_type NOT NULL,
    total_impressions DECIMAL(15, 6) NOT NULL,
    
    -- Staging metadata
    processing_batch_id UUID NOT NULL,
    record_classification VARCHAR(50) NOT NULL,
    source_row_number INTEGER NOT NULL,
    validation_errors TEXT NULL,
    
    -- Audit timestamps
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NULL
);

-- =====================================================
-- Performance Indexes (7 total)
-- =====================================================

-- Campaigns staging indexes (4 indexes)
CREATE INDEX idx_campaigns_staging_batch_id ON campaigns_staging (processing_batch_id);
CREATE INDEX idx_campaigns_staging_buyer ON campaigns_staging (buyer);
CREATE INDEX idx_campaigns_staging_runtime_dates ON campaigns_staging (start_date, end_date);
CREATE INDEX idx_campaigns_staging_classification ON campaigns_staging (record_classification);

-- Reporting staging indexes (3 indexes)
CREATE INDEX idx_reporting_staging_batch_id ON reporting_staging (processing_batch_id);
CREATE INDEX idx_reporting_staging_purchase_type ON reporting_staging (purchase_type);
CREATE INDEX idx_reporting_staging_date_recorded ON reporting_staging (date_recorded);

-- =====================================================
-- Audit Timestamp Triggers
-- =====================================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for automatic updated_at handling
CREATE TRIGGER update_campaigns_staging_updated_at 
    BEFORE UPDATE ON campaigns_staging 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_reporting_staging_updated_at 
    BEFORE UPDATE ON reporting_staging 
    FOR EACH ROW 
    EXECUTE FUNCTION update_updated_at_column();

-- =====================================================
-- Comments for Documentation
-- =====================================================

COMMENT ON TABLE campaigns_staging IS 'Staging table for campaign data processing and validation';
COMMENT ON TABLE reporting_staging IS 'Staging table for reporting data processing and validation';

COMMENT ON COLUMN campaigns_staging.deal_campaign_id IS 'UUID primary key for campaign staging records';
COMMENT ON COLUMN campaigns_staging.impression_goal IS 'Campaign impression goal (3K-720K range)';
COMMENT ON COLUMN campaigns_staging.budget_eur IS 'Campaign budget in EUR (nullable, 8.7% null rate)';
COMMENT ON COLUMN campaigns_staging.cpm_eur IS 'Cost per mille in EUR (€0.01-€45.00 range)';
COMMENT ON COLUMN campaigns_staging.processing_batch_id IS 'Batch ID for processing tracking';
COMMENT ON COLUMN campaigns_staging.record_classification IS 'Data validation classification';

COMMENT ON COLUMN reporting_staging.deal_id IS 'UUID deal identifier (part of composite PK)';
COMMENT ON COLUMN reporting_staging.date_recorded IS 'Recording date (part of composite PK)';
COMMENT ON COLUMN reporting_staging.core_dsp_audience_segment IS 'DSP audience segment (58% population rate)';
COMMENT ON COLUMN reporting_staging.purchase_type IS 'Purchase type: guaranteed or unguaranteed';
COMMENT ON COLUMN reporting_staging.total_impressions IS 'Total impressions (619-231M range)';

-- =====================================================
-- Validation: Verify tables and indexes created
-- =====================================================

-- Verify campaigns_staging table exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'campaigns_staging') THEN
        RAISE EXCEPTION 'Migration failed: campaigns_staging table not created';
    END IF;
END $$;

-- Verify reporting_staging table exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'reporting_staging') THEN
        RAISE EXCEPTION 'Migration failed: reporting_staging table not created';
    END IF;
END $$;

-- Verify purchase_type enum exists
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_type WHERE typname = 'purchase_type') THEN
        RAISE EXCEPTION 'Migration failed: purchase_type enum not created';
    END IF;
END $$;

-- Migration completed successfully
SELECT 'Migration 001_create_staging_tables completed successfully' AS migration_result;
"""


def run_forward_migration(engine: Engine) -> Dict[str, Any]:
    """
    Execute the forward migration.
    
    Args:
        engine: SQLAlchemy engine for database connection
        
    Returns:
        Dict containing migration result and metadata
    """
    migration_start = datetime.utcnow()
    
    try:
        with engine.connect() as connection:
            # Execute the complete migration SQL
            connection.execute(text(get_forward_migration_sql()))
            connection.commit()
            
            # Verify migration success
            result = connection.execute(
                text("SELECT COUNT(*) FROM information_schema.tables WHERE table_name IN ('campaigns_staging', 'reporting_staging')")
            )
            tables_created = result.fetchone()[0]
            
            if tables_created != 2:
                raise Exception(f"Expected 2 tables, found {tables_created}")
            
            # Verify indexes created
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
            indexes_created = result.fetchone()[0]
            
            if indexes_created != 7:
                raise Exception(f"Expected 7 indexes, found {indexes_created}")
            
            migration_end = datetime.utcnow()
            
            return {
                'success': True,
                'migration_id': MIGRATION_ID,
                'migration_name': MIGRATION_NAME,
                'schema_version_from': SCHEMA_VERSION_FROM,
                'schema_version_to': SCHEMA_VERSION_TO,
                'tables_created': ['campaigns_staging', 'reporting_staging'],
                'indexes_created': 7,
                'enums_created': ['purchase_type'],
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
            'tables_created': [],
            'indexes_created': 0,
            'enums_created': [],
            'execution_time_seconds': (migration_end - migration_start).total_seconds(),
            'executed_at': migration_start.isoformat(),
            'error_message': str(e)
        }


# Migration validation functions
def validate_campaigns_staging_schema(engine: Engine) -> bool:
    """Validate campaigns_staging table schema matches SQLAlchemy model."""
    with engine.connect() as connection:
        # Check column definitions
        result = connection.execute(text("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'campaigns_staging'
            ORDER BY ordinal_position
        """))
        
        columns = {row[0]: {'type': row[1], 'nullable': row[2] == 'YES', 'default': row[3]} 
                   for row in result.fetchall()}
        
        # Validate key columns exist with correct types
        required_columns = {
            'deal_campaign_id': 'uuid',
            'deal_campaign_name': 'character varying',
            'start_date': 'timestamp without time zone',
            'end_date': 'timestamp without time zone',
            'impression_goal': 'bigint',
            'budget_eur': 'numeric',
            'cpm_eur': 'numeric',
            'buyer': 'character varying',
            'processing_batch_id': 'uuid',
            'record_classification': 'character varying',
            'source_row_number': 'integer',
            'validation_errors': 'text',
            'created_at': 'timestamp without time zone',
            'updated_at': 'timestamp without time zone'
        }
        
        for col_name, expected_type in required_columns.items():
            if col_name not in columns:
                return False
            if expected_type not in columns[col_name]['type']:
                return False
        
        return True


def validate_reporting_staging_schema(engine: Engine) -> bool:
    """Validate reporting_staging table schema matches SQLAlchemy model."""
    with engine.connect() as connection:
        # Check composite primary key
        result = connection.execute(text("""
            SELECT constraint_name, column_name
            FROM information_schema.key_column_usage
            WHERE table_name = 'reporting_staging' AND constraint_name LIKE '%pkey'
            ORDER BY ordinal_position
        """))
        
        pk_columns = [row[1] for row in result.fetchall()]
        if set(pk_columns) != {'deal_id', 'date_recorded'}:
            return False
        
        # Check enum type usage
        result = connection.execute(text("""
            SELECT column_name, udt_name
            FROM information_schema.columns 
            WHERE table_name = 'reporting_staging' AND column_name = 'purchase_type'
        """))
        
        enum_info = result.fetchone()
        if not enum_info or enum_info[1] != 'purchase_type':
            return False
        
        return True