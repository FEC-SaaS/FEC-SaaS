/**
 * =============================================================================
 * FILE: api-client.ts
 * PURPOSE: HTTP client for API Gateway communication
 * =============================================================================
 *
 * This module provides a typed HTTP client for communicating with the
 * FEC SaaS API Gateway. It handles authentication, error handling,
 * and request/response transformation.
 *
 * FEATURES:
 * - Automatic token management (access/refresh)
 * - Request interceptors for auth headers
 * - Response interceptors for error handling
 * - Typed API responses
 * - Automatic token refresh on 401
 *
 * USAGE:
 *   import { apiClient } from '@/lib/api-client';
 *
 *   // GET request
 *   const venues = await apiClient.get<Venue[]>('/api/v1/venues');
 *
 *   // POST request
 *   const newVenue = await apiClient.post<Venue>('/api/v1/venues', venueData);
 *
 * =============================================================================
 */

// API base URL - defaults to localhost for development
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';

// Token storage keys
const ACCESS_TOKEN_KEY = 'fec_access_token';
const REFRESH_TOKEN_KEY = 'fec_refresh_token';

/**
 * API Error class for handling HTTP errors
 */
export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(message: string, status: number, data?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

/**
 * Token storage utilities
 */
export const tokenStorage = {
  getAccessToken: (): string | null => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(ACCESS_TOKEN_KEY);
  },

  getRefreshToken: (): string | null => {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(REFRESH_TOKEN_KEY);
  },

  setTokens: (accessToken: string, refreshToken: string): void => {
    if (typeof window === 'undefined') return;
    localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
    localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  },

  clearTokens: (): void => {
    if (typeof window === 'undefined') return;
    localStorage.removeItem(ACCESS_TOKEN_KEY);
    localStorage.removeItem(REFRESH_TOKEN_KEY);
  },

  hasTokens: (): boolean => {
    return !!tokenStorage.getAccessToken() && !!tokenStorage.getRefreshToken();
  },
};

/**
 * Request options type
 */
interface RequestOptions extends Omit<RequestInit, 'body'> {
  body?: unknown;
  skipAuth?: boolean;
}

/**
 * Refresh the access token using the refresh token
 */
async function refreshAccessToken(): Promise<boolean> {
  const refreshToken = tokenStorage.getRefreshToken();
  if (!refreshToken) return false;

  try {
    const response = await fetch(`${API_BASE_URL}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });

    if (!response.ok) {
      tokenStorage.clearTokens();
      return false;
    }

    const data = await response.json();
    tokenStorage.setTokens(data.access_token, data.refresh_token);
    return true;
  } catch {
    tokenStorage.clearTokens();
    return false;
  }
}

/**
 * Make an authenticated API request
 */
async function makeRequest<T>(
  endpoint: string,
  options: RequestOptions = {}
): Promise<T> {
  const { body, skipAuth = false, ...fetchOptions } = options;

  // Build headers
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  // Add auth token if available and not skipped
  if (!skipAuth) {
    const accessToken = tokenStorage.getAccessToken();
    if (accessToken) {
      (headers as Record<string, string>)['Authorization'] = `Bearer ${accessToken}`;
    }
  }

  // Build request config
  const config: RequestInit = {
    ...fetchOptions,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  };

  // Make request
  let response = await fetch(`${API_BASE_URL}${endpoint}`, config);

  // Handle 401 - try to refresh token
  if (response.status === 401 && !skipAuth) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      // Retry with new token
      const newToken = tokenStorage.getAccessToken();
      (headers as Record<string, string>)['Authorization'] = `Bearer ${newToken}`;
      response = await fetch(`${API_BASE_URL}${endpoint}`, {
        ...config,
        headers,
      });
    }
  }

  // Handle response
  if (!response.ok) {
    let errorData: unknown;
    try {
      errorData = await response.json();
    } catch {
      errorData = { message: response.statusText };
    }

    throw new ApiError(
      (errorData as { detail?: string; message?: string })?.detail ||
        (errorData as { message?: string })?.message ||
        'An error occurred',
      response.status,
      errorData
    );
  }

  // Return empty for 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

/**
 * API Client with typed methods
 */
export const apiClient = {
  /**
   * GET request
   */
  get: <T>(endpoint: string, options?: RequestOptions): Promise<T> => {
    return makeRequest<T>(endpoint, { ...options, method: 'GET' });
  },

  /**
   * POST request
   */
  post: <T>(endpoint: string, body?: unknown, options?: RequestOptions): Promise<T> => {
    return makeRequest<T>(endpoint, { ...options, method: 'POST', body });
  },

  /**
   * PUT request
   */
  put: <T>(endpoint: string, body?: unknown, options?: RequestOptions): Promise<T> => {
    return makeRequest<T>(endpoint, { ...options, method: 'PUT', body });
  },

  /**
   * PATCH request
   */
  patch: <T>(endpoint: string, body?: unknown, options?: RequestOptions): Promise<T> => {
    return makeRequest<T>(endpoint, { ...options, method: 'PATCH', body });
  },

  /**
   * DELETE request
   */
  delete: <T>(endpoint: string, options?: RequestOptions): Promise<T> => {
    return makeRequest<T>(endpoint, { ...options, method: 'DELETE' });
  },
};

/**
 * Auth API helpers
 */
export const authApi = {
  /**
   * Login with email and password
   */
  login: async (email: string, password: string) => {
    const response = await apiClient.post<{
      user: User;
      tokens: { access_token: string; refresh_token: string };
    }>('/api/v1/auth/login', { email, password }, { skipAuth: true });

    tokenStorage.setTokens(response.tokens.access_token, response.tokens.refresh_token);
    return response;
  },

  /**
   * Register new user
   */
  register: async (data: {
    email: string;
    password: string;
    first_name?: string;
    last_name?: string;
  }) => {
    const response = await apiClient.post<{
      user: User;
      tokens: { access_token: string; refresh_token: string };
    }>('/api/v1/auth/register', data, { skipAuth: true });

    tokenStorage.setTokens(response.tokens.access_token, response.tokens.refresh_token);
    return response;
  },

  /**
   * Logout
   */
  logout: async () => {
    const refreshToken = tokenStorage.getRefreshToken();
    if (refreshToken) {
      try {
        await apiClient.post('/api/v1/auth/logout', { refresh_token: refreshToken });
      } catch {
        // Ignore errors during logout
      }
    }
    tokenStorage.clearTokens();
  },

  /**
   * Get current user
   */
  getCurrentUser: () => {
    return apiClient.get<User>('/api/v1/auth/me');
  },

  /**
   * Update current user
   */
  updateCurrentUser: (data: Partial<User>) => {
    return apiClient.put<User>('/api/v1/auth/me', data);
  },

  /**
   * Request password reset
   */
  forgotPassword: (email: string) => {
    return apiClient.post('/api/v1/auth/forgot-password', { email }, { skipAuth: true });
  },

  /**
   * Reset password with token
   */
  resetPassword: (token: string, newPassword: string) => {
    return apiClient.post(
      '/api/v1/auth/reset-password',
      { token, new_password: newPassword },
      { skipAuth: true }
    );
  },
};

/**
 * User type (basic structure)
 */
export interface User {
  id: string;
  email: string;
  first_name?: string;
  last_name?: string;
  phone?: string;
  email_verified: boolean;
  phone_verified: boolean;
  created_at: string;
  updated_at: string;
}

// =============================================================================
// END OF FILE
// =============================================================================
