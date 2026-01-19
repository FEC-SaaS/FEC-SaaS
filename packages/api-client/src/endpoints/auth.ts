/**
 * Auth API endpoints
 */
import { api } from '../client';
import type {
  User,
  AuthResponse,
  AuthTokens,
  LoginInput,
  RegisterInput,
  PasswordResetInput,
  PasswordResetConfirmInput,
  FamilyGroup,
  FamilyMember,
  ParentalControl,
  Membership,
  MembershipPlan,
  UserPreference,
  UserSession,
} from '@fec-saas/types';

const AUTH_BASE = '/api/v1/auth';
const USERS_BASE = '/api/v1/users';

// ============================================================================
// Authentication
// ============================================================================

export const authApi = {
  /**
   * Login with email and password
   */
  login: (data: LoginInput) =>
    api.post<AuthResponse>(`${AUTH_BASE}/login`, data),

  /**
   * Register a new user
   */
  register: (data: RegisterInput) =>
    api.post<AuthResponse>(`${AUTH_BASE}/register`, data),

  /**
   * Logout (invalidate tokens)
   */
  logout: () =>
    api.post<{ message: string }>(`${AUTH_BASE}/logout`),

  /**
   * Refresh access token
   */
  refreshToken: (refreshToken: string) =>
    api.post<AuthTokens>(`${AUTH_BASE}/refresh`, { refresh_token: refreshToken }),

  /**
   * Request password reset email
   */
  requestPasswordReset: (data: PasswordResetInput) =>
    api.post<{ message: string }>(`${AUTH_BASE}/password-reset`, data),

  /**
   * Confirm password reset with token
   */
  confirmPasswordReset: (data: PasswordResetConfirmInput) =>
    api.post<{ message: string }>(`${AUTH_BASE}/password-reset/confirm`, data),

  /**
   * Verify email with token
   */
  verifyEmail: (token: string) =>
    api.post<{ message: string }>(`${AUTH_BASE}/verify-email`, { token }),

  /**
   * Resend email verification
   */
  resendVerificationEmail: () =>
    api.post<{ message: string }>(`${AUTH_BASE}/resend-verification`),

  /**
   * Get current user (me)
   */
  me: () =>
    api.get<User>(`${USERS_BASE}/me`),

  /**
   * Update current user profile
   */
  updateProfile: (data: Partial<User>) =>
    api.put<User>(`${USERS_BASE}/me`, data),

  /**
   * Change password
   */
  changePassword: (currentPassword: string, newPassword: string) =>
    api.post<{ message: string }>(`${USERS_BASE}/me/password`, {
      current_password: currentPassword,
      new_password: newPassword,
    }),

  /**
   * Get user sessions
   */
  getSessions: () =>
    api.get<UserSession[]>(`${USERS_BASE}/me/sessions`),

  /**
   * Revoke a session
   */
  revokeSession: (sessionId: string) =>
    api.delete<void>(`${USERS_BASE}/me/sessions/${sessionId}`),
};

// ============================================================================
// Family Management
// ============================================================================

export const familyApi = {
  /**
   * Get user's family groups
   */
  getGroups: () =>
    api.get<FamilyGroup[]>('/api/v1/family'),

  /**
   * Create a family group
   */
  createGroup: (data: { name: string; sharedRewardsEnabled?: boolean }) =>
    api.post<FamilyGroup>('/api/v1/family', data),

  /**
   * Get family group by ID
   */
  getGroup: (groupId: string) =>
    api.get<FamilyGroup>(`/api/v1/family/${groupId}`),

  /**
   * Update family group
   */
  updateGroup: (groupId: string, data: Partial<FamilyGroup>) =>
    api.put<FamilyGroup>(`/api/v1/family/${groupId}`, data),

  /**
   * Delete family group
   */
  deleteGroup: (groupId: string) =>
    api.delete<void>(`/api/v1/family/${groupId}`),

  /**
   * Add member to family
   */
  addMember: (groupId: string, data: { email: string; role?: string }) =>
    api.post<FamilyMember>(`/api/v1/family/${groupId}/members`, data),

  /**
   * Remove member from family
   */
  removeMember: (groupId: string, memberId: string) =>
    api.delete<void>(`/api/v1/family/${groupId}/members/${memberId}`),
};

// ============================================================================
// Parental Controls
// ============================================================================

export const parentalApi = {
  /**
   * Get parental controls for a child
   */
  getControls: (childId: string) =>
    api.get<ParentalControl>(`/api/v1/parental/controls/${childId}`),

  /**
   * Set parental controls
   */
  setControls: (childId: string, data: Partial<ParentalControl>) =>
    api.post<ParentalControl>(`/api/v1/parental/controls/${childId}`, data),

  /**
   * Update parental controls
   */
  updateControls: (childId: string, data: Partial<ParentalControl>) =>
    api.put<ParentalControl>(`/api/v1/parental/controls/${childId}`, data),

  /**
   * Delete parental controls
   */
  deleteControls: (childId: string) =>
    api.delete<void>(`/api/v1/parental/controls/${childId}`),
};

// ============================================================================
// Membership
// ============================================================================

export const membershipApi = {
  /**
   * Get available membership plans
   */
  getPlans: (venueId?: string) =>
    api.get<MembershipPlan[]>('/api/v1/membership/plans', {
      params: { venue_id: venueId },
    }),

  /**
   * Get user's memberships
   */
  getMyMemberships: () =>
    api.get<Membership[]>('/api/v1/membership/my'),

  /**
   * Subscribe to a membership plan
   */
  subscribe: (planId: string, paymentMethodId?: string) =>
    api.post<Membership>('/api/v1/membership/subscribe', {
      plan_id: planId,
      payment_method_id: paymentMethodId,
    }),

  /**
   * Cancel membership
   */
  cancel: (membershipId: string, reason?: string) =>
    api.post<Membership>(`/api/v1/membership/${membershipId}/cancel`, { reason }),

  /**
   * Freeze membership
   */
  freeze: (membershipId: string, endDate: string) =>
    api.post<Membership>(`/api/v1/membership/${membershipId}/freeze`, {
      end_date: endDate,
    }),

  /**
   * Unfreeze membership
   */
  unfreeze: (membershipId: string) =>
    api.post<Membership>(`/api/v1/membership/${membershipId}/unfreeze`),
};

// ============================================================================
// Loyalty
// ============================================================================

export const loyaltyApi = {
  /**
   * Get loyalty status
   */
  getStatus: () =>
    api.get<{
      tier: string;
      points: number;
      lifetimePoints: number;
      pointsToNextTier: number;
      tierBenefits: string[];
    }>('/api/v1/loyalty/status'),

  /**
   * Get loyalty tiers info
   */
  getTiers: () =>
    api.get<{
      name: string;
      minPoints: number;
      benefits: string[];
    }[]>('/api/v1/loyalty/tiers'),

  /**
   * Get points history
   */
  getHistory: (params?: { page?: number; limit?: number }) =>
    api.get<{
      data: {
        id: string;
        points: number;
        reason: string;
        createdAt: string;
      }[];
      pagination: {
        page: number;
        limit: number;
        total: number;
      };
    }>('/api/v1/loyalty/history', { params }),
};
