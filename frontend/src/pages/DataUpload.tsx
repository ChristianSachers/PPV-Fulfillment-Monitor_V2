import React, { useState, useRef } from 'react';
import { Card, Button, Alert, Spin, Typography } from 'antd';
import { UploadOutlined, DeleteOutlined } from '@ant-design/icons';
import * as uploadService from '../services/uploadService';
import { ValidationResult } from '../services/uploadService';
import { ProgressTracker } from '../components/ProgressTracker';

const { Text } = Typography;

interface FileProgress {
  id: string;
  name: string;
  size: number;
  progress: number;
  status: 'uploading' | 'completed' | 'failed' | 'pending';
}

type UploadState = 'idle' | 'uploading' | 'success' | 'error';

const DataUpload: React.FC = () => {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploadState, setUploadState] = useState<UploadState>('idle');
  const [uploadProgress, setUploadProgress] = useState<FileProgress[]>([]);
  const [errorMessage, setErrorMessage] = useState<string>('');
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [uploadIds, setUploadIds] = useState<string[]>([]);
  const [currentUploadId, setCurrentUploadId] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string>('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const uploadButtonRef = useRef<HTMLButtonElement>(null);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    setSelectedFiles(files);
    setValidationErrors([]);
    setErrorMessage('');
    setUploadState('idle');

    // Validate each file
    const errors: string[] = [];
    files.forEach(file => {
      const validation: ValidationResult = uploadService.validateFile(file);
      if (!validation.isValid) {
        errors.push(...validation.errors);
      }
    });
    
    if (errors.length > 0) {
      setValidationErrors(errors);
    }
  };

  const handleClearFiles = () => {
    setSelectedFiles([]);
    setValidationErrors([]);
    setErrorMessage('');
    setUploadState('idle');
    setUploadProgress([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleUpload = async () => {
    if (selectedFiles.length === 0 || validationErrors.length > 0) return;

    setUploadState('uploading'); 
    setErrorMessage('');
    setStatusMessage('Upload in progress');
    
    // Initialize progress tracking
    const initialProgress: FileProgress[] = selectedFiles.map((file, index) => ({
      id: `${index}-${file.name}`,
      name: file.name,
      size: file.size,
      progress: 0,
      status: 'pending' as const
    }));
    setUploadProgress(initialProgress);

    try {
      const newUploadIds: string[] = [];
      
      // Generate a temporary upload ID for cancellation purposes
      const currentUploadTempId = Math.random().toString(36).substring(7);
      setCurrentUploadId(currentUploadTempId);
      
      // Upload files sequentially
      for (let i = 0; i < selectedFiles.length; i++) {
        const file = selectedFiles[i];
        const fileId = `${i}-${file.name}`;
        
        // Update status to uploading
        setUploadProgress(prev => prev.map(item => 
          item.id === fileId ? { ...item, status: 'uploading' as const } : item
        ));

        const result = await uploadService.uploadFile(file, (progress: number) => {
          setUploadProgress(prev => prev.map(item => 
            item.id === fileId ? { ...item, progress } : item
          ));
        });

        newUploadIds.push(result.upload_id);
        
        // Update status to completed
        setUploadProgress(prev => prev.map(item => 
          item.id === fileId ? { ...item, status: 'completed' as const, progress: 100 } : item
        ));
      }

      setUploadIds(newUploadIds);
      setCurrentUploadId(null);
      setUploadState('success');
      setStatusMessage('Upload completed successfully');
      setSelectedFiles([]);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
      
      // Clear status message after brief delay for accessibility announcement
      setTimeout(() => {
        setStatusMessage('');
      }, 100);
      
      // Hide progress tracker after success
      setTimeout(() => {
        setUploadProgress([]);
      }, 1000);

    } catch (error) {
      setCurrentUploadId(null);
      setUploadState('error');
      const errorMsg = error instanceof Error ? error.message : 'Upload failed';
      setErrorMessage(errorMsg);
      setStatusMessage('File upload failed');
      
      // Mark all remaining files as failed
      setUploadProgress(prev => prev.map(item => 
        item.status === 'uploading' || item.status === 'pending' 
          ? { ...item, status: 'failed' as const } 
          : item
      ));
    }
  };

  const handleRetry = () => {
    handleUpload();
  };

  const handleCancel = () => {
    // Cancel the current upload using the temporary ID
    if (currentUploadId) {
      uploadService.cancelUpload(currentUploadId);
    }
    // Also cancel any completed upload IDs
    uploadIds.forEach(id => {
      uploadService.cancelUpload(id);
    });
    
    setUploadState('idle');
    setUploadProgress([]);
    setCurrentUploadId(null);
  };

  const handleUploadMore = () => {
    setUploadState('idle');
    setErrorMessage('');
    setStatusMessage('');
    setUploadProgress([]);
  };

  const isUploadDisabled = selectedFiles.length === 0 || validationErrors.length > 0 || uploadState === 'uploading';
  const hasValidFiles = selectedFiles.length > 0 && validationErrors.length === 0;

  return (
    <div>
      <h1>Data Upload</h1>
      <p>Upload your data files for analysis and visualization.</p>
      
      <Card style={{ marginTop: '24px' }}>
        <div style={{ textAlign: 'center', padding: '40px 0' }}>
          <UploadOutlined style={{ fontSize: '48px', color: '#1890ff', marginBottom: '16px' }} />
          <h3>Drop files here or click to upload</h3>
          <p>Supported formats: CSV, Excel, JSON</p>
          
          <input
            ref={fileInputRef}
            data-testid="file-input"
            type="file"
            accept=".csv,.xlsx,.json"
            multiple
            aria-label="Select files to upload"
            onChange={handleFileChange}
            onKeyDown={(e) => {
              if (e.key === 'Tab' && !e.shiftKey) {
                e.preventDefault();
                if (uploadButtonRef.current) {
                  uploadButtonRef.current.focus();
                }
              }
            }}
            style={{ 
              position: 'absolute',
              left: '-1px',
              top: '-1px',
              width: '1px',
              height: '1px',
              opacity: 0,
              overflow: 'hidden',
              clip: 'rect(0,0,0,0)',
              whiteSpace: 'nowrap'
            }}
            tabIndex={0}
          />
          
          <Button 
            type="primary" 
            icon={<UploadOutlined />} 
            size="large"
            onClick={() => fileInputRef.current?.click()}
            style={{ marginBottom: '16px' }}
          >
            Select Files
          </Button>
          
          {selectedFiles.length > 0 && (
            <div style={{ marginTop: '16px' }}>
              <Text strong>{selectedFiles.length} files selected</Text>
              <div style={{ marginTop: '8px' }}>
                {selectedFiles.map((file, index) => (
                  <div key={index} style={{ margin: '4px 0' }}>
                    <Text>{file.name}</Text>
                  </div>
                ))}
              </div>
              <Button
                data-testid="clear-files-button"
                icon={<DeleteOutlined />}
                onClick={handleClearFiles}
                style={{ marginTop: '8px' }}
              >
                Clear Files
              </Button>
            </div>
          )}
        </div>
        
        {validationErrors.length > 0 && (
          <Alert
            type="error"
            message={validationErrors.join(', ')}
            style={{ marginBottom: '16px' }}
          />
        )}
        
        <div style={{ textAlign: 'center' }}>
          <Button
            ref={uploadButtonRef}
            data-testid="upload-button"
            type="primary"
            size="large"
            disabled={isUploadDisabled}
            onClick={handleUpload}
            aria-label="Start file upload"
            style={{ marginRight: '8px' }}
          >
            {uploadState === 'uploading' ? (
              <>
                <Spin data-testid="upload-spinner" size="small" style={{ marginRight: '8px' }} />
                Uploading...
              </>
            ) : (
              'Start Upload'
            )}
          </Button>
          
          {uploadState === 'uploading' && (
            <Button
              data-testid="cancel-upload-button"
              onClick={handleCancel}
            >
              Cancel Upload
            </Button>
          )}
        </div>
      </Card>

      {uploadProgress.length > 0 && uploadState !== 'success' && (
        <div style={{ marginTop: '24px' }}>
          <ProgressTracker
            files={uploadProgress}
            onCancel={(fileId) => {
              // Handle individual file cancellation
              const uploadId = uploadIds.find((_, index) => `${index}-${selectedFiles[index]?.name}` === fileId);
              if (uploadId) {
                uploadService.cancelUpload(uploadId);
              }
            }}
            onRetry={(fileId) => {
              // Handle individual file retry - for now just retry all
              handleRetry();
            }}
          />
        </div>
      )}

      {uploadState === 'error' && (
        <Alert
          data-testid="error-message"
          type="error"
          message={errorMessage}
          style={{ marginTop: '16px' }}
          action={
            <Button
              data-testid="retry-upload-button"
              size="small"
              onClick={handleRetry}
            >
              Retry
            </Button>
          }
        />
      )}

      {uploadState === 'success' && (
        <Alert
          data-testid="success-message"
          type="success"
          message="Upload completed successfully"
          style={{ marginTop: '16px' }}
          action={
            <Button
              data-testid="upload-more-button"
              type="primary"
              size="small"
              onClick={handleUploadMore}
            >
              Upload More
            </Button>
          }
        />
      )}

      <div
        data-testid="upload-status"
        aria-live="polite"
        aria-label="Upload status"
        style={{ 
          position: 'absolute',
          left: '-10000px',
          width: '1px',
          height: '1px',
          overflow: 'hidden'
        }}
      >
        {statusMessage}
      </div>
    </div>
  );
};

export default DataUpload;