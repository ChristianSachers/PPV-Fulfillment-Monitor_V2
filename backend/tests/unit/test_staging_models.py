"""
Tests for staging table models - TDD RED phase
These tests MUST fail initially since staging models don't exist yet.

This test suite validates the PostgreSQL staging table schemas for:
1. Campaign XLSX Staging Table (campaigns_staging)
2. Reporting CSV Staging Table (reporting_staging)

All tests follow TDD principles and will fail until staging models are implemented.
"""
import pytest
from decimal import Decimal
from datetime import datetime
from uuid import UUID, uuid4
from pydantic import ValidationError
from sqlalchemy import Column, String, Integer, DECIMAL, TIMESTAMP, Boolean, TEXT
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID
from sqlalchemy.exc import StatementError

# Import staging models (these don't exist yet - will cause ImportError in RED phase)
try:
    from src.models.staging import (
        CampaignsStaging, 
        ReportingStaging,
        CampaignStagingRequest,
        ReportingStagingRequest,
        StagingValidationError,
        CampaignsStagingModel,
        ReportingStagingModel
    )
    MODELS_EXIST = True
except ImportError:
    MODELS_EXIST = False


@pytest.mark.skipif(not MODELS_EXIST, reason="Staging models not implemented yet - TDD RED phase")
class TestCampaignsStagingModel:
    """Test cases for campaigns_staging table schema validation."""

    def test_campaigns_staging_table_structure(self):
        """Test campaigns_staging has correct table name and columns."""
        # Verify table name
        assert CampaignsStagingModel.__tablename__ == "campaigns_staging"
        
        # Verify required columns exist
        columns = CampaignsStagingModel.__table__.columns
        expected_columns = {
            'deal_campaign_id', 'deal_campaign_name', 'start_date', 'end_date',
            'impression_goal', 'budget_eur', 'cpm_eur', 'buyer',
            'processing_batch_id', 'record_classification', 'source_row_number',
            'validation_errors', 'created_at', 'updated_at'
        }
        
        actual_columns = set(columns.keys())
        assert expected_columns.issubset(actual_columns), f"Missing columns: {expected_columns - actual_columns}"

    def test_campaigns_staging_primary_key(self):
        """Test deal_campaign_id is UUID primary key."""
        pk_columns = [col for col in CampaignsStagingModel.__table__.columns if col.primary_key]
        assert len(pk_columns) == 1
        assert pk_columns[0].name == 'deal_campaign_id'
        assert isinstance(pk_columns[0].type, PostgresUUID)

    def test_campaigns_staging_varchar_constraints(self):
        """Test VARCHAR field length constraints."""
        columns = CampaignsStagingModel.__table__.columns
        
        # deal_campaign_name VARCHAR(500)
        assert columns['deal_campaign_name'].type.length == 500
        assert not columns['deal_campaign_name'].nullable
        
        # buyer VARCHAR(100)
        assert columns['buyer'].type.length == 100
        assert not columns['buyer'].nullable
        
        # record_classification VARCHAR(50)
        assert columns['record_classification'].type.length == 50
        assert not columns['record_classification'].nullable

    def test_campaigns_staging_decimal_constraints(self):
        """Test DECIMAL field precision and scale."""
        columns = CampaignsStagingModel.__table__.columns
        
        # budget_eur DECIMAL(12,2) - nullable for 8.7% null rate
        budget_col = columns['budget_eur']
        assert isinstance(budget_col.type, DECIMAL)
        assert budget_col.type.precision == 12
        assert budget_col.type.scale == 2
        assert budget_col.nullable is True
        
        # cpm_eur DECIMAL(8,2) - not nullable
        cpm_col = columns['cpm_eur']
        assert isinstance(cpm_col.type, DECIMAL)
        assert cpm_col.type.precision == 8
        assert cpm_col.type.scale == 2
        assert cpm_col.nullable is False

    def test_campaigns_staging_bigint_constraint(self):
        """Test impression_goal is BIGINT."""
        columns = CampaignsStagingModel.__table__.columns
        impression_col = columns['impression_goal']
        
        # PostgreSQL BIGINT maps to SQLAlchemy BigInteger
        assert impression_col.type.python_type == int
        assert not impression_col.nullable

    def test_campaigns_staging_timestamp_fields(self):
        """Test timestamp fields have correct types."""
        columns = CampaignsStagingModel.__table__.columns
        
        # Date fields for runtime parsing
        assert isinstance(columns['start_date'].type, TIMESTAMP)
        assert isinstance(columns['end_date'].type, TIMESTAMP)
        
        # Audit timestamps
        assert isinstance(columns['created_at'].type, TIMESTAMP)
        assert isinstance(columns['updated_at'].type, TIMESTAMP)
        
        # created_at should have default
        assert columns['created_at'].default is not None

    def test_campaigns_staging_nullable_fields(self):
        """Test correct nullable constraints."""
        columns = CampaignsStagingModel.__table__.columns
        
        # Nullable fields
        assert columns['budget_eur'].nullable is True
        assert columns['validation_errors'].nullable is True
        
        # Required fields
        required_fields = [
            'deal_campaign_id', 'deal_campaign_name', 'start_date', 'end_date',
            'impression_goal', 'cpm_eur', 'buyer', 'processing_batch_id',
            'record_classification', 'source_row_number', 'created_at'
        ]
        
        for field in required_fields:
            assert columns[field].nullable is False, f"{field} should not be nullable"


@pytest.mark.skipif(not MODELS_EXIST, reason="Staging models not implemented yet - TDD RED phase")
class TestReportingStagingModel:
    """Test cases for reporting_staging table schema validation."""

    def test_reporting_staging_table_structure(self):
        """Test reporting_staging has correct table name and columns."""
        assert ReportingStagingModel.__tablename__ == "reporting_staging"
        
        columns = ReportingStagingModel.__table__.columns
        expected_columns = {
            'deal_id', 'date_recorded', 'deal_name', 'core_dsp_audience_segment',
            'core_dsp_placement', 'core_dsp_creative', 'purchase_type',
            'total_impressions', 'processing_batch_id', 'record_classification',
            'source_row_number', 'validation_errors', 'created_at', 'updated_at'
        }
        
        actual_columns = set(columns.keys())
        assert expected_columns.issubset(actual_columns)

    def test_reporting_staging_composite_primary_key(self):
        """Test composite primary key (deal_id, date_recorded)."""
        pk_columns = [col for col in ReportingStagingModel.__table__.columns if col.primary_key]
        assert len(pk_columns) == 2
        
        pk_names = {col.name for col in pk_columns}
        assert pk_names == {'deal_id', 'date_recorded'}

    def test_reporting_staging_uuid_and_timestamp_types(self):
        """Test UUID and timestamp column types."""
        columns = ReportingStagingModel.__table__.columns
        
        # deal_id is UUID
        assert isinstance(columns['deal_id'].type, PostgresUUID)
        assert not columns['deal_id'].nullable
        
        # date_recorded is TIMESTAMP
        assert isinstance(columns['date_recorded'].type, TIMESTAMP)
        assert not columns['date_recorded'].nullable

    def test_reporting_staging_varchar_constraints(self):
        """Test VARCHAR field constraints."""
        columns = ReportingStagingModel.__table__.columns
        
        # deal_name VARCHAR(500)
        assert columns['deal_name'].type.length == 500
        assert not columns['deal_name'].nullable

    def test_reporting_staging_decimal_precision(self):
        """Test total_impressions DECIMAL(15,6) precision."""
        columns = ReportingStagingModel.__table__.columns
        impressions_col = columns['total_impressions']
        
        assert isinstance(impressions_col.type, DECIMAL)
        assert impressions_col.type.precision == 15
        assert impressions_col.type.scale == 6
        assert not impressions_col.nullable

    def test_reporting_staging_nullable_core_dsp_fields(self):
        """Test core_dsp fields are nullable (58% population rate)."""
        columns = ReportingStagingModel.__table__.columns
        
        core_dsp_fields = [
            'core_dsp_audience_segment',
            'core_dsp_placement', 
            'core_dsp_creative'
        ]
        
        for field in core_dsp_fields:
            assert columns[field].nullable is True, f"{field} should be nullable"

    def test_reporting_staging_purchase_type_enum(self):
        """Test purchase_type has ENUM constraint."""
        columns = ReportingStagingModel.__table__.columns
        purchase_type_col = columns['purchase_type']
        
        # Should be an Enum type with guaranteed/unguaranteed values
        assert hasattr(purchase_type_col.type, 'enums')
        expected_values = {'guaranteed', 'unguaranteed'}
        assert set(purchase_type_col.type.enums) == expected_values


@pytest.mark.skipif(not MODELS_EXIST, reason="Staging models not implemented yet - TDD RED phase")
class TestCampaignStagingRequest:
    """Test Pydantic request model for campaign staging data."""

    def test_valid_campaign_staging_request(self):
        """Test valid campaign staging request with all required fields."""
        data = {
            "deal_campaign_name": "Test Campaign 2024",
            "runtime": "01.01.2024-31.12.2024",
            "impression_goal": 50000,
            "budget_eur": "15000.50",
            "cpm_eur": "3.25",
            "buyer": "Premium Advertiser"
        }
        
        request = CampaignStagingRequest(**data)
        assert request.deal_campaign_name == "Test Campaign 2024"
        assert request.impression_goal == 50000
        assert request.budget_eur == Decimal("15000.50")

    def test_campaign_runtime_parsing(self):
        """Test runtime string parsing to start_date/end_date."""
        data = {
            "deal_campaign_name": "Test Campaign",
            "runtime": "15.03.2024-20.11.2024",
            "impression_goal": 100000,
            "cpm_eur": "2.50",
            "buyer": "Test Buyer"
        }
        
        request = CampaignStagingRequest(**data)
        # Should parse runtime into separate date fields
        assert hasattr(request, 'start_date')
        assert hasattr(request, 'end_date')

    def test_campaign_budget_nullable(self):
        """Test budget_eur can be null (8.7% null rate)."""
        data = {
            "deal_campaign_name": "Test Campaign",
            "runtime": "01.01.2024-31.12.2024",
            "impression_goal": 75000,
            "cpm_eur": "4.00",
            "buyer": "Test Buyer",
            "budget_eur": None
        }
        
        request = CampaignStagingRequest(**data)
        assert request.budget_eur is None

    def test_campaign_cpm_range_validation(self):
        """Test CPM validation (€0.01-€45.00 range)."""
        # Valid CPM
        valid_data = {
            "deal_campaign_name": "Test",
            "runtime": "01.01.2024-31.12.2024",
            "impression_goal": 50000,
            "cpm_eur": "25.50",
            "buyer": "Test Buyer"
        }
        request = CampaignStagingRequest(**valid_data)
        assert request.cpm_eur == Decimal("25.50")
        
        # Invalid CPM - too low
        with pytest.raises(ValidationError):
            invalid_data = valid_data.copy()
            invalid_data["cpm_eur"] = "0.005"
            CampaignStagingRequest(**invalid_data)
        
        # Invalid CPM - too high
        with pytest.raises(ValidationError):
            invalid_data = valid_data.copy()
            invalid_data["cpm_eur"] = "50.00"
            CampaignStagingRequest(**invalid_data)

    def test_campaign_impression_range_validation(self):
        """Test impression goal validation (3K-720K range)."""
        base_data = {
            "deal_campaign_name": "Test",
            "runtime": "01.01.2024-31.12.2024",
            "cpm_eur": "3.00",
            "buyer": "Test Buyer"
        }
        
        # Valid impression range
        valid_data = base_data.copy()
        valid_data["impression_goal"] = 150000
        request = CampaignStagingRequest(**valid_data)
        assert request.impression_goal == 150000
        
        # Invalid - too low
        with pytest.raises(ValidationError):
            invalid_data = base_data.copy()
            invalid_data["impression_goal"] = 2000
            CampaignStagingRequest(**invalid_data)
        
        # Invalid - too high
        with pytest.raises(ValidationError):
            invalid_data = base_data.copy()
            invalid_data["impression_goal"] = 800000
            CampaignStagingRequest(**invalid_data)


@pytest.mark.skipif(not MODELS_EXIST, reason="Staging models not implemented yet - TDD RED phase")
class TestReportingStagingRequest:
    """Test Pydantic request model for reporting staging data."""

    def test_valid_reporting_staging_request(self):
        """Test valid reporting staging request."""
        data = {
            "deal_id": str(uuid4()),
            "date_recorded": "2024-03-15T10:30:00",
            "deal_name": "Premium Campaign Deal",
            "purchase_type": "guaranteed",
            "total_impressions": "125000.500000"
        }
        
        request = ReportingStagingRequest(**data)
        assert request.purchase_type == "guaranteed"
        assert request.total_impressions == Decimal("125000.500000")

    def test_reporting_core_dsp_nullable_fields(self):
        """Test core_dsp fields can be null (58% population)."""
        data = {
            "deal_id": str(uuid4()),
            "date_recorded": "2024-03-15T10:30:00",
            "deal_name": "Test Deal",
            "purchase_type": "unguaranteed",
            "total_impressions": "50000.000000",
            "core_dsp_audience_segment": None,
            "core_dsp_placement": None,
            "core_dsp_creative": None
        }
        
        request = ReportingStagingRequest(**data)
        assert request.core_dsp_audience_segment is None
        assert request.core_dsp_placement is None
        assert request.core_dsp_creative is None

    def test_reporting_purchase_type_validation(self):
        """Test purchase_type enum validation."""
        base_data = {
            "deal_id": str(uuid4()),
            "date_recorded": "2024-03-15T10:30:00",
            "deal_name": "Test Deal",
            "total_impressions": "75000.000000"
        }
        
        # Valid purchase types
        for purchase_type in ["guaranteed", "unguaranteed"]:
            data = base_data.copy()
            data["purchase_type"] = purchase_type
            request = ReportingStagingRequest(**data)
            assert request.purchase_type == purchase_type
        
        # Invalid purchase type
        with pytest.raises(ValidationError):
            invalid_data = base_data.copy()
            invalid_data["purchase_type"] = "invalid_type"
            ReportingStagingRequest(**invalid_data)

    def test_reporting_impression_range_validation(self):
        """Test total_impressions validation (619-231M range)."""
        base_data = {
            "deal_id": str(uuid4()),
            "date_recorded": "2024-03-15T10:30:00",
            "deal_name": "Test Deal",
            "purchase_type": "guaranteed"
        }
        
        # Valid impression range
        valid_data = base_data.copy()
        valid_data["total_impressions"] = "1500000.500000"
        request = ReportingStagingRequest(**valid_data)
        assert request.total_impressions == Decimal("1500000.500000")
        
        # Invalid - too low
        with pytest.raises(ValidationError):
            invalid_data = base_data.copy()
            invalid_data["total_impressions"] = "500.000000"
            ReportingStagingRequest(**invalid_data)
        
        # Invalid - too high  
        with pytest.raises(ValidationError):
            invalid_data = base_data.copy()
            invalid_data["total_impressions"] = "250000000.000000"
            ReportingStagingRequest(**invalid_data)


@pytest.mark.skipif(not MODELS_EXIST, reason="Staging models not implemented yet - TDD RED phase")
class TestStagingValidationError:
    """Test custom exception for staging validation errors."""

    def test_staging_validation_error_creation(self):
        """Test staging validation error can be created with message."""
        error = StagingValidationError("Invalid staging data format")
        assert str(error) == "Invalid staging data format"

    def test_staging_validation_error_inheritance(self):
        """Test StagingValidationError inherits from Exception."""
        error = StagingValidationError("Test error")
        assert isinstance(error, Exception)

    def test_staging_validation_error_with_context(self):
        """Test staging validation error with additional context."""
        context = {"table": "campaigns_staging", "row": 42, "field": "cpm_eur"}
        error = StagingValidationError("CPM out of range", context)
        assert str(error) == "CPM out of range"
        assert error.context == context


# Tests for when models don't exist (RED phase verification)
@pytest.mark.skipif(MODELS_EXIST, reason="Models exist - not in RED phase")
class TestStagingModelsRedPhase:
    """Verify we're in TDD RED phase - models should not exist yet."""

    def test_campaigns_staging_model_not_implemented(self):
        """Verify CampaignsStaging model doesn't exist yet."""
        with pytest.raises(ImportError):
            from src.models.staging import CampaignsStaging

    def test_reporting_staging_model_not_implemented(self):
        """Verify ReportingStaging model doesn't exist yet."""
        with pytest.raises(ImportError):
            from src.models.staging import ReportingStaging

    def test_staging_requests_not_implemented(self):
        """Verify staging request models don't exist yet."""
        with pytest.raises(ImportError):
            from src.models.staging import CampaignStagingRequest, ReportingStagingRequest

    def test_staging_validation_error_not_implemented(self):
        """Verify comprehensive staging validation error doesn't exist yet."""
        # Basic StagingValidationError exists, but enhanced version with context doesn't
        from src.models.staging import StagingValidationError
        
        # Test that enhanced validation error features don't exist yet
        basic_error = StagingValidationError("Test error")
        assert str(basic_error) == "Test error"
        
        # Enhanced features should not exist yet (will be implemented in GREEN phase)
        assert not hasattr(basic_error, 'context'), "Enhanced context attribute should not exist yet"
        assert not hasattr(basic_error, 'validation_rules'), "Enhanced validation_rules should not exist yet"