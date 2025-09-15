import axios, { AxiosError } from 'axios';

const API_BASE_URL = 'http://localhost:8001/api';

// Types
export interface UploadResponse {
  upload_id: string;
  filename: string;
  file_size: number;
  upload_date: string;
  status: string;
}

export interface ValidationResult {
  isValid: boolean;
  errors: string[];
}

// Upload cancellation tracking
const uploadControllers = new Map<string, AbortController>();

/**
 * Upload a file to the server with optional progress tracking
 */
export const uploadFile = async (
  file: File,
  onProgress?: (progress: number) => void
): Promise<UploadResponse> => {
  const formData = new FormData();
  formData.append('file', file);

  const uploadId = Math.random().toString(36).substring(7);
  const controller = new AbortController();
  uploadControllers.set(uploadId, controller);

  const config = {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    signal: controller.signal,
    onUploadProgress: onProgress ? (progressEvent: any) => {
      const progress = Math.round((progressEvent.loaded / progressEvent.total) * 100);
      onProgress(progress);
    } : undefined,
  };

  try {
    const response = await uploadWithRetry(`${API_BASE_URL}/uploads/`, formData, config);
    uploadControllers.delete(uploadId);
    return response.data;
  } catch (error) {
    uploadControllers.delete(uploadId);
    if ((axios.isAxiosError(error) && error.response) || (error as any)?.response) {
      throw handleApiError(error as AxiosError);
    }
    throw error;
  }
};

/**
 * Upload with retry logic for network failures
 */
const uploadWithRetry = async (url: string, data: FormData, config: any, maxRetries = 3): Promise<any> => {
  let lastError: any;
  
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    try {
      return await axios.post(url, data, config);
    } catch (error) {
      lastError = error;
      
      // If it's an axios error with response, don't retry (API error)
      if ((axios.isAxiosError(error) && error.response) || (error as any)?.response) {
        throw error; // Don't call handleApiError here, let the caller handle it
      }
      
      // For network errors, retry unless it's the last attempt
      if (attempt === maxRetries) {
        throw error;
      }
      
      // Wait before retry (exponential backoff)
      await new Promise(resolve => setTimeout(resolve, Math.pow(2, attempt - 1) * 1000));
    }
  }
  
  throw lastError;
};

/**
 * Get list of uploads with pagination
 */
export const getUploads = async (skip = 0, limit = 20): Promise<UploadResponse[]> => {
  try {
    const response = await axios.get(`${API_BASE_URL}/uploads/`, {
      params: { skip, limit }
    });
    return response.data;
  } catch (error) {
    if ((axios.isAxiosError(error) && error.response) || (error as any)?.response) {
      throw handleApiError(error as AxiosError);
    }
    throw error;
  }
};

/**
 * Get a specific upload by ID
 */
export const getUploadById = async (id: string): Promise<UploadResponse> => {
  try {
    const response = await axios.get(`${API_BASE_URL}/uploads/${id}`);
    return response.data;
  } catch (error) {
    if ((axios.isAxiosError(error) && error.response) || (error as any)?.response) {
      throw handleApiError(error as AxiosError);
    }
    throw error;
  }
};

/**
 * Validate file before upload
 */
export const validateFile = (file: File): ValidationResult => {
  const errors: string[] = [];
  
  // Check if file is empty
  if (file.size === 0) {
    errors.push('File cannot be empty');
  }
  
  // Check file size (250MB limit)
  const maxSize = 250 * 1024 * 1024; // 250MB in bytes
  if (file.size > maxSize) {
    errors.push('File size exceeds 250MB limit');
  }
  
  // Check file type
  const allowedTypes = [
    'text/csv',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', // .xlsx
    'application/json'
  ];
  
  const allowedExtensions = ['.csv', '.xlsx', '.json'];
  const fileName = file.name.toLowerCase();
  const hasValidType = allowedTypes.includes(file.type);
  const hasValidExtension = allowedExtensions.some(ext => fileName.endsWith(ext));
  
  if (!hasValidType && !hasValidExtension) {
    errors.push('Unsupported file type. Only CSV, Excel, and JSON files are allowed');
  }
  
  return {
    isValid: errors.length === 0,
    errors
  };
};

/**
 * Cancel an ongoing upload
 */
export const cancelUpload = (uploadId: string): void => {
  const controller = uploadControllers.get(uploadId);
  if (controller) {
    controller.abort();
    uploadControllers.delete(uploadId);
  }
  // Don't throw error for non-existent uploads, as per test expectations
};

/**
 * Handle API errors and extract meaningful error messages
 */
const handleApiError = (error: AxiosError): Error => {
  if (error.response?.data && typeof error.response.data === 'object') {
    const errorData = error.response.data as any;
    if (errorData.detail) {
      return new Error(errorData.detail);
    }
  }
  
  // Fallback error messages based on status code
  let errorMessage: string;
  switch (error.response?.status) {
    case 404:
      errorMessage = 'Upload not found';
      break;
    case 422:
      errorMessage = 'File validation failed';
      break;
    case 500:
      errorMessage = 'Internal server error';
      break;
    default:
      errorMessage = error.message || 'An error occurred';
  }
  
  return new Error(errorMessage);
};