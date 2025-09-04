/**
 * Upload Type Definitions
 * Provides TypeScript interfaces, enums, and utility functions for file upload operations
 */

// Status enum for uploads
export enum UploadStatus {
  PENDING = 'pending',
  UPLOADING = 'uploading',
  COMPLETED = 'completed',
  FAILED = 'failed'
}

// Core interfaces
export interface UploadResponse {
  upload_id: string;
  filename: string;
  file_size: number;
  upload_date: string;
  status: 'pending' | 'uploading' | 'completed' | 'failed';
}

export interface UploadFile {
  id: string;
  name: string;
  size: number;
  status: string;
}

export interface UploadState {
  files: UploadFile[];
  uploading: boolean;
  progress: Record<string, number>;
  errors: Record<string, string>;
}

export interface ValidationResult {
  isValid: boolean;
  errors: string[];
}

// Type guard functions
export function isUploadResponse(value: unknown): value is UploadResponse {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const obj = value as Record<string, unknown>;
  
  return (
    typeof obj.upload_id === 'string' &&
    typeof obj.filename === 'string' &&
    typeof obj.file_size === 'number' &&
    typeof obj.upload_date === 'string' &&
    typeof obj.status === 'string' &&
    ['pending', 'uploading', 'completed', 'failed'].includes(obj.status as string)
  );
}

export function isUploadState(value: unknown): value is UploadState {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const obj = value as Record<string, unknown>;
  
  return (
    Array.isArray(obj.files) &&
    typeof obj.uploading === 'boolean' &&
    obj.progress !== undefined && typeof obj.progress === 'object' && !Array.isArray(obj.progress) &&
    obj.errors !== undefined && typeof obj.errors === 'object' && !Array.isArray(obj.errors)
  );
}

export function isValidationResult(value: unknown): value is ValidationResult {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const obj = value as Record<string, unknown>;
  
  return (
    typeof obj.isValid === 'boolean' &&
    Array.isArray(obj.errors)
  );
}

// Validation functions
export function validateUploadResponse(value: unknown): ValidationResult {
  const errors: string[] = [];

  if (!value || typeof value !== 'object') {
    errors.push('response must be an object');
    return { isValid: false, errors };
  }

  const obj = value as Record<string, unknown>;

  // Validate upload_id
  if (typeof obj.upload_id !== 'string') {
    errors.push('upload_id must be a string');
  } else if (obj.upload_id === '') {
    errors.push('upload_id cannot be empty');
  }

  // Validate filename
  if (typeof obj.filename !== 'string') {
    errors.push('filename must be a string');
  }

  // Validate file_size
  if (typeof obj.file_size !== 'number') {
    errors.push('file_size must be a number');
  } else if (obj.file_size < 0) {
    errors.push('file_size must be positive');
  }

  // Validate upload_date
  if (typeof obj.upload_date !== 'string') {
    errors.push('upload_date must be a string');
  } else {
    // Basic ISO date format validation
    const dateRegex = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/;
    if (!dateRegex.test(obj.upload_date)) {
      errors.push('invalid upload_date format');
    }
  }

  // Validate status
  if (typeof obj.status !== 'string') {
    errors.push('status must be a string');
  } else if (!['pending', 'uploading', 'completed', 'failed'].includes(obj.status)) {
    errors.push('invalid status value');
  }

  return {
    isValid: errors.length === 0,
    errors
  };
}

export function validateUploadState(value: unknown): ValidationResult {
  const errors: string[] = [];

  if (!value || typeof value !== 'object') {
    errors.push('state must be an object');
    return { isValid: false, errors };
  }

  const obj = value as Record<string, unknown>;

  // Validate files array
  if (!Array.isArray(obj.files)) {
    errors.push('files must be an array');
  } else {
    obj.files.forEach((file: unknown, index: number) => {
      if (!file || typeof file !== 'object') {
        errors.push(`file at index ${index} must be an object`);
        return;
      }

      const fileObj = file as Record<string, unknown>;
      
      if (typeof fileObj.id !== 'string') {
        errors.push(`file at index ${index}: id must be a string`);
      }
      
      if (typeof fileObj.name !== 'string') {
        errors.push(`file at index ${index}: name must be a string`);
      } else if (fileObj.name === '') {
        errors.push(`file at index ${index}: name cannot be empty`);
      }
      
      if (typeof fileObj.size !== 'number') {
        errors.push(`file at index ${index}: size must be a number`);
      } else if (fileObj.size < 0) {
        errors.push(`file at index ${index}: size must be positive`);
      }
      
      if (typeof fileObj.status !== 'string') {
        errors.push(`file at index ${index}: status must be a string`);
      } else if (!['pending', 'uploading', 'completed', 'failed'].includes(fileObj.status)) {
        errors.push(`file at index ${index}: invalid status value`);
      }
    });
  }

  // Validate uploading
  if (typeof obj.uploading !== 'boolean') {
    errors.push('uploading must be a boolean');
  }

  // Validate progress
  if (!obj.progress || typeof obj.progress !== 'object' || Array.isArray(obj.progress)) {
    errors.push('progress must be an object');
  } else {
    const progress = obj.progress as Record<string, unknown>;
    Object.entries(progress).forEach(([key, value]) => {
      if (typeof value !== 'number') {
        errors.push(`progress.${key} must be a number`);
      } else if (value < 0 || value > 100) {
        errors.push(`progress.${key} must be between 0 and 100`);
      }
    });
  }

  // Validate errors
  if (!obj.errors || typeof obj.errors !== 'object' || Array.isArray(obj.errors)) {
    errors.push('errors must be an object');
  } else {
    const errorsObj = obj.errors as Record<string, unknown>;
    Object.entries(errorsObj).forEach(([key, value]) => {
      if (typeof value !== 'string') {
        errors.push(`errors.${key} must be a string`);
      }
    });
  }

  return {
    isValid: errors.length === 0,
    errors
  };
}