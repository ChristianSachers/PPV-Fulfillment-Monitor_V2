"""
Tests for Phase 1.2 staging table extensions - TDD RED phase
These tests MUST fail initially since Phase 1.2 extensions don't exist yet.

This test suite validates the Phase 1.2 extension columns for:
1. campaigns_staging table extensions
2. reporting_staging table extensions
3. Backward compatibility with Phase 1.1
4. New indexes for performance

All tests follow TDD principles and will fail until extensions are implemented.
"""
import pytest
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import Column, String, Boolean, Index
from sqlalchemy.dialects.postgresql import JSONB

# Import staging models
try:
    from src.models.staging import CampaignsStaging, ReportingStaging
    from src.database.staging_connection import StagingDatabase
    MODELS_EXIST = True
except ImportError:
    MODELS_EXIST = False


@pytest.mark.skipif(not MODELS_EXIST, reason="Staging models not implemented yet - TDD RED phase")
class TestPhase12StagingExtensions:
    """Test cases for Phase 1.2 staging table extensions."""

    def test_campaigns_staging_phase_12_columns_exist(self):
        """Test campaigns_staging has Phase 1.2 extension columns."""
        columns = CampaignsStaging.__table__.columns
        
        # New Phase 1.2 columns should exist
        expected_new_columns = {
            'phase_context',      # VARCHAR(10) - Phase identifier ('1.1' or '1.2')
            'violation_details',  # JSONB - Structured violation information
            'flagged_for_review', # BOOLEAN - Review requirement flag
            'variance_detected'   # BOOLEAN - Change detection flag
        }
        
        actual_columns = set(columns.keys())
        missing_columns = expected_new_columns - actual_columns
        assert len(missing_columns) == 0, f"Missing Phase 1.2 columns: {missing_columns}"

    def test_reporting_staging_phase_12_columns_exist(self):
        """Test reporting_staging has Phase 1.2 extension columns."""
        columns = ReportingStaging.__table__.columns
        
        # New Phase 1.2 columns should exist
        expected_new_columns = {
            'phase_context',      # VARCHAR(10) - Phase identifier ('1.1' or '1.2')
            'violation_details',  # JSONB - Structured violation information
            'flagged_for_review', # BOOLEAN - Review requirement flag
            'variance_detected'   # BOOLEAN - Change detection flag
        }
        
        actual_columns = set(columns.keys())
        missing_columns = expected_new_columns - actual_columns
        assert len(missing_columns) == 0, f"Missing Phase 1.2 columns: {missing_columns}"

    def test_phase_context_column_constraints(self):
        """Test phase_context column has correct constraints."""
        # Test campaigns table
        campaigns_columns = CampaignsStaging.__table__.columns
        phase_col = campaigns_columns['phase_context']
        
        assert isinstance(phase_col.type, String)
        assert phase_col.type.length == 10
        assert phase_col.nullable is True  # Nullable for backward compatibility
        
        # Test reporting table
        reporting_columns = ReportingStaging.__table__.columns
        phase_col = reporting_columns['phase_context']
        
        assert isinstance(phase_col.type, String)
        assert phase_col.type.length == 10
        assert phase_col.nullable is True  # Nullable for backward compatibility

    def test_violation_details_jsonb_column(self):
        """Test violation_details is JSONB type and nullable."""
        # Test campaigns table
        campaigns_columns = CampaignsStaging.__table__.columns
        violation_col = campaigns_columns['violation_details']
        
        assert isinstance(violation_col.type, JSONB)
        assert violation_col.nullable is True  # Nullable for backward compatibility
        
        # Test reporting table
        reporting_columns = ReportingStaging.__table__.columns
        violation_col = reporting_columns['violation_details']
        
        assert isinstance(violation_col.type, JSONB)
        assert violation_col.nullable is True  # Nullable for backward compatibility

    def test_boolean_flags_constraints(self):
        """Test flagged_for_review and variance_detected are proper booleans."""
        # Test campaigns table
        campaigns_columns = CampaignsStaging.__table__.columns
        
        flagged_col = campaigns_columns['flagged_for_review']
        assert isinstance(flagged_col.type, Boolean)
        assert flagged_col.nullable is True  # Nullable for backward compatibility
        
        variance_col = campaigns_columns['variance_detected']
        assert isinstance(variance_col.type, Boolean)
        assert variance_col.nullable is True  # Nullable for backward compatibility
        
        # Test reporting table
        reporting_columns = ReportingStaging.__table__.columns
        
        flagged_col = reporting_columns['flagged_for_review']
        assert isinstance(flagged_col.type, Boolean)
        assert flagged_col.nullable is True  # Nullable for backward compatibility
        
        variance_col = reporting_columns['variance_detected']
        assert isinstance(variance_col.type, Boolean)
        assert variance_col.nullable is True  # Nullable for backward compatibility

    def test_phase_12_indexes_exist(self):
        """Test Phase 1.2 performance indexes exist."""
        # Test campaigns table indexes
        campaigns_indexes = CampaignsStaging.__table__.indexes
        index_names = {idx.name for idx in campaigns_indexes}
        
        assert 'idx_campaigns_staging_phase_context' in index_names
        
        # Test reporting table indexes
        reporting_indexes = ReportingStaging.__table__.indexes
        index_names = {idx.name for idx in reporting_indexes}
        
        assert 'idx_reporting_staging_phase_context' in index_names

    def test_backward_compatibility_phase_11_columns(self):
        """Test all Phase 1.1 columns still exist and unchanged."""
        # Test campaigns table - all original columns should exist
        campaigns_columns = CampaignsStaging.__table__.columns
        phase_11_columns = {
            'deal_campaign_id', 'deal_campaign_name', 'start_date', 'end_date',
            'impression_goal', 'budget_eur', 'cpm_eur', 'buyer',
            'processing_batch_id', 'record_classification', 'source_row_number',
            'validation_errors', 'created_at', 'updated_at'
        }
        
        actual_columns = set(campaigns_columns.keys())
        missing_columns = phase_11_columns - actual_columns
        assert len(missing_columns) == 0, f"Phase 1.1 columns missing: {missing_columns}"
        
        # Test reporting table - all original columns should exist
        reporting_columns = ReportingStaging.__table__.columns
        phase_11_columns = {
            'deal_id', 'date_recorded', 'deal_name', 'core_dsp_audience_segment',
            'core_dsp_placement', 'core_dsp_creative', 'purchase_type',
            'total_impressions', 'processing_batch_id', 'record_classification',
            'source_row_number', 'validation_errors', 'created_at', 'updated_at'
        }
        
        actual_columns = set(reporting_columns.keys())
        missing_columns = phase_11_columns - actual_columns
        assert len(missing_columns) == 0, f"Phase 1.1 columns missing: {missing_columns}"


@pytest.mark.skipif(not MODELS_EXIST, reason="Database not available - TDD RED phase")
class TestPhase12DatabaseOperations:
    """Test database operations for Phase 1.2 extensions."""

    def test_staging_database_can_create_phase_12_extensions(self):
        """Test StagingDatabase can create Phase 1.2 extensions."""
        db = StagingDatabase()
        
        # This method should exist for Phase 1.2
        assert hasattr(db, 'create_phase_1_2_extensions'), "create_phase_1_2_extensions method should exist"
        
        # Method should be callable without errors
        try:
            result = db.create_phase_1_2_extensions()
            assert result is not None
        except Exception as e:
            pytest.fail(f"create_phase_1_2_extensions should not raise exception: {e}")

    def test_staging_database_can_verify_phase_12_extensions(self):
        """Test StagingDatabase can verify Phase 1.2 extensions."""
        db = StagingDatabase()
        
        # This method should exist for Phase 1.2
        assert hasattr(db, 'verify_phase_1_2_extensions'), "verify_phase_1_2_extensions method should exist"
        
        # Method should be callable and return verification result
        try:
            result = db.verify_phase_1_2_extensions()
            assert isinstance(result, dict), "Verification should return dict with results"
            
            # Should have these verification keys
            expected_keys = {'campaigns_extended', 'reporting_extended', 'indexes_created', 'backward_compatible'}
            assert all(key in result for key in expected_keys), f"Missing verification keys: {expected_keys - set(result.keys())}"
            
        except Exception as e:
            pytest.fail(f"verify_phase_1_2_extensions should not raise exception: {e}")

    def test_phase_12_data_insertion_with_new_columns(self):
        """Test inserting data with Phase 1.2 columns."""
        db = StagingDatabase()
        
        # Test data with Phase 1.2 columns
        campaign_data_phase_12 = {
            'deal_campaign_id': str(uuid4()),
            'deal_campaign_name': 'Phase 1.2 Test Campaign',
            'start_date': datetime(2024, 1, 1),
            'end_date': datetime(2024, 12, 31),
            'impression_goal': 100000,
            'budget_eur': 15000.50,
            'cpm_eur': 3.25,
            'buyer': 'Test Buyer',
            'processing_batch_id': str(uuid4()),
            'record_classification': 'new_entry',
            'source_row_number': 1,
            'validation_errors': None,
            # Phase 1.2 extensions
            'phase_context': '1.2',
            'violation_details': {'error_codes': ['BIZ_101', 'BIZ_102'], 'severity': 'high'},
            'flagged_for_review': True,
            'variance_detected': False
        }
        
        # Should be able to save without errors
        try:
            db.save_campaigns_batch([campaign_data_phase_12])
        except Exception as e:
            pytest.fail(f"Phase 1.2 data insertion should not fail: {e}")


# Tests for when extensions don't exist (RED phase verification)
@pytest.mark.skipif(MODELS_EXIST, reason="Models exist - not in RED phase")
class TestPhase12ExtensionsRedPhase:
    """Verify we're in TDD RED phase - Phase 1.2 extensions should not exist yet."""

    def test_phase_12_columns_not_implemented(self):
        """Verify Phase 1.2 extension columns don't exist yet."""
        from src.models.staging import CampaignsStaging, ReportingStaging
        
        campaigns_columns = set(CampaignsStaging.__table__.columns.keys())
        reporting_columns = set(ReportingStaging.__table__.columns.keys())
        
        phase_12_columns = {'phase_context', 'violation_details', 'flagged_for_review', 'variance_detected'}
        
        # These columns should NOT exist yet
        campaigns_missing = phase_12_columns - campaigns_columns
        reporting_missing = phase_12_columns - reporting_columns
        
        assert len(campaigns_missing) == 4, f"Phase 1.2 columns should not exist yet in campaigns: {campaigns_missing}"
        assert len(reporting_missing) == 4, f"Phase 1.2 columns should not exist yet in reporting: {reporting_missing}"

    def test_phase_12_database_methods_not_implemented(self):
        """Verify Phase 1.2 database methods don't exist yet."""
        from src.database.staging_connection import StagingDatabase
        
        db = StagingDatabase()
        
        # These methods should NOT exist yet
        assert not hasattr(db, 'create_phase_1_2_extensions'), "create_phase_1_2_extensions should not exist yet"
        assert not hasattr(db, 'verify_phase_1_2_extensions'), "verify_phase_1_2_extensions should not exist yet"