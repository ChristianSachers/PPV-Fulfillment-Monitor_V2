# Incremental Data Verification with Comprehensive Upload Reporting (TDD)

## Data Sources
This system processes two distinct data file types with complete specifications:
- **Campaign Setup Data**: `/docs/dataValidation/campaignXLSXstructure.md` - 7,057 campaign records with budgets, goals, runtime dates
- **Performance Reporting Data**: `/docs/dataValidation/reportingCSVstructure.md` - 1,073 performance records with impression metrics, deal name parsing

## Core Workflow
**Upload → Staging Analysis → Batch Report → Full Batch Approval → Production Migration**
- Process all data in temporary staging environment 
- Generate comprehensive report with 4 categories (new/updated/unchanged/inconsistent)
- User approves entire batch or rejects (no partial approvals)
- Migrate approved data to production, delete staging data
- Single user application (no user management required)

## Phase 1: Staging Environment & Analysis Engine (TDD)
**Agent**: backend-engineer
**Dependencies**: Requires campaignXLSXstructure.md and reportingCSVstructure.md specifications

### 1.1 Upload Processing Pipeline
- **Test**: Process uploads in temporary staging database
- **Test**: Parse Campaign Setup files (XLSX format, 7 columns) per campaignXLSXstructure.md
- **Test**: Parse Performance Reporting files (CSV format, 8 columns) per reportingCSVstructure.md
- **Test**: Compare incoming records against production database using UUID matching
- **Test**: Categorize every record into 4 buckets (new/updated/unchanged/inconsistent)
- **Test**: Never touch production database during analysis
- **Implement**: Staging-first processing system

### 1.2 Record Classification Engine
**New Entries** (UUID not in production):
- **Test**: Identify completely new Campaign/Deal records
- **Test**: Validate new records against business rules
- **Test**: Count and catalog all new entries

**Updated Entries** (reasonable changes):
- **Test**: Detect records with acceptable changes (impression increases, etc.)
- **Test**: Validate updates don't violate business logic
- **Test**: Track specific fields that changed per record

**No-Change Discards** (identical to existing):
- **Test**: Identify records identical to production data
- **Test**: Count discarded unchanged records
- **Test**: Option to show/hide these in report

**Inconsistent Data** (suspicious changes):
- **Test**: Flag name changes, date modifications, major decreases
- **Test**: Detect mutual exclusion violations (both Campaign & Deal IDs)
- **Test**: Identify cross-file consistency failures
- **Implement**: Comprehensive record classification

## Phase 2: Upload Report Dashboard (TDD)
**Agent**: ui-design-expert
**Dependencies**: Phase 1 complete, staging data models available

### 2.1 Summary Statistics Display  
- **Test**: Show counts for all 4 categories prominently after analysis completion
- **Test**: Visual progress indicators (pie charts, progress bars) 
- **Test**: High-level impact summary (X new, Y updated, Z flagged)
- **Test**: Processing time and file statistics
- **Test**: No real-time updates required - update after full file analysis
- **Implement**: Static dashboard view with refresh capability

### 2.2 Detailed Category Views
**New Entries Section**:
- **Test**: List all new records with key identifying information
- **Test**: Show validation status for each new record
- **Test**: Expandable details for complex records

**Updated Entries Section**:
- **Test**: Before/after comparison for each updated record
- **Test**: Highlight specific fields that changed
- **Test**: Show why each update was classified as reasonable

**Inconsistent Data Section**:
- **Test**: Before/after comparison with differences highlighted
- **Test**: Specific rule violations listed per record
- **Test**: Recommended actions for each inconsistent record
- **Test**: Export options (copy to clipboard, XLSX download)
- **Implement**: Comprehensive detailed views

## Phase 3: Inconsistent Data Analysis & Export (TDD)
### 3.1 Detailed Inconsistency Reporting
- **Test**: Before/after field comparison with visual diff
- **Test**: Rule violation explanations (why flagged)
- **Test**: Impact assessment (what this change would affect)
- **Test**: Recommended resolution actions per record
- **Implement**: Inconsistency analysis engine

### 3.2 Export Functionality
**Agent**: backend-engineer + ui-design-expert collaboration
- **Test**: Display inconsistent data directly in UI with expandable details
- **Test**: Copy to clipboard (formatted table for pasting into Excel)
- **Test**: XLSX download with inconsistent data organized by error type
- **Test**: Include all context: before/after data, specific rule violations, recommended actions
- **Test**: No filtering required - export all inconsistent data
- **Implement**: Three-format export system (UI display, clipboard, Excel download)

## Phase 4: User Approval Workflow (TDD)
**Agent**: ui-design-expert + backend-engineer collaboration

### 4.1 Full Batch Approval Interface
- **Test**: Clear approve/reject options for entire upload batch
- **Test**: Approval applies to New + Updated entries only (full batch)
- **Test**: Inconsistent data excluded from approval (export only)
- **Test**: Preview showing exactly what will be migrated to production
- **Test**: Single user approval (no user management required)
- **Implement**: Simple batch approval workflow

### 4.2 Production Migration
- **Test**: Migration only occurs after explicit user approval
- **Test**: Transaction-based migration (all approved records or none)
- **Test**: Post-migration confirmation report
- **Test**: Automatic staging data cleanup after successful migration
- **Test**: No rollback functionality required (data validation ensures correctness)
- **Implement**: Simplified production migration system

## Phase 5: Cross-File Validation & Consistency (TDD)
**Agent**: backend-engineer
**Dependencies**: Both campaignXLSXstructure.md and reportingCSVstructure.md specifications

### 5.1 UUID Relationship Validation
- **Test**: Campaign vs Deal mutual exclusivity in reporting files (never both populated)
- **Test**: Cross-file UUID consistency (Deal names must match exactly between files)
- **Test**: Hierarchical name parsing for campaigns (" > " structure, validate last segment)
- **Test**: Strip leading spaces from campaign name segments
- **Test**: Handle campaign names without " > " (treat entire string as last segment)
- **Test**: Orphaned record detection (UUID exists in one file but not the other)
- **Test**: Flag all inconsistencies for user attention (conflicting lines are invalid)
- **Implement**: Cross-file consistency validator

### 5.2 Business Logic Validation - Reasonable Changes
- **Test**: Total impression increases are reasonable (primary acceptable change)
- **Test**: Date consistency validation (start dates shouldn't change - flag as inconsistent)
- **Test**: Name stability validation (Deal names must match exactly - flag changes)
- **Test**: Campaign name last segment validation (after " > " parsing)
- **Test**: Learn new reasonable change patterns from usage (configurable rules)
- **Implement**: Adaptive business rule validation engine

## Phase 6: Future API Integration Preparation (TDD)
**Agent**: backend-engineer
**Optional**: Implementation based on future requirements

### 6.1 API Data Ingestion Framework
- **Test**: Bearer token authentication for API data sources
- **Test**: API data ingestion using same staging analysis pipeline
- **Test**: Rate limiting and error handling for API calls
- **Test**: Data transformation from API format to staging format
- **Implement**: API integration layer (same workflow as file uploads)

## Success Criteria
1. **Complete Transparency** - User sees exactly what will change before full batch approval
2. **4-Category Classification** - Every record classified as new/updated/unchanged/inconsistent
3. **Data Source Compliance** - Process campaignXLSXstructure.md and reportingCSVstructure.md specifications exactly
4. **Inconsistent Data Export** - Full details viewable in UI, copyable to clipboard, downloadable as XLSX
5. **Production Safety** - Nothing touches production until user approves entire batch
6. **Cross-File Validation** - UUID relationships validated, hierarchical names parsed correctly
7. **Single User Simplicity** - No user management, no notifications, no rollback complexity
8. **API Ready** - Architecture supports future Bearer token API integration

## Technical Architecture
- **Staging Database**: Temporary PostgreSQL storage for upload analysis (deleted after migration)
- **Report Dashboard**: React with batch-based updates (no real-time requirements)
- **Export Engine**: Three-format system (UI display, clipboard copy, XLSX download)
- **Migration System**: Simple transaction-safe batch production updates
- **Validation Engine**: Rule-based classification with impression increase detection
- **File Parsers**: XLSX and CSV parsers following documented specifications
- **API Framework**: Bearer token authentication ready for future data sources

## Agent Implementation Assignments
- **Phase 1**: backend-engineer (staging models, file processing)
- **Phase 2**: ui-design-expert (dashboard design, user experience)
- **Phase 3**: backend-engineer + ui-design-expert (export functionality)
- **Phase 4**: ui-design-expert + backend-engineer (approval workflow)
- **Phase 5**: backend-engineer (cross-file validation, business rules)
- **Phase 6**: backend-engineer (optional API integration)