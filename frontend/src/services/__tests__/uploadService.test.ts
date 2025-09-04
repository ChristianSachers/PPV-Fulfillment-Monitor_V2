import axios from 'axios';
import { uploadFile, getUploads, getUploadById, validateFile, cancelUpload } from '../uploadService';

// Mock axios
jest.mock('axios');
const mockedAxios = axios as jest.Mocked<typeof axios>;

// Mock data types
interface UploadResponse {
  upload_id: string;
  filename: string;
  file_size: number;
  upload_date: string;
  status: string;
}

interface ValidationResult {
  isValid: boolean;
  errors: string[];
}

describe('UploadService', () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockedAxios.post.mockClear();
    mockedAxios.get.mockClear();
  });

  describe('uploadFile', () => {
    it('should upload file successfully with progress tracking', async () => {
      const mockFile = new File(['test content'], 'test.csv', { type: 'text/csv' });
      const mockProgress = jest.fn();
      const mockResponse: UploadResponse = {
        upload_id: '123',
        filename: 'test.csv',
        file_size: 1024,
        upload_date: '2025-09-04T10:00:00Z',
        status: 'completed'
      };

      mockedAxios.post.mockResolvedValue({ data: mockResponse });

      const result = await uploadFile(mockFile, mockProgress);

      expect(mockedAxios.post).toHaveBeenCalledWith(
        'http://localhost:8001/api/uploads/',
        expect.any(FormData),
        expect.objectContaining({
          headers: { 'Content-Type': 'multipart/form-data' },
          onUploadProgress: expect.any(Function)
        })
      );
      expect(result).toEqual(mockResponse);
    });

    it('should track upload progress correctly', async () => {
      const mockFile = new File(['test content'], 'test.csv', { type: 'text/csv' });
      const mockProgress = jest.fn();
      const mockResponse: UploadResponse = {
        upload_id: '123',
        filename: 'test.csv',
        file_size: 1024,
        upload_date: '2025-09-04T10:00:00Z',
        status: 'completed'
      };

      mockedAxios.post.mockImplementation((url, data, config) => {
        // Simulate progress events
        if (config?.onUploadProgress) {
          config.onUploadProgress({ loaded: 50, total: 100 });
          config.onUploadProgress({ loaded: 100, total: 100 });
        }
        return Promise.resolve({ data: mockResponse });
      });

      await uploadFile(mockFile, mockProgress);

      expect(mockProgress).toHaveBeenCalledWith(50);
      expect(mockProgress).toHaveBeenCalledWith(100);
    });

    it('should handle upload errors', async () => {
      const mockFile = new File(['test content'], 'test.csv', { type: 'text/csv' });
      const mockError = {
        response: {
          status: 422,
          data: { detail: 'File validation failed' }
        }
      };

      mockedAxios.post.mockRejectedValue(mockError);

      await expect(uploadFile(mockFile)).rejects.toThrow('File validation failed');
    });

    it('should handle network failures with retry logic', async () => {
      const mockFile = new File(['test content'], 'test.csv', { type: 'text/csv' });
      const networkError = new Error('Network Error');

      mockedAxios.post.mockRejectedValueOnce(networkError);
      mockedAxios.post.mockRejectedValueOnce(networkError);
      mockedAxios.post.mockResolvedValueOnce({
        data: {
          upload_id: '123',
          filename: 'test.csv',
          file_size: 1024,
          upload_date: '2025-09-04T10:00:00Z',
          status: 'completed'
        }
      });

      const result = await uploadFile(mockFile);

      expect(mockedAxios.post).toHaveBeenCalledTimes(3);
      expect(result.upload_id).toBe('123');
    });

    it('should upload without progress callback', async () => {
      const mockFile = new File(['test content'], 'test.csv', { type: 'text/csv' });
      const mockResponse: UploadResponse = {
        upload_id: '123',
        filename: 'test.csv',
        file_size: 1024,
        upload_date: '2025-09-04T10:00:00Z',
        status: 'completed'
      };

      mockedAxios.post.mockResolvedValue({ data: mockResponse });

      const result = await uploadFile(mockFile);

      expect(result).toEqual(mockResponse);
    });
  });

  describe('getUploads', () => {
    it('should fetch uploads with default pagination', async () => {
      const mockUploads: UploadResponse[] = [
        {
          upload_id: '1',
          filename: 'file1.csv',
          file_size: 1024,
          upload_date: '2025-09-04T10:00:00Z',
          status: 'completed'
        },
        {
          upload_id: '2',
          filename: 'file2.xlsx',
          file_size: 2048,
          upload_date: '2025-09-04T11:00:00Z',
          status: 'processing'
        }
      ];

      mockedAxios.get.mockResolvedValue({ data: mockUploads });

      const result = await getUploads();

      expect(mockedAxios.get).toHaveBeenCalledWith(
        'http://localhost:8001/api/uploads/',
        { params: { skip: 0, limit: 20 } }
      );
      expect(result).toEqual(mockUploads);
    });

    it('should fetch uploads with custom pagination parameters', async () => {
      const mockUploads: UploadResponse[] = [];

      mockedAxios.get.mockResolvedValue({ data: mockUploads });

      await getUploads(10, 5);

      expect(mockedAxios.get).toHaveBeenCalledWith(
        'http://localhost:8001/api/uploads/',
        { params: { skip: 10, limit: 5 } }
      );
    });

    it('should handle API errors when fetching uploads', async () => {
      const mockError = {
        response: {
          status: 500,
          data: { detail: 'Internal server error' }
        }
      };

      mockedAxios.get.mockRejectedValue(mockError);

      await expect(getUploads()).rejects.toThrow('Internal server error');
    });
  });

  describe('getUploadById', () => {
    it('should fetch specific upload by ID', async () => {
      const mockUpload: UploadResponse = {
        upload_id: '123',
        filename: 'test.csv',
        file_size: 1024,
        upload_date: '2025-09-04T10:00:00Z',
        status: 'completed'
      };

      mockedAxios.get.mockResolvedValue({ data: mockUpload });

      const result = await getUploadById('123');

      expect(mockedAxios.get).toHaveBeenCalledWith(
        'http://localhost:8001/api/uploads/123'
      );
      expect(result).toEqual(mockUpload);
    });

    it('should handle 404 error for non-existent upload', async () => {
      const mockError = {
        response: {
          status: 404,
          data: { detail: 'Upload not found' }
        }
      };

      mockedAxios.get.mockRejectedValue(mockError);

      await expect(getUploadById('invalid-id')).rejects.toThrow('Upload not found');
    });
  });

  describe('validateFile', () => {
    it('should validate CSV file successfully', () => {
      const csvFile = new File(['test'], 'test.csv', { type: 'text/csv' });

      const result = validateFile(csvFile);

      expect(result.isValid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it('should validate Excel file successfully', () => {
      const excelFile = new File(['test'], 'test.xlsx', {
        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
      });

      const result = validateFile(excelFile);

      expect(result.isValid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it('should validate JSON file successfully', () => {
      const jsonFile = new File(['{}'], 'test.json', { type: 'application/json' });

      const result = validateFile(jsonFile);

      expect(result.isValid).toBe(true);
      expect(result.errors).toHaveLength(0);
    });

    it('should reject files that are too large', () => {
      const largeFile = new File(['test content'], 'large.csv', { type: 'text/csv' });
      
      // Mock the file size to be larger than 500MB
      Object.defineProperty(largeFile, 'size', {
        value: 500 * 1024 * 1024 + 1,
        writable: false
      });

      const result = validateFile(largeFile);

      expect(result.isValid).toBe(false);
      expect(result.errors).toContain('File size exceeds 500MB limit');
    });

    it('should reject unsupported file types', () => {
      const textFile = new File(['test'], 'test.txt', { type: 'text/plain' });

      const result = validateFile(textFile);

      expect(result.isValid).toBe(false);
      expect(result.errors).toContain('Unsupported file type. Only CSV, Excel, and JSON files are allowed');
    });

    it('should reject empty files', () => {
      const emptyFile = new File([''], 'empty.csv', { type: 'text/csv' });

      const result = validateFile(emptyFile);

      expect(result.isValid).toBe(false);
      expect(result.errors).toContain('File cannot be empty');
    });

    it('should return multiple validation errors', () => {
      const invalidFile = new File([''], 'test.txt', { type: 'text/plain' });

      const result = validateFile(invalidFile);

      expect(result.isValid).toBe(false);
      expect(result.errors.length).toBeGreaterThan(1);
    });
  });

  describe('cancelUpload', () => {
    it('should cancel ongoing upload', () => {
      const uploadId = '123';

      expect(() => cancelUpload(uploadId)).not.toThrow();
    });

    it('should handle cancellation of non-existent upload', () => {
      const uploadId = 'non-existent';

      expect(() => cancelUpload(uploadId)).not.toThrow();
    });
  });
});