import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ErrorDisplayPanel } from '../ErrorDisplayPanel';
import {
  ProcessingError,
  ErrorCategory,
  ErrorSeverity,
  FileType,
  createProcessingError
} from '../../types/processing';

// Extended ProcessingError interface for full specification compliance
interface ExtendedProcessingError extends ProcessingError {
  technical_details?: string;
  suggested_actions?: string[];
}

// ProcessingErrorResponse interface from specification
interface ProcessingErrorResponse {
  batch_id: string;
  timestamp: string;
  errors: ExtendedProcessingError[];
}

// Mock data for testing - Time-ordered errors (oldest first)
const createMockError = (
  category: ErrorCategory,
  severity: ErrorSeverity,
  code: string,
  message: string,
  timestamp: string,
  context: { file_type: FileType; [key: string]: any },
  technicalDetails?: string,
  suggestedActions?: string[]
): ExtendedProcessingError => ({
  error_id: `error-${timestamp}-${Math.random().toString(36).substring(2, 8)}`,
  timestamp,
  category,
  severity,
  code,
  message,
  context,
  technical_details: technicalDetails,
  suggested_actions: suggestedActions
});

const mockErrorsTimeOrdered: ExtendedProcessingError[] = [
  // Oldest error first
  createMockError(
    ErrorCategory.VALIDATION,
    ErrorSeverity.ERROR,
    'INVALID_UUID',
    'Invalid Deal UUID format in row 1,234',
    '2025-09-09T10:30:15Z',
    {
      file_type: FileType.CAMPAIGN_XLSX,
      row_number: 1234,
      column_name: 'Deal/Campaign ID',
      invalid_value: 'abc123'
    },
    "UUID 'abc123' does not match pattern ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    [
      'Verify Deal UUID format in source system',
      'Check row 1,234 in uploaded file'
    ]
  ),
  createMockError(
    ErrorCategory.PARSING,
    ErrorSeverity.ERROR,
    'MALFORMED_HEADER',
    'Required column "Campaign Name" not found',
    '2025-09-09T10:31:22Z',
    {
      file_type: FileType.CAMPAIGN_XLSX,
      expected_columns: ['Campaign Name', 'Deal/Campaign ID', 'Start Date'],
      found_columns: ['Campaign_Name', 'Deal ID', 'Start Date']
    },
    'Excel header parsing failed at column index 0',
    ['Verify column names match template exactly', 'Check for extra spaces or special characters']
  ),
  createMockError(
    ErrorCategory.PROCESSING,
    ErrorSeverity.WARNING,
    'DUPLICATE_CAMPAIGNS',
    'Found 3 duplicate campaign entries',
    '2025-09-09T10:32:45Z',
    {
      file_type: FileType.CAMPAIGN_XLSX,
      duplicates: [
        { row: 156, campaign_id: 'CAMP_001' },
        { row: 278, campaign_id: 'CAMP_001' },
        { row: 399, campaign_id: 'CAMP_001' }
      ]
    },
    'Duplicate detection algorithm found matching campaign_id values',
    ['Review duplicate campaigns manually', 'Remove or update conflicting entries']
  ),
  createMockError(
    ErrorCategory.SYSTEM,
    ErrorSeverity.ERROR,
    'DATABASE_CONNECTION',
    'Unable to connect to classification database',
    '2025-09-09T10:33:12Z',
    {
      file_type: FileType.REPORTING_CSV,
      database_host: 'classification-db.internal',
      connection_timeout: 30
    },
    'Connection timeout after 30 seconds to host classification-db.internal:5432',
    ['Check database connectivity', 'Retry processing after database recovery']
  ),
  // Most recent error
  createMockError(
    ErrorCategory.VALIDATION,
    ErrorSeverity.INFO,
    'DATE_FORMAT_NORMALIZED',
    'Date formats normalized from MM/DD/YYYY to ISO 8601',
    '2025-09-09T10:34:01Z',
    {
      file_type: FileType.CAMPAIGN_XLSX,
      normalized_count: 1567,
      columns_affected: ['Start Date', 'End Date']
    },
    'Automatic date format conversion applied using parseDate() utility',
    ['No action required - dates automatically normalized']
  )
];

const mockGroupedErrors: ExtendedProcessingError[] = [
  // Multiple similar UUID validation errors for grouping
  createMockError(
    ErrorCategory.VALIDATION,
    ErrorSeverity.ERROR,
    'INVALID_UUID',
    'Invalid Deal UUID format in row 45',
    '2025-09-09T10:30:15Z',
    { file_type: FileType.CAMPAIGN_XLSX, row_number: 45, column_name: 'Deal/Campaign ID', invalid_value: 'xyz789' }
  ),
  createMockError(
    ErrorCategory.VALIDATION,
    ErrorSeverity.ERROR,
    'INVALID_UUID',
    'Invalid Deal UUID format in row 67',
    '2025-09-09T10:30:16Z',
    { file_type: FileType.CAMPAIGN_XLSX, row_number: 67, column_name: 'Deal/Campaign ID', invalid_value: 'bad-uuid' }
  ),
  createMockError(
    ErrorCategory.VALIDATION,
    ErrorSeverity.ERROR,
    'INVALID_UUID',
    'Invalid Deal UUID format in row 123',
    '2025-09-09T10:30:17Z',
    { file_type: FileType.CAMPAIGN_XLSX, row_number: 123, column_name: 'Deal/Campaign ID', invalid_value: '12345' }
  ),
  createMockError(
    ErrorCategory.VALIDATION,
    ErrorSeverity.ERROR,
    'INVALID_UUID',
    'Invalid Deal UUID format in row 189',
    '2025-09-09T10:30:18Z',
    { file_type: FileType.CAMPAIGN_XLSX, row_number: 189, column_name: 'Deal/Campaign ID', invalid_value: 'not-uuid' }
  ),
  createMockError(
    ErrorCategory.VALIDATION,
    ErrorSeverity.ERROR,
    'INVALID_UUID',
    'Invalid Deal UUID format in row 234',
    '2025-09-09T10:30:19Z',
    { file_type: FileType.CAMPAIGN_XLSX, row_number: 234, column_name: 'Deal/Campaign ID', invalid_value: 'invalid' }
  )
];

const mockProcessingErrorResponse: ProcessingErrorResponse = {
  batch_id: 'batch-test-123',
  timestamp: '2025-09-09T10:30:00Z',
  errors: mockErrorsTimeOrdered
};

// Mock console.error to catch rendering issues
const originalError = console.error;
let consoleErrors: string[] = [];

// Error Boundary component to catch rendering errors
class TestErrorBoundary extends React.Component<
  { children: React.ReactNode; onError?: (error: Error) => void },
  { hasError: boolean; error?: Error }
> {
  constructor(props: any) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: any) {
    if (this.props.onError) {
      this.props.onError(error);
    }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div data-testid="error-boundary">
          <h2>ErrorDisplayPanel Rendering Error</h2>
          <pre>{this.state.error?.message}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

describe('ErrorDisplayPanel Component', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    consoleErrors = [];
    console.error = (...args: any[]) => {
      consoleErrors.push(args.join(' '));
      originalError(...args);
    };
  });

  afterEach(() => {
    console.error = originalError;
  });

  describe('TDD RED Phase - Component Rendering Tests', () => {
    test('ErrorDisplayPanel component renders without crashing', () => {
      const errors: Error[] = [];
      const onError = (error: Error) => errors.push(error);
      
      render(
        <TestErrorBoundary onError={onError}>
          <ErrorDisplayPanel errors={mockErrorsTimeOrdered} />
        </TestErrorBoundary>
      );
      
      // This test should FAIL if component doesn't exist or has rendering errors
      expect(errors).toHaveLength(0);
      expect(consoleErrors.filter(err => err.includes('Error')).length).toBe(0);
      expect(screen.queryByTestId('error-boundary')).not.toBeInTheDocument();
    });

    test('renders component container with proper test id', () => {
      render(<ErrorDisplayPanel errors={mockErrorsTimeOrdered} />);
      
      // Should fail if container doesn't have proper test id
      expect(screen.getByTestId('error-display-panel')).toBeInTheDocument();
    });

    test('component imports load successfully', () => {
      // This test will fail if there are import/module loading issues
      expect(() => {
        require('../ErrorDisplayPanel');
      }).not.toThrow();
    });

    test('component mounts and unmounts cleanly', () => {
      const { unmount } = render(<ErrorDisplayPanel errors={mockErrorsTimeOrdered} />);
      
      // Should fail if component doesn't mount properly
      expect(screen.getByTestId('error-display-panel')).toBeInTheDocument();
      
      // Should fail if component doesn't unmount cleanly
      expect(() => unmount()).not.toThrow();
    });
  });

  describe('Error Display Structure Tests', () => {
    test('displays errors in time-ordered list (oldest first)', () => {
      render(<ErrorDisplayPanel errors={mockErrorsTimeOrdered} />);
      
      // Should fail if errors are not displayed in chronological order
      const errorItems = screen.getAllByTestId(/^error-item-/);
      expect(errorItems).toHaveLength(5);
      
      // First error should be the oldest (10:30:15Z)
      expect(screen.getByTestId('error-item-0')).toHaveTextContent('Invalid Deal UUID format in row 1,234');
      expect(screen.getByTestId('error-timestamp-0')).toHaveTextContent('10:30:15 AM');
      
      // Last error should be the newest (10:34:01Z)
      expect(screen.getByTestId('error-item-4')).toHaveTextContent('Date formats normalized from MM/DD/YYYY to ISO 8601');
      expect(screen.getByTestId('error-timestamp-4')).toHaveTextContent('10:34:01 AM');
    });

    test('displays single error correctly', () => {
      const singleError = [mockErrorsTimeOrdered[0]];
      render(<ErrorDisplayPanel errors={singleError} />);
      
      // Should fail if single error display is incorrect
      expect(screen.getByTestId('error-display-panel')).toBeInTheDocument();
      expect(screen.getByTestId('error-item-0')).toBeInTheDocument();
      expect(screen.getByText('Invalid Deal UUID format in row 1,234')).toBeInTheDocument();
      expect(screen.queryByTestId('error-item-1')).not.toBeInTheDocument();
    });

    test('displays empty state when no errors', () => {
      render(<ErrorDisplayPanel errors={[]} />);
      
      // Should fail if empty state is not displayed
      expect(screen.getByTestId('no-errors-message')).toBeInTheDocument();
      expect(screen.getByText('No processing errors found')).toBeInTheDocument();
      expect(screen.getByTestId('no-errors-icon')).toBeInTheDocument();
    });

    test('has expandable error details functionality', () => {
      render(<ErrorDisplayPanel errors={mockErrorsTimeOrdered} />);
      
      // Should fail if expand/collapse functionality is missing
      const expandButton = screen.getByTestId('expand-error-0');
      expect(expandButton).toBeInTheDocument();
      expect(expandButton).toHaveAttribute('aria-expanded', 'false');
      
      // Initially, technical details should be hidden
      expect(screen.queryByTestId('technical-details-0')).not.toBeInTheDocument();
      
      // Click to expand
      fireEvent.click(expandButton);
      
      // Should fail if expansion doesn't work
      expect(expandButton).toHaveAttribute('aria-expanded', 'true');
      expect(screen.getByTestId('technical-details-0')).toBeInTheDocument();
    });

    test('supports error grouping for similar issues', () => {
      render(<ErrorDisplayPanel errors={mockGroupedErrors} />);
      
      // Should fail if error grouping is not implemented
      expect(screen.getByTestId('error-group-INVALID_UUID')).toBeInTheDocument();
      expect(screen.getByText('Invalid UUID Format (5 errors)')).toBeInTheDocument();
      expect(screen.getByTestId('group-expand-INVALID_UUID')).toBeInTheDocument();
      
      // Initially grouped errors should be collapsed
      expect(screen.queryByTestId('grouped-error-0')).not.toBeInTheDocument();
    });
  });

  describe('Error Content Tests', () => {
    test('displays structured error response format', () => {
      render(<ErrorDisplayPanel errorResponse={mockProcessingErrorResponse} />);
      
      // Should fail if structured response format is not supported
      expect(screen.getByTestId('batch-id')).toHaveTextContent('batch-test-123');
      expect(screen.getByTestId('response-timestamp')).toHaveTextContent('10:30:00 AM');
      expect(screen.getAllByTestId(/^error-item-/)).toHaveLength(5);
    });

    test('displays error categories with appropriate icons', () => {
      render(<ErrorDisplayPanel errors={mockErrorsTimeOrdered} />);
      
      // Should fail if category icons and labels are missing
      expect(screen.getByTestId('category-validation-0')).toBeInTheDocument();
      expect(screen.getByTestId('category-icon-validation-0')).toBeInTheDocument();
      
      expect(screen.getByTestId('category-parsing-1')).toBeInTheDocument();
      expect(screen.getByTestId('category-icon-parsing-1')).toBeInTheDocument();
      
      expect(screen.getByTestId('category-processing-2')).toBeInTheDocument();
      expect(screen.getByTestId('category-icon-processing-2')).toBeInTheDocument();
      
      expect(screen.getByTestId('category-system-3')).toBeInTheDocument();
      expect(screen.getByTestId('category-icon-system-3')).toBeInTheDocument();
    });

    test('displays error severity levels with appropriate styling', () => {
      render(<ErrorDisplayPanel errors={mockErrorsTimeOrdered} />);
      
      // Should fail if severity styling is missing
      expect(screen.getByTestId('severity-error-0')).toHaveClass('severity-error');
      expect(screen.getByTestId('severity-error-1')).toHaveClass('severity-error');
      expect(screen.getByTestId('severity-warning-2')).toHaveClass('severity-warning');
      expect(screen.getByTestId('severity-error-3')).toHaveClass('severity-error');
      expect(screen.getByTestId('severity-info-4')).toHaveClass('severity-info');
    });

    test('displays contextual information for each error', () => {
      render(<ErrorDisplayPanel errors={mockErrorsTimeOrdered} />);
      
      // Should fail if contextual information is missing
      const firstError = screen.getByTestId('error-context-0');
      expect(firstError).toHaveTextContent('Campaign XLSX');
      expect(firstError).toHaveTextContent('Row: 1,234');
      expect(firstError).toHaveTextContent('Column: Deal/Campaign ID');
      expect(firstError).toHaveTextContent('Value: abc123');
    });

    test('displays technical details in expandable sections', () => {
      render(<ErrorDisplayPanel errors={mockErrorsTimeOrdered} />);
      
      // Expand first error to see technical details
      fireEvent.click(screen.getByTestId('expand-error-0'));
      
      // Should fail if technical details are not shown
      const technicalDetails = screen.getByTestId('technical-details-0');
      expect(technicalDetails).toBeInTheDocument();
      expect(technicalDetails).toHaveTextContent(
        "UUID 'abc123' does not match pattern ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
      );
    });
  });

  describe('Time-Ordered Display Tests', () => {
    test('maintains chronological sorting when new errors are added', () => {
      const initialErrors = [mockErrorsTimeOrdered[0], mockErrorsTimeOrdered[2]]; // Non-consecutive errors
      const { rerender } = render(<ErrorDisplayPanel errors={initialErrors} />);
      
      // Add a new error that should be inserted in the middle chronologically
      const newError = createMockError(
        ErrorCategory.VALIDATION,
        ErrorSeverity.ERROR,
        'NEW_ERROR',
        'New error between existing ones',
        '2025-09-09T10:31:00Z', // Between first (10:30:15Z) and third (10:32:45Z)
        { file_type: FileType.CAMPAIGN_XLSX }
      );
      
      const updatedErrors = [...initialErrors, newError];
      rerender(<ErrorDisplayPanel errors={updatedErrors} />);
      
      // Should fail if chronological order is not maintained
      const errorItems = screen.getAllByTestId(/^error-item-/);
      expect(errorItems[0]).toHaveTextContent('Invalid Deal UUID format in row 1,234'); // 10:30:15Z
      expect(errorItems[1]).toHaveTextContent('New error between existing ones'); // 10:31:00Z
      expect(errorItems[2]).toHaveTextContent('Found 3 duplicate campaign entries'); // 10:32:45Z
    });

    test('displays timestamp formatting correctly', () => {
      render(<ErrorDisplayPanel errors={mockErrorsTimeOrdered} />);
      
      // Should fail if timestamp formatting is incorrect
      expect(screen.getByTestId('error-timestamp-0')).toHaveTextContent('10:30:15 AM');
      expect(screen.getByTestId('error-timestamp-1')).toHaveTextContent('10:31:22 AM');
      expect(screen.getByTestId('error-timestamp-2')).toHaveTextContent('10:32:45 AM');
      expect(screen.getByTestId('error-timestamp-3')).toHaveTextContent('10:33:12 AM');
      expect(screen.getByTestId('error-timestamp-4')).toHaveTextContent('10:34:01 AM');
    });

    test('handles timezone display correctly', () => {
      render(<ErrorDisplayPanel errors={mockErrorsTimeOrdered} showTimezone={true} />);
      
      // Should fail if timezone information is not displayed
      expect(screen.getByTestId('error-timestamp-0')).toHaveTextContent('10:30:15 AM UTC');
      expect(screen.getByTestId('timezone-indicator')).toHaveTextContent('All times shown in UTC');
    });

    test('validates error list is sorted by timestamp', () => {
      const unsortedErrors = [mockErrorsTimeOrdered[2], mockErrorsTimeOrdered[0], mockErrorsTimeOrdered[1]];
      
      const errors: Error[] = [];
      const onError = (error: Error) => errors.push(error);
      
      render(
        <TestErrorBoundary onError={onError}>
          <ErrorDisplayPanel errors={unsortedErrors} />
        </TestErrorBoundary>
      );
      
      // Should fail if unsorted errors are not detected and handled
      expect(errors).toHaveLength(1);
      expect(errors[0].message).toContain('Errors must be sorted by timestamp');
    });
  });

  describe('Error Categorization Tests', () => {
    test('displays validation errors with file context', () => {
      const validationError = [mockErrorsTimeOrdered[0]]; // VALIDATION error
      render(<ErrorDisplayPanel errors={validationError} />);
      
      // Should fail if validation error context is missing
      expect(screen.getByTestId('category-validation-0')).toBeInTheDocument();
      expect(screen.getByTestId('validation-context-0')).toHaveTextContent('File validation failed');
      expect(screen.getByTestId('file-context-0')).toHaveTextContent('Campaign XLSX, Row 1,234');
    });

    test('displays parsing errors with structure information', () => {
      const parsingError = [mockErrorsTimeOrdered[1]]; // PARSING error
      render(<ErrorDisplayPanel errors={parsingError} />);
      
      // Should fail if parsing error structure info is missing
      expect(screen.getByTestId('category-parsing-0')).toBeInTheDocument();
      expect(screen.getByTestId('parsing-context-0')).toHaveTextContent('File structure parsing failed');
      expect(screen.getByTestId('structure-info-0')).toHaveTextContent('Expected: Campaign Name, Deal/Campaign ID, Start Date');
    });

    test('displays processing errors with stage information', () => {
      const processingError = [mockErrorsTimeOrdered[2]]; // PROCESSING error
      render(<ErrorDisplayPanel errors={processingError} />);
      
      // Should fail if processing stage info is missing
      expect(screen.getByTestId('category-processing-0')).toBeInTheDocument();
      expect(screen.getByTestId('processing-stage-0')).toHaveTextContent('Data processing stage');
      expect(screen.getByTestId('stage-info-0')).toHaveTextContent('Classification stage');
    });

    test('displays system errors with technical details', () => {
      const systemError = [mockErrorsTimeOrdered[3]]; // SYSTEM error
      render(<ErrorDisplayPanel errors={systemError} />);
      
      // Should fail if system error technical details are missing
      expect(screen.getByTestId('category-system-0')).toBeInTheDocument();
      expect(screen.getByTestId('system-context-0')).toHaveTextContent('System infrastructure error');
      expect(screen.getByTestId('technical-context-0')).toHaveTextContent('Database: classification-db.internal');
    });

    test('applies category-specific styling and icons', () => {
      render(<ErrorDisplayPanel errors={mockErrorsTimeOrdered} />);
      
      // Should fail if category-specific styling is missing
      expect(screen.getByTestId('category-validation-0')).toHaveClass('category-validation');
      expect(screen.getByTestId('category-parsing-1')).toHaveClass('category-parsing');
      expect(screen.getByTestId('category-processing-2')).toHaveClass('category-processing');
      expect(screen.getByTestId('category-system-3')).toHaveClass('category-system');
      
      // Check for category-specific icons
      expect(screen.getByTestId('category-icon-validation-0')).toHaveClass('icon-validation');
      expect(screen.getByTestId('category-icon-parsing-1')).toHaveClass('icon-parsing');
      expect(screen.getByTestId('category-icon-processing-2')).toHaveClass('icon-processing');
      expect(screen.getByTestId('category-icon-system-3')).toHaveClass('icon-system');
    });
  });

  describe('Actionable Error Messages Tests', () => {
    test('displays user-friendly error messages', () => {
      render(<ErrorDisplayPanel errors={mockErrorsTimeOrdered} />);
      
      // Should fail if user-friendly messages are not displayed
      expect(screen.getByText('Invalid Deal UUID format in row 1,234')).toBeInTheDocument();
      expect(screen.getByText('Required column "Campaign Name" not found')).toBeInTheDocument();
      expect(screen.getByText('Found 3 duplicate campaign entries')).toBeInTheDocument();
      expect(screen.getByText('Unable to connect to classification database')).toBeInTheDocument();
    });

    test('displays suggested actions for each error', () => {
      render(<ErrorDisplayPanel errors={mockErrorsTimeOrdered} />);
      
      // Expand first error to see suggested actions
      fireEvent.click(screen.getByTestId('expand-error-0'));
      
      // Should fail if suggested actions are not displayed
      const suggestedActions = screen.getByTestId('suggested-actions-0');
      expect(suggestedActions).toBeInTheDocument();
      expect(suggestedActions).toHaveTextContent('Verify Deal UUID format in source system');
      expect(suggestedActions).toHaveTextContent('Check row 1,234 in uploaded file');
    });

    test('displays action buttons for error resolution', () => {
      render(<ErrorDisplayPanel errors={mockErrorsTimeOrdered} />);
      
      // Expand first error to see action buttons
      fireEvent.click(screen.getByTestId('expand-error-0'));
      
      // Should fail if action buttons are missing
      expect(screen.getByTestId('action-copy-details-0')).toBeInTheDocument();
      expect(screen.getByTestId('action-mark-resolved-0')).toBeInTheDocument();
      expect(screen.getByTestId('action-view-context-0')).toBeInTheDocument();
    });

    test('provides context-specific guidance', () => {
      render(<ErrorDisplayPanel errors={mockErrorsTimeOrdered} />);
      
      // Should fail if context-specific guidance is missing
      fireEvent.click(screen.getByTestId('expand-error-1'));
      const guidance = screen.getByTestId('context-guidance-1');
      expect(guidance).toHaveTextContent('Column header mismatch detected');
      expect(guidance).toHaveTextContent('Ensure Excel column names match the required template exactly');
    });

    test('handles action button interactions', () => {
      const mockOnActionClick = jest.fn();
      render(<ErrorDisplayPanel errors={mockErrorsTimeOrdered} onActionClick={mockOnActionClick} />);
      
      fireEvent.click(screen.getByTestId('expand-error-0'));
      
      // Should fail if action button clicks are not handled
      fireEvent.click(screen.getByTestId('action-copy-details-0'));
      expect(mockOnActionClick).toHaveBeenCalledWith('copy-details', mockErrorsTimeOrdered[0]);
      
      fireEvent.click(screen.getByTestId('action-mark-resolved-0'));
      expect(mockOnActionClick).toHaveBeenCalledWith('mark-resolved', mockErrorsTimeOrdered[0]);
    });
  });

  describe('Error Grouping and Counts Tests', () => {
    test('detects and groups similar errors', () => {
      render(<ErrorDisplayPanel errors={mockGroupedErrors} />);
      
      // Should fail if error grouping is not working
      expect(screen.getByTestId('error-group-INVALID_UUID')).toBeInTheDocument();
      expect(screen.getByText('Invalid UUID Format (5 errors)')).toBeInTheDocument();
      expect(screen.queryByTestId('error-item-0')).not.toBeInTheDocument(); // Individual errors should be hidden when grouped
    });

    test('displays error count for grouped errors', () => {
      render(<ErrorDisplayPanel errors={mockGroupedErrors} />);
      
      // Should fail if error counts are not displayed
      const groupHeader = screen.getByTestId('group-header-INVALID_UUID');
      expect(groupHeader).toHaveTextContent('5 errors');
      expect(screen.getByTestId('group-count-INVALID_UUID')).toHaveTextContent('5');
    });

    test('allows expansion of grouped errors', () => {
      render(<ErrorDisplayPanel errors={mockGroupedErrors} />);
      
      // Initially, grouped errors should be collapsed
      expect(screen.queryByTestId('grouped-error-0')).not.toBeInTheDocument();
      
      // Expand group
      fireEvent.click(screen.getByTestId('group-expand-INVALID_UUID'));
      
      // Should fail if grouped error expansion doesn't work
      expect(screen.getByTestId('grouped-error-0')).toBeInTheDocument();
      expect(screen.getByTestId('grouped-error-1')).toBeInTheDocument();
      expect(screen.getByTestId('grouped-error-2')).toBeInTheDocument();
      expect(screen.getByTestId('grouped-error-3')).toBeInTheDocument();
      expect(screen.getByTestId('grouped-error-4')).toBeInTheDocument();
    });

    test('displays group summary information', () => {
      render(<ErrorDisplayPanel errors={mockGroupedErrors} />);
      
      // Should fail if group summary is missing
      const groupSummary = screen.getByTestId('group-summary-INVALID_UUID');
      expect(groupSummary).toHaveTextContent('UUID validation failed in 5 locations');
      expect(groupSummary).toHaveTextContent('Rows: 45, 67, 123, 189, 234');
      expect(groupSummary).toHaveTextContent('Column: Deal/Campaign ID');
    });

    test('switches between individual and grouped error display', () => {
      const { rerender } = render(<ErrorDisplayPanel errors={mockGroupedErrors} />);
      
      // Initially grouped
      expect(screen.getByTestId('error-group-INVALID_UUID')).toBeInTheDocument();
      
      // Switch to individual display
      rerender(<ErrorDisplayPanel errors={mockGroupedErrors} groupSimilarErrors={false} />);
      
      // Should fail if switching to individual display doesn't work
      expect(screen.queryByTestId('error-group-INVALID_UUID')).not.toBeInTheDocument();
      expect(screen.getByTestId('error-item-0')).toBeInTheDocument();
      expect(screen.getByTestId('error-item-4')).toBeInTheDocument();
    });
  });

  describe('Interactive Features Tests', () => {
    test('supports error details expansion and collapse', () => {
      render(<ErrorDisplayPanel errors={mockErrorsTimeOrdered} />);
      
      const expandButton = screen.getByTestId('expand-error-0');
      
      // Initially collapsed
      expect(expandButton).toHaveAttribute('aria-expanded', 'false');
      expect(screen.queryByTestId('technical-details-0')).not.toBeInTheDocument();
      
      // Expand
      fireEvent.click(expandButton);
      expect(expandButton).toHaveAttribute('aria-expanded', 'true');
      expect(screen.getByTestId('technical-details-0')).toBeInTheDocument();
      
      // Collapse
      fireEvent.click(expandButton);
      expect(expandButton).toHaveAttribute('aria-expanded', 'false');
      expect(screen.queryByTestId('technical-details-0')).not.toBeInTheDocument();
    });

    test('implements "Show technical details" functionality', () => {
      render(<ErrorDisplayPanel errors={mockErrorsTimeOrdered} />);
      
      fireEvent.click(screen.getByTestId('expand-error-0'));
      
      // Should fail if technical details toggle is missing
      const technicalToggle = screen.getByTestId('technical-details-toggle-0');
      expect(technicalToggle).toBeInTheDocument();
      
      fireEvent.click(technicalToggle);
      expect(screen.getByTestId('raw-technical-details-0')).toBeInTheDocument();
    });

    test('implements "Copy error details" functionality', () => {
      // Mock clipboard API
      const mockWriteText = jest.fn();
      Object.assign(navigator, {
        clipboard: {
          writeText: mockWriteText,
        },
      });
      
      render(<ErrorDisplayPanel errors={mockErrorsTimeOrdered} />);
      
      fireEvent.click(screen.getByTestId('expand-error-0'));
      fireEvent.click(screen.getByTestId('action-copy-details-0'));
      
      // Should fail if copy functionality doesn't work
      expect(mockWriteText).toHaveBeenCalledWith(
        expect.stringContaining('Invalid Deal UUID format in row 1,234')
      );
      expect(screen.getByTestId('copy-success-message-0')).toBeInTheDocument();
    });

    test('supports error filtering by category', () => {
      render(<ErrorDisplayPanel errors={mockErrorsTimeOrdered} />);
      
      // Should fail if category filter is missing
      const categoryFilter = screen.getByTestId('error-category-filter');
      expect(categoryFilter).toBeInTheDocument();
      
      // Filter by validation errors only
      fireEvent.change(categoryFilter, { target: { value: 'validation' } });
      
      // Should show only validation errors
      expect(screen.getByTestId('error-item-0')).toBeInTheDocument(); // Validation error
      expect(screen.queryByTestId('error-item-1')).not.toBeInTheDocument(); // Parsing error - should be hidden
      expect(screen.getByTestId('error-item-4')).toBeInTheDocument(); // Info validation error
    });

    test('supports error filtering by severity', () => {
      render(<ErrorDisplayPanel errors={mockErrorsTimeOrdered} />);
      
      // Should fail if severity filter is missing
      const severityFilter = screen.getByTestId('error-severity-filter');
      expect(severityFilter).toBeInTheDocument();
      
      // Filter by error severity only
      fireEvent.change(severityFilter, { target: { value: 'error' } });
      
      // Should show only error severity items
      expect(screen.getByTestId('error-item-0')).toBeInTheDocument(); // Error
      expect(screen.getByTestId('error-item-1')).toBeInTheDocument(); // Error
      expect(screen.queryByTestId('error-item-2')).not.toBeInTheDocument(); // Warning - should be hidden
      expect(screen.getByTestId('error-item-3')).toBeInTheDocument(); // Error
      expect(screen.queryByTestId('error-item-4')).not.toBeInTheDocument(); // Info - should be hidden
    });

    test('implements error search functionality', () => {
      render(<ErrorDisplayPanel errors={mockErrorsTimeOrdered} />);
      
      // Should fail if search functionality is missing
      const searchInput = screen.getByTestId('error-search-input');
      expect(searchInput).toBeInTheDocument();
      
      // Search for "UUID"
      fireEvent.change(searchInput, { target: { value: 'UUID' } });
      
      // Should show only errors containing "UUID"
      expect(screen.getByTestId('error-item-0')).toBeInTheDocument(); // Contains "UUID"
      expect(screen.queryByTestId('error-item-1')).not.toBeInTheDocument(); // Doesn't contain "UUID"
      expect(screen.queryByTestId('error-item-2')).not.toBeInTheDocument(); // Doesn't contain "UUID"
      expect(screen.queryByTestId('error-item-3')).not.toBeInTheDocument(); // Doesn't contain "UUID"
      expect(screen.queryByTestId('error-item-4')).not.toBeInTheDocument(); // Doesn't contain "UUID"
    });
  });

  describe('Accessibility Tests', () => {
    test('has proper ARIA labels for screen readers', () => {
      render(<ErrorDisplayPanel errors={mockErrorsTimeOrdered} />);
      
      // Should fail if ARIA labels are missing
      const container = screen.getByTestId('error-display-panel');
      expect(container).toHaveAttribute('role', 'region');
      expect(container).toHaveAttribute('aria-label', 'Processing errors');
      
      // Error list should have proper ARIA structure
      const errorList = screen.getByTestId('error-list');
      expect(errorList).toHaveAttribute('role', 'list');
      expect(errorList).toHaveAttribute('aria-label', 'Processing error details');
    });

    test('supports keyboard navigation for expansion', () => {
      render(<ErrorDisplayPanel errors={mockErrorsTimeOrdered} />);
      
      const expandButton = screen.getByTestId('expand-error-0');
      
      // Should fail if keyboard navigation is not supported
      expect(expandButton).toHaveAttribute('tabindex', '0');
      expect(expandButton).toHaveAttribute('role', 'button');
      
      // Test keyboard activation
      expandButton.focus();
      fireEvent.keyDown(expandButton, { key: 'Enter' });
      
      expect(expandButton).toHaveAttribute('aria-expanded', 'true');
      expect(screen.getByTestId('technical-details-0')).toBeInTheDocument();
    });

    test('announces error updates to screen readers', () => {
      const { rerender } = render(<ErrorDisplayPanel errors={[mockErrorsTimeOrdered[0]]} />);
      
      // Should fail if aria-live region is missing
      expect(screen.getByTestId('error-announcer')).toHaveAttribute('aria-live', 'polite');
      expect(screen.getByTestId('error-announcer')).toHaveAttribute('aria-atomic', 'false');
      
      // Add new error
      rerender(<ErrorDisplayPanel errors={mockErrorsTimeOrdered} />);
      
      // Should announce the update
      expect(screen.getByTestId('error-announcer')).toHaveTextContent('4 new processing errors added');
    });

    test('maintains focus during error updates', () => {
      const { rerender } = render(<ErrorDisplayPanel errors={mockErrorsTimeOrdered} />);
      
      const expandButton = screen.getByTestId('expand-error-0');
      expandButton.focus();
      fireEvent.click(expandButton); // Expand error
      
      // Update errors (add new error)
      const newError = createMockError(
        ErrorCategory.VALIDATION,
        ErrorSeverity.ERROR,
        'NEW_ERROR',
        'New error added',
        '2025-09-09T10:35:00Z',
        { file_type: FileType.CAMPAIGN_XLSX }
      );
      
      rerender(<ErrorDisplayPanel errors={[...mockErrorsTimeOrdered, newError]} />);
      
      // Should fail if focus is not maintained
      expect(expandButton).toHaveFocus();
      expect(expandButton).toHaveAttribute('aria-expanded', 'true');
    });

    test('has semantic HTML structure for error hierarchy', () => {
      render(<ErrorDisplayPanel errors={mockErrorsTimeOrdered} />);
      
      // Should fail if semantic structure is incorrect
      expect(screen.getByRole('heading', { level: 2, name: /processing errors/i })).toBeInTheDocument();
      
      // Error list should use proper list semantics
      const errorList = screen.getByTestId('error-list');
      expect(errorList.tagName).toBe('UL');
      
      // Each error should be a list item
      const errorItems = screen.getAllByTestId(/^error-item-/);
      errorItems.forEach(item => {
        expect(item.tagName).toBe('LI');
      });
    });

    test('ensures color contrast compliance for error severity', () => {
      render(<ErrorDisplayPanel errors={mockErrorsTimeOrdered} />);
      
      // Should fail if color contrast is not compliant
      const errorSeverityElement = screen.getByTestId('severity-error-0');
      const computedStyle = window.getComputedStyle(errorSeverityElement);
      
      // Check that error severity has appropriate contrast
      expect(errorSeverityElement).toHaveClass('high-contrast-error');
      
      const warningSeverityElement = screen.getByTestId('severity-warning-2');
      expect(warningSeverityElement).toHaveClass('high-contrast-warning');
    });
  });

  describe('Integration Tests', () => {
    test('integrates correctly with ProcessingError interface', () => {
      const validError = createProcessingError(
        ErrorCategory.VALIDATION,
        ErrorSeverity.ERROR,
        'TEST_001',
        'Test integration error',
        { file_type: FileType.CAMPAIGN_XLSX, row: 1 }
      );
      
      render(<ErrorDisplayPanel errors={[validError]} />);
      
      // Should fail if ProcessingError integration is incorrect
      expect(screen.getByTestId('error-display-panel')).toBeInTheDocument();
      expect(screen.getByText('Test integration error')).toBeInTheDocument();
      expect(screen.getByTestId('category-validation-0')).toBeInTheDocument();
    });

    test('handles ProcessingErrorResponse format', () => {
      render(<ErrorDisplayPanel errorResponse={mockProcessingErrorResponse} />);
      
      // Should fail if response format integration is incorrect
      expect(screen.getByTestId('batch-id')).toHaveTextContent('batch-test-123');
      expect(screen.getAllByTestId(/^error-item-/)).toHaveLength(5);
    });

    test('integrates with different file types correctly', () => {
      const campaignError = createProcessingError(
        ErrorCategory.VALIDATION,
        ErrorSeverity.ERROR,
        'CAMPAIGN_001',
        'Campaign file error',
        { file_type: FileType.CAMPAIGN_XLSX }
      );
      
      const reportingError = createProcessingError(
        ErrorCategory.PARSING,
        ErrorSeverity.ERROR,
        'REPORTING_001',
        'Reporting file error',
        { file_type: FileType.REPORTING_CSV }
      );
      
      render(<ErrorDisplayPanel errors={[campaignError, reportingError]} />);
      
      // Should fail if file type integration is incorrect
      expect(screen.getByTestId('file-type-campaign-xlsx-0')).toBeInTheDocument();
      expect(screen.getByTestId('file-type-reporting-csv-1')).toBeInTheDocument();
    });

    test('validates error context from different processing stages', () => {
      const stageContextErrors = [
        createMockError(
          ErrorCategory.PARSING,
          ErrorSeverity.ERROR,
          'PARSE_001',
          'Parse stage error',
          '2025-09-09T10:30:00Z',
          { file_type: FileType.CAMPAIGN_XLSX, stage: 'parse', header_row: 1 }
        ),
        createMockError(
          ErrorCategory.VALIDATION,
          ErrorSeverity.ERROR,
          'VALIDATE_001',
          'Validation stage error',
          '2025-09-09T10:31:00Z',
          { file_type: FileType.CAMPAIGN_XLSX, stage: 'validate', validated_rows: 1500 }
        )
      ];
      
      render(<ErrorDisplayPanel errors={stageContextErrors} />);
      
      // Should fail if stage context is not displayed correctly
      expect(screen.getByTestId('stage-context-parse-0')).toHaveTextContent('Parse Stage');
      expect(screen.getByTestId('stage-context-validate-1')).toHaveTextContent('Validation Stage');
    });

    test('displays error context during active processing', () => {
      render(
        <ErrorDisplayPanel 
          errors={mockErrorsTimeOrdered} 
          isProcessingActive={true}
          currentStage="validate"
        />
      );
      
      // Should fail if active processing context is missing
      expect(screen.getByTestId('active-processing-indicator')).toBeInTheDocument();
      expect(screen.getByText('Processing continues despite errors')).toBeInTheDocument();
      expect(screen.getByTestId('current-stage-indicator')).toHaveTextContent('Validation Stage');
    });
  });

  describe('Edge Cases and Error Handling', () => {
    test('handles malformed error timestamps', () => {
      const malformedError = {
        ...mockErrorsTimeOrdered[0],
        timestamp: 'invalid-timestamp'
      };
      
      render(<ErrorDisplayPanel errors={[malformedError]} />);
      
      // Should fail if malformed timestamps are not handled gracefully
      expect(screen.getByTestId('timestamp-error-fallback-0')).toBeInTheDocument();
      expect(screen.getByText('Timestamp unavailable')).toBeInTheDocument();
    });

    test('handles missing error context gracefully', () => {
      const errorWithoutContext = {
        ...mockErrorsTimeOrdered[0],
        context: undefined
      } as any;
      
      render(<ErrorDisplayPanel errors={[errorWithoutContext]} />);
      
      // Should fail if missing context is not handled
      expect(screen.getByTestId('context-unavailable-0')).toBeInTheDocument();
      expect(screen.getByText('Context information unavailable')).toBeInTheDocument();
    });

    test('handles empty suggested actions', () => {
      const errorWithoutActions = {
        ...mockErrorsTimeOrdered[0],
        suggested_actions: []
      };
      
      render(<ErrorDisplayPanel errors={[errorWithoutActions]} />);
      
      fireEvent.click(screen.getByTestId('expand-error-0'));
      
      // Should fail if empty actions are not handled
      expect(screen.getByTestId('no-actions-message-0')).toBeInTheDocument();
      expect(screen.getByText('No specific actions recommended')).toBeInTheDocument();
    });

    test('handles rapid error updates without performance issues', () => {
      const { rerender } = render(<ErrorDisplayPanel errors={[mockErrorsTimeOrdered[0]]} />);
      
      // Rapid updates with many errors
      const manyErrors = Array.from({ length: 100 }, (_, i) => 
        createMockError(
          ErrorCategory.VALIDATION,
          ErrorSeverity.ERROR,
          `RAPID_${i}`,
          `Rapid error ${i}`,
          `2025-09-09T10:30:${String(i).padStart(2, '0')}Z`,
          { file_type: FileType.CAMPAIGN_XLSX }
        )
      );
      
      rerender(<ErrorDisplayPanel errors={manyErrors} />);
      
      // Should fail if rapid updates cause performance issues
      expect(consoleErrors.filter(err => err.includes('Warning')).length).toBe(0);
      expect(screen.getByTestId('error-display-panel')).toBeInTheDocument();
      expect(screen.getAllByTestId(/^error-item-/)).toHaveLength(100);
    });

    test('handles null or undefined errors prop', () => {
      const errors: Error[] = [];
      const onError = (error: Error) => errors.push(error);
      
      render(
        <TestErrorBoundary onError={onError}>
          <ErrorDisplayPanel errors={null as any} />
        </TestErrorBoundary>
      );
      
      // Should fail if null errors are not handled
      expect(errors).toHaveLength(1);
      expect(errors[0].message).toContain('Errors prop cannot be null or undefined');
    });

    test('validates error response structure', () => {
      const invalidResponse = {
        batch_id: 'test',
        // Missing timestamp
        errors: mockErrorsTimeOrdered
      } as any;
      
      const errors: Error[] = [];
      const onError = (error: Error) => errors.push(error);
      
      render(
        <TestErrorBoundary onError={onError}>
          <ErrorDisplayPanel errorResponse={invalidResponse} />
        </TestErrorBoundary>
      );
      
      // Should fail if invalid response structure is not validated
      expect(errors).toHaveLength(1);
      expect(errors[0].message).toContain('Invalid error response structure');
    });
  });
});