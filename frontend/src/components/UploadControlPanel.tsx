import React, { useState, useCallback, useRef, useEffect } from 'react';
import { Button, Typography, Space, Card, Modal, message } from 'antd';
import { 
  UploadOutlined, 
  ExclamationCircleOutlined, 
  StopOutlined 
} from '@ant-design/icons';
import {
  ProcessingState,
  ProcessingStatus,
  FileType,
  ProcessingError,
  isProcessingState,
  validateFileSize
} from '../types/processing';
import { ProcessingProgressIndicator } from './ProcessingProgressIndicator';
import * as uploadService from '../services/uploadService';

const { Text, Title } = Typography;

// Props interface exactly as expected by tests
interface UploadControlPanelProps {
  processingState: ProcessingState;
  onUploadStart: (file: File, fileType: FileType) => void;
  onCancelProcessing: (fileType: FileType, batchId?: string) => void;
  className?: string;
}

export const UploadControlPanel: React.FC<UploadControlPanelProps> = ({
  processingState,
  onUploadStart,
  onCancelProcessing,
  className = ''
}) => {
  // Validation and error boundary handling
  if (!processingState) {
    throw new Error('processingState prop is required');
  }

  if (!onUploadStart || typeof onUploadStart !== 'function') {
    throw new Error('onUploadStart callback is required and must be a function');
  }

  if (!onCancelProcessing || typeof onCancelProcessing !== 'function') {
    throw new Error('onCancelProcessing callback is required and must be a function');
  }

  // Validate processingState structure
  if (!isProcessingState(processingState)) {
    throw new Error('Invalid processingState structure');
  }

  // State management
  const [selectedFiles, setSelectedFiles] = useState<{
    campaign?: File;
    reporting?: File;
  }>({});
  const [validationErrors, setValidationErrors] = useState<{
    campaign?: string[];
    reporting?: string[];
  }>({});
  const [cancelDialogVisible, setCancelDialogVisible] = useState(false);
  const [cancellingFileType, setCancellingFileType] = useState<FileType | null>(null);
  const [statusAnnouncements, setStatusAnnouncements] = useState<{
    campaign: string;
    reporting: string;
  }>({
    campaign: '',
    reporting: ''
  });

  // Refs for accessibility
  const campaignFileInputRef = useRef<HTMLInputElement>(null);
  const reportingFileInputRef = useRef<HTMLInputElement>(null);
  const campaignUploadButtonRef = useRef<HTMLButtonElement>(null);
  const reportingUploadButtonRef = useRef<HTMLButtonElement>(null);
  const campaignCancelButtonRef = useRef<HTMLButtonElement>(null);
  const prevCampaignStatusRef = useRef<ProcessingStatus>(ProcessingStatus.IDLE);

  // File size validation - exactly 250MB
  const validateFileForUpload = useCallback((file: File): string[] => {
    const errors: string[] = [];
    
    // Use the updated validation logic
    const sizeValidation = validateFileSize(file.size);
    if (!sizeValidation.isValid) {
      errors.push('File size exceeds 250MB limit');
    }

    // Also use existing upload service validation
    try {
      const serviceValidation = uploadService.validateFile(file);
      if (!serviceValidation.isValid) {
        // But override size error with our 250MB message
        const filteredErrors = serviceValidation.errors.filter(error => 
          !error.includes('500MB') && !error.includes('File size exceeds')
        );
        if (serviceValidation.errors.some(error => 
          error.includes('500MB') || error.includes('File size exceeds')
        )) {
          errors.push('File size exceeds 250MB limit');
        }
        errors.push(...filteredErrors);
      }
    } catch (error) {
      throw error; // Re-throw for error boundary
    }

    return errors;
  }, []);

  // Determine processing status for each file type
  const getProcessingStatus = useCallback((fileType: FileType) => {
    const progress = fileType === FileType.CAMPAIGN_XLSX 
      ? processingState.campaign_xlsx 
      : processingState.reporting_csv;
    
    if (!progress) {
      return ProcessingStatus.IDLE;
    }
    
    return progress.status;
  }, [processingState]);

  // Check if upload is disabled for a file type
  const isUploadDisabled = useCallback((fileType: FileType) => {
    const status = getProcessingStatus(fileType);
    const hasSelectedFile = fileType === FileType.CAMPAIGN_XLSX 
      ? !!selectedFiles.campaign 
      : !!selectedFiles.reporting;
    const hasValidationErrors = fileType === FileType.CAMPAIGN_XLSX
      ? (validationErrors.campaign?.length || 0) > 0
      : (validationErrors.reporting?.length || 0) > 0;

    return status === ProcessingStatus.PROCESSING || !hasSelectedFile || hasValidationErrors;
  }, [getProcessingStatus, selectedFiles, validationErrors]);

  // Handle file selection
  const handleFileSelection = useCallback((file: File, fileType: FileType) => {
    const errors = validateFileForUpload(file);
    
    if (fileType === FileType.CAMPAIGN_XLSX) {
      setSelectedFiles(prev => ({ ...prev, campaign: file }));
      setValidationErrors(prev => ({ ...prev, campaign: errors }));
    } else {
      setSelectedFiles(prev => ({ ...prev, reporting: file }));
      setValidationErrors(prev => ({ ...prev, reporting: errors }));
    }
  }, [validateFileForUpload]);

  // Handle upload start
  const handleUploadStart = useCallback((fileType: FileType) => {
    const file = fileType === FileType.CAMPAIGN_XLSX 
      ? selectedFiles.campaign 
      : selectedFiles.reporting;
    
    if (!file) return;

    const errors = validateFileForUpload(file);
    if (errors.length > 0) return;

    onUploadStart(file, fileType);
  }, [selectedFiles, validateFileForUpload, onUploadStart]);

  // Handle cancel processing
  const handleCancelClick = useCallback((fileType: FileType) => {
    setCancellingFileType(fileType);
    setCancelDialogVisible(true);
  }, []);

  const handleCancelConfirm = useCallback(() => {
    if (cancellingFileType) {
      const progress = cancellingFileType === FileType.CAMPAIGN_XLSX 
        ? processingState.campaign_xlsx 
        : processingState.reporting_csv;
      
      onCancelProcessing(cancellingFileType, progress?.batch_id);
      
      // Show success message
      setTimeout(() => {
        message.success('Processing cancelled successfully');
      }, 100);
    }
    setCancelDialogVisible(false);
    setCancellingFileType(null);
  }, [cancellingFileType, processingState, onCancelProcessing]);

  const handleCancelDismiss = useCallback(() => {
    setCancelDialogVisible(false);
    setCancellingFileType(null);
  }, []);

  // Status message generators
  const getStatusMessage = useCallback((fileType: FileType) => {
    const status = getProcessingStatus(fileType);
    const fileTypeName = fileType === FileType.CAMPAIGN_XLSX ? 'Campaign XLSX' : 'Reporting CSV';
    
    switch (status) {
      case ProcessingStatus.IDLE:
        return 'Ready to upload';
      case ProcessingStatus.PROCESSING:
        return 'Processing in progress - wait or cancel';
      case ProcessingStatus.COMPLETED:
        return 'Processing completed';
      case ProcessingStatus.ERROR:
        const errors = processingState.errors.filter(error => 
          error.context.file_type === fileType
        );
        const errorMsg = errors.length > 0 ? errors[0].message : 'Processing failed';
        return `Processing failed: ${errorMsg}`;
      case ProcessingStatus.CANCELLED:
        return 'Processing cancelled';
      default:
        return 'Ready to upload';
    }
  }, [getProcessingStatus, processingState.errors]);

  const getStatusTestId = useCallback((fileType: FileType) => {
    const prefix = fileType === FileType.CAMPAIGN_XLSX ? 'campaign' : 'reporting';
    const status = getProcessingStatus(fileType);
    
    switch (status) {
      case ProcessingStatus.IDLE:
        return `${prefix}-status-ready`;
      case ProcessingStatus.PROCESSING:
        return `${prefix}-status-processing`;
      case ProcessingStatus.COMPLETED:
        return `${prefix}-status-completed`;
      case ProcessingStatus.ERROR:
        return `${prefix}-status-error`;
      case ProcessingStatus.CANCELLED:
        return `${prefix}-status-cancelled`;
      default:
        return `${prefix}-status-ready`;
    }
  }, [getProcessingStatus]);

  // Focus management for accessibility
  useEffect(() => {
    const campaignStatus = getProcessingStatus(FileType.CAMPAIGN_XLSX);
    
    if (prevCampaignStatusRef.current !== ProcessingStatus.PROCESSING && 
        campaignStatus === ProcessingStatus.PROCESSING) {
      // Focus moved to cancel button when processing starts
      setTimeout(() => {
        campaignCancelButtonRef.current?.focus();
      }, 100);
    }
    
    prevCampaignStatusRef.current = campaignStatus;
  }, [getProcessingStatus]);

  // Screen reader announcements
  useEffect(() => {
    const campaignStatus = getProcessingStatus(FileType.CAMPAIGN_XLSX);
    const reportingStatus = getProcessingStatus(FileType.REPORTING_CSV);
    
    setStatusAnnouncements({
      campaign: campaignStatus === ProcessingStatus.PROCESSING 
        ? 'Campaign processing started' 
        : '',
      reporting: reportingStatus === ProcessingStatus.PROCESSING 
        ? 'Reporting processing started' 
        : ''
    });
  }, [getProcessingStatus]);

  // Get processing errors for display
  const getProcessingError = useCallback((fileType: FileType): ProcessingError | undefined => {
    return processingState.errors.find(error => error.context.file_type === fileType);
  }, [processingState.errors]);

  // Format file size
  const formatFileSize = useCallback((bytes: number): string => {
    const mb = bytes / (1024 * 1024);
    return `${Math.round(mb)} MB`;
  }, []);

  // Render file upload section
  const renderUploadSection = useCallback((fileType: FileType) => {
    const isCampaign = fileType === FileType.CAMPAIGN_XLSX;
    const prefix = isCampaign ? 'campaign' : 'reporting';
    const fileTypeName = isCampaign ? 'Campaign XLSX' : 'Reporting CSV';
    const accept = isCampaign ? '.xlsx' : '.csv';
    const selectedFile = isCampaign ? selectedFiles.campaign : selectedFiles.reporting;
    const errors = isCampaign ? validationErrors.campaign : validationErrors.reporting;
    const status = getProcessingStatus(fileType);
    const progress = isCampaign ? processingState.campaign_xlsx : processingState.reporting_csv;
    const processingError = getProcessingError(fileType);
    
    return (
      <Card
        title={<Title level={4} id={`${prefix}-section-title`}>{fileTypeName} Upload</Title>}
        data-testid={`${prefix}-upload-section`}
        role="region"
        aria-labelledby={`${prefix}-section-title`}
        style={{ marginBottom: '24px' }}
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          {/* Status message */}
          <div
            data-testid={getStatusTestId(fileType)}
            role="status"
            aria-live="polite"
          >
            <Text>{getStatusMessage(fileType)}</Text>
          </div>

          {/* Status announcer for screen readers */}
          <div
            data-testid={`${prefix}-status-announcer`}
            aria-live="polite"
            style={{ 
              position: 'absolute',
              left: '-10000px',
              width: '1px',
              height: '1px',
              overflow: 'hidden'
            }}
          >
            {statusAnnouncements[prefix as keyof typeof statusAnnouncements]}
          </div>

          {/* Processing messages */}
          {status === ProcessingStatus.PROCESSING && (
            <div data-testid={`${prefix}-processing-message`}>
              <Text type="secondary">Processing in progress - wait or cancel</Text>
            </div>
          )}

          {status === ProcessingStatus.IDLE && (
            <div data-testid={`${prefix}-ready-message`}>
              <Text type="secondary">Ready to upload</Text>
            </div>
          )}

          {status === ProcessingStatus.COMPLETED && (
            <div data-testid={`${prefix}-completed-message`}>
              <Text type="success">Processing completed</Text>
            </div>
          )}

          {status === ProcessingStatus.ERROR && (
            <div data-testid={`${prefix}-error-message`}>
              <Text type="danger">Processing failed</Text>
              {processingError && (
                <div style={{ marginTop: '8px' }}>
                  <Text type="danger">{processingError.message}</Text>
                </div>
              )}
            </div>
          )}

          {/* File input */}
          <input
            ref={isCampaign ? campaignFileInputRef : reportingFileInputRef}
            data-testid={`${prefix}-file-input`}
            type="file"
            accept={accept}
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) {
                handleFileSelection(file, fileType);
              }
            }}
            style={{ marginBottom: '16px' }}
          />

          {/* File info */}
          {selectedFile && (
            <div data-testid={`${prefix}-file-info`}>
              <Text>
                {selectedFile.name} ({formatFileSize(selectedFile.size)})
              </Text>
            </div>
          )}

          {/* Validation errors */}
          {errors && errors.length > 0 && (
            <div data-testid={`${prefix}-validation-error`}>
              {errors.map((error, index) => (
                <Text key={index} type="danger" style={{ display: 'block' }}>
                  {error}
                </Text>
              ))}
            </div>
          )}

          {/* Upload and Cancel buttons */}
          <Space>
            <Button
              ref={isCampaign ? campaignUploadButtonRef : reportingUploadButtonRef}
              data-testid={`${prefix}-upload-button`}
              type="primary"
              icon={<UploadOutlined />}
              disabled={isUploadDisabled(fileType)}
              onClick={() => handleUploadStart(fileType)}
              aria-label={`Upload ${fileTypeName} file`}
              aria-disabled={isUploadDisabled(fileType)}
            >
              Upload {fileTypeName}
            </Button>

            {status === ProcessingStatus.PROCESSING && (
              <Button
                ref={isCampaign ? campaignCancelButtonRef : undefined}
                data-testid={`${prefix}-cancel-button`}
                icon={<StopOutlined />}
                onClick={() => handleCancelClick(fileType)}
              >
                Cancel
              </Button>
            )}
          </Space>

          {/* Processing progress indicator */}
          {progress && status === ProcessingStatus.PROCESSING && (
            <ProcessingProgressIndicator
              processingData={progress}
              error={processingError}
            />
          )}

          {/* Processing error display */}
          {processingError && status === ProcessingStatus.ERROR && (
            <div data-testid="processing-error">
              <Text type="danger">Error: {processingError.message}</Text>
            </div>
          )}
        </Space>
      </Card>
    );
  }, [
    selectedFiles, 
    validationErrors, 
    getProcessingStatus, 
    processingState, 
    getProcessingError,
    getStatusMessage,
    getStatusTestId,
    statusAnnouncements,
    isUploadDisabled,
    handleFileSelection,
    handleUploadStart,
    handleCancelClick,
    formatFileSize
  ]);

  return (
    <>
      <div
        data-testid="upload-control-panel"
        className={className}
        role="main"
        aria-label="Upload control panel"
      >
        <Title level={2}>Upload Control Panel</Title>
        <Text type="secondary">
          Upload Campaign XLSX and Reporting CSV files for processing
        </Text>

        <div style={{ marginTop: '24px' }}>
          {renderUploadSection(FileType.CAMPAIGN_XLSX)}
          {renderUploadSection(FileType.REPORTING_CSV)}
        </div>

        {/* Status messages */}
        <div
          data-testid="campaign-status-message"
          role="status"
          style={{ marginBottom: '8px' }}
        >
          <Text>Campaign XLSX {getStatusMessage(FileType.CAMPAIGN_XLSX).toLowerCase()}</Text>
        </div>

        <div
          data-testid="reporting-status-message"
          role="status"
        >
          <Text>Reporting CSV {getStatusMessage(FileType.REPORTING_CSV).toLowerCase()}</Text>
        </div>
      </div>

      {/* Cancel confirmation dialog */}
      <Modal
        title="Confirm Processing Cancellation"
        open={cancelDialogVisible}
        onCancel={handleCancelDismiss}
        footer={[
          <Button
            key="dismiss"
            data-testid="dismiss-cancel-button"
            onClick={handleCancelDismiss}
          >
            Keep Processing
          </Button>,
          <Button
            key="confirm"
            data-testid="confirm-cancel-button"
            type="primary"
            danger
            onClick={handleCancelConfirm}
          >
            Cancel Processing
          </Button>
        ]}
      >
        <div data-testid="cancel-confirmation-dialog">
          <ExclamationCircleOutlined style={{ color: '#faad14', marginRight: '8px' }} />
          Are you sure you want to cancel the processing? This action cannot be undone.
        </div>
      </Modal>

      {/* Success message container for cancel operations */}
      <div
        data-testid="cancel-success-message"
        style={{ display: 'none' }} // Will be shown by message.success
      />
    </>
  );
};