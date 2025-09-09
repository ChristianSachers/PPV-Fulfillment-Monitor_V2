/**
 * TDD Red Phase: Tests for Processing types that don't exist yet
 * These tests will fail initially until the interfaces are implemented
 * 
 * Test suite for Upload Processing Pipeline UI types and validation functions
 * Covers processing states, stages, error handling, progress tracking, and API communication
 */

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
  ProcessingCancellationRequest,
  ProcessingStateManager,
  isProcessingProgress,
  isProcessingError,
  isProcessingState,
  isProcessingStatusResponse,
  validateProcessingProgress,
  validateProcessingError,
  validateProcessingState,
  validateFileSize,
  validateProgressStage,
  canStartProcessing,
  getProcessingPercentage,
  isValidFileType,
  createProcessingError,
} from '../processing';

describe('Processing Enums', () => {
  describe('ProcessingStatus Enum', () => {
    it('should define valid processing status values', () => {
      expect(ProcessingStatus.IDLE).toBe('idle');
      expect(ProcessingStatus.PROCESSING).toBe('processing');
      expect(ProcessingStatus.COMPLETED).toBe('completed');
      expect(ProcessingStatus.ERROR).toBe('error');
      expect(ProcessingStatus.CANCELLED).toBe('cancelled');
    });
  });

  describe('ProcessingStage Enum', () => {
    it('should define valid processing stages with exact percentages', () => {
      expect(ProcessingStage.PARSE).toBe('parse');
      expect(ProcessingStage.VALIDATE).toBe('validate');
      expect(ProcessingStage.CLASSIFY).toBe('classify');
      expect(ProcessingStage.COMPLETE).toBe('complete');
    });
  });

  describe('FileType Enum', () => {
    it('should define valid file types for processing', () => {
      expect(FileType.CAMPAIGN_XLSX).toBe('campaign_xlsx');
      expect(FileType.REPORTING_CSV).toBe('reporting_csv');
    });
  });

  describe('ErrorCategory Enum', () => {
    it('should define valid error categories', () => {
      expect(ErrorCategory.VALIDATION).toBe('validation');
      expect(ErrorCategory.PARSING).toBe('parsing');
      expect(ErrorCategory.PROCESSING).toBe('processing');
      expect(ErrorCategory.SYSTEM).toBe('system');
    });
  });

  describe('ErrorSeverity Enum', () => {
    it('should define valid error severity levels', () => {
      expect(ErrorSeverity.ERROR).toBe('error');
      expect(ErrorSeverity.WARNING).toBe('warning');
      expect(ErrorSeverity.INFO).toBe('info');
    });
  });
});

describe('ProcessingProgress Interface', () => {
  describe('Type Definition', () => {
    it('should define ProcessingProgress with required properties', () => {
      const mockProgress: ProcessingProgress = {
        batch_id: 'batch-123',
        stage: ProcessingStage.VALIDATE,
        progress: 50,
        status: ProcessingStatus.PROCESSING,
        file_type: FileType.CAMPAIGN_XLSX,
        started_at: '2024-09-09T10:00:00Z',
        updated_at: '2024-09-09T10:05:00Z'
      };

      expect(mockProgress.batch_id).toBe('batch-123');
      expect(mockProgress.stage).toBe('validate');
      expect(mockProgress.progress).toBe(50);
      expect(mockProgress.status).toBe('processing');
      expect(mockProgress.file_type).toBe('campaign_xlsx');
      expect(mockProgress.started_at).toBe('2024-09-09T10:00:00Z');
      expect(mockProgress.updated_at).toBe('2024-09-09T10:05:00Z');
    });

    it('should support optional completed_at timestamp', () => {
      const completedProgress: ProcessingProgress = {
        batch_id: 'batch-456',
        stage: ProcessingStage.COMPLETE,
        progress: 100,
        status: ProcessingStatus.COMPLETED,
        file_type: FileType.REPORTING_CSV,
        started_at: '2024-09-09T10:00:00Z',
        updated_at: '2024-09-09T10:10:00Z',
        completed_at: '2024-09-09T10:10:00Z'
      };

      expect(completedProgress.completed_at).toBe('2024-09-09T10:10:00Z');
    });
  });

  describe('Type Guard: isProcessingProgress', () => {
    it('should return true for valid ProcessingProgress', () => {
      const validProgress = {
        batch_id: 'batch-123',
        stage: 'validate',
        progress: 50,
        status: 'processing',
        file_type: 'campaign_xlsx',
        started_at: '2024-09-09T10:00:00Z',
        updated_at: '2024-09-09T10:05:00Z'
      };

      expect(isProcessingProgress(validProgress)).toBe(true);
    });

    it('should return false for invalid ProcessingProgress - missing properties', () => {
      const invalidProgress = {
        batch_id: 'batch-123',
        stage: 'validate'
        // missing other required properties
      };

      expect(isProcessingProgress(invalidProgress)).toBe(false);
    });

    it('should return false for invalid ProcessingProgress - wrong types', () => {
      const invalidProgress = {
        batch_id: 123, // should be string
        stage: 'validate',
        progress: '50', // should be number
        status: 'processing',
        file_type: 'campaign_xlsx',
        started_at: '2024-09-09T10:00:00Z',
        updated_at: '2024-09-09T10:05:00Z'
      };

      expect(isProcessingProgress(invalidProgress)).toBe(false);
    });
  });

  describe('Validation: validateProcessingProgress', () => {
    it('should return valid result for correct ProcessingProgress', () => {
      const validProgress = {
        batch_id: 'batch-123',
        stage: 'validate',
        progress: 50,
        status: 'processing',
        file_type: 'campaign_xlsx',
        started_at: '2024-09-09T10:00:00Z',
        updated_at: '2024-09-09T10:05:00Z'
      };

      const result = validateProcessingProgress(validProgress);
      expect(result.isValid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it('should validate progress values are exactly 25, 50, 75, or 100', () => {
      const invalidProgress = {
        batch_id: 'batch-123',
        stage: 'validate',
        progress: 30, // invalid - must be exactly 25, 50, 75, or 100
        status: 'processing',
        file_type: 'campaign_xlsx',
        started_at: '2024-09-09T10:00:00Z',
        updated_at: '2024-09-09T10:05:00Z'
      };

      const result = validateProcessingProgress(invalidProgress);
      expect(result.isValid).toBe(false);
      expect(result.errors).toContain('progress must be exactly 25, 50, 75, or 100');
    });

    it('should validate stage-progress consistency', () => {
      const inconsistentProgress = {
        batch_id: 'batch-123',
        stage: 'parse', // parse stage should be 25%
        progress: 50, // but progress is 50%
        status: 'processing',
        file_type: 'campaign_xlsx',
        started_at: '2024-09-09T10:00:00Z',
        updated_at: '2024-09-09T10:05:00Z'
      };

      const result = validateProcessingProgress(inconsistentProgress);
      expect(result.isValid).toBe(false);
      expect(result.errors).toContain('stage parse must have progress 25');
    });
  });
});

describe('ProcessingError Interface', () => {
  describe('Type Definition', () => {
    it('should define ProcessingError with required properties', () => {
      const mockError: ProcessingError = {
        error_id: 'error-123',
        timestamp: '2024-09-09T10:00:00Z',
        category: ErrorCategory.VALIDATION,
        severity: ErrorSeverity.ERROR,
        code: 'INVALID_ROW',
        message: 'Row 5 contains invalid data',
        context: {
          file_type: FileType.CAMPAIGN_XLSX,
          row_number: 5,
          column_name: 'budget'
        }
      };

      expect(mockError.error_id).toBe('error-123');
      expect(mockError.timestamp).toBe('2024-09-09T10:00:00Z');
      expect(mockError.category).toBe('validation');
      expect(mockError.severity).toBe('error');
      expect(mockError.code).toBe('INVALID_ROW');
      expect(mockError.message).toBe('Row 5 contains invalid data');
      expect(mockError.context.file_type).toBe('campaign_xlsx');
      expect(mockError.context.row_number).toBe(5);
      expect(mockError.context.column_name).toBe('budget');
    });

    it('should support optional suggested_action property', () => {
      const errorWithAction: ProcessingError = {
        error_id: 'error-456',
        timestamp: '2024-09-09T10:00:00Z',
        category: ErrorCategory.PARSING,
        severity: ErrorSeverity.WARNING,
        code: 'MISSING_COLUMN',
        message: 'Column "description" is missing',
        context: {
          file_type: FileType.REPORTING_CSV
        },
        suggested_action: 'Add the missing column to your CSV file'
      };

      expect(errorWithAction.suggested_action).toBe('Add the missing column to your CSV file');
    });
  });

  describe('Type Guard: isProcessingError', () => {
    it('should return true for valid ProcessingError', () => {
      const validError = {
        error_id: 'error-123',
        timestamp: '2024-09-09T10:00:00Z',
        category: 'validation',
        severity: 'error',
        code: 'INVALID_ROW',
        message: 'Row 5 contains invalid data',
        context: {
          file_type: 'campaign_xlsx'
        }
      };

      expect(isProcessingError(validError)).toBe(true);
    });

    it('should return false for invalid ProcessingError - missing properties', () => {
      const invalidError = {
        error_id: 'error-123',
        timestamp: '2024-09-09T10:00:00Z'
        // missing other required properties
      };

      expect(isProcessingError(invalidError)).toBe(false);
    });
  });

  describe('Validation: validateProcessingError', () => {
    it('should return valid result for correct ProcessingError', () => {
      const validError = {
        error_id: 'error-123',
        timestamp: '2024-09-09T10:00:00Z',
        category: 'validation',
        severity: 'error',
        code: 'INVALID_ROW',
        message: 'Row 5 contains invalid data',
        context: {
          file_type: 'campaign_xlsx'
        }
      };

      const result = validateProcessingError(validError);
      expect(result.isValid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it('should validate context contains file_type', () => {
      const invalidError = {
        error_id: 'error-123',
        timestamp: '2024-09-09T10:00:00Z',
        category: 'validation',
        severity: 'error',
        code: 'INVALID_ROW',
        message: 'Row 5 contains invalid data',
        context: {} // missing file_type
      };

      const result = validateProcessingError(invalidError);
      expect(result.isValid).toBe(false);
      expect(result.errors).toContain('context must contain file_type');
    });
  });
});

describe('ProcessingState Interface', () => {
  describe('Type Definition', () => {
    it('should define ProcessingState for concurrent file processing', () => {
      const mockState: ProcessingState = {
        campaign_xlsx: {
          batch_id: 'batch-123',
          stage: ProcessingStage.VALIDATE,
          progress: 50,
          status: ProcessingStatus.PROCESSING,
          file_type: FileType.CAMPAIGN_XLSX,
          started_at: '2024-09-09T10:00:00Z',
          updated_at: '2024-09-09T10:05:00Z'
        },
        reporting_csv: {
          batch_id: 'batch-456',
          stage: ProcessingStage.PARSE,
          progress: 25,
          status: ProcessingStatus.PROCESSING,
          file_type: FileType.REPORTING_CSV,
          started_at: '2024-09-09T10:01:00Z',
          updated_at: '2024-09-09T10:06:00Z'
        },
        errors: [
          {
            error_id: 'error-123',
            timestamp: '2024-09-09T10:00:00Z',
            category: ErrorCategory.VALIDATION,
            severity: ErrorSeverity.WARNING,
            code: 'MISSING_COLUMN',
            message: 'Optional column "notes" is missing',
            context: {
              file_type: FileType.CAMPAIGN_XLSX
            }
          }
        ],
        last_updated: '2024-09-09T10:06:00Z'
      };

      expect(mockState.campaign_xlsx.batch_id).toBe('batch-123');
      expect(mockState.reporting_csv.batch_id).toBe('batch-456');
      expect(mockState.errors).toHaveLength(1);
      expect(mockState.last_updated).toBe('2024-09-09T10:06:00Z');
    });

    it('should support optional processing states', () => {
      const partialState: ProcessingState = {
        campaign_xlsx: null,
        reporting_csv: {
          batch_id: 'batch-456',
          stage: ProcessingStage.COMPLETE,
          progress: 100,
          status: ProcessingStatus.COMPLETED,
          file_type: FileType.REPORTING_CSV,
          started_at: '2024-09-09T10:00:00Z',
          updated_at: '2024-09-09T10:10:00Z',
          completed_at: '2024-09-09T10:10:00Z'
        },
        errors: [],
        last_updated: '2024-09-09T10:10:00Z'
      };

      expect(partialState.campaign_xlsx).toBeNull();
      expect(partialState.reporting_csv).not.toBeNull();
    });
  });

  describe('Type Guard: isProcessingState', () => {
    it('should return true for valid ProcessingState', () => {
      const validState = {
        campaign_xlsx: null,
        reporting_csv: {
          batch_id: 'batch-456',
          stage: 'complete',
          progress: 100,
          status: 'completed',
          file_type: 'reporting_csv',
          started_at: '2024-09-09T10:00:00Z',
          updated_at: '2024-09-09T10:10:00Z'
        },
        errors: [],
        last_updated: '2024-09-09T10:10:00Z'
      };

      expect(isProcessingState(validState)).toBe(true);
    });

    it('should return false for invalid ProcessingState - missing properties', () => {
      const invalidState = {
        campaign_xlsx: null
        // missing other required properties
      };

      expect(isProcessingState(invalidState)).toBe(false);
    });
  });

  describe('Validation: validateProcessingState', () => {
    it('should return valid result for correct ProcessingState', () => {
      const validState = {
        campaign_xlsx: null,
        reporting_csv: null,
        errors: [],
        last_updated: '2024-09-09T10:00:00Z'
      };

      const result = validateProcessingState(validState);
      expect(result.isValid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it('should validate errors are sorted by timestamp (oldest first)', () => {
      const invalidState = {
        campaign_xlsx: null,
        reporting_csv: null,
        errors: [
          {
            error_id: 'error-2',
            timestamp: '2024-09-09T10:05:00Z', // newer timestamp first
            category: 'validation',
            severity: 'error',
            code: 'TEST',
            message: 'Test error 2',
            context: { file_type: 'campaign_xlsx' }
          },
          {
            error_id: 'error-1',
            timestamp: '2024-09-09T10:00:00Z', // older timestamp second
            category: 'validation',
            severity: 'error',
            code: 'TEST',
            message: 'Test error 1',
            context: { file_type: 'campaign_xlsx' }
          }
        ],
        last_updated: '2024-09-09T10:05:00Z'
      };

      const result = validateProcessingState(invalidState);
      expect(result.isValid).toBe(false);
      expect(result.errors).toContain('errors must be sorted by timestamp (oldest first)');
    });
  });
});

describe('ProcessingStatusResponse Interface', () => {
  describe('Type Definition', () => {
    it('should define ProcessingStatusResponse for API polling', () => {
      const mockResponse: ProcessingStatusResponse = {
        success: true,
        data: {
          campaign_xlsx: {
            batch_id: 'batch-123',
            stage: ProcessingStage.VALIDATE,
            progress: 50,
            status: ProcessingStatus.PROCESSING,
            file_type: FileType.CAMPAIGN_XLSX,
            started_at: '2024-09-09T10:00:00Z',
            updated_at: '2024-09-09T10:05:00Z'
          },
          reporting_csv: null,
          errors: [],
          last_updated: '2024-09-09T10:05:00Z'
        },
        polling_interval: 2000
      };

      expect(mockResponse.success).toBe(true);
      expect(mockResponse.data.campaign_xlsx?.batch_id).toBe('batch-123');
      expect(mockResponse.polling_interval).toBe(2000);
    });

    it('should support error responses', () => {
      const errorResponse: ProcessingStatusResponse = {
        success: false,
        error: {
          code: 'PROCESSING_FAILED',
          message: 'Processing pipeline encountered an error',
          details: 'Database connection failed'
        },
        polling_interval: 2000
      };

      expect(errorResponse.success).toBe(false);
      expect(errorResponse.error?.code).toBe('PROCESSING_FAILED');
      expect(errorResponse.error?.message).toBe('Processing pipeline encountered an error');
    });
  });

  describe('Type Guard: isProcessingStatusResponse', () => {
    it('should return true for valid success response', () => {
      const validResponse = {
        success: true,
        data: {
          campaign_xlsx: null,
          reporting_csv: null,
          errors: [],
          last_updated: '2024-09-09T10:00:00Z'
        },
        polling_interval: 2000
      };

      expect(isProcessingStatusResponse(validResponse)).toBe(true);
    });

    it('should return true for valid error response', () => {
      const validErrorResponse = {
        success: false,
        error: {
          code: 'TEST_ERROR',
          message: 'Test error message'
        },
        polling_interval: 2000
      };

      expect(isProcessingStatusResponse(validErrorResponse)).toBe(true);
    });
  });
});

describe('Utility Functions', () => {
  describe('validateFileSize', () => {
    it('should accept files exactly at 250MB limit', () => {
      const result = validateFileSize(250 * 1024 * 1024); // exactly 250MB
      expect(result.isValid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it('should reject files over 250MB limit', () => {
      const result = validateFileSize(251 * 1024 * 1024); // 251MB
      expect(result.isValid).toBe(false);
      expect(result.errors).toContain('file size exceeds 250MB limit');
    });

    it('should accept files under 250MB limit', () => {
      const result = validateFileSize(100 * 1024 * 1024); // 100MB
      expect(result.isValid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });
  });

  describe('validateProgressStage', () => {
    it('should validate stage-progress consistency', () => {
      expect(validateProgressStage('parse', 25).isValid).toBe(true);
      expect(validateProgressStage('validate', 50).isValid).toBe(true);
      expect(validateProgressStage('classify', 75).isValid).toBe(true);
      expect(validateProgressStage('complete', 100).isValid).toBe(true);
    });

    it('should reject inconsistent stage-progress combinations', () => {
      const result = validateProgressStage('parse', 50);
      expect(result.isValid).toBe(false);
      expect(result.errors).toContain('stage parse must have progress 25');
    });
  });

  describe('canStartProcessing', () => {
    it('should allow processing when no files are being processed', () => {
      const state: ProcessingState = {
        campaign_xlsx: null,
        reporting_csv: null,
        errors: [],
        last_updated: '2024-09-09T10:00:00Z'
      };

      expect(canStartProcessing(state, FileType.CAMPAIGN_XLSX)).toBe(true);
      expect(canStartProcessing(state, FileType.REPORTING_CSV)).toBe(true);
    });

    it('should block processing when file type is already being processed', () => {
      const state: ProcessingState = {
        campaign_xlsx: {
          batch_id: 'batch-123',
          stage: ProcessingStage.VALIDATE,
          progress: 50,
          status: ProcessingStatus.PROCESSING,
          file_type: FileType.CAMPAIGN_XLSX,
          started_at: '2024-09-09T10:00:00Z',
          updated_at: '2024-09-09T10:05:00Z'
        },
        reporting_csv: null,
        errors: [],
        last_updated: '2024-09-09T10:05:00Z'
      };

      expect(canStartProcessing(state, FileType.CAMPAIGN_XLSX)).toBe(false);
      expect(canStartProcessing(state, FileType.REPORTING_CSV)).toBe(true);
    });

    it('should allow processing when previous file completed or failed', () => {
      const state: ProcessingState = {
        campaign_xlsx: {
          batch_id: 'batch-123',
          stage: ProcessingStage.COMPLETE,
          progress: 100,
          status: ProcessingStatus.COMPLETED,
          file_type: FileType.CAMPAIGN_XLSX,
          started_at: '2024-09-09T10:00:00Z',
          updated_at: '2024-09-09T10:10:00Z',
          completed_at: '2024-09-09T10:10:00Z'
        },
        reporting_csv: null,
        errors: [],
        last_updated: '2024-09-09T10:10:00Z'
      };

      expect(canStartProcessing(state, FileType.CAMPAIGN_XLSX)).toBe(true);
    });
  });

  describe('getProcessingPercentage', () => {
    it('should return correct percentages for each stage', () => {
      expect(getProcessingPercentage(ProcessingStage.PARSE)).toBe(25);
      expect(getProcessingPercentage(ProcessingStage.VALIDATE)).toBe(50);
      expect(getProcessingPercentage(ProcessingStage.CLASSIFY)).toBe(75);
      expect(getProcessingPercentage(ProcessingStage.COMPLETE)).toBe(100);
    });
  });

  describe('isValidFileType', () => {
    it('should validate supported file types', () => {
      expect(isValidFileType('campaign_xlsx')).toBe(true);
      expect(isValidFileType('reporting_csv')).toBe(true);
      expect(isValidFileType('unsupported_type')).toBe(false);
    });
  });

  describe('createProcessingError', () => {
    it('should create ProcessingError with proper structure', () => {
      const error = createProcessingError(
        ErrorCategory.VALIDATION,
        ErrorSeverity.ERROR,
        'INVALID_DATA',
        'Invalid data in row 5',
        { file_type: FileType.CAMPAIGN_XLSX, row_number: 5 }
      );

      expect(error.error_id).toBeDefined();
      expect(error.timestamp).toBeDefined();
      expect(error.category).toBe('validation');
      expect(error.severity).toBe('error');
      expect(error.code).toBe('INVALID_DATA');
      expect(error.message).toBe('Invalid data in row 5');
      expect(error.context.file_type).toBe('campaign_xlsx');
      expect(error.context.row_number).toBe(5);
    });

    it('should generate unique error IDs and current timestamps', () => {
      const error1 = createProcessingError(
        ErrorCategory.PARSING,
        ErrorSeverity.WARNING,
        'TEST',
        'Test message',
        { file_type: FileType.REPORTING_CSV }
      );

      const error2 = createProcessingError(
        ErrorCategory.PARSING,
        ErrorSeverity.WARNING,
        'TEST',
        'Test message',
        { file_type: FileType.REPORTING_CSV }
      );

      expect(error1.error_id).not.toBe(error2.error_id);
      expect(error1.timestamp).toBeDefined();
      expect(error2.timestamp).toBeDefined();
    });
  });
});

describe('ProcessingCancellationRequest Interface', () => {
  describe('Type Definition', () => {
    it('should define ProcessingCancellationRequest for API calls', () => {
      const mockRequest: ProcessingCancellationRequest = {
        batch_id: 'batch-123',
        file_type: FileType.CAMPAIGN_XLSX,
        reason: 'User requested cancellation'
      };

      expect(mockRequest.batch_id).toBe('batch-123');
      expect(mockRequest.file_type).toBe('campaign_xlsx');
      expect(mockRequest.reason).toBe('User requested cancellation');
    });

    it('should support optional reason', () => {
      const minimalRequest: ProcessingCancellationRequest = {
        batch_id: 'batch-456',
        file_type: FileType.REPORTING_CSV
      };

      expect(minimalRequest.batch_id).toBe('batch-456');
      expect(minimalRequest.file_type).toBe('reporting_csv');
      expect(minimalRequest.reason).toBeUndefined();
    });
  });
});

describe('ProcessingStateManager Class', () => {
  describe('State Management', () => {
    it('should initialize with empty state', () => {
      const manager = new ProcessingStateManager();
      const state = manager.getState();

      expect(state.campaign_xlsx).toBeNull();
      expect(state.reporting_csv).toBeNull();
      expect(state.errors).toHaveLength(0);
      expect(state.last_updated).toBeDefined();
    });

    it('should update processing progress', () => {
      const manager = new ProcessingStateManager();
      const progress: ProcessingProgress = {
        batch_id: 'batch-123',
        stage: ProcessingStage.VALIDATE,
        progress: 50,
        status: ProcessingStatus.PROCESSING,
        file_type: FileType.CAMPAIGN_XLSX,
        started_at: '2024-09-09T10:00:00Z',
        updated_at: '2024-09-09T10:05:00Z'
      };

      manager.updateProgress(progress);
      const state = manager.getState();

      expect(state.campaign_xlsx?.batch_id).toBe('batch-123');
      expect(state.campaign_xlsx?.progress).toBe(50);
    });

    it('should add errors in time-ordered fashion', () => {
      const manager = new ProcessingStateManager();
      
      const error1 = createProcessingError(
        ErrorCategory.VALIDATION,
        ErrorSeverity.ERROR,
        'ERROR1',
        'First error',
        { file_type: FileType.CAMPAIGN_XLSX }
      );

      // Simulate time passing
      setTimeout(() => {
        const error2 = createProcessingError(
          ErrorCategory.PARSING,
          ErrorSeverity.WARNING,
          'ERROR2',
          'Second error',
          { file_type: FileType.REPORTING_CSV }
        );

        manager.addError(error1);
        manager.addError(error2);

        const state = manager.getState();
        expect(state.errors).toHaveLength(2);
        expect(state.errors[0].error_id).toBe(error1.error_id); // oldest first
        expect(state.errors[1].error_id).toBe(error2.error_id);
      }, 10);
    });

    it('should clear processing state for specific file type', () => {
      const manager = new ProcessingStateManager();
      const progress: ProcessingProgress = {
        batch_id: 'batch-123',
        stage: ProcessingStage.COMPLETE,
        progress: 100,
        status: ProcessingStatus.COMPLETED,
        file_type: FileType.CAMPAIGN_XLSX,
        started_at: '2024-09-09T10:00:00Z',
        updated_at: '2024-09-09T10:10:00Z',
        completed_at: '2024-09-09T10:10:00Z'
      };

      manager.updateProgress(progress);
      manager.clearProcessing(FileType.CAMPAIGN_XLSX);

      const state = manager.getState();
      expect(state.campaign_xlsx).toBeNull();
    });
  });
});