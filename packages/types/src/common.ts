/**
 * Common types used across the FEC SaaS platform
 */

// Pagination
export interface PaginationParams {
  page?: number;
  limit?: number;
  sortBy?: string;
  sortOrder?: 'asc' | 'desc';
}

export interface PaginatedResponse<T> {
  data: T[];
  pagination: {
    page: number;
    limit: number;
    total: number;
    totalPages: number;
    hasNext: boolean;
    hasPrev: boolean;
  };
}

// API Response wrappers
export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
}

export interface ApiError {
  success: false;
  error: {
    code: string;
    message: string;
    details?: Record<string, string[]>;
  };
}

// Date/Time
export type ISODateString = string;
export type TimeString = string; // HH:mm format

// Status types
export type Status = 'ACTIVE' | 'INACTIVE' | 'SUSPENDED' | 'DELETED';

// Priority levels
export type Priority = 'LOW' | 'MEDIUM' | 'HIGH' | 'URGENT';

// Subscription tiers
export type SubscriptionTier = 'STARTER' | 'PRO' | 'ENTERPRISE';

// Currency
export interface Money {
  amount: number;
  currency: string;
}

// Address
export interface Address {
  street: string;
  city: string;
  state: string;
  zipCode: string;
  country: string;
}

// Contact info
export interface ContactInfo {
  email?: string;
  phone?: string;
  website?: string;
}

// Audit fields
export interface AuditFields {
  createdAt: ISODateString;
  updatedAt: ISODateString;
  createdBy?: string;
  updatedBy?: string;
}

// Day of week
export type DayOfWeek = 0 | 1 | 2 | 3 | 4 | 5 | 6;
export const DAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

// UUID type alias
export type UUID = string;
