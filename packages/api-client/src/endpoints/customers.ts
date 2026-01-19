/**
 * Customer API endpoints (GuestIQ)
 */
import { api } from '../client';
import type {
  Customer,
  CustomerVisit,
  CustomerFeedback,
  CustomerFilter,
  CustomerAnalytics,
  CreateCustomerInput,
  UpdateCustomerInput,
  PaginatedResponse,
  PaginationParams,
} from '@fec-saas/types';

const BASE = '/api/v1/customers';

export const customersApi = {
  // ============================================================================
  // Customer CRUD
  // ============================================================================

  /**
   * List customers with filters
   */
  list: (params?: PaginationParams & CustomerFilter & { venueId?: string }) =>
    api.get<PaginatedResponse<Customer>>(BASE, { params }),

  /**
   * Get customer by ID
   */
  get: (customerId: string) =>
    api.get<Customer>(`${BASE}/${customerId}`),

  /**
   * Create customer
   */
  create: (venueId: string, data: CreateCustomerInput) =>
    api.post<Customer>(BASE, { venue_id: venueId, ...data }),

  /**
   * Update customer
   */
  update: (customerId: string, data: UpdateCustomerInput) =>
    api.put<Customer>(`${BASE}/${customerId}`, data),

  /**
   * Delete customer
   */
  delete: (customerId: string) =>
    api.delete<void>(`${BASE}/${customerId}`),

  /**
   * Search customers
   */
  search: (venueId: string, query: string, limit?: number) =>
    api.get<Customer[]>(`${BASE}/search`, {
      params: { venue_id: venueId, q: query, limit },
    }),

  // ============================================================================
  // Customer Visits
  // ============================================================================

  /**
   * Get customer visit history
   */
  getVisits: (customerId: string, params?: PaginationParams) =>
    api.get<PaginatedResponse<CustomerVisit>>(`${BASE}/${customerId}/visits`, {
      params,
    }),

  /**
   * Record a customer visit
   */
  recordVisit: (
    customerId: string,
    data: {
      venueId: string;
      partySize?: number;
      activities?: string[];
      notes?: string;
    }
  ) =>
    api.post<CustomerVisit>(`${BASE}/${customerId}/visits`, data),

  /**
   * Check out customer
   */
  checkOut: (customerId: string, visitId: string, totalSpend?: number) =>
    api.post<CustomerVisit>(`${BASE}/${customerId}/visits/${visitId}/checkout`, {
      total_spend: totalSpend,
    }),

  // ============================================================================
  // Customer Feedback
  // ============================================================================

  /**
   * Get customer feedback
   */
  getFeedback: (customerId: string, params?: PaginationParams) =>
    api.get<PaginatedResponse<CustomerFeedback>>(`${BASE}/${customerId}/feedback`, {
      params,
    }),

  /**
   * Submit feedback
   */
  submitFeedback: (
    customerId: string,
    data: {
      venueId: string;
      visitId?: string;
      rating: number;
      comment?: string;
      category?: string;
    }
  ) =>
    api.post<CustomerFeedback>(`${BASE}/${customerId}/feedback`, data),

  /**
   * Respond to feedback
   */
  respondToFeedback: (customerId: string, feedbackId: string, responseText: string) =>
    api.post<CustomerFeedback>(
      `${BASE}/${customerId}/feedback/${feedbackId}/respond`,
      { response_text: responseText }
    ),

  // ============================================================================
  // Loyalty
  // ============================================================================

  /**
   * Get customer loyalty info
   */
  getLoyaltyInfo: (customerId: string) =>
    api.get<{
      tier: string;
      points: number;
      lifetimePoints: number;
      pointsToNextTier: number;
    }>(`${BASE}/${customerId}/loyalty`),

  /**
   * Add loyalty points (admin)
   */
  addPoints: (customerId: string, points: number, reason: string) =>
    api.post<{ points: number; newTotal: number }>(`${BASE}/${customerId}/loyalty/add`, {
      points,
      reason,
    }),

  /**
   * Redeem loyalty points
   */
  redeemPoints: (customerId: string, points: number, rewardId?: string) =>
    api.post<{ points: number; remaining: number }>(`${BASE}/${customerId}/loyalty/redeem`, {
      points,
      reward_id: rewardId,
    }),

  // ============================================================================
  // Tags & Notes
  // ============================================================================

  /**
   * Add tag to customer
   */
  addTag: (customerId: string, tag: string) =>
    api.post<Customer>(`${BASE}/${customerId}/tags`, { tag }),

  /**
   * Remove tag from customer
   */
  removeTag: (customerId: string, tag: string) =>
    api.delete<Customer>(`${BASE}/${customerId}/tags/${tag}`),

  /**
   * Add note to customer
   */
  addNote: (customerId: string, note: string) =>
    api.post<Customer>(`${BASE}/${customerId}/notes`, { note }),

  // ============================================================================
  // Analytics
  // ============================================================================

  /**
   * Get customer analytics
   */
  getAnalytics: (params?: { venueId?: string; startDate?: string; endDate?: string }) =>
    api.get<CustomerAnalytics>(`${BASE}/analytics`, { params }),

  /**
   * Get top customers
   */
  getTopCustomers: (venueId: string, params?: { metric?: string; limit?: number }) =>
    api.get<Customer[]>(`${BASE}/top`, {
      params: { venue_id: venueId, ...params },
    }),

  /**
   * Get at-risk customers
   */
  getAtRiskCustomers: (venueId: string, params?: { threshold?: number; limit?: number }) =>
    api.get<Customer[]>(`${BASE}/at-risk`, {
      params: { venue_id: venueId, ...params },
    }),

  // ============================================================================
  // Bulk Operations
  // ============================================================================

  /**
   * Import customers from CSV
   */
  import: (venueId: string, file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('venue_id', venueId);
    return api.post<{ imported: number; failed: number; errors?: string[] }>(
      `${BASE}/import`,
      formData
    );
  },

  /**
   * Export customers to CSV
   */
  export: (venueId: string, filters?: CustomerFilter) =>
    api.get<Blob>(`${BASE}/export`, {
      params: { venue_id: venueId, ...filters },
    }),

  /**
   * Merge duplicate customers
   */
  merge: (primaryCustomerId: string, duplicateCustomerIds: string[]) =>
    api.post<Customer>(`${BASE}/merge`, {
      primary_id: primaryCustomerId,
      duplicate_ids: duplicateCustomerIds,
    }),
};
