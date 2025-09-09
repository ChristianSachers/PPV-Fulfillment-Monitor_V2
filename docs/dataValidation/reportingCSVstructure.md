# CSV Data Structure Analysis for Database Implementation

## Target Audience
This document is specifically designed for Claude Code agents to implement a comprehensive database schema and validation system for PPV (Programmatic Public Video) campaign data.

## Executive Summary
Analysis of `/uploads/examples/2025-09-03_21-25-08.csv` containing **1,073 campaign records** with **8 data columns**. The dataset represents digital advertising campaign data with structured deal names, impression metrics, and campaign metadata requiring sophisticated parsing and validation.

---

## =� Data File Specifications

### File Metrics
- **Total Records**: 1,073 rows
- **Data Columns**: 8 fields
- **Unique Deal Names**: 452 (indicates record duplication/time-series data)
- **File Size**: ~8,584 data cells
- **Data Completeness**: Variable (58% - 100% across columns)

### Column Structure
```
1. Date                    | TIMESTAMP | 100% populated | ISO8601 format
2. Core DSP Campaign Name  | STRING    | 58% populated  | Max 255 chars
3. Core DSP Campaign ID    | UUID      | 58% populated  | Standard UUID format
4. Deal Name               | STRING    | 100% populated | Structured naming pattern
5. Deal ID                 | UUID      | 100% populated | Primary identifier
6. Campaign Purchase Type  | ENUM      | 58% populated  | guaranteed/unguaranteed
7. Deal Purchase Type      | ENUM      | 100% populated | guaranteed/unguaranteed
8. Total Impressions       | DECIMAL   | 100% populated | Range: 619 - 231,810,865
```

---

## <� Database Schema Implementation

### Required Tables

#### 1. `campaigns` (Primary Table)
```sql
CREATE TABLE campaigns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    deal_id UUID UNIQUE NOT NULL,
    deal_name VARCHAR(500) NOT NULL,
    core_dsp_campaign_name VARCHAR(255),
    core_dsp_campaign_id UUID,
    campaign_purchase_type VARCHAR(20) CHECK (campaign_purchase_type IN ('guaranteed', 'unguaranteed')),
    deal_purchase_type VARCHAR(20) NOT NULL CHECK (deal_purchase_type IN ('guaranteed', 'unguaranteed')),
    total_impressions DECIMAL(15,6) NOT NULL CHECK (total_impressions > 0),
    record_date TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Critical Indexes
CREATE INDEX idx_campaigns_deal_id ON campaigns(deal_id);
CREATE INDEX idx_campaigns_purchase_type ON campaigns(deal_purchase_type);
CREATE INDEX idx_campaigns_impressions ON campaigns(total_impressions);
CREATE INDEX idx_campaigns_date ON campaigns(record_date);
```

#### 2. `campaign_details` (Parsed Deal Name Components)
```sql
CREATE TABLE campaign_details (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    campaign_id UUID REFERENCES campaigns(id) ON DELETE CASCADE,
    year SMALLINT NOT NULL,
    campaign_number VARCHAR(50),
    sequence_number VARCHAR(20),
    placement_type_id UUID REFERENCES placement_types(id),
    advertiser_id UUID REFERENCES advertisers(id),
    description TEXT,
    start_date DATE,
    end_date DATE,
    CONSTRAINT valid_date_range CHECK (start_date <= end_date)
);

-- Performance Indexes
CREATE INDEX idx_campaign_details_campaign_id ON campaign_details(campaign_id);
CREATE INDEX idx_campaign_details_year ON campaign_details(year);
CREATE INDEX idx_campaign_details_placement ON campaign_details(placement_type_id);
CREATE INDEX idx_campaign_details_advertiser ON campaign_details(advertiser_id);
CREATE INDEX idx_campaign_details_date_range ON campaign_details(start_date, end_date);
```

#### 3. `advertisers` (Normalized Advertiser Data)
```sql
CREATE TABLE advertisers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) UNIQUE NOT NULL,
    normalized_name VARCHAR(200) NOT NULL,
    industry VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Pre-populate with discovered advertisers (137 unique)
-- Top advertisers: Wolt Enterprises (18), EDEKA ZENTRALE AG & Co. KG (11), Vodafone GmbH (10)
```

#### 4. `placement_types` (Standardized Placement Categories)
```sql
CREATE TABLE placement_types (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(50) UNIQUE NOT NULL,
    category VARCHAR(50),
    description TEXT
);

-- Pre-populate with discovered types (15 unique)
-- Top types: Station (113), Infoscreen (89), City (82), Roadside (44), Netzwerk (36)
```

---

##  Critical Validation Rules

### Field-Level Validation

#### UUID Validation Pattern
```regex
^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$
```

#### Deal Name Validation
- **Pattern**: `^[A-Za-z0-9_\-\.\s]+$`
- **Length**: 10-500 characters
- **Structure**: 89% follow `YEAR_CAMPAIGN_ID_SEQUENCE_PLACEMENT_ADVERTISER_DESCRIPTION_DATE_RANGE`

#### Timestamp Validation
```regex
^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$
```

#### Date Range Patterns (in Deal Names)
```regex
\d{2}\.\d{2}\.-\d{2}\.\d{2}\.     # Format: 01.12.-31.12.
\d{1,2}\.-\d{2}\.\d{2}\.          # Format: 1.-31.12.
\d{2}\.\d{2}\.                    # Format: 01.12.
\d{2}-\d{2}\.\d{2}\.              # Format: 01-31.12.
```

### Business Logic Validation

#### Deal Name Structure Parsing
```python
# Expected pattern components:
YEAR_CAMPAIGN_ID_SEQUENCE_PLACEMENT_ADVERTISER_DESCRIPTION_DATE_RANGE

# Implementation priority:
# 1. Extract year (2025 = 100% of records)
# 2. Parse campaign ID (numeric sequence)
# 3. Identify placement type from known list
# 4. Extract advertiser name
# 5. Parse date range if present (418/452 records have dates)
```

#### Data Quality Checks
1. **Completeness**: Required fields must not be null
2. **Uniqueness**: Deal IDs must be unique per timestamp
3. **Consistency**: Purchase types should align between campaign and deal levels
4. **Range Validation**: Impressions within reasonable bounds (619 - 231M observed)
5. **Date Logic**: Record date should fall within campaign date range when available

---

## =� Data Patterns & Analytics Insights

### Structure Pattern Distribution
- **Complete Standard Pattern**: 402 records (89%)
- **Missing Date Range**: 33 records (7%)
- **Missing Description**: 13 records (3%)
- **Minimal Structure**: 4 records (1%)

### Key Metrics
- **Total Impressions**: 4,011,077,273 across all records
- **Average Impressions**: 3,741,677 per record
- **Impression Range**: 619 (minimum) to 231,810,865 (maximum)

### Top Data Categories
**Placement Types (15 total)**:
- Station: 113 records (25%)
- Infoscreen: 89 records (20%)
- City: 82 records (18%)
- Roadside: 44 records (10%)

**Advertisers (137 total)**:
- Wolt Enterprises: 18 campaigns
- EDEKA ZENTRALE AG & Co. KG: 11 campaigns
- Vodafone GmbH: 10 campaigns

---

## =' Implementation Guidelines for Claude Code Agent

### Phase 1: Database Setup
1. Create PostgreSQL database with UUID extension
2. Implement all 4 tables with proper relationships
3. Add all specified indexes for query performance
4. Populate lookup tables (advertisers, placement_types)

### Phase 2: Data Migration Pipeline
1. Parse existing deal names using regex patterns provided
2. Validate all UUID formats before insertion
3. Handle null values according to column specifications
4. Implement duplicate detection for deal_id + timestamp combinations

### Phase 3: Validation Layer
1. Create validation service with all regex patterns
2. Implement business logic checks for date consistency
3. Add impression range validation by placement type
4. Build data quality reporting dashboard

### Phase 4: API Endpoints
```
GET    /api/v1/campaigns              # List with filtering
GET    /api/v1/campaigns/{deal_id}    # Single campaign
GET    /api/v1/analytics/advertisers  # Performance metrics
GET    /api/v1/analytics/placements   # Placement analysis
POST   /api/v1/campaigns/validate     # Bulk validation
POST   /api/v1/campaigns/import       # CSV import
```

### Required Validation Functions
```python
def validate_deal_name_structure(deal_name: str) -> ValidationResult
def parse_deal_name_components(deal_name: str) -> dict
def validate_impression_range(impressions: float, placement_type: str) -> bool
def check_date_consistency(record_date: datetime, deal_name: str) -> bool
```

---

## =� Generated Analysis Files

### Available Resources
- `temp_csv_analysis_report.json` - Complete structural analysis
- `temp_deal_name_analysis.json` - Advanced pattern analysis with 20 sample parsed records
- Validation rules and database recommendations included in both files

### Data Quality Flags
- **High Priority**: 418 records need date range parsing
- **Medium Priority**: 58% missing campaign metadata needs investigation
- **Low Priority**: Advertiser name standardization (spacing inconsistencies detected)

---

## <� Success Criteria

The implemented system should:
1. **Parse 89% of deal names** into structured components automatically
2. **Validate 100% of UUID fields** against standard format
3. **Handle impression data** across 6+ orders of magnitude (619 to 231M)
4. **Support time-series analysis** with proper date range extraction
5. **Enable advertiser analytics** across 137 unique entities
6. **Provide placement performance** metrics across 15 placement types

This analysis provides complete specifications for implementing a robust campaign data management system with comprehensive validation and analytics capabilities.