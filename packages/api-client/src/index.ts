/**
 * FEC SaaS API Client
 *
 * Central export point for all API endpoints and utilities.
 */

// Core client
export {
  api,
  get,
  post,
  put,
  patch,
  del,
  initializeApiClient,
  getApiConfig,
  type ApiClientConfig,
  type ApiError,
  type RequestOptions,
} from './client';

// Auth endpoints
export { authApi, familyApi, parentalApi, membershipApi, loyaltyApi } from './endpoints/auth';

// Venue endpoints
export { venuesApi } from './endpoints/venues';

// Party & Booking endpoints
export { partiesApi, bookingsApi } from './endpoints/parties';

// Customer endpoints
export { customersApi } from './endpoints/customers';

// Notification endpoints
export { notificationsApi, templatesApi } from './endpoints/notifications';

// Re-export types
export * from './types';
