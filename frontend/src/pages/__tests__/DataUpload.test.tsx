import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import DataUpload from '../DataUpload';
import * as uploadService from '../../services/uploadService';
import { 
  ProcessingState, 
  ProcessingStatus, 
  ProcessingStage, 
  FileType, 
  ProcessingFileType,
  ErrorCategory,
  ErrorSeverity 
} from '../../types/processing';

// Mock the upload service and processing components
jest.mock('../../services/uploadService');
jest.mock('../../services/processingStatusService');
jest.mock('../../hooks/useProcessingStatus');
jest.mock('../../components/ProcessingProgressIndicator');
jest.mock('../../components/UploadControlPanel');
jest.mock('../../components/ErrorDisplayPanel');

const mockedUploadService = uploadService as jest.Mocked<typeof uploadService>;

// Mock implementations for processing pipeline components
const mockUseProcessingStatus = require('../../hooks/useProcessingStatus');
const mockProcessingProgressIndicator = require('../../components/ProcessingProgressIndicator');
const mockUploadControlPanel = require('../../components/UploadControlPanel');
const mockErrorDisplayPanel = require('../../components/ErrorDisplayPanel');

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
          <h2>DataUpload Rendering Error</h2>
          <pre>{this.state.error?.message}</pre>
          <pre>{this.state.error?.stack}</pre>
        </div>
      );
    }
    return this.props.children;
  }
}

describe('DataUpload Processing Pipeline Integration Component', () => {
  let mockProcessingStatusHook: any;

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

    // Mock processing status hook with default idle state
    mockProcessingStatusHook = {
      processingState: {
        campaign_xlsx: null,
        reporting_csv: null,
        errors: [],
        last_updated: new Date().toISOString()
      },
      currentProgress: null,
      errors: [],
      startProcessing: jest.fn(),
      cancelProcessing: jest.fn(),
      clearErrors: jest.fn(),
      isProcessing: false,
      canUpload: jest.fn(() => true),
      hasErrors: false
    };
    mockUseProcessingStatus.useProcessingStatus.mockReturnValue(mockProcessingStatusHook);

    // Mock component implementations
    mockProcessingProgressIndicator.ProcessingProgressIndicator.mockImplementation(
      ({ processingData, error }: any) => (
        <div data-testid="processing-progress-indicator">
          <div data-testid="progress-stage">{processingData?.stage}</div>
          <div data-testid="progress-percent">{processingData?.progress}%</div>
          <div data-testid="progress-status">{processingData?.status}</div>
          {error && <div data-testid="progress-error">{error.message}</div>}
        </div>
      )
    );

    mockUploadControlPanel.UploadControlPanel.mockImplementation(
      ({ processingState, onUploadStart, onCancelProcessing }: any) => (
        <div data-testid="upload-control-panel">
          <div data-testid="campaign-upload-section">
            <input
              data-testid="campaign-file-input"
              type="file"
              accept=".xlsx"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) onUploadStart(file, FileType.CAMPAIGN_XLSX);
              }}
            />
            <button
              data-testid="campaign-upload-button"
              disabled={processingState?.campaign_xlsx?.status === ProcessingStatus.PROCESSING}
              onClick={() => {
                const fileInput = document.querySelector('[data-testid="campaign-file-input"]') as HTMLInputElement;
                const file = fileInput?.files?.[0];
                if (file) onUploadStart(file, FileType.CAMPAIGN_XLSX);
              }}
            >
              Upload Campaign XLSX
            </button>
          </div>
          <div data-testid="reporting-upload-section">
            <input
              data-testid="reporting-file-input"
              type="file"
              accept=".csv"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) onUploadStart(file, FileType.REPORTING_CSV);
              }}
            />
            <button
              data-testid="reporting-upload-button"
              disabled={processingState?.reporting_csv?.status === ProcessingStatus.PROCESSING}
              onClick={() => {
                const fileInput = document.querySelector('[data-testid="reporting-file-input"]') as HTMLInputElement;
                const file = fileInput?.files?.[0];
                if (file) onUploadStart(file, FileType.REPORTING_CSV);
              }}
            >
              Upload Reporting CSV
            </button>
          </div>
        </div>
      )
    );

    mockErrorDisplayPanel.ErrorDisplayPanel.mockImplementation(
      ({ errors }: any) => (
        <div data-testid="error-display-panel">
          {errors?.map((error: any, index: number) => (
            <div key={error.error_id} data-testid={`error-item-${index}`}>
              <div data-testid={`error-message-${index}`}>{error.message}</div>
            </div>
          ))}
        </div>
      )
    );
  });

  afterEach(() => {
    console.error = originalError;
  });

  describe('TDD RED Phase - Rendering Tests', () => {
    test('DataUpload component renders without crashing', () => {
      const errors: Error[] = [];
      const onError = (error: Error) => errors.push(error);
      
      render(
        <TestErrorBoundary onError={onError}>
          <DataUpload />
        </TestErrorBoundary>
      );
      
      // This test should FAIL if there are rendering errors
      expect(errors).toHaveLength(0);
      expect(consoleErrors.filter(err => err.includes('Error')).length).toBe(0);
      expect(screen.queryByTestId('error-boundary')).not.toBeInTheDocument();
    });

    test('renders Ant Design Card component correctly', () => {
      render(<DataUpload />);
      
      // Test for Ant Design Card component - should fail if Card doesn't render
      const cardElements = document.querySelectorAll('.ant-card');
      expect(cardElements.length).toBeGreaterThan(0);
      expect(cardElements[0]?.querySelector('.ant-card-body')).toBeInTheDocument();
    });

    test('renders Ant Design Typography components correctly', () => {
      render(<DataUpload />);
      
      // Test Typography Text component
      const textElements = document.querySelectorAll('.ant-typography');
      expect(textElements.length).toBeGreaterThan(0);
      
      // Check for page title
      expect(screen.getByText('Data Upload')).toBeInTheDocument();
    });

    test('no deprecation warnings from Ant Design components', () => {
      render(<DataUpload />);
      
      // Should fail if there are Ant Design deprecation warnings
      const deprecationWarnings = consoleErrors.filter(err => 
        err.includes('deprecated') || err.includes('Warning')
      );
      expect(deprecationWarnings).toHaveLength(0);
    });

    test('component mounts and unmounts cleanly', () => {
      const { unmount } = render(<DataUpload />);
      
      // Should fail if component doesn't mount properly
      expect(screen.getByText('Data Upload')).toBeInTheDocument();
      
      // Should fail if component doesn't unmount cleanly
      expect(() => unmount()).not.toThrow();
    });
  });

  describe('Processing Pipeline Integration', () => {
    test('renders page with processing pipeline components', () => {
      render(<DataUpload />);
      
      expect(screen.getByRole('heading', { name: /data upload/i })).toBeInTheDocument();
      expect(screen.getByText(/upload your campaign xlsx and reporting csv files/i)).toBeInTheDocument();
      expect(screen.getByTestId('upload-control-panel')).toBeInTheDocument();
    });

    test('displays file format information correctly', () => {
      render(<DataUpload />);
      
      expect(screen.getByText(/campaign xlsx/i)).toBeInTheDocument();
      expect(screen.getByText(/reporting csv/i)).toBeInTheDocument();
      expect(screen.getByText(/250mb/i)).toBeInTheDocument();
    });

    test('shows processing status summary', () => {
      render(<DataUpload />);
      
      expect(screen.getByText('Processing Status Overview')).toBeInTheDocument();
      expect(screen.getByText('Campaign XLSX:')).toBeInTheDocument();
      expect(screen.getByText('Reporting CSV:')).toBeInTheDocument();
      expect(screen.getByText('Processing Errors:')).toBeInTheDocument();
    });

    test('displays correct initial processing status', () => {
      render(<DataUpload />);
      
      // Should show "Ready" status for both file types initially
      const statusElements = screen.getAllByText('Ready');
      expect(statusElements.length).toBeGreaterThanOrEqual(2);
    });
  });

  describe('Upload Control Panel Integration', () => {
    test('renders upload control panel with both file type sections', () => {
      render(<DataUpload />);
      
      expect(screen.getByTestId('upload-control-panel')).toBeInTheDocument();
      expect(screen.getByTestId('campaign-upload-section')).toBeInTheDocument();
      expect(screen.getByTestId('reporting-upload-section')).toBeInTheDocument();
    });

    test('shows file inputs for both file types', () => {
      render(<DataUpload />);
      
      const campaignFileInput = screen.getByTestId('campaign-file-input');
      const reportingFileInput = screen.getByTestId('reporting-file-input');
      
      expect(campaignFileInput).toBeInTheDocument();
      expect(campaignFileInput).toHaveAttribute('accept', '.xlsx');
      
      expect(reportingFileInput).toBeInTheDocument();
      expect(reportingFileInput).toHaveAttribute('accept', '.csv');
    });

    test('shows upload buttons for both file types', () => {
      render(<DataUpload />);
      
      expect(screen.getByTestId('campaign-upload-button')).toBeInTheDocument();
      expect(screen.getByTestId('reporting-upload-button')).toBeInTheDocument();
      expect(screen.getByText('Upload Campaign XLSX')).toBeInTheDocument();
      expect(screen.getByText('Upload Reporting CSV')).toBeInTheDocument();
    });

    test('calls onUploadStart when file is selected', async () => {
      render(<DataUpload />);
      
      const campaignFile = new File(['campaign data'], 'campaign.xlsx', {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      });
      
      const fileInput = screen.getByTestId('campaign-file-input');
      fireEvent.change(fileInput, { target: { files: [campaignFile] } });
      
      expect(mockProcessingStatusHook.startProcessing).toHaveBeenCalledWith(
        campaignFile,
        ProcessingFileType.CAMPAIGN_XLSX
      );
    });
  });

  describe('Processing Progress Integration', () => {
    test('shows progress indicator when processing is active', () => {
      const progressData = {
        batch_id: 'batch-123',
        stage: ProcessingStage.VALIDATE,
        progress: 50,
        status: ProcessingStatus.PROCESSING,
        file_type: FileType.CAMPAIGN_XLSX,
        started_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      };

      mockProcessingStatusHook.currentProgress = progressData;
      mockUseProcessingStatus.useProcessingStatus.mockReturnValue(mockProcessingStatusHook);

      render(<DataUpload />);

      expect(screen.getByTestId('processing-progress-indicator')).toBeInTheDocument();
      expect(screen.getByTestId('progress-stage')).toHaveTextContent('validate');
      expect(screen.getByTestId('progress-percent')).toHaveTextContent('50%');
    });

    test('hides progress indicator when not processing', () => {
      // Default state has no current progress
      render(<DataUpload />);

      expect(screen.queryByTestId('processing-progress-indicator')).not.toBeInTheDocument();
    });
  });

  describe('Error Display Integration', () => {
    test('shows error display panel when errors exist', () => {
      const processingError = {
        error_id: 'error-123',
        timestamp: new Date().toISOString(),
        category: ErrorCategory.VALIDATION,
        severity: ErrorSeverity.ERROR,
        code: 'INVALID_FORMAT',
        message: 'Invalid file format detected',
        context: {
          file_type: FileType.CAMPAIGN_XLSX
        }
      };

      mockProcessingStatusHook.errors = [processingError];
      mockProcessingStatusHook.hasErrors = true;
      mockUseProcessingStatus.useProcessingStatus.mockReturnValue(mockProcessingStatusHook);

      render(<DataUpload />);

      expect(screen.getByTestId('error-display-panel')).toBeInTheDocument();
      expect(screen.getByTestId('error-item-0')).toBeInTheDocument();
      expect(screen.getByTestId('error-message-0')).toHaveTextContent('Invalid file format detected');
    });

    test('hides error display panel when no errors exist', () => {
      // Default state has no errors
      render(<DataUpload />);

      expect(screen.queryByTestId('error-display-panel')).not.toBeInTheDocument();
    });
  });

  describe('Success State Integration', () => {
    test('shows success message when processing completes', () => {
      const processingState: ProcessingState = {
        campaign_xlsx: {
          batch_id: 'batch-123',
          stage: ProcessingStage.COMPLETE,
          progress: 100,
          status: ProcessingStatus.COMPLETED,
          file_type: FileType.CAMPAIGN_XLSX,
          started_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        },
        reporting_csv: null,
        errors: [],
        last_updated: new Date().toISOString()
      };

      mockProcessingStatusHook.processingState = processingState;
      mockUseProcessingStatus.useProcessingStatus.mockReturnValue(mockProcessingStatusHook);

      render(<DataUpload />);

      expect(screen.getByTestId('processing-success-message')).toBeInTheDocument();
      expect(screen.getByText('Processing Completed Successfully')).toBeInTheDocument();
    });

    test('allows dismissing success message', async () => {
      const processingState: ProcessingState = {
        campaign_xlsx: {
          batch_id: 'batch-123',
          stage: ProcessingStage.COMPLETE,
          progress: 100,
          status: ProcessingStatus.COMPLETED,
          file_type: FileType.CAMPAIGN_XLSX,
          started_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        },
        reporting_csv: null,
        errors: [],
        last_updated: new Date().toISOString()
      };

      mockProcessingStatusHook.processingState = processingState;
      mockUseProcessingStatus.useProcessingStatus.mockReturnValue(mockProcessingStatusHook);

      render(<DataUpload />);

      const dismissButton = screen.getByText('Dismiss');
      fireEvent.click(dismissButton);

      // Should not throw errors when clicking dismiss
      expect(dismissButton).toBeInTheDocument();
    });
  });

  describe('Processing Status Summary', () => {
    test('shows correct status for different processing states', () => {
      const processingState: ProcessingState = {
        campaign_xlsx: {
          batch_id: 'batch-123',
          stage: ProcessingStage.VALIDATE,
          progress: 50,
          status: ProcessingStatus.PROCESSING,
          file_type: FileType.CAMPAIGN_XLSX,
          started_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        },
        reporting_csv: {
          batch_id: 'batch-456',
          stage: ProcessingStage.COMPLETE,
          progress: 100,
          status: ProcessingStatus.COMPLETED,
          file_type: FileType.REPORTING_CSV,
          started_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        },
        errors: [],
        last_updated: new Date().toISOString()
      };

      mockProcessingStatusHook.processingState = processingState;
      mockUseProcessingStatus.useProcessingStatus.mockReturnValue(mockProcessingStatusHook);

      render(<DataUpload />);

      expect(screen.getByText('Processing')).toBeInTheDocument();
      expect(screen.getByText('Completed')).toBeInTheDocument();
    });

    test('displays error count correctly', () => {
      const processingError = {
        error_id: 'error-123',
        timestamp: new Date().toISOString(),
        category: ErrorCategory.VALIDATION,
        severity: ErrorSeverity.ERROR,
        code: 'INVALID_FORMAT',
        message: 'Invalid file format detected',
        context: {
          file_type: FileType.CAMPAIGN_XLSX
        }
      };

      mockProcessingStatusHook.errors = [processingError];
      mockProcessingStatusHook.hasErrors = true;
      mockUseProcessingStatus.useProcessingStatus.mockReturnValue(mockProcessingStatusHook);

      render(<DataUpload />);

      expect(screen.getByText('1 error')).toBeInTheDocument();
    });

    test('shows last updated timestamp', () => {
      render(<DataUpload />);

      expect(screen.getByText('Last Updated:')).toBeInTheDocument();
      // Should show some form of timestamp
      const timestampElements = document.querySelectorAll('[style*="font-size: 12px"]');
      expect(timestampElements.length).toBeGreaterThan(0);
    });
  });

  describe('Accessibility', () => {
    test('has proper ARIA labels for status announcements', () => {
      render(<DataUpload />);
      
      const statusAnnouncer = screen.getByTestId('processing-status-announcer');
      expect(statusAnnouncer).toHaveAttribute('aria-live', 'polite');
      expect(statusAnnouncer).toHaveAttribute('aria-atomic', 'true');
    });

    test('maintains screen reader friendly structure', () => {
      render(<DataUpload />);
      
      // Should have proper heading structure
      expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Data Upload');
      
      // Should have accessible status announcer
      const statusAnnouncer = screen.getByTestId('processing-status-announcer');
      expect(statusAnnouncer).toBeInTheDocument();
    });
  });

  describe('File Format Information', () => {
    test('displays supported file formats and size limits', () => {
      render(<DataUpload />);
      
      expect(screen.getByText('Supported File Formats')).toBeInTheDocument();
      expect(screen.getByText(/excel format \(\.xlsx\) up to 250mb/i)).toBeInTheDocument();
      expect(screen.getByText(/comma-separated values \(\.csv\) up to 250mb/i)).toBeInTheDocument();
    });

    test('shows processing information', () => {
      render(<DataUpload />);
      
      expect(screen.getByText('Processing Information')).toBeInTheDocument();
      expect(screen.getByText(/files are processed through validation, parsing, and classification stages/i)).toBeInTheDocument();
    });
  });
});