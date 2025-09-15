import React from 'react';
import { Typography, Space, Alert } from 'antd';
import { UploadControlPanel } from '../components/UploadControlPanel';
import { ErrorDisplayPanel } from '../components/ErrorDisplayPanel';
import { useProcessingStatus } from '../hooks/useProcessingStatus';
import { FileType, ProcessingFileType } from '../types/processing';

const { Text, Title } = Typography;

const DataUpload: React.FC = () => {
  // Use the processing status hook to manage state
  const {
    processingState,
    errors,
    startProcessing,
    cancelProcessing,
    hasErrors
  } = useProcessingStatus();

  // Map FileType to ProcessingFileType
  const mapToProcessingFileType = (fileType: FileType): ProcessingFileType => {
    return fileType === FileType.CAMPAIGN_XLSX 
      ? ProcessingFileType.CAMPAIGN_XLSX 
      : ProcessingFileType.REPORTING_CSV;
  };

  // Handle upload start
  const handleUploadStart = async (file: File, fileType: FileType) => {
    try {
      await startProcessing(file, mapToProcessingFileType(fileType));
    } catch (error) {
      console.error('Upload start failed:', error);
    }
  };

  // Handle cancel processing
  const handleCancelProcessing = async (fileType: FileType) => {
    try {
      await cancelProcessing(mapToProcessingFileType(fileType));
    } catch (error) {
      console.error('Cancel processing failed:', error);
    }
  };

  return (
    <div>
      <Title level={1}>Data Upload</Title>
      <Text type="secondary" style={{ fontSize: '16px', display: 'block', marginBottom: '24px' }}>
        Upload Campaign XLSX and Reporting CSV files for processing and analysis.
      </Text>

      <Space direction="vertical" size="large" style={{ width: '100%' }}>
        {/* Upload Control Panel */}
        <UploadControlPanel
          processingState={processingState}
          onUploadStart={handleUploadStart}
          onCancelProcessing={handleCancelProcessing}
        />

        {/* Error Display Panel */}
        {hasErrors && (
          <ErrorDisplayPanel
            errors={errors}
            showGrouped={true}
            groupSimilarErrors={true}
            showTimezone={true}
          />
        )}

        {/* Status Information */}
        <Alert
          message="Upload Processing Pipeline"
          description="Monitor your file processing progress above. Files are processed through parsing, validation, and classification stages."
          type="info"
          showIcon
          style={{ marginTop: '24px' }}
        />
      </Space>
    </div>
  );
};

export default DataUpload;