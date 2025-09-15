"""
Database Migration: Add Phase 1.2 Extensions to Staging Tables
Migration ID: 002
Dependencies: 001_create_staging_tables.py

This migration adds Phase 1.2 extension columns to existing staging tables:
- phase_context VARCHAR(10) NULLABLE - Phase identifier ('1.1' or '1.2')  
- violation_details JSONB NULLABLE - Structured violation information
- flagged_for_review BOOLEAN NULLABLE - Review requirement flag
- variance_detected BOOLEAN NULLABLE - Change detection flag

All columns are nullable to maintain backward compatibility with Phase 1.1.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent.parent / 'backend'))

from src.database.staging_connection import create_staging_engine
from sqlalchemy import text, MetaData, Table
from sqlalchemy.exc import ProgrammingError


def upgrade():
    """Apply Phase 1.2 extension migration."""
    print("🔄 Starting Phase 1.2 extension migration...")
    
    engine = create_staging_engine()
    
    try:
        with engine.connect() as connection:
            # Begin transaction
            trans = connection.begin()
            
            try:
                # Add Phase 1.2 columns to campaigns_staging table
                print("📊 Adding Phase 1.2 columns to campaigns_staging table...")
                
                connection.execute(text("""
                    ALTER TABLE campaigns_staging 
                    ADD COLUMN IF NOT EXISTS phase_context VARCHAR(10) NULL
                """))
                
                connection.execute(text("""
                    ALTER TABLE campaigns_staging 
                    ADD COLUMN IF NOT EXISTS violation_details JSONB NULL
                """))
                
                connection.execute(text("""
                    ALTER TABLE campaigns_staging 
                    ADD COLUMN IF NOT EXISTS flagged_for_review BOOLEAN NULL
                """))
                
                connection.execute(text("""
                    ALTER TABLE campaigns_staging 
                    ADD COLUMN IF NOT EXISTS variance_detected BOOLEAN NULL
                """))
                
                # Add Phase 1.2 columns to reporting_staging table
                print("📊 Adding Phase 1.2 columns to reporting_staging table...")
                
                connection.execute(text("""
                    ALTER TABLE reporting_staging 
                    ADD COLUMN IF NOT EXISTS phase_context VARCHAR(10) NULL
                """))
                
                connection.execute(text("""
                    ALTER TABLE reporting_staging 
                    ADD COLUMN IF NOT EXISTS violation_details JSONB NULL
                """))
                
                connection.execute(text("""
                    ALTER TABLE reporting_staging 
                    ADD COLUMN IF NOT EXISTS flagged_for_review BOOLEAN NULL
                """))
                
                connection.execute(text("""
                    ALTER TABLE reporting_staging 
                    ADD COLUMN IF NOT EXISTS variance_detected BOOLEAN NULL
                """))
                
                # Add Phase 1.2 performance indexes
                print("🔍 Creating Phase 1.2 performance indexes...")
                
                # Index for campaigns staging phase context
                connection.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_campaigns_staging_phase_context 
                    ON campaigns_staging (phase_context)
                """))
                
                # Index for reporting staging phase context
                connection.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_reporting_staging_phase_context 
                    ON reporting_staging (phase_context)
                """))
                
                # Commit transaction
                trans.commit()
                print("✅ Phase 1.2 extension migration completed successfully!")
                
                # Verify migration
                verify_migration(connection)
                
            except Exception as e:
                trans.rollback()
                raise e
                
    except Exception as e:
        print(f"❌ Migration failed: {str(e)}")
        raise e
    finally:
        engine.dispose()


def downgrade():
    """Rollback Phase 1.2 extension migration."""
    print("🔄 Rolling back Phase 1.2 extension migration...")
    
    engine = create_staging_engine()
    
    try:
        with engine.connect() as connection:
            # Begin transaction
            trans = connection.begin()
            
            try:
                # Drop Phase 1.2 indexes
                print("🗑️ Dropping Phase 1.2 indexes...")
                
                connection.execute(text("""
                    DROP INDEX IF EXISTS idx_campaigns_staging_phase_context
                """))
                
                connection.execute(text("""
                    DROP INDEX IF EXISTS idx_reporting_staging_phase_context
                """))
                
                # Remove Phase 1.2 columns from campaigns_staging
                print("🗑️ Removing Phase 1.2 columns from campaigns_staging...")
                
                connection.execute(text("""
                    ALTER TABLE campaigns_staging 
                    DROP COLUMN IF EXISTS phase_context
                """))
                
                connection.execute(text("""
                    ALTER TABLE campaigns_staging 
                    DROP COLUMN IF EXISTS violation_details
                """))
                
                connection.execute(text("""
                    ALTER TABLE campaigns_staging 
                    DROP COLUMN IF EXISTS flagged_for_review
                """))
                
                connection.execute(text("""
                    ALTER TABLE campaigns_staging 
                    DROP COLUMN IF EXISTS variance_detected
                """))
                
                # Remove Phase 1.2 columns from reporting_staging
                print("🗑️ Removing Phase 1.2 columns from reporting_staging...")
                
                connection.execute(text("""
                    ALTER TABLE reporting_staging 
                    DROP COLUMN IF EXISTS phase_context
                """))
                
                connection.execute(text("""
                    ALTER TABLE reporting_staging 
                    DROP COLUMN IF EXISTS violation_details
                """))
                
                connection.execute(text("""
                    ALTER TABLE reporting_staging 
                    DROP COLUMN IF EXISTS flagged_for_review
                """))
                
                connection.execute(text("""
                    ALTER TABLE reporting_staging 
                    DROP COLUMN IF EXISTS variance_detected
                """))
                
                # Commit transaction
                trans.commit()
                print("✅ Phase 1.2 extension rollback completed successfully!")
                
            except Exception as e:
                trans.rollback()
                raise e
                
    except Exception as e:
        print(f"❌ Rollback failed: {str(e)}")
        raise e
    finally:
        engine.dispose()


def verify_migration(connection):
    """Verify the migration was applied successfully."""
    print("🔍 Verifying Phase 1.2 extension migration...")
    
    # Check campaigns_staging columns
    result = connection.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'campaigns_staging' 
        AND column_name IN ('phase_context', 'violation_details', 'flagged_for_review', 'variance_detected')
        ORDER BY column_name
    """))
    
    campaigns_columns = [row[0] for row in result.fetchall()]
    expected_columns = ['flagged_for_review', 'phase_context', 'variance_detected', 'violation_details']
    
    if set(campaigns_columns) != set(expected_columns):
        raise Exception(f"campaigns_staging columns verification failed. Expected: {expected_columns}, Found: {campaigns_columns}")
    
    # Check reporting_staging columns
    result = connection.execute(text("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name = 'reporting_staging' 
        AND column_name IN ('phase_context', 'violation_details', 'flagged_for_review', 'variance_detected')
        ORDER BY column_name
    """))
    
    reporting_columns = [row[0] for row in result.fetchall()]
    
    if set(reporting_columns) != set(expected_columns):
        raise Exception(f"reporting_staging columns verification failed. Expected: {expected_columns}, Found: {reporting_columns}")
    
    # Check indexes
    result = connection.execute(text("""
        SELECT indexname 
        FROM pg_indexes 
        WHERE indexname IN ('idx_campaigns_staging_phase_context', 'idx_reporting_staging_phase_context')
        ORDER BY indexname
    """))
    
    indexes = [row[0] for row in result.fetchall()]
    expected_indexes = ['idx_campaigns_staging_phase_context', 'idx_reporting_staging_phase_context']
    
    if set(indexes) != set(expected_indexes):
        raise Exception(f"Index verification failed. Expected: {expected_indexes}, Found: {indexes}")
    
    print("✅ Phase 1.2 extension migration verification successful!")
    print(f"   - Added {len(expected_columns)} columns to campaigns_staging")
    print(f"   - Added {len(expected_columns)} columns to reporting_staging") 
    print(f"   - Created {len(expected_indexes)} performance indexes")


def get_migration_info():
    """Get information about this migration."""
    return {
        'id': '002',
        'name': 'add_phase_12_extensions',
        'description': 'Add Phase 1.2 extension columns to staging tables',
        'dependencies': ['001_create_staging_tables'],
        'tables_modified': ['campaigns_staging', 'reporting_staging'],
        'columns_added': ['phase_context', 'violation_details', 'flagged_for_review', 'variance_detected'],
        'indexes_created': ['idx_campaigns_staging_phase_context', 'idx_reporting_staging_phase_context'],
        'backward_compatible': True
    }


if __name__ == "__main__":
    """Run migration directly."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Phase 1.2 Extension Migration')
    parser.add_argument('action', choices=['upgrade', 'downgrade', 'info'], 
                       help='Migration action to perform')
    
    args = parser.parse_args()
    
    if args.action == 'upgrade':
        upgrade()
    elif args.action == 'downgrade':
        downgrade()
    elif args.action == 'info':
        info = get_migration_info()
        print(f"Migration {info['id']}: {info['name']}")
        print(f"Description: {info['description']}")
        print(f"Dependencies: {info['dependencies']}")
        print(f"Tables Modified: {info['tables_modified']}")
        print(f"Columns Added: {info['columns_added']}")
        print(f"Indexes Created: {info['indexes_created']}")
        print(f"Backward Compatible: {info['backward_compatible']}")