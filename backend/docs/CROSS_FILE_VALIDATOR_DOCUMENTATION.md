# Cross-File Validator Documentation

## Overview

The CrossFileValidator is a comprehensive validation system that coordinates Campaign and Performance file processing, enforces combined upload requirements, and validates relationships between files. It serves as a critical component in Phase 1.2 of the PPV Fulfillment Monitor system.

## Key Features

### 1. Combined Upload Enforcement
- **Requirement**: Both Campaign (XLSX) and Performance (CSV) files must be uploaded together
- **Error Code**: BIZ_105 - "Combined upload incomplete"
- **Behavior**: Rejects any upload attempt that contains only one file type

### 2. Cross-File Relationship Validation
- **Deal Name Matching**: Case-sensitive exact string matching between Campaign and Performance files
- **UUID Relationships**: Validates matching UUIDs across file types
- **Error Codes**:
  - BIZ_104: "Cross-file relationship failure"
  - BIZ_101: "Deal name modification not allowed" (case mismatch)
  - BIZ_106: "Campaign/Deal ID conflict"

### 3. Hierarchical Name Parsing
- **Structure**: Validates " > " (space-greater-space) separator usage
- **Error Code**: VAL_015 - "Invalid hierarchical structure"
- **Validation Rules**:
  - No consecutive separators (e.g., ">>")
  - No empty segments
  - No trailing/leading separators
  - Proper whitespace handling around separators

### 4. Phase 1.1 Integration
- **Reuses**: Existing file upload tracking and batch management
- **Extends**: Shared processing_batches table coordination
- **Maintains**: Backward compatibility with Phase 1.1 error codes

## Architecture

```python
class CrossFileValidator:
    def __init__(self, staging_db_url: Optional[str] = None)
    def validate_combined_upload(self, batch_id: str) -> ValidationResult
    def validate_cross_file_relationships(self, campaign_records, performance_records) -> ValidationResult
    def validate_hierarchical_names(self, records) -> List[ValidationError]
    def validate_batch_cross_file_consistency(self, batch_id: str) -> ValidationResult
```

## Validation Rules

### Combined Upload Rules

1. **Both File Types Required**
   ```python
   # Valid: Both files present
   campaigns_count > 0 AND performance_count > 0
   
   # Invalid: Missing Campaign file
   campaigns_count == 0 AND performance_count > 0  # → BIZ_105
   
   # Invalid: Missing Performance file
   campaigns_count > 0 AND performance_count == 0  # → BIZ_105
   
   # Invalid: Both files missing
   campaigns_count == 0 AND performance_count == 0  # → BIZ_105
   ```

### Cross-File Relationship Rules

1. **Exact Deal Name Matching (Case-Sensitive)**
   ```python
   # Valid
   campaign_name = "Brand A > Campaign 2024 > Q1 Launch"
   performance_deal_name = "Brand A > Campaign 2024 > Q1 Launch"  # Exact match
   
   # Invalid - Case mismatch
   campaign_name = "Brand A > Campaign 2024 > Q1 Launch"
   performance_deal_name = "brand a > campaign 2024 > q1 launch"  # → BIZ_101
   
   # Invalid - Name not found
   campaign_name = "Brand A > Campaign 2024 > Q1 Launch"
   performance_deal_name = "Different Campaign Name"  # → BIZ_104
   ```

2. **UUID Relationship Validation**
   ```python
   # Valid
   campaign_uuid = "11111111-1111-1111-1111-111111111111"
   performance_uuid = "11111111-1111-1111-1111-111111111111"  # Matching
   
   # Invalid - UUID mismatch with matching names
   campaign_uuid = "11111111-1111-1111-1111-111111111111"
   performance_uuid = "22222222-2222-2222-2222-222222222222"  # → BIZ_106
   
   # Invalid - UUID not found
   performance_uuid = "99999999-9999-9999-9999-999999999999"  # → BIZ_104
   ```

### Hierarchical Name Rules

1. **Valid Hierarchical Structures**
   ```python
   # Valid examples
   "Level1 > Level2 > Level3"
   "Campaign > Main Campaign > Sub Campaign"
   "Deal > Parent > Child > Grandchild"
   "Simple Campaign Name"  # Non-hierarchical is allowed
   ```

2. **Invalid Hierarchical Structures**
   ```python
   # Invalid - Multiple consecutive separators
   "Level1 >> Level2 > Level3"  # → VAL_015
   
   # Invalid - Empty segments
   "Campaign > > Sub Campaign"  # → VAL_015
   
   # Invalid - Trailing separator
   "Level1 > Level2 > "  # → VAL_015
   
   # Invalid - Leading separator
   " > Level1 > Level2"  # → VAL_015
   ```

## Error Codes and Messages

### Phase 1.1 Compatible Codes
| Code    | Message                        | Priority | Phase Compatibility |
|---------|--------------------------------|----------|-------------------|
| VAL_015 | Invalid hierarchical structure | MEDIUM   | both              |

### Phase 1.2 Specific Codes
| Code    | Message                           | Priority | Phase Compatibility |
|---------|-----------------------------------|----------|-------------------|
| BIZ_101 | Deal name modification not allowed| CRITICAL | 1.2               |
| BIZ_104 | Cross-file relationship failure   | CRITICAL | 1.2               |
| BIZ_105 | Combined upload incomplete        | CRITICAL | 1.2               |
| BIZ_106 | Campaign/Deal ID conflict         | HIGH     | 1.2               |

## Usage Examples

### Basic Validation

```python
from src.services.cross_file_validator import CrossFileValidator

# Initialize validator
validator = CrossFileValidator()

# Validate combined upload requirement
result = validator.validate_combined_upload(batch_id)
if not result.is_valid:
    for error in result.errors:
        print(f"Error {error.error_code}: {error.message}")

# Validate cross-file relationships
relationship_result = validator.validate_cross_file_relationships(
    campaign_records, 
    performance_records
)

# Comprehensive batch validation
batch_result = validator.validate_batch_cross_file_consistency(batch_id)
```

### Error Handling

```python
from src.services.cross_file_validator import CrossFileValidationError

try:
    result = validator.validate_combined_upload(batch_id)
except CrossFileValidationError as e:
    print(f"Validation failed: {e}")
    print(f"Context: {e.context}")
```

## Integration with Phase 1.1

### Database Integration
- **Reuses**: StagingDatabase class and connection management
- **Extends**: Batch tracking and record counting functionality
- **Maintains**: Transaction isolation and rollback capabilities

### Batch Management Integration
```python
# Integrates with existing batch operations
staging_db = StagingDatabase()
campaign_records = staging_db.get_campaign_batch_by_processing_id(batch_id)
performance_records = staging_db.get_reporting_batch_by_processing_id(batch_id)

# Validates using Phase 1.1 infrastructure
validator = CrossFileValidator()
result = validator.validate_batch_cross_file_consistency(batch_id)
```

### Error Code System Integration
```python
from src.services.unified_error_codes import get_error_info, is_phase_11_compatible

# Check error code compatibility
if is_phase_11_compatible('VAL_015'):
    # Handle Phase 1.1 compatible error
    pass

if is_phase_12_specific('BIZ_105'):
    # Handle Phase 1.2 specific error
    pass
```

## Performance Considerations

### Optimization Strategies
1. **Efficient Lookups**: Uses dictionary indexing for campaign names and IDs
2. **Batch Processing**: Validates multiple records in single operations
3. **Early Termination**: Stops validation on critical errors when appropriate
4. **Memory Management**: Processes records in batches to manage memory usage

### Database Optimization
1. **Index Usage**: Leverages existing indexes on processing_batch_id
2. **Query Optimization**: Minimizes database queries by batch operations
3. **Transaction Management**: Uses proper transaction isolation

## Testing

### Unit Tests
- **Coverage**: 24 comprehensive test cases
- **Scenarios**: Combined upload, relationship validation, hierarchical parsing
- **Error Handling**: All error codes and edge cases covered

### Integration Tests
- **Database Integration**: Real staging database operations
- **Phase 1.1 Integration**: Batch management and error code compatibility
- **End-to-End Workflows**: Complete validation scenarios

### Test Commands
```bash
# Run unit tests
python -m pytest tests/unit/test_cross_file_validator.py -v

# Run integration tests (requires test database)
python -m pytest tests/integration/test_cross_file_integration.py -v

# Run all cross-file validator tests
python -m pytest tests/ -k cross_file -v
```

## Configuration

### Environment Variables
- **DB_HOST**: Database host (default: localhost)
- **DB_PORT**: Database port (default: 5432)
- **DB_NAME**: Database name (default: ppv_fulfillment_dev)
- **DB_USER**: Database user (optional for local development)
- **DB_PASSWORD**: Database password (optional for local development)

### Initialization
```python
# Default initialization (uses environment configuration)
validator = CrossFileValidator()

# Custom database URL
validator = CrossFileValidator(staging_db_url="postgresql://user:pass@host:port/db")
```

## Troubleshooting

### Common Issues

1. **Database Connection Errors**
   ```python
   # Error: Failed to initialize CrossFileValidator
   # Solution: Check database configuration and connectivity
   ```

2. **Missing Batch Records**
   ```python
   # Error: BIZ_105 - Combined upload incomplete
   # Solution: Ensure both Campaign and Performance files are uploaded
   ```

3. **Case Sensitivity Issues**
   ```python
   # Error: BIZ_101 - Deal name case mismatch
   # Solution: Ensure exact case matching between file names
   ```

4. **Hierarchical Structure Errors**
   ```python
   # Error: VAL_015 - Invalid hierarchical structure
   # Solution: Use proper " > " separators without empty segments
   ```

### Debug Information
```python
# Enable debug logging
import logging
logging.getLogger('src.services.cross_file_validator').setLevel(logging.DEBUG)

# Check validation result details
result = validator.validate_cross_file_relationships(campaigns, performance)
print(f"Validation result: {result.is_valid}")
print(f"Error count: {len(result.errors)}")
print(f"Context: {result.context}")

for error in result.errors:
    print(f"Error: {error.error_code} - {error.message}")
    print(f"Source row: {error.source_row_number}")
    print(f"Context: {error.context}")
```

## Best Practices

### Development Guidelines
1. **Always Test First**: Follow TDD principles - write tests before implementation
2. **Error Context**: Provide comprehensive error context for debugging
3. **Database Cleanup**: Always cleanup test data in integration tests
4. **Transaction Safety**: Use proper transaction management for database operations

### Production Guidelines
1. **Monitoring**: Implement proper logging and monitoring
2. **Error Handling**: Handle database connection failures gracefully
3. **Performance**: Monitor validation performance for large batches
4. **Documentation**: Keep error messages user-friendly and actionable

## Future Enhancements

### Planned Features
1. **Configurable Validation Rules**: Allow customization of validation logic
2. **Batch Size Optimization**: Dynamic batch sizing based on system resources  
3. **Async Processing**: Support for asynchronous validation workflows
4. **Enhanced Reporting**: Detailed validation reports and statistics

### Extension Points
1. **Custom Validators**: Plugin architecture for custom validation rules
2. **Multiple File Types**: Support for additional file formats
3. **Real-time Validation**: Streaming validation for large datasets
4. **Integration APIs**: REST API endpoints for external system integration