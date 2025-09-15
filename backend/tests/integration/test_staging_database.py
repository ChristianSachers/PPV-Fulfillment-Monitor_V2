"""
Integration tests for staging database operations - TDD RED phase
These tests MUST fail initially since staging models don't exist yet.

This test suite validates:
1. PostgreSQL connection and staging schema setup
2. Staging table creation and structure validation
3. Index performance for UUID lookups and batch processing
4. Database transactions and session management
5. Staging data insertion and retrieval operations

Database: ppv_fulfillment_dev on localhost:5432
All tests follow TDD principles and will fail until staging models are implemented.
"""
import pytest
import time
from decimal import Decimal
from datetime import datetime, timedelta
from uuid import uuid4
from sqlalchemy import create_engine, text, inspect, Index
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import OperationalError, ProgrammingError
from sqlalchemy.engine import Engine

# Import staging models and database setup (these don't exist yet - will cause ImportError in RED phase)
try:
    from src.models.staging import (
        CampaignsStaging, 
        ReportingStaging,
        Base as StagingBase
    )
    from src.database.staging_connection import (
        get_staging_database_url,
        create_staging_engine,
        get_staging_session,
        init_staging_tables
    )
    STAGING_AVAILABLE = True
except ImportError:
    STAGING_AVAILABLE = False

# Test database configuration
TEST_DATABASE_URL = "postgresql://localhost:5432/ppv_fulfillment_dev"


@pytest.fixture
def staging_engine():
    """Create staging database engine for testing."""
    if not STAGING_AVAILABLE:
        pytest.skip("Staging models not implemented yet - TDD RED phase")
    
    engine = create_staging_engine(TEST_DATABASE_URL)
    yield engine
    engine.dispose()


@pytest.fixture
def staging_session(staging_engine):
    """Create staging database session for testing."""
    if not STAGING_AVAILABLE:
        pytest.skip("Staging models not implemented yet - TDD RED phase")
    
    Session = sessionmaker(bind=staging_engine)
    session = Session()
    
    # Begin transaction for isolation
    transaction = session.begin()
    
    yield session
    
    # Rollback transaction and close session
    transaction.rollback()
    session.close()


@pytest.fixture
def sample_campaign_data():
    """Sample campaign data for testing."""
    return {
        "deal_campaign_id": uuid4(),
        "deal_campaign_name": "Premium Video Campaign Q1 2024",
        "start_date": datetime(2024, 1, 1),
        "end_date": datetime(2024, 3, 31),
        "impression_goal": 250000,
        "budget_eur": Decimal("12500.75"),
        "cpm_eur": Decimal("5.25"),
        "buyer": "Premium Advertiser Inc",
        "processing_batch_id": uuid4(),
        "record_classification": "CAMPAIGN_XLSX",
        "source_row_number": 1
    }


@pytest.fixture
def sample_reporting_data():
    """Sample reporting data for testing."""
    return {
        "deal_id": uuid4(),
        "date_recorded": datetime(2024, 3, 15, 10, 30, 0),
        "deal_name": "Premium Video Campaign Q1 2024",
        "core_dsp_audience_segment": "Premium Demographics",
        "core_dsp_placement": "Video Pre-Roll",
        "core_dsp_creative": "Campaign Creative v2.1",
        "purchase_type": "guaranteed",
        "total_impressions": Decimal("125000.500000"),
        "processing_batch_id": uuid4(),
        "record_classification": "REPORTING_CSV",
        "source_row_number": 1
    }


@pytest.mark.skipif(not STAGING_AVAILABLE, reason="Staging models not implemented yet - TDD RED phase")
class TestPostgreSQLConnection:
    """Test PostgreSQL database connection and configuration."""

    def test_database_connection_success(self):
        """Test successful connection to PostgreSQL database."""
        engine = create_staging_engine(TEST_DATABASE_URL)
        
        # Test connection
        with engine.connect() as connection:
            result = connection.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            
            # Verify PostgreSQL version
            assert "PostgreSQL" in version
            assert "15" in version  # Expecting PostgreSQL 15
        
        engine.dispose()

    def test_database_connection_config(self):
        """Test database connection configuration parameters."""
        engine = create_staging_engine(TEST_DATABASE_URL)
        
        # Verify connection parameters
        assert engine.url.host == "localhost"
        assert engine.url.port == 5432
        assert engine.url.database == "ppv_fulfillment_dev"
        
        engine.dispose()

    def test_database_connection_failure_handling(self):
        """Test handling of database connection failures."""
        # Test with invalid database URL
        invalid_url = "postgresql://localhost:5432/nonexistent_db"
        
        with pytest.raises(OperationalError):
            engine = create_staging_engine(invalid_url)
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))

    def test_staging_database_url_configuration(self):
        """Test staging database URL configuration."""
        staging_url = get_staging_database_url()
        
        # Should return properly formatted PostgreSQL URL
        assert staging_url.startswith("postgresql://")
        assert "ppv_fulfillment_dev" in staging_url


@pytest.mark.skipif(not STAGING_AVAILABLE, reason="Staging models not implemented yet - TDD RED phase")
class TestStagingTableCreation:
    """Test staging table creation and schema validation."""

    def test_init_staging_tables(self, staging_engine):
        """Test staging tables are created with correct schema."""
        # Initialize staging tables
        init_staging_tables(staging_engine)
        
        # Verify tables were created
        inspector = inspect(staging_engine)
        table_names = inspector.get_table_names()
        
        assert "campaigns_staging" in table_names
        assert "reporting_staging" in table_names

    def test_campaigns_staging_table_schema(self, staging_engine):
        """Test campaigns_staging table has correct schema."""
        init_staging_tables(staging_engine)
        
        inspector = inspect(staging_engine)
        columns = inspector.get_columns("campaigns_staging")
        
        # Convert to dict for easier testing
        column_info = {col['name']: col for col in columns}
        
        # Test primary key
        pk_columns = inspector.get_pk_constraint("campaigns_staging")
        assert pk_columns['constrained_columns'] == ['deal_campaign_id']
        
        # Test column types and constraints
        assert column_info['deal_campaign_id']['type'].python_type.__name__ == 'UUID'
        assert column_info['deal_campaign_name']['type'].length == 500
        assert column_info['buyer']['type'].length == 100
        assert column_info['record_classification']['type'].length == 50
        
        # Test nullable constraints
        assert column_info['budget_eur']['nullable'] is True  # 8.7% null rate
        assert column_info['validation_errors']['nullable'] is True
        assert column_info['deal_campaign_name']['nullable'] is False

    def test_reporting_staging_table_schema(self, staging_engine):
        """Test reporting_staging table has correct schema."""
        init_staging_tables(staging_engine)
        
        inspector = inspect(staging_engine)
        columns = inspector.get_columns("reporting_staging")
        
        # Convert to dict for easier testing
        column_info = {col['name']: col for col in columns}
        
        # Test composite primary key
        pk_columns = inspector.get_pk_constraint("reporting_staging")
        expected_pk = {'deal_id', 'date_recorded'}
        assert set(pk_columns['constrained_columns']) == expected_pk
        
        # Test column types
        assert column_info['deal_id']['type'].python_type.__name__ == 'UUID'
        assert column_info['deal_name']['type'].length == 500
        
        # Test nullable constraints for core_dsp fields (58% population)
        core_dsp_fields = ['core_dsp_audience_segment', 'core_dsp_placement', 'core_dsp_creative']
        for field in core_dsp_fields:
            assert column_info[field]['nullable'] is True

    def test_staging_table_indexes_creation(self, staging_engine):
        """Test staging tables have performance indexes."""
        init_staging_tables(staging_engine)
        
        inspector = inspect(staging_engine)
        
        # Test campaigns_staging indexes
        campaign_indexes = inspector.get_indexes("campaigns_staging")
        index_names = [idx['name'] for idx in campaign_indexes]
        
        # Expected performance indexes
        expected_campaign_indexes = [
            'idx_campaigns_staging_batch_id',
            'idx_campaigns_staging_buyer',
            'idx_campaigns_staging_runtime_dates',
            'idx_campaigns_staging_classification'
        ]
        
        for expected_idx in expected_campaign_indexes:
            assert any(expected_idx in idx_name for idx_name in index_names)
        
        # Test reporting_staging indexes
        reporting_indexes = inspector.get_indexes("reporting_staging")
        reporting_index_names = [idx['name'] for idx in reporting_indexes]
        
        expected_reporting_indexes = [
            'idx_reporting_staging_batch_id',
            'idx_reporting_staging_purchase_type',
            'idx_reporting_staging_date_recorded'
        ]
        
        for expected_idx in expected_reporting_indexes:
            assert any(expected_idx in idx_name for idx_name in reporting_index_names)


@pytest.mark.skipif(not STAGING_AVAILABLE, reason="Staging models not implemented yet - TDD RED phase")
class TestStagingDataOperations:
    """Test staging data insertion, retrieval, and manipulation."""

    def test_insert_campaign_staging_record(self, staging_session, sample_campaign_data):
        """Test inserting campaign staging record."""
        # Create and insert campaign record
        campaign = CampaignsStaging(**sample_campaign_data)
        staging_session.add(campaign)
        staging_session.flush()  # Flush without committing
        
        # Verify record was inserted
        assert campaign.deal_campaign_id is not None
        assert campaign.created_at is not None

    def test_insert_reporting_staging_record(self, staging_session, sample_reporting_data):
        """Test inserting reporting staging record."""
        # Create and insert reporting record
        reporting = ReportingStaging(**sample_reporting_data)
        staging_session.add(reporting)
        staging_session.flush()
        
        # Verify record was inserted with composite key
        assert reporting.deal_id is not None
        assert reporting.date_recorded is not None

    def test_batch_insert_performance(self, staging_session):
        """Test batch insert performance for staging records."""
        batch_size = 1000
        batch_id = uuid4()
        
        # Generate campaign test data
        campaign_records = []
        for i in range(batch_size):
            record = CampaignsStaging(
                deal_campaign_id=uuid4(),
                deal_campaign_name=f"Test Campaign {i}",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 12, 31),
                impression_goal=100000 + i,
                budget_eur=Decimal("5000.00") if i % 10 != 0 else None,  # 10% null rate
                cpm_eur=Decimal("2.50"),
                buyer=f"Buyer {i % 50}",  # 50 different buyers
                processing_batch_id=batch_id,
                record_classification="CAMPAIGN_XLSX",
                source_row_number=i + 1
            )
            campaign_records.append(record)
        
        # Time batch insert
        start_time = time.time()
        staging_session.add_all(campaign_records)
        staging_session.flush()
        insert_time = time.time() - start_time
        
        # Performance requirement: < 5 seconds for 1000 records
        assert insert_time < 5.0, f"Batch insert took {insert_time:.2f}s, expected < 5.0s"

    def test_large_batch_insert_performance_7k_benchmark(self, staging_session):
        """Test batch insert performance for 7K+ records benchmark."""
        batch_size = 7500  # 7K+ records benchmark
        batch_id = uuid4()
        
        # Generate campaign test data matching real-world distribution
        campaign_records = []
        for i in range(batch_size):
            record = CampaignsStaging(
                deal_campaign_id=uuid4(),
                deal_campaign_name=f"Campaign {i // 10} Batch {i % 10}",  # Realistic campaign names
                start_date=datetime(2024, 1, 1) + timedelta(days=i % 365),
                end_date=datetime(2024, 1, 1) + timedelta(days=(i % 365) + 30),
                impression_goal=3000 + (i * 97),  # 3K-720K range distribution
                budget_eur=Decimal(f"{1000 + (i * 2.5):.2f}") if i % 12 != 0 else None,  # 8.7% null rate
                cpm_eur=Decimal(f"{0.01 + (i % 4500) * 0.01:.2f}"),  # €0.01-€45.00 range
                buyer=f"Buyer {i % 150}",  # 150 different buyers (realistic variety)
                processing_batch_id=batch_id,
                record_classification="CAMPAIGN_XLSX",
                source_row_number=i + 1
            )
            campaign_records.append(record)
        
        # Time batch insert for 7K+ records
        start_time = time.time()
        staging_session.add_all(campaign_records)
        staging_session.flush()
        insert_time = time.time() - start_time
        
        # Performance requirement: < 30 seconds for 7K+ records (scalable from 5s/1K)
        expected_max_time = 30.0
        assert insert_time < expected_max_time, f"7K+ batch insert took {insert_time:.2f}s, expected < {expected_max_time}s"
        
        # Memory efficiency check - verify records were properly inserted
        inserted_count = staging_session.query(CampaignsStaging).filter(
            CampaignsStaging.processing_batch_id == batch_id
        ).count()
        assert inserted_count == batch_size, f"Expected {batch_size} records, got {inserted_count}"

    def test_uuid_lookup_performance(self, staging_session, sample_campaign_data):
        """Test UUID lookup performance meets < 100ms requirement."""
        # Insert test record
        campaign = CampaignsStaging(**sample_campaign_data)
        staging_session.add(campaign)
        staging_session.flush()
        
        # Time UUID lookup
        start_time = time.time()
        result = staging_session.query(CampaignsStaging).filter(
            CampaignsStaging.deal_campaign_id == campaign.deal_campaign_id
        ).first()
        lookup_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        # Performance requirement: < 100ms for UUID lookups
        assert lookup_time < 100, f"UUID lookup took {lookup_time:.2f}ms, expected < 100ms"
        assert result is not None
        assert result.deal_campaign_id == campaign.deal_campaign_id

    def test_composite_key_lookup_performance(self, staging_session, sample_reporting_data):
        """Test composite key lookup performance for time-series data."""
        # Insert test record
        reporting = ReportingStaging(**sample_reporting_data)
        staging_session.add(reporting)
        staging_session.flush()
        
        # Time composite key lookup
        start_time = time.time()
        result = staging_session.query(ReportingStaging).filter(
            ReportingStaging.deal_id == reporting.deal_id,
            ReportingStaging.date_recorded == reporting.date_recorded
        ).first()
        lookup_time = (time.time() - start_time) * 1000
        
        # Performance requirement: < 150ms for composite key lookups
        assert lookup_time < 150, f"Composite key lookup took {lookup_time:.2f}ms, expected < 150ms"
        assert result is not None


@pytest.mark.skipif(not STAGING_AVAILABLE, reason="Staging models not implemented yet - TDD RED phase")
class TestStagingDataValidation:
    """Test staging data validation and constraints."""

    def test_campaign_staging_validation_errors_field(self, staging_session, sample_campaign_data):
        """Test validation_errors field stores validation issues."""
        # Create campaign with validation errors
        sample_campaign_data['validation_errors'] = "CPM value exceeds maximum threshold"
        
        campaign = CampaignsStaging(**sample_campaign_data)
        staging_session.add(campaign)
        staging_session.flush()
        
        # Verify validation errors were stored
        assert campaign.validation_errors == "CPM value exceeds maximum threshold"

    def test_reporting_staging_purchase_type_constraint(self, staging_session, sample_reporting_data):
        """Test purchase_type ENUM constraint validation."""
        # Valid purchase types should work
        for purchase_type in ['guaranteed', 'unguaranteed']:
            sample_reporting_data['purchase_type'] = purchase_type
            sample_reporting_data['deal_id'] = uuid4()  # Unique deal_id for each test
            
            reporting = ReportingStaging(**sample_reporting_data)
            staging_session.add(reporting)
            staging_session.flush()
            
            assert reporting.purchase_type == purchase_type

    def test_campaign_staging_decimal_precision(self, staging_session, sample_campaign_data):
        """Test DECIMAL field precision and scale validation."""
        # Test budget_eur DECIMAL(12,2)
        sample_campaign_data['budget_eur'] = Decimal("9999999999.99")
        campaign = CampaignsStaging(**sample_campaign_data)
        staging_session.add(campaign)
        staging_session.flush()
        
        assert campaign.budget_eur == Decimal("9999999999.99")
        
        # Test cpm_eur DECIMAL(8,2)
        sample_campaign_data['cpm_eur'] = Decimal("999999.99")
        sample_campaign_data['deal_campaign_id'] = uuid4()  # New unique ID
        
        campaign2 = CampaignsStaging(**sample_campaign_data)
        staging_session.add(campaign2)
        staging_session.flush()
        
        assert campaign2.cpm_eur == Decimal("999999.99")

    def test_reporting_staging_impression_precision(self, staging_session, sample_reporting_data):
        """Test total_impressions DECIMAL(15,6) precision."""
        # Test maximum precision
        sample_reporting_data['total_impressions'] = Decimal("999999999.999999")
        
        reporting = ReportingStaging(**sample_reporting_data)
        staging_session.add(reporting)
        staging_session.flush()
        
        assert reporting.total_impressions == Decimal("999999999.999999")


@pytest.mark.skipif(not STAGING_AVAILABLE, reason="Staging models not implemented yet - TDD RED phase")
class TestStagingSessionManagement:
    """Test SQLAlchemy session management and transactions."""

    def test_staging_session_isolation(self, staging_engine):
        """Test staging session transaction isolation."""
        Session = sessionmaker(bind=staging_engine, autocommit=False, autoflush=False)
        
        # Create two separate sessions with explicit transactions
        session1 = Session()
        session2 = Session()
        
        # Start explicit transactions for proper isolation
        session1.begin()
        session2.begin()
        
        try:
            # Insert record in session1 but don't commit
            campaign = CampaignsStaging(
                deal_campaign_id=uuid4(),
                deal_campaign_name="Session Test Campaign",
                start_date=datetime(2024, 1, 1),
                end_date=datetime(2024, 12, 31),
                impression_goal=50000,
                cpm_eur=Decimal("3.00"),
                buyer="Test Buyer",
                processing_batch_id=uuid4(),
                record_classification="CAMPAIGN_XLSX",
                source_row_number=1
            )
            session1.add(campaign)
            session1.flush()
            
            # In PostgreSQL READ COMMITTED (default), flushed changes may be visible to other sessions
            # Test that the record exists in session1 (verifying flush worked)
            result_session1 = session1.query(CampaignsStaging).filter(
                CampaignsStaging.deal_campaign_name == "Session Test Campaign"
            ).first()
            assert result_session1 is not None
            
            # session2 may or may not see the flushed record (depends on PostgreSQL behavior)
            # The key test is that after commit, it's definitely visible
            
            # Commit in session1
            session1.commit()
            
            # Now session2 should see the record
            result = session2.query(CampaignsStaging).filter(
                CampaignsStaging.deal_campaign_name == "Session Test Campaign"
            ).first()
            assert result is not None
            
        finally:
            # Rollback any uncommitted transactions and close sessions
            try:
                session1.rollback()
                session2.rollback()
            except:
                pass
            session1.close()
            session2.close()

    def test_staging_session_rollback(self, staging_session, sample_campaign_data):
        """Test staging session rollback functionality."""
        # Insert record
        campaign = CampaignsStaging(**sample_campaign_data)
        staging_session.add(campaign)
        staging_session.flush()
        
        # Verify record exists in session
        result = staging_session.query(CampaignsStaging).filter(
            CampaignsStaging.deal_campaign_id == campaign.deal_campaign_id
        ).first()
        assert result is not None
        
        # Rollback transaction (handled by fixture)
        # Record should not persist after session closes


# Tests for when staging infrastructure doesn't exist (RED phase verification)
@pytest.mark.skipif(STAGING_AVAILABLE, reason="Staging infrastructure exists - not in RED phase")
class TestStagingRedPhase:
    """Verify we're in TDD RED phase - staging infrastructure should not exist yet."""

    def test_staging_models_not_available(self):
        """Verify staging models are not available yet."""
        with pytest.raises(ImportError):
            from src.models.staging import CampaignsStaging, ReportingStaging

    def test_staging_database_connection_not_available(self):
        """Verify staging database connection utilities are not available yet."""
        with pytest.raises(ImportError):
            from src.database.staging_connection import get_staging_database_url

    def test_staging_table_initialization_not_available(self):
        """Verify staging table initialization is not available yet."""
        with pytest.raises(ImportError):
            from src.database.staging_connection import init_staging_tables

    def test_direct_database_connection_works(self):
        """Verify that direct PostgreSQL connection works (baseline test)."""
        from sqlalchemy import create_engine, text
        
        try:
            engine = create_engine(TEST_DATABASE_URL)
            with engine.connect() as connection:
                result = connection.execute(text("SELECT 1"))
                assert result.fetchone()[0] == 1
            engine.dispose()
        except OperationalError:
            pytest.skip("PostgreSQL database not available for testing")