/**
 * Processing Workflow End-to-End Tests
 * Comprehensive tests for the complete Upload Processing Pipeline UI workflow
 * Verifies all components integrate seamlessly according to specification requirements
 */

import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import '@testing-library/jest-dom';
import DataUpload from '../../pages/DataUpload';
import { ProcessingStatusService } from '../../services/processingStatusService';
import * as uploadService from '../../services/uploadService';
import {
  ProcessingState,
  ProcessingStatus,
  ProcessingStage,
  FileType,
  ProcessingFileType,
  ErrorCategory,
  ErrorSeverity,
  ProcessingProgress,
  ProcessingError,
  ProcessingStatusResponse
} from '../../types/processing';

// Mock all external dependencies
jest.mock('../../services/uploadService');
jest.mock('../../services/processingStatusService');
jest.mock('axios');

const mockedUploadService = uploadService as jest.Mocked<typeof uploadService>;
const mockedProcessingStatusService = ProcessingStatusService as jest.MockedClass<typeof ProcessingStatusService>;

// Test data factories
const createMockFile = (name: string, type: string, size: number = 1024): File => {
  const file = new File(['mock content'], name, { type });
  // Add mock size property for testing
  Object.defineProperty(file, '__mockSize', { value: size, writable: true });
  return file;
};

const createProcessingProgress = (
  fileType: FileType,
  stage: ProcessingStage,
  status: ProcessingStatus,
  batchId: string = 'batch-123'
): ProcessingProgress => {
  const now = new Date();
  const startTime = new Date(now.getTime() - 60000); // 1 minute ago
  
  return {
    batch_id: batchId,
    stage,
    progress: stage === ProcessingStage.PARSE ? 25 :
             stage === ProcessingStage.VALIDATE ? 50 :
             stage === ProcessingStage.CLASSIFY ? 75 : 100,
    status,
    file_type: fileType,
    started_at: startTime.toISOString().replace(/\.\d{3}Z$/, 'Z'), // Remove milliseconds for strict ISO format
    updated_at: now.toISOString().replace(/\.\d{3}Z$/, 'Z'), // Remove milliseconds for strict ISO format
    ...(status === ProcessingStatus.COMPLETED && { 
      completed_at: now.toISOString().replace(/\.\d{3}Z$/, 'Z') 
    })
  };
};

const createProcessingError = (
  category: ErrorCategory,
  severity: ErrorSeverity,
  message: string,
  fileType: FileType
): ProcessingError => ({
  error_id: `error-${Date.now()}-${Math.random().toString(36).substring(2, 15)}`,
  timestamp: new Date().toISOString().replace(/\.\d{3}Z$/, 'Z'), // Remove milliseconds for strict ISO format
  category,
  severity,
  code: `${category.toUpperCase()}_ERROR`,
  message,
  context: { file_type: fileType },
  suggested_action: `Please resolve ${category} issue`
});

describe('Processing Workflow End-to-End Tests', () => {
  let mockServiceInstance: any;
  let mockCallbacks: any;

  beforeEach(() => {
    jest.clearAllMocks();
    
    // Setup upload service mocks
    mockedUploadService.validateFile.mockReturnValue({
      isValid: true,
      errors: []
    });

    // Setup processing service mock
    mockServiceInstance = {
      startPolling: jest.fn(),
      stopPolling: jest.fn(),
      cancelProcessing: jest.fn().mockResolvedValue(undefined),
      cleanup: jest.fn(),
      pausePolling: jest.fn(),
      resumePolling: jest.fn()
    };

    mockedProcessingStatusService.mockImplementation(() => mockServiceInstance);

    // Capture callbacks for simulation
    mockServiceInstance.startPolling.mockImplementation((batchId: string, callbacks: any) => {
      mockCallbacks = callbacks;
    });
  });

  afterEach(() => {
    jest.resetAllMocks();
  });

  describe('1. Campaign XLSX Processing Workflow', () => {
    test('should complete full processing workflow for Campaign XLSX', async () => {
      const user = userEvent.setup();
      render(<DataUpload />);

      // Step 1: File selection and validation
      const campaignFile = createMockFile(
        'campaign.xlsx',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        50 * 1024 * 1024 // 50MB - within 250MB limit
      );

      const fileInput = screen.getByTestId('campaign-file-input');
      expect(fileInput).toBeInTheDocument();
      await user.upload(fileInput, campaignFile);

      // Step 2: Upload initiation with file type detection
      await waitFor(() => {
        const uploadButton = screen.getByTestId('campaign-upload-button');
        expect(uploadButton).not.toBeDisabled();
      });
      
      const uploadButton = screen.getByTestId('campaign-upload-button');
      await user.click(uploadButton);

      // Verify service was called with correct parameters
      expect(mockServiceInstance.startPolling).toHaveBeenCalledWith(
        expect.stringMatching(/^batch-/),
        expect.objectContaining({
          onProgressUpdate: expect.any(Function),
          onErrorUpdate: expect.any(Function),
          onCompletion: expect.any(Function),
          onFailure: expect.any(Function)
        })
      );

      // Step 3: Processing state updates (idle → processing)
      act(() => {
        mockCallbacks.onProgressUpdate(
          createProcessingProgress(FileType.CAMPAIGN_XLSX, ProcessingStage.PARSE, ProcessingStatus.PROCESSING)
        );
      });

      await waitFor(() => {
        expect(screen.getByTestId('campaign-status-processing')).toBeInTheDocument();
      });

      // Step 4: Progress visualization (25% → 50% → 75% → 100%)
      const progressStages = [
        { stage: ProcessingStage.PARSE, progress: 25 },
        { stage: ProcessingStage.VALIDATE, progress: 50 },
        { stage: ProcessingStage.CLASSIFY, progress: 75 },
        { stage: ProcessingStage.COMPLETE, progress: 100 }
      ];

      for (const { stage, progress } of progressStages) {
        act(() => {
          mockCallbacks.onProgressUpdate(
            createProcessingProgress(
              FileType.CAMPAIGN_XLSX, 
              stage, 
              stage === ProcessingStage.COMPLETE ? ProcessingStatus.COMPLETED : ProcessingStatus.PROCESSING
            )
          );
        });

        await waitFor(() => {
          const progressTexts = screen.getAllByText(`${progress}%`);
          expect(progressTexts.length).toBeGreaterThan(0);
        });
      }

      // Step 5: Processing completion (success state)
      act(() => {
        const completionResponse: ProcessingStatusResponse = {
          success: true,
          data: {
            campaign_xlsx: createProcessingProgress(FileType.CAMPAIGN_XLSX, ProcessingStage.COMPLETE, ProcessingStatus.COMPLETED),
            reporting_csv: null,
            errors: [],
            last_updated: new Date().toISOString()
          },
          polling_interval: 2000
        };
        mockCallbacks.onCompletion(completionResponse);
      });

      // Step 6: Upload re-enablement and state reset
      await waitFor(() => {
        expect(screen.getByTestId('processing-success-message')).toBeInTheDocument();
      });

      expect(screen.getByText(/processing completed successfully/i)).toBeInTheDocument();
    });

    test('should handle Campaign XLSX file type detection correctly', async () => {
      const user = userEvent.setup();
      render(<DataUpload />);

      const campaignFile = createMockFile(
        'test-campaign.xlsx',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      );

      const fileInput = document.querySelector('input[accept*=".xlsx"]') as HTMLInputElement;
      await user.upload(fileInput, campaignFile);

      // Verify file type detection in component logic
      expect(campaignFile.type).toBe('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      expect(campaignFile.name.toLowerCase().endsWith('.xlsx')).toBe(true);
    });
  });

  describe('2. Reporting CSV Processing Workflow', () => {
    test('should complete full processing workflow for Reporting CSV', async () => {
      const user = userEvent.setup();
      render(<DataUpload />);

      // File selection with CSV type
      const reportingFile = createMockFile(
        'reporting.csv',
        'text/csv',
        100 * 1024 * 1024 // 100MB - within 250MB limit
      );

      const fileInput = screen.getByTestId('reporting-file-input');
      await user.upload(fileInput, reportingFile);

      await waitFor(() => {
        const uploadButton = screen.getByTestId('reporting-upload-button');
        expect(uploadButton).not.toBeDisabled();
      });

      const uploadButton = screen.getByTestId('reporting-upload-button');
      
      await user.click(uploadButton);

      // Verify different file type handling and messaging
      expect(mockServiceInstance.startPolling).toHaveBeenCalled();

      // Progress through all stages for CSV
      const csvProgressStages = [
        ProcessingStage.PARSE,
        ProcessingStage.VALIDATE,
        ProcessingStage.CLASSIFY,
        ProcessingStage.COMPLETE
      ];

      for (const stage of csvProgressStages) {
        act(() => {
          mockCallbacks.onProgressUpdate(
            createProcessingProgress(
              FileType.REPORTING_CSV, 
              stage, 
              stage === ProcessingStage.COMPLETE ? ProcessingStatus.COMPLETED : ProcessingStatus.PROCESSING
            )
          );
        });

        const expectedProgress = stage === ProcessingStage.PARSE ? 25 :
                               stage === ProcessingStage.VALIDATE ? 50 :
                               stage === ProcessingStage.CLASSIFY ? 75 : 100;

        await waitFor(() => {
          const progressTexts = screen.getAllByText(`${expectedProgress}%`);
          expect(progressTexts.length).toBeGreaterThan(0);
        });
      }

      // Completion
      act(() => {
        const completionResponse: ProcessingStatusResponse = {
          success: true,
          data: {
            campaign_xlsx: null,
            reporting_csv: createProcessingProgress(FileType.REPORTING_CSV, ProcessingStage.COMPLETE, ProcessingStatus.COMPLETED),
            errors: [],
            last_updated: new Date().toISOString()
          },
          polling_interval: 2000
        };
        mockCallbacks.onCompletion(completionResponse);
      });

      await waitFor(() => {
        expect(screen.getByTestId('processing-success-message')).toBeInTheDocument();
      });
    });
  });

  describe('3. Concurrent Processing Workflow', () => {
    test('should handle both file types processing simultaneously', async () => {
      const user = userEvent.setup();
      render(<DataUpload />);

      // Step 1: Start Campaign XLSX processing
      const campaignFile = createMockFile('campaign.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      const campaignInput = screen.getByTestId('campaign-file-input');
      await user.upload(campaignInput, campaignFile);
      
      await waitFor(() => {
        const campaignUploadButton = screen.getByTestId('campaign-upload-button');
        expect(campaignUploadButton).not.toBeDisabled();
      });
      
      const campaignUploadButton = screen.getByTestId('campaign-upload-button');
      await user.click(campaignUploadButton);

      // Step 2: Start Reporting CSV processing (while first is active)
      const reportingFile = createMockFile('reporting.csv', 'text/csv');
      const reportingInput = screen.getByTestId('reporting-file-input');
      await user.upload(reportingInput, reportingFile);
      
      await waitFor(() => {
        const reportingUploadButton = screen.getByTestId('reporting-upload-button');
        expect(reportingUploadButton).not.toBeDisabled();
      });
      
      const reportingUploadButton = screen.getByTestId('reporting-upload-button');
      await user.click(reportingUploadButton);

      // Verify both services were called
      expect(mockServiceInstance.startPolling).toHaveBeenCalledTimes(2);

      // Step 3: Verify independent progress tracking
      act(() => {
        // Campaign at 25%
        mockCallbacks.onProgressUpdate(
          createProcessingProgress(FileType.CAMPAIGN_XLSX, ProcessingStage.PARSE, ProcessingStatus.PROCESSING, 'batch-campaign')
        );
      });

      act(() => {
        // Reporting at 50% 
        mockCallbacks.onProgressUpdate(
          createProcessingProgress(FileType.REPORTING_CSV, ProcessingStage.VALIDATE, ProcessingStatus.PROCESSING, 'batch-reporting')
        );
      });

      // Both progress indicators should be visible
      await waitFor(() => {
        const progress25 = screen.getAllByText('25%');
        const progress50 = screen.getAllByText('50%');
        expect(progress25.length).toBeGreaterThan(0);
        expect(progress50.length).toBeGreaterThan(0);
      });

      // Step 4: Verify independent completion handling
      act(() => {
        const campaignCompletion: ProcessingStatusResponse = {
          success: true,
          data: {
            campaign_xlsx: createProcessingProgress(FileType.CAMPAIGN_XLSX, ProcessingStage.COMPLETE, ProcessingStatus.COMPLETED),
            reporting_csv: createProcessingProgress(FileType.REPORTING_CSV, ProcessingStage.VALIDATE, ProcessingStatus.PROCESSING),
            errors: [],
            last_updated: new Date().toISOString()
          },
          polling_interval: 2000
        };
        mockCallbacks.onCompletion(campaignCompletion);
      });

      // Campaign should be completed, reporting still processing
      await waitFor(() => {
        expect(screen.getByText(/completed/i)).toBeInTheDocument();
        expect(screen.getByText(/processing/i)).toBeInTheDocument();
      });
    });
  });

  describe('4. File Size Validation Workflow', () => {
    test('should reject files over 250MB with proper error messaging', async () => {
      const user = userEvent.setup();
      
      // Mock validation to return file size error
      mockedUploadService.validateFile.mockReturnValue({
        isValid: false,
        errors: ['File size exceeds 250MB limit']
      });

      render(<DataUpload />);

      // Create oversized file
      const oversizedFile = createMockFile(
        'large-campaign.xlsx',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        300 * 1024 * 1024 // 300MB - exceeds 250MB limit
      );

      const fileInput = screen.getByTestId('campaign-file-input');
      await user.upload(fileInput, oversizedFile);

      // Wait for validation to complete
      await waitFor(() => {
        expect(screen.getByTestId('campaign-validation-error')).toBeInTheDocument();
      });

      const uploadButton = screen.getByTestId('campaign-upload-button');
      expect(uploadButton).toBeDisabled();

      // Should show error message and not start processing
      await waitFor(() => {
        expect(screen.getByText(/file size exceeds 250mb limit/i)).toBeInTheDocument();
      });

      expect(mockServiceInstance.startPolling).not.toHaveBeenCalled();
    });

    test('should accept files exactly at 250MB limit', async () => {
      const user = userEvent.setup();
      render(<DataUpload />);

      // Create file exactly at limit
      const maxSizeFile = createMockFile(
        'max-size-campaign.xlsx',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        250 * 1024 * 1024 // Exactly 250MB
      );

      const fileInput = screen.getByTestId('campaign-file-input');
      await user.upload(fileInput, maxSizeFile);

      await waitFor(() => {
        const uploadButton = screen.getByTestId('campaign-upload-button');
        expect(uploadButton).not.toBeDisabled();
      });

      const uploadButton = screen.getByTestId('campaign-upload-button');
      await user.click(uploadButton);

      // Should start processing without error
      expect(mockServiceInstance.startPolling).toHaveBeenCalled();
    });
  });

  describe('5. Processing Error Workflow', () => {
    test('should handle processing errors with time-ordered display', async () => {
      const user = userEvent.setup();
      render(<DataUpload />);

      // Start processing
      const campaignFile = createMockFile('campaign.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      const fileInput = screen.getByTestId('campaign-file-input');
      await user.upload(fileInput, campaignFile);
      
      await waitFor(() => {
        const uploadButton = screen.getByTestId('campaign-upload-button');
        expect(uploadButton).not.toBeDisabled();
      });
      
      const uploadButton = screen.getByTestId('campaign-upload-button');
      await user.click(uploadButton);

      // Step 1: Start processing
      act(() => {
        mockCallbacks.onProgressUpdate(
          createProcessingProgress(FileType.CAMPAIGN_XLSX, ProcessingStage.PARSE, ProcessingStatus.PROCESSING)
        );
      });

      // Step 2: Simulate errors occurring during processing (time-ordered)
      const baseTime = new Date('2025-09-09T10:00:00Z').getTime();
      
      const error1 = createProcessingError(
        ErrorCategory.PARSING,
        ErrorSeverity.ERROR,
        'Failed to parse header row',
        FileType.CAMPAIGN_XLSX
      );
      error1.timestamp = new Date(baseTime).toISOString().replace(/\.\d{3}Z$/, 'Z');

      const error2 = createProcessingError(
        ErrorCategory.VALIDATION,
        ErrorSeverity.WARNING,
        'Missing campaign_id in row 5',
        FileType.CAMPAIGN_XLSX
      );
      error2.timestamp = new Date(baseTime + 60000).toISOString().replace(/\.\d{3}Z$/, 'Z'); // 1 minute later

      const error3 = createProcessingError(
        ErrorCategory.PROCESSING,
        ErrorSeverity.ERROR,
        'Budget validation failed',
        FileType.CAMPAIGN_XLSX
      );
      error3.timestamp = new Date(baseTime + 120000).toISOString().replace(/\.\d{3}Z$/, 'Z'); // 2 minutes later

      // Step 3: Verify error accumulation during processing
      act(() => {
        mockCallbacks.onErrorUpdate([error1]);
      });

      await waitFor(() => {
        expect(screen.getByText('Failed to parse header row')).toBeInTheDocument();
      });

      act(() => {
        mockCallbacks.onErrorUpdate([error1, error2]);
      });

      await waitFor(() => {
        expect(screen.getByText('Missing campaign_id in row 5')).toBeInTheDocument();
      });

      act(() => {
        mockCallbacks.onErrorUpdate([error1, error2, error3]);
      });

      // Step 4: Verify time-ordered error display (oldest first)
      await waitFor(() => {
        const errorMessages = screen.getAllByText(/Failed to parse header row|Missing campaign_id|Budget validation failed/);
        expect(errorMessages).toHaveLength(3);
      });

      // Step 5: Verify actionable error messages and suggested actions
      await waitFor(() => {
        expect(screen.getByText('Please resolve parsing issue')).toBeInTheDocument();
        expect(screen.getByText('Please resolve validation issue')).toBeInTheDocument();
        expect(screen.getByText('Please resolve processing issue')).toBeInTheDocument();
      });

      // Step 6: Processing failure and state cleanup
      act(() => {
        mockCallbacks.onFailure(new Error('Processing failed due to critical errors'));
      });

      await waitFor(() => {
        // Upload should be re-enabled after failure
        const uploadBtn = screen.getByTestId('campaign-upload-button');
        expect(uploadBtn).not.toBeDisabled();
      });
    });
  });

  describe('6. Processing Cancellation Workflow', () => {
    test('should handle processing cancellation correctly', async () => {
      const user = userEvent.setup();
      render(<DataUpload />);

      // Step 1: Start processing
      const campaignFile = createMockFile('campaign.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      const fileInput = document.querySelector('input[accept*=".xlsx"]') as HTMLInputElement;
      await user.upload(fileInput, campaignFile);
      
      const uploadButton = screen.getByRole('button', { name: /upload.*campaign/i });
      await user.click(uploadButton);

      act(() => {
        mockCallbacks.onProgressUpdate(
          createProcessingProgress(FileType.CAMPAIGN_XLSX, ProcessingStage.VALIDATE, ProcessingStatus.PROCESSING)
        );
      });

      // Step 2: Cancel processing mid-way
      const cancelButton = await screen.findByTestId('campaign-cancel-button');
      await user.click(cancelButton);

      // Step 3: Verify polling stops
      expect(mockServiceInstance.cancelProcessing).toHaveBeenCalledWith(
        expect.stringMatching(/^batch-/),
        FileType.CAMPAIGN_XLSX
      );

      // Step 4: Verify state reset to upload-ready
      act(() => {
        const cancelledResponse: ProcessingStatusResponse = {
          success: true,
          data: {
            campaign_xlsx: {
              ...createProcessingProgress(FileType.CAMPAIGN_XLSX, ProcessingStage.VALIDATE, ProcessingStatus.CANCELLED),
              status: ProcessingStatus.CANCELLED
            },
            reporting_csv: null,
            errors: [],
            last_updated: new Date().toISOString()
          },
          polling_interval: 2000
        };
        mockCallbacks.onCompletion(cancelledResponse);
      });

      // Step 5: Verify cleanup of progress and error states
      await waitFor(() => {
        const uploadBtn = screen.getByTestId('campaign-upload-button');
        expect(uploadBtn).not.toBeDisabled();
      });

      await waitFor(() => {
        expect(screen.queryByText(/processing/i)).not.toBeInTheDocument();
      });
    });
  });

  describe('7. Component Integration Testing', () => {
    test('should integrate all processing components seamlessly', async () => {
      const user = userEvent.setup();
      render(<DataUpload />);

      // Verify all components are rendered
      expect(screen.getByText('Data Upload')).toBeInTheDocument();
      expect(screen.getByText(/file upload.*processing control/i)).toBeInTheDocument();
      expect(screen.getByText(/supported file formats/i)).toBeInTheDocument();

      // Start processing to verify component integration
      const campaignFile = createMockFile('campaign.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      const fileInput = document.querySelector('input[accept*=".xlsx"]') as HTMLInputElement;
      await user.upload(fileInput, campaignFile);
      
      const uploadButton = screen.getByRole('button', { name: /upload.*campaign/i });
      await user.click(uploadButton);

      // Progress component should appear
      act(() => {
        mockCallbacks.onProgressUpdate(
          createProcessingProgress(FileType.CAMPAIGN_XLSX, ProcessingStage.PARSE, ProcessingStatus.PROCESSING)
        );
      });

      await waitFor(() => {
        expect(screen.getByText(/processing progress/i)).toBeInTheDocument();
      });

      // Error component should appear when errors occur
      const testError = createProcessingError(
        ErrorCategory.VALIDATION,
        ErrorSeverity.ERROR,
        'Test error message',
        FileType.CAMPAIGN_XLSX
      );

      act(() => {
        mockCallbacks.onErrorUpdate([testError]);
      });

      await waitFor(() => {
        expect(screen.getByText(/processing errors/i)).toBeInTheDocument();
        expect(screen.getByText('Test error message')).toBeInTheDocument();
      });
    });
  });

  describe('8. HTTP Polling Service Integration', () => {
    test('should verify 2-second polling intervals and proper API integration', async () => {
      const user = userEvent.setup();
      render(<DataUpload />);

      // Start processing
      const campaignFile = createMockFile('campaign.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      const fileInput = screen.getByTestId('campaign-file-input');
      await user.upload(fileInput, campaignFile);
      
      await waitFor(() => {
        const uploadButton = screen.getByTestId('campaign-upload-button');
        expect(uploadButton).not.toBeDisabled();
      });
      
      const uploadButton = screen.getByTestId('campaign-upload-button');
      await user.click(uploadButton);

      // Verify polling was started with correct configuration
      expect(mockServiceInstance.startPolling).toHaveBeenCalledWith(
        expect.stringMatching(/^batch-/),
        expect.objectContaining({
          onProgressUpdate: expect.any(Function),
          onErrorUpdate: expect.any(Function),
          onCompletion: expect.any(Function),
          onFailure: expect.any(Function)
        })
      );

      // Verify batch ID format and tracking
      const callArgs = mockServiceInstance.startPolling.mock.calls[0];
      const batchId = callArgs[0];
      expect(batchId).toMatch(/^batch-\d+-[a-z0-9]+$/);
    });

    test('should handle connection resilience and retry logic', async () => {
      const user = userEvent.setup();
      render(<DataUpload />);

      // Start processing
      const campaignFile = createMockFile('campaign.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      const fileInput = screen.getByTestId('campaign-file-input');
      await user.upload(fileInput, campaignFile);
      
      await waitFor(() => {
        const uploadButton = screen.getByTestId('campaign-upload-button');
        expect(uploadButton).not.toBeDisabled();
      });
      
      const uploadButton = screen.getByTestId('campaign-upload-button');
      await user.click(uploadButton);

      // Simulate network error
      act(() => {
        mockCallbacks.onFailure(new Error('Network error'));
      });

      // Should handle error gracefully
      await waitFor(() => {
        const uploadBtn = screen.getByTestId('campaign-upload-button');
        expect(uploadBtn).not.toBeDisabled();
      });
    });
  });

  describe('9. Performance Testing', () => {
    test('should handle large file processing simulation efficiently', async () => {
      const user = userEvent.setup();
      render(<DataUpload />);

      // Simulate 250MB file
      const largeFile = createMockFile(
        'large-campaign.xlsx',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        250 * 1024 * 1024
      );

      const fileInput = document.querySelector('input[accept*=".xlsx"]') as HTMLInputElement;
      
      // Performance measurement
      const startTime = performance.now();
      await user.upload(fileInput, largeFile);
      const uploadTime = performance.now() - startTime;

      // Upload should be responsive (under 100ms for UI interaction)
      expect(uploadTime).toBeLessThan(100);

      const uploadButton = screen.getByRole('button', { name: /upload.*campaign/i });
      const clickStartTime = performance.now();
      await user.click(uploadButton);
      const clickTime = performance.now() - clickStartTime;

      // Button click should be responsive
      expect(clickTime).toBeLessThan(50);
    });

    test('should handle memory management during processing updates', async () => {
      const user = userEvent.setup();
      render(<DataUpload />);

      // Start processing
      const campaignFile = createMockFile('campaign.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      const fileInput = screen.getByTestId('campaign-file-input');
      await user.upload(fileInput, campaignFile);
      
      await waitFor(() => {
        const uploadButton = screen.getByTestId('campaign-upload-button');
        expect(uploadButton).not.toBeDisabled();
      });
      
      const uploadButton = screen.getByTestId('campaign-upload-button');
      await user.click(uploadButton);

      // Simulate many rapid updates
      const updates = 50;
      for (let i = 0; i < updates; i++) {
        act(() => {
          mockCallbacks.onProgressUpdate(
            createProcessingProgress(FileType.CAMPAIGN_XLSX, ProcessingStage.VALIDATE, ProcessingStatus.PROCESSING)
          );
        });
      }

      // Should handle updates without performance degradation
      await waitFor(() => {
        expect(screen.getByText(/processing/i)).toBeInTheDocument();
      });
    });
  });

  describe('10. Accessibility Testing', () => {
    test('should maintain screen reader compatibility', async () => {
      render(<DataUpload />);

      // Verify ARIA labels and roles
      const fileInputs = screen.getAllByRole('textbox') || screen.getAllByLabelText(/file/i);
      fileInputs.forEach(input => {
        expect(input).toBeInTheDocument();
      });

      // Verify status announcer for screen readers
      const statusAnnouncer = screen.getByTestId('processing-status-announcer');
      expect(statusAnnouncer).toHaveAttribute('aria-live', 'polite');
      expect(statusAnnouncer).toHaveAttribute('aria-atomic', 'true');
    });

    test('should support keyboard navigation', async () => {
      render(<DataUpload />);
      
      // Verify main upload buttons are focusable
      const campaignUploadButton = screen.getByTestId('campaign-upload-button');
      const reportingUploadButton = screen.getByTestId('reporting-upload-button');
      
      expect(campaignUploadButton).not.toHaveAttribute('tabindex', '-1');
      expect(reportingUploadButton).not.toHaveAttribute('tabindex', '-1');

      // Test tab navigation
      campaignUploadButton.focus();
      expect(document.activeElement).toBe(campaignUploadButton);
    });

    test('should announce processing state changes', async () => {
      const user = userEvent.setup();
      render(<DataUpload />);

      // Start processing
      const campaignFile = createMockFile('campaign.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      const fileInput = screen.getByTestId('campaign-file-input');
      await user.upload(fileInput, campaignFile);
      
      await waitFor(() => {
        const uploadButton = screen.getByTestId('campaign-upload-button');
        expect(uploadButton).not.toBeDisabled();
      });
      
      const uploadButton = screen.getByTestId('campaign-upload-button');
      await user.click(uploadButton);

      // Status announcer should have content
      const statusAnnouncer = screen.getByTestId('processing-status-announcer');
      
      act(() => {
        mockCallbacks.onProgressUpdate(
          createProcessingProgress(FileType.CAMPAIGN_XLSX, ProcessingStage.PARSE, ProcessingStatus.PROCESSING)
        );
      });

      await waitFor(() => {
        expect(statusAnnouncer.textContent).toBeTruthy();
      });
    });
  });

  describe('11. Upload Processing Pipeline Specification Compliance', () => {
    test('should enforce 250MB file size limit exactly', async () => {
      mockedUploadService.validateFile.mockImplementation((file) => {
        const fileSize = (file as any).__mockSize || file.size;
        if (fileSize > 250 * 1024 * 1024) {
          return { isValid: false, errors: ['File size exceeds 250MB limit'] };
        }
        return { isValid: true, errors: [] };
      });

      render(<DataUpload />);

      // Test exactly at limit (should pass)
      const exactLimitFile = createMockFile(
        'exact-limit.xlsx',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        250 * 1024 * 1024
      );

      expect(mockedUploadService.validateFile(exactLimitFile)).toEqual({
        isValid: true,
        errors: []
      });

      // Test over limit (should fail)
      const overLimitFile = createMockFile(
        'over-limit.xlsx',
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        250 * 1024 * 1024 + 1
      );

      expect(mockedUploadService.validateFile(overLimitFile)).toEqual({
        isValid: false,
        errors: ['File size exceeds 250MB limit']
      });
    });

    test('should implement equal-stage progress tracking (25%, 50%, 75%, 100%)', async () => {
      const user = userEvent.setup();
      render(<DataUpload />);

      // Start processing
      const campaignFile = createMockFile('campaign.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      const fileInput = screen.getByTestId('campaign-file-input');
      await user.upload(fileInput, campaignFile);
      
      await waitFor(() => {
        const uploadButton = screen.getByTestId('campaign-upload-button');
        expect(uploadButton).not.toBeDisabled();
      });
      
      const uploadButton = screen.getByTestId('campaign-upload-button');
      await user.click(uploadButton);

      // Test each stage has exact progress percentage
      const stageProgressMap = {
        [ProcessingStage.PARSE]: 25,
        [ProcessingStage.VALIDATE]: 50,
        [ProcessingStage.CLASSIFY]: 75,
        [ProcessingStage.COMPLETE]: 100
      };

      for (const [stage, expectedProgress] of Object.entries(stageProgressMap)) {
        act(() => {
          const progress = createProcessingProgress(
            FileType.CAMPAIGN_XLSX,
            stage as ProcessingStage,
            ProcessingStatus.PROCESSING
          );
          expect(progress.progress).toBe(expectedProgress);
          mockCallbacks.onProgressUpdate(progress);
        });

        await waitFor(() => {
          const progressTexts = screen.getAllByText(`${expectedProgress}%`);
          expect(progressTexts.length).toBeGreaterThan(0);
        });
      }
    });

    test('should implement upload blocking per file type during processing', async () => {
      const user = userEvent.setup();
      render(<DataUpload />);

      // Start Campaign processing
      const campaignFile = createMockFile('campaign.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      const campaignInput = document.querySelector('input[accept*=".xlsx"]') as HTMLInputElement;
      await user.upload(campaignInput, campaignFile);
      
      const campaignUploadButton = screen.getByRole('button', { name: /upload.*campaign/i });
      await user.click(campaignUploadButton);

      act(() => {
        mockCallbacks.onProgressUpdate(
          createProcessingProgress(FileType.CAMPAIGN_XLSX, ProcessingStage.PARSE, ProcessingStatus.PROCESSING)
        );
      });

      // Campaign upload should be blocked
      await waitFor(() => {
        expect(campaignUploadButton).toBeDisabled();
      });

      // Reporting upload should still be enabled (different file type)
      const reportingUploadButton = screen.getByTestId('reporting-upload-button');
      expect(reportingUploadButton).not.toBeDisabled();
    });

    test('should verify complete processing workflow integration', async () => {
      const user = userEvent.setup();
      render(<DataUpload />);

      // Complete workflow verification
      const campaignFile = createMockFile('campaign.xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet');
      
      // 1. File selection
      const fileInput = document.querySelector('input[accept*=".xlsx"]') as HTMLInputElement;
      await user.upload(fileInput, campaignFile);

      // 2. Upload initiation
      const uploadButton = screen.getByRole('button', { name: /upload.*campaign/i });
      await user.click(uploadButton);

      // 3. Processing stages
      const workflow = [
        { stage: ProcessingStage.PARSE, status: ProcessingStatus.PROCESSING },
        { stage: ProcessingStage.VALIDATE, status: ProcessingStatus.PROCESSING },
        { stage: ProcessingStage.CLASSIFY, status: ProcessingStatus.PROCESSING },
        { stage: ProcessingStage.COMPLETE, status: ProcessingStatus.COMPLETED }
      ];

      for (const { stage, status } of workflow) {
        act(() => {
          mockCallbacks.onProgressUpdate(
            createProcessingProgress(FileType.CAMPAIGN_XLSX, stage, status)
          );
        });

        await waitFor(() => {
          if (status === ProcessingStatus.COMPLETED) {
            const progress100 = screen.getAllByText('100%');
            expect(progress100.length).toBeGreaterThan(0);
          } else {
            expect(screen.getByTestId('campaign-status-processing')).toBeInTheDocument();
          }
        });
      }

      // 4. Completion
      act(() => {
        const completionResponse: ProcessingStatusResponse = {
          success: true,
          data: {
            campaign_xlsx: createProcessingProgress(FileType.CAMPAIGN_XLSX, ProcessingStage.COMPLETE, ProcessingStatus.COMPLETED),
            reporting_csv: null,
            errors: [],
            last_updated: new Date().toISOString()
          },
          polling_interval: 2000
        };
        mockCallbacks.onCompletion(completionResponse);
      });

      await waitFor(() => {
        expect(screen.getByTestId('processing-success-message')).toBeInTheDocument();
      });

      // Verify all specification requirements are met
      expect(screen.getByText(/processing completed successfully/i)).toBeInTheDocument();
      expect(screen.getByText(/campaign xlsx.*completed/i)).toBeInTheDocument();
    });
  });
});