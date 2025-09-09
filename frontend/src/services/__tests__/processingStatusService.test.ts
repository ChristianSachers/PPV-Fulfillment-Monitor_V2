/**
 * Processing Status Service Tests
 * Comprehensive test suite for HTTP polling service following TDD methodology
 * Tests the 2-second polling mechanism for processing status updates
 */

import axios from 'axios';
import {
  ProcessingStatusService,
  StatusCallbacks,
  PollingConfiguration
} from '../processingStatusService';
import {
  ProcessingStatusResponse,
  ProcessingProgress,
  ProcessingError,
  ProcessingState,
  ProcessingStatus,
  ProcessingStage,
  FileType,
  ErrorCategory,
  ErrorSeverity
} from '../../types/processing';

// Mock axios
jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

// Mock window focus/blur events
Object.defineProperty(document, 'hidden', {
  writable: true,
  value: false,
});

Object.defineProperty(document, 'visibilityState', {
  writable: true,
  value: 'visible',
});

const mockVisibilityChangeEvent = () => {
  const event = new Event('visibilitychange');
  document.dispatchEvent(event);
};

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

describe('ProcessingStatusService', () => {
  let service: ProcessingStatusService;
  let mockCallbacks: StatusCallbacks;

  beforeEach(() => {
    jest.clearAllMocks();
    jest.useFakeTimers();
    
    // Reset document visibility state
    (document as any).hidden = false;
    (document as any).visibilityState = 'visible';

    mockCallbacks = {
      onProgressUpdate: jest.fn(),
      onErrorUpdate: jest.fn(),
      onCompletion: jest.fn(),
      onFailure: jest.fn()
    };

    service = new ProcessingStatusService();
  });

  afterEach(() => {
    service.cleanup();
    jest.useRealTimers();
  });

  describe('1. Polling Mechanism Tests', () => {
    describe('2-second polling interval accuracy', () => {
      it('should poll status endpoint exactly every 2 seconds', async () => {
        const batchId = 'batch-123';
        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse() });

        service.startPolling(batchId, mockCallbacks);

        // Initial call should happen immediately
        expect(mockedAxios.get).toHaveBeenCalledTimes(1);
        expect(mockedAxios.get).toHaveBeenCalledWith(`/api/upload/status/${batchId}`);

        // Advance timer by 2 seconds
        jest.advanceTimersByTime(2000);
        expect(mockedAxios.get).toHaveBeenCalledTimes(2);

        // Advance another 2 seconds
        jest.advanceTimersByTime(2000);
        expect(mockedAxios.get).toHaveBeenCalledTimes(3);

        // Advance by 1.5 seconds (should not trigger another call)
        jest.advanceTimersByTime(1500);
        expect(mockedAxios.get).toHaveBeenCalledTimes(3);

        // Complete the remaining 0.5 seconds
        jest.advanceTimersByTime(500);
        expect(mockedAxios.get).toHaveBeenCalledTimes(4);
      });

      it('should maintain 2-second interval even with slow API responses', async () => {
        const batchId = 'batch-123';
        let resolveResponse: (value: any) => void;
        
        mockedAxios.get.mockImplementation(() => {
          return new Promise((resolve) => {
            resolveResponse = resolve;
          });
        });

        service.startPolling(batchId, mockCallbacks);

        // Initial call
        expect(mockedAxios.get).toHaveBeenCalledTimes(1);

        // Simulate slow response (1.5 seconds)
        jest.advanceTimersByTime(1500);
        resolveResponse!({ data: createMockStatusResponse() });
        
        // Wait for promise resolution
        await Promise.resolve();

        // Next poll should still happen at exactly 2 seconds from start
        jest.advanceTimersByTime(500);
        expect(mockedAxios.get).toHaveBeenCalledTimes(2);
      });

      it('should not drift in polling interval over multiple cycles', async () => {
        const batchId = 'batch-123';
        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse() });

        service.startPolling(batchId, mockCallbacks);

        // Test 10 polling cycles
        for (let i = 1; i <= 10; i++) {
          jest.advanceTimersByTime(2000);
          expect(mockedAxios.get).toHaveBeenCalledTimes(i + 1);
        }
      });
    });

    describe('polling start/stop functionality', () => {
      it('should start polling when startPolling is called', () => {
        const batchId = 'batch-123';
        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse() });

        service.startPolling(batchId, mockCallbacks);

        expect(mockedAxios.get).toHaveBeenCalledWith(`/api/upload/status/${batchId}`);
      });

      it('should stop polling when stopPolling is called', () => {
        const batchId = 'batch-123';
        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse() });

        service.startPolling(batchId, mockCallbacks);
        expect(mockedAxios.get).toHaveBeenCalledTimes(1);

        service.stopPolling(batchId);

        // Advance time and verify no more calls
        jest.advanceTimersByTime(10000);
        expect(mockedAxios.get).toHaveBeenCalledTimes(1);
      });

      it('should handle stopping non-existent polling session gracefully', () => {
        expect(() => service.stopPolling('non-existent-batch')).not.toThrow();
      });
    });

    describe('polling pause on window blur/inactive', () => {
      it('should pause polling when window becomes hidden', async () => {
        const batchId = 'batch-123';
        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse() });

        service.startPolling(batchId, mockCallbacks);
        expect(mockedAxios.get).toHaveBeenCalledTimes(1);

        // Simulate window becoming hidden
        (document as any).hidden = true;
        (document as any).visibilityState = 'hidden';
        mockVisibilityChangeEvent();

        // Advance time - should not poll while hidden
        jest.advanceTimersByTime(10000);
        expect(mockedAxios.get).toHaveBeenCalledTimes(1);
      });

      it('should pause polling when window loses focus', async () => {
        const batchId = 'batch-123';
        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse() });

        service.startPolling(batchId, mockCallbacks);
        expect(mockedAxios.get).toHaveBeenCalledTimes(1);

        // Simulate window blur
        mockWindowBlurEvent();

        // Advance time - should not poll while blurred
        jest.advanceTimersByTime(10000);
        expect(mockedAxios.get).toHaveBeenCalledTimes(1);
      });
    });

    describe('polling resume on window focus/active', () => {
      it('should resume polling when window becomes visible', async () => {
        const batchId = 'batch-123';
        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse() });

        service.startPolling(batchId, mockCallbacks);
        
        // Hide window
        (document as any).hidden = true;
        (document as any).visibilityState = 'hidden';
        mockVisibilityChangeEvent();

        // Show window again
        (document as any).hidden = false;
        (document as any).visibilityState = 'visible';
        mockVisibilityChangeEvent();

        // Should immediately poll and resume normal schedule
        expect(mockedAxios.get).toHaveBeenCalledTimes(2);

        jest.advanceTimersByTime(2000);
        expect(mockedAxios.get).toHaveBeenCalledTimes(3);
      });

      it('should resume polling when window regains focus', async () => {
        const batchId = 'batch-123';
        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse() });

        service.startPolling(batchId, mockCallbacks);
        
        // Blur window
        mockWindowBlurEvent();

        // Focus window again
        mockWindowFocusEvent();

        // Should immediately poll and resume normal schedule
        expect(mockedAxios.get).toHaveBeenCalledTimes(2);

        jest.advanceTimersByTime(2000);
        expect(mockedAxios.get).toHaveBeenCalledTimes(3);
      });
    });

    describe('multiple concurrent polling sessions', () => {
      it('should handle multiple batch IDs simultaneously', () => {
        const batchId1 = 'batch-123';
        const batchId2 = 'batch-456';
        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse() });

        service.startPolling(batchId1, mockCallbacks);
        service.startPolling(batchId2, {...mockCallbacks});

        expect(mockedAxios.get).toHaveBeenCalledWith(`/api/upload/status/${batchId1}`);
        expect(mockedAxios.get).toHaveBeenCalledWith(`/api/upload/status/${batchId2}`);

        jest.advanceTimersByTime(2000);
        expect(mockedAxios.get).toHaveBeenCalledTimes(4); // 2 initial + 2 after interval
      });

      it('should stop individual polling sessions without affecting others', () => {
        const batchId1 = 'batch-123';
        const batchId2 = 'batch-456';
        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse() });

        service.startPolling(batchId1, mockCallbacks);
        service.startPolling(batchId2, {...mockCallbacks});

        service.stopPolling(batchId1);

        jest.advanceTimersByTime(2000);
        expect(mockedAxios.get).toHaveBeenCalledTimes(3); // 2 initial + 1 for batchId2
      });
    });

    describe('polling cleanup on component unmount', () => {
      it('should cleanup all polling sessions on service cleanup', () => {
        const batchId1 = 'batch-123';
        const batchId2 = 'batch-456';
        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse() });

        service.startPolling(batchId1, mockCallbacks);
        service.startPolling(batchId2, {...mockCallbacks});

        service.cleanup();

        jest.advanceTimersByTime(10000);
        expect(mockedAxios.get).toHaveBeenCalledTimes(2); // Only initial calls
      });

      it('should remove event listeners on cleanup', () => {
        const removeEventListenerSpy = jest.spyOn(document, 'removeEventListener');
        const windowRemoveEventListenerSpy = jest.spyOn(window, 'removeEventListener');

        service.cleanup();

        expect(removeEventListenerSpy).toHaveBeenCalledWith('visibilitychange', expect.any(Function));
        expect(windowRemoveEventListenerSpy).toHaveBeenCalledWith('focus', expect.any(Function));
        expect(windowRemoveEventListenerSpy).toHaveBeenCalledWith('blur', expect.any(Function));
      });
    });
  });

  describe('2. API Integration Tests', () => {
    describe('status endpoint polling with batch_id', () => {
      it('should call status endpoint with correct batch_id', async () => {
        const batchId = 'test-batch-123';
        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse() });

        service.startPolling(batchId, mockCallbacks);

        expect(mockedAxios.get).toHaveBeenCalledWith(`/api/upload/status/${batchId}`);
      });

      it('should handle status response and trigger callbacks', async () => {
        const batchId = 'batch-123';
        const mockProgress = createMockProgress();
        const mockState = createMockState({ campaign_xlsx: mockProgress });
        const mockResponse = createMockStatusResponse(true, mockState);

        mockedAxios.get.mockResolvedValue({ data: mockResponse });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve(); // Wait for async operations

        expect(mockCallbacks.onProgressUpdate).toHaveBeenCalledWith(mockProgress);
      });
    });

    describe('progress endpoint integration', () => {
      it('should handle 25% progress (parse stage)', async () => {
        const batchId = 'batch-123';
        const mockProgress = createMockProgress({
          stage: ProcessingStage.PARSE,
          progress: 25
        });
        const mockState = createMockState({ campaign_xlsx: mockProgress });

        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse(true, mockState) });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onProgressUpdate).toHaveBeenCalledWith(
          expect.objectContaining({
            stage: ProcessingStage.PARSE,
            progress: 25
          })
        );
      });

      it('should handle 50% progress (validate stage)', async () => {
        const batchId = 'batch-123';
        const mockProgress = createMockProgress({
          stage: ProcessingStage.VALIDATE,
          progress: 50
        });
        const mockState = createMockState({ campaign_xlsx: mockProgress });

        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse(true, mockState) });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onProgressUpdate).toHaveBeenCalledWith(
          expect.objectContaining({
            stage: ProcessingStage.VALIDATE,
            progress: 50
          })
        );
      });

      it('should handle 75% progress (classify stage)', async () => {
        const batchId = 'batch-123';
        const mockProgress = createMockProgress({
          stage: ProcessingStage.CLASSIFY,
          progress: 75
        });
        const mockState = createMockState({ campaign_xlsx: mockProgress });

        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse(true, mockState) });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onProgressUpdate).toHaveBeenCalledWith(
          expect.objectContaining({
            stage: ProcessingStage.CLASSIFY,
            progress: 75
          })
        );
      });

      it('should handle 100% progress (complete stage)', async () => {
        const batchId = 'batch-123';
        const mockProgress = createMockProgress({
          stage: ProcessingStage.COMPLETE,
          progress: 100,
          status: ProcessingStatus.COMPLETED,
          completed_at: '2025-09-09T10:05:00Z'
        });
        const mockState = createMockState({ campaign_xlsx: mockProgress });

        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse(true, mockState) });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onProgressUpdate).toHaveBeenCalledWith(
          expect.objectContaining({
            stage: ProcessingStage.COMPLETE,
            progress: 100,
            status: ProcessingStatus.COMPLETED
          })
        );
      });
    });

    describe('processing state endpoint per file type', () => {
      it('should handle campaign XLSX processing state', async () => {
        const batchId = 'batch-123';
        const mockProgress = createMockProgress({
          file_type: FileType.CAMPAIGN_XLSX
        });
        const mockState = createMockState({ campaign_xlsx: mockProgress });

        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse(true, mockState) });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onProgressUpdate).toHaveBeenCalledWith(
          expect.objectContaining({
            file_type: FileType.CAMPAIGN_XLSX
          })
        );
      });

      it('should handle reporting CSV processing state', async () => {
        const batchId = 'batch-123';
        const mockProgress = createMockProgress({
          file_type: FileType.REPORTING_CSV
        });
        const mockState = createMockState({ reporting_csv: mockProgress });

        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse(true, mockState) });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onProgressUpdate).toHaveBeenCalledWith(
          expect.objectContaining({
            file_type: FileType.REPORTING_CSV
          })
        );
      });

      it('should handle both file types processing simultaneously', async () => {
        const batchId = 'batch-123';
        const campaignProgress = createMockProgress({
          file_type: FileType.CAMPAIGN_XLSX,
          stage: ProcessingStage.PARSE,
          progress: 25
        });
        const reportingProgress = createMockProgress({
          file_type: FileType.REPORTING_CSV,
          stage: ProcessingStage.VALIDATE,
          progress: 50
        });
        const mockState = createMockState({
          campaign_xlsx: campaignProgress,
          reporting_csv: reportingProgress
        });

        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse(true, mockState) });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onProgressUpdate).toHaveBeenCalledWith(campaignProgress);
        expect(mockCallbacks.onProgressUpdate).toHaveBeenCalledWith(reportingProgress);
      });
    });

    describe('error endpoint integration', () => {
      it('should handle time-ordered error responses', async () => {
        const batchId = 'batch-123';
        const error1 = createMockError({
          timestamp: '2025-09-09T10:00:10Z',
          message: 'First error'
        });
        const error2 = createMockError({
          timestamp: '2025-09-09T10:00:20Z',
          message: 'Second error'
        });
        const mockState = createMockState({
          errors: [error1, error2]
        });

        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse(true, mockState) });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onErrorUpdate).toHaveBeenCalledWith([error1, error2]);
      });

      it('should handle different error categories and severities', async () => {
        const batchId = 'batch-123';
        const validationError = createMockError({
          category: ErrorCategory.VALIDATION,
          severity: ErrorSeverity.ERROR
        });
        const parsingWarning = createMockError({
          category: ErrorCategory.PARSING,
          severity: ErrorSeverity.WARNING
        });
        const mockState = createMockState({
          errors: [validationError, parsingWarning]
        });

        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse(true, mockState) });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onErrorUpdate).toHaveBeenCalledWith([validationError, parsingWarning]);
      });
    });

    describe('cancel endpoint integration', () => {
      it('should call cancel endpoint when cancelProcessing is called', async () => {
        const batchId = 'batch-123';
        mockedAxios.post.mockResolvedValue({ data: { success: true } });

        await service.cancelProcessing(batchId, FileType.CAMPAIGN_XLSX);

        expect(mockedAxios.post).toHaveBeenCalledWith(`/api/upload/cancel/${batchId}`, {
          file_type: FileType.CAMPAIGN_XLSX
        });
      });

      it('should handle cancelled status in polling response', async () => {
        const batchId = 'batch-123';
        const cancelledProgress = createMockProgress({
          status: ProcessingStatus.CANCELLED
        });
        const mockState = createMockState({ campaign_xlsx: cancelledProgress });

        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse(true, mockState) });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onProgressUpdate).toHaveBeenCalledWith(
          expect.objectContaining({
            status: ProcessingStatus.CANCELLED
          })
        );
      });
    });

    describe('API response format validation', () => {
      it('should validate ProcessingStatusResponse format', async () => {
        const batchId = 'batch-123';
        const invalidResponse = { invalid: 'format' };

        mockedAxios.get.mockResolvedValue({ data: invalidResponse });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onFailure).toHaveBeenCalledWith(
          expect.objectContaining({
            message: expect.stringContaining('Invalid response format')
          })
        );
      });

      it('should validate ProcessingProgress format', async () => {
        const batchId = 'batch-123';
        const invalidProgress = { batch_id: 'test', invalid: 'progress' };
        const mockState = createMockState({ campaign_xlsx: invalidProgress as any });

        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse(true, mockState) });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onFailure).toHaveBeenCalledWith(
          expect.objectContaining({
            message: expect.stringContaining('Invalid progress format')
          })
        );
      });
    });
  });

  describe('3. Connection Resilience Tests', () => {
    describe('network error handling and recovery', () => {
      it('should handle network timeout errors', async () => {
        const batchId = 'batch-123';
        const timeoutError = new Error('Network timeout');
        timeoutError.name = 'TIMEOUT';

        mockedAxios.get.mockRejectedValueOnce(timeoutError);
        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse() });

        service.startPolling(batchId, mockCallbacks);

        // Initial call fails
        await Promise.resolve();
        
        // Next poll should succeed
        jest.advanceTimersByTime(2000);
        await Promise.resolve();

        expect(mockedAxios.get).toHaveBeenCalledTimes(2);
        expect(mockCallbacks.onFailure).not.toHaveBeenCalled();
      });

      it('should handle connection refused errors', async () => {
        const batchId = 'batch-123';
        const connectionError = new Error('Connection refused');
        connectionError.name = 'ECONNREFUSED';

        mockedAxios.get.mockRejectedValueOnce(connectionError);
        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse() });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();
        jest.advanceTimersByTime(2000);
        await Promise.resolve();

        expect(mockedAxios.get).toHaveBeenCalledTimes(2);
      });
    });

    describe('exponential backoff retry logic', () => {
      it('should implement exponential backoff for consecutive failures', async () => {
        const batchId = 'batch-123';
        const networkError = new Error('Network Error');

        mockedAxios.get.mockRejectedValue(networkError);

        service.startPolling(batchId, mockCallbacks);

        // First failure - should retry after 2 seconds (normal interval)
        await Promise.resolve();
        jest.advanceTimersByTime(2000);
        
        // Second failure - should retry after 4 seconds (2 * 2)
        await Promise.resolve();
        jest.advanceTimersByTime(4000);
        
        // Third failure - should retry after 8 seconds (4 * 2)
        await Promise.resolve();
        jest.advanceTimersByTime(8000);

        expect(mockedAxios.get).toHaveBeenCalledTimes(4); // Initial + 3 retries
      });

      it('should reset backoff interval on successful response', async () => {
        const batchId = 'batch-123';
        const networkError = new Error('Network Error');

        mockedAxios.get.mockRejectedValueOnce(networkError);
        mockedAxios.get.mockResolvedValueOnce({ data: createMockStatusResponse() });
        mockedAxios.get.mockRejectedValueOnce(networkError);

        service.startPolling(batchId, mockCallbacks);

        // First failure
        await Promise.resolve();
        jest.advanceTimersByTime(2000);
        
        // Success - should reset backoff
        await Promise.resolve();
        jest.advanceTimersByTime(2000);
        
        // Another failure - should start with normal interval again
        await Promise.resolve();
        jest.advanceTimersByTime(2000);

        expect(mockedAxios.get).toHaveBeenCalledTimes(4);
      });

      it('should cap maximum backoff interval at 30 seconds', async () => {
        const batchId = 'batch-123';
        const networkError = new Error('Network Error');

        mockedAxios.get.mockRejectedValue(networkError);

        service.startPolling(batchId, mockCallbacks);

        // Simulate many consecutive failures
        for (let i = 0; i < 10; i++) {
          await Promise.resolve();
          // Should eventually cap at 30 seconds
          const expectedInterval = Math.min(2000 * Math.pow(2, i), 30000);
          jest.advanceTimersByTime(expectedInterval);
        }

        expect(mockedAxios.get).toHaveBeenCalledTimes(11); // Initial + 10 retries
      });
    });

    describe('connection timeout handling', () => {
      it('should handle request timeout with axios timeout configuration', async () => {
        const batchId = 'batch-123';
        const timeoutError = { code: 'ECONNABORTED', message: 'timeout of 10000ms exceeded' };

        mockedAxios.get.mockRejectedValueOnce(timeoutError);
        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse() });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();
        jest.advanceTimersByTime(2000);
        await Promise.resolve();

        expect(mockedAxios.get).toHaveBeenCalledTimes(2);
      });
    });

    describe('API endpoint unavailability scenarios', () => {
      it('should handle 503 Service Unavailable errors', async () => {
        const batchId = 'batch-123';
        const serviceUnavailableError = {
          response: {
            status: 503,
            data: { detail: 'Service temporarily unavailable' }
          }
        };

        mockedAxios.get.mockRejectedValueOnce(serviceUnavailableError);
        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse() });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();
        jest.advanceTimersByTime(4000); // Should use backoff for server errors
        await Promise.resolve();

        expect(mockedAxios.get).toHaveBeenCalledTimes(2);
      });

      it('should handle 404 Not Found errors (batch not found)', async () => {
        const batchId = 'batch-123';
        const notFoundError = {
          response: {
            status: 404,
            data: { detail: 'Batch not found' }
          }
        };

        mockedAxios.get.mockRejectedValue(notFoundError);

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onFailure).toHaveBeenCalledWith(
          expect.objectContaining({
            message: expect.stringContaining('Batch not found')
          })
        );
      });
    });

    describe('malformed response handling', () => {
      it('should handle JSON parsing errors', async () => {
        const batchId = 'batch-123';
        const malformedResponse = 'invalid json response';

        mockedAxios.get.mockResolvedValueOnce({ data: malformedResponse });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onFailure).toHaveBeenCalledWith(
          expect.objectContaining({
            message: expect.stringContaining('Invalid response format')
          })
        );
      });

      it('should handle responses missing required fields', async () => {
        const batchId = 'batch-123';
        const incompleteResponse = { success: true }; // Missing data and polling_interval

        mockedAxios.get.mockResolvedValueOnce({ data: incompleteResponse });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onFailure).toHaveBeenCalledWith(
          expect.objectContaining({
            message: expect.stringContaining('Invalid response format')
          })
        );
      });
    });

    describe('retry limit and failure recovery', () => {
      it('should stop polling after maximum retry attempts for persistent failures', async () => {
        const batchId = 'batch-123';
        const persistentError = new Error('Persistent network error');

        mockedAxios.get.mockRejectedValue(persistentError);

        service.startPolling(batchId, mockCallbacks);

        // Simulate maximum retries (e.g., 10 attempts)
        for (let i = 0; i < 10; i++) {
          await Promise.resolve();
          jest.advanceTimersByTime(30000); // Use max backoff interval
        }

        expect(mockCallbacks.onFailure).toHaveBeenCalledWith(
          expect.objectContaining({
            message: expect.stringContaining('Maximum retry attempts exceeded')
          })
        );

        // Should stop polling after max retries
        jest.advanceTimersByTime(60000);
        expect(mockedAxios.get).toHaveBeenCalledTimes(10);
      });
    });
  });

  describe('4. Processing State Management Tests', () => {
    describe('status update callbacks with ProcessingProgress', () => {
      it('should trigger onProgressUpdate callback with correct progress data', async () => {
        const batchId = 'batch-123';
        const mockProgress = createMockProgress();
        const mockState = createMockState({ campaign_xlsx: mockProgress });

        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse(true, mockState) });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onProgressUpdate).toHaveBeenCalledWith(mockProgress);
        expect(mockCallbacks.onProgressUpdate).toHaveBeenCalledTimes(1);
      });

      it('should only trigger progress updates when progress changes', async () => {
        const batchId = 'batch-123';
        const mockProgress = createMockProgress();
        const mockState = createMockState({ campaign_xlsx: mockProgress });

        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse(true, mockState) });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();
        
        // Second poll with same progress
        jest.advanceTimersByTime(2000);
        await Promise.resolve();

        expect(mockCallbacks.onProgressUpdate).toHaveBeenCalledTimes(1); // Should not call again
      });
    });

    describe('error state handling', () => {
      it('should trigger onErrorUpdate callback with ProcessingError arrays', async () => {
        const batchId = 'batch-123';
        const mockError = createMockError();
        const mockState = createMockState({ errors: [mockError] });

        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse(true, mockState) });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onErrorUpdate).toHaveBeenCalledWith([mockError]);
      });

      it('should handle processing status ERROR and trigger appropriate callbacks', async () => {
        const batchId = 'batch-123';
        const errorProgress = createMockProgress({
          status: ProcessingStatus.ERROR
        });
        const mockError = createMockError();
        const mockState = createMockState({
          campaign_xlsx: errorProgress,
          errors: [mockError]
        });

        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse(true, mockState) });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onProgressUpdate).toHaveBeenCalledWith(
          expect.objectContaining({
            status: ProcessingStatus.ERROR
          })
        );
        expect(mockCallbacks.onErrorUpdate).toHaveBeenCalledWith([mockError]);
      });
    });

    describe('completion state detection and polling termination', () => {
      it('should detect completion and trigger onCompletion callback', async () => {
        const batchId = 'batch-123';
        const completedProgress = createMockProgress({
          status: ProcessingStatus.COMPLETED,
          stage: ProcessingStage.COMPLETE,
          progress: 100,
          completed_at: '2025-09-09T10:05:00Z'
        });
        const mockState = createMockState({ campaign_xlsx: completedProgress });
        const mockResponse = createMockStatusResponse(true, mockState);

        mockedAxios.get.mockResolvedValue({ data: mockResponse });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onCompletion).toHaveBeenCalledWith(mockResponse);
      });

      it('should stop polling when all processing is completed', async () => {
        const batchId = 'batch-123';
        const completedProgress = createMockProgress({
          status: ProcessingStatus.COMPLETED,
          stage: ProcessingStage.COMPLETE,
          progress: 100
        });
        const mockState = createMockState({ campaign_xlsx: completedProgress });

        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse(true, mockState) });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        // Should stop polling after completion
        jest.advanceTimersByTime(10000);
        expect(mockedAxios.get).toHaveBeenCalledTimes(1);
      });

      it('should continue polling if only one file type is completed', async () => {
        const batchId = 'batch-123';
        const completedProgress = createMockProgress({
          status: ProcessingStatus.COMPLETED,
          file_type: FileType.CAMPAIGN_XLSX
        });
        const processingProgress = createMockProgress({
          status: ProcessingStatus.PROCESSING,
          file_type: FileType.REPORTING_CSV
        });
        const mockState = createMockState({
          campaign_xlsx: completedProgress,
          reporting_csv: processingProgress
        });

        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse(true, mockState) });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        // Should continue polling
        jest.advanceTimersByTime(2000);
        expect(mockedAxios.get).toHaveBeenCalledTimes(2);
      });
    });

    describe('cancelled state handling', () => {
      it('should handle cancelled status and stop polling', async () => {
        const batchId = 'batch-123';
        const cancelledProgress = createMockProgress({
          status: ProcessingStatus.CANCELLED
        });
        const mockState = createMockState({ campaign_xlsx: cancelledProgress });

        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse(true, mockState) });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onProgressUpdate).toHaveBeenCalledWith(
          expect.objectContaining({
            status: ProcessingStatus.CANCELLED
          })
        );

        // Should stop polling after cancellation
        jest.advanceTimersByTime(10000);
        expect(mockedAxios.get).toHaveBeenCalledTimes(1);
      });
    });

    describe('processing stage transitions', () => {
      it('should handle stage progression from parse to complete', async () => {
        const batchId = 'batch-123';
        const progressStages = [
          createMockProgress({ stage: ProcessingStage.PARSE, progress: 25 }),
          createMockProgress({ stage: ProcessingStage.VALIDATE, progress: 50 }),
          createMockProgress({ stage: ProcessingStage.CLASSIFY, progress: 75 }),
          createMockProgress({ stage: ProcessingStage.COMPLETE, progress: 100, status: ProcessingStatus.COMPLETED })
        ];

        progressStages.forEach((progress, index) => {
          const mockState = createMockState({ campaign_xlsx: progress });
          mockedAxios.get.mockResolvedValueOnce({ data: createMockStatusResponse(true, mockState) });
        });

        service.startPolling(batchId, mockCallbacks);

        for (let i = 0; i < progressStages.length; i++) {
          await Promise.resolve();
          expect(mockCallbacks.onProgressUpdate).toHaveBeenNthCalledWith(i + 1, progressStages[i]);
          
          if (i < progressStages.length - 1) {
            jest.advanceTimersByTime(2000);
          }
        }
      });
    });

    describe('batch_id tracking and validation', () => {
      it('should validate batch_id consistency in responses', async () => {
        const batchId = 'batch-123';
        const inconsistentProgress = createMockProgress({
          batch_id: 'different-batch-456'
        });
        const mockState = createMockState({ campaign_xlsx: inconsistentProgress });

        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse(true, mockState) });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onFailure).toHaveBeenCalledWith(
          expect.objectContaining({
            message: expect.stringContaining('Batch ID mismatch')
          })
        );
      });
    });
  });

  describe('5. Performance Optimization Tests', () => {
    describe('window focus/blur polling control', () => {
      it('should pause and resume polling based on window focus state', () => {
        const batchId = 'batch-123';
        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse() });

        service.startPolling(batchId, mockCallbacks);
        expect(mockedAxios.get).toHaveBeenCalledTimes(1);

        // Lose focus
        mockWindowBlurEvent();
        jest.advanceTimersByTime(6000);
        expect(mockedAxios.get).toHaveBeenCalledTimes(1); // No additional calls

        // Regain focus
        mockWindowFocusEvent();
        expect(mockedAxios.get).toHaveBeenCalledTimes(2); // Immediate call on focus

        jest.advanceTimersByTime(2000);
        expect(mockedAxios.get).toHaveBeenCalledTimes(3); // Resume normal polling
      });
    });

    describe('memory cleanup during long polling sessions', () => {
      it('should not accumulate memory leaks during extended polling', async () => {
        const batchId = 'batch-123';
        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse() });

        service.startPolling(batchId, mockCallbacks);

        // Simulate 100 polling cycles
        for (let i = 0; i < 100; i++) {
          jest.advanceTimersByTime(2000);
          await Promise.resolve();
        }

        // Memory usage should remain stable (tested via monitoring tools in real scenarios)
        expect(mockedAxios.get).toHaveBeenCalledTimes(101); // Initial + 100 polls
      });

      it('should cleanup timers properly to prevent memory leaks', () => {
        const batchId = 'batch-123';
        const clearTimeoutSpy = jest.spyOn(global, 'clearTimeout');

        service.startPolling(batchId, mockCallbacks);
        service.stopPolling(batchId);

        expect(clearTimeoutSpy).toHaveBeenCalled();
      });
    });

    describe('request deduplication for rapid calls', () => {
      it('should not send duplicate requests if previous request is still pending', async () => {
        const batchId = 'batch-123';
        let resolveResponse: (value: any) => void;

        mockedAxios.get.mockImplementation(() => {
          return new Promise((resolve) => {
            resolveResponse = resolve;
          });
        });

        service.startPolling(batchId, mockCallbacks);
        expect(mockedAxios.get).toHaveBeenCalledTimes(1);

        // Try to advance time while request is pending
        jest.advanceTimersByTime(2000);
        expect(mockedAxios.get).toHaveBeenCalledTimes(1); // Should not make another request

        // Resolve the pending request
        resolveResponse!({ data: createMockStatusResponse() });
        await Promise.resolve();

        // Now next poll should work
        jest.advanceTimersByTime(2000);
        expect(mockedAxios.get).toHaveBeenCalledTimes(2);
      });
    });

    describe('polling performance under high frequency updates', () => {
      it('should handle rapid state changes efficiently', async () => {
        const batchId = 'batch-123';
        const progressUpdates = [25, 50, 75, 100];
        let updateIndex = 0;

        mockedAxios.get.mockImplementation(() => {
          const progress = createMockProgress({
            progress: progressUpdates[updateIndex % progressUpdates.length] as 25 | 50 | 75 | 100
          });
          updateIndex++;
          const mockState = createMockState({ campaign_xlsx: progress });
          return Promise.resolve({ data: createMockStatusResponse(true, mockState) });
        });

        service.startPolling(batchId, mockCallbacks);

        // Rapid polling cycles
        for (let i = 0; i < 20; i++) {
          await Promise.resolve();
          jest.advanceTimersByTime(2000);
        }

        expect(mockCallbacks.onProgressUpdate).toHaveBeenCalledTimes(21); // Initial + 20 updates
      });
    });

    describe('browser tab switching behavior', () => {
      it('should handle tab visibility changes correctly', () => {
        const batchId = 'batch-123';
        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse() });

        service.startPolling(batchId, mockCallbacks);
        expect(mockedAxios.get).toHaveBeenCalledTimes(1);

        // Tab becomes hidden
        (document as any).hidden = true;
        (document as any).visibilityState = 'hidden';
        mockVisibilityChangeEvent();

        jest.advanceTimersByTime(10000);
        expect(mockedAxios.get).toHaveBeenCalledTimes(1); // No polling while hidden

        // Tab becomes visible again
        (document as any).hidden = false;
        (document as any).visibilityState = 'visible';
        mockVisibilityChangeEvent();

        expect(mockedAxios.get).toHaveBeenCalledTimes(2); // Immediate poll on visible
      });
    });

    describe('background tab polling suspension', () => {
      it('should suspend polling when tab is in background', () => {
        const batchId = 'batch-123';
        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse() });

        service.startPolling(batchId, mockCallbacks);

        // Simulate background tab
        (document as any).visibilityState = 'hidden';
        mockVisibilityChangeEvent();

        jest.advanceTimersByTime(30000); // Long time in background
        expect(mockedAxios.get).toHaveBeenCalledTimes(1); // Only initial call

        // Bring tab to foreground
        (document as any).visibilityState = 'visible';
        mockVisibilityChangeEvent();

        expect(mockedAxios.get).toHaveBeenCalledTimes(2); // Resume polling
      });
    });
  });

  describe('6. Mock Response Integration Tests', () => {
    describe('ProcessingStatusResponse format handling', () => {
      it('should handle successful response format correctly', async () => {
        const batchId = 'batch-123';
        const mockResponse = createMockStatusResponse(true, createMockState());

        mockedAxios.get.mockResolvedValue({ data: mockResponse });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onFailure).not.toHaveBeenCalled();
      });

      it('should handle error response format correctly', async () => {
        const batchId = 'batch-123';
        const mockResponse = createMockStatusResponse(false);

        mockedAxios.get.mockResolvedValue({ data: mockResponse });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onFailure).toHaveBeenCalledWith(
          expect.objectContaining({
            message: 'PROCESSING_ERROR: Processing failed'
          })
        );
      });
    });

    describe('ProcessingProgress updates with equal-stage percentages', () => {
      it('should handle parse stage with 25% progress', async () => {
        const batchId = 'batch-123';
        const progress = createMockProgress({
          stage: ProcessingStage.PARSE,
          progress: 25
        });
        const mockState = createMockState({ campaign_xlsx: progress });

        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse(true, mockState) });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onProgressUpdate).toHaveBeenCalledWith(
          expect.objectContaining({
            stage: ProcessingStage.PARSE,
            progress: 25
          })
        );
      });
    });

    describe('ProcessingError arrays with time-ordered display', () => {
      it('should maintain error chronological order', async () => {
        const batchId = 'batch-123';
        const errors = [
          createMockError({ timestamp: '2025-09-09T10:00:10Z', message: 'First error' }),
          createMockError({ timestamp: '2025-09-09T10:00:20Z', message: 'Second error' }),
          createMockError({ timestamp: '2025-09-09T10:00:30Z', message: 'Third error' })
        ];
        const mockState = createMockState({ errors });

        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse(true, mockState) });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onErrorUpdate).toHaveBeenCalledWith(errors);
      });
    });

    describe('different file types', () => {
      it('should handle Campaign XLSX processing correctly', async () => {
        const batchId = 'batch-123';
        const progress = createMockProgress({ file_type: FileType.CAMPAIGN_XLSX });
        const mockState = createMockState({ campaign_xlsx: progress });

        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse(true, mockState) });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onProgressUpdate).toHaveBeenCalledWith(
          expect.objectContaining({
            file_type: FileType.CAMPAIGN_XLSX
          })
        );
      });

      it('should handle Reporting CSV processing correctly', async () => {
        const batchId = 'batch-123';
        const progress = createMockProgress({ file_type: FileType.REPORTING_CSV });
        const mockState = createMockState({ reporting_csv: progress });

        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse(true, mockState) });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onProgressUpdate).toHaveBeenCalledWith(
          expect.objectContaining({
            file_type: FileType.REPORTING_CSV
          })
        );
      });
    });

    describe('structured error responses with contextual information', () => {
      it('should handle validation errors with context', async () => {
        const batchId = 'batch-123';
        const error = createMockError({
          category: ErrorCategory.VALIDATION,
          context: {
            file_type: FileType.CAMPAIGN_XLSX,
            column: 'budget',
            row: 5,
            value: 'invalid_amount'
          }
        });
        const mockState = createMockState({ errors: [error] });

        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse(true, mockState) });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onErrorUpdate).toHaveBeenCalledWith([
          expect.objectContaining({
            category: ErrorCategory.VALIDATION,
            context: expect.objectContaining({
              file_type: FileType.CAMPAIGN_XLSX,
              column: 'budget',
              row: 5,
              value: 'invalid_amount'
            })
          })
        ]);
      });
    });

    describe('processing completion vs error vs cancellation scenarios', () => {
      it('should handle successful completion scenario', async () => {
        const batchId = 'batch-123';
        const completedProgress = createMockProgress({
          status: ProcessingStatus.COMPLETED,
          stage: ProcessingStage.COMPLETE,
          progress: 100,
          completed_at: '2025-09-09T10:05:00Z'
        });
        const mockState = createMockState({ campaign_xlsx: completedProgress });
        const mockResponse = createMockStatusResponse(true, mockState);

        mockedAxios.get.mockResolvedValue({ data: mockResponse });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onCompletion).toHaveBeenCalledWith(mockResponse);
        expect(mockCallbacks.onProgressUpdate).toHaveBeenCalledWith(completedProgress);
      });

      it('should handle error scenario', async () => {
        const batchId = 'batch-123';
        const errorProgress = createMockProgress({
          status: ProcessingStatus.ERROR
        });
        const error = createMockError();
        const mockState = createMockState({
          campaign_xlsx: errorProgress,
          errors: [error]
        });

        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse(true, mockState) });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onProgressUpdate).toHaveBeenCalledWith(errorProgress);
        expect(mockCallbacks.onErrorUpdate).toHaveBeenCalledWith([error]);
      });

      it('should handle cancellation scenario', async () => {
        const batchId = 'batch-123';
        const cancelledProgress = createMockProgress({
          status: ProcessingStatus.CANCELLED
        });
        const mockState = createMockState({ campaign_xlsx: cancelledProgress });

        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse(true, mockState) });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onProgressUpdate).toHaveBeenCalledWith(cancelledProgress);
      });
    });
  });

  describe('7. Service Lifecycle Tests', () => {
    describe('service initialization with batch_id', () => {
      it('should initialize service without errors', () => {
        expect(() => new ProcessingStatusService()).not.toThrow();
      });

      it('should accept valid configuration options', () => {
        const config: PollingConfiguration = {
          pollingInterval: 2000,
          maxRetries: 10,
          timeoutMs: 30000
        };

        expect(() => new ProcessingStatusService(config)).not.toThrow();
      });
    });

    describe('polling start with proper configuration', () => {
      it('should start polling with valid batch_id and callbacks', () => {
        const batchId = 'batch-123';
        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse() });

        expect(() => service.startPolling(batchId, mockCallbacks)).not.toThrow();
        expect(mockedAxios.get).toHaveBeenCalledWith(`/api/upload/status/${batchId}`);
      });

      it('should throw error for invalid batch_id', () => {
        expect(() => service.startPolling('', mockCallbacks)).toThrow('Invalid batch_id');
        expect(() => service.startPolling('   ', mockCallbacks)).toThrow('Invalid batch_id');
      });

      it('should throw error for missing callbacks', () => {
        expect(() => service.startPolling('batch-123', null as any)).toThrow('Callbacks are required');
      });
    });

    describe('polling stop and cleanup', () => {
      it('should stop specific polling session', () => {
        const batchId = 'batch-123';
        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse() });

        service.startPolling(batchId, mockCallbacks);
        service.stopPolling(batchId);

        jest.advanceTimersByTime(10000);
        expect(mockedAxios.get).toHaveBeenCalledTimes(1); // Only initial call
      });

      it('should clean up resources when stopping polling', () => {
        const batchId = 'batch-123';
        const clearTimeoutSpy = jest.spyOn(global, 'clearTimeout');

        service.startPolling(batchId, mockCallbacks);
        service.stopPolling(batchId);

        expect(clearTimeoutSpy).toHaveBeenCalled();
      });
    });

    describe('service destruction and memory cleanup', () => {
      it('should cleanup all resources on service destruction', () => {
        const clearTimeoutSpy = jest.spyOn(global, 'clearTimeout');
        const removeEventListenerSpy = jest.spyOn(document, 'removeEventListener');

        service.startPolling('batch-1', mockCallbacks);
        service.startPolling('batch-2', {...mockCallbacks});

        service.cleanup();

        expect(clearTimeoutSpy).toHaveBeenCalled();
        expect(removeEventListenerSpy).toHaveBeenCalled();
      });
    });

    describe('multiple service instances', () => {
      it('should handle multiple service instances with different batch_ids', () => {
        const service2 = new ProcessingStatusService();
        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse() });

        service.startPolling('batch-1', mockCallbacks);
        service2.startPolling('batch-2', {...mockCallbacks});

        expect(mockedAxios.get).toHaveBeenCalledWith('/api/upload/status/batch-1');
        expect(mockedAxios.get).toHaveBeenCalledWith('/api/upload/status/batch-2');

        service2.cleanup();
      });
    });

    describe('service restart scenarios', () => {
      it('should handle restarting polling for same batch_id', () => {
        const batchId = 'batch-123';
        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse() });

        service.startPolling(batchId, mockCallbacks);
        service.stopPolling(batchId);
        service.startPolling(batchId, mockCallbacks);

        expect(mockedAxios.get).toHaveBeenCalledTimes(2); // Initial calls for each start
      });
    });
  });

  describe('8. Integration with UI Components Tests', () => {
    describe('integration with ProcessingProgressIndicator updates', () => {
      it('should provide progress data compatible with ProcessingProgressIndicator', async () => {
        const batchId = 'batch-123';
        const progress = createMockProgress({
          stage: ProcessingStage.VALIDATE,
          progress: 50,
          status: ProcessingStatus.PROCESSING
        });
        const mockState = createMockState({ campaign_xlsx: progress });

        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse(true, mockState) });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onProgressUpdate).toHaveBeenCalledWith(
          expect.objectContaining({
            stage: ProcessingStage.VALIDATE,
            progress: 50,
            status: ProcessingStatus.PROCESSING,
            file_type: expect.any(String),
            batch_id: batchId
          })
        );
      });
    });

    describe('integration with UploadControlPanel state changes', () => {
      it('should provide callbacks that enable UploadControlPanel state management', async () => {
        const batchId = 'batch-123';
        const completedProgress = createMockProgress({
          status: ProcessingStatus.COMPLETED
        });
        const mockState = createMockState({ campaign_xlsx: completedProgress });
        const mockResponse = createMockStatusResponse(true, mockState);

        mockedAxios.get.mockResolvedValue({ data: mockResponse });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        // Should provide completion callback for UploadControlPanel to update its state
        expect(mockCallbacks.onCompletion).toHaveBeenCalledWith(mockResponse);
      });
    });

    describe('integration with ErrorDisplayPanel error updates', () => {
      it('should provide error data compatible with ErrorDisplayPanel', async () => {
        const batchId = 'batch-123';
        const errors = [
          createMockError({
            severity: ErrorSeverity.ERROR,
            message: 'Critical validation error'
          }),
          createMockError({
            severity: ErrorSeverity.WARNING,
            message: 'Minor formatting issue'
          })
        ];
        const mockState = createMockState({ errors });

        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse(true, mockState) });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onErrorUpdate).toHaveBeenCalledWith(
          expect.arrayContaining([
            expect.objectContaining({
              severity: ErrorSeverity.ERROR,
              message: 'Critical validation error'
            }),
            expect.objectContaining({
              severity: ErrorSeverity.WARNING,
              message: 'Minor formatting issue'
            })
          ])
        );
      });
    });

    describe('callback integration for UI state management', () => {
      it('should provide all necessary callbacks for comprehensive UI state management', async () => {
        const batchId = 'batch-123';

        // Test progress callback
        const progress = createMockProgress();
        const stateWithProgress = createMockState({ campaign_xlsx: progress });
        mockedAxios.get.mockResolvedValueOnce({ data: createMockStatusResponse(true, stateWithProgress) });

        service.startPolling(batchId, mockCallbacks);
        await Promise.resolve();

        expect(mockCallbacks.onProgressUpdate).toHaveBeenCalled();

        // Test error callback
        const error = createMockError();
        const stateWithError = createMockState({ errors: [error] });
        mockedAxios.get.mockResolvedValueOnce({ data: createMockStatusResponse(true, stateWithError) });

        jest.advanceTimersByTime(2000);
        await Promise.resolve();

        expect(mockCallbacks.onErrorUpdate).toHaveBeenCalled();
      });
    });

    describe('processing completion UI transitions', () => {
      it('should trigger UI transition callbacks when processing completes', async () => {
        const batchId = 'batch-123';
        const completedProgress = createMockProgress({
          status: ProcessingStatus.COMPLETED,
          stage: ProcessingStage.COMPLETE,
          progress: 100
        });
        const mockState = createMockState({ campaign_xlsx: completedProgress });
        const mockResponse = createMockStatusResponse(true, mockState);

        mockedAxios.get.mockResolvedValue({ data: mockResponse });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onProgressUpdate).toHaveBeenCalledWith(completedProgress);
        expect(mockCallbacks.onCompletion).toHaveBeenCalledWith(mockResponse);
      });
    });

    describe('error state UI updates', () => {
      it('should trigger error UI updates when processing encounters errors', async () => {
        const batchId = 'batch-123';
        const errorProgress = createMockProgress({
          status: ProcessingStatus.ERROR
        });
        const processingError = createMockError({
          severity: ErrorSeverity.ERROR,
          message: 'Processing failed due to invalid data'
        });
        const mockState = createMockState({
          campaign_xlsx: errorProgress,
          errors: [processingError]
        });

        mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse(true, mockState) });

        service.startPolling(batchId, mockCallbacks);

        await Promise.resolve();

        expect(mockCallbacks.onProgressUpdate).toHaveBeenCalledWith(errorProgress);
        expect(mockCallbacks.onErrorUpdate).toHaveBeenCalledWith([processingError]);
      });
    });
  });

  describe('Edge Cases and Error Scenarios', () => {
    it('should handle empty response data', async () => {
      const batchId = 'batch-123';
      mockedAxios.get.mockResolvedValue({ data: null });

      service.startPolling(batchId, mockCallbacks);

      await Promise.resolve();

      expect(mockCallbacks.onFailure).toHaveBeenCalledWith(
        expect.objectContaining({
          message: expect.stringContaining('Empty response')
        })
      );
    });

    it('should handle rapid start/stop cycles', () => {
      const batchId = 'batch-123';
      mockedAxios.get.mockResolvedValue({ data: createMockStatusResponse() });

      for (let i = 0; i < 10; i++) {
        service.startPolling(batchId, mockCallbacks);
        service.stopPolling(batchId);
      }

      expect(() => service.cleanup()).not.toThrow();
    });

    it('should handle invalid batch_id formats', () => {
      const invalidBatchIds = ['', '   ', null, undefined, 123, {}, []];

      invalidBatchIds.forEach(invalidId => {
        expect(() => service.startPolling(invalidId as any, mockCallbacks))
          .toThrow('Invalid batch_id');
      });
    });

    it('should handle network errors during polling', async () => {
      const batchId = 'batch-123';
      const networkError = new Error('ENOTFOUND');
      
      mockedAxios.get.mockRejectedValue(networkError);

      service.startPolling(batchId, mockCallbacks);

      await Promise.resolve();

      // Should implement retry logic, not immediately fail
      jest.advanceTimersByTime(4000); // Exponential backoff
      expect(mockedAxios.get).toHaveBeenCalledTimes(2);
    });
  });
});