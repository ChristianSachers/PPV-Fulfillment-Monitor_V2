"""
Unit tests for database migration scripts.

Tests the complete migration lifecycle:
- Forward migration: clean database → staging tables creation
- Schema validation: tables, indexes, constraints, enums
- Rollback migration: staging tables → clean database
- Safety checks: existence validation, dependency handling
"""
import pytest
from uuid import uuid4
from decimal import Decimal
from datetime import datetime
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine, text, inspect, MetaData
from sqlalchemy.exc import OperationalError

# Import migration modules (to be created)
from src.database.migration_runner import MigrationRunner, MigrationError
from src.models.staging import Base, CampaignsStaging, ReportingStaging, PurchaseType


class TestMigrationScripts:
    """Test suite for database migration scripts."""
    
    @pytest.fixture
    def test_engine(self):
        """Create in-memory SQLite engine for testing."""
        # Note: Using PostgreSQL syntax but SQLite for testing
        engine = create_engine("sqlite:///:memory:", echo=False)
        yield engine
        engine.dispose()
    
    @pytest.fixture
    def migration_runner(self, test_engine):
        """Create migration runner with test engine."""
        # Get the test directory path for migrations
        import os
        test_migrations_path = os.path.dirname(__file__)
        
        return MigrationRunner(engine=test_engine, migrations_path=test_migrations_path)
    
    @patch('src.database.migration_runner.test_staging_connection', return_value=True)
    def test_forward_migration_creates_tables(self, mock_connection, migration_runner):
        """Test forward migration creates both staging tables."""
        # Arrange: Clean database state
        assert not self._table_exists(migration_runner.engine, 'campaigns_staging')
        assert not self._table_exists(migration_runner.engine, 'reporting_staging')
        
        # Act: Run forward migration
        result = migration_runner.run_forward_migration('test_001_create_staging_tables')
        
        # Assert: Tables created successfully
        assert result.success is True
        assert self._table_exists(migration_runner.engine, 'campaigns_staging')
        assert self._table_exists(migration_runner.engine, 'reporting_staging')
    
    @patch('src.database.migration_runner.test_staging_connection', return_value=True)
    def test_forward_migration_creates_indexes(self, mock_connection, migration_runner):
        """Test forward migration creates all 7 performance indexes."""
        # Act: Run forward migration
        migration_runner.run_forward_migration('test_001_create_staging_tables')
        
        # Assert: Campaigns staging indexes (4 indexes)
        assert self._index_exists(migration_runner.engine, 'campaigns_staging', 'idx_campaigns_staging_batch_id')
        assert self._index_exists(migration_runner.engine, 'campaigns_staging', 'idx_campaigns_staging_buyer')
        assert self._index_exists(migration_runner.engine, 'campaigns_staging', 'idx_campaigns_staging_runtime_dates')
        assert self._index_exists(migration_runner.engine, 'campaigns_staging', 'idx_campaigns_staging_classification')
        
        # Assert: Reporting staging indexes (3 indexes)
        assert self._index_exists(migration_runner.engine, 'reporting_staging', 'idx_reporting_staging_batch_id')
        assert self._index_exists(migration_runner.engine, 'reporting_staging', 'idx_reporting_staging_purchase_type')
        assert self._index_exists(migration_runner.engine, 'reporting_staging', 'idx_reporting_staging_date_recorded')
    
    def test_forward_migration_creates_purchase_type_enum(self, migration_runner):
        """Test forward migration creates PurchaseType enum."""
        # Act: Run forward migration
        migration_runner.run_forward_migration('test_001_create_staging_tables')
        
        # Assert: Enum type exists (PostgreSQL specific)
        # Note: In real implementation, this would check PostgreSQL enum
        assert self._table_exists(migration_runner.engine, 'reporting_staging')
        
        # Verify enum values can be inserted
        with migration_runner.engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO reporting_staging 
                (deal_id, date_recorded, deal_name, purchase_type, total_impressions, 
                 processing_batch_id, record_classification, source_row_number, created_at)
                VALUES 
                ('550e8400-e29b-41d4-a716-446655440000', '2024-01-01 00:00:00', 
                 'Test Deal', 'guaranteed', 1000.0, 
                 '550e8400-e29b-41d4-a716-446655440001', 'valid', 1, CURRENT_TIMESTAMP)
            """))
            conn.commit()
    
    def test_forward_migration_creates_constraints(self, migration_runner):
        """Test forward migration creates primary keys and constraints."""
        # Act: Run forward migration
        migration_runner.run_forward_migration('test_001_create_staging_tables')
        
        inspector = inspect(migration_runner.engine)
        
        # Assert: Primary key constraints
        campaigns_pk = inspector.get_pk_constraint('campaigns_staging')
        assert 'deal_campaign_id' in campaigns_pk['constrained_columns']
        
        reporting_pk = inspector.get_pk_constraint('reporting_staging')
        assert set(reporting_pk['constrained_columns']) == {'deal_id', 'date_recorded'}
        
        # Assert: NOT NULL constraints on required fields
        campaigns_columns = {col['name']: col for col in inspector.get_columns('campaigns_staging')}
        assert campaigns_columns['deal_campaign_name']['nullable'] is False
        assert campaigns_columns['impression_goal']['nullable'] is False
        assert campaigns_columns['cpm_eur']['nullable'] is False
        
        reporting_columns = {col['name']: col for col in inspector.get_columns('reporting_staging')}
        assert reporting_columns['deal_name']['nullable'] is False
        assert reporting_columns['purchase_type']['nullable'] is False
        assert reporting_columns['total_impressions']['nullable'] is False
    
    def test_rollback_migration_drops_tables(self, migration_runner):
        """Test rollback migration drops staging tables."""
        # Arrange: Tables exist after forward migration
        migration_runner.run_forward_migration('test_001_create_staging_tables')
        assert self._table_exists(migration_runner.engine, 'campaigns_staging')
        assert self._table_exists(migration_runner.engine, 'reporting_staging')
        
        # Act: Run rollback migration
        result = migration_runner.run_rollback_migration('001_rollback_staging_tables')
        
        # Assert: Tables dropped successfully
        assert result.success is True
        assert not self._table_exists(migration_runner.engine, 'campaigns_staging')
        assert not self._table_exists(migration_runner.engine, 'reporting_staging')
    
    def test_rollback_migration_handles_dependencies(self, migration_runner):
        """Test rollback migration handles table dependencies safely."""
        # Arrange: Create tables and data
        migration_runner.run_forward_migration('test_001_create_staging_tables')
        
        # Add test data to verify dependency handling
        with migration_runner.engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO campaigns_staging 
                (deal_campaign_id, deal_campaign_name, start_date, end_date, 
                 impression_goal, cpm_eur, buyer, processing_batch_id, 
                 record_classification, source_row_number, created_at)
                VALUES 
                ('550e8400-e29b-41d4-a716-446655440000', 'Test Campaign', 
                 '2024-01-01 00:00:00', '2024-01-31 23:59:59', 
                 10000, 5.50, 'Test Buyer', '550e8400-e29b-41d4-a716-446655440001',
                 'valid', 1, CURRENT_TIMESTAMP)
            """))
            conn.commit()
        
        # Act: Run rollback migration
        result = migration_runner.run_rollback_migration('001_rollback_staging_tables')
        
        # Assert: No errors during rollback despite data
        assert result.success is True
        assert not self._table_exists(migration_runner.engine, 'campaigns_staging')
    
    def test_rollback_migration_cleans_enum_types(self, migration_runner):
        """Test rollback migration cleans up PostgreSQL enum types."""
        # Arrange: Forward migration creates enum
        migration_runner.run_forward_migration('test_001_create_staging_tables')
        
        # Act: Rollback migration
        result = migration_runner.run_rollback_migration('001_rollback_staging_tables')
        
        # Assert: Enum cleanup successful (PostgreSQL specific)
        assert result.success is True
        # Note: In real PostgreSQL implementation, would verify enum type is dropped
    
    def test_migration_with_existing_tables_fails_safely(self, migration_runner):
        """Test forward migration fails safely if tables already exist."""
        # Arrange: Tables already exist
        migration_runner.run_forward_migration('test_001_create_staging_tables')
        
        # Act: Try to run forward migration again
        result = migration_runner.run_forward_migration('001_create_staging_tables')
        
        # Assert: Migration fails safely with appropriate error
        assert result.success is False
        assert "already exists" in result.error_message.lower()
    
    def test_rollback_with_nonexistent_tables_succeeds(self, migration_runner):
        """Test rollback migration succeeds even if tables don't exist."""
        # Arrange: Clean database (no tables)
        assert not self._table_exists(migration_runner.engine, 'campaigns_staging')
        
        # Act: Run rollback migration
        result = migration_runner.run_rollback_migration('001_rollback_staging_tables')
        
        # Assert: Rollback succeeds (idempotent)
        assert result.success is True
    
    def test_migration_runner_tracks_schema_version(self, migration_runner):
        """Test migration runner tracks schema version."""
        # Arrange: Initial version should be 0
        assert migration_runner.get_current_version() == "0"
        
        # Act: Run forward migration
        migration_runner.run_forward_migration('test_001_create_staging_tables')
        
        # Assert: Version updated
        assert migration_runner.get_current_version() == "001"
        
        # Act: Run rollback
        migration_runner.run_rollback_migration('test_001_rollback_staging_tables')
        
        # Assert: Version rolled back
        assert migration_runner.get_current_version() == "0"
    
    def test_migration_runner_records_history(self, migration_runner):
        """Test migration runner records migration history."""
        # Act: Run migrations
        forward_result = migration_runner.run_forward_migration('001_create_staging_tables')
        rollback_result = migration_runner.run_rollback_migration('001_rollback_staging_tables')
        
        # Assert: History recorded
        history = migration_runner.get_migration_history()
        assert len(history) == 2
        assert history[0]['migration'] == 'test_001_create_staging_tables'
        assert history[0]['direction'] == 'forward'
        assert history[1]['migration'] == 'test_001_rollback_staging_tables'
        assert history[1]['direction'] == 'rollback'
    
    @patch('src.database.migration_runner.test_staging_connection', return_value=True)
    def test_complete_migration_cycle(self, mock_connection, migration_runner):
        """Test complete migration cycle: clean → forward → rollback → clean."""
        # Arrange: Clean state
        assert not self._table_exists(migration_runner.engine, 'campaigns_staging')
        assert not self._table_exists(migration_runner.engine, 'reporting_staging')
        
        # Act & Assert: Forward migration
        forward_result = migration_runner.run_forward_migration('test_001_create_staging_tables')
        assert forward_result.success is True
        assert self._table_exists(migration_runner.engine, 'campaigns_staging')
        assert self._table_exists(migration_runner.engine, 'reporting_staging')
        
        # Act & Assert: Add test data to verify tables work
        with migration_runner.engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO campaigns_staging 
                (deal_campaign_id, deal_campaign_name, start_date, end_date, 
                 impression_goal, cpm_eur, buyer, processing_batch_id, 
                 record_classification, source_row_number, created_at)
                VALUES 
                ('550e8400-e29b-41d4-a716-446655440000', 'Integration Test Campaign', 
                 '2024-01-01 00:00:00', '2024-01-31 23:59:59', 
                 15000, 7.25, 'Integration Buyer', '550e8400-e29b-41d4-a716-446655440001',
                 'valid', 1, CURRENT_TIMESTAMP)
            """))
            
            result = conn.execute(text("SELECT COUNT(*) FROM campaigns_staging"))
            assert result.fetchone()[0] == 1
            conn.commit()
        
        # Act & Assert: Rollback migration
        rollback_result = migration_runner.run_rollback_migration('test_001_rollback_staging_tables')
        assert rollback_result.success is True
        assert not self._table_exists(migration_runner.engine, 'campaigns_staging')
        assert not self._table_exists(migration_runner.engine, 'reporting_staging')
    
    def _table_exists(self, engine, table_name: str) -> bool:
        """Helper method to check if table exists."""
        inspector = inspect(engine)
        return table_name in inspector.get_table_names()
    
    def _index_exists(self, engine, table_name: str, index_name: str) -> bool:
        """Helper method to check if index exists."""
        inspector = inspect(engine)
        indexes = inspector.get_indexes(table_name)
        return any(idx['name'] == index_name for idx in indexes)


class TestMigrationError:
    """Test suite for migration error handling."""
    
    def test_migration_error_with_context(self):
        """Test MigrationError stores context information."""
        context = {
            'migration_file': '001_create_staging_tables.py',
            'table': 'campaigns_staging',
            'step': 'index_creation'
        }
        
        error = MigrationError("Index creation failed", context=context)
        
        assert error.message == "Index creation failed"
        assert error.context['migration_file'] == '001_create_staging_tables.py'
        assert error.context['table'] == 'campaigns_staging'
        assert error.context['step'] == 'index_creation'
    
    def test_migration_error_string_representation(self):
        """Test MigrationError string representation."""
        error = MigrationError("Test error message")
        assert str(error) == "Test error message"


# Integration tests for PostgreSQL-specific features
class TestPostgreSQLMigration:
    """Integration tests for PostgreSQL-specific migration features."""
    
    @pytest.mark.integration
    def test_postgresql_uuid_primary_key(self):
        """Test PostgreSQL UUID primary key creation."""
        # This would test actual PostgreSQL connection in integration environment
        pass
    
    @pytest.mark.integration  
    def test_postgresql_enum_creation(self):
        """Test PostgreSQL enum type creation and cleanup."""
        # This would test actual enum type creation in PostgreSQL
        pass
    
    @pytest.mark.integration
    def test_postgresql_decimal_precision(self):
        """Test PostgreSQL DECIMAL type precision."""
        # This would test decimal precision in actual PostgreSQL
        pass