# Campaign XLSX File Structure Documentation

## File Information

**File Name**: `campaings.xlsx`  
**File Size**: 666,864 bytes (651.2 KB)  
**Format**: Microsoft Excel (.xlsx)  
**Sheet Count**: 1  
**Sheet Name**: "Campaign list"  
**Data Dimensions**: 7,058 rows × 7 columns (including header row)  
**Data Records**: 7,057 campaign records  

## Column Structure

### Column 1: Deal/Campaign name
- **Data Type**: VARCHAR/TEXT
- **Max Length**: 500 characters (estimated)
- **Null Count**: 0 (100% populated)
- **Unique Values**: 7,057 (100% unique)
- **Pattern**: `YYYY_NNNNN_NNNN_N_Description_Client_Campaign_Dates_`
- **Example**: `2025_11573_0006_3_Infoscreen_Sierra Germany GmbH_PPV Sonae Sierra PV Berlin_04-06.09._`

**Naming Convention Components**:
- Year (4 digits)
- Primary ID (5 digits)
- Sub ID (4 digits)  
- Type indicator (1 digit)
- Medium/placement type
- Client name
- Campaign description
- Date reference

### Column 2: Runtime
- **Data Type**: VARCHAR/TEXT
- **Format Pattern**: `DD.MM.YYYY-DD.MM.YYYY`
- **Null Count**: 0 (100% populated)
- **Unique Values**: 2,293 distinct date ranges
- **Example**: `04.09.2025-06.09.2025`

**Date Range Characteristics**:
- Consistent DD.MM.YYYY format
- Hyphen separator between start and end dates
- All dates appear to be in 2025
- Campaign durations vary from 1 day to several months

### Column 3: Impression goal
- **Data Type**: INTEGER (stored as mixed type)
- **Null Count**: 0 (100% populated)
- **Unique Values**: 4,089 distinct values
- **Range**: 3,000 to 720,000+ impressions
- **Example**: `720000`

**Value Distribution**:
- Minimum values around 3,000
- Maximum values exceed 700,000
- Most values are whole numbers
- Some scientific notation in source data

### Column 4: Budget ¬
- **Data Type**: DECIMAL(10,2)
- **Null Count**: 616 (8.7% missing)
- **Unique Values**: 5,227 distinct values
- **Range**: ¬0.15 to ¬5,464.8
- **Currency**: Euro (¬)
- **Example**: `5464.8`

**Budget Characteristics**:
- 2 decimal places precision
- Wide value range
- Missing values represent incomplete data
- Values align with impression goals and CPM calculations

### Column 5: CPM ¬
- **Data Type**: DECIMAL(8,2)
- **Null Count**: 0 (100% populated)
- **Unique Values**: 902 distinct values
- **Range**: ¬0.01 to ¬45.00 (estimated)
- **Currency**: Euro (¬)
- **Example**: `7.59`

**CPM Characteristics**:
- Cost per thousand impressions
- 2 decimal places precision
- No missing values
- Values used in budget calculations

### Column 6: Deal/Campaign ID
- **Data Type**: UUID
- **Format**: Standard UUID format (8-4-4-4-12 hex digits)
- **Null Count**: 0 (100% populated)
- **Unique Values**: 7,057 (100% unique)
- **Example**: `089552b0-a53c-41a7-8299-c499310af484`

**UUID Characteristics**:
- Version 4 UUIDs
- Perfect uniqueness across dataset
- 36 characters including hyphens
- Suitable for primary key usage

### Column 7: Buyer
- **Data Type**: VARCHAR/TEXT
- **Max Length**: 100 characters (estimated)
- **Null Count**: 0 (100% populated)
- **Unique Values**: 68 distinct buyers
- **Example**: `WEISCHER_JVB_GMBH < Displayce_rtb (Seat 4227)`

**Buyer Characteristics**:
- Structured format with company and seat information
- Contains "Not set" placeholder values
- Represents advertising agencies/buyers
- Many-to-one relationship with campaigns

## Data Relationships

### Primary Key Candidates
1. **Deal/Campaign ID** (UUID) - Perfect uniqueness, recommended primary key
2. **Deal/Campaign name** - Unique but long, suitable for alternate key

### Foreign Key Relationships
- **Buyer** ’ Buyers table (68 unique buyers across 7,057 campaigns)
- **Runtime dates** ’ Potential calendar/date dimension

### Calculated Relationships
- **Budget = (Impression goal × CPM) ÷ 1000** (mathematical relationship)

## Data Patterns

### Campaign Naming Convention
```
Pattern: YYYY_XXXXX_YYYY_X_Type_Client_Description_Dates_
- YYYY: Campaign year (2025)
- XXXXX: 5-digit primary identifier
- YYYY: 4-digit sub-identifier  
- X: Single digit type/category code
- Type: Media type (Infoscreen, Digital, etc.)
- Client: Client company name
- Description: Campaign description
- Dates: Date reference in DD-DD.MM format
```

### Runtime Date Patterns
```
Format: DD.MM.YYYY-DD.MM.YYYY
- Start date always before end date
- Consistent German date format (DD.MM.YYYY)
- All campaigns appear to be in 2025
- Duration ranges from days to months
```

### Buyer Naming Patterns
```
Format: COMPANY_NAME < Platform_Type (Seat XXXX)
- Company: Advertising agency name
- Platform: Technology platform identifier
- Seat: Numeric seat identifier for programmatic buying
- Special case: "Not set" for incomplete records
```

## Database Schema Requirements

### Table Structure Recommendations

**Primary Table: campaigns**
- **Primary Key**: campaign_id (UUID)
- **Unique Constraints**: campaign_name, campaign_id
- **Indexes Needed**: buyer_id, start_date, end_date, campaign_name

**Related Tables**:
- **buyers**: Normalize buyer information
- **campaign_types**: Extract campaign type classification
- **date_ranges**: Optional date dimension for reporting

### Data Type Specifications

```sql
campaign_id          UUID PRIMARY KEY
campaign_name        VARCHAR(500) NOT NULL UNIQUE
start_date          DATE NOT NULL
end_date            DATE NOT NULL  
impression_goal     BIGINT NOT NULL
budget_euros        DECIMAL(12,2) NULL
cpm_euros           DECIMAL(8,2) NOT NULL
buyer_id            INTEGER REFERENCES buyers(id)
```

### Constraint Requirements

**Business Rules**:
- start_date < end_date
- impression_goal > 0
- cpm_euros >= 0
- budget_euros >= 0 (when not null)

**Data Validation**:
- UUID format validation for campaign_id
- Date format validation for runtime conversion
- Numeric validation for impression_goal
- Budget consistency checks against CPM and impressions

## Statistical Summary

| Metric | Value |
|--------|-------|
| Total Records | 7,057 |
| Complete Records | 6,441 (91.3%) |
| Records with Missing Budget | 616 (8.7%) |
| Unique Campaigns | 7,057 (100%) |
| Unique Buyers | 68 |
| Unique Date Ranges | 2,293 |
| Unique CPM Values | 902 |
| Data Completeness | 91.3% |

## Import Considerations

### Data Conversion Requirements
1. **Runtime Field**: Split "DD.MM.YYYY-DD.MM.YYYY" into separate start_date and end_date columns
2. **Impression Goal**: Convert to INTEGER type
3. **Budget**: Handle NULL values appropriately
4. **Buyer**: Normalize to foreign key relationship

### Validation Points
1. UUID format validation
2. Date parsing and validation
3. Numeric type conversion
4. Business rule validation (dates, amounts)
5. Referential integrity for buyers

### Performance Considerations
- Index on campaign_id (primary key)
- Index on buyer_id (foreign key)
- Composite index on start_date, end_date for date range queries
- Index on campaign_name for search functionality

## File Processing Notes

- File uses standard Excel formatting
- No merged cells or complex structures
- Header row in row 1
- Data starts from row 2
- UTF-8 compatible text encoding
- Standard numeric formatting for currency and integers