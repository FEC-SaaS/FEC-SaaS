/**
 * Base API client for FEC SaaS platform
 */

export interface ApiClientConfig {
  baseUrl: string;
  getAccessToken?: () => string | null;
  onUnauthorized?: () => void;
  onError?: (error: ApiError) => void;
}

export interface ApiError {
  status: number;
  code: string;
  message: string;
  details?: Record<string, string[]>;
}

export interface RequestOptions {
  headers?: Record<string, string>;
  params?: Record<string, string | number | boolean | undefined>;
  signal?: AbortSignal;
}

let config: ApiClientConfig = {
  baseUrl: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
};

/**
 * Initialize the API client with configuration
 */
export function initializeApiClient(newConfig: Partial<ApiClientConfig>) {
  config = { ...config, ...newConfig };
}

/**
 * Get current configuration
 */
export function getApiConfig(): ApiClientConfig {
  return config;
}

/**
 * Build URL with query parameters
 */
function buildUrl(path: string, params?: Record<string, string | number | boolean | undefined>): string {
  const url = new URL(path, config.baseUrl);

  if (params) {
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        url.searchParams.append(key, String(value));
      }
    });
  }

  return url.toString();
}

/**
 * Build headers with authentication
 */
function buildHeaders(customHeaders?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...customHeaders,
  };

  const token = config.getAccessToken?.();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  return headers;
}

/**
 * Handle API response
 */
async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error: ApiError = {
      status: response.status,
      code: 'API_ERROR',
      message: 'An error occurred',
    };

    try {
      const errorData = await response.json();
      error.code = errorData.code || errorData.detail || 'API_ERROR';
      error.message = errorData.message || errorData.detail || response.statusText;
      error.details = errorData.details;
    } catch {
      error.message = response.statusText;
    }

    if (response.status === 401) {
      config.onUnauthorized?.();
    }

    config.onError?.(error);
    throw error;
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
}

/**
 * HTTP GET request
 */
export async function get<T>(path: string, options?: RequestOptions): Promise<T> {
  const url = buildUrl(path, options?.params);
  const response = await fetch(url, {
    method: 'GET',
    headers: buildHeaders(options?.headers),
    signal: options?.signal,
  });
  return handleResponse<T>(response);
}

/**
 * HTTP POST request
 */
export async function post<T, D = unknown>(path: string, data?: D, options?: RequestOptions): Promise<T> {
  const url = buildUrl(path, options?.params);
  const response = await fetch(url, {
    method: 'POST',
    headers: buildHeaders(options?.headers),
    body: data ? JSON.stringify(data) : undefined,
    signal: options?.signal,
  });
  return handleResponse<T>(response);
}

/**
 * HTTP PUT request
 */
export async function put<T, D = unknown>(path: string, data?: D, options?: RequestOptions): Promise<T> {
  const url = buildUrl(path, options?.params);
  const response = await fetch(url, {
    method: 'PUT',
    headers: buildHeaders(options?.headers),
    body: data ? JSON.stringify(data) : undefined,
    signal: options?.signal,
  });
  return handleResponse<T>(response);
}

/**
 * HTTP PATCH request
 */
export async function patch<T, D = unknown>(path: string, data?: D, options?: RequestOptions): Promise<T> {
  const url = buildUrl(path, options?.params);
  const response = await fetch(url, {
    method: 'PATCH',
    headers: buildHeaders(options?.headers),
    body: data ? JSON.stringify(data) : undefined,
    signal: options?.signal,
  });
  return handleResponse<T>(response);
}

/**
 * HTTP DELETE request
 */
export async function del<T>(path: string, options?: RequestOptions): Promise<T> {
  const url = buildUrl(path, options?.params);
  const response = await fetch(url, {
    method: 'DELETE',
    headers: buildHeaders(options?.headers),
    signal: options?.signal,
  });
  return handleResponse<T>(response);
}

// Export api object for convenience
export const api = {
  get,
  post,
  put,
  patch,
  delete: del,
};
