/**
 * Notification API endpoints
 */
import { api } from '../client';
import type {
  NotificationTemplate,
  NotificationQueueItem,
  UserNotificationPreferences,
  InAppNotification,
  NotificationAnalytics,
  SendNotificationInput,
  SendBatchNotificationInput,
  NotificationType,
  NotificationChannel,
  PaginatedResponse,
  PaginationParams,
} from '@fec-saas/types';

const BASE = '/api/v1/notifications';
const TEMPLATES_BASE = '/api/v1/templates';

export const notificationsApi = {
  // ============================================================================
  // Send Notifications
  // ============================================================================

  /**
   * Send a notification
   */
  send: (data: SendNotificationInput) =>
    api.post<{
      success: boolean;
      notifications: { id: string; channel: string; status: string }[];
      message: string;
    }>(`${BASE}/send`, data),

  /**
   * Send batch notification
   */
  sendBatch: (data: SendBatchNotificationInput) =>
    api.post<{
      batchId: string;
      totalRecipients: number;
      queuedCount: number;
      failedCount: number;
      status: string;
    }>(`${BASE}/send-batch`, data),

  /**
   * Schedule a notification
   */
  schedule: (data: SendNotificationInput & { scheduledSendTime: string }) =>
    api.post<{
      success: boolean;
      notifications: { id: string; scheduledTime: string }[];
      message: string;
    }>(`${BASE}/schedule`, data),

  // ============================================================================
  // Notification Status
  // ============================================================================

  /**
   * Get notification status
   */
  getStatus: (notificationId: string) =>
    api.get<NotificationQueueItem>(`${BASE}/${notificationId}/status`),

  /**
   * Get notification tracking info
   */
  getTracking: (notificationId: string) =>
    api.get<{
      id: string;
      channel: string;
      sentAt?: string;
      deliveredAt?: string;
      openedAt?: string;
      clickedAt?: string;
      deliveryStatus: string;
    }>(`${BASE}/${notificationId}/tracking`),

  // ============================================================================
  // In-App Notifications
  // ============================================================================

  /**
   * Get in-app notifications for current user
   */
  getInAppNotifications: (params?: { limit?: number; unreadOnly?: boolean }) =>
    api.get<{
      notifications: InAppNotification[];
      unreadCount: number;
    }>(`${BASE}/in-app`, { params }),

  /**
   * Mark notification as read
   */
  markAsRead: (notificationId: string) =>
    api.post<void>(`${BASE}/in-app/${notificationId}/read`),

  /**
   * Mark all notifications as read
   */
  markAllAsRead: () =>
    api.post<void>(`${BASE}/in-app/read-all`),

  /**
   * Dismiss notification
   */
  dismiss: (notificationId: string) =>
    api.delete<void>(`${BASE}/in-app/${notificationId}`),

  // ============================================================================
  // User Preferences
  // ============================================================================

  /**
   * Get notification preferences
   */
  getPreferences: (userId?: string, notificationType?: NotificationType) =>
    api.get<UserNotificationPreferences[]>(`${BASE}/preferences`, {
      params: { user_id: userId, notification_type: notificationType },
    }),

  /**
   * Update notification preferences
   */
  updatePreferences: (
    notificationType: NotificationType,
    preferences: Partial<UserNotificationPreferences>
  ) =>
    api.put<UserNotificationPreferences>(`${BASE}/preferences`, {
      notification_type: notificationType,
      ...preferences,
    }),

  // ============================================================================
  // Analytics
  // ============================================================================

  /**
   * Get delivery analytics
   */
  getDeliveryAnalytics: (params?: {
    venueId?: string;
    startDate?: string;
    endDate?: string;
  }) =>
    api.get<NotificationAnalytics>(`${BASE}/analytics/delivery`, { params }),

  /**
   * Get engagement analytics
   */
  getEngagementAnalytics: (params?: {
    venueId?: string;
    startDate?: string;
    endDate?: string;
  }) =>
    api.get<{
      totalOpened: number;
      totalClicked: number;
      openRate: number;
      clickRate: number;
      byNotificationType: Record<string, { opened: number; clicked: number }>;
    }>(`${BASE}/analytics/engagement`, { params }),
};

// ============================================================================
// Templates
// ============================================================================

export const templatesApi = {
  /**
   * List templates
   */
  list: (params?: {
    venueId?: string;
    notificationType?: NotificationType;
    isActive?: boolean;
  }) =>
    api.get<NotificationTemplate[]>(TEMPLATES_BASE, { params }),

  /**
   * Get template by ID
   */
  get: (templateId: string) =>
    api.get<NotificationTemplate>(`${TEMPLATES_BASE}/${templateId}`),

  /**
   * Create template
   */
  create: (data: Omit<NotificationTemplate, 'id' | 'createdAt' | 'updatedAt'>) =>
    api.post<NotificationTemplate>(TEMPLATES_BASE, data),

  /**
   * Update template
   */
  update: (templateId: string, data: Partial<NotificationTemplate>) =>
    api.put<NotificationTemplate>(`${TEMPLATES_BASE}/${templateId}`, data),

  /**
   * Delete template
   */
  delete: (templateId: string) =>
    api.delete<void>(`${TEMPLATES_BASE}/${templateId}`),

  /**
   * Preview template with variables
   */
  preview: (templateId: string, variables: Record<string, string>) =>
    api.post<{
      templateId: string;
      templateName: string;
      variablesUsed: Record<string, string>;
      renderedContent: {
        email?: { subject: string; bodyHtml: string };
        sms?: { message: string };
        push?: { title: string; body: string };
        inApp?: { title: string; message: string };
      };
    }>(`${TEMPLATES_BASE}/${templateId}/preview`, { variables }),
};
