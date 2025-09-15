"""Staging models for data processing and validation"""
from datetime import datetime
from decimal import Decimal
from typing import Optional, Any, Dict
from uuid import UUID, uuid4
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import (
    Column, String, Integer, DateTime, DECIMAL, Boolean, TEXT, Index,
    BIGINT, TIMESTAMP, Enum as SQLEnum
)
from sqlalchemy.dialects.postgresql import UUID as PostgresUUID, JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class PurchaseType(str, Enum):
    """Purchase type enumeration for reporting data."""
    guaranteed = "guaranteed"
    unguaranteed = "unguaranteed"


class CampaignsStaging(Base):
    """SQLAlchemy model for campaigns_staging table."""
    __tablename__ = "campaigns_staging"
    
    # Primary key
    deal_campaign_id = Column(PostgresUUID(as_uuid=True), primary_key=True, default=uuid4)
    
    # Campaign data fields
    deal_campaign_name = Column(String(500), nullable=False)
    start_date = Column(TIMESTAMP, nullable=False)
    end_date = Column(TIMESTAMP, nullable=False)
    impression_goal = Column(BIGINT, nullable=False)
    budget_eur = Column(DECIMAL(12, 2), nullable=True)  # 8.7% null rate
    cpm_eur = Column(DECIMAL(8, 2), nullable=False)
    buyer = Column(String(100), nullable=False)
    
    # Staging metadata
    processing_batch_id = Column(PostgresUUID(as_uuid=True), nullable=False)
    record_classification = Column(String(50), nullable=False)
    source_row_number = Column(Integer, nullable=False)
    validation_errors = Column(TEXT, nullable=True)
    
    # Audit timestamps
    created_at = Column(TIMESTAMP, nullable=False, default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.now())
    
    # Phase 1.2 extensions (nullable for backward compatibility)
    phase_context = Column(String(10), nullable=True)  # Phase identifier ('1.1' or '1.2')
    violation_details = Column(JSONB, nullable=True)    # Structured violation information
    flagged_for_review = Column(Boolean, nullable=True) # Review requirement flag
    variance_detected = Column(Boolean, nullable=True)  # Change detection flag
    
    # Performance indexes
    __table_args__ = (
        Index('idx_campaigns_staging_batch_id', 'processing_batch_id'),
        Index('idx_campaigns_staging_buyer', 'buyer'),
        Index('idx_campaigns_staging_runtime_dates', 'start_date', 'end_date'),
        Index('idx_campaigns_staging_classification', 'record_classification'),
        Index('idx_campaigns_staging_phase_context', 'phase_context'),  # Phase 1.2 index
    )


class ReportingStaging(Base):
    """SQLAlchemy model for reporting_staging table."""
    __tablename__ = "reporting_staging"
    
    # Composite primary key
    deal_id = Column(PostgresUUID(as_uuid=True), primary_key=True)
    date_recorded = Column(TIMESTAMP, primary_key=True)
    
    # Reporting data fields
    deal_name = Column(String(500), nullable=False)
    core_dsp_audience_segment = Column(TEXT, nullable=True)  # 58% population rate
    core_dsp_placement = Column(TEXT, nullable=True)
    core_dsp_creative = Column(TEXT, nullable=True)
    purchase_type = Column(SQLEnum(PurchaseType), nullable=False)
    total_impressions = Column(DECIMAL(15, 6), nullable=False)
    
    # Staging metadata
    processing_batch_id = Column(PostgresUUID(as_uuid=True), nullable=False)
    record_classification = Column(String(50), nullable=False)
    source_row_number = Column(Integer, nullable=False)
    validation_errors = Column(TEXT, nullable=True)
    
    # Audit timestamps
    created_at = Column(TIMESTAMP, nullable=False, default=func.now())
    updated_at = Column(TIMESTAMP, nullable=True, onupdate=func.now())
    
    # Phase 1.2 extensions (nullable for backward compatibility)
    phase_context = Column(String(10), nullable=True)  # Phase identifier ('1.1' or '1.2')
    violation_details = Column(JSONB, nullable=True)    # Structured violation information
    flagged_for_review = Column(Boolean, nullable=True) # Review requirement flag
    variance_detected = Column(Boolean, nullable=True)  # Change detection flag
    
    # Performance indexes
    __table_args__ = (
        Index('idx_reporting_staging_batch_id', 'processing_batch_id'),
        Index('idx_reporting_staging_purchase_type', 'purchase_type'),
        Index('idx_reporting_staging_date_recorded', 'date_recorded'),
        Index('idx_reporting_staging_phase_context', 'phase_context'),  # Phase 1.2 index
    )


class CampaignStagingRequest(BaseModel):
    """Pydantic request model for campaign staging data with validation."""
    deal_campaign_name: str = Field(..., min_length=1, max_length=500)
    runtime: str = Field(..., description="Date range in format 'DD.MM.YYYY-DD.MM.YYYY'")
    impression_goal: int = Field(..., ge=3000, le=720000, description="Impression goal range 3K-720K")
    budget_eur: Optional[Decimal] = Field(None, ge=0, description="Budget in EUR, nullable")
    cpm_eur: Decimal = Field(..., ge=Decimal('0.01'), le=Decimal('45.00'), description="CPM range €0.01-€45.00")
    buyer: str = Field(..., min_length=1, max_length=100)
    
    # Parsed fields (set by root_validator)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
    @field_validator('cpm_eur', mode='before')
    @classmethod
    def parse_cpm_eur(cls, v):
        """Parse CPM value to Decimal."""
        if isinstance(v, str):
            return Decimal(v)
        return v
    
    @field_validator('budget_eur', mode='before')
    @classmethod
    def parse_budget_eur(cls, v):
        """Parse budget value to Decimal."""
        if v is None:
            return None
        if isinstance(v, str):
            return Decimal(v)
        return v
    
    @model_validator(mode='after')
    def parse_runtime(self):
        """Parse runtime string into start_date and end_date."""
        runtime = getattr(self, 'runtime', None)
        if runtime:
            try:
                start_str, end_str = runtime.split('-')
                start_date = datetime.strptime(start_str.strip(), '%d.%m.%Y')
                end_date = datetime.strptime(end_str.strip(), '%d.%m.%Y')
                self.start_date = start_date
                self.end_date = end_date
            except (ValueError, AttributeError) as e:
                raise ValueError(f"Invalid runtime format: {runtime}. Expected 'DD.MM.YYYY-DD.MM.YYYY'") from e
        return self


class ReportingStagingRequest(BaseModel):
    """Pydantic request model for reporting staging data with validation."""
    deal_id: UUID
    date_recorded: datetime
    deal_name: str = Field(..., min_length=1, max_length=500)
    core_dsp_audience_segment: Optional[str] = None
    core_dsp_placement: Optional[str] = None
    core_dsp_creative: Optional[str] = None
    purchase_type: PurchaseType
    total_impressions: Decimal = Field(..., ge=619, le=231000000, description="Impressions range 619-231M")
    
    @field_validator('total_impressions', mode='before')
    @classmethod
    def parse_total_impressions(cls, v):
        """Parse total impressions to Decimal."""
        if isinstance(v, str):
            return Decimal(v)
        return v
    
    @field_validator('deal_id', mode='before')
    @classmethod
    def parse_deal_id(cls, v):
        """Parse deal_id to UUID."""
        if isinstance(v, str):
            return UUID(v)
        return v


class StagingValidationError(Exception):
    """Enhanced exception for staging validation errors with context support."""
    
    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.context = context or {}
        self.message = message
    
    def __str__(self):
        return self.message


# Aliases for test compatibility
CampaignsStagingModel = CampaignsStaging
ReportingStagingModel = ReportingStaging