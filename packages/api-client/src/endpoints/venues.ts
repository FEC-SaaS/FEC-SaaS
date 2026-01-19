/**
 * Venue API endpoints
 */
import { api } from '../client';
import type {
  Venue,
  VenueWithDetails,
  VenueHours,
  VenueHoursInput,
  VenueFeatureConfig,
  VenueAIConfig,
  VenueSetting,
  VenuePerformance,
  VenueBenchmark,
  VenueDashboardStats,
  CreateVenueInput,
  UpdateVenueInput,
  PaginatedResponse,
  PaginationParams,
} from '@fec-saas/types';

const BASE = '/api/v1/venues';

export const venuesApi = {
  // ============================================================================
  // Venue CRUD
  // ============================================================================

  /**
   * List all venues (with pagination and filters)
   */
  list: (params?: PaginationParams & { status?: string; tier?: string }) =>
    api.get<PaginatedResponse<Venue>>(BASE, { params }),

  /**
   * Get venue by ID
   */
  get: (venueId: string) =>
    api.get<Venue>(`${BASE}/${venueId}`),

  /**
   * Get venue with all details (hours, features, AI config)
   */
  getWithDetails: (venueId: string) =>
    api.get<VenueWithDetails>(`${BASE}/${venueId}/details`),

  /**
   * Create a new venue
   */
  create: (data: CreateVenueInput) =>
    api.post<Venue>(BASE, data),

  /**
   * Update venue
   */
  update: (venueId: string, data: UpdateVenueInput) =>
    api.put<Venue>(`${BASE}/${venueId}`, data),

  /**
   * Delete venue
   */
  delete: (venueId: string) =>
    api.delete<void>(`${BASE}/${venueId}`),

  /**
   * Change venue status
   */
  updateStatus: (venueId: string, status: string) =>
    api.patch<Venue>(`${BASE}/${venueId}/status`, { status }),

  // ============================================================================
  // Operating Hours
  // ============================================================================

  /**
   * Get venue operating hours
   */
  getHours: (venueId: string) =>
    api.get<VenueHours[]>(`${BASE}/${venueId}/hours`),

  /**
   * Update venue operating hours
   */
  updateHours: (venueId: string, hours: VenueHoursInput[]) =>
    api.put<VenueHours[]>(`${BASE}/${venueId}/hours`, { hours }),

  // ============================================================================
  // Features
  // ============================================================================

  /**
   * Get venue features
   */
  getFeatures: (venueId: string) =>
    api.get<VenueFeatureConfig[]>(`${BASE}/${venueId}/features`),

  /**
   * Update venue features
   */
  updateFeatures: (venueId: string, features: Partial<VenueFeatureConfig>[]) =>
    api.put<VenueFeatureConfig[]>(`${BASE}/${venueId}/features`, { features }),

  /**
   * Toggle a feature
   */
  toggleFeature: (venueId: string, featureName: string, enabled: boolean) =>
    api.patch<VenueFeatureConfig>(`${BASE}/${venueId}/features/${featureName}`, {
      is_enabled: enabled,
    }),

  // ============================================================================
  // AI Configuration
  // ============================================================================

  /**
   * Get AI configuration
   */
  getAIConfig: (venueId: string) =>
    api.get<VenueAIConfig[]>(`${BASE}/${venueId}/ai-config`),

  /**
   * Update AI configuration
   */
  updateAIConfig: (venueId: string, config: Partial<VenueAIConfig>[]) =>
    api.put<VenueAIConfig[]>(`${BASE}/${venueId}/ai-config`, { config }),

  /**
   * Toggle AI service
   */
  toggleAIService: (
    venueId: string,
    serviceName: string,
    enabled: boolean,
    strategy?: string
  ) =>
    api.patch<VenueAIConfig>(`${BASE}/${venueId}/ai-config/${serviceName}`, {
      is_enabled: enabled,
      strategy,
    }),

  // ============================================================================
  // Settings
  // ============================================================================

  /**
   * Get all venue settings
   */
  getSettings: (venueId: string) =>
    api.get<VenueSetting[]>(`${BASE}/${venueId}/settings`),

  /**
   * Update settings (bulk)
   */
  updateSettings: (venueId: string, settings: Record<string, unknown>) =>
    api.put<VenueSetting[]>(`${BASE}/${venueId}/settings`, { settings }),

  /**
   * Get a single setting
   */
  getSetting: (venueId: string, key: string) =>
    api.get<VenueSetting>(`${BASE}/${venueId}/settings/${key}`),

  /**
   * Update a single setting
   */
  updateSetting: (venueId: string, key: string, value: unknown) =>
    api.put<VenueSetting>(`${BASE}/${venueId}/settings/${key}`, { value }),

  // ============================================================================
  // Performance & Analytics
  // ============================================================================

  /**
   * Get venue performance metrics
   */
  getPerformance: (
    venueId: string,
    params?: { startDate?: string; endDate?: string }
  ) =>
    api.get<VenuePerformance[]>(`${BASE}/${venueId}/performance`, { params }),

  /**
   * Get dashboard stats
   */
  getDashboardStats: (venueId: string) =>
    api.get<VenueDashboardStats>(`${BASE}/${venueId}/dashboard`),

  /**
   * Get cross-venue benchmarks
   */
  getBenchmarks: (params?: { metric?: string; period?: string }) =>
    api.get<VenueBenchmark[]>(`${BASE}/benchmarks`, { params }),

  /**
   * Get venue leaderboard
   */
  getLeaderboard: (params?: { metric?: string; limit?: number }) =>
    api.get<VenueBenchmark[]>(`${BASE}/leaderboard`, { params }),

  // ============================================================================
  // Onboarding
  // ============================================================================

  /**
   * Start onboarding process
   */
  startOnboarding: (venueId: string) =>
    api.post<{ venueId: string; steps: unknown[] }>(`${BASE}/${venueId}/onboard`),

  /**
   * Get onboarding status
   */
  getOnboardingStatus: (venueId: string) =>
    api.get<{
      venueId: string;
      completedSteps: number;
      totalSteps: number;
      isComplete: boolean;
      steps: { name: string; isComplete: boolean }[];
    }>(`${BASE}/${venueId}/onboarding-status`),

  /**
   * Mark venue as go-live
   */
  goLive: (venueId: string) =>
    api.post<Venue>(`${BASE}/${venueId}/go-live`),
};
