import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import DataUpload from '../DataUpload';
import * as uploadService from '../../services/uploadService';
import { ProcessingStatusService } from '../../services/processingStatusService';
import {
  ProcessingState,
  ProcessingStatus,
  ProcessingStage,
  FileType,
  ProcessingFileType,
  ErrorCategory,
  ErrorSeverity,
  ProcessingProgress,
  ProcessingError
} from '../../types/processing';

// Mock the upload service and processing components
jest.mock('../../services/uploadService');
jest.mock('../../services/processingStatusService');
jest.mock('../../hooks/useProcessingStatus');
jest.mock('../../components/ProcessingProgressIndicator');
jest.mock('../../components/UploadControlPanel');
jest.mock('../../components/ErrorDisplayPanel');

const mockedUploadService = uploadService as jest.Mocked<typeof uploadService>;
const mockedProcessingStatusService = ProcessingStatusService as jest.MockedClass<typeof ProcessingStatusService>;

// Mock implementations for processing pipeline components
const mockUseProcessingStatus = require('../../hooks/useProcessingStatus');
const mockProcessingProgressIndicator = require('../../components/ProcessingProgressIndicator');
const mockUploadControlPanel = require('../../components/UploadControlPanel');
const mockErrorDisplayPanel = require('../../components/ErrorDisplayPanel');

describe('DataUpload Processing Pipeline Integration', () => {
  let mockProcessingStatusHook: any;
  let mockProcessingService: any;

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Setup default successful file validation
    mockedUploadService.validateFile.mockReturnValue({
      isValid: true,
      errors: []
    });

    // Mock processing service instance
    mockProcessingService = {
      startPolling: jest.fn(),
      stopPolling: jest.fn(),
      cancelProcessing: jest.fn(),
      cleanup: jest.fn()
    };
    mockedProcessingStatusService.mockImplementation(() => mockProcessingService);

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
            {processingState?.campaign_xlsx?.status === ProcessingStatus.PROCESSING && (
              <button
                data-testid="campaign-cancel-button"
                onClick={() => onCancelProcessing(FileType.CAMPAIGN_XLSX)}
              >
                Cancel Campaign
              </button>
            )}
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
            {processingState?.reporting_csv?.status === ProcessingStatus.PROCESSING && (
              <button
                data-testid="reporting-cancel-button"
                onClick={() => onCancelProcessing(FileType.REPORTING_CSV)}
              >
                Cancel Reporting
              </button>
            )}
          </div>
        </div>
      )
    );

    mockErrorDisplayPanel.ErrorDisplayPanel.mockImplementation(
      ({ errors, onErrorAction }: any) => (
        <div data-testid="error-display-panel">
          {errors?.map((error: ProcessingError, index: number) => (
            <div key={error.error_id} data-testid={`error-item-${index}`}>
              <div data-testid={`error-message-${index}`}>{error.message}</div>
              <div data-testid={`error-category-${index}`}>{error.category}</div>
              <div data-testid={`error-severity-${index}`}>{error.severity}</div>
              <button
                data-testid={`error-action-${index}`}
                onClick={() => onErrorAction?.('resolve', error.error_id)}
              >
                Resolve Error
              </button>
            </div>
          ))}
        </div>
      )
    );
  });

  describe('Processing Pipeline Integration - File Type Detection', () => {
    test('should detect and route Campaign XLSX files correctly', async () => {
      render(<DataUpload />);

      const campaignFile = new File(['campaign data'], 'campaign.xlsx', {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      });

      const fileInput = screen.getByTestId('campaign-file-input');
      await userEvent.upload(fileInput, campaignFile);

      expect(mockProcessingStatusHook.startProcessing).toHaveBeenCalledWith(
        campaignFile,
        ProcessingFileType.CAMPAIGN_XLSX
      );
    });

    test('should detect and route Reporting CSV files correctly', async () => {
      render(<DataUpload />);

      const reportingFile = new File(['reporting data'], 'reporting.csv', {
        type: 'text/csv'
      });

      const fileInput = screen.getByTestId('reporting-file-input');
      await userEvent.upload(fileInput, reportingFile);

      expect(mockProcessingStatusHook.startProcessing).toHaveBeenCalledWith(
        reportingFile,
        ProcessingFileType.REPORTING_CSV
      );
    });

    test('should validate file size limit of 250MB', async () => {
      mockedUploadService.validateFile.mockReturnValue({
        isValid: false,
        errors: ['File size exceeds 250MB limit']
      });

      render(<DataUpload />);

      // Should show validation error for oversized files
      expect(screen.getByText(/file size exceeds 250mb limit/i)).toBeInTheDocument();
    });
  });

  describe('Processing Pipeline Integration - Upload Control Panel', () => {
    test('should render UploadControlPanel with processing state', () => {
      const processingState: ProcessingState = {
        campaign_xlsx: {
          batch_id: 'batch-123',
          stage: ProcessingStage.PARSE,
          progress: 25,
          status: ProcessingStatus.PROCESSING,
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

      expect(screen.getByTestId('upload-control-panel')).toBeInTheDocument();
      expect(screen.getByTestId('campaign-upload-section')).toBeInTheDocument();
      expect(screen.getByTestId('reporting-upload-section')).toBeInTheDocument();
    });

    test('should disable upload buttons during processing', () => {
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
        reporting_csv: null,
        errors: [],
        last_updated: new Date().toISOString()
      };

      mockProcessingStatusHook.processingState = processingState;
      mockProcessingStatusHook.isProcessing = true;
      mockUseProcessingStatus.useProcessingStatus.mockReturnValue(mockProcessingStatusHook);

      render(<DataUpload />);

      const campaignUploadButton = screen.getByTestId('campaign-upload-button');
      expect(campaignUploadButton).toBeDisabled();

      const reportingUploadButton = screen.getByTestId('reporting-upload-button');
      expect(reportingUploadButton).not.toBeDisabled(); // Different file type should not be blocked
    });

    test('should show cancel buttons during processing', () => {
      const processingState: ProcessingState = {
        campaign_xlsx: {
          batch_id: 'batch-123',
          stage: ProcessingStage.CLASSIFY,
          progress: 75,
          status: ProcessingStatus.PROCESSING,
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

      expect(screen.getByTestId('campaign-cancel-button')).toBeInTheDocument();
      expect(screen.queryByTestId('reporting-cancel-button')).not.toBeInTheDocument();
    });
  });

  describe('Processing Pipeline Integration - Progress Visualization', () => {
    test('should show ProcessingProgressIndicator during processing', () => {
      const progressData: ProcessingProgress = {
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
      expect(screen.getByTestId('progress-status')).toHaveTextContent('processing');
    });

    test('should update progress through all stages', async () => {
      const { rerender } = render(<DataUpload />);

      // Stage 1: Parse (25%)
      let progressData: ProcessingProgress = {
        batch_id: 'batch-123',
        stage: ProcessingStage.PARSE,
        progress: 25,
        status: ProcessingStatus.PROCESSING,
        file_type: FileType.CAMPAIGN_XLSX,
        started_at: new Date().toISOString(),
        updated_at: new Date().toISOString()
      };

      mockProcessingStatusHook.currentProgress = progressData;
      mockUseProcessingStatus.useProcessingStatus.mockReturnValue(mockProcessingStatusHook);
      rerender(<DataUpload />);

      expect(screen.getByTestId('progress-stage')).toHaveTextContent('parse');
      expect(screen.getByTestId('progress-percent')).toHaveTextContent('25%');

      // Stage 2: Validate (50%)
      progressData = {
        ...progressData,
        stage: ProcessingStage.VALIDATE,
        progress: 50
      };
      mockProcessingStatusHook.currentProgress = progressData;
      rerender(<DataUpload />);

      expect(screen.getByTestId('progress-stage')).toHaveTextContent('validate');
      expect(screen.getByTestId('progress-percent')).toHaveTextContent('50%');

      // Stage 3: Classify (75%)
      progressData = {
        ...progressData,
        stage: ProcessingStage.CLASSIFY,
        progress: 75
      };
      mockProcessingStatusHook.currentProgress = progressData;
      rerender(<DataUpload />);

      expect(screen.getByTestId('progress-stage')).toHaveTextContent('classify');
      expect(screen.getByTestId('progress-percent')).toHaveTextContent('75%');

      // Stage 4: Complete (100%)
      progressData = {
        ...progressData,
        stage: ProcessingStage.COMPLETE,
        progress: 100,
        status: ProcessingStatus.COMPLETED
      };
      mockProcessingStatusHook.currentProgress = progressData;
      rerender(<DataUpload />);

      expect(screen.getByTestId('progress-stage')).toHaveTextContent('complete');
      expect(screen.getByTestId('progress-percent')).toHaveTextContent('100%');
      expect(screen.getByTestId('progress-status')).toHaveTextContent('completed');
    });
  });

  describe('Processing Pipeline Integration - Error Handling', () => {
    test('should display ErrorDisplayPanel when processing errors occur', () => {
      const processingError: ProcessingError = {
        error_id: 'error-123',
        timestamp: new Date().toISOString(),
        category: ErrorCategory.VALIDATION,
        severity: ErrorSeverity.ERROR,
        code: 'INVALID_FORMAT',
        message: 'Invalid file format detected',
        context: {
          file_type: FileType.CAMPAIGN_XLSX,
          row_number: 5,
          column_name: 'campaign_id'
        }
      };

      mockProcessingStatusHook.errors = [processingError];
      mockProcessingStatusHook.hasErrors = true;
      mockUseProcessingStatus.useProcessingStatus.mockReturnValue(mockProcessingStatusHook);

      render(<DataUpload />);

      expect(screen.getByTestId('error-display-panel')).toBeInTheDocument();
      expect(screen.getByTestId('error-item-0')).toBeInTheDocument();
      expect(screen.getByTestId('error-message-0')).toHaveTextContent('Invalid file format detected');
      expect(screen.getByTestId('error-category-0')).toHaveTextContent('validation');
      expect(screen.getByTestId('error-severity-0')).toHaveTextContent('error');
    });

    test('should handle time-ordered error display', () => {
      const error1: ProcessingError = {
        error_id: 'error-1',
        timestamp: '2025-09-09T10:00:00Z',
        category: ErrorCategory.PARSING,
        severity: ErrorSeverity.ERROR,
        code: 'PARSE_FAILED',
        message: 'Failed to parse file header',
        context: { file_type: FileType.CAMPAIGN_XLSX }
      };

      const error2: ProcessingError = {
        error_id: 'error-2',
        timestamp: '2025-09-09T10:01:00Z',
        category: ErrorCategory.VALIDATION,
        severity: ErrorSeverity.WARNING,
        code: 'MISSING_FIELD',
        message: 'Missing required field',
        context: { file_type: FileType.CAMPAIGN_XLSX, column_name: 'budget' }
      };

      mockProcessingStatusHook.errors = [error1, error2]; // Should be time-ordered
      mockProcessingStatusHook.hasErrors = true;
      mockUseProcessingStatus.useProcessingStatus.mockReturnValue(mockProcessingStatusHook);

      render(<DataUpload />);

      expect(screen.getByTestId('error-item-0')).toBeInTheDocument();
      expect(screen.getByTestId('error-item-1')).toBeInTheDocument();
      
      // First error should be the older one
      expect(screen.getByTestId('error-message-0')).toHaveTextContent('Failed to parse file header');
      expect(screen.getByTestId('error-message-1')).toHaveTextContent('Missing required field');
    });

    test('should provide error action handling', async () => {
      const processingError: ProcessingError = {
        error_id: 'error-123',
        timestamp: new Date().toISOString(),
        category: ErrorCategory.SYSTEM,
        severity: ErrorSeverity.ERROR,
        code: 'SYSTEM_ERROR',
        message: 'Database connection failed',
        context: { file_type: FileType.REPORTING_CSV }
      };

      mockProcessingStatusHook.errors = [processingError];
      mockProcessingStatusHook.hasErrors = true;
      mockUseProcessingStatus.useProcessingStatus.mockReturnValue(mockProcessingStatusHook);

      render(<DataUpload />);

      const errorActionButton = screen.getByTestId('error-action-0');
      await userEvent.click(errorActionButton);

      // Should call error action handler
      expect(mockErrorDisplayPanel.ErrorDisplayPanel).toHaveBeenCalledWith(
        expect.objectContaining({
          onErrorAction: expect.any(Function)
        }),
        expect.anything()
      );
    });
  });

  describe('Processing Pipeline Integration - Complete Workflow', () => {
    test('should handle complete Campaign XLSX processing workflow', async () => {
      const user = userEvent.setup();
      
      render(<DataUpload />);

      // Step 1: File selection
      const campaignFile = new File(['campaign data'], 'campaign.xlsx', {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      });

      const fileInput = screen.getByTestId('campaign-file-input');
      await user.upload(fileInput, campaignFile);

      // Step 2: Start processing
      const uploadButton = screen.getByTestId('campaign-upload-button');
      await user.click(uploadButton);

      expect(mockProcessingStatusHook.startProcessing).toHaveBeenCalledWith(
        campaignFile,
        ProcessingFileType.CAMPAIGN_XLSX
      );

      // Step 3: Simulate processing state updates
      const processingStates = [
        {
          stage: ProcessingStage.PARSE,
          progress: 25,
          status: ProcessingStatus.PROCESSING
        },
        {
          stage: ProcessingStage.VALIDATE,
          progress: 50,
          status: ProcessingStatus.PROCESSING
        },
        {
          stage: ProcessingStage.CLASSIFY,
          progress: 75,
          status: ProcessingStatus.PROCESSING
        },
        {
          stage: ProcessingStage.COMPLETE,
          progress: 100,
          status: ProcessingStatus.COMPLETED
        }
      ];

      // Verify each processing stage
      for (const state of processingStates) {
        const currentProgress: ProcessingProgress = {
          batch_id: 'batch-123',
          stage: state.stage,
          progress: state.progress as 25 | 50 | 75 | 100,
          status: state.status,
          file_type: FileType.CAMPAIGN_XLSX,
          started_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        };

        mockProcessingStatusHook.currentProgress = currentProgress;
        mockProcessingStatusHook.isProcessing = state.status === ProcessingStatus.PROCESSING;
        
        // Force re-render to update component
        await act(async () => {
          mockUseProcessingStatus.useProcessingStatus.mockReturnValue(mockProcessingStatusHook);
        });
      }
    });

    test('should handle concurrent Campaign and Reporting processing', async () => {
      const user = userEvent.setup();
      
      render(<DataUpload />);

      // Upload both file types
      const campaignFile = new File(['campaign data'], 'campaign.xlsx', {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      });
      const reportingFile = new File(['reporting data'], 'reporting.csv', {
        type: 'text/csv'
      });

      const campaignFileInput = screen.getByTestId('campaign-file-input');
      const reportingFileInput = screen.getByTestId('reporting-file-input');

      await user.upload(campaignFileInput, campaignFile);
      await user.upload(reportingFileInput, reportingFile);

      const campaignUploadButton = screen.getByTestId('campaign-upload-button');
      const reportingUploadButton = screen.getByTestId('reporting-upload-button');

      await user.click(campaignUploadButton);
      await user.click(reportingUploadButton);

      // Both processing calls should be made
      expect(mockProcessingStatusHook.startProcessing).toHaveBeenCalledWith(
        campaignFile,
        ProcessingFileType.CAMPAIGN_XLSX
      );
      expect(mockProcessingStatusHook.startProcessing).toHaveBeenCalledWith(
        reportingFile,
        ProcessingFileType.REPORTING_CSV
      );
    });

    test('should handle processing cancellation', async () => {
      const user = userEvent.setup();
      
      // Setup processing state
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
        reporting_csv: null,
        errors: [],
        last_updated: new Date().toISOString()
      };

      mockProcessingStatusHook.processingState = processingState;
      mockProcessingStatusHook.isProcessing = true;
      mockUseProcessingStatus.useProcessingStatus.mockReturnValue(mockProcessingStatusHook);

      render(<DataUpload />);

      const cancelButton = screen.getByTestId('campaign-cancel-button');
      await user.click(cancelButton);

      expect(mockProcessingStatusHook.cancelProcessing).toHaveBeenCalledWith(
        ProcessingFileType.CAMPAIGN_XLSX
      );
    });
  });

  describe('Processing Pipeline Integration - Accessibility', () => {
    test('should maintain accessibility features during processing', () => {
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
        reporting_csv: null,
        errors: [],
        last_updated: new Date().toISOString()
      };

      mockProcessingStatusHook.processingState = processingState;
      mockProcessingStatusHook.currentProgress = processingState.campaign_xlsx;
      mockUseProcessingStatus.useProcessingStatus.mockReturnValue(mockProcessingStatusHook);

      render(<DataUpload />);

      // Verify components maintain accessibility
      expect(screen.getByTestId('upload-control-panel')).toBeInTheDocument();
      expect(screen.getByTestId('processing-progress-indicator')).toBeInTheDocument();
      
      // File inputs should have proper attributes
      const campaignFileInput = screen.getByTestId('campaign-file-input');
      expect(campaignFileInput).toHaveAttribute('type', 'file');
      expect(campaignFileInput).toHaveAttribute('accept', '.xlsx');
      
      const reportingFileInput = screen.getByTestId('reporting-file-input');
      expect(reportingFileInput).toHaveAttribute('type', 'file');
      expect(reportingFileInput).toHaveAttribute('accept', '.csv');
    });
  });
});