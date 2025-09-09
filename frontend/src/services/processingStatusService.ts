/**
 * Processing Status Service
 * HTTP polling service for Upload Processing Pipeline UI
 * Implements 2-second polling with connection resilience and performance optimization
 */

import axios, { AxiosError } from 'axios';
import {
  ProcessingStatusResponse,
  ProcessingProgress,
  ProcessingError,
  ProcessingState,
  ProcessingStatus,
  ProcessingStage,
  FileType,
  ErrorCategory,
  ErrorSeverity,
  isProcessingStatusResponse,
  isProcessingProgress,
  isProcessingState
} from '../types/processing';

// Service interfaces
export interface StatusCallbacks {
  onProgressUpdate: (progress: ProcessingProgress) => void;
  onErrorUpdate: (errors: ProcessingError[]) => void;
  onCompletion: (result: ProcessingStatusResponse) => void;
  onFailure: (error: Error) => void;
}

export interface PollingConfiguration {
  pollingInterval: number;
  maxRetries: number;
  timeoutMs: number;
}

// Default configuration
const DEFAULT_CONFIG: PollingConfiguration = {
  pollingInterval: 2000, // 2 seconds
  maxRetries: 10,
  timeoutMs: 30000 // 30 seconds
};

// Polling session interface
interface PollingSession {
  batchId: string;
  callbacks: StatusCallbacks;
  timer: NodeJS.Timeout | null;
  retryCount: number;
  backoffInterval: number;
  isPending: boolean;
  lastProgressData: ProcessingProgress | null;
  lastErrorData: ProcessingError[];
}

/**
 * ProcessingStatusService class
 * Handles HTTP polling for processing status updates with resilience and optimization
 */
export class ProcessingStatusService {
  private config: PollingConfiguration;
  private sessions: Map<string, PollingSession> = new Map();
  private isWindowActive: boolean = true;
  private isGloballyPaused: boolean = false;

  // Event handlers (bound to maintain context)
  private handleVisibilityChange = () => {
    const wasActive = this.isWindowActive;
    this.isWindowActive = !document.hidden && document.visibilityState === 'visible';
    
    if (this.isWindowActive && !wasActive) {
      // Window became visible - resume with immediate polls
      this.resumeAllSessions();
    } else if (!this.isWindowActive && wasActive) {
      // Window became hidden - pause all sessions
      this.pauseAllSessions();
    }
  };

  private handleWindowFocus = () => {
    const wasActive = this.isWindowActive;
    this.isWindowActive = true;
    
    if (!wasActive) {
      // Window gained focus - resume with immediate polls
      this.resumeAllSessions();
    }
  };

  private handleWindowBlur = () => {
    this.isWindowActive = false;
    this.pauseAllSessions();
  };

  constructor(config?: Partial<PollingConfiguration>) {
    this.config = { ...DEFAULT_CONFIG, ...config };
    
    // Set up event listeners for window focus/blur and visibility changes
    document.addEventListener('visibilitychange', this.handleVisibilityChange);
    window.addEventListener('focus', this.handleWindowFocus);
    window.addEventListener('blur', this.handleWindowBlur);
  }

  /**
   * Start polling for a specific batch ID
   */
  startPolling(batchId: string, callbacks: StatusCallbacks): void {
    // Validate inputs
    if (!batchId || typeof batchId !== 'string' || batchId.trim() === '') {
      throw new Error('Invalid batch_id');
    }
    
    if (!callbacks) {
      throw new Error('Callbacks are required');
    }

    // Stop existing session if it exists
    if (this.sessions.has(batchId)) {
      this.stopPolling(batchId);
    }

    // Create new session
    const session: PollingSession = {
      batchId,
      callbacks,
      timer: null,
      retryCount: 0,
      backoffInterval: this.config.pollingInterval,
      isPending: false,
      lastProgressData: null,
      lastErrorData: []
    };

    this.sessions.set(batchId, session);

    // Start polling with initial poll and schedule next
    if (this.isWindowActive && !this.isGloballyPaused) {
      // Perform initial poll and schedule next
      this.performPoll(session);
    } else {
      // Even if paused, schedule a timer for later execution
      this.scheduleNextPoll(session);
    }
  }

  /**
   * Stop polling for a specific batch ID
   */
  stopPolling(batchId: string): void {
    const session = this.sessions.get(batchId);
    if (session) {
      if (session.timer) {
        clearTimeout(session.timer);
        session.timer = null;
      }
      this.sessions.delete(batchId);
    }
  }

  /**
   * Pause all polling sessions
   */
  pausePolling(): void {
    this.isGloballyPaused = true;
    this.pauseAllSessions();
  }

  /**
   * Resume all polling sessions
   */
  resumePolling(): void {
    this.isGloballyPaused = false;
    if (this.isWindowActive) {
      this.resumeAllSessions();
    }
  }

  /**
   * Cancel processing for a specific batch and file type
   */
  async cancelProcessing(batchId: string, fileType: FileType): Promise<void> {
    try {
      await axios.post(`/api/upload/cancel/${batchId}`, {
        file_type: fileType
      });
    } catch (error) {
      if (axios.isAxiosError(error)) {
        throw this.handleApiError(error);
      }
      throw error;
    }
  }

  /**
   * Cleanup all resources
   */
  cleanup(): void {
    // Clear all polling sessions
    for (const [batchId] of this.sessions) {
      this.stopPolling(batchId);
    }

    // Remove event listeners
    document.removeEventListener('visibilitychange', this.handleVisibilityChange);
    window.removeEventListener('focus', this.handleWindowFocus);
    window.removeEventListener('blur', this.handleWindowBlur);
  }

  /**
   * Perform a single poll for a session
   */
  private async performPoll(session: PollingSession): Promise<void> {
    // Prevent overlapping requests
    if (session.isPending) {
      return;
    }

    session.isPending = true;

    try {
      const response = await axios.get(`/api/upload/status/${session.batchId}`);

      // Handle empty response data
      if (response.data === null || response.data === undefined) {
        throw new Error('Empty response');
      }

      // Validate response format
      if (!isProcessingStatusResponse(response.data)) {
        throw new Error('Invalid response format');
      }

      const statusResponse: ProcessingStatusResponse = response.data;

      // Handle successful response
      this.handleSuccessfulResponse(session, statusResponse);
      
      // Reset retry count on success
      session.retryCount = 0;
      session.backoffInterval = this.config.pollingInterval;

    } catch (error) {
      this.handlePollingError(session, error);
    } finally {
      session.isPending = false;
    }
  }

  /**
   * Handle successful API response
   */
  private handleSuccessfulResponse(session: PollingSession, response: ProcessingStatusResponse): void {
    if (!response.success) {
      // Handle API error response
      const errorMessage = response.error ? `${response.error.code}: ${response.error.message}` : 'Unknown API error';
      session.callbacks.onFailure(new Error(errorMessage));
      return;
    }

    if (!response.data || !isProcessingState(response.data)) {
      session.callbacks.onFailure(new Error('Invalid response format'));
      return;
    }

    const state = response.data;

    // Process progress updates
    this.processProgressUpdates(session, state);

    // Process error updates
    this.processErrorUpdates(session, state);

    // Check for completion
    const isCompleted = this.checkCompletionStatus(state);
    if (isCompleted) {
      session.callbacks.onCompletion(response);
      this.stopPolling(session.batchId);
      return;
    }

    // Schedule next poll if not completed
    this.scheduleNextPoll(session);
  }

  /**
   * Process progress updates from state
   */
  private processProgressUpdates(session: PollingSession, state: ProcessingState): void {
    // Handle campaign XLSX progress
    if (state.campaign_xlsx) {
      if (!isProcessingProgress(state.campaign_xlsx)) {
        session.callbacks.onFailure(new Error('Invalid progress format'));
        return;
      }

      // Validate batch_id consistency
      if (state.campaign_xlsx.batch_id !== session.batchId) {
        session.callbacks.onFailure(new Error('Batch ID mismatch'));
        return;
      }

      // Only update if progress has changed
      if (!this.isProgressDataEqual(session.lastProgressData, state.campaign_xlsx)) {
        session.callbacks.onProgressUpdate(state.campaign_xlsx);
        session.lastProgressData = state.campaign_xlsx;
      }
    }

    // Handle reporting CSV progress
    if (state.reporting_csv) {
      if (!isProcessingProgress(state.reporting_csv)) {
        session.callbacks.onFailure(new Error('Invalid progress format'));
        return;
      }

      // Validate batch_id consistency
      if (state.reporting_csv.batch_id !== session.batchId) {
        session.callbacks.onFailure(new Error('Batch ID mismatch'));
        return;
      }

      // Only update if progress has changed
      if (!this.isProgressDataEqual(session.lastProgressData, state.reporting_csv)) {
        session.callbacks.onProgressUpdate(state.reporting_csv);
        session.lastProgressData = state.reporting_csv;
      }
    }
  }

  /**
   * Process error updates from state
   */
  private processErrorUpdates(session: PollingSession, state: ProcessingState): void {
    if (state.errors && state.errors.length > 0) {
      // Only update if errors have changed
      if (!this.areErrorsEqual(session.lastErrorData, state.errors)) {
        session.callbacks.onErrorUpdate(state.errors);
        session.lastErrorData = [...state.errors];
      }
    }
  }

  /**
   * Check if processing is completed
   */
  private checkCompletionStatus(state: ProcessingState): boolean {
    // If both file types are null, processing hasn't started - continue polling
    if (!state.campaign_xlsx && !state.reporting_csv) {
      return false;
    }

    const campaignCompleted = !state.campaign_xlsx || 
      state.campaign_xlsx.status === ProcessingStatus.COMPLETED ||
      state.campaign_xlsx.status === ProcessingStatus.ERROR ||
      state.campaign_xlsx.status === ProcessingStatus.CANCELLED;

    const reportingCompleted = !state.reporting_csv ||
      state.reporting_csv.status === ProcessingStatus.COMPLETED ||
      state.reporting_csv.status === ProcessingStatus.ERROR ||
      state.reporting_csv.status === ProcessingStatus.CANCELLED;

    // Only complete if there's at least one file type processing and all are finished
    return campaignCompleted && reportingCompleted;
  }

  /**
   * Handle polling errors with retry logic
   */
  private handlePollingError(session: PollingSession, error: any): void {
    session.retryCount++;

    // Check for permanent errors (404, validation errors)
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      session.callbacks.onFailure(new Error('Batch not found'));
      this.stopPolling(session.batchId);
      return;
    }

    // Check if we've exceeded max retries
    if (session.retryCount >= this.config.maxRetries) {
      session.callbacks.onFailure(new Error('Maximum retry attempts exceeded'));
      this.stopPolling(session.batchId);
      return;
    }

    // Apply exponential backoff
    session.backoffInterval = Math.min(
      this.config.pollingInterval * Math.pow(2, session.retryCount - 1),
      30000 // Cap at 30 seconds
    );

    // Schedule retry if window is active
    if (this.isWindowActive && !this.isGloballyPaused) {
      this.scheduleNextPoll(session);
    }
  }

  /**
   * Schedule the next poll for a session
   */
  private scheduleNextPoll(session: PollingSession): void {
    const interval = session.retryCount > 0 ? session.backoffInterval : this.config.pollingInterval;
    
    // Clear any existing timer
    if (session.timer) {
      clearTimeout(session.timer);
      session.timer = null;
    }
    
    // Schedule next poll
    session.timer = setTimeout(() => {
      // Check if session still exists and window is active
      if (this.sessions.has(session.batchId) && this.isWindowActive && !this.isGloballyPaused) {
        const currentSession = this.sessions.get(session.batchId);
        if (currentSession) {
          this.performPoll(currentSession);
        }
      }
    }, interval);
  }

  /**
   * Pause all active sessions
   */
  private pauseAllSessions(): void {
    for (const session of this.sessions.values()) {
      if (session.timer) {
        clearTimeout(session.timer);
        session.timer = null;
      }
    }
  }

  /**
   * Resume all sessions
   */
  private resumeAllSessions(): void {
    for (const session of this.sessions.values()) {
      if (!session.timer && !session.isPending) {
        // Immediate poll on resume
        this.performPoll(session);
      }
    }
  }

  /**
   * Check if two progress objects are equal
   */
  private isProgressDataEqual(prev: ProcessingProgress | null, current: ProcessingProgress): boolean {
    if (!prev) return false;
    
    return prev.batch_id === current.batch_id &&
           prev.stage === current.stage &&
           prev.progress === current.progress &&
           prev.status === current.status &&
           prev.file_type === current.file_type &&
           prev.updated_at === current.updated_at;
  }

  /**
   * Check if two error arrays are equal
   */
  private areErrorsEqual(prev: ProcessingError[], current: ProcessingError[]): boolean {
    if (prev.length !== current.length) return false;
    
    return prev.every((prevError, index) => {
      const currentError = current[index];
      return prevError.error_id === currentError.error_id &&
             prevError.timestamp === currentError.timestamp &&
             prevError.message === currentError.message;
    });
  }

  /**
   * Handle API errors and extract meaningful error messages
   */
  private handleApiError(error: AxiosError): Error {
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
        errorMessage = 'Batch not found';
        break;
      case 503:
        errorMessage = 'Service temporarily unavailable';
        break;
      case 500:
        errorMessage = 'Internal server error';
        break;
      default:
        errorMessage = error.message || 'An error occurred';
    }
    
    return new Error(errorMessage);
  }
}

// Export default instance (can be replaced with new instance if needed)
export default new ProcessingStatusService();