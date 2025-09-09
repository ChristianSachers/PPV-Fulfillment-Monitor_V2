/**
 * Processing Type Definitions
 * Provides TypeScript interfaces, enums, and utility functions for file processing operations
 * Used by the Upload Processing Pipeline UI components
 */

// Processing status enum
export enum ProcessingStatus {
  IDLE = 'idle',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  ERROR = 'error',
  CANCELLED = 'cancelled'
}

// Processing stage enum with exact progress mapping
export enum ProcessingStage {
  PARSE = 'parse',
  VALIDATE = 'validate', 
  CLASSIFY = 'classify',
  COMPLETE = 'complete'
}

// File type enum for processing
export enum FileType {
  CAMPAIGN_XLSX = 'campaign_xlsx',
  REPORTING_CSV = 'reporting_csv'
}

// Processing file type enum for UI interaction
export enum ProcessingFileType {
  CAMPAIGN_XLSX = 'campaign_xlsx',
  REPORTING_CSV = 'reporting_csv'
}

// Error category enum
export enum ErrorCategory {
  VALIDATION = 'validation',
  PARSING = 'parsing',
  PROCESSING = 'processing',
  SYSTEM = 'system'
}

// Error severity enum
export enum ErrorSeverity {
  ERROR = 'error',
  WARNING = 'warning',
  INFO = 'info'
}

// Core interfaces
export interface ProcessingProgress {
  batch_id: string;
  stage: ProcessingStage;
  progress: 25 | 50 | 75 | 100;
  status: ProcessingStatus;
  file_type: FileType;
  started_at: string;
  updated_at: string;
  completed_at?: string;
}

export interface ProcessingError {
  error_id: string;
  timestamp: string;
  category: ErrorCategory;
  severity: ErrorSeverity;
  code: string;
  message: string;
  context: {
    file_type: FileType;
    [key: string]: any;
  };
  suggested_action?: string;
}

export interface ProcessingState {
  campaign_xlsx: ProcessingProgress | null;
  reporting_csv: ProcessingProgress | null;
  errors: ProcessingError[];
  last_updated: string;
}

export interface ProcessingStatusResponse {
  success: boolean;
  data?: ProcessingState;
  error?: {
    code: string;
    message: string;
    details?: string;
  };
  polling_interval: number;
}

export interface ProcessingCancellationRequest {
  batch_id: string;
  file_type: FileType;
  reason?: string;
}

export interface ValidationResult {
  isValid: boolean;
  errors: string[];
}

// ProcessingStateManager class
export class ProcessingStateManager {
  private state: ProcessingState;

  constructor() {
    this.state = {
      campaign_xlsx: null,
      reporting_csv: null,
      errors: [],
      last_updated: new Date().toISOString()
    };
  }

  getState(): ProcessingState {
    return { ...this.state };
  }

  updateProgress(progress: ProcessingProgress): void {
    if (progress.file_type === FileType.CAMPAIGN_XLSX) {
      this.state.campaign_xlsx = progress;
    } else if (progress.file_type === FileType.REPORTING_CSV) {
      this.state.reporting_csv = progress;
    }
    this.state.last_updated = new Date().toISOString();
  }

  addError(error: ProcessingError): void {
    this.state.errors.push(error);
    // Keep errors sorted by timestamp (oldest first)
    this.state.errors.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
    this.state.last_updated = new Date().toISOString();
  }

  clearProcessing(fileType: FileType): void {
    if (fileType === FileType.CAMPAIGN_XLSX) {
      this.state.campaign_xlsx = null;
    } else if (fileType === FileType.REPORTING_CSV) {
      this.state.reporting_csv = null;
    }
    this.state.last_updated = new Date().toISOString();
  }
}

// Type guard functions
export function isProcessingProgress(value: unknown): value is ProcessingProgress {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const obj = value as Record<string, unknown>;
  
  return (
    typeof obj.batch_id === 'string' &&
    typeof obj.stage === 'string' &&
    ['parse', 'validate', 'classify', 'complete'].includes(obj.stage as string) &&
    typeof obj.progress === 'number' &&
    [25, 50, 75, 100].includes(obj.progress as number) &&
    typeof obj.status === 'string' &&
    ['idle', 'processing', 'completed', 'error', 'cancelled'].includes(obj.status as string) &&
    typeof obj.file_type === 'string' &&
    ['campaign_xlsx', 'reporting_csv'].includes(obj.file_type as string) &&
    typeof obj.started_at === 'string' &&
    typeof obj.updated_at === 'string' &&
    (obj.completed_at === undefined || typeof obj.completed_at === 'string')
  );
}

export function isProcessingError(value: unknown): value is ProcessingError {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const obj = value as Record<string, unknown>;
  
  return (
    typeof obj.error_id === 'string' &&
    typeof obj.timestamp === 'string' &&
    typeof obj.category === 'string' &&
    ['validation', 'parsing', 'processing', 'system'].includes(obj.category as string) &&
    typeof obj.severity === 'string' &&
    ['error', 'warning', 'info'].includes(obj.severity as string) &&
    typeof obj.code === 'string' &&
    typeof obj.message === 'string' &&
    obj.context !== undefined && typeof obj.context === 'object' && !Array.isArray(obj.context) &&
    (obj.suggested_action === undefined || typeof obj.suggested_action === 'string')
  );
}

export function isProcessingState(value: unknown): value is ProcessingState {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const obj = value as Record<string, unknown>;
  
  return (
    (obj.campaign_xlsx === null || isProcessingProgress(obj.campaign_xlsx)) &&
    (obj.reporting_csv === null || isProcessingProgress(obj.reporting_csv)) &&
    Array.isArray(obj.errors) &&
    obj.errors.every((error: unknown) => isProcessingError(error)) &&
    typeof obj.last_updated === 'string'
  );
}

export function isProcessingStatusResponse(value: unknown): value is ProcessingStatusResponse {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const obj = value as Record<string, unknown>;
  
  if (typeof obj.success !== 'boolean' || typeof obj.polling_interval !== 'number') {
    return false;
  }

  if (obj.success) {
    return obj.data === undefined || isProcessingState(obj.data);
  } else {
    return obj.error !== undefined && 
           typeof obj.error === 'object' && 
           !Array.isArray(obj.error) &&
           typeof (obj.error as any).code === 'string' &&
           typeof (obj.error as any).message === 'string';
  }
}

// Validation functions
export function validateProcessingProgress(value: unknown): ValidationResult {
  const errors: string[] = [];

  if (!value || typeof value !== 'object') {
    errors.push('progress must be an object');
    return { isValid: false, errors };
  }

  const obj = value as Record<string, unknown>;

  // Validate batch_id
  if (typeof obj.batch_id !== 'string') {
    errors.push('batch_id must be a string');
  }

  // Validate stage
  if (typeof obj.stage !== 'string') {
    errors.push('stage must be a string');
  } else if (!['parse', 'validate', 'classify', 'complete'].includes(obj.stage)) {
    errors.push('invalid stage value');
  }

  // Validate progress
  if (typeof obj.progress !== 'number') {
    errors.push('progress must be a number');
  } else if (![25, 50, 75, 100].includes(obj.progress)) {
    errors.push('progress must be exactly 25, 50, 75, or 100');
  }

  // Validate stage-progress consistency
  if (typeof obj.stage === 'string' && typeof obj.progress === 'number') {
    const stageProgressMap: Record<string, number> = {
      'parse': 25,
      'validate': 50,
      'classify': 75,
      'complete': 100
    };
    
    if (stageProgressMap[obj.stage] && stageProgressMap[obj.stage] !== obj.progress) {
      errors.push(`stage ${obj.stage} must have progress ${stageProgressMap[obj.stage]}`);
    }
  }

  // Validate status
  if (typeof obj.status !== 'string') {
    errors.push('status must be a string');
  } else if (!['idle', 'processing', 'completed', 'error', 'cancelled'].includes(obj.status)) {
    errors.push('invalid status value');
  }

  // Validate file_type
  if (typeof obj.file_type !== 'string') {
    errors.push('file_type must be a string');
  } else if (!['campaign_xlsx', 'reporting_csv'].includes(obj.file_type)) {
    errors.push('invalid file_type value');
  }

  // Validate timestamps
  const dateRegex = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
  
  if (typeof obj.started_at !== 'string') {
    errors.push('started_at must be a string');
  } else if (!dateRegex.test(obj.started_at)) {
    errors.push('invalid started_at format');
  }

  if (typeof obj.updated_at !== 'string') {
    errors.push('updated_at must be a string');
  } else if (!dateRegex.test(obj.updated_at)) {
    errors.push('invalid updated_at format');
  }

  if (obj.completed_at !== undefined) {
    if (typeof obj.completed_at !== 'string') {
      errors.push('completed_at must be a string');
    } else if (!dateRegex.test(obj.completed_at)) {
      errors.push('invalid completed_at format');
    }
  }

  return {
    isValid: errors.length === 0,
    errors
  };
}

export function validateProcessingError(value: unknown): ValidationResult {
  const errors: string[] = [];

  if (!value || typeof value !== 'object') {
    errors.push('error must be an object');
    return { isValid: false, errors };
  }

  const obj = value as Record<string, unknown>;

  // Validate error_id
  if (typeof obj.error_id !== 'string') {
    errors.push('error_id must be a string');
  }

  // Validate timestamp
  const dateRegex = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
  if (typeof obj.timestamp !== 'string') {
    errors.push('timestamp must be a string');
  } else if (!dateRegex.test(obj.timestamp)) {
    errors.push('invalid timestamp format');
  }

  // Validate category
  if (typeof obj.category !== 'string') {
    errors.push('category must be a string');
  } else if (!['validation', 'parsing', 'processing', 'system'].includes(obj.category)) {
    errors.push('invalid category value');
  }

  // Validate severity
  if (typeof obj.severity !== 'string') {
    errors.push('severity must be a string');
  } else if (!['error', 'warning', 'info'].includes(obj.severity)) {
    errors.push('invalid severity value');
  }

  // Validate code
  if (typeof obj.code !== 'string') {
    errors.push('code must be a string');
  }

  // Validate message
  if (typeof obj.message !== 'string') {
    errors.push('message must be a string');
  }

  // Validate context
  if (!obj.context || typeof obj.context !== 'object' || Array.isArray(obj.context)) {
    errors.push('context must be an object');
  } else {
    const context = obj.context as Record<string, unknown>;
    if (!context.file_type) {
      errors.push('context must contain file_type');
    } else if (typeof context.file_type !== 'string' || !['campaign_xlsx', 'reporting_csv'].includes(context.file_type)) {
      errors.push('context.file_type must be a valid file type');
    }
  }

  // Validate suggested_action (optional)
  if (obj.suggested_action !== undefined && typeof obj.suggested_action !== 'string') {
    errors.push('suggested_action must be a string');
  }

  return {
    isValid: errors.length === 0,
    errors
  };
}

export function validateProcessingState(value: unknown): ValidationResult {
  const errors: string[] = [];

  if (!value || typeof value !== 'object') {
    errors.push('state must be an object');
    return { isValid: false, errors };
  }

  const obj = value as Record<string, unknown>;

  // Validate campaign_xlsx
  if (obj.campaign_xlsx !== null) {
    if (!isProcessingProgress(obj.campaign_xlsx)) {
      errors.push('campaign_xlsx must be null or valid ProcessingProgress');
    }
  }

  // Validate reporting_csv
  if (obj.reporting_csv !== null) {
    if (!isProcessingProgress(obj.reporting_csv)) {
      errors.push('reporting_csv must be null or valid ProcessingProgress');  
    }
  }

  // Validate errors array
  if (!Array.isArray(obj.errors)) {
    errors.push('errors must be an array');
  } else {
    // Check if errors are sorted by timestamp (oldest first)
    for (let i = 1; i < obj.errors.length; i++) {
      const current = obj.errors[i] as any;
      const previous = obj.errors[i - 1] as any;
      
      if (current.timestamp && previous.timestamp) {
        const currentTime = new Date(current.timestamp).getTime();
        const previousTime = new Date(previous.timestamp).getTime();
        
        if (currentTime < previousTime) {
          errors.push('errors must be sorted by timestamp (oldest first)');
          break;
        }
      }
    }

    // Validate each error
    obj.errors.forEach((error: unknown, index: number) => {
      if (!isProcessingError(error)) {
        errors.push(`error at index ${index} is invalid`);
      }
    });
  }

  // Validate last_updated
  const dateRegex = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
  if (typeof obj.last_updated !== 'string') {
    errors.push('last_updated must be a string');
  } else if (!dateRegex.test(obj.last_updated)) {
    errors.push('invalid last_updated format');
  }

  return {
    isValid: errors.length === 0,
    errors
  };
}

// Utility functions
export function validateFileSize(sizeInBytes: number): ValidationResult {
  const errors: string[] = [];
  const maxSize = 250 * 1024 * 1024; // 250MB in bytes

  if (sizeInBytes > maxSize) {
    errors.push('file size exceeds 250MB limit');
  }

  return {
    isValid: errors.length === 0,
    errors
  };
}

export function validateProgressStage(stage: string, progress: number): ValidationResult {
  const errors: string[] = [];
  const stageProgressMap: Record<string, number> = {
    'parse': 25,
    'validate': 50,
    'classify': 75,
    'complete': 100
  };

  if (stageProgressMap[stage] && stageProgressMap[stage] !== progress) {
    errors.push(`stage ${stage} must have progress ${stageProgressMap[stage]}`);
  }

  return {
    isValid: errors.length === 0,
    errors
  };
}

export function canStartProcessing(state: ProcessingState, fileType: FileType): boolean {
  const progress = fileType === FileType.CAMPAIGN_XLSX ? state.campaign_xlsx : state.reporting_csv;
  
  if (!progress) {
    return true; // No processing for this file type
  }

  // Can start if previous processing completed, failed, or was cancelled
  return ['completed', 'error', 'cancelled'].includes(progress.status);
}

export function getProcessingPercentage(stage: ProcessingStage): number {
  const stageProgressMap: Record<ProcessingStage, number> = {
    [ProcessingStage.PARSE]: 25,
    [ProcessingStage.VALIDATE]: 50,
    [ProcessingStage.CLASSIFY]: 75,
    [ProcessingStage.COMPLETE]: 100
  };

  return stageProgressMap[stage];
}

export function isValidFileType(fileType: string): boolean {
  return ['campaign_xlsx', 'reporting_csv'].includes(fileType);
}

export function createProcessingError(
  category: ErrorCategory,
  severity: ErrorSeverity,
  code: string,
  message: string,
  context: { file_type: FileType; [key: string]: any }
): ProcessingError {
  return {
    error_id: `error-${Date.now()}-${Math.random().toString(36).substring(2, 15)}`,
    timestamp: new Date().toISOString(),
    category,
    severity,
    code,
    message,
    context
  };
}