/**
 * TDD Red Phase: Comprehensive tests for useProcessingStatus React hook
 * These tests will fail initially until the hook is implemented
 * 
 * Test suite for Upload Processing Pipeline UI React hook integration
 * Covers processing state management, HTTP polling integration, and UI component data provision
 */

import { renderHook, act, waitFor } from '@testing-library/react';
import { ProcessingStatusService } from '../../services/processingStatusService';
import { useProcessingStatus } from '../useProcessingStatus';
import {
  ProcessingState,
  ProcessingStatus,
  ProcessingStage,
  FileType,
  ErrorCategory,
  ErrorSeverity,
  ProcessingProgress,
  ProcessingError,
  ProcessingStatusResponse,
  ProcessingFileType
} from '../../types/processing';

// Mock ProcessingStatusService
jest.mock('../../services/processingStatusService');
const MockedProcessingStatusService = ProcessingStatusService as jest.MockedClass<typeof ProcessingStatusService>;

// Mock window focus/blur events
const mockWindowFocusEvent = () => {
  const event = new Event('focus');
  window.dispatchEvent(event);
};

const mockWindowBlurEvent = () => {
  const event = new Event('blur');
  window.dispatchEvent(event);
};

// Test data factory functions
const createMockFile = (name: string, size: number = 1024 * 1024, type: string = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'): File => {
  const file = new File(['mock content'], name, { type, lastModified: Date.now() });
  // Set mock size for testing file size validation
  (file as any).__mockSize = size;
  return file;
};

const createMockProgress = (overrides: Partial<ProcessingProgress> = {}): ProcessingProgress => ({
  batch_id: 'batch-123',
  stage: ProcessingStage.PARSE,
  progress: 25,
  status: ProcessingStatus.PROCESSING,
  file_type: FileType.CAMPAIGN_XLSX,
  started_at: '2025-09-09T10:00:00Z',
  updated_at: '2025-09-09T10:00:30Z',
  ...overrides
});

const createMockError = (overrides: Partial<ProcessingError> = {}): ProcessingError => ({
  error_id: 'error-123',
  timestamp: '2025-09-09T10:00:15Z',
  category: ErrorCategory.VALIDATION,
  severity: ErrorSeverity.ERROR,
  code: 'INVALID_FORMAT',
  message: 'Invalid file format detected',
  context: {
    file_type: FileType.CAMPAIGN_XLSX,
    line_number: 5
  },
  suggested_action: 'Please check the file format and try again',
  ...overrides
});

const createMockState = (overrides: Partial<ProcessingState> = {}): ProcessingState => ({
  campaign_xlsx: null,
  reporting_csv: null,
  errors: [],
  last_updated: '2025-09-09T10:00:00Z',
  ...overrides
});

const createMockStatusResponse = (success: boolean = true, data?: ProcessingState): ProcessingStatusResponse => ({
  success,
  data: success ? data || createMockState() : undefined,
  error: success ? undefined : {
    code: 'PROCESSING_ERROR',
    message: 'Processing failed',
    details: 'Detailed error information'
  },
  polling_interval: 2000
});

describe('useProcessingStatus Hook', () => {
  let mockServiceInstance: jest.Mocked<ProcessingStatusService>;
  let mockCallbacks: any;

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();

    // Create mock service instance
    mockServiceInstance = {
      startPolling: jest.fn(),
      stopPolling: jest.fn(),
      cleanup: jest.fn(),
      cancelProcessing: jest.fn()
    } as any;

    MockedProcessingStatusService.mockImplementation(() => mockServiceInstance);

    // Setup default service behavior
    mockServiceInstance.startPolling.mockImplementation((batchId, callbacks) => {
      mockCallbacks = callbacks;
    });
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  describe('1. Hook Initialization Tests', () => {
    describe('hook returns proper initial state', () => {
      it('should return correct initial state structure', () => {
        const { result } = renderHook(() => useProcessingStatus());

        expect(result.current.processingState).toEqual({
          campaign_xlsx: null,
          reporting_csv: null,
          errors: [],
          last_updated: expect.any(String)
        });
        expect(result.current.currentProgress).toBeNull();
        expect(result.current.errors).toEqual([]);
        expect(result.current.isProcessing).toBe(false);
        expect(result.current.hasErrors).toBe(false);
      });

      it('should provide all required hook interface functions', () => {
        const { result } = renderHook(() => useProcessingStatus());

        expect(typeof result.current.startProcessing).toBe('function');
        expect(typeof result.current.cancelProcessing).toBe('function');
        expect(typeof result.current.clearErrors).toBe('function');
        expect(typeof result.current.canUpload).toBe('function');
      });

      it('should initialize ProcessingStatusService instance', () => {
        renderHook(() => useProcessingStatus());

        expect(MockedProcessingStatusService).toHaveBeenCalledTimes(1);
      });
    });

    describe('default ProcessingState for both file types idle', () => {
      it('should have both file types in idle state initially', () => {
        const { result } = renderHook(() => useProcessingStatus());

        expect(result.current.processingState.campaign_xlsx).toBeNull();
        expect(result.current.processingState.reporting_csv).toBeNull();
        expect(result.current.canUpload(ProcessingFileType.CAMPAIGN_XLSX)).toBe(true);
        expect(result.current.canUpload(ProcessingFileType.REPORTING_CSV)).toBe(true);
      });

      it('should indicate no processing is active initially', () => {
        const { result } = renderHook(() => useProcessingStatus());

        expect(result.current.isProcessing).toBe(false);
        expect(result.current.currentProgress).toBeNull();
      });
    });

    describe('initial values for progress, errors, status flags', () => {
      it('should have empty error state initially', () => {
        const { result } = renderHook(() => useProcessingStatus());

        expect(result.current.errors).toEqual([]);
        expect(result.current.hasErrors).toBe(false);
      });

      it('should have correct status flags initially', () => {
        const { result } = renderHook(() => useProcessingStatus());

        expect(result.current.isProcessing).toBe(false);
        expect(result.current.hasErrors).toBe(false);
        expect(result.current.canUpload(ProcessingFileType.CAMPAIGN_XLSX)).toBe(true);
        expect(result.current.canUpload(ProcessingFileType.REPORTING_CSV)).toBe(true);
      });
    });

    describe('hook with custom initial state', () => {
      it('should support initialization with existing processing state', () => {
        const initialState = createMockState({
          campaign_xlsx: createMockProgress({ status: ProcessingStatus.COMPLETED }),
          errors: [createMockError()]
        });

        const { result } = renderHook(() => useProcessingStatus(initialState));

        expect(result.current.processingState.campaign_xlsx?.status).toBe(ProcessingStatus.COMPLETED);
        expect(result.current.errors).toHaveLength(1);
        expect(result.current.hasErrors).toBe(true);
      });
    });

    describe('multiple hook instances independence', () => {
      it('should maintain independent state across multiple hook instances', () => {
        const { result: result1 } = renderHook(() => useProcessingStatus());
        const { result: result2 } = renderHook(() => useProcessingStatus());

        expect(result1.current.processingState).not.toBe(result2.current.processingState);
        expect(MockedProcessingStatusService).toHaveBeenCalledTimes(2);
      });
    });
  });

  describe('2. Processing Lifecycle Tests', () => {
    describe('startProcessing function with valid file', () => {
      it('should start processing with valid campaign XLSX file', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx', 50 * 1024 * 1024); // 50MB

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        expect(mockServiceInstance.startPolling).toHaveBeenCalledWith(
          expect.any(String), // batch_id
          expect.objectContaining({
            onProgressUpdate: expect.any(Function),
            onErrorUpdate: expect.any(Function),
            onCompletion: expect.any(Function),
            onFailure: expect.any(Function)
          })
        );
      });

      it('should start processing with valid reporting CSV file', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('reporting.csv', 30 * 1024 * 1024, 'text/csv'); // 30MB

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.REPORTING_CSV);
        });

        expect(mockServiceInstance.startPolling).toHaveBeenCalledWith(
          expect.any(String),
          expect.any(Object)
        );
      });
    });

    describe('file type detection and processing state updates', () => {
      it('should update processing state for campaign XLSX', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        // Simulate progress update from service
        act(() => {
          mockCallbacks.onProgressUpdate(createMockProgress({ file_type: FileType.CAMPAIGN_XLSX }));
        });

        expect(result.current.processingState.campaign_xlsx).not.toBeNull();
        expect(result.current.processingState.campaign_xlsx?.file_type).toBe(FileType.CAMPAIGN_XLSX);
      });

      it('should update processing state for reporting CSV', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('reporting.csv', 1024 * 1024, 'text/csv');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.REPORTING_CSV);
        });

        // Simulate progress update from service
        act(() => {
          mockCallbacks.onProgressUpdate(createMockProgress({ file_type: FileType.REPORTING_CSV }));
        });

        expect(result.current.processingState.reporting_csv).not.toBeNull();
        expect(result.current.processingState.reporting_csv?.file_type).toBe(FileType.REPORTING_CSV);
      });
    });

    describe('processing state transitions', () => {
      it('should transition from idle to processing to completed', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        // Initial idle state
        expect(result.current.isProcessing).toBe(false);

        // Start processing
        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        // Simulate processing update
        act(() => {
          mockCallbacks.onProgressUpdate(createMockProgress({ 
            status: ProcessingStatus.PROCESSING,
            stage: ProcessingStage.VALIDATE,
            progress: 50
          }));
        });

        expect(result.current.isProcessing).toBe(true);
        expect(result.current.currentProgress?.stage).toBe(ProcessingStage.VALIDATE);

        // Simulate completion
        act(() => {
          mockCallbacks.onProgressUpdate(createMockProgress({ 
            status: ProcessingStatus.COMPLETED,
            stage: ProcessingStage.COMPLETE,
            progress: 100
          }));
        });

        expect(result.current.currentProgress?.status).toBe(ProcessingStatus.COMPLETED);
      });
    });

    describe('multiple file types processing concurrently', () => {
      it('should handle concurrent processing of both file types', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const campaignFile = createMockFile('campaign.xlsx');
        const reportingFile = createMockFile('reporting.csv', 1024 * 1024, 'text/csv');

        // Start both processes
        await act(async () => {
          await result.current.startProcessing(campaignFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        await act(async () => {
          await result.current.startProcessing(reportingFile, ProcessingFileType.REPORTING_CSV);
        });

        // Simulate progress updates for both
        act(() => {
          mockCallbacks.onProgressUpdate(createMockProgress({ 
            file_type: FileType.CAMPAIGN_XLSX,
            stage: ProcessingStage.PARSE,
            progress: 25
          }));
          mockCallbacks.onProgressUpdate(createMockProgress({ 
            file_type: FileType.REPORTING_CSV,
            stage: ProcessingStage.VALIDATE,
            progress: 50
          }));
        });

        expect(result.current.processingState.campaign_xlsx?.stage).toBe(ProcessingStage.PARSE);
        expect(result.current.processingState.reporting_csv?.stage).toBe(ProcessingStage.VALIDATE);
        expect(result.current.isProcessing).toBe(true);
      });
    });

    describe('processing completion and state reset', () => {
      it('should maintain completed state after processing finishes', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        // Complete processing
        act(() => {
          const completedProgress = createMockProgress({ 
            status: ProcessingStatus.COMPLETED,
            stage: ProcessingStage.COMPLETE,
            progress: 100,
            completed_at: '2025-09-09T10:05:00Z'
          });
          mockCallbacks.onProgressUpdate(completedProgress);
          mockCallbacks.onCompletion(createMockStatusResponse(true, createMockState({ campaign_xlsx: completedProgress })));
        });

        expect(result.current.processingState.campaign_xlsx?.status).toBe(ProcessingStatus.COMPLETED);
        expect(result.current.canUpload(ProcessingFileType.CAMPAIGN_XLSX)).toBe(true); // Should allow new upload
      });
    });
  });

  describe('3. HTTP Polling Integration Tests', () => {
    describe('ProcessingStatusService integration', () => {
      it('should create ProcessingStatusService instance on hook initialization', () => {
        renderHook(() => useProcessingStatus());

        expect(MockedProcessingStatusService).toHaveBeenCalledTimes(1);
        expect(MockedProcessingStatusService).toHaveBeenCalledWith();
      });

      it('should pass correct configuration to ProcessingStatusService', () => {
        renderHook(() => useProcessingStatus());

        expect(MockedProcessingStatusService).toHaveBeenCalledWith();
      });
    });

    describe('polling start when processing begins', () => {
      it('should start polling when startProcessing is called', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        expect(mockServiceInstance.startPolling).toHaveBeenCalledWith(
          expect.any(String),
          expect.objectContaining({
            onProgressUpdate: expect.any(Function),
            onErrorUpdate: expect.any(Function),
            onCompletion: expect.any(Function),
            onFailure: expect.any(Function)
          })
        );
      });

      it('should generate unique batch IDs for different processing sessions', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile1 = createMockFile('campaign1.xlsx');
        const mockFile2 = createMockFile('campaign2.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile1, ProcessingFileType.CAMPAIGN_XLSX);
        });

        const firstBatchId = mockServiceInstance.startPolling.mock.calls[0][0];

        // Complete first processing
        act(() => {
          mockCallbacks.onCompletion(createMockStatusResponse());
        });

        // Start second processing
        await act(async () => {
          await result.current.startProcessing(mockFile2, ProcessingFileType.CAMPAIGN_XLSX);
        });

        const secondBatchId = mockServiceInstance.startPolling.mock.calls[1][0];
        expect(firstBatchId).not.toBe(secondBatchId);
      });
    });

    describe('polling callbacks update hook state correctly', () => {
      it('should update hook state when onProgressUpdate callback is called', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        const mockProgress = createMockProgress({ 
          stage: ProcessingStage.VALIDATE,
          progress: 50
        });

        act(() => {
          mockCallbacks.onProgressUpdate(mockProgress);
        });

        expect(result.current.currentProgress).toEqual(mockProgress);
        expect(result.current.processingState.campaign_xlsx).toEqual(mockProgress);
      });

      it('should update hook state when onErrorUpdate callback is called', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        const mockErrors = [createMockError(), createMockError({ error_id: 'error-456' })];

        act(() => {
          mockCallbacks.onErrorUpdate(mockErrors);
        });

        expect(result.current.errors).toEqual(mockErrors);
        expect(result.current.hasErrors).toBe(true);
      });
    });

    describe('polling stop on processing completion/error', () => {
      it('should stop polling when processing completes', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        const batchId = mockServiceInstance.startPolling.mock.calls[0][0];

        act(() => {
          mockCallbacks.onCompletion(createMockStatusResponse());
        });

        expect(mockServiceInstance.stopPolling).toHaveBeenCalledWith(batchId);
      });

      it('should stop polling when processing fails', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        const batchId = mockServiceInstance.startPolling.mock.calls[0][0];

        act(() => {
          mockCallbacks.onFailure({ code: 'ERROR', message: 'Processing failed' });
        });

        expect(mockServiceInstance.stopPolling).toHaveBeenCalledWith(batchId);
      });
    });

    describe('service cleanup on hook unmount', () => {
      it('should cleanup ProcessingStatusService on hook unmount', () => {
        const { unmount } = renderHook(() => useProcessingStatus());

        unmount();

        expect(mockServiceInstance.cleanup).toHaveBeenCalledTimes(1);
      });

      it('should stop all active polling sessions on unmount', async () => {
        const { result, unmount } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        unmount();

        expect(mockServiceInstance.cleanup).toHaveBeenCalledTimes(1);
      });
    });
  });

  describe('4. Progress State Management Tests', () => {
    describe('progress updates from polling service', () => {
      it('should update currentProgress when progress callback is triggered', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        const progressUpdate = createMockProgress({ 
          stage: ProcessingStage.CLASSIFY,
          progress: 75
        });

        act(() => {
          mockCallbacks.onProgressUpdate(progressUpdate);
        });

        expect(result.current.currentProgress).toEqual(progressUpdate);
      });

      it('should maintain progress history in processing state', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        const progress1 = createMockProgress({ stage: ProcessingStage.PARSE, progress: 25 });
        const progress2 = createMockProgress({ stage: ProcessingStage.VALIDATE, progress: 50 });

        act(() => {
          mockCallbacks.onProgressUpdate(progress1);
        });

        expect(result.current.processingState.campaign_xlsx).toEqual(progress1);

        act(() => {
          mockCallbacks.onProgressUpdate(progress2);
        });

        expect(result.current.processingState.campaign_xlsx).toEqual(progress2);
        expect(result.current.currentProgress).toEqual(progress2);
      });
    });

    describe('stage transitions', () => {
      it('should handle stage progression through all processing stages', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        const stages = [
          { stage: ProcessingStage.PARSE, progress: 25 },
          { stage: ProcessingStage.VALIDATE, progress: 50 },
          { stage: ProcessingStage.CLASSIFY, progress: 75 },
          { stage: ProcessingStage.COMPLETE, progress: 100 }
        ];

        stages.forEach((stageData, index) => {
          act(() => {
            mockCallbacks.onProgressUpdate(createMockProgress(stageData));
          });

          expect(result.current.currentProgress?.stage).toBe(stageData.stage);
          expect(result.current.currentProgress?.progress).toBe(stageData.progress);
        });
      });
    });

    describe('progress percentage updates', () => {
      it('should track exact progress percentages (25%, 50%, 75%, 100%)', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        const progressValues: (25 | 50 | 75 | 100)[] = [25, 50, 75, 100];

        progressValues.forEach((progress) => {
          act(() => {
            mockCallbacks.onProgressUpdate(createMockProgress({ progress }));
          });

          expect(result.current.currentProgress?.progress).toBe(progress);
        });
      });
    });

    describe('currentProgress state with ProcessingProgress interface', () => {
      it('should maintain ProcessingProgress interface structure', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        const mockProgress = createMockProgress({
          batch_id: 'test-batch-123',
          stage: ProcessingStage.VALIDATE,
          progress: 50,
          status: ProcessingStatus.PROCESSING,
          file_type: FileType.CAMPAIGN_XLSX,
          started_at: '2025-09-09T10:00:00Z',
          updated_at: '2025-09-09T10:02:30Z'
        });

        act(() => {
          mockCallbacks.onProgressUpdate(mockProgress);
        });

        expect(result.current.currentProgress).toMatchObject({
          batch_id: 'test-batch-123',
          stage: ProcessingStage.VALIDATE,
          progress: 50,
          status: ProcessingStatus.PROCESSING,
          file_type: FileType.CAMPAIGN_XLSX,
          started_at: expect.any(String),
          updated_at: expect.any(String)
        });
      });
    });

    describe('progress reset after completion', () => {
      it('should maintain completed progress after processing finishes', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        const completedProgress = createMockProgress({ 
          status: ProcessingStatus.COMPLETED,
          stage: ProcessingStage.COMPLETE,
          progress: 100,
          completed_at: '2025-09-09T10:05:00Z'
        });

        act(() => {
          mockCallbacks.onProgressUpdate(completedProgress);
          mockCallbacks.onCompletion(createMockStatusResponse());
        });

        expect(result.current.currentProgress?.status).toBe(ProcessingStatus.COMPLETED);
        expect(result.current.processingState.campaign_xlsx?.status).toBe(ProcessingStatus.COMPLETED);
      });
    });
  });

  describe('5. Error State Management Tests', () => {
    describe('error updates from polling service', () => {
      it('should update errors when onErrorUpdate callback is called', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        const mockErrors = [
          createMockError({ error_id: 'error-1', message: 'First error' }),
          createMockError({ error_id: 'error-2', message: 'Second error' })
        ];

        act(() => {
          mockCallbacks.onErrorUpdate(mockErrors);
        });

        expect(result.current.errors).toEqual(mockErrors);
        expect(result.current.hasErrors).toBe(true);
      });
    });

    describe('error accumulation during processing', () => {
      it('should accumulate errors throughout processing lifecycle', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        // First batch of errors
        const firstErrors = [createMockError({ error_id: 'error-1' })];
        act(() => {
          mockCallbacks.onErrorUpdate(firstErrors);
        });

        expect(result.current.errors).toHaveLength(1);

        // Additional errors
        const moreErrors = [
          createMockError({ error_id: 'error-1' }),
          createMockError({ error_id: 'error-2' }),
          createMockError({ error_id: 'error-3' })
        ];
        act(() => {
          mockCallbacks.onErrorUpdate(moreErrors);
        });

        expect(result.current.errors).toHaveLength(3);
      });
    });

    describe('time-ordered error display', () => {
      it('should maintain chronological order of errors', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        const orderedErrors = [
          createMockError({ 
            error_id: 'error-1', 
            timestamp: '2025-09-09T10:00:10Z',
            message: 'First error'
          }),
          createMockError({ 
            error_id: 'error-2', 
            timestamp: '2025-09-09T10:00:20Z',
            message: 'Second error'
          }),
          createMockError({ 
            error_id: 'error-3', 
            timestamp: '2025-09-09T10:00:30Z',
            message: 'Third error'
          })
        ];

        act(() => {
          mockCallbacks.onErrorUpdate(orderedErrors);
        });

        expect(result.current.errors[0].message).toBe('First error');
        expect(result.current.errors[1].message).toBe('Second error');
        expect(result.current.errors[2].message).toBe('Third error');
      });
    });

    describe('clearErrors function', () => {
      it('should clear all errors when clearErrors is called', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        // Add some errors
        const mockErrors = [createMockError(), createMockError({ error_id: 'error-2' })];
        act(() => {
          mockCallbacks.onErrorUpdate(mockErrors);
        });

        expect(result.current.hasErrors).toBe(true);

        // Clear errors
        act(() => {
          result.current.clearErrors();
        });

        expect(result.current.errors).toEqual([]);
        expect(result.current.hasErrors).toBe(false);
      });
    });

    describe('error state with different categories and severities', () => {
      it('should handle errors of different categories and severities', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        const diverseErrors = [
          createMockError({ 
            category: ErrorCategory.VALIDATION,
            severity: ErrorSeverity.ERROR
          }),
          createMockError({ 
            category: ErrorCategory.PARSING,
            severity: ErrorSeverity.WARNING
          }),
          createMockError({ 
            category: ErrorCategory.SYSTEM,
            severity: ErrorSeverity.INFO
          })
        ];

        act(() => {
          mockCallbacks.onErrorUpdate(diverseErrors);
        });

        expect(result.current.errors).toHaveLength(3);
        expect(result.current.errors[0].category).toBe(ErrorCategory.VALIDATION);
        expect(result.current.errors[1].severity).toBe(ErrorSeverity.WARNING);
        expect(result.current.errors[2].category).toBe(ErrorCategory.SYSTEM);
      });
    });

    describe('error state reset on new processing', () => {
      it('should reset errors when starting new processing session', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile1 = createMockFile('campaign1.xlsx');
        const mockFile2 = createMockFile('campaign2.xlsx');

        // First processing with errors
        await act(async () => {
          await result.current.startProcessing(mockFile1, ProcessingFileType.CAMPAIGN_XLSX);
        });

        act(() => {
          mockCallbacks.onErrorUpdate([createMockError()]);
        });

        expect(result.current.hasErrors).toBe(true);

        // Complete first processing
        act(() => {
          mockCallbacks.onCompletion(createMockStatusResponse());
        });

        // Start second processing
        await act(async () => {
          await result.current.startProcessing(mockFile2, ProcessingFileType.CAMPAIGN_XLSX);
        });

        expect(result.current.errors).toEqual([]);
        expect(result.current.hasErrors).toBe(false);
      });
    });
  });

  describe('6. Processing Control Tests', () => {
    describe('startProcessing with file size validation', () => {
      it('should accept files exactly at 250MB limit', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('large_campaign.xlsx', 250 * 1024 * 1024); // Exactly 250MB

        await expect(
          act(async () => {
            await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
          })
        ).resolves.not.toThrow();

        expect(mockServiceInstance.startPolling).toHaveBeenCalled();
      });

      it('should reject files over 250MB limit', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('oversized_campaign.xlsx', 251 * 1024 * 1024); // 251MB

        await expect(
          act(async () => {
            await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
          })
        ).rejects.toThrow('File size exceeds 250MB limit');

        expect(mockServiceInstance.startPolling).not.toHaveBeenCalled();
      });

      it('should accept files under 250MB limit', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('small_campaign.xlsx', 100 * 1024 * 1024); // 100MB

        await expect(
          act(async () => {
            await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
          })
        ).resolves.not.toThrow();

        expect(mockServiceInstance.startPolling).toHaveBeenCalled();
      });
    });

    describe('startProcessing with file type validation', () => {
      it('should validate campaign XLSX file type', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.txt', 1024 * 1024, 'text/plain'); // Wrong type

        await expect(
          act(async () => {
            await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
          })
        ).rejects.toThrow('Invalid file type');

        expect(mockServiceInstance.startPolling).not.toHaveBeenCalled();
      });

      it('should validate reporting CSV file type', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('reporting.xlsx', 1024 * 1024, 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'); // Wrong type

        await expect(
          act(async () => {
            await result.current.startProcessing(mockFile, ProcessingFileType.REPORTING_CSV);
          })
        ).rejects.toThrow('Invalid file type');

        expect(mockServiceInstance.startPolling).not.toHaveBeenCalled();
      });
    });

    describe('cancelProcessing function', () => {
      it('should cancel processing for campaign XLSX', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        const batchId = mockServiceInstance.startPolling.mock.calls[0][0];

        await act(async () => {
          await result.current.cancelProcessing(ProcessingFileType.CAMPAIGN_XLSX);
        });

        expect(mockServiceInstance.cancelProcessing).toHaveBeenCalledWith(
          batchId,
          FileType.CAMPAIGN_XLSX
        );
      });

      it('should cancel processing for reporting CSV', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('reporting.csv', 1024 * 1024, 'text/csv');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.REPORTING_CSV);
        });

        const batchId = mockServiceInstance.startPolling.mock.calls[0][0];

        await act(async () => {
          await result.current.cancelProcessing(ProcessingFileType.REPORTING_CSV);
        });

        expect(mockServiceInstance.cancelProcessing).toHaveBeenCalledWith(
          batchId,
          FileType.REPORTING_CSV
        );
      });
    });

    describe('upload blocking during active processing', () => {
      it('should block upload when same file type is processing', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        // Simulate processing state
        act(() => {
          mockCallbacks.onProgressUpdate(createMockProgress({ 
            status: ProcessingStatus.PROCESSING
          }));
        });

        expect(result.current.canUpload(ProcessingFileType.CAMPAIGN_XLSX)).toBe(false);
      });

      it('should allow upload for different file type during processing', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        // Simulate processing state for campaign
        act(() => {
          mockCallbacks.onProgressUpdate(createMockProgress({ 
            file_type: FileType.CAMPAIGN_XLSX,
            status: ProcessingStatus.PROCESSING
          }));
        });

        expect(result.current.canUpload(ProcessingFileType.CAMPAIGN_XLSX)).toBe(false);
        expect(result.current.canUpload(ProcessingFileType.REPORTING_CSV)).toBe(true);
      });
    });

    describe('canUpload function logic', () => {
      it('should allow upload when no processing is active', () => {
        const { result } = renderHook(() => useProcessingStatus());

        expect(result.current.canUpload(ProcessingFileType.CAMPAIGN_XLSX)).toBe(true);
        expect(result.current.canUpload(ProcessingFileType.REPORTING_CSV)).toBe(true);
      });

      it('should allow upload when previous processing completed', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        // Complete processing
        act(() => {
          mockCallbacks.onProgressUpdate(createMockProgress({ 
            status: ProcessingStatus.COMPLETED
          }));
          mockCallbacks.onCompletion(createMockStatusResponse());
        });

        expect(result.current.canUpload(ProcessingFileType.CAMPAIGN_XLSX)).toBe(true);
      });

      it('should allow upload when previous processing failed', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        // Simulate processing failure
        act(() => {
          mockCallbacks.onProgressUpdate(createMockProgress({ 
            status: ProcessingStatus.ERROR
          }));
        });

        expect(result.current.canUpload(ProcessingFileType.CAMPAIGN_XLSX)).toBe(true);
      });
    });

    describe('processing state per file type', () => {
      it('should track processing state independently for each file type', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const campaignFile = createMockFile('campaign.xlsx');
        const reportingFile = createMockFile('reporting.csv', 1024 * 1024, 'text/csv');

        // Start campaign processing
        await act(async () => {
          await result.current.startProcessing(campaignFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        act(() => {
          mockCallbacks.onProgressUpdate(createMockProgress({ 
            file_type: FileType.CAMPAIGN_XLSX,
            status: ProcessingStatus.PROCESSING
          }));
        });

        expect(result.current.canUpload(ProcessingFileType.CAMPAIGN_XLSX)).toBe(false);
        expect(result.current.canUpload(ProcessingFileType.REPORTING_CSV)).toBe(true);

        // Start reporting processing
        await act(async () => {
          await result.current.startProcessing(reportingFile, ProcessingFileType.REPORTING_CSV);
        });

        act(() => {
          mockCallbacks.onProgressUpdate(createMockProgress({ 
            file_type: FileType.REPORTING_CSV,
            status: ProcessingStatus.PROCESSING
          }));
        });

        expect(result.current.canUpload(ProcessingFileType.CAMPAIGN_XLSX)).toBe(false);
        expect(result.current.canUpload(ProcessingFileType.REPORTING_CSV)).toBe(false);
      });
    });
  });

  describe('7. React Integration Tests', () => {
    describe('hook state triggers component re-renders', () => {
      it('should trigger re-render when processing state changes', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        const initialRenderCount = result.all.length;

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        act(() => {
          mockCallbacks.onProgressUpdate(createMockProgress());
        });

        expect(result.all.length).toBeGreaterThan(initialRenderCount);
      });

      it('should trigger re-render when error state changes', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        const initialRenderCount = result.all.length;

        act(() => {
          mockCallbacks.onErrorUpdate([createMockError()]);
        });

        expect(result.all.length).toBeGreaterThan(initialRenderCount);
      });
    });

    describe('useEffect cleanup on unmount', () => {
      it('should cleanup service and stop polling on unmount', async () => {
        const { result, unmount } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        unmount();

        expect(mockServiceInstance.cleanup).toHaveBeenCalledTimes(1);
      });
    });

    describe('state updates are batched properly', () => {
      it('should batch state updates to prevent excessive re-renders', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        const renderCountBefore = result.all.length;

        // Multiple simultaneous updates should be batched
        act(() => {
          mockCallbacks.onProgressUpdate(createMockProgress({ progress: 25 }));
          mockCallbacks.onErrorUpdate([createMockError()]);
        });

        // Should only cause one additional render due to batching
        expect(result.all.length - renderCountBefore).toBeLessThanOrEqual(2);
      });
    });

    describe('concurrent state updates don\'t conflict', () => {
      it('should handle concurrent updates to different file types', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const campaignFile = createMockFile('campaign.xlsx');
        const reportingFile = createMockFile('reporting.csv', 1024 * 1024, 'text/csv');

        await act(async () => {
          await result.current.startProcessing(campaignFile, ProcessingFileType.CAMPAIGN_XLSX);
          await result.current.startProcessing(reportingFile, ProcessingFileType.REPORTING_CSV);
        });

        // Simulate concurrent updates
        act(() => {
          mockCallbacks.onProgressUpdate(createMockProgress({ 
            file_type: FileType.CAMPAIGN_XLSX,
            progress: 25
          }));
          mockCallbacks.onProgressUpdate(createMockProgress({ 
            file_type: FileType.REPORTING_CSV,
            progress: 50
          }));
        });

        expect(result.current.processingState.campaign_xlsx?.progress).toBe(25);
        expect(result.current.processingState.reporting_csv?.progress).toBe(50);
      });
    });

    describe('hook performance with frequent updates', () => {
      it('should handle high-frequency progress updates efficiently', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        const startTime = Date.now();

        // Simulate rapid progress updates
        act(() => {
          for (let i = 0; i < 100; i++) {
            mockCallbacks.onProgressUpdate(createMockProgress({ 
              progress: 25,
              updated_at: new Date().toISOString()
            }));
          }
        });

        const endTime = Date.now();
        expect(endTime - startTime).toBeLessThan(1000); // Should complete within 1 second
      });
    });

    describe('memory leaks prevention', () => {
      it('should not create memory leaks with repeated mount/unmount cycles', () => {
        const mounts = [];

        for (let i = 0; i < 10; i++) {
          const { unmount } = renderHook(() => useProcessingStatus());
          mounts.push(unmount);
        }

        mounts.forEach(unmount => unmount());

        expect(MockedProcessingStatusService).toHaveBeenCalledTimes(10);
        expect(mockServiceInstance.cleanup).toHaveBeenCalledTimes(10);
      });
    });
  });

  describe('8. UI Component Integration Tests', () => {
    describe('data format for ProcessingProgressIndicator', () => {
      it('should provide progress data compatible with ProcessingProgressIndicator', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        const mockProgress = createMockProgress({
          stage: ProcessingStage.VALIDATE,
          progress: 50,
          status: ProcessingStatus.PROCESSING,
          file_type: FileType.CAMPAIGN_XLSX
        });

        act(() => {
          mockCallbacks.onProgressUpdate(mockProgress);
        });

        expect(result.current.currentProgress).toMatchObject({
          stage: ProcessingStage.VALIDATE,
          progress: 50,
          status: ProcessingStatus.PROCESSING,
          file_type: FileType.CAMPAIGN_XLSX,
          batch_id: expect.any(String),
          started_at: expect.any(String),
          updated_at: expect.any(String)
        });
      });

      it('should provide null currentProgress when no processing is active', () => {
        const { result } = renderHook(() => useProcessingStatus());

        expect(result.current.currentProgress).toBeNull();
      });
    });

    describe('data format for UploadControlPanel', () => {
      it('should provide processing state data for upload control', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        act(() => {
          mockCallbacks.onProgressUpdate(createMockProgress({ 
            status: ProcessingStatus.PROCESSING
          }));
        });

        expect(result.current.processingState).toMatchObject({
          campaign_xlsx: expect.objectContaining({
            status: ProcessingStatus.PROCESSING
          }),
          reporting_csv: null,
          errors: expect.any(Array),
          last_updated: expect.any(String)
        });

        expect(result.current.isProcessing).toBe(true);
      });

      it('should provide upload blocking status for each file type', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        act(() => {
          mockCallbacks.onProgressUpdate(createMockProgress({ 
            file_type: FileType.CAMPAIGN_XLSX,
            status: ProcessingStatus.PROCESSING
          }));
        });

        expect(result.current.canUpload(ProcessingFileType.CAMPAIGN_XLSX)).toBe(false);
        expect(result.current.canUpload(ProcessingFileType.REPORTING_CSV)).toBe(true);
      });
    });

    describe('data format for ErrorDisplayPanel', () => {
      it('should provide error data compatible with ErrorDisplayPanel', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        const mockErrors = [
          createMockError({
            severity: ErrorSeverity.ERROR,
            message: 'Critical validation error',
            category: ErrorCategory.VALIDATION
          }),
          createMockError({
            severity: ErrorSeverity.WARNING,
            message: 'Minor formatting issue',
            category: ErrorCategory.PARSING
          })
        ];

        act(() => {
          mockCallbacks.onErrorUpdate(mockErrors);
        });

        expect(result.current.errors).toEqual(
          expect.arrayContaining([
            expect.objectContaining({
              error_id: expect.any(String),
              timestamp: expect.any(String),
              category: ErrorCategory.VALIDATION,
              severity: ErrorSeverity.ERROR,
              code: expect.any(String),
              message: 'Critical validation error',
              context: expect.any(Object)
            }),
            expect.objectContaining({
              severity: ErrorSeverity.WARNING,
              message: 'Minor formatting issue',
              category: ErrorCategory.PARSING
            })
          ])
        );

        expect(result.current.hasErrors).toBe(true);
      });

      it('should provide clearErrors function for error panel', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        act(() => {
          mockCallbacks.onErrorUpdate([createMockError()]);
        });

        expect(result.current.hasErrors).toBe(true);

        act(() => {
          result.current.clearErrors();
        });

        expect(result.current.errors).toEqual([]);
        expect(result.current.hasErrors).toBe(false);
      });
    });

    describe('processing state flags for UI components', () => {
      it('should provide comprehensive status flags for UI state management', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        // Initial state
        expect(result.current.isProcessing).toBe(false);
        expect(result.current.hasErrors).toBe(false);

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        // Processing state
        act(() => {
          mockCallbacks.onProgressUpdate(createMockProgress({ 
            status: ProcessingStatus.PROCESSING
          }));
        });

        expect(result.current.isProcessing).toBe(true);

        // Error state
        act(() => {
          mockCallbacks.onErrorUpdate([createMockError()]);
        });

        expect(result.current.hasErrors).toBe(true);

        // Completion state
        act(() => {
          mockCallbacks.onCompletion(createMockStatusResponse());
        });

        expect(result.current.isProcessing).toBe(false);
      });
    });

    describe('error data for error display component', () => {
      it('should provide time-ordered error arrays for display', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        const timeOrderedErrors = [
          createMockError({ 
            error_id: 'error-1',
            timestamp: '2025-09-09T10:00:10Z',
            message: 'First error'
          }),
          createMockError({ 
            error_id: 'error-2',
            timestamp: '2025-09-09T10:00:20Z',
            message: 'Second error'
          })
        ];

        act(() => {
          mockCallbacks.onErrorUpdate(timeOrderedErrors);
        });

        expect(result.current.errors).toHaveLength(2);
        expect(result.current.errors[0].timestamp).toBe('2025-09-09T10:00:10Z');
        expect(result.current.errors[1].timestamp).toBe('2025-09-09T10:00:20Z');
      });
    });

    describe('progress data for progress indicator', () => {
      it('should provide stage and progress data for visual indicators', async () => {
        const { result } = renderHook(() => useProcessingStatus());
        const mockFile = createMockFile('campaign.xlsx');

        await act(async () => {
          await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
        });

        const progressStages: Array<{ stage: ProcessingStage; progress: 25 | 50 | 75 | 100 }> = [
          { stage: ProcessingStage.PARSE, progress: 25 },
          { stage: ProcessingStage.VALIDATE, progress: 50 },
          { stage: ProcessingStage.CLASSIFY, progress: 75 },
          { stage: ProcessingStage.COMPLETE, progress: 100 }
        ];

        progressStages.forEach((stageData) => {
          act(() => {
            mockCallbacks.onProgressUpdate(createMockProgress(stageData));
          });

          expect(result.current.currentProgress?.stage).toBe(stageData.stage);
          expect(result.current.currentProgress?.progress).toBe(stageData.progress);
        });
      });
    });
  });

  describe('Edge Cases and Error Scenarios', () => {
    it('should handle service initialization failure gracefully', () => {
      MockedProcessingStatusService.mockImplementation(() => {
        throw new Error('Service initialization failed');
      });

      expect(() => renderHook(() => useProcessingStatus())).toThrow('Service initialization failed');
    });

    it('should handle missing file parameter in startProcessing', async () => {
      const { result } = renderHook(() => useProcessingStatus());

      await expect(
        act(async () => {
          await result.current.startProcessing(null as any, ProcessingFileType.CAMPAIGN_XLSX);
        })
      ).rejects.toThrow('File is required');
    });

    it('should handle invalid file type parameter', async () => {
      const { result } = renderHook(() => useProcessingStatus());
      const mockFile = createMockFile('test.xlsx');

      await expect(
        act(async () => {
          await result.current.startProcessing(mockFile, 'invalid_type' as any);
        })
      ).rejects.toThrow('Invalid file type');
    });

    it('should handle cancelProcessing when no processing is active', async () => {
      const { result } = renderHook(() => useProcessingStatus());

      await expect(
        act(async () => {
          await result.current.cancelProcessing(ProcessingFileType.CAMPAIGN_XLSX);
        })
      ).rejects.toThrow('No active processing to cancel');
    });

    it('should handle rapid successive startProcessing calls', async () => {
      const { result } = renderHook(() => useProcessingStatus());
      const mockFile1 = createMockFile('campaign1.xlsx');
      const mockFile2 = createMockFile('campaign2.xlsx');

      await act(async () => {
        await result.current.startProcessing(mockFile1, ProcessingFileType.CAMPAIGN_XLSX);
      });

      await expect(
        act(async () => {
          await result.current.startProcessing(mockFile2, ProcessingFileType.CAMPAIGN_XLSX);
        })
      ).rejects.toThrow('Processing already in progress for this file type');
    });

    it('should handle service polling failure scenarios', async () => {
      const { result } = renderHook(() => useProcessingStatus());
      const mockFile = createMockFile('campaign.xlsx');

      await act(async () => {
        await result.current.startProcessing(mockFile, ProcessingFileType.CAMPAIGN_XLSX);
      });

      act(() => {
        mockCallbacks.onFailure({ 
          code: 'NETWORK_ERROR', 
          message: 'Network connection failed',
          details: 'Unable to connect to processing service'
        });
      });

      expect(result.current.processingState.campaign_xlsx?.status).toBe(ProcessingStatus.ERROR);
    });
  });
});