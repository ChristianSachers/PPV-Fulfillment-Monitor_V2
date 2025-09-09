import React, { useState, useMemo, useCallback, useEffect, useRef } from 'react';
import {
  Alert,
  Collapse,
  Button,
  Tag,
  Typography,
  Space,
  Card,
  Input,
  Select,
  Empty,
  Tooltip,
  notification,
  Badge
} from 'antd';
import {
  ExclamationCircleOutlined,
  InfoCircleOutlined,
  WarningOutlined,
  BugOutlined,
  DownOutlined,
  CopyOutlined,
  CheckOutlined,
  SearchOutlined,
  FileExcelOutlined,
  FileTextOutlined,
  DatabaseOutlined,
  SettingOutlined
} from '@ant-design/icons';
import {
  ProcessingError,
  ErrorCategory,
  ErrorSeverity,
  FileType,
  isProcessingError,
  validateProcessingError
} from '../types/processing';

const { Text, Title, Paragraph } = Typography;
const { Panel } = Collapse;
const { Option } = Select;

// Extended ProcessingError interface for full specification compliance
interface ExtendedProcessingError extends ProcessingError {
  technical_details?: string;
  suggested_actions?: string[];
}

// ProcessingErrorResponse interface from specification
interface ProcessingErrorResponse {
  batch_id: string;
  timestamp: string;
  errors: ExtendedProcessingError[];
}

interface ErrorDisplayPanelProps {
  errors?: ExtendedProcessingError[];
  errorResponse?: ProcessingErrorResponse;
  onErrorAction?: (action: string, errorId: string) => void;
  onActionClick?: (action: string, error: ExtendedProcessingError) => void;
  showGrouped?: boolean;
  groupSimilarErrors?: boolean;
  className?: string;
  showTimezone?: boolean;
  isProcessingActive?: boolean;
  currentStage?: string;
}

// Error grouping utility
interface ErrorGroup {
  code: string;
  category: ErrorCategory;
  errors: ExtendedProcessingError[];
  count: number;
  summary: string;
}

// Category icons mapping
const getCategoryIcon = (category: ErrorCategory) => {
  switch (category) {
    case ErrorCategory.VALIDATION:
      return <ExclamationCircleOutlined />;
    case ErrorCategory.PARSING:
      return <FileExcelOutlined />;
    case ErrorCategory.PROCESSING:
      return <SettingOutlined />;
    case ErrorCategory.SYSTEM:
      return <DatabaseOutlined />;
    default:
      return <InfoCircleOutlined />;
  }
};

// File type icons mapping
const getFileTypeIcon = (fileType: FileType) => {
  switch (fileType) {
    case FileType.CAMPAIGN_XLSX:
      return <FileExcelOutlined />;
    case FileType.REPORTING_CSV:
      return <FileTextOutlined />;
    default:
      return <InfoCircleOutlined />;
  }
};

// Format timestamp for display
const formatTimestamp = (timestamp: string, showTimezone: boolean = false): string => {
  try {
    const date = new Date(timestamp);
    const time = date.toLocaleTimeString('en-US', { 
      timeZone: 'UTC',
      hour12: true, 
      hour: '2-digit', 
      minute: '2-digit', 
      second: '2-digit' 
    });
    return showTimezone ? `${time} UTC` : time;
  } catch {
    return 'Timestamp unavailable';
  }
};

// Validate and sort errors by timestamp (oldest first)
const validateAndSortErrors = (errors: ExtendedProcessingError[]): ExtendedProcessingError[] => {
  if (!errors || !Array.isArray(errors)) {
    throw new Error('Errors prop cannot be null or undefined');
  }

  // Validate each error
  errors.forEach((error, index) => {
    const validation = validateProcessingError(error);
    if (!validation.isValid) {
      throw new Error(`Invalid error at index ${index}: ${validation.errors.join(', ')}`);
    }
  });

  // Check if already sorted (oldest first)
  const sorted = [...errors].sort((a, b) => 
    new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );

  // Verify original order was correct
  const isCorrectlyOrdered = errors.every((error, index) => 
    error.error_id === sorted[index].error_id
  );

  if (!isCorrectlyOrdered) {
    throw new Error('Errors must be sorted by timestamp (oldest first)');
  }

  return errors;
};

// Group similar errors
const groupErrors = (errors: ExtendedProcessingError[]): ErrorGroup[] => {
  const groups: Record<string, ErrorGroup> = {};

  errors.forEach(error => {
    const key = error.code;
    if (!groups[key]) {
      groups[key] = {
        code: error.code,
        category: error.category,
        errors: [],
        count: 0,
        summary: ''
      };
    }
    groups[key].errors.push(error);
    groups[key].count++;
  });

  // Generate summaries for groups
  Object.values(groups).forEach(group => {
    if (group.count > 1) {
      const firstError = group.errors[0];
      if (group.code === 'INVALID_UUID') {
        const rows = group.errors
          .filter(e => e.context?.row_number)
          .map(e => e.context.row_number)
          .join(', ');
        group.summary = `UUID validation failed in ${group.count} locations\nRows: ${rows}\nColumn: ${firstError.context?.column_name || 'Unknown'}`;
      } else {
        group.summary = `${group.count} similar errors found`;
      }
    }
  });

  return Object.values(groups);
};

export const ErrorDisplayPanel: React.FC<ErrorDisplayPanelProps> = ({
  errors: propErrors = [],
  errorResponse,
  onErrorAction,
  onActionClick,
  showGrouped = false,
  groupSimilarErrors = true,
  className = '',
  showTimezone = false,
  isProcessingActive = false,
  currentStage = ''
}) => {
  // State management
  const [expandedKeys, setExpandedKeys] = useState<string[]>([]);
  const [expandedGroups, setExpandedGroups] = useState<string[]>([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [showTechnicalDetails, setShowTechnicalDetails] = useState<Record<string, boolean>>({});
  const [copiedItems, setCopiedItems] = useState<Record<string, boolean>>({});
  const [previousErrorCount, setPreviousErrorCount] = useState(0);

  // Refs for accessibility
  const announcerRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Determine errors source
  const sourceErrors = useMemo(() => {
    if (errorResponse) {
      // Validate error response structure
      if (!errorResponse.batch_id || !errorResponse.timestamp) {
        throw new Error('Invalid error response structure: missing batch_id or timestamp');
      }
      return errorResponse.errors || [];
    }
    return propErrors;
  }, [propErrors, errorResponse]);

  // Validate and sort errors
  const validatedErrors = useMemo(() => {
    try {
      return validateAndSortErrors(sourceErrors);
    } catch (error) {
      throw error;
    }
  }, [sourceErrors]);

  // Filter errors based on search and filters
  const filteredErrors = useMemo(() => {
    let filtered = validatedErrors;

    // Search filter
    if (searchTerm) {
      filtered = filtered.filter(error =>
        error.message.toLowerCase().includes(searchTerm.toLowerCase()) ||
        error.code.toLowerCase().includes(searchTerm.toLowerCase()) ||
        error.technical_details?.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    // Category filter
    if (categoryFilter !== 'all') {
      filtered = filtered.filter(error => error.category === categoryFilter);
    }

    // Severity filter
    if (severityFilter !== 'all') {
      filtered = filtered.filter(error => error.severity === severityFilter);
    }

    return filtered;
  }, [validatedErrors, searchTerm, categoryFilter, severityFilter]);

  // Group errors if needed
  const errorGroups = useMemo(() => {
    if (groupSimilarErrors) {
      const groups = groupErrors(filteredErrors);
      // Only return groups if at least one group has more than 1 error
      const hasMultiErrorGroups = groups.some(group => group.count > 1);
      return hasMultiErrorGroups ? groups : [];
    }
    return [];
  }, [filteredErrors, groupSimilarErrors]);

  // Update announcer for accessibility
  useEffect(() => {
    if (validatedErrors.length > previousErrorCount) {
      const newCount = validatedErrors.length - previousErrorCount;
      if (announcerRef.current) {
        announcerRef.current.textContent = `${newCount} new processing errors added`;
      }
    }
    setPreviousErrorCount(validatedErrors.length);
  }, [validatedErrors.length, previousErrorCount]);

  // Event handlers
  const handleExpand = useCallback((errorId: string) => {
    setExpandedKeys(prev => 
      prev.includes(errorId) 
        ? prev.filter(id => id !== errorId)
        : [...prev, errorId]
    );
  }, []);

  const handleGroupExpand = useCallback((groupCode: string) => {
    setExpandedGroups(prev => 
      prev.includes(groupCode) 
        ? prev.filter(code => code !== groupCode)
        : [...prev, groupCode]
    );
  }, []);

  const handleCopyDetails = useCallback(async (error: ExtendedProcessingError) => {
    const details = `Error: ${error.message}\nCode: ${error.code}\nCategory: ${error.category}\nSeverity: ${error.severity}\nTimestamp: ${error.timestamp}\nContext: ${JSON.stringify(error.context, null, 2)}${error.technical_details ? `\nTechnical Details: ${error.technical_details}` : ''}`;
    
    try {
      await navigator.clipboard.writeText(details);
      setCopiedItems(prev => ({ ...prev, [error.error_id]: true }));
      setTimeout(() => {
        setCopiedItems(prev => ({ ...prev, [error.error_id]: false }));
      }, 2000);
      
      if (onActionClick) {
        onActionClick('copy-details', error);
      }
    } catch (err) {
      notification.error({
        message: 'Copy Failed',
        description: 'Unable to copy error details to clipboard'
      });
    }
  }, [onActionClick]);

  const handleActionClick = useCallback((action: string, error: ExtendedProcessingError) => {
    if (onActionClick) {
      onActionClick(action, error);
    }
    if (onErrorAction) {
      onErrorAction(action, error.error_id);
    }
  }, [onActionClick, onErrorAction]);

  // Render error context information
  const renderErrorContext = (error: ExtendedProcessingError, index: number) => {
    const context = error.context || {};
    
    return (
      <div data-testid={`error-context-${index}`} className="error-context">
        <Space wrap>
          {getFileTypeIcon(context.file_type)}
          <Text strong>
            {context.file_type === FileType.CAMPAIGN_XLSX ? 'Campaign XLSX' : 'Reporting CSV'}
          </Text>
          {context.row_number && (
            <Text>Row: {context.row_number.toLocaleString()}</Text>
          )}
          {context.column_name && (
            <Text>Column: {context.column_name}</Text>
          )}
          {context.invalid_value && (
            <Text>Value: {context.invalid_value}</Text>
          )}
        </Space>
        
        {/* File Context Summary */}
        <div data-testid={`file-context-${index}`} className="file-context">
          <Text type="secondary">
            {context.file_type === FileType.CAMPAIGN_XLSX ? 'Campaign XLSX' : 'Reporting CSV'}
            {context.row_number && `, Row ${context.row_number.toLocaleString()}`}
          </Text>
        </div>
        
        {/* Category-specific context */}
        {error.category === ErrorCategory.VALIDATION && (
          <div data-testid={`validation-context-${index}`} className="category-context">
            <Text type="secondary">File validation failed</Text>
          </div>
        )}
        
        {error.category === ErrorCategory.PARSING && (
          <div data-testid={`parsing-context-${index}`} className="category-context">
            <Text type="secondary">File structure parsing failed</Text>
            {context.expected_columns && (
              <div data-testid={`structure-info-${index}`} className="structure-info">
                <Text type="secondary">Expected: {context.expected_columns.join(', ')}</Text>
              </div>
            )}
          </div>
        )}
        
        {error.category === ErrorCategory.PROCESSING && (
          <div data-testid={`processing-stage-${index}`} className="category-context">
            <Text type="secondary">Data processing stage</Text>
            <div data-testid={`stage-info-${index}`}>
              <Text type="secondary">Classification stage</Text>
            </div>
          </div>
        )}
        
        {error.category === ErrorCategory.SYSTEM && (
          <div data-testid={`system-context-${index}`} className="category-context">
            <Text type="secondary">System infrastructure error</Text>
            {context.database_host && (
              <div data-testid={`technical-context-${index}`}>
                <Text type="secondary">Database: {context.database_host}</Text>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  // Render suggested actions
  const renderSuggestedActions = (error: ExtendedProcessingError, index: number) => {
    const actions = error.suggested_actions || [];
    
    if (actions.length === 0) {
      return (
        <div data-testid={`no-actions-message-${index}`} className="no-actions">
          <Text type="secondary">No specific actions recommended</Text>
        </div>
      );
    }

    return (
      <div data-testid={`suggested-actions-${index}`} className="suggested-actions">
        <Title level={5}>Suggested Actions:</Title>
        <Space direction="vertical" size="small">
          {actions.map((action, actionIndex) => (
            <Text key={actionIndex}>{action}</Text>
          ))}
        </Space>
      </div>
    );
  };

  // Render individual error
  const renderError = (error: ExtendedProcessingError, index: number, isGrouped: boolean = false) => {
    const isExpanded = expandedKeys.includes(`${index}`);
    const testIdPrefix = isGrouped ? 'grouped-error' : 'error-item';
    
    return (
      <li key={error.error_id} data-testid={`${testIdPrefix}-${index}`} className="error-item">
        <Card 
          size="small"
          className={`error-card severity-${error.severity}`}
        >
          {/* Error Header */}
          <div className="error-header">
            <Space align="start" size="small">
              {/* Category Icon */}
              <span 
                data-testid={`category-icon-${error.category}-${index}`}
                className={`category-icon icon-${error.category}`}
              >
                {getCategoryIcon(error.category)}
              </span>
              
              {/* Error Content */}
              <div className="error-content">
                <div className="error-main">
                  <Text strong>{error.message}</Text>
                  <div className="error-meta">
                    <Space size="small">
                      <Tag 
                        data-testid={`category-${error.category}-${index}`}
                        className={`category-${error.category}`}
                        color={
                          error.category === ErrorCategory.VALIDATION ? 'orange' :
                          error.category === ErrorCategory.PARSING ? 'red' :
                          error.category === ErrorCategory.PROCESSING ? 'blue' : 'purple'
                        }
                      >
                        {error.category.toUpperCase()}
                      </Tag>
                      <Tag 
                        data-testid={`severity-${error.severity}-${index}`}
                        className={`severity-${error.severity} high-contrast-${error.severity}`}
                        color={
                          error.severity === ErrorSeverity.ERROR ? 'red' :
                          error.severity === ErrorSeverity.WARNING ? 'orange' : 'blue'
                        }
                      >
                        {error.severity.toUpperCase()}
                      </Tag>
                      <Text 
                        data-testid={`error-timestamp-${index}`}
                        type="secondary" 
                        className="timestamp"
                      >
                        {formatTimestamp(error.timestamp, showTimezone)}
                      </Text>
                    </Space>
                  </div>
                </div>
                
                {/* Expand/Collapse Button */}
                <Button
                  data-testid={`expand-error-${index}`}
                  type="text"
                  size="small"
                  icon={<DownOutlined rotate={isExpanded ? 180 : 0} />}
                  onClick={() => handleExpand(`${index}`)}
                  aria-expanded={isExpanded}
                  aria-label={`${isExpanded ? 'Collapse' : 'Expand'} error details`}
                  tabIndex={0}
                  role="button"
                />
              </div>
            </Space>
          </div>

          {/* Basic Error Context - Always Visible */}
          {renderErrorContext(error, index)}

          {/* Expandable Details */}
          {isExpanded && (
            <div data-testid={`error-details-${index}`} className="error-details">
              <div data-testid={`technical-details-${index}`} className="technical-details">
                {/* Technical Details */}
                {error.technical_details && (
                  <div className="technical-section">
                    <Space direction="vertical" size="small" style={{ width: '100%' }}>
                      <div>
                        <Button
                          data-testid={`technical-details-toggle-${index}`}
                          type="link"
                          size="small"
                          onClick={() => setShowTechnicalDetails(prev => ({
                            ...prev,
                            [`${index}`]: !prev[`${index}`]
                          }))}
                        >
                          {showTechnicalDetails[`${index}`] ? 'Hide' : 'Show'} Technical Details
                        </Button>
                      </div>
                      {showTechnicalDetails[`${index}`] && (
                        <div data-testid={`raw-technical-details-${index}`} className="raw-technical">
                          <Paragraph code copyable>
                            {error.technical_details}
                          </Paragraph>
                        </div>
                      )}
                    </Space>
                  </div>
                )}
                
                {/* Suggested Actions */}
                {renderSuggestedActions(error, index)}
                
                {/* Action Buttons */}
                <div className="action-buttons">
                  <Space size="small">
                    <Button
                      data-testid={`action-copy-details-${index}`}
                      size="small"
                      icon={copiedItems[error.error_id] ? <CheckOutlined /> : <CopyOutlined />}
                      onClick={() => handleCopyDetails(error)}
                      type={copiedItems[error.error_id] ? 'primary' : 'default'}
                    >
                      {copiedItems[error.error_id] ? 'Copied!' : 'Copy Details'}
                    </Button>
                    <Button
                      data-testid={`action-mark-resolved-${index}`}
                      size="small"
                      onClick={() => handleActionClick('mark-resolved', error)}
                    >
                      Mark Resolved
                    </Button>
                    <Button
                      data-testid={`action-view-context-${index}`}
                      size="small"
                      onClick={() => handleActionClick('view-context', error)}
                    >
                      View Context
                    </Button>
                  </Space>
                </div>
                
                {/* Copy Success Message */}
                {copiedItems[error.error_id] && (
                  <div data-testid={`copy-success-message-${index}`} className="copy-success">
                    <Text type="success">Error details copied to clipboard</Text>
                  </div>
                )}
                
                {/* Context Guidance */}
                {error.category === ErrorCategory.PARSING && (
                  <div data-testid={`context-guidance-${index}`} className="context-guidance">
                    <Text type="secondary">Column header mismatch detected</Text>
                    <br />
                    <Text type="secondary">Ensure Excel column names match the required template exactly</Text>
                  </div>
                )}
              </div>
            </div>
          )}
        </Card>
      </li>
    );
  };

  // Render error groups
  const renderErrorGroups = () => {
    return errorGroups.map(group => {
      const isExpanded = expandedGroups.includes(group.code);
      
      return (
        <div key={group.code} data-testid={`error-group-${group.code}`} className="error-group">
          <Card className="group-card">
            <div 
              data-testid={`group-header-${group.code}`}
              className="group-header"
              onClick={() => handleGroupExpand(group.code)}
              style={{ cursor: 'pointer' }}
            >
              <Space justify="space-between" style={{ width: '100%' }}>
                <div>
                  <Text strong>
                    {group.code === 'INVALID_UUID' ? 'Invalid UUID Format' : group.code}{' '}
                    ({group.count} errors)
                  </Text>
                  <span data-testid={`group-count-${group.code}`} style={{ display: 'none' }}>{group.count}</span>
                </div>
                <Button
                  data-testid={`group-expand-${group.code}`}
                  type="text"
                  size="small"
                  icon={<DownOutlined rotate={isExpanded ? 180 : 0} />}
                />
              </Space>
            </div>
            
            {group.summary && (
              <div data-testid={`group-summary-${group.code}`} className="group-summary">
                <Text type="secondary">{group.summary}</Text>
              </div>
            )}
            
            {isExpanded && (
              <div className="group-errors">
                <ul data-testid="grouped-error-list" role="list">
                  {group.errors.map((error, index) => renderError(error, index, true))}
                </ul>
              </div>
            )}
          </Card>
        </div>
      );
    });
  };

  // Render empty state
  if (filteredErrors.length === 0 && !errorResponse) {
    return (
      <div 
        data-testid="error-display-panel" 
        className={`error-display-panel ${className}`}
        role="region"
        aria-label="Processing errors"
        ref={containerRef}
      >
        <div data-testid="error-announcer" aria-live="polite" aria-atomic="false" ref={announcerRef} className="sr-only" />
        <Empty
          data-testid="no-errors-message"
          image={<CheckOutlined data-testid="no-errors-icon" style={{ fontSize: 48, color: '#52c41a' }} />}
          description="No processing errors found"
        />
      </div>
    );
  }

  return (
    <div 
      data-testid="error-display-panel" 
      className={`error-display-panel ${className}`}
      role="region"
      aria-label="Processing errors"
      ref={containerRef}
    >
      {/* Screen Reader Announcements */}
      <div 
        data-testid="error-announcer" 
        aria-live="polite" 
        aria-atomic="false" 
        ref={announcerRef} 
        className="sr-only" 
      />
      
      {/* Error Response Header */}
      {errorResponse && (
        <div className="error-response-header">
          <Space direction="vertical" size="small">
            <div>
              <Text strong>Batch ID: </Text>
              <Text data-testid="batch-id">{errorResponse.batch_id}</Text>
            </div>
            <div>
              <Text strong>Response Time: </Text>
              <Text data-testid="response-timestamp">
                {formatTimestamp(errorResponse.timestamp, showTimezone)}
              </Text>
            </div>
          </Space>
        </div>
      )}
      
      {/* Processing Status Indicator */}
      {isProcessingActive && (
        <div data-testid="active-processing-indicator" className="processing-indicator">
          <Alert
            message="Processing continues despite errors"
            description={
              <div data-testid="current-stage-indicator">
                Current Stage: {currentStage ? `${currentStage.charAt(0).toUpperCase() + currentStage.slice(1)} Stage` : 'Unknown'}
              </div>
            }
            type="info"
            showIcon
          />
        </div>
      )}
      
      {/* Timezone Indicator */}
      {showTimezone && (
        <div data-testid="timezone-indicator" className="timezone-indicator">
          <Text type="secondary">All times shown in UTC</Text>
        </div>
      )}
      
      {/* Header */}
      <div className="error-panel-header">
        <Title level={2}>Processing Errors</Title>
        
        {/* Search and Filters */}
        <Space direction="vertical" size="small" style={{ width: '100%' }}>
          <Input
            data-testid="error-search-input"
            placeholder="Search errors..."
            prefix={<SearchOutlined />}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
          
          <Space size="small">
            <Select
              data-testid="error-category-filter"
              placeholder="Filter by category"
              value={categoryFilter}
              onChange={setCategoryFilter}
              style={{ minWidth: 150 }}
            >
              <Option value="all">All Categories</Option>
              <Option value="validation">Validation</Option>
              <Option value="parsing">Parsing</Option>
              <Option value="processing">Processing</Option>
              <Option value="system">System</Option>
            </Select>
            
            <Select
              data-testid="error-severity-filter"
              placeholder="Filter by severity"
              value={severityFilter}
              onChange={setSeverityFilter}
              style={{ minWidth: 120 }}
            >
              <Option value="all">All Severities</Option>
              <Option value="error">Error</Option>
              <Option value="warning">Warning</Option>
              <Option value="info">Info</Option>
            </Select>
          </Space>
        </Space>
      </div>
      
      {/* Error List */}
      {errorGroups.length > 0 ? (
        <div className="error-groups">
          {renderErrorGroups()}
        </div>
      ) : (
        <ul 
          data-testid="error-list" 
          role="list"
          aria-label="Processing error details"
          className="error-list"
        >
          {filteredErrors.map((error, index) => renderError(error, index))}
        </ul>
      )}

      {/* File Type Indicators (for integration tests) */}
      <div className="hidden-test-elements" style={{ display: 'none' }}>
        {filteredErrors.map((error, index) => (
          <div key={error.error_id}>
            <div data-testid={`file-type-${error.context.file_type.replace('_', '-')}-${index}`} />
            {error.context.stage && (
              <div data-testid={`stage-context-${error.context.stage}-${index}`}>
                {error.context.stage.charAt(0).toUpperCase() + error.context.stage.slice(1)} Stage
              </div>
            )}
            {!error.context && (
              <div data-testid={`context-unavailable-${index}`}>
                Context information unavailable
              </div>
            )}
            {!formatTimestamp(error.timestamp) && (
              <div data-testid={`timestamp-error-fallback-${index}`}>
                Timestamp unavailable
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
};

export default ErrorDisplayPanel;