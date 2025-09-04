import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom';
import { ProgressTracker } from '../ProgressTracker';

describe('ProgressTracker', () => {
  const mockFiles = [
    {
      id: '1',
      name: 'document.pdf',
      size: 1024000,
      progress: 50,
      status: 'uploading'
    },
    {
      id: '2',
      name: 'image.jpg',
      size: 512000,
      progress: 100,
      status: 'completed'
    },
    {
      id: '3',
      name: 'video.mp4',
      size: 5120000,
      progress: 25,
      status: 'failed'
    }
  ];

  const mockOnCancel = jest.fn();
  const mockOnRetry = jest.fn();

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe('Rendering', () => {
    test('renders progress bars for all files', () => {
      render(<ProgressTracker files={mockFiles} />);
      
      mockFiles.forEach(file => {
        expect(screen.getByTestId(`progress-bar-${file.id}`)).toBeInTheDocument();
      });
    });

    test('displays correct file names', () => {
      render(<ProgressTracker files={mockFiles} />);
      
      expect(screen.getByText('document.pdf')).toBeInTheDocument();
      expect(screen.getByText('image.jpg')).toBeInTheDocument();
      expect(screen.getByText('video.mp4')).toBeInTheDocument();
    });

    test('displays formatted file sizes', () => {
      render(<ProgressTracker files={mockFiles} />);
      
      expect(screen.getByText('1.02 MB')).toBeInTheDocument();
      expect(screen.getByText('512 KB')).toBeInTheDocument();
      expect(screen.getByText('5.12 MB')).toBeInTheDocument();
    });

    test('shows correct progress percentages', () => {
      render(<ProgressTracker files={mockFiles} />);
      
      expect(screen.getByText('50%')).toBeInTheDocument();
      expect(screen.getByText('100%')).toBeInTheDocument();
      expect(screen.getByText('25%')).toBeInTheDocument();
    });

    test('displays status indicators', () => {
      render(<ProgressTracker files={mockFiles} />);
      
      expect(screen.getByTestId('status-uploading-1')).toBeInTheDocument();
      expect(screen.getByTestId('status-completed-2')).toBeInTheDocument();
      expect(screen.getByTestId('status-failed-3')).toBeInTheDocument();
    });

    test('renders without files when array is empty', () => {
      render(<ProgressTracker files={[]} />);
      
      expect(screen.getByTestId('progress-tracker')).toBeInTheDocument();
      expect(screen.getByText('No files to display')).toBeInTheDocument();
    });
  });

  describe('Progress Bar Functionality', () => {
    test('progress bars show correct fill percentage', () => {
      render(<ProgressTracker files={mockFiles} />);
      
      const progressBar1 = screen.getByTestId(`progress-fill-${mockFiles[0].id}`);
      const progressBar2 = screen.getByTestId(`progress-fill-${mockFiles[1].id}`);
      const progressBar3 = screen.getByTestId(`progress-fill-${mockFiles[2].id}`);
      
      expect(progressBar1).toHaveStyle('width: 50%');
      expect(progressBar2).toHaveStyle('width: 100%');
      expect(progressBar3).toHaveStyle('width: 25%');
    });

    test('progress bars have correct ARIA attributes', () => {
      render(<ProgressTracker files={mockFiles} />);
      
      const progressBar1 = screen.getByTestId(`progress-bar-${mockFiles[0].id}`);
      
      expect(progressBar1).toHaveAttribute('role', 'progressbar');
      expect(progressBar1).toHaveAttribute('aria-valuenow', '50');
      expect(progressBar1).toHaveAttribute('aria-valuemin', '0');
      expect(progressBar1).toHaveAttribute('aria-valuemax', '100');
    });
  });

  describe('Cancel Button Functionality', () => {
    test('shows cancel button for uploading files', () => {
      render(<ProgressTracker files={mockFiles} onCancel={mockOnCancel} />);
      
      expect(screen.getByTestId('cancel-button-1')).toBeInTheDocument();
      expect(screen.queryByTestId('cancel-button-2')).not.toBeInTheDocument();
      expect(screen.queryByTestId('cancel-button-3')).not.toBeInTheDocument();
    });

    test('calls onCancel with correct file ID when cancel button is clicked', () => {
      render(<ProgressTracker files={mockFiles} onCancel={mockOnCancel} />);
      
      const cancelButton = screen.getByTestId('cancel-button-1');
      fireEvent.click(cancelButton);
      
      expect(mockOnCancel).toHaveBeenCalledTimes(1);
      expect(mockOnCancel).toHaveBeenCalledWith('1');
    });

    test('does not show cancel button when onCancel is not provided', () => {
      render(<ProgressTracker files={mockFiles} />);
      
      expect(screen.queryByTestId('cancel-button-1')).not.toBeInTheDocument();
    });
  });

  describe('Retry Button Functionality', () => {
    test('shows retry button for failed files', () => {
      render(<ProgressTracker files={mockFiles} onRetry={mockOnRetry} />);
      
      expect(screen.queryByTestId('retry-button-1')).not.toBeInTheDocument();
      expect(screen.queryByTestId('retry-button-2')).not.toBeInTheDocument();
      expect(screen.getByTestId('retry-button-3')).toBeInTheDocument();
    });

    test('calls onRetry with correct file ID when retry button is clicked', () => {
      render(<ProgressTracker files={mockFiles} onRetry={mockOnRetry} />);
      
      const retryButton = screen.getByTestId('retry-button-3');
      fireEvent.click(retryButton);
      
      expect(mockOnRetry).toHaveBeenCalledTimes(1);
      expect(mockOnRetry).toHaveBeenCalledWith('3');
    });

    test('does not show retry button when onRetry is not provided', () => {
      render(<ProgressTracker files={mockFiles} />);
      
      expect(screen.queryByTestId('retry-button-3')).not.toBeInTheDocument();
    });
  });

  describe('Status Indicators', () => {
    test('applies correct CSS classes for different statuses', () => {
      render(<ProgressTracker files={mockFiles} />);
      
      expect(screen.getByTestId('status-uploading-1')).toHaveClass('status-uploading');
      expect(screen.getByTestId('status-completed-2')).toHaveClass('status-completed');
      expect(screen.getByTestId('status-failed-3')).toHaveClass('status-failed');
    });

    test('shows appropriate status text', () => {
      render(<ProgressTracker files={mockFiles} />);
      
      expect(screen.getByText('Uploading...')).toBeInTheDocument();
      expect(screen.getByText('Completed')).toBeInTheDocument();
      expect(screen.getByText('Failed')).toBeInTheDocument();
    });
  });

  describe('Edge Cases', () => {
    test('handles files with zero progress', () => {
      const filesWithZeroProgress = [
        { id: '1', name: 'test.txt', size: 1000, progress: 0, status: 'pending' }
      ];
      
      render(<ProgressTracker files={filesWithZeroProgress} />);
      
      expect(screen.getByText('0%')).toBeInTheDocument();
      expect(screen.getByTestId('progress-fill-1')).toHaveStyle('width: 0%');
    });

    test('handles files with 100% progress', () => {
      const filesWithFullProgress = [
        { id: '1', name: 'test.txt', size: 1000, progress: 100, status: 'completed' }
      ];
      
      render(<ProgressTracker files={filesWithFullProgress} />);
      
      expect(screen.getByText('100%')).toBeInTheDocument();
      expect(screen.getByTestId('progress-fill-1')).toHaveStyle('width: 100%');
    });

    test('handles very large file sizes', () => {
      const largeFiles = [
        { id: '1', name: 'huge.zip', size: 1073741824, progress: 50, status: 'uploading' }
      ];
      
      render(<ProgressTracker files={largeFiles} />);
      
      expect(screen.getByText('1.07 GB')).toBeInTheDocument();
    });

    test('handles very long file names', () => {
      const longNameFiles = [
        { 
          id: '1', 
          name: 'very_long_file_name_that_might_cause_layout_issues.txt', 
          size: 1000, 
          progress: 50, 
          status: 'uploading' 
        }
      ];
      
      render(<ProgressTracker files={longNameFiles} />);
      
      expect(screen.getByText('very_long_file_name_that_might_cause_layout_issues.txt')).toBeInTheDocument();
    });
  });

  describe('Accessibility', () => {
    test('has proper ARIA labels for screen readers', () => {
      render(<ProgressTracker files={mockFiles} />);
      
      expect(screen.getByLabelText('File upload progress tracker')).toBeInTheDocument();
    });

    test('cancel and retry buttons have descriptive labels', () => {
      render(<ProgressTracker files={mockFiles} onCancel={mockOnCancel} onRetry={mockOnRetry} />);
      
      expect(screen.getByLabelText('Cancel upload for document.pdf')).toBeInTheDocument();
      expect(screen.getByLabelText('Retry upload for video.mp4')).toBeInTheDocument();
    });
  });
});