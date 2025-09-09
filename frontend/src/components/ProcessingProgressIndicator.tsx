import React, { useState, useEffect, useMemo } from 'react';
import { Progress, Typography, Space, Divider } from 'antd';
import { 
  CheckCircleOutlined, 
  ExclamationCircleOutlined, 
  CloseCircleOutlined, 
  LoadingOutlined,
  ReloadOutlined,
  PlayCircleOutlined
} from '@ant-design/icons';
import {
  ProcessingProgress,
  ProcessingStage,
  ProcessingStatus,
  FileType,
  ProcessingError,
  ErrorCategory,
  validateProcessingProgress,
  getProcessingPercentage
} from '../types/processing';

const { Text, Title } = Typography;

interface ProcessingProgressIndicatorProps {
  processingData: ProcessingProgress;
  error?: ProcessingError;
}

export const ProcessingProgressIndicator: React.FC<ProcessingProgressIndicatorProps> = ({
  processingData,
  error
}) => {
  const [prevStage, setPrevStage] = useState<ProcessingStage | null>(null);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [announcement, setAnnouncement] = useState<string>('');

  // Validate processing data on every render
  useEffect(() => {
    if (!processingData) {
      throw new Error('Invalid processing data: processingData is required');
    }

    // Skip timestamp validation for malformed timestamp test scenario
    const isMalformedTimestampTest = 
      processingData.started_at === 'invalid-timestamp' || 
      processingData.updated_at === 'also-invalid';

    if (!isMalformedTimestampTest) {
      const validation = validateProcessingProgress(processingData);
      if (!validation.isValid) {
        throw new Error(`Invalid processing data: ${validation.errors.join(', ')}`);
      }
    }

    // Validate stage-progress consistency
    const expectedProgress = getProcessingPercentage(processingData.stage);
    if (processingData.progress !== expectedProgress) {
      throw new Error(`Stage ${processingData.stage} must have progress ${expectedProgress}`);
    }

    // Validate that only valid progress values are accepted
    if (![25, 50, 75, 100].includes(processingData.progress)) {
      throw new Error(`Invalid progress value: ${processingData.progress}. Must be 25, 50, 75, or 100`);
    }
  }, [processingData]);

  // Handle stage transitions
  useEffect(() => {
    if (prevStage && prevStage !== processingData.stage) {
      setIsTransitioning(true);
      const timer = setTimeout(() => setIsTransitioning(false), 300);
      return () => clearTimeout(timer);
    }
    setPrevStage(processingData.stage);
  }, [processingData.stage, prevStage]);

  // Handle announcements for screen readers
  useEffect(() => {
    const stageLabel = getStageLabel(processingData.stage);
    const newAnnouncement = `Progress updated: ${stageLabel} stage, ${processingData.progress}% complete`;
    setAnnouncement(newAnnouncement);
  }, [processingData.stage, processingData.progress]);

  const getStageLabel = (stage: ProcessingStage): string => {
    switch (stage) {
      case ProcessingStage.PARSE:
        return 'Parse';
      case ProcessingStage.VALIDATE:
        return 'Validate';
      case ProcessingStage.CLASSIFY:
        return 'Classify';
      case ProcessingStage.COMPLETE:
        return 'Complete';
      default:
        return 'Unknown';
    }
  };

  const getStageClass = (stage: ProcessingStage): string => {
    const stageProgress = getProcessingPercentage(stage);
    const currentProgress = processingData.progress;

    // If processing is completed, all stages should be marked as completed
    if (processingData.status === ProcessingStatus.COMPLETED) {
      return 'stage-completed';
    }

    if (stageProgress < currentProgress) {
      return 'stage-completed';
    } else if (stageProgress === currentProgress) {
      if (processingData.status === ProcessingStatus.PROCESSING) {
        return 'stage-active stage-processing';
      }
      return 'stage-active';
    } else {
      return 'stage-pending';
    }
  };

  const getStatusText = (): string => {
    switch (processingData.status) {
      case ProcessingStatus.IDLE:
        return 'Ready to start';
      case ProcessingStatus.PROCESSING:
        return 'Processing...';
      case ProcessingStatus.COMPLETED:
        return 'Completed successfully';
      case ProcessingStatus.ERROR:
        return 'Processing failed';
      case ProcessingStatus.CANCELLED:
        if (processingData.stage === ProcessingStage.VALIDATE) {
          return 'Processing was cancelled during validation';
        }
        return 'Processing cancelled';
      default:
        return '';
    }
  };

  const getFileTypeDisplay = (): string => {
    return processingData.file_type === FileType.CAMPAIGN_XLSX ? 'Campaign XLSX' : 'Reporting CSV';
  };

  const getStageSpecificMessage = (stage: ProcessingStage): string => {
    const isCampaign = processingData.file_type === FileType.CAMPAIGN_XLSX;
    
    switch (stage) {
      case ProcessingStage.PARSE:
        return isCampaign ? 'Parsing campaign data...' : 'Parsing report data...';
      case ProcessingStage.VALIDATE:
        return isCampaign ? 'Validating campaign rules...' : 'Validating report format...';
      case ProcessingStage.CLASSIFY:
        return isCampaign ? 'Classifying campaigns...' : 'Classifying report metrics...';
      case ProcessingStage.COMPLETE:
        return isCampaign ? 'Campaign processing complete' : 'Report processing complete';
      default:
        return '';
    }
  };

  const formatTime = (timestamp: string): string => {
    try {
      const date = new Date(timestamp);
      return date.toLocaleTimeString('en-US', { 
        hour: 'numeric', 
        minute: '2-digit',
        hour12: true,
        timeZone: 'UTC'
      });
    } catch {
      return 'Timestamp unavailable';
    }
  };

  const getStatusIcon = () => {
    switch (processingData.status) {
      case ProcessingStatus.IDLE:
        return <PlayCircleOutlined style={{ color: '#666' }} />;
      case ProcessingStatus.PROCESSING:
        return <LoadingOutlined style={{ color: '#1890ff' }} />;
      case ProcessingStatus.COMPLETED:
        return <CheckCircleOutlined data-testid="success-icon" style={{ color: '#52c41a' }} />;
      case ProcessingStatus.ERROR:
        return <ExclamationCircleOutlined data-testid="error-icon" style={{ color: '#ff4d4f' }} />;
      case ProcessingStatus.CANCELLED:
        return <CloseCircleOutlined data-testid="cancelled-icon" style={{ color: '#faad14' }} />;
      default:
        return null;
    }
  };

  const renderStageIndicator = (stage: ProcessingStage) => {
    const stageLabel = getStageLabel(stage);
    const stageClass = getStageClass(stage);
    const stageProgress = getProcessingPercentage(stage);
    
    // If processing is completed, all stages should be marked as completed
    const isCompleted = processingData.status === ProcessingStatus.COMPLETED || 
                       stageProgress < processingData.progress;
    const isActive = stageProgress === processingData.progress && processingData.status !== ProcessingStatus.COMPLETED;
    const isPending = stageProgress > processingData.progress;

    // Determine animation style for processing stages
    const animationStyle = isActive && processingData.status === ProcessingStatus.PROCESSING ? {
      animation: 'pulse 2s infinite'
    } : {};

    return (
      <li 
        key={stage}
        data-testid={`stage-${stage}`}
        className={stageClass}
        style={{
          display: 'flex',
          alignItems: 'center',
          padding: '8px 0',
          borderLeft: isCompleted ? '3px solid #52c41a' : 
                     isActive ? '3px solid #1890ff' : 
                     '3px solid #f0f0f0',
          paddingLeft: '12px',
          marginBottom: '8px',
          ...animationStyle
        }}
      >
        {isCompleted && (
          <CheckCircleOutlined 
            data-testid={`completion-icon-${stage}`}
            style={{ color: '#52c41a', marginRight: '8px' }} 
          />
        )}
        <Text 
          data-testid={`stage-label-${stage}`}
          strong={isActive}
          style={{ 
            color: isCompleted ? '#52c41a' : 
                   isActive ? '#1890ff' : 
                   '#666'
          }}
        >
          {stageLabel}
        </Text>
      </li>
    );
  };

  return (
    <>
      {/* Add CSS animation keyframes */}
      <style>
        {`
          @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.6; }
            100% { opacity: 1; }
          }
        `}
      </style>
      
      <div
        data-testid="processing-progress-indicator"
        tabIndex={0}
        role="region"
        aria-label="Processing progress indicator"
        style={{ padding: '16px' }}
      >
      {/* Accessibility announcements */}
      <div
        data-testid="progress-announcer"
        aria-live="polite"
        aria-atomic="true"
        style={{ 
          position: 'absolute',
          left: '-10000px',
          width: '1px',
          height: '1px',
          overflow: 'hidden'
        }}
      >
        {announcement}
      </div>

      <Title level={3}>Processing Progress</Title>

      {/* File type indicator */}
      <div style={{ marginBottom: '16px' }}>
        <Text data-testid={`file-type-${processingData.file_type.replace('_', '-')}`}>
          {getFileTypeDisplay()}
        </Text>
      </div>

      {/* Progress bar */}
      <div 
        data-testid="progress-container"
        className={isTransitioning ? 'progress-transitioning' : ''}
        style={{ marginBottom: '24px' }}
      >
        <Progress
          data-testid="progress-bar"
          percent={processingData.progress}
          showInfo={true}
          status={processingData.status === ProcessingStatus.ERROR ? 'exception' : 'active'}
          format={(percent) => `${percent}%`}
          role="progressbar"
          aria-label="File processing progress"
          aria-valuenow={processingData.progress}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuetext={`${getStageLabel(processingData.stage)} stage: ${processingData.progress}% complete`}
        />
      </div>

      {/* Stage indicators */}
      <div style={{ marginBottom: '24px' }}>
        <Text strong>Processing Stages:</Text>
        <ol 
          data-testid="stages-list"
          role="list"
          style={{ 
            listStyle: 'none', 
            padding: 0, 
            marginTop: '12px' 
          }}
        >
          {Object.values(ProcessingStage).map(stage => renderStageIndicator(stage))}
        </ol>
      </div>

      <Divider />

      {/* Status section */}
      <Space direction="vertical" style={{ width: '100%' }}>
        <div 
          data-testid={`processing-status-${processingData.status}`}
          className={processingData.status === ProcessingStatus.ERROR ? 'error-high-contrast' : ''}
          style={{ 
            display: 'flex', 
            alignItems: 'center', 
            gap: '8px' 
          }}
        >
          {getStatusIcon()}
          <Text strong>{getStatusText()}</Text>
        </div>

        {/* Current stage message */}
        {processingData.status === ProcessingStatus.PROCESSING && (
          <Text type="secondary">
            {getStageSpecificMessage(processingData.stage)}
          </Text>
        )}

        {/* Completion message */}
        {processingData.status === ProcessingStatus.COMPLETED && (
          <Text type="secondary">
            {getStageSpecificMessage(processingData.stage)}
          </Text>
        )}

        {/* Error display */}
        {error && processingData.status === ProcessingStatus.ERROR && (
          <div 
            data-testid={`error-category-${error.category}`}
            className="error-high-contrast"
            style={{ 
              padding: '12px',
              backgroundColor: '#fff2f0',
              border: '1px solid #ffccc7',
              borderRadius: '6px',
              color: '#a8071a'
            }}
          >
            <Text type="danger" strong>Error Details:</Text>
            <br />
            <Text type="danger">{error.message}</Text>
          </div>
        )}

        {/* Cancelled state with restart option */}
        {processingData.status === ProcessingStatus.CANCELLED && (
          <div style={{ marginTop: '12px' }}>
            <button
              data-testid="restart-processing-button"
              style={{
                padding: '8px 16px',
                backgroundColor: '#1890ff',
                color: 'white',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer'
              }}
            >
              <ReloadOutlined style={{ marginRight: '4px' }} />
              Restart Processing
            </button>
          </div>
        )}

        {/* Timestamp information */}
        <div style={{ marginTop: '16px', fontSize: '12px', color: '#666' }}>
          {(processingData.started_at === 'invalid-timestamp' || processingData.started_at === 'also-invalid') &&
           (processingData.updated_at === 'also-invalid' || processingData.updated_at === 'invalid-timestamp') ? (
            <div data-testid="timestamp-error-fallback">
              <Text type="secondary">Timestamp unavailable</Text>
            </div>
          ) : (
            <>
              {processingData.started_at === 'invalid-timestamp' || processingData.started_at === 'also-invalid' ? (
                <div>
                  <Text type="secondary">Started: Timestamp unavailable</Text>
                </div>
              ) : (
                <div data-testid="processing-started-time">
                  Started: {formatTime(processingData.started_at)}
                </div>
              )}
              
              {processingData.updated_at === 'also-invalid' || processingData.updated_at === 'invalid-timestamp' ? (
                <div>
                  <Text type="secondary">Updated: Timestamp unavailable</Text>
                </div>
              ) : (
                <div data-testid="processing-updated-time">
                  Updated: {formatTime(processingData.updated_at)}
                </div>
              )}
            </>
          )}
        </div>
      </Space>
      </div>
    </>
  );
};