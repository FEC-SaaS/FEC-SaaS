/**
 * Notification types
 */
import type { UUID, ISODateString, Priority } from './common';

// Notification channel
export type NotificationChannel = 'EMAIL' | 'SMS' | 'PUSH' | 'IN_APP';

// Notification type
export type NotificationType =
  | 'BOOKING_CONFIRMATION'
  | 'BOOKING_REMINDER'
  | 'BOOKING_CANCELLATION'
  | 'PARTY_REMINDER'
  | 'LOYALTY_POINTS_EARNED'
  | 'LOYALTY_TIER_UPGRADE'
  | 'PROMOTION'
  | 'BIRTHDAY'
  | 'WELCOME'
  | 'PASSWORD_RESET'
  | 'STAFF_SCHEDULE'
  | 'LOW_INVENTORY'
  | 'MAINTENANCE_ALERT'
  | 'GENERAL';

// Notification status
export type NotificationStatus = 'QUEUED' | 'SENDING' | 'SENT' | 'DELIVERED' | 'FAILED' | 'CANCELLED';

// Delivery status
export type DeliveryStatus = 'SENT' | 'DELIVERED' | 'OPENED' | 'CLICKED' | 'BOUNCED' | 'FAILED';

// Recipient type
export type RecipientType = 'CUSTOMER' | 'STAFF' | 'ADMIN';

// Frequency
export type NotificationFrequency = 'IMMEDIATE' | 'DIGEST_DAILY' | 'DIGEST_WEEKLY';

// Notification content
export interface NotificationContent {
  email?: {
    subject: string;
    bodyHtml: string;
    bodyText?: string;
  };
  sms?: {
    message: string;
  };
  push?: {
    title: string;
    body: string;
    imageUrl?: string;
    actionUrl?: string;
  };
  inApp?: {
    title: string;
    message: string;
    actionUrl?: string;
    icon?: string;
  };
}

// Notification template
export interface NotificationTemplate {
  id: UUID;
  venueId?: UUID;
  templateName: string;
  notificationType: NotificationType;
  channels: NotificationChannel[];
  priority: Priority;
  content: NotificationContent;
  variables?: string[];
  isActive: boolean;
  createdAt: ISODateString;
  updatedAt: ISODateString;
}

// Notification queue item
export interface NotificationQueueItem {
  id: UUID;
  venueId?: UUID;
  recipientId: UUID;
  recipientType: RecipientType;
  recipientEmail?: string;
  recipientPhone?: string;
  notificationType: NotificationType;
  channel: NotificationChannel;
  priority: Priority;
  content: NotificationContent;
  templateId?: UUID;
  scheduledSendTime?: ISODateString;
  status: NotificationStatus;
  attempts: number;
  maxAttempts: number;
  sentAt?: ISODateString;
  deliveredAt?: ISODateString;
  readAt?: ISODateString;
  errorMessage?: string;
  providerMessageId?: string;
  createdAt: ISODateString;
}

// User notification preferences
export interface UserNotificationPreferences {
  id: UUID;
  userId: UUID;
  notificationType: NotificationType;
  emailEnabled: boolean;
  smsEnabled: boolean;
  pushEnabled: boolean;
  inAppEnabled: boolean;
  frequency: NotificationFrequency;
  quietHoursStart?: string;
  quietHoursEnd?: string;
}

// Delivery tracking
export interface NotificationDeliveryTracking {
  id: UUID;
  notificationQueueId: UUID;
  channel: NotificationChannel;
  sentAt?: ISODateString;
  deliveredAt?: ISODateString;
  openedAt?: ISODateString;
  clickedAt?: ISODateString;
  bouncedAt?: ISODateString;
  deliveryStatus?: DeliveryStatus;
  providerMessageId?: string;
  providerResponse?: Record<string, unknown>;
}

// Send notification input
export interface SendNotificationInput {
  venueId?: UUID;
  recipientId: UUID;
  recipientType?: RecipientType;
  recipientEmail?: string;
  recipientPhone?: string;
  notificationType: NotificationType;
  channels: NotificationChannel[];
  priority?: Priority;
  content: NotificationContent;
  templateId?: UUID;
  templateVars?: Record<string, string>;
  scheduledSendTime?: ISODateString;
}

// Batch notification
export interface SendBatchNotificationInput {
  venueId?: UUID;
  recipientIds: UUID[];
  recipientType?: RecipientType;
  notificationType: NotificationType;
  channels: NotificationChannel[];
  priority?: Priority;
  content: NotificationContent;
  templateId?: UUID;
  templateVars?: Record<string, string>;
}

// In-app notification for UI
export interface InAppNotification {
  id: UUID;
  title: string;
  message: string;
  type: NotificationType;
  actionUrl?: string;
  icon?: string;
  isRead: boolean;
  createdAt: ISODateString;
}

// Notification analytics
export interface NotificationAnalytics {
  totalSent: number;
  totalDelivered: number;
  totalFailed: number;
  deliveryRate: number;
  openRate: number;
  clickRate: number;
  byChannel: Record<NotificationChannel, {
    sent: number;
    delivered: number;
    failed: number;
    opened: number;
    clicked: number;
  }>;
  byType: Record<NotificationType, {
    sent: number;
    delivered: number;
  }>;
}
