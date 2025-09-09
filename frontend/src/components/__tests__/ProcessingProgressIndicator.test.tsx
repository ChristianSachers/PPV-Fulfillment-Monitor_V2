import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ProcessingProgressIndicator } from '../ProcessingProgressIndicator';
import {
  ProcessingProgress,
  ProcessingStage,
  ProcessingStatus,
  FileType,
  createProcessingError,
  ErrorCategory,
  ErrorSeverity
} from '../../types/processing';

// Mock data for testing
const createMockProcessingProgress = (
  stage: ProcessingStage,
  status: ProcessingStatus,
  overrides?: Partial<ProcessingProgress>
): ProcessingProgress => ({
  batch_id: 'batch-123',
  stage,
  progress: stage === ProcessingStage.PARSE ? 25 :
           stage === ProcessingStage.VALIDATE ? 50 :
           stage === ProcessingStage.CLASSIFY ? 75 : 100,
  status,
  file_type: FileType.CAMPAIGN_XLSX,
  started_at: '2025-09-09T10:00:00Z',
  updated_at: '2025-09-09T10:30:00Z',
  completed_at: status === ProcessingStatus.COMPLETED ? '2025-09-09T10:35:00Z' : undefined,
  ...overrides
});

const mockProcessingData = {
  parse: createMockProcessingProgress(ProcessingStage.PARSE, ProcessingStatus.PROCESSING),
  validate: createMockProcessingProgress(ProcessingStage.VALIDATE, ProcessingStatus.PROCESSING),
  classify: createMockProcessingProgress(ProcessingStage.CLASSIFY, ProcessingStatus.PROCESSING),
  complete: createMockProcessingProgress(ProcessingStage.COMPLETE, ProcessingStatus.COMPLETED),
  error: createMockProcessingProgress(ProcessingStage.VALIDATE, ProcessingStatus.ERROR),
  cancelled: createMockProcessingProgress(ProcessingStage.CLASSIFY, ProcessingStatus.CANCELLED),
  idle: createMockProcessingProgress(ProcessingStage.PARSE, ProcessingStatus.IDLE)
};

const mockProcessingError = createProcessingError(
  ErrorCategory.VALIDATION,
  ErrorSeverity.ERROR,
  'VALIDATION_001',
  'Invalid file format detected',
  { file_type: FileType.CAMPAIGN_XLSX, row: 5, column: 'campaign_name' }
);

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
          <h2>ProcessingProgressIndicator Rendering Error</h2>
          <pre>{this.state.error?.message}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

describe('ProcessingProgressIndicator Component', () => {
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
    test('ProcessingProgressIndicator component renders without crashing', () => {
      const errors: Error[] = [];
      const onError = (error: Error) => errors.push(error);
      
      render(
        <TestErrorBoundary onError={onError}>
          <ProcessingProgressIndicator processingData={mockProcessingData.parse} />
        </TestErrorBoundary>
      );
      
      // This test should FAIL if component doesn't exist or has rendering errors
      expect(errors).toHaveLength(0);
      expect(consoleErrors.filter(err => err.includes('Error')).length).toBe(0);
      expect(screen.queryByTestId('error-boundary')).not.toBeInTheDocument();
    });

    test('renders Ant Design Progress component correctly', () => {
      render(<ProcessingProgressIndicator processingData={mockProcessingData.parse} />);
      
      // Test for Ant Design Progress component - should fail if Progress doesn't render
      const progressElement = document.querySelector('.ant-progress');
      expect(progressElement).toBeInTheDocument();
      expect(progressElement?.querySelector('.ant-progress-bg')).toBeInTheDocument();
    });

    test('renders component container with proper test id', () => {
      render(<ProcessingProgressIndicator processingData={mockProcessingData.parse} />);
      
      // Should fail if container doesn't have proper test id
      expect(screen.getByTestId('processing-progress-indicator')).toBeInTheDocument();
    });

    test('component imports load successfully', () => {
      // This test will fail if there are import/module loading issues
      expect(() => {
        require('../ProcessingProgressIndicator');
      }).not.toThrow();
      
      expect(() => {
        require('../../types/processing');
      }).not.toThrow();
    });

    test('component mounts and unmounts cleanly', () => {
      const { unmount } = render(
        <ProcessingProgressIndicator processingData={mockProcessingData.parse} />
      );
      
      // Should fail if component doesn't mount properly
      expect(screen.getByTestId('processing-progress-indicator')).toBeInTheDocument();
      
      // Should fail if component doesn't unmount cleanly
      expect(() => unmount()).not.toThrow();
    });
  });

  describe('Progress Display Tests', () => {
    test('displays correct progress percentage for parse stage (25%)', () => {
      render(<ProcessingProgressIndicator processingData={mockProcessingData.parse} />);
      
      // Should fail if progress percentage is not 25%
      const progressElement = screen.getByTestId('progress-bar');
      expect(progressElement).toHaveAttribute('aria-valuenow', '25');
      expect(screen.getByText('25%')).toBeInTheDocument();
    });

    test('displays correct progress percentage for validate stage (50%)', () => {
      render(<ProcessingProgressIndicator processingData={mockProcessingData.validate} />);
      
      // Should fail if progress percentage is not 50%
      const progressElement = screen.getByTestId('progress-bar');
      expect(progressElement).toHaveAttribute('aria-valuenow', '50');
      expect(screen.getByText('50%')).toBeInTheDocument();
    });

    test('displays correct progress percentage for classify stage (75%)', () => {
      render(<ProcessingProgressIndicator processingData={mockProcessingData.classify} />);
      
      // Should fail if progress percentage is not 75%
      const progressElement = screen.getByTestId('progress-bar');
      expect(progressElement).toHaveAttribute('aria-valuenow', '75');
      expect(screen.getByText('75%')).toBeInTheDocument();
    });

    test('displays correct progress percentage for complete stage (100%)', () => {
      render(<ProcessingProgressIndicator processingData={mockProcessingData.complete} />);
      
      // Should fail if progress percentage is not 100%
      const progressElement = screen.getByTestId('progress-bar');
      expect(progressElement).toHaveAttribute('aria-valuenow', '100');
      expect(screen.getByText('100%')).toBeInTheDocument();
    });

    test('displays correct stage labels', () => {
      const stages = [
        { data: mockProcessingData.parse, label: 'Parse' },
        { data: mockProcessingData.validate, label: 'Validate' },
        { data: mockProcessingData.classify, label: 'Classify' },
        { data: mockProcessingData.complete, label: 'Complete' }
      ];

      stages.forEach(({ data, label }) => {
        const { unmount } = render(<ProcessingProgressIndicator processingData={data} />);
        
        // Should fail if stage labels don't match
        expect(screen.getByText(label)).toBeInTheDocument();
        expect(screen.getByTestId(`stage-label-${label.toLowerCase()}`)).toBeInTheDocument();
        
        unmount();
      });
    });

    test('highlights active processing stage', () => {
      render(<ProcessingProgressIndicator processingData={mockProcessingData.validate} />);
      
      // Should fail if active stage is not highlighted
      const activeStage = screen.getByTestId('stage-validate');
      expect(activeStage).toHaveClass('stage-active');
      
      // Previous stages should be marked as completed
      const parseStage = screen.getByTestId('stage-parse');
      expect(parseStage).toHaveClass('stage-completed');
    });

    test('shows completed stage visual indication', () => {
      render(<ProcessingProgressIndicator processingData={mockProcessingData.complete} />);
      
      // Should fail if completed stages don't have visual indication
      const stages = ['parse', 'validate', 'classify', 'complete'];
      stages.forEach(stage => {
        const stageElement = screen.getByTestId(`stage-${stage}`);
        expect(stageElement).toHaveClass('stage-completed');
      });
    });

    test('rejects invalid progress values', () => {
      const invalidProgress = {
        ...mockProcessingData.parse,
        progress: 33 as any // Invalid progress value
      };
      
      const errors: Error[] = [];
      const onError = (error: Error) => errors.push(error);
      
      render(
        <TestErrorBoundary onError={onError}>
          <ProcessingProgressIndicator processingData={invalidProgress} />
        </TestErrorBoundary>
      );
      
      // Should fail if invalid progress values are accepted
      expect(errors).toHaveLength(1);
      expect(screen.getByTestId('error-boundary')).toBeInTheDocument();
    });
  });

  describe('Processing State Tests', () => {
    test('displays idle state correctly', () => {
      render(<ProcessingProgressIndicator processingData={mockProcessingData.idle} />);
      
      // Should fail if idle state is not displayed correctly
      expect(screen.getByTestId('processing-status-idle')).toBeInTheDocument();
      expect(screen.getByText('Ready to start')).toBeInTheDocument();
    });

    test('displays processing state with active stage indication', () => {
      render(<ProcessingProgressIndicator processingData={mockProcessingData.validate} />);
      
      // Should fail if processing state is not displayed correctly
      expect(screen.getByTestId('processing-status-processing')).toBeInTheDocument();
      expect(screen.getByText('Processing...')).toBeInTheDocument();
      
      // Active stage should have pulsing animation
      const activeStage = screen.getByTestId('stage-validate');
      expect(activeStage).toHaveClass('stage-processing');
    });

    test('displays completed state with success indication', () => {
      render(<ProcessingProgressIndicator processingData={mockProcessingData.complete} />);
      
      // Should fail if completed state is not displayed correctly
      expect(screen.getByTestId('processing-status-completed')).toBeInTheDocument();
      expect(screen.getByText('Completed successfully')).toBeInTheDocument();
      expect(screen.getByTestId('success-icon')).toBeInTheDocument();
    });

    test('displays error state with error indication', () => {
      render(
        <ProcessingProgressIndicator 
          processingData={mockProcessingData.error}
          error={mockProcessingError}
        />
      );
      
      // Should fail if error state is not displayed correctly
      expect(screen.getByTestId('processing-status-error')).toBeInTheDocument();
      expect(screen.getByText('Processing failed')).toBeInTheDocument();
      expect(screen.getByTestId('error-icon')).toBeInTheDocument();
      expect(screen.getByText(mockProcessingError.message)).toBeInTheDocument();
    });

    test('displays cancelled state correctly', () => {
      render(<ProcessingProgressIndicator processingData={mockProcessingData.cancelled} />);
      
      // Should fail if cancelled state is not displayed correctly
      expect(screen.getByTestId('processing-status-cancelled')).toBeInTheDocument();
      expect(screen.getByText('Processing cancelled')).toBeInTheDocument();
      expect(screen.getByTestId('cancelled-icon')).toBeInTheDocument();
    });
  });

  describe('Stage Transition Tests', () => {
    test('shows smooth transitions between stages', () => {
      const { rerender } = render(
        <ProcessingProgressIndicator processingData={mockProcessingData.parse} />
      );
      
      // Initial state
      expect(screen.getByTestId('stage-parse')).toHaveClass('stage-active');
      
      // Transition to validate stage
      rerender(<ProcessingProgressIndicator processingData={mockProcessingData.validate} />);
      
      // Should fail if transitions are not smooth
      expect(screen.getByTestId('stage-parse')).toHaveClass('stage-completed');
      expect(screen.getByTestId('stage-validate')).toHaveClass('stage-active');
      
      // Check for transition CSS classes
      const progressContainer = screen.getByTestId('progress-container');
      expect(progressContainer).toHaveClass('progress-transitioning');
    });

    test('validates stage-percentage consistency', () => {
      const inconsistentData = {
        ...mockProcessingData.parse,
        stage: ProcessingStage.VALIDATE,
        progress: 25 as any // Wrong progress for validate stage
      };
      
      const errors: Error[] = [];
      const onError = (error: Error) => errors.push(error);
      
      render(
        <TestErrorBoundary onError={onError}>
          <ProcessingProgressIndicator processingData={inconsistentData} />
        </TestErrorBoundary>
      );
      
      // Should fail if stage-percentage inconsistency is not caught
      expect(errors).toHaveLength(1);
      expect(screen.getByTestId('error-boundary')).toBeInTheDocument();
    });

    test('shows stage completion indicators', () => {
      render(<ProcessingProgressIndicator processingData={mockProcessingData.classify} />);
      
      // Should fail if stage completion indicators are missing
      expect(screen.getByTestId('stage-parse')).toHaveClass('stage-completed');
      expect(screen.getByTestId('stage-validate')).toHaveClass('stage-completed');
      expect(screen.getByTestId('stage-classify')).toHaveClass('stage-active');
      expect(screen.getByTestId('stage-complete')).toHaveClass('stage-pending');
      
      // Check for completion checkmarks
      expect(screen.getByTestId('completion-icon-parse')).toBeInTheDocument();
      expect(screen.getByTestId('completion-icon-validate')).toBeInTheDocument();
    });
  });

  describe('Accessibility Tests', () => {
    test('has proper ARIA labels for screen readers', () => {
      render(<ProcessingProgressIndicator processingData={mockProcessingData.validate} />);
      
      // Should fail if ARIA labels are missing or incorrect
      const progressBar = screen.getByTestId('progress-bar');
      expect(progressBar).toHaveAttribute('role', 'progressbar');
      expect(progressBar).toHaveAttribute('aria-label', 'File processing progress');
      expect(progressBar).toHaveAttribute('aria-valuenow', '50');
      expect(progressBar).toHaveAttribute('aria-valuemin', '0');
      expect(progressBar).toHaveAttribute('aria-valuemax', '100');
      expect(progressBar).toHaveAttribute('aria-valuetext', 'Validate stage: 50% complete');
    });

    test('supports keyboard navigation', () => {
      render(<ProcessingProgressIndicator processingData={mockProcessingData.validate} />);
      
      // Should fail if keyboard navigation is not supported
      const container = screen.getByTestId('processing-progress-indicator');
      expect(container).toHaveAttribute('tabindex', '0');
      expect(container).toHaveAttribute('role', 'region');
      expect(container).toHaveAttribute('aria-label', 'Processing progress indicator');
      
      // Test keyboard focus
      container.focus();
      expect(container).toHaveFocus();
    });

    test('manages focus during progress updates', () => {
      const { rerender } = render(
        <ProcessingProgressIndicator processingData={mockProcessingData.parse} />
      );
      
      const container = screen.getByTestId('processing-progress-indicator');
      container.focus();
      
      // Update progress
      rerender(<ProcessingProgressIndicator processingData={mockProcessingData.validate} />);
      
      // Should fail if focus is not managed properly during updates
      expect(container).toHaveFocus();
    });

    test('has semantic HTML structure', () => {
      render(<ProcessingProgressIndicator processingData={mockProcessingData.validate} />);
      
      // Should fail if semantic HTML structure is incorrect
      const container = screen.getByTestId('processing-progress-indicator');
      expect(container.tagName).toBe('DIV');
      expect(container).toHaveAttribute('role', 'region');
      
      // Check for proper heading structure
      expect(screen.getByRole('heading', { level: 3, name: /processing progress/i })).toBeInTheDocument();
      
      // Check for list structure for stages
      const stagesList = screen.getByTestId('stages-list');
      expect(stagesList.tagName).toBe('OL');
      expect(stagesList).toHaveAttribute('role', 'list');
    });

    test('ensures color contrast compliance', () => {
      render(<ProcessingProgressIndicator processingData={mockProcessingData.error} />);
      
      // Should fail if color contrast is not compliant
      const errorElement = screen.getByTestId('processing-status-error');
      const computedStyle = window.getComputedStyle(errorElement);
      
      // Check that error state has appropriate contrast
      expect(computedStyle.color).not.toBe('rgb(255, 255, 255)'); // Not white on white
      expect(errorElement).toHaveClass('error-high-contrast');
    });

    test('announces progress changes to screen readers', () => {
      const { rerender } = render(
        <ProcessingProgressIndicator processingData={mockProcessingData.parse} />
      );
      
      // Should fail if aria-live region is not present
      expect(screen.getByTestId('progress-announcer')).toHaveAttribute('aria-live', 'polite');
      expect(screen.getByTestId('progress-announcer')).toHaveAttribute('aria-atomic', 'true');
      
      // Update progress
      rerender(<ProcessingProgressIndicator processingData={mockProcessingData.validate} />);
      
      // Should announce the change
      expect(screen.getByTestId('progress-announcer')).toHaveTextContent('Progress updated: Validate stage, 50% complete');
    });
  });

  describe('Integration Tests', () => {
    test('integrates correctly with ProcessingProgress interface', () => {
      const validProgress = createMockProcessingProgress(
        ProcessingStage.CLASSIFY,
        ProcessingStatus.PROCESSING,
        { file_type: FileType.REPORTING_CSV }
      );
      
      render(<ProcessingProgressIndicator processingData={validProgress} />);
      
      // Should fail if integration with types is incorrect
      expect(screen.getByTestId('processing-progress-indicator')).toBeInTheDocument();
      expect(screen.getByText('75%')).toBeInTheDocument();
      expect(screen.getByText('Classify')).toBeInTheDocument();
    });

    test('handles different file types correctly', () => {
      const campaignProgress = createMockProcessingProgress(
        ProcessingStage.VALIDATE,
        ProcessingStatus.PROCESSING,
        { file_type: FileType.CAMPAIGN_XLSX }
      );
      
      const reportingProgress = createMockProcessingProgress(
        ProcessingStage.VALIDATE,
        ProcessingStatus.PROCESSING,
        { file_type: FileType.REPORTING_CSV }
      );
      
      // Test campaign XLSX
      const { rerender } = render(<ProcessingProgressIndicator processingData={campaignProgress} />);
      expect(screen.getByTestId('file-type-campaign-xlsx')).toBeInTheDocument();
      expect(screen.getByText('Campaign XLSX')).toBeInTheDocument();
      
      // Test reporting CSV
      rerender(<ProcessingProgressIndicator processingData={reportingProgress} />);
      expect(screen.getByTestId('file-type-reporting-csv')).toBeInTheDocument();
      expect(screen.getByText('Reporting CSV')).toBeInTheDocument();
    });

    test('handles processing with timestamps correctly', () => {
      const progress = createMockProcessingProgress(
        ProcessingStage.CLASSIFY,
        ProcessingStatus.PROCESSING,
        {
          started_at: '2025-09-09T10:00:00Z',
          updated_at: '2025-09-09T10:15:00Z'
        }
      );
      
      render(<ProcessingProgressIndicator processingData={progress} />);
      
      // Should fail if timestamps are not displayed correctly
      expect(screen.getByTestId('processing-started-time')).toHaveTextContent('Started: 10:00 AM');
      expect(screen.getByTestId('processing-updated-time')).toHaveTextContent('Updated: 10:15 AM');
    });

    test('validates props with processing types validators', () => {
      // Test with invalid data that should trigger validation
      const invalidData = {
        batch_id: 'test',
        stage: 'invalid-stage',
        progress: 33,
        status: ProcessingStatus.PROCESSING,
        file_type: FileType.CAMPAIGN_XLSX,
        started_at: 'invalid-date',
        updated_at: '2025-09-09T10:15:00Z'
      } as any;
      
      const errors: Error[] = [];
      const onError = (error: Error) => errors.push(error);
      
      render(
        <TestErrorBoundary onError={onError}>
          <ProcessingProgressIndicator processingData={invalidData} />
        </TestErrorBoundary>
      );
      
      // Should fail if validation is not working
      expect(errors).toHaveLength(1);
      expect(errors[0].message).toContain('Invalid processing data');
    });
  });

  describe('Mock Data Integration Tests', () => {
    test('works with campaign XLSX processing scenarios', () => {
      const campaignScenarios = [
        { stage: ProcessingStage.PARSE, status: ProcessingStatus.PROCESSING, expectedText: 'Parsing campaign data...' },
        { stage: ProcessingStage.VALIDATE, status: ProcessingStatus.PROCESSING, expectedText: 'Validating campaign rules...' },
        { stage: ProcessingStage.CLASSIFY, status: ProcessingStatus.PROCESSING, expectedText: 'Classifying campaigns...' },
        { stage: ProcessingStage.COMPLETE, status: ProcessingStatus.COMPLETED, expectedText: 'Campaign processing complete' }
      ];
      
      campaignScenarios.forEach(scenario => {
        const mockData = createMockProcessingProgress(
          scenario.stage,
          scenario.status,
          { file_type: FileType.CAMPAIGN_XLSX }
        );
        
        const { unmount } = render(<ProcessingProgressIndicator processingData={mockData} />);
        
        // Should fail if campaign-specific messaging is not shown
        expect(screen.getByText(scenario.expectedText)).toBeInTheDocument();
        
        unmount();
      });
    });

    test('works with reporting CSV processing scenarios', () => {
      const reportingScenarios = [
        { stage: ProcessingStage.PARSE, status: ProcessingStatus.PROCESSING, expectedText: 'Parsing report data...' },
        { stage: ProcessingStage.VALIDATE, status: ProcessingStatus.PROCESSING, expectedText: 'Validating report format...' },
        { stage: ProcessingStage.CLASSIFY, status: ProcessingStatus.PROCESSING, expectedText: 'Classifying report metrics...' },
        { stage: ProcessingStage.COMPLETE, status: ProcessingStatus.COMPLETED, expectedText: 'Report processing complete' }
      ];
      
      reportingScenarios.forEach(scenario => {
        const mockData = createMockProcessingProgress(
          scenario.stage,
          scenario.status,
          { file_type: FileType.REPORTING_CSV }
        );
        
        const { unmount } = render(<ProcessingProgressIndicator processingData={mockData} />);
        
        // Should fail if reporting-specific messaging is not shown
        expect(screen.getByText(scenario.expectedText)).toBeInTheDocument();
        
        unmount();
      });
    });

    test('handles error scenarios with appropriate error display', () => {
      const errorScenarios = [
        { category: ErrorCategory.PARSING, message: 'Failed to parse file header' },
        { category: ErrorCategory.VALIDATION, message: 'Invalid campaign data format' },
        { category: ErrorCategory.PROCESSING, message: 'Classification service unavailable' },
        { category: ErrorCategory.SYSTEM, message: 'Database connection error' }
      ];
      
      errorScenarios.forEach(scenario => {
        const mockError = createProcessingError(
          scenario.category,
          ErrorSeverity.ERROR,
          'TEST_001',
          scenario.message,
          { file_type: FileType.CAMPAIGN_XLSX }
        );
        
        const { unmount } = render(
          <ProcessingProgressIndicator 
            processingData={mockProcessingData.error}
            error={mockError}
          />
        );
        
        // Should fail if error scenarios are not handled properly
        expect(screen.getByTestId(`error-category-${scenario.category}`)).toBeInTheDocument();
        expect(screen.getByText(scenario.message)).toBeInTheDocument();
        
        unmount();
      });
    });

    test('handles cancelled processing scenarios', () => {
      const cancelledData = createMockProcessingProgress(
        ProcessingStage.VALIDATE,
        ProcessingStatus.CANCELLED,
        { file_type: FileType.CAMPAIGN_XLSX }
      );
      
      render(<ProcessingProgressIndicator processingData={cancelledData} />);
      
      // Should fail if cancelled scenarios are not handled
      expect(screen.getByTestId('processing-status-cancelled')).toBeInTheDocument();
      expect(screen.getByText('Processing was cancelled during validation')).toBeInTheDocument();
      expect(screen.getByTestId('restart-processing-button')).toBeInTheDocument();
    });
  });

  describe('Edge Cases and Error Handling', () => {
    test('handles missing processingData prop', () => {
      const errors: Error[] = [];
      const onError = (error: Error) => errors.push(error);
      
      render(
        <TestErrorBoundary onError={onError}>
          <ProcessingProgressIndicator processingData={null as any} />
        </TestErrorBoundary>
      );
      
      // Should fail if null data is not handled
      expect(errors).toHaveLength(1);
      expect(screen.getByTestId('error-boundary')).toBeInTheDocument();
    });

    test('handles malformed timestamp data', () => {
      const malformedData = createMockProcessingProgress(
        ProcessingStage.PARSE,
        ProcessingStatus.PROCESSING,
        {
          started_at: 'invalid-timestamp',
          updated_at: 'also-invalid'
        }
      );
      
      render(<ProcessingProgressIndicator processingData={malformedData} />);
      
      // Should fail if malformed timestamps are not handled gracefully
      expect(screen.getByTestId('timestamp-error-fallback')).toBeInTheDocument();
      expect(screen.getByText('Timestamp unavailable')).toBeInTheDocument();
    });

    test('handles rapid progress updates without performance issues', () => {
      const { rerender } = render(
        <ProcessingProgressIndicator processingData={mockProcessingData.parse} />
      );
      
      // Rapid updates
      const stages = [mockProcessingData.validate, mockProcessingData.classify, mockProcessingData.complete];
      
      stages.forEach(stage => {
        rerender(<ProcessingProgressIndicator processingData={stage} />);
      });
      
      // Should fail if rapid updates cause performance issues or errors
      expect(consoleErrors.filter(err => err.includes('Warning')).length).toBe(0);
      expect(screen.getByTestId('processing-progress-indicator')).toBeInTheDocument();
    });
  });
});