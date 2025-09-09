# Product Owner Clarifications Required

## Overview
This document consolidates all questions and assumptions from the implementation phase files (1.1 through 6.1) that require product owner clarification before development begins. These clarifications will ensure implementation aligns with business requirements and user expectations.

---

## Phase 1.1: Upload Processing Pipeline

### Questions Requiring Clarification

1. **File Size Limits**: What are the maximum file sizes we should support for XLSX and CSV uploads?
   - **Answered**: Maximum file size is 250 MB

2. **Concurrent Processing**: Should the system support multiple simultaneous uploads, or enforce single upload at a time?
   - **Answered**: System should support multiple uploads in parallel (e.g. a set of campaign and reporting information in 2 files uploaded together.)

3. **Staging Data Retention**: How long should staging data be retained after successful migration or rejection?
   - **Answered**: Staging data does not need to be retained after successful migration or rejection

4. **Error Recovery**: If processing fails mid-way, should users be able to resume or must they restart completely?
   - **Answered**: They must restart completely but a comprehensive explanation why it failed should be given

5. **Production Matching Strategy**: For "Updated Entries" classification, which fields are acceptable to change vs. which should trigger "Inconsistent" classification?
   - **Answered**: 
     - Acceptable: Total Impressions
     - Inconsistent: Deal/Campaign Name, Runtime, Impression goal, Budget, CPM, Buyer, Core DSP Campaign Name, Deal Name, Campaign Purchase Type, Deal Purchase Type

---

## Phase 1.2: Record Classification Engine

### Questions Requiring Clarification

1. **Update Thresholds**: What constitutes a "reasonable" impression increase vs. a suspicious change? (e.g., 50% increase OK, 500% suspicious?)

2. **Name Changes**: Are there any circumstances where Deal name changes should be acceptable rather than flagged as inconsistent?

3. **Date Change Rules**: Should ANY date changes be flagged as inconsistent, or are there acceptable scenarios (e.g., extending end dates)?

4. **Cross-File Timing**: If Campaign and Performance files are uploaded separately, how should timing mismatches be handled?

5. **Business Rule Priority**: When multiple business rules conflict, what is the priority order for classification decisions?

---

## Phase 2.1: Summary Statistics Display

### Questions Requiring Clarification

1. **Chart Library Preference**: Is there a preferred charting library for the visual indicators (Chart.js, D3, etc.)?

2. **Color Scheme**: Are there brand colors or accessibility requirements for the category color coding?

3. **Auto-Refresh**: Should the dashboard automatically refresh while processing is ongoing, or only after completion?

4. **Mobile Priority**: What is the relative importance of mobile vs. desktop experience for this dashboard?

5. **Localization**: Does the dashboard need to support multiple languages for the summary text?

---

## Phase 2.2: Detailed Category Views

### Questions Requiring Clarification

1. **Pagination Strategy**: How many records should be displayed per page for each category? (e.g., 50, 100, 200?)

2. **Default Category View**: Which category should be displayed by default when users first access detailed views?

3. **Export Granularity**: Should users be able to export individual records, or only bulk exports by category?

4. **Search Functionality**: Do users need search/filter capabilities within each category section?

5. **Record Navigation**: Should users be able to navigate directly from one record to related records in other categories?

---

## Phase 3.1: Detailed Inconsistency Reporting

### Questions Requiring Clarification

1. **Resolution Authority**: Can users mark inconsistencies as "acceptable" and proceed with batch approval, or must all inconsistencies be resolved?

2. **Impact Assessment Scope**: How deeply should impact assessment analyze cascade effects (immediate relationships only, or multiple levels deep)?

3. **Recommendation Automation**: Should the system automatically apply certain low-risk recommendations, or require manual review for all?

4. **Historical Context**: Should inconsistency analysis consider historical patterns of acceptable changes for similar records?

5. **Performance Limits**: What is the maximum number of inconsistent records the system should handle efficiently (100s, 1000s, 10,000s)?

---

## Phase 3.2: Export Functionality

### Questions Requiring Clarification

1. **Export Permissions**: Are there any access control requirements for export functionality (user roles, data sensitivity)?

2. **Export Retention**: How long should generated Excel files be available for download before cleanup?

3. **Export Scope**: Should users be able to export data from categories other than inconsistent data (new, updated entries)?

4. **Excel Complexity**: How sophisticated should Excel formatting be (basic tables vs. advanced formatting with charts/formulas)?

5. **Export Notifications**: Should users receive email notifications when large exports are ready for download?

---

## Phase 4.1: Full Batch Approval Interface

### Questions Requiring Clarification

1. **Approval Timeout**: How long should approval sessions remain active before requiring re-authentication or refresh?

2. **Partial Approval**: Should there be any mechanism for partial approval of batches, or is all-or-nothing the requirement?

3. **Approval Reversibility**: Once approved and migrated, is there any way to reverse or undo an approval decision?

4. **Concurrent Processing**: Should the system prevent new uploads while an approval is pending, or allow concurrent processing?

5. **Approval Notifications**: Are any external notifications required when batches are approved or rejected (email, webhook, etc.)?

---

## Phase 4.2: Production Migration

### Questions Requiring Clarification

1. **Migration Timing**: Should migration happen immediately after approval, or should there be a scheduled migration window?

2. **Production Backup**: Are automated production database backups required before each migration?

3. **Migration Notifications**: Should external systems be notified when migrations complete (webhooks, emails, etc.)?

4. **Migration Performance**: What is the acceptable timeframe for migrating large batches (7000+ records)?

5. **Failure Recovery**: If migration fails, should users be able to retry immediately or wait for manual intervention?

---

## Phase 5.1: UUID Relationship Validation

### Questions Requiring Clarification

1. **Name Matching Tolerance**: Should Deal name matching be exactly case-sensitive, or allow for minor variations (case differences, whitespace)?

2. **Orphaned Record Handling**: Are orphaned records (UUIDs in one file but not the other) always errors, or can they be acceptable in some cases?

3. **Hierarchical Complexity**: How deep can hierarchical campaign names go? Are there limits to the number of " > " segments?

4. **Validation Priority**: Which cross-file validation failures should block approval vs. which should be warnings?

5. **Historical Context**: Should validation consider historical patterns of acceptable cross-file relationships?

---

## Phase 5.2: Business Logic Validation

### Questions Requiring Clarification

1. **Impression Thresholds**: Are there maximum acceptable impression increases (e.g., 1000% increase might be suspicious)?

2. **Date Change Exceptions**: Are there any scenarios where start date changes should be acceptable (campaign rescheduling, etc.)?

3. **Name Change Tolerance**: Should the system support any name variations (abbreviations, formatting changes) or require exact matches?

4. **Rule Learning Authority**: Who has authority to approve new business rules suggested by the adaptive learning system?

5. **Rule Override Capability**: Should users be able to override business rule violations in special circumstances?

---

## Phase 6.1: API Data Ingestion Framework

### Questions Requiring Clarification

1. **API Data Sources**: Which specific API data sources should be supported initially? What are their authentication and format requirements?

2. **Ingestion Scheduling**: Should API data ingestion be triggered manually, on a schedule, or both?

3. **Data Volume Expectations**: What volume of data is expected from API sources? How does this compare to file upload volumes?

4. **Error Notification**: Should API ingestion errors trigger notifications (email, webhook, dashboard alerts)?

5. **API Source Priority**: If multiple API sources are configured, is there a priority order for ingestion?

---

## Priority Questions for Immediate Clarification

Based on the implementation dependencies and impact, the following questions require immediate clarification:

### High Priority (Blocks Core Development)
1. **Update Thresholds** (Phase 1.2): Essential for classification engine
2. **Resolution Authority** (Phase 3.1): Determines approval workflow design
3. **Partial Approval** (Phase 4.1): Affects entire approval system architecture
4. **Name Matching Tolerance** (Phase 5.1): Impacts validation logic
5. **Impression Thresholds** (Phase 5.2): Critical for business rule validation

### Medium Priority (Affects User Experience)
1. **Pagination Strategy** (Phase 2.2): Impacts performance and usability
2. **Chart Library Preference** (Phase 2.1): Affects implementation approach
3. **Export Scope** (Phase 3.2): Determines export functionality scope
4. **Migration Timing** (Phase 4.2): Affects user workflow
5. **API Data Sources** (Phase 6.1): Determines initial API implementation scope

### Low Priority (Nice to Have Clarifications)
1. **Localization** (Phase 2.1): Can be addressed in future iterations
2. **Excel Complexity** (Phase 3.2): Can start with basic implementation
3. **Historical Context** (Multiple phases): Can be added as enhancement
4. **Export Notifications** (Phase 3.2): Can be implemented later
5. **API Source Priority** (Phase 6.1): Relevant only with multiple sources

---

## Summary

**Total Questions**: 55 questions across all phases
**Answered Questions**: 5 questions (Phase 1.1)
**Remaining Questions**: 50 questions requiring clarification

The implementation can begin with Phase 1.1 (partially answered) while awaiting clarification on the priority questions listed above. The high-priority questions should be resolved before proceeding with their respective phases to avoid rework and ensure proper architecture decisions.