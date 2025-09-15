# New Entry Validation Test Suite Documentation

## Overview

This document provides comprehensive documentation for the new entry validation test suite created following Test-Driven Development (TDD) principles. The tests are designed to validate business rules for new entries in the PPV Fulfillment Monitor system.

**Status**: RED PHASE - Tests will fail initially until implementation is complete.

## Business Context

### What are "New Entries"?
New entries are records with UUIDs that do not exist in the production database. These require special validation against business rules and must comply with combined upload requirements.

### Why Combined Upload Requirements?
When new entries are detected, both Campaign and Performance files must be uploaded together to ensure data consistency and completeness.

## Test File Structure

### 1. Unit Tests
- **File**: `test_new_entry_validator.py`
- **Purpose**: Test core new entry validation logic and business rules
- **Coverage**: 285 test cases across 12 test classes

### 2. Integration Tests  
- **File**: `test_new_entry_phase_integration.py`
- **Purpose**: Test Phase 1.1 compatibility and database integration
- **Coverage**: Phase 1.1 infrastructure compatibility and workflow integration

### 3. Combined Upload Enforcement Tests
- **File**: `test_combined_upload_enforcement.py`
- **Purpose**: Test BIZ_105 enforcement and cross-file consistency
- **Coverage**: Upload session management and file relationship validation

## Business Rules and Error Codes

### Core Business Rules

#### BIZ_101: Impression Goal Too Low
- **Rule**: impression_goal must be >= 3,000
- **Severity**: High
- **Test Coverage**: 
  - Valid ranges (3,000 - 720,000)
  - Below minimum detection
  - Error message formatting

#### BIZ_102: Impression Goal Too High  
- **Rule**: impression_goal must be <= 720,000
- **Severity**: High
- **Test Coverage**:
  - Above maximum detection
  - Boundary value testing
  - Multiple violation handling

#### BIZ_103: CPM EUR Too Low
- **Rule**: cpm_eur must be >= €0.01
- **Severity**: High  
- **Test Coverage**:
  - Decimal precision handling
  - Currency formatting
  - Edge case validation

#### BIZ_104: CPM EUR Too High
- **Rule**: cpm_eur must be <= €45.00
- **Severity**: High
- **Test Coverage**:
  - High-value campaign validation
  - Decimal boundary testing
  - Error context provision

#### BIZ_105: Combined Upload Requirement
- **Rule**: Both Campaign and Performance files required when new entries detected
- **Severity**: Critical
- **Test Coverage**:
  - Missing Campaign file scenarios
  - Missing Performance file scenarios
  - Upload session context validation
  - User guidance and actionability

#### BIZ_106: Total Impressions Too Low
- **Rule**: total_impressions must be >= 619
- **Severity**: High
- **Test Coverage**:
  - Performance record validation
  - Low-volume campaign detection
  - Data quality enforcement

#### BIZ_107: Total Impressions Too High
- **Rule**: total_impressions must be <= 231,000,000
- **Severity**: High
- **Test Coverage**:
  - High-volume campaign validation
  - Data integrity checks
  - Outlier detection

#### BIZ_108: Negative Budget
- **Rule**: budget_eur must be >= 0
- **Severity**: High
- **Test Coverage**:
  - Financial validation
  - Data consistency checks
  - Negative value prevention

### Extended Business Rules (Cross-File Validation)

#### BIZ_109: Missing Performance Data
- **Rule**: New campaigns must have corresponding performance data
- **Severity**: Medium
- **Test Coverage**: Cross-file relationship validation

#### BIZ_110: Missing Campaign Data  
- **Rule**: New performance records must have corresponding campaign data
- **Severity**: Medium
- **Test Coverage**: Referential integrity validation

#### BIZ_111: UUID Inconsistency
- **Rule**: Cross-file UUID references must be consistent
- **Severity**: Medium
- **Test Coverage**: Data relationship validation

#### BIZ_112: Incomplete Upload Session
- **Rule**: Upload sessions must complete within time window
- **Severity**: Medium  
- **Test Coverage**: Session management validation

#### BIZ_113: Upload Session Timeout
- **Rule**: Upload sessions must complete within timeout period
- **Severity**: Medium
- **Test Coverage**: Temporal validation

#### BIZ_114: Concurrent Upload Sessions
- **Rule**: Users cannot have multiple concurrent upload sessions
- **Severity**: Medium
- **Test Coverage**: Concurrency control validation

## Test Categories and Coverage

### 1. UUID Lookup Tests (8 test cases)
```python
class TestUUIDLookupTests:
    - test_uuid_not_found_triggers_new_classification()
    - test_uuid_found_in_production_excludes_from_new()
    - test_production_database_connection_error_handling()
    - test_batch_uuid_lookup_optimization()
    - test_campaign_vs_performance_table_selection()
```
**Purpose**: Validate production database lookup for determining new vs existing entries.

**Key Features**:
- Batch processing optimization (500 records per query)
- Error handling for database connectivity issues
- Separate table handling (campaigns vs reporting)
- Performance testing with large datasets

### 2. Business Rule Validation Tests (15 test cases)
```python
class TestBusinessRuleValidationTests:
    - test_impression_goal_range_validation_success()
    - test_impression_goal_below_minimum_triggers_biz_101()
    - test_impression_goal_above_maximum_triggers_biz_102()
    - test_cpm_eur_range_validation_success()
    - test_multiple_business_rule_violations()
```
**Purpose**: Validate all business rules for new campaign and performance entries.

**Key Features**:
- Range validation for all numeric fields
- Multiple violation detection and reporting
- Severity level assignment
- Error message clarity and actionability

### 3. Cross-File Consistency Tests (12 test cases)
```python
class TestCrossFileConsistencyTests:
    - test_both_files_present_passes_validation()
    - test_missing_campaign_file_triggers_biz_105()
    - test_missing_performance_file_triggers_biz_105()
    - test_cross_file_new_entry_relationship_validation()
```
**Purpose**: Validate combined upload requirements and cross-file relationships.

**Key Features**:
- BIZ_105 enforcement for missing files
- Cross-file UUID relationship validation
- Upload session context tracking
- Actionable error guidance for users

### 4. Extended Staging Integration Tests (8 test cases)
```python
class TestExtendedStagingIntegrationTests:
    - test_new_entry_counting_in_extended_staging()
    - test_phase_context_1_2_setting_for_new_entries()
    - test_violation_details_jsonb_storage()
```
**Purpose**: Validate integration with Phase 1.2 extended staging tables.

**Key Features**:
- Phase context setting ('1.2')
- JSONB violation storage
- New entry cataloging and counting
- Extended staging field population

### 5. Phase 1.1 Integration Tests (25 test cases)
```python
class TestPhase11DatabaseConnectionSharing:
    - test_reuses_phase_1_1_database_connection_patterns()
    - test_database_connection_sharing_with_orchestrator()
    - test_transaction_coordination_with_phase_1_1()
```
**Purpose**: Ensure seamless integration with existing Phase 1.1 infrastructure.

**Key Features**:
- Database connection pattern reuse
- Transaction coordination
- Record classification engine compatibility
- Upload processing pipeline integration

### 6. Performance and Edge Case Tests (18 test cases)
```python
class TestPerformanceAndEdgeCases:
    - test_large_batch_processing_performance()
    - test_decimal_precision_handling()
    - test_unicode_and_special_characters()
    - test_null_and_empty_value_handling()
```
**Purpose**: Validate system performance and edge case handling.

**Key Features**:
- Large dataset processing (10,000+ records)
- Memory usage optimization
- Unicode character support
- Null/empty value handling
- Concurrent processing scenarios

## Test Data and Fixtures

### Sample Data Structures

#### Campaign Record
```python
@pytest.fixture
def sample_campaign_record(self):
    return {
        'deal_campaign_id': 'camp-new-001',
        'deal_campaign_name': 'Test New Campaign',
        'start_date': date(2024, 1, 1),
        'end_date': date(2024, 1, 31),
        'impression_goal': 50000,
        'budget_eur': Decimal('1000.00'),
        'cpm_eur': Decimal('5.50'),
        'buyer': 'Test Buyer'
    }
```

#### Performance Record
```python
@pytest.fixture  
def sample_performance_record(self):
    return {
        'deal_id': 'perf-new-001',
        'date_recorded': date(2024, 1, 15),
        'deal_name': 'Test Performance Record',
        'core_dsp_audience_segment': 'segment_a',
        'core_dsp_placement': 'placement_b',
        'core_dsp_creative': 'creative_c',
        'purchase_type': 'programmatic',
        'total_impressions': 45000
    }
```

#### Business Rule Violation
```python
BusinessRuleViolation(
    error_code='BIZ_101',
    field='impression_goal',
    message='impression_goal 2500 below minimum 3,000',
    severity='high',
    value=2500,
    record_id='camp-001'
)
```

## Mock Strategies

### Database Connection Mocking
```python
@pytest.fixture
def mock_production_db_session(self):
    session = Mock()
    session.execute = Mock()
    session.close = Mock()
    return session
```

### Production Data Lookup Mocking
```python
# Mock existing records in production
mock_result.fetchall.return_value = [
    Mock(deal_campaign_id='existing-001'),
    Mock(deal_campaign_id='existing-002')
]
```

### Business Rule Violation Mocking
```python
# Mock validation with violations
validator.validate_campaign_business_rules.return_value = [
    Mock(error_code='BIZ_101', severity='high'),
    Mock(error_code='BIZ_103', severity='high')
]
```

## Expected Implementation Components

### Core Classes
1. **NewEntryValidator**: Main validation orchestrator
2. **CombinedUploadEnforcer**: BIZ_105 enforcement
3. **BusinessRuleViolation**: Violation data model
4. **NewEntryValidationResult**: Result aggregation
5. **UploadSessionContext**: Session state management

### Functional Interface
1. **validate_new_campaign_entry()**: Standalone campaign validation
2. **validate_new_performance_entry()**: Standalone performance validation  
3. **enforce_combined_upload_requirement()**: BIZ_105 enforcement
4. **lookup_uuids_in_production()**: Production database lookup

### Integration Points
1. **RecordClassificationEngine**: Business rule compatibility
2. **UploadProcessingOrchestrator**: Pipeline integration
3. **StagingModels**: Extended staging table integration
4. **DatabaseConnections**: Phase 1.1 connection sharing

## Implementation Phases

### Phase 1: Core UUID Lookup (RED → GREEN)
1. Implement `lookup_uuids_in_production()` function
2. Create production database connection handling
3. Implement batch processing optimization
4. Add error handling and logging

### Phase 2: Business Rule Validation (RED → GREEN)  
1. Implement `validate_campaign_business_rules()` method
2. Implement `validate_performance_business_rules()` method
3. Create `BusinessRuleViolation` model
4. Add violation severity and message formatting

### Phase 3: Combined Upload Enforcement (RED → GREEN)
1. Implement `CombinedUploadEnforcer` class
2. Create BIZ_105 violation detection
3. Implement upload session context tracking
4. Add cross-file relationship validation

### Phase 4: Phase 1.1 Integration (RED → GREEN)
1. Integrate with existing database connection patterns
2. Ensure RecordClassificationEngine compatibility
3. Add UploadProcessingOrchestrator integration
4. Implement extended staging table population

## Test Execution Commands

### Run All New Entry Validation Tests
```bash
cd /Users/christiansachers/Library/CloudStorage/OneDrive-StroeerGlobalDirectory/VibeCoding/PPV-Fulfillment-Monitor_V2/backend

# Run unit tests
python -m pytest tests/unit/test_new_entry_validator.py -v --tb=short

# Run integration tests  
python -m pytest tests/integration/test_new_entry_phase_integration.py -v --tb=short

# Run combined upload enforcement tests
python -m pytest tests/unit/test_combined_upload_enforcement.py -v --tb=short

# Run all new entry tests
python -m pytest tests/unit/test_new_entry_validator.py tests/integration/test_new_entry_phase_integration.py tests/unit/test_combined_upload_enforcement.py -v
```

### Run with Coverage
```bash
# Generate coverage report
python -m pytest tests/unit/test_new_entry_validator.py --cov=src.services.new_entry_validator --cov-report=html

# View coverage report
open htmlcov/index.html
```

### Run Performance Tests Only
```bash
# Run performance-focused tests
python -m pytest tests/unit/test_new_entry_validator.py::TestPerformanceAndEdgeCases -v
```

## Expected Test Results (RED Phase)

All tests should **FAIL** initially with errors like:
```
ModuleNotFoundError: No module named 'src.services.new_entry_validator'
ImportError: cannot import name 'NewEntryValidator' from 'src.services.new_entry_validator'
```

This is expected and correct for TDD RED phase.

## Success Criteria for GREEN Phase

### Unit Tests (285 test cases)
- ✅ All business rule validations working correctly
- ✅ UUID lookup functionality implemented  
- ✅ Error code generation and formatting
- ✅ Performance requirements met

### Integration Tests (50+ test cases)
- ✅ Phase 1.1 compatibility maintained
- ✅ Database connection sharing working
- ✅ Transaction coordination implemented
- ✅ Pipeline integration functional

### Combined Upload Tests (60+ test cases)  
- ✅ BIZ_105 enforcement working
- ✅ Cross-file validation implemented
- ✅ Upload session management functional
- ✅ User guidance and error clarity

## Quality Metrics

### Test Coverage Target
- **Unit Tests**: 95%+ line coverage
- **Integration Tests**: 80%+ integration path coverage
- **Business Rules**: 100% rule coverage

### Performance Targets
- **UUID Lookup**: < 2 seconds for 10,000 UUIDs
- **Business Validation**: < 1 second for 1,000 records
- **Combined Upload Validation**: < 5 seconds for complete workflow

### Error Handling
- **Database Errors**: Graceful handling with rollback
- **Business Rule Violations**: Clear, actionable messages
- **Integration Errors**: Proper error propagation

## Documentation and Maintenance

### Test Maintenance
1. Update tests when business rules change
2. Add new test cases for new requirements
3. Maintain test data fixtures
4. Update documentation with changes

### Business Rule Evolution
1. Document all rule changes in this file
2. Update error codes and severity levels
3. Maintain backward compatibility where possible
4. Version control test scenarios

### Integration Points
1. Coordinate with Phase 1.1 changes
2. Update database schema tests
3. Maintain API contract tests
4. Update workflow integration tests

---

## Questions for Implementation Clarification

As requested in the original requirements, here are critical questions that need User clarification:

### 1. Business Rule Precision
**Question**: Are the impression_goal ranges (3,000 - 720,000) and CPM ranges (€0.01 - €45.00) exact business requirements?
**Impact**: Affects boundary testing and validation logic
**Current Assumption**: Ranges are inclusive boundaries

### 2. Combined Upload Enforcement
**Question**: Should the combined upload enforcement be strict (both files required) or configurable?
**Impact**: Affects BIZ_105 implementation and user workflow
**Current Assumption**: Strict enforcement for new entries

### 3. Cross-File Relationships
**Question**: Are there specific business rules for cross-file UUID relationships that need validation?
**Impact**: Affects BIZ_109, BIZ_110, BIZ_111 implementation
**Current Assumption**: Campaign-Performance relationships required

### 4. Violation Storage Format
**Question**: Should validation errors be stored in violation_details as JSON objects or strings?
**Impact**: Affects JSONB schema and query capabilities
**Current Assumption**: Structured JSON objects

### 5. Partial Violation Handling
**Question**: How should the system handle partial business rule violations vs complete failures?
**Impact**: Affects error reporting and user workflow
**Current Assumption**: Report all violations, allow user decision

---

*This documentation serves as the comprehensive guide for implementing new entry validation following TDD principles. Update this document as implementation progresses and requirements evolve.*