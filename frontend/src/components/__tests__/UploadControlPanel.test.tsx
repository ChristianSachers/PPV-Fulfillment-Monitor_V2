import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { UploadControlPanel } from '../UploadControlPanel';
import {
  ProcessingState,
  ProcessingProgress,
  ProcessingStatus,
  ProcessingStage,
  FileType,
  ProcessingError,
  ErrorCategory,
  ErrorSeverity,
  createProcessingError,
  validateFileSize
} from '../../types/processing';
import * as uploadService from '../../services/uploadService';

// Mock the upload service
jest.mock('../../services/uploadService');
const mockedUploadService = uploadService as jest.Mocked<typeof uploadService>;

// Mock data for testing
const createMockProcessingProgress = (
  stage: ProcessingStage,
  status: ProcessingStatus,
  fileType: FileType,
  overrides?: Partial<ProcessingProgress>
): ProcessingProgress => ({
  batch_id: `batch-${fileType}-${Date.now()}`,
  stage,
  progress: stage === ProcessingStage.PARSE ? 25 :
           stage === ProcessingStage.VALIDATE ? 50 :
           stage === ProcessingStage.CLASSIFY ? 75 : 100,
  status,
  file_type: fileType,
  started_at: '2025-09-09T10:00:00Z',
  updated_at: '2025-09-09T10:30:00Z',
  completed_at: status === ProcessingStatus.COMPLETED ? '2025-09-09T10:35:00Z' : undefined,
  ...overrides
});

const createMockProcessingState = (
  campaignProgress?: ProcessingProgress | null,
  reportingProgress?: ProcessingProgress | null,
  errors: ProcessingError[] = []
): ProcessingState => ({
  campaign_xlsx: campaignProgress || null,
  reporting_csv: reportingProgress || null,
  errors,
  last_updated: new Date().toISOString()
});

// Processing state scenarios
const mockProcessingStates = {
  idle: createMockProcessingState(),
  campaignProcessing: createMockProcessingState(
    createMockProcessingProgress(ProcessingStage.VALIDATE, ProcessingStatus.PROCESSING, FileType.CAMPAIGN_XLSX)
  ),
  reportingProcessing: createMockProcessingState(
    null,
    createMockProcessingProgress(ProcessingStage.CLASSIFY, ProcessingStatus.PROCESSING, FileType.REPORTING_CSV)
  ),
  bothProcessing: createMockProcessingState(
    createMockProcessingProgress(ProcessingStage.PARSE, ProcessingStatus.PROCESSING, FileType.CAMPAIGN_XLSX),
    createMockProcessingProgress(ProcessingStage.VALIDATE, ProcessingStatus.PROCESSING, FileType.REPORTING_CSV)
  ),
  campaignCompleted: createMockProcessingState(
    createMockProcessingProgress(ProcessingStage.COMPLETE, ProcessingStatus.COMPLETED, FileType.CAMPAIGN_XLSX)
  ),
  campaignError: createMockProcessingState(
    createMockProcessingProgress(ProcessingStage.VALIDATE, ProcessingStatus.ERROR, FileType.CAMPAIGN_XLSX),
    null,
    [createProcessingError(
      ErrorCategory.VALIDATION,
      ErrorSeverity.ERROR,
      'VAL_001',
      'Invalid campaign data format',
      { file_type: FileType.CAMPAIGN_XLSX, row: 5 }
    )]
  ),
  reportingCancelled: createMockProcessingState(
    null,
    createMockProcessingProgress(ProcessingStage.CLASSIFY, ProcessingStatus.CANCELLED, FileType.REPORTING_CSV)
  )
};

// File size test data
const createMockFile = (name: string, sizeInMB: number, type: string = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'): File => {
  const sizeInBytes = sizeInMB * 1024 * 1024;
  const file = new File(['x'.repeat(sizeInBytes)], name, { type });
  // Mock the size property since File constructor doesn't set it correctly in tests
  Object.defineProperty(file, 'size', { value: sizeInBytes, writable: false });
  return file;
};

const testFiles = {
  validCampaignXLSX: createMockFile('campaign.xlsx', 50),
  validReportingCSV: createMockFile('report.csv', 30, 'text/csv'),
  oversizedCampaign: createMockFile('huge-campaign.xlsx', 300),
  exactLimitFile: createMockFile('limit-file.xlsx', 250),
  emptyFile: createMockFile('empty.xlsx', 0),
  invalidTypeFile: createMockFile('document.pdf', 10, 'application/pdf')
};

// Mock console.error to catch rendering issues
const originalError = console.error;
let consoleErrors: string[] = [];

// Mock ProcessingProgressIndicator component
jest.mock('../ProcessingProgressIndicator', () => ({
  ProcessingProgressIndicator: ({ processingData, error, onCancel }: any) => (
    <div data-testid="processing-progress-indicator">
      <div data-testid={`processing-status-${processingData?.status || 'unknown'}`}>
        Status: {processingData?.status || 'unknown'}
      </div>
      <div data-testid={`processing-stage-${processingData?.stage || 'unknown'}`}>
        Stage: {processingData?.stage || 'unknown'}
      </div>
      <div data-testid={`file-type-${processingData?.file_type || 'unknown'}`}>
        File Type: {processingData?.file_type || 'unknown'}
      </div>
      {error && (
        <div data-testid="processing-error">
          Error: {error.message}
        </div>
      )}
      {onCancel && (
        <button data-testid="cancel-processing-button" onClick={onCancel}>
          Cancel Processing
        </button>
      )}
    </div>
  )
}));

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
          <h2>UploadControlPanel Rendering Error</h2>
          <pre>{this.state.error?.message}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

describe('UploadControlPanel Component - TDD Test Suite', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    consoleErrors = [];
    console.error = (...args: any[]) => {
      consoleErrors.push(args.join(' '));
      originalError(...args);
    };
    
    // Mock successful validation by default
    mockedUploadService.validateFile.mockReturnValue({
      isValid: true,
      errors: []
    });
    
    // Mock successful upload by default
    mockedUploadService.uploadFile.mockResolvedValue({
      upload_id: 'test-upload-id',
      filename: 'test.xlsx',
      file_size: 1024,
      upload_date: '2025-09-09T10:00:00Z',
      status: 'completed'
    });
  });

  afterEach(() => {
    console.error = originalError;
  });

  describe('TDD RED Phase - Component Rendering Tests', () => {
    test('UploadControlPanel component renders without crashing', () => {
      const errors: Error[] = [];
      const onError = (error: Error) => errors.push(error);
      
      render(
        <TestErrorBoundary onError={onError}>
          <UploadControlPanel 
            processingState={mockProcessingStates.idle}
            onUploadStart={() => {}}
            onCancelProcessing={() => {}}
          />
        </TestErrorBoundary>
      );
      
      // This test should FAIL if component doesn't exist or has rendering errors
      expect(errors).toHaveLength(0);
      expect(consoleErrors.filter(err => err.includes('Error')).length).toBe(0);
      expect(screen.queryByTestId('error-boundary')).not.toBeInTheDocument();
    });

    test('renders main container with proper test id', () => {
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.idle}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if container doesn't have proper test id
      expect(screen.getByTestId('upload-control-panel')).toBeInTheDocument();
    });

    test('renders separate sections for Campaign XLSX and Reporting CSV', () => {
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.idle}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if file type sections are not rendered
      expect(screen.getByTestId('campaign-upload-section')).toBeInTheDocument();
      expect(screen.getByTestId('reporting-upload-section')).toBeInTheDocument();
    });

    test('component imports load successfully', () => {
      // This test will fail if there are import/module loading issues
      expect(() => {
        require('../UploadControlPanel');
      }).not.toThrow();
      
      expect(() => {
        require('../../types/processing');
      }).not.toThrow();
      
      expect(() => {
        require('../../services/uploadService');
      }).not.toThrow();
    });

    test('component mounts and unmounts cleanly', () => {
      const { unmount } = render(
        <UploadControlPanel 
          processingState={mockProcessingStates.idle}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if component doesn't mount properly
      expect(screen.getByTestId('upload-control-panel')).toBeInTheDocument();
      
      // Should fail if component doesn't unmount cleanly
      expect(() => unmount()).not.toThrow();
    });
  });

  describe('1. Upload Button State Tests', () => {
    test('upload buttons enabled when no processing active', () => {
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.idle}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if buttons are not enabled when idle
      const campaignUploadButton = screen.getByTestId('campaign-upload-button');
      const reportingUploadButton = screen.getByTestId('reporting-upload-button');
      
      expect(campaignUploadButton).not.toBeDisabled();
      expect(reportingUploadButton).not.toBeDisabled();
    });

    test('campaign upload button disabled when campaign processing active', () => {
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.campaignProcessing}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if campaign button is not disabled during processing
      const campaignUploadButton = screen.getByTestId('campaign-upload-button');
      expect(campaignUploadButton).toBeDisabled();
      expect(campaignUploadButton).toHaveAttribute('aria-disabled', 'true');
    });

    test('reporting upload button disabled when reporting processing active', () => {
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.reportingProcessing}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if reporting button is not disabled during processing
      const reportingUploadButton = screen.getByTestId('reporting-upload-button');
      expect(reportingUploadButton).toBeDisabled();
      expect(reportingUploadButton).toHaveAttribute('aria-disabled', 'true');
    });

    test('buttons remain enabled for non-processing file types during concurrent processing', () => {
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.campaignProcessing}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if non-processing file type button is disabled
      const campaignUploadButton = screen.getByTestId('campaign-upload-button');
      const reportingUploadButton = screen.getByTestId('reporting-upload-button');
      
      expect(campaignUploadButton).toBeDisabled(); // Campaign is processing
      expect(reportingUploadButton).not.toBeDisabled(); // Reporting is not processing
    });

    test('button re-enablement after processing completion', () => {
      const { rerender } = render(
        <UploadControlPanel 
          processingState={mockProcessingStates.campaignProcessing}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      const campaignUploadButton = screen.getByTestId('campaign-upload-button');
      expect(campaignUploadButton).toBeDisabled();
      
      // Processing completes
      rerender(
        <UploadControlPanel 
          processingState={mockProcessingStates.campaignCompleted}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if button is not re-enabled after completion
      expect(campaignUploadButton).not.toBeDisabled();
    });

    test('button re-enablement after processing error', () => {
      const { rerender } = render(
        <UploadControlPanel 
          processingState={mockProcessingStates.campaignProcessing}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      const campaignUploadButton = screen.getByTestId('campaign-upload-button');
      expect(campaignUploadButton).toBeDisabled();
      
      // Processing fails
      rerender(
        <UploadControlPanel 
          processingState={mockProcessingStates.campaignError}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if button is not re-enabled after error
      expect(campaignUploadButton).not.toBeDisabled();
    });

    test('button re-enablement after processing cancellation', () => {
      const { rerender } = render(
        <UploadControlPanel 
          processingState={mockProcessingStates.reportingProcessing}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      const reportingUploadButton = screen.getByTestId('reporting-upload-button');
      expect(reportingUploadButton).toBeDisabled();
      
      // Processing is cancelled
      rerender(
        <UploadControlPanel 
          processingState={mockProcessingStates.reportingCancelled}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if button is not re-enabled after cancellation
      expect(reportingUploadButton).not.toBeDisabled();
    });

    test('button state with invalid processing states', () => {
      const invalidState = {
        ...mockProcessingStates.idle,
        campaign_xlsx: {
          ...createMockProcessingProgress(ProcessingStage.VALIDATE, ProcessingStatus.PROCESSING, FileType.CAMPAIGN_XLSX),
          status: 'invalid-status' as any
        }
      };
      
      const errors: Error[] = [];
      const onError = (error: Error) => errors.push(error);
      
      render(
        <TestErrorBoundary onError={onError}>
          <UploadControlPanel 
            processingState={invalidState}
            onUploadStart={() => {}}
            onCancelProcessing={() => {}}
          />
        </TestErrorBoundary>
      );
      
      // Should fail if invalid states are not handled gracefully
      expect(errors).toHaveLength(1);
      expect(screen.getByTestId('error-boundary')).toBeInTheDocument();
    });
  });

  describe('2. File Type Separation Tests', () => {
    test('Campaign XLSX upload control independent of Reporting CSV processing', () => {
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.reportingProcessing}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if campaign controls are affected by reporting processing
      const campaignUploadButton = screen.getByTestId('campaign-upload-button');
      const reportingUploadButton = screen.getByTestId('reporting-upload-button');
      
      expect(campaignUploadButton).not.toBeDisabled();
      expect(reportingUploadButton).toBeDisabled();
      
      // Campaign section should show ready state
      expect(screen.getByTestId('campaign-status-ready')).toBeInTheDocument();
      // Reporting section should show processing state
      expect(screen.getByTestId('reporting-status-processing')).toBeInTheDocument();
    });

    test('Reporting CSV upload control independent of Campaign XLSX processing', () => {
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.campaignProcessing}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if reporting controls are affected by campaign processing
      const campaignUploadButton = screen.getByTestId('campaign-upload-button');
      const reportingUploadButton = screen.getByTestId('reporting-upload-button');
      
      expect(campaignUploadButton).toBeDisabled();
      expect(reportingUploadButton).not.toBeDisabled();
      
      // Reporting section should show ready state
      expect(screen.getByTestId('reporting-status-ready')).toBeInTheDocument();
      // Campaign section should show processing state
      expect(screen.getByTestId('campaign-status-processing')).toBeInTheDocument();
    });

    test('concurrent processing limits (one Campaign + one Reporting max)', () => {
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.bothProcessing}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if both file types cannot process concurrently
      const campaignUploadButton = screen.getByTestId('campaign-upload-button');
      const reportingUploadButton = screen.getByTestId('reporting-upload-button');
      
      expect(campaignUploadButton).toBeDisabled();
      expect(reportingUploadButton).toBeDisabled();
      
      // Both sections should show processing state
      expect(screen.getByTestId('campaign-status-processing')).toBeInTheDocument();
      expect(screen.getByTestId('reporting-status-processing')).toBeInTheDocument();
    });

    test('file type detection and routing', () => {
      const mockOnUploadStart = jest.fn();
      
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.idle}
          onUploadStart={mockOnUploadStart}
          onCancelProcessing={() => {}}
        />
      );
      
      // Test Campaign XLSX file selection
      const campaignFileInput = screen.getByTestId('campaign-file-input');
      fireEvent.change(campaignFileInput, { 
        target: { files: [testFiles.validCampaignXLSX] } 
      });
      
      const campaignUploadButton = screen.getByTestId('campaign-upload-button');
      fireEvent.click(campaignUploadButton);
      
      // Should fail if file type routing is incorrect
      expect(mockOnUploadStart).toHaveBeenCalledWith(
        testFiles.validCampaignXLSX,
        FileType.CAMPAIGN_XLSX
      );
    });

    test('file type specific messaging', () => {
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.campaignProcessing}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if file type specific messages are not shown
      expect(screen.getByText(/campaign xlsx processing/i)).toBeInTheDocument();
      expect(screen.getByText(/reporting csv ready/i)).toBeInTheDocument();
    });
  });

  describe('3. Processing State Display Tests', () => {
    test('displays "Processing in progress" message when active', () => {
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.campaignProcessing}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if processing message is not displayed
      expect(screen.getByTestId('campaign-processing-message')).toBeInTheDocument();
      expect(screen.getByText(/processing in progress/i)).toBeInTheDocument();
      expect(screen.getByText(/wait or cancel/i)).toBeInTheDocument();
    });

    test('displays "Ready to upload" message when idle', () => {
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.idle}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if ready message is not displayed
      expect(screen.getByTestId('campaign-ready-message')).toBeInTheDocument();
      expect(screen.getByTestId('reporting-ready-message')).toBeInTheDocument();
      expect(screen.getAllByText(/ready to upload/i)).toHaveLength(2);
    });

    test('displays "Processing completed" message after success', () => {
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.campaignCompleted}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if completion message is not displayed
      expect(screen.getByTestId('campaign-completed-message')).toBeInTheDocument();
      expect(screen.getByText(/processing completed/i)).toBeInTheDocument();
    });

    test('displays "Processing failed" message after error', () => {
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.campaignError}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if error message is not displayed
      expect(screen.getByTestId('campaign-error-message')).toBeInTheDocument();
      expect(screen.getByText(/processing failed/i)).toBeInTheDocument();
      expect(screen.getByText(/invalid campaign data format/i)).toBeInTheDocument();
    });

    test('processing state transitions and messaging updates', () => {
      const { rerender } = render(
        <UploadControlPanel 
          processingState={mockProcessingStates.idle}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Initial state
      expect(screen.getByTestId('campaign-ready-message')).toBeInTheDocument();
      
      // Transition to processing
      rerender(
        <UploadControlPanel 
          processingState={mockProcessingStates.campaignProcessing}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if state transition messaging is not updated
      expect(screen.getByTestId('campaign-processing-message')).toBeInTheDocument();
      expect(screen.queryByTestId('campaign-ready-message')).not.toBeInTheDocument();
    });
  });

  describe('4. Cancel Processing Tests', () => {
    test('cancel button appears during active processing', () => {
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.campaignProcessing}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if cancel button is not shown during processing
      expect(screen.getByTestId('campaign-cancel-button')).toBeInTheDocument();
      expect(screen.getByText(/cancel/i)).toBeInTheDocument();
    });

    test('cancel button functionality triggers processing cancellation', () => {
      const mockOnCancelProcessing = jest.fn();
      
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.campaignProcessing}
          onUploadStart={() => {}}
          onCancelProcessing={mockOnCancelProcessing}
        />
      );
      
      const cancelButton = screen.getByTestId('campaign-cancel-button');
      fireEvent.click(cancelButton);
      
      // Should fail if cancel callback is not triggered
      expect(mockOnCancelProcessing).toHaveBeenCalledWith(
        FileType.CAMPAIGN_XLSX,
        mockProcessingStates.campaignProcessing.campaign_xlsx?.batch_id
      );
    });

    test('cancel confirmation dialog', () => {
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.campaignProcessing}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      const cancelButton = screen.getByTestId('campaign-cancel-button');
      fireEvent.click(cancelButton);
      
      // Should fail if confirmation dialog is not shown
      expect(screen.getByTestId('cancel-confirmation-dialog')).toBeInTheDocument();
      expect(screen.getByText(/are you sure you want to cancel/i)).toBeInTheDocument();
      expect(screen.getByTestId('confirm-cancel-button')).toBeInTheDocument();
      expect(screen.getByTestId('dismiss-cancel-button')).toBeInTheDocument();
    });

    test('cancel button disabled when no processing active', () => {
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.idle}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if cancel button is shown when not processing
      expect(screen.queryByTestId('campaign-cancel-button')).not.toBeInTheDocument();
      expect(screen.queryByTestId('reporting-cancel-button')).not.toBeInTheDocument();
    });

    test('cancel operation success/failure handling', async () => {
      const mockOnCancelProcessing = jest.fn().mockResolvedValue({ success: true });
      
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.campaignProcessing}
          onUploadStart={() => {}}
          onCancelProcessing={mockOnCancelProcessing}
        />
      );
      
      const cancelButton = screen.getByTestId('campaign-cancel-button');
      fireEvent.click(cancelButton);
      
      const confirmButton = screen.getByTestId('confirm-cancel-button');
      fireEvent.click(confirmButton);
      
      // Should fail if cancel success handling is not implemented
      await waitFor(() => {
        expect(screen.getByTestId('cancel-success-message')).toBeInTheDocument();
      });
    });
  });

  describe('5. File Upload Integration Tests', () => {
    test('file selection triggers upload process', () => {
      const mockOnUploadStart = jest.fn();
      
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.idle}
          onUploadStart={mockOnUploadStart}
          onCancelProcessing={() => {}}
        />
      );
      
      const campaignFileInput = screen.getByTestId('campaign-file-input');
      fireEvent.change(campaignFileInput, { 
        target: { files: [testFiles.validCampaignXLSX] } 
      });
      
      const campaignUploadButton = screen.getByTestId('campaign-upload-button');
      fireEvent.click(campaignUploadButton);
      
      // Should fail if upload process is not triggered
      expect(mockOnUploadStart).toHaveBeenCalledWith(
        testFiles.validCampaignXLSX,
        FileType.CAMPAIGN_XLSX
      );
    });

    test('file validation before upload (size, type)', () => {
      mockedUploadService.validateFile.mockReturnValue({
        isValid: false,
        errors: ['File size exceeds 250MB limit']
      });
      
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.idle}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      const campaignFileInput = screen.getByTestId('campaign-file-input');
      fireEvent.change(campaignFileInput, { 
        target: { files: [testFiles.oversizedCampaign] } 
      });
      
      // Should fail if validation is not performed
      expect(screen.getByTestId('campaign-validation-error')).toBeInTheDocument();
      expect(screen.getByText(/file size exceeds 250mb limit/i)).toBeInTheDocument();
      expect(screen.getByTestId('campaign-upload-button')).toBeDisabled();
    });

    test('upload progress integration with ProcessingProgressIndicator', () => {
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.campaignProcessing}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if ProcessingProgressIndicator is not integrated
      expect(screen.getByTestId('processing-progress-indicator')).toBeInTheDocument();
      expect(screen.getByTestId('processing-status-processing')).toBeInTheDocument();
      expect(screen.getByTestId('processing-stage-validate')).toBeInTheDocument();
      expect(screen.getByTestId('file-type-campaign_xlsx')).toBeInTheDocument();
    });

    test('upload error handling and display', () => {
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.campaignError}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if upload errors are not handled and displayed
      expect(screen.getByTestId('processing-error')).toBeInTheDocument();
      expect(screen.getByText(/invalid campaign data format/i)).toBeInTheDocument();
    });

    test('upload success handling', () => {
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.campaignCompleted}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if upload success is not handled properly
      expect(screen.getByTestId('campaign-completed-message')).toBeInTheDocument();
      expect(screen.getByTestId('campaign-upload-button')).not.toBeDisabled();
    });
  });

  describe('6. File Size Validation Tests', () => {
    test('250MB limit enforcement (exactly)', () => {
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.idle}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      const campaignFileInput = screen.getByTestId('campaign-file-input');
      fireEvent.change(campaignFileInput, { 
        target: { files: [testFiles.exactLimitFile] } 
      });
      
      // Should fail if exact 250MB limit is not handled correctly
      expect(screen.queryByTestId('campaign-validation-error')).not.toBeInTheDocument();
      expect(screen.getByTestId('campaign-upload-button')).not.toBeDisabled();
    });

    test('file size validation before backend submission', () => {
      const mockOnUploadStart = jest.fn();
      
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.idle}
          onUploadStart={mockOnUploadStart}
          onCancelProcessing={() => {}}
        />
      );
      
      const campaignFileInput = screen.getByTestId('campaign-file-input');
      fireEvent.change(campaignFileInput, { 
        target: { files: [testFiles.oversizedCampaign] } 
      });
      
      const campaignUploadButton = screen.getByTestId('campaign-upload-button');
      fireEvent.click(campaignUploadButton);
      
      // Should fail if oversized files are sent to backend
      expect(mockOnUploadStart).not.toHaveBeenCalled();
      expect(screen.getByTestId('campaign-validation-error')).toBeInTheDocument();
    });

    test('oversized file rejection with proper error messages', () => {
      mockedUploadService.validateFile.mockReturnValue({
        isValid: false,
        errors: ['File size exceeds 250MB limit']
      });
      
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.idle}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      const campaignFileInput = screen.getByTestId('campaign-file-input');
      fireEvent.change(campaignFileInput, { 
        target: { files: [testFiles.oversizedCampaign] } 
      });
      
      // Should fail if oversized file error messages are not displayed
      expect(screen.getByTestId('campaign-validation-error')).toBeInTheDocument();
      expect(screen.getByText(/file size exceeds 250mb limit/i)).toBeInTheDocument();
    });

    test('file size display and formatting', () => {
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.idle}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      const campaignFileInput = screen.getByTestId('campaign-file-input');
      fireEvent.change(campaignFileInput, { 
        target: { files: [testFiles.validCampaignXLSX] } 
      });
      
      // Should fail if file size is not displayed with proper formatting
      expect(screen.getByTestId('campaign-file-info')).toBeInTheDocument();
      expect(screen.getByText(/50(\s)?mb/i)).toBeInTheDocument();
    });

    test('validation error handling', () => {
      mockedUploadService.validateFile.mockImplementation(() => {
        throw new Error('Validation service error');
      });
      
      const errors: Error[] = [];
      const onError = (error: Error) => errors.push(error);
      
      render(
        <TestErrorBoundary onError={onError}>
          <UploadControlPanel 
            processingState={mockProcessingStates.idle}
            onUploadStart={() => {}}
            onCancelProcessing={() => {}}
          />
        </TestErrorBoundary>
      );
      
      const campaignFileInput = screen.getByTestId('campaign-file-input');
      fireEvent.change(campaignFileInput, { 
        target: { files: [testFiles.validCampaignXLSX] } 
      });
      
      // Should fail if validation errors are not handled gracefully
      expect(errors).toHaveLength(1);
      expect(screen.getByTestId('error-boundary')).toBeInTheDocument();
    });
  });

  describe('7. Accessibility Tests', () => {
    test('keyboard navigation for upload controls', () => {
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.idle}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if keyboard navigation is not supported
      const campaignFileInput = screen.getByTestId('campaign-file-input');
      const campaignUploadButton = screen.getByTestId('campaign-upload-button');
      const reportingFileInput = screen.getByTestId('reporting-file-input');
      
      campaignFileInput.focus();
      expect(campaignFileInput).toHaveFocus();
      
      fireEvent.keyDown(campaignFileInput, { key: 'Tab' });
      expect(campaignUploadButton).toHaveFocus();
      
      fireEvent.keyDown(campaignUploadButton, { key: 'Tab' });
      expect(reportingFileInput).toHaveFocus();
    });

    test('screen reader compatibility for state changes', () => {
      const { rerender } = render(
        <UploadControlPanel 
          processingState={mockProcessingStates.idle}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if aria-live regions are not present
      expect(screen.getByTestId('campaign-status-announcer')).toHaveAttribute('aria-live', 'polite');
      expect(screen.getByTestId('reporting-status-announcer')).toHaveAttribute('aria-live', 'polite');
      
      // State change
      rerender(
        <UploadControlPanel 
          processingState={mockProcessingStates.campaignProcessing}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should announce state change
      expect(screen.getByTestId('campaign-status-announcer')).toHaveTextContent(
        /campaign processing started/i
      );
    });

    test('ARIA labels for upload buttons and status messages', () => {
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.idle}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if ARIA labels are missing
      const campaignUploadButton = screen.getByTestId('campaign-upload-button');
      const reportingUploadButton = screen.getByTestId('reporting-upload-button');
      
      expect(campaignUploadButton).toHaveAttribute('aria-label', 'Upload Campaign XLSX file');
      expect(reportingUploadButton).toHaveAttribute('aria-label', 'Upload Reporting CSV file');
      
      expect(screen.getByTestId('campaign-status-message')).toHaveAttribute('role', 'status');
      expect(screen.getByTestId('reporting-status-message')).toHaveAttribute('role', 'status');
    });

    test('focus management during state transitions', () => {
      const { rerender } = render(
        <UploadControlPanel 
          processingState={mockProcessingStates.idle}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      const campaignUploadButton = screen.getByTestId('campaign-upload-button');
      campaignUploadButton.focus();
      
      // State changes to processing
      rerender(
        <UploadControlPanel 
          processingState={mockProcessingStates.campaignProcessing}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if focus is not managed properly
      const cancelButton = screen.getByTestId('campaign-cancel-button');
      expect(cancelButton).toHaveFocus();
    });

    test('semantic HTML structure', () => {
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.idle}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if semantic HTML structure is incorrect
      const mainContainer = screen.getByTestId('upload-control-panel');
      expect(mainContainer).toHaveAttribute('role', 'main');
      
      const campaignSection = screen.getByTestId('campaign-upload-section');
      expect(campaignSection).toHaveAttribute('role', 'region');
      expect(campaignSection).toHaveAttribute('aria-labelledby', 'campaign-section-title');
      
      const reportingSection = screen.getByTestId('reporting-upload-section');
      expect(reportingSection).toHaveAttribute('role', 'region');
      expect(reportingSection).toHaveAttribute('aria-labelledby', 'reporting-section-title');
    });
  });

  describe('8. Integration Tests', () => {
    test('integrates correctly with ProcessingState interface', () => {
      const customProcessingState = createMockProcessingState(
        createMockProcessingProgress(ProcessingStage.CLASSIFY, ProcessingStatus.PROCESSING, FileType.CAMPAIGN_XLSX),
        createMockProcessingProgress(ProcessingStage.VALIDATE, ProcessingStatus.COMPLETED, FileType.REPORTING_CSV)
      );
      
      render(
        <UploadControlPanel 
          processingState={customProcessingState}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if ProcessingState integration is incorrect
      expect(screen.getByTestId('campaign-status-processing')).toBeInTheDocument();
      expect(screen.getByTestId('reporting-status-completed')).toBeInTheDocument();
    });

    test('handles different file types correctly', () => {
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.bothProcessing}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if file type handling is incorrect
      expect(screen.getByTestId('file-type-campaign_xlsx')).toBeInTheDocument();
      expect(screen.getByTestId('file-type-reporting_csv')).toBeInTheDocument();
    });

    test('ProcessingProgress updates', () => {
      const { rerender } = render(
        <UploadControlPanel 
          processingState={mockProcessingStates.campaignProcessing}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      expect(screen.getByTestId('processing-stage-validate')).toBeInTheDocument();
      
      // Update to different stage
      const updatedState = createMockProcessingState(
        createMockProcessingProgress(ProcessingStage.CLASSIFY, ProcessingStatus.PROCESSING, FileType.CAMPAIGN_XLSX)
      );
      
      rerender(
        <UploadControlPanel 
          processingState={updatedState}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if progress updates are not reflected
      expect(screen.getByTestId('processing-stage-classify')).toBeInTheDocument();
    });

    test('ProcessingError handling and display', () => {
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.campaignError}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Should fail if error handling integration is incorrect
      expect(screen.getByTestId('processing-error')).toBeInTheDocument();
      expect(screen.getByText(/invalid campaign data format/i)).toBeInTheDocument();
    });

    test('file type enum usage', () => {
      const mockOnUploadStart = jest.fn();
      
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.idle}
          onUploadStart={mockOnUploadStart}
          onCancelProcessing={() => {}}
        />
      );
      
      const reportingFileInput = screen.getByTestId('reporting-file-input');
      fireEvent.change(reportingFileInput, { 
        target: { files: [testFiles.validReportingCSV] } 
      });
      
      const reportingUploadButton = screen.getByTestId('reporting-upload-button');
      fireEvent.click(reportingUploadButton);
      
      // Should fail if FileType enum is not used correctly
      expect(mockOnUploadStart).toHaveBeenCalledWith(
        testFiles.validReportingCSV,
        FileType.REPORTING_CSV
      );
    });

    test('processing status enum integration', () => {
      const testStatuses = [
        { status: ProcessingStatus.IDLE, expectedTestId: 'campaign-status-ready' },
        { status: ProcessingStatus.PROCESSING, expectedTestId: 'campaign-status-processing' },
        { status: ProcessingStatus.COMPLETED, expectedTestId: 'campaign-status-completed' },
        { status: ProcessingStatus.ERROR, expectedTestId: 'campaign-status-error' },
        { status: ProcessingStatus.CANCELLED, expectedTestId: 'campaign-status-cancelled' }
      ];
      
      testStatuses.forEach(({ status, expectedTestId }) => {
        const testState = createMockProcessingState(
          status === ProcessingStatus.IDLE ? null : 
          createMockProcessingProgress(ProcessingStage.VALIDATE, status, FileType.CAMPAIGN_XLSX)
        );
        
        const { unmount } = render(
          <UploadControlPanel 
            processingState={testState}
            onUploadStart={() => {}}
            onCancelProcessing={() => {}}
          />
        );
        
        // Should fail if status enum integration is incorrect
        expect(screen.getByTestId(expectedTestId)).toBeInTheDocument();
        
        unmount();
      });
    });
  });

  describe('Edge Cases and Error Handling', () => {
    test('handles missing processingState prop', () => {
      const errors: Error[] = [];
      const onError = (error: Error) => errors.push(error);
      
      render(
        <TestErrorBoundary onError={onError}>
          <UploadControlPanel 
            processingState={null as any}
            onUploadStart={() => {}}
            onCancelProcessing={() => {}}
          />
        </TestErrorBoundary>
      );
      
      // Should fail if null processingState is not handled
      expect(errors).toHaveLength(1);
      expect(screen.getByTestId('error-boundary')).toBeInTheDocument();
    });

    test('handles malformed processing state data', () => {
      const malformedState = {
        campaign_xlsx: 'invalid-data',
        reporting_csv: null,
        errors: [],
        last_updated: 'invalid-timestamp'
      } as any;
      
      const errors: Error[] = [];
      const onError = (error: Error) => errors.push(error);
      
      render(
        <TestErrorBoundary onError={onError}>
          <UploadControlPanel 
            processingState={malformedState}
            onUploadStart={() => {}}
            onCancelProcessing={() => {}}
          />
        </TestErrorBoundary>
      );
      
      // Should fail if malformed data is not handled gracefully
      expect(errors).toHaveLength(1);
      expect(screen.getByTestId('error-boundary')).toBeInTheDocument();
    });

    test('handles empty file selection gracefully', () => {
      render(
        <UploadControlPanel 
          processingState={mockProcessingStates.idle}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      const campaignFileInput = screen.getByTestId('campaign-file-input');
      fireEvent.change(campaignFileInput, { target: { files: [] } });
      
      // Should fail if empty file selection is not handled
      expect(screen.getByTestId('campaign-upload-button')).toBeDisabled();
    });

    test('handles rapid state changes without performance issues', () => {
      const states = [
        mockProcessingStates.idle,
        mockProcessingStates.campaignProcessing,
        mockProcessingStates.campaignCompleted,
        mockProcessingStates.campaignError,
        mockProcessingStates.idle
      ];
      
      const { rerender } = render(
        <UploadControlPanel 
          processingState={states[0]}
          onUploadStart={() => {}}
          onCancelProcessing={() => {}}
        />
      );
      
      // Rapid state changes
      states.forEach(state => {
        rerender(
          <UploadControlPanel 
            processingState={state}
            onUploadStart={() => {}}
            onCancelProcessing={() => {}}
          />
        );
      });
      
      // Should fail if rapid updates cause performance issues or errors
      expect(consoleErrors.filter(err => err.includes('Warning')).length).toBe(0);
      expect(screen.getByTestId('upload-control-panel')).toBeInTheDocument();
    });

    test('validates callback function props', () => {
      const errors: Error[] = [];
      const onError = (error: Error) => errors.push(error);
      
      render(
        <TestErrorBoundary onError={onError}>
          <UploadControlPanel 
            processingState={mockProcessingStates.idle}
            onUploadStart={null as any}
            onCancelProcessing={undefined as any}
          />
        </TestErrorBoundary>
      );
      
      // Should fail if invalid callback props are not validated
      expect(errors).toHaveLength(1);
      expect(screen.getByTestId('error-boundary')).toBeInTheDocument();
    });
  });
});