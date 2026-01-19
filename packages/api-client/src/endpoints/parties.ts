/**
 * Party & Booking API endpoints
 */
import { api } from '../client';
import type {
  PartyPackage,
  PartyAddon,
  PartyBooking,
  PartyTimelineItem,
  PartyStaffAssignment,
  CorporateEvent,
  Booking,
  CalendarEvent,
  AvailabilityResponse,
  PartyAnalytics,
  CreatePartyBookingInput,
  CreateBookingInput,
  PaginatedResponse,
  PaginationParams,
} from '@fec-saas/types';

const BASE = '/api/v1/parties';
const BOOKINGS_BASE = '/api/v1/bookings';

export const partiesApi = {
  // ============================================================================
  // Party Packages
  // ============================================================================

  /**
   * List party packages
   */
  getPackages: (venueId?: string, params?: { isActive?: boolean }) =>
    api.get<PartyPackage[]>(`${BASE}/packages`, {
      params: { venue_id: venueId, ...params },
    }),

  /**
   * Get package by ID
   */
  getPackage: (packageId: string) =>
    api.get<PartyPackage>(`${BASE}/packages/${packageId}`),

  /**
   * Create package (admin)
   */
  createPackage: (data: Omit<PartyPackage, 'id' | 'createdAt' | 'updatedAt'>) =>
    api.post<PartyPackage>(`${BASE}/packages`, data),

  /**
   * Update package (admin)
   */
  updatePackage: (packageId: string, data: Partial<PartyPackage>) =>
    api.put<PartyPackage>(`${BASE}/packages/${packageId}`, data),

  /**
   * Delete package (admin)
   */
  deletePackage: (packageId: string) =>
    api.delete<void>(`${BASE}/packages/${packageId}`),

  // ============================================================================
  // Party Add-ons
  // ============================================================================

  /**
   * List add-ons
   */
  getAddons: (venueId?: string) =>
    api.get<PartyAddon[]>(`${BASE}/addons`, {
      params: { venue_id: venueId },
    }),

  /**
   * Create add-on (admin)
   */
  createAddon: (data: Omit<PartyAddon, 'id'>) =>
    api.post<PartyAddon>(`${BASE}/addons`, data),

  /**
   * Update add-on (admin)
   */
  updateAddon: (addonId: string, data: Partial<PartyAddon>) =>
    api.put<PartyAddon>(`${BASE}/addons/${addonId}`, data),

  // ============================================================================
  // Party Bookings
  // ============================================================================

  /**
   * List party bookings
   */
  getBookings: (
    params?: PaginationParams & {
      venueId?: string;
      status?: string;
      dateFrom?: string;
      dateTo?: string;
    }
  ) =>
    api.get<PaginatedResponse<PartyBooking>>(`${BASE}/bookings`, { params }),

  /**
   * Get booking by ID
   */
  getBooking: (bookingId: string) =>
    api.get<PartyBooking>(`${BASE}/bookings/${bookingId}`),

  /**
   * Create party booking
   */
  createBooking: (venueId: string, data: CreatePartyBookingInput) =>
    api.post<PartyBooking>(`${BASE}/bookings`, { venue_id: venueId, ...data }),

  /**
   * Update booking
   */
  updateBooking: (bookingId: string, data: Partial<PartyBooking>) =>
    api.put<PartyBooking>(`${BASE}/bookings/${bookingId}`, data),

  /**
   * Cancel booking
   */
  cancelBooking: (bookingId: string, reason?: string) =>
    api.delete<void>(`${BASE}/bookings/${bookingId}`, {
      params: { reason },
    }),

  /**
   * Check in party
   */
  checkIn: (bookingId: string) =>
    api.post<PartyBooking>(`${BASE}/bookings/${bookingId}/check-in`),

  /**
   * Complete party
   */
  complete: (bookingId: string) =>
    api.post<PartyBooking>(`${BASE}/bookings/${bookingId}/complete`),

  // ============================================================================
  // Party Execution
  // ============================================================================

  /**
   * Get party timeline
   */
  getTimeline: (bookingId: string) =>
    api.get<PartyTimelineItem[]>(`${BASE}/bookings/${bookingId}/timeline`),

  /**
   * Mark timeline item complete
   */
  completeTimelineItem: (bookingId: string, itemId: string) =>
    api.post<PartyTimelineItem>(
      `${BASE}/bookings/${bookingId}/timeline/item/${itemId}/complete`
    ),

  /**
   * Get assigned staff
   */
  getAssignedStaff: (bookingId: string) =>
    api.get<PartyStaffAssignment[]>(`${BASE}/bookings/${bookingId}/staff`),

  /**
   * Assign staff to party
   */
  assignStaff: (
    bookingId: string,
    staffId: string,
    role: 'PRIMARY_HOST' | 'ASSISTANT' | 'FOOD_RUNNER'
  ) =>
    api.post<PartyStaffAssignment>(`${BASE}/bookings/${bookingId}/staff`, {
      staff_id: staffId,
      role,
    }),

  /**
   * Remove staff from party
   */
  removeStaff: (bookingId: string, assignmentId: string) =>
    api.delete<void>(`${BASE}/bookings/${bookingId}/staff/${assignmentId}`),

  // ============================================================================
  // Corporate Events
  // ============================================================================

  /**
   * List corporate events
   */
  getCorporateEvents: (params?: PaginationParams & { venueId?: string; status?: string }) =>
    api.get<PaginatedResponse<CorporateEvent>>(`${BASE}/corporate`, { params }),

  /**
   * Get corporate event by ID
   */
  getCorporateEvent: (eventId: string) =>
    api.get<CorporateEvent>(`${BASE}/corporate/${eventId}`),

  /**
   * Create corporate event inquiry
   */
  createCorporateEvent: (data: Omit<CorporateEvent, 'id' | 'createdAt'>) =>
    api.post<CorporateEvent>(`${BASE}/corporate`, data),

  /**
   * Update corporate event
   */
  updateCorporateEvent: (eventId: string, data: Partial<CorporateEvent>) =>
    api.put<CorporateEvent>(`${BASE}/corporate/${eventId}`, data),

  /**
   * Update corporate event status
   */
  updateCorporateEventStatus: (eventId: string, status: string) =>
    api.patch<CorporateEvent>(`${BASE}/corporate/${eventId}/status`, { status }),

  // ============================================================================
  // Availability
  // ============================================================================

  /**
   * Check availability for a date
   */
  checkAvailability: (
    venueId: string,
    date: string,
    params?: { packageId?: string; partySize?: number }
  ) =>
    api.get<AvailabilityResponse>(`${BASE}/availability`, {
      params: { venue_id: venueId, date, ...params },
    }),

  // ============================================================================
  // Analytics
  // ============================================================================

  /**
   * Get party analytics
   */
  getAnalytics: (params?: { venueId?: string; startDate?: string; endDate?: string }) =>
    api.get<PartyAnalytics>(`${BASE}/analytics`, { params }),
};

// ============================================================================
// General Bookings (bowling, arcade, etc.)
// ============================================================================

export const bookingsApi = {
  /**
   * List bookings
   */
  list: (
    params?: PaginationParams & {
      venueId?: string;
      type?: string;
      status?: string;
      dateFrom?: string;
      dateTo?: string;
    }
  ) =>
    api.get<PaginatedResponse<Booking>>(BOOKINGS_BASE, { params }),

  /**
   * Get booking by ID
   */
  get: (bookingId: string) =>
    api.get<Booking>(`${BOOKINGS_BASE}/${bookingId}`),

  /**
   * Create booking
   */
  create: (venueId: string, data: CreateBookingInput) =>
    api.post<Booking>(BOOKINGS_BASE, { venue_id: venueId, ...data }),

  /**
   * Update booking
   */
  update: (bookingId: string, data: Partial<Booking>) =>
    api.put<Booking>(`${BOOKINGS_BASE}/${bookingId}`, data),

  /**
   * Cancel booking
   */
  cancel: (bookingId: string) =>
    api.delete<void>(`${BOOKINGS_BASE}/${bookingId}`),

  /**
   * Get calendar events for a date range
   */
  getCalendarEvents: (params: {
    venueId: string;
    startDate: string;
    endDate: string;
    types?: string[];
  }) =>
    api.get<CalendarEvent[]>(`${BOOKINGS_BASE}/calendar`, { params }),
};
