import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import DataUpload from '../DataUpload';
import * as uploadService from '../../services/uploadService';

// Mock the upload service
jest.mock('../../services/uploadService');
const mockedUploadService = uploadService as jest.Mocked<typeof uploadService>;

// Mock the ProgressTracker component
jest.mock('../../components/ProgressTracker', () => ({
  ProgressTracker: ({ files, onCancel, onRetry }: any) => (
    <div data-testid="progress-tracker" data-files-count={files.length}>
      {files.map((file: any) => (
        <div key={file.id} data-testid={`progress-item-${file.id}`}>
          <span>{file.name}</span>
          <span>{file.progress}%</span>
          <span>{file.status}</span>
          {file.status === 'uploading' && onCancel && (
            <button
              data-testid={`cancel-${file.id}`}
              onClick={() => onCancel(file.id)}
            >
              Cancel
            </button>
          )}
          {file.status === 'failed' && onRetry && (
            <button
              data-testid={`retry-${file.id}`}
              onClick={() => onRetry(file.id)}
            >
              Retry
            </button>
          )}
        </div>
      ))}
    </div>
  )
}));

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

describe('DataUpload Component', () => {
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
      const cardElement = document.querySelector('.ant-card');
      expect(cardElement).toBeInTheDocument();
      expect(cardElement?.querySelector('.ant-card-body')).toBeInTheDocument();
    });

    test('renders Ant Design Button components correctly', () => {
      render(<DataUpload />);
      
      // Test for Ant Design Button components - should fail if Buttons don't render
      const buttonElements = document.querySelectorAll('.ant-btn');
      expect(buttonElements.length).toBeGreaterThan(0);
      
      // Check specific buttons exist
      const selectFilesButton = screen.getByText('Select Files');
      expect(selectFilesButton.closest('.ant-btn')).toBeInTheDocument();
      
      const uploadButton = screen.getByTestId('upload-button');
      expect(uploadButton.closest('.ant-btn')).toBeInTheDocument();
    });

    test('renders Ant Design Icons correctly', () => {
      render(<DataUpload />);
      
      // Test icons render - should fail if @ant-design/icons has issues
      const iconElements = document.querySelectorAll('[class*="anticon"]');
      expect(iconElements.length).toBeGreaterThan(0);
      
      // Check for specific icons
      expect(document.querySelector('[class*="anticon-upload"]')).toBeInTheDocument();
    });

    test('renders Ant Design Typography components correctly', () => {
      render(<DataUpload />);
      
      // Test Typography Text component
      const textElements = document.querySelectorAll('.ant-typography');
      expect(textElements.length).toBeGreaterThan(0);
    });

    test('renders Ant Design Alert components when needed', async () => {
      // Mock validation to show error alert
      mockedUploadService.validateFile.mockReturnValue({
        isValid: false,
        errors: ['Test validation error']
      });

      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      const testFile = new File(['test'], 'test.txt', { type: 'text/plain' });
      
      fireEvent.change(fileInput, { target: { files: [testFile] } });
      
      // Should render Alert component for validation errors
      await waitFor(() => {
        const alertElement = document.querySelector('.ant-alert');
        expect(alertElement).toBeInTheDocument();
        expect(alertElement?.querySelector('.ant-alert-message')).toBeInTheDocument();
      });
    });

    test('renders Ant Design Spin component during upload', async () => {
      mockedUploadService.uploadFile.mockImplementation(() => 
        new Promise(resolve => {
          setTimeout(() => resolve({ upload_id: 'test-id' }), 1000);
        })
      );

      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      const testFile = new File(['test content'], 'test.csv', { type: 'text/csv' });
      
      fireEvent.change(fileInput, { target: { files: [testFile] } });
      
      const uploadButton = screen.getByTestId('upload-button');
      fireEvent.click(uploadButton);
      
      // Should render Spin component during upload
      const spinElement = screen.getByTestId('upload-spinner');
      expect(spinElement.closest('.ant-spin')).toBeInTheDocument();
    });

    test('no deprecation warnings from Ant Design components', () => {
      render(<DataUpload />);
      
      // Should fail if there are Ant Design deprecation warnings
      const deprecationWarnings = consoleErrors.filter(err => 
        err.includes('deprecated') || err.includes('Warning')
      );
      expect(deprecationWarnings).toHaveLength(0);
    });

    test('no unhandled JavaScript errors during render', () => {
      render(<DataUpload />);
      
      // Should fail if there are JavaScript runtime errors
      const jsErrors = consoleErrors.filter(err => 
        err.includes('TypeError') || 
        err.includes('ReferenceError') || 
        err.includes('SyntaxError')
      );
      expect(jsErrors).toHaveLength(0);
    });

    test('all DataUpload imports load successfully', () => {
      // This test will fail if there are import/module loading issues
      expect(() => {
        require('../DataUpload');
      }).not.toThrow();
      
      expect(() => {
        require('../../services/uploadService');
      }).not.toThrow();
      
      expect(() => {
        require('../../components/ProgressTracker');
      }).not.toThrow();
    });

    test('component mounts and unmounts cleanly', () => {
      const { unmount } = render(<DataUpload />);
      
      // Should fail if component doesn't mount properly
      expect(screen.getByText('Data Upload')).toBeInTheDocument();
      
      // Should fail if component doesn't unmount cleanly
      expect(() => unmount()).not.toThrow();
    });
  });

  describe('Initial Render', () => {
    test('renders upload interface with proper heading and description', () => {
      render(<DataUpload />);
      
      expect(screen.getByRole('heading', { name: /data upload/i })).toBeInTheDocument();
      expect(screen.getByText(/upload your data files for analysis and visualization/i)).toBeInTheDocument();
    });

    test('displays supported file formats information', () => {
      render(<DataUpload />);
      
      expect(screen.getByText(/supported formats: csv, excel, json/i)).toBeInTheDocument();
    });

    test('shows file input for selecting files', () => {
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      expect(fileInput).toBeInTheDocument();
      expect(fileInput).toHaveAttribute('type', 'file');
      expect(fileInput).toHaveAttribute('accept', '.csv,.xlsx,.json');
      expect(fileInput).toHaveAttribute('multiple');
    });

    test('displays upload button in disabled state initially', () => {
      render(<DataUpload />);
      
      const uploadButton = screen.getByTestId('upload-button');
      expect(uploadButton).toBeInTheDocument();
      expect(uploadButton).toBeDisabled();
      expect(uploadButton).toHaveTextContent(/start upload/i);
    });

    test('does not show progress tracker initially', () => {
      render(<DataUpload />);
      
      expect(screen.queryByTestId('progress-tracker')).not.toBeInTheDocument();
    });

    test('does not show success or error messages initially', () => {
      render(<DataUpload />);
      
      expect(screen.queryByTestId('success-message')).not.toBeInTheDocument();
      expect(screen.queryByTestId('error-message')).not.toBeInTheDocument();
    });
  });

  describe('File Selection', () => {
    test('enables upload button when valid files are selected', async () => {
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      const testFile = new File(['test content'], 'test.csv', { type: 'text/csv' });
      
      fireEvent.change(fileInput, { target: { files: [testFile] } });
      
      const uploadButton = screen.getByTestId('upload-button');
      expect(uploadButton).not.toBeDisabled();
    });

    test('displays selected file names and count', async () => {
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      const testFiles = [
        new File(['content1'], 'file1.csv', { type: 'text/csv' }),
        new File(['content2'], 'file2.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
      ];
      
      fireEvent.change(fileInput, { target: { files: testFiles } });
      
      expect(screen.getByText('2 files selected')).toBeInTheDocument();
      expect(screen.getByText('file1.csv')).toBeInTheDocument();
      expect(screen.getByText('file2.xlsx')).toBeInTheDocument();
    });

    test('supports multiple file selection', async () => {
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      expect(fileInput).toHaveAttribute('multiple');
      
      const testFiles = [
        new File(['content1'], 'file1.csv', { type: 'text/csv' }),
        new File(['content2'], 'file2.json', { type: 'application/json' }),
        new File(['content3'], 'file3.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
      ];
      
      fireEvent.change(fileInput, { target: { files: testFiles } });
      
      expect(screen.getByText('3 files selected')).toBeInTheDocument();
    });

    test('validates file types and shows error for invalid files', async () => {
      // Mock validation to return error for invalid file
      mockedUploadService.validateFile.mockReturnValue({
        isValid: false,
        errors: ['Unsupported file type. Only CSV, Excel, and JSON files are allowed']
      });
      
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      const invalidFile = new File(['content'], 'test.txt', { type: 'text/plain' });
      
      fireEvent.change(fileInput, { target: { files: [invalidFile] } });
      
      expect(screen.getByText(/unsupported file type/i)).toBeInTheDocument();
      expect(screen.getByTestId('upload-button')).toBeDisabled();
    });

    test('validates file size and shows error for oversized files', async () => {
      // Mock validation to return size error
      mockedUploadService.validateFile.mockReturnValue({
        isValid: false,
        errors: ['File size exceeds 500MB limit']
      });
      
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      const largeFile = new File(['x'.repeat(1000)], 'large.csv', { type: 'text/csv' });
      
      fireEvent.change(fileInput, { target: { files: [largeFile] } });
      
      expect(screen.getByText(/file size exceeds 500mb limit/i)).toBeInTheDocument();
      expect(screen.getByTestId('upload-button')).toBeDisabled();
    });

    test('allows clearing selected files', async () => {
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      const testFile = new File(['content'], 'test.csv', { type: 'text/csv' });
      
      fireEvent.change(fileInput, { target: { files: [testFile] } });
      expect(screen.getByText('1 files selected')).toBeInTheDocument();
      
      const clearButton = screen.getByTestId('clear-files-button');
      fireEvent.click(clearButton);
      
      expect(screen.queryByText(/files selected/)).not.toBeInTheDocument();
      expect(screen.getByTestId('upload-button')).toBeDisabled();
    });
  });

  describe('Upload Process', () => {
    test('starts upload process when upload button is clicked', async () => {
      const mockUploadResponse = {
        upload_id: '123',
        filename: 'test.csv',
        file_size: 1024,
        upload_date: '2025-09-04T10:00:00Z',
        status: 'completed'
      };
      
      mockedUploadService.uploadFile.mockResolvedValue(mockUploadResponse);
      
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      const testFile = new File(['content'], 'test.csv', { type: 'text/csv' });
      
      fireEvent.change(fileInput, { target: { files: [testFile] } });
      
      const uploadButton = screen.getByTestId('upload-button');
      fireEvent.click(uploadButton);
      
      expect(mockedUploadService.uploadFile).toHaveBeenCalledWith(
        testFile,
        expect.any(Function)
      );
    });

    test('disables upload button during upload process', async () => {
      // Mock a pending upload
      mockedUploadService.uploadFile.mockImplementation(() => 
        new Promise(resolve => setTimeout(resolve, 1000))
      );
      
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      const testFile = new File(['content'], 'test.csv', { type: 'text/csv' });
      
      fireEvent.change(fileInput, { target: { files: [testFile] } });
      
      const uploadButton = screen.getByTestId('upload-button');
      fireEvent.click(uploadButton);
      
      expect(uploadButton).toBeDisabled();
      expect(uploadButton).toHaveTextContent(/uploading/i);
    });

    test('shows loading spinner during upload', async () => {
      mockedUploadService.uploadFile.mockImplementation(() => 
        new Promise(resolve => setTimeout(resolve, 1000))
      );
      
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      const testFile = new File(['content'], 'test.csv', { type: 'text/csv' });
      
      fireEvent.change(fileInput, { target: { files: [testFile] } });
      
      const uploadButton = screen.getByTestId('upload-button');
      fireEvent.click(uploadButton);
      
      expect(screen.getByTestId('upload-spinner')).toBeInTheDocument();
    });
  });

  describe('Progress Display', () => {
    test('shows progress tracker during upload', async () => {
      mockedUploadService.uploadFile.mockImplementation((file, onProgress) => {
        // Simulate progress updates
        setTimeout(() => onProgress && onProgress(25), 10);
        setTimeout(() => onProgress && onProgress(50), 20);
        setTimeout(() => onProgress && onProgress(100), 30);
        
        return Promise.resolve({
          upload_id: '123',
          filename: file.name,
          file_size: file.size,
          upload_date: '2025-09-04T10:00:00Z',
          status: 'completed'
        });
      });
      
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      const testFile = new File(['content'], 'test.csv', { type: 'text/csv' });
      
      fireEvent.change(fileInput, { target: { files: [testFile] } });
      
      const uploadButton = screen.getByTestId('upload-button');
      fireEvent.click(uploadButton);
      
      await waitFor(() => {
        expect(screen.getByTestId('progress-tracker')).toBeInTheDocument();
      });
    });

    test('updates progress during upload', async () => {
      let progressCallback: ((progress: number) => void) | null = null;
      
      mockedUploadService.uploadFile.mockImplementation((file, onProgress) => {
        progressCallback = onProgress || null;
        return new Promise(resolve => {
          setTimeout(() => {
            resolve({
              upload_id: '123',
              filename: file.name,
              file_size: file.size,
              upload_date: '2025-09-04T10:00:00Z',
              status: 'completed'
            });
          }, 100);
        });
      });
      
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      const testFile = new File(['content'], 'test.csv', { type: 'text/csv' });
      
      fireEvent.change(fileInput, { target: { files: [testFile] } });
      
      const uploadButton = screen.getByTestId('upload-button');
      fireEvent.click(uploadButton);
      
      // Simulate progress updates
      if (progressCallback) {
        progressCallback(25);
        progressCallback(50);
        progressCallback(75);
      }
      
      await waitFor(() => {
        const progressTracker = screen.getByTestId('progress-tracker');
        expect(progressTracker).toBeInTheDocument();
        // The progress should be shown through the ProgressTracker component
      });
    });

    test('displays file names in progress tracker', async () => {
      mockedUploadService.uploadFile.mockResolvedValue({
        upload_id: '123',
        filename: 'test.csv',
        file_size: 1024,
        upload_date: '2025-09-04T10:00:00Z',
        status: 'completed'
      });
      
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      const testFile = new File(['content'], 'test.csv', { type: 'text/csv' });
      
      fireEvent.change(fileInput, { target: { files: [testFile] } });
      
      const uploadButton = screen.getByTestId('upload-button');
      fireEvent.click(uploadButton);
      
      await waitFor(() => {
        expect(screen.getByTestId('progress-tracker')).toBeInTheDocument();
      });
    });

    test('handles multiple file uploads with individual progress tracking', async () => {
      mockedUploadService.uploadFile
        .mockResolvedValueOnce({
          upload_id: '123',
          filename: 'file1.csv',
          file_size: 1024,
          upload_date: '2025-09-04T10:00:00Z',
          status: 'completed'
        })
        .mockResolvedValueOnce({
          upload_id: '124',
          filename: 'file2.xlsx',
          file_size: 2048,
          upload_date: '2025-09-04T10:00:00Z',
          status: 'completed'
        });
      
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      const testFiles = [
        new File(['content1'], 'file1.csv', { type: 'text/csv' }),
        new File(['content2'], 'file2.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
      ];
      
      fireEvent.change(fileInput, { target: { files: testFiles } });
      
      const uploadButton = screen.getByTestId('upload-button');
      fireEvent.click(uploadButton);
      
      await waitFor(() => {
        const progressTracker = screen.getByTestId('progress-tracker');
        expect(progressTracker).toHaveAttribute('data-files-count', '2');
      });
    });
  });

  describe('Error Handling', () => {
    test('displays error message when upload fails', async () => {
      const errorMessage = 'Upload failed due to network error';
      mockedUploadService.uploadFile.mockRejectedValue(new Error(errorMessage));
      
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      const testFile = new File(['content'], 'test.csv', { type: 'text/csv' });
      
      fireEvent.change(fileInput, { target: { files: [testFile] } });
      
      const uploadButton = screen.getByTestId('upload-button');
      fireEvent.click(uploadButton);
      
      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toBeInTheDocument();
        expect(screen.getByText(errorMessage)).toBeInTheDocument();
      });
    });

    test('allows retry after upload failure', async () => {
      mockedUploadService.uploadFile
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce({
          upload_id: '123',
          filename: 'test.csv',
          file_size: 1024,
          upload_date: '2025-09-04T10:00:00Z',
          status: 'completed'
        });
      
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      const testFile = new File(['content'], 'test.csv', { type: 'text/csv' });
      
      fireEvent.change(fileInput, { target: { files: [testFile] } });
      
      const uploadButton = screen.getByTestId('upload-button');
      fireEvent.click(uploadButton);
      
      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toBeInTheDocument();
      });
      
      const retryButton = screen.getByTestId('retry-upload-button');
      fireEvent.click(retryButton);
      
      expect(mockedUploadService.uploadFile).toHaveBeenCalledTimes(2);
    });

    test('handles server validation errors', async () => {
      const validationError = new Error('File validation failed on server');
      mockedUploadService.uploadFile.mockRejectedValue(validationError);
      
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      const testFile = new File(['content'], 'test.csv', { type: 'text/csv' });
      
      fireEvent.change(fileInput, { target: { files: [testFile] } });
      
      const uploadButton = screen.getByTestId('upload-button');
      fireEvent.click(uploadButton);
      
      await waitFor(() => {
        expect(screen.getByText(/file validation failed on server/i)).toBeInTheDocument();
      });
    });

    test('handles network connectivity issues', async () => {
      mockedUploadService.uploadFile.mockRejectedValue(new Error('Network Error'));
      
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      const testFile = new File(['content'], 'test.csv', { type: 'text/csv' });
      
      fireEvent.change(fileInput, { target: { files: [testFile] } });
      
      const uploadButton = screen.getByTestId('upload-button');
      fireEvent.click(uploadButton);
      
      await waitFor(() => {
        expect(screen.getByTestId('error-message')).toBeInTheDocument();
        expect(screen.getByText(/network error/i)).toBeInTheDocument();
      });
    });

    test('enables upload cancellation', async () => {
      mockedUploadService.uploadFile.mockImplementation(() => 
        new Promise(() => {}) // Never resolves to simulate ongoing upload
      );
      
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      const testFile = new File(['content'], 'test.csv', { type: 'text/csv' });
      
      fireEvent.change(fileInput, { target: { files: [testFile] } });
      
      const uploadButton = screen.getByTestId('upload-button');
      fireEvent.click(uploadButton);
      
      await waitFor(() => {
        expect(screen.getByTestId('progress-tracker')).toBeInTheDocument();
      });
      
      const cancelButton = screen.getByTestId('cancel-upload-button');
      fireEvent.click(cancelButton);
      
      expect(mockedUploadService.cancelUpload).toHaveBeenCalled();
    });
  });

  describe('Success State', () => {
    test('displays success message after successful upload', async () => {
      mockedUploadService.uploadFile.mockResolvedValue({
        upload_id: '123',
        filename: 'test.csv',
        file_size: 1024,
        upload_date: '2025-09-04T10:00:00Z',
        status: 'completed'
      });
      
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      const testFile = new File(['content'], 'test.csv', { type: 'text/csv' });
      
      fireEvent.change(fileInput, { target: { files: [testFile] } });
      
      const uploadButton = screen.getByTestId('upload-button');
      fireEvent.click(uploadButton);
      
      await waitFor(() => {
        expect(screen.getByTestId('success-message')).toBeInTheDocument();
        expect(screen.getByText(/upload completed successfully/i)).toBeInTheDocument();
      });
    });

    test('clears file list after successful upload', async () => {
      mockedUploadService.uploadFile.mockResolvedValue({
        upload_id: '123',
        filename: 'test.csv',
        file_size: 1024,
        upload_date: '2025-09-04T10:00:00Z',
        status: 'completed'
      });
      
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      const testFile = new File(['content'], 'test.csv', { type: 'text/csv' });
      
      fireEvent.change(fileInput, { target: { files: [testFile] } });
      expect(screen.getByText('1 files selected')).toBeInTheDocument();
      
      const uploadButton = screen.getByTestId('upload-button');
      fireEvent.click(uploadButton);
      
      await waitFor(() => {
        expect(screen.getByTestId('success-message')).toBeInTheDocument();
      });
      
      expect(screen.queryByText(/files selected/)).not.toBeInTheDocument();
    });

    test('resets upload button after successful upload', async () => {
      mockedUploadService.uploadFile.mockResolvedValue({
        upload_id: '123',
        filename: 'test.csv',
        file_size: 1024,
        upload_date: '2025-09-04T10:00:00Z',
        status: 'completed'
      });
      
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      const testFile = new File(['content'], 'test.csv', { type: 'text/csv' });
      
      fireEvent.change(fileInput, { target: { files: [testFile] } });
      
      const uploadButton = screen.getByTestId('upload-button');
      fireEvent.click(uploadButton);
      
      await waitFor(() => {
        expect(screen.getByTestId('success-message')).toBeInTheDocument();
      });
      
      expect(uploadButton).toBeDisabled();
      expect(uploadButton).toHaveTextContent(/start upload/i);
    });

    test('provides option to upload more files after success', async () => {
      mockedUploadService.uploadFile.mockResolvedValue({
        upload_id: '123',
        filename: 'test.csv',
        file_size: 1024,
        upload_date: '2025-09-04T10:00:00Z',
        status: 'completed'
      });
      
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      const testFile = new File(['content'], 'test.csv', { type: 'text/csv' });
      
      fireEvent.change(fileInput, { target: { files: [testFile] } });
      
      const uploadButton = screen.getByTestId('upload-button');
      fireEvent.click(uploadButton);
      
      await waitFor(() => {
        expect(screen.getByTestId('success-message')).toBeInTheDocument();
      });
      
      expect(screen.getByTestId('upload-more-button')).toBeInTheDocument();
    });

    test('hides progress tracker after successful upload', async () => {
      mockedUploadService.uploadFile.mockResolvedValue({
        upload_id: '123',
        filename: 'test.csv',
        file_size: 1024,
        upload_date: '2025-09-04T10:00:00Z',
        status: 'completed'
      });
      
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      const testFile = new File(['content'], 'test.csv', { type: 'text/csv' });
      
      fireEvent.change(fileInput, { target: { files: [testFile] } });
      
      const uploadButton = screen.getByTestId('upload-button');
      fireEvent.click(uploadButton);
      
      await waitFor(() => {
        expect(screen.getByTestId('success-message')).toBeInTheDocument();
      });
      
      expect(screen.queryByTestId('progress-tracker')).not.toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    test('has proper ARIA labels for screen readers', () => {
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      expect(fileInput).toHaveAttribute('aria-label', 'Select files to upload');
      
      const uploadButton = screen.getByTestId('upload-button');
      expect(uploadButton).toHaveAttribute('aria-label', 'Start file upload');
    });

    test('provides keyboard navigation support', async () => {
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      const uploadButton = screen.getByTestId('upload-button');
      
      fileInput.focus();
      expect(fileInput).toHaveFocus();
      
      fireEvent.keyDown(fileInput, { key: 'Tab', code: 'Tab' });
      expect(uploadButton).toHaveFocus();
    });

    test('announces upload status changes to screen readers', async () => {
      mockedUploadService.uploadFile.mockResolvedValue({
        upload_id: '123',
        filename: 'test.csv',
        file_size: 1024,
        upload_date: '2025-09-04T10:00:00Z',
        status: 'completed'
      });
      
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      const testFile = new File(['content'], 'test.csv', { type: 'text/csv' });
      
      fireEvent.change(fileInput, { target: { files: [testFile] } });
      
      const uploadButton = screen.getByTestId('upload-button');
      fireEvent.click(uploadButton);
      
      await waitFor(() => {
        const statusElement = screen.getByTestId('upload-status');
        expect(statusElement).toHaveAttribute('aria-live', 'polite');
        expect(statusElement).toHaveTextContent(/upload completed successfully/i);
      });
    });
  });

  describe('Edge Cases', () => {
    test('handles empty file selection gracefully', async () => {
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      
      // Simulate selecting and then clearing files
      fireEvent.change(fileInput, { target: { files: [] } });
      
      expect(screen.getByTestId('upload-button')).toBeDisabled();
      expect(screen.queryByText(/files selected/)).not.toBeInTheDocument();
    });

    test('handles very large number of files', async () => {
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      const manyFiles = Array.from({ length: 50 }, (_, i) => 
        new File([`content${i}`], `file${i}.csv`, { type: 'text/csv' })
      );
      
      fireEvent.change(fileInput, { target: { files: manyFiles } });
      
      expect(screen.getByText('50 files selected')).toBeInTheDocument();
      expect(screen.getByTestId('upload-button')).not.toBeDisabled();
    });

    test('handles duplicate file names', async () => {
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      const duplicateFiles = [
        new File(['content1'], 'duplicate.csv', { type: 'text/csv' }),
        new File(['content2'], 'duplicate.csv', { type: 'text/csv' })
      ];
      
      fireEvent.change(fileInput, { target: { files: duplicateFiles } });
      
      expect(screen.getByText('2 files selected')).toBeInTheDocument();
      // Should handle duplicates gracefully, possibly with warnings
    });

    test('maintains state during rapid file selection changes', async () => {
      render(<DataUpload />);
      
      const fileInput = screen.getByTestId('file-input');
      
      // Rapidly change file selection
      const file1 = new File(['content1'], 'file1.csv', { type: 'text/csv' });
      const file2 = new File(['content2'], 'file2.json', { type: 'application/json' });
      
      fireEvent.change(fileInput, { target: { files: [file1] } });
      expect(screen.getByText('1 files selected')).toBeInTheDocument();
      
      fireEvent.change(fileInput, { target: { files: [file2] } });
      expect(screen.getByText('1 files selected')).toBeInTheDocument();
      expect(screen.getByText('file2.json')).toBeInTheDocument();
    });
  });
});