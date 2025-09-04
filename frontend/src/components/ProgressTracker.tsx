import React from 'react';
import { Card, Button, Typography } from 'antd';
import { CloseOutlined, ReloadOutlined } from '@ant-design/icons';

const { Text } = Typography;

interface FileProgress {
  id: string;
  name: string;
  size: number;
  progress: number; // 0-100
  status: 'uploading' | 'completed' | 'failed' | 'pending';
}

interface ProgressTrackerProps {
  files: FileProgress[];
  onCancel?: (fileId: string) => void;
  onRetry?: (fileId: string) => void;
}

const formatFileSize = (bytes: number): string => {
  if (bytes === 0) return '0 Bytes';
  
  const k = 1000; // Use decimal units (1000) instead of binary (1024)
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  
  const value = bytes / Math.pow(k, i);
  
  // Format differently based on size unit
  let formattedValue: string;
  if (i === 0) {
    // Bytes - no decimals
    formattedValue = value.toString();
  } else if (i === 1 && value === Math.floor(value)) {
    // KB - no decimals if it's a whole number
    formattedValue = value.toString();
  } else {
    // MB, GB or fractional KB - 2 decimal places, but remove trailing zeros
    formattedValue = parseFloat(value.toFixed(2)).toString();
  }
  
  return `${formattedValue} ${sizes[i]}`;
};

const getStatusText = (status: FileProgress['status']): string => {
  switch (status) {
    case 'uploading':
      return 'Uploading...';
    case 'completed':
      return 'Completed';
    case 'failed':
      return 'Failed';
    case 'pending':
      return 'Pending';
    default:
      return '';
  }
};

const getStatusClass = (status: FileProgress['status']): string => {
  return `status-${status}`;
};

export const ProgressTracker: React.FC<ProgressTrackerProps> = ({
  files,
  onCancel,
  onRetry
}) => {
  if (files.length === 0) {
    return (
      <div 
        data-testid="progress-tracker"
        aria-label="File upload progress tracker"
      >
        <Text>No files to display</Text>
      </div>
    );
  }

  return (
    <div 
      data-testid="progress-tracker"
      aria-label="File upload progress tracker"
    >
      {files.map((file) => (
        <Card 
          key={file.id} 
          style={{ marginBottom: 16 }}
          size="small"
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
            <div style={{ flex: 1 }}>
              <Text strong>{file.name}</Text>
              <div style={{ fontSize: '12px', color: '#666', marginTop: 2 }}>
                {formatFileSize(file.size)}
              </div>
            </div>
            
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div 
                data-testid={`status-${file.status}-${file.id}`}
                className={getStatusClass(file.status)}
                style={{ 
                  fontSize: '12px',
                  color: file.status === 'completed' ? '#52c41a' : 
                         file.status === 'failed' ? '#ff4d4f' : 
                         file.status === 'uploading' ? '#1890ff' : '#666'
                }}
              >
                {getStatusText(file.status)}
              </div>
              
              {file.status === 'uploading' && onCancel && (
                <Button
                  data-testid={`cancel-button-${file.id}`}
                  size="small"
                  type="text"
                  icon={<CloseOutlined />}
                  onClick={() => onCancel(file.id)}
                  aria-label={`Cancel upload for ${file.name}`}
                />
              )}
              
              {file.status === 'failed' && onRetry && (
                <Button
                  data-testid={`retry-button-${file.id}`}
                  size="small"
                  type="text"
                  icon={<ReloadOutlined />}
                  onClick={() => onRetry(file.id)}
                  aria-label={`Retry upload for ${file.name}`}
                />
              )}
            </div>
          </div>
          
          <div style={{ position: 'relative' }}>
            <div
              data-testid={`progress-bar-${file.id}`}
              role="progressbar"
              aria-valuenow={file.progress}
              aria-valuemin={0}
              aria-valuemax={100}
              style={{
                width: '100%',
                height: '8px',
                backgroundColor: '#f0f0f0',
                borderRadius: '4px',
                overflow: 'hidden'
              }}
            >
              <div
                data-testid={`progress-fill-${file.id}`}
                style={{
                  width: `${file.progress}%`,
                  height: '100%',
                  backgroundColor: file.status === 'completed' ? '#52c41a' : 
                                 file.status === 'failed' ? '#ff4d4f' : 
                                 '#1890ff',
                  transition: 'width 0.3s ease'
                }}
              />
            </div>
            
            <div style={{ 
              position: 'absolute', 
              top: '10px', 
              right: 0, 
              fontSize: '12px', 
              color: '#666' 
            }}>
              {file.progress}%
            </div>
          </div>
        </Card>
      ))}
    </div>
  );
};