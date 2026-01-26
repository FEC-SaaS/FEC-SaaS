/**
 * =============================================================================
 * FILE: auth-context.tsx
 * PURPOSE: Authentication context and provider for the admin portal
 * =============================================================================
 *
 * This module provides React context for authentication state management.
 * It handles user login/logout, token management, and auth state persistence.
 *
 * FEATURES:
 * - Global auth state management
 * - Auto-login on page load (if tokens exist)
 * - Login/logout functions
 * - User profile access
 * - Loading and error states
 *
 * USAGE:
 *   // Wrap app with provider
 *   <AuthProvider>
 *     <App />
 *   </AuthProvider>
 *
 *   // Use in components
 *   const { user, login, logout, isAuthenticated } = useAuth();
 *
 * =============================================================================
 */

'use client';

import React, {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  ReactNode,
} from 'react';
import { useRouter } from 'next/navigation';
import { authApi, tokenStorage, User, ApiError } from '@/lib/api-client';

/**
 * Auth context state type
 */
interface AuthContextType {
  // State
  user: User | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;

  // Actions
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  updateUser: (data: Partial<User>) => Promise<void>;
  clearError: () => void;
}

interface RegisterData {
  email: string;
  password: string;
  first_name?: string;
  last_name?: string;
}

/**
 * Auth context with default values
 */
const AuthContext = createContext<AuthContextType>({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  error: null,
  login: async () => {},
  logout: async () => {},
  register: async () => {},
  updateUser: async () => {},
  clearError: () => {},
});

/**
 * Auth Provider component
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  /**
   * Check if user is authenticated
   */
  const isAuthenticated = !!user;

  /**
   * Load user on mount if tokens exist
   */
  useEffect(() => {
    const initAuth = async () => {
      if (!tokenStorage.hasTokens()) {
        setIsLoading(false);
        return;
      }

      try {
        const userData = await authApi.getCurrentUser();
        setUser(userData);
      } catch (err) {
        // Token invalid, clear it
        tokenStorage.clearTokens();
        console.error('Failed to load user:', err);
      } finally {
        setIsLoading(false);
      }
    };

    initAuth();
  }, []);

  /**
   * Login function
   */
  const login = useCallback(async (email: string, password: string) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await authApi.login(email, password);
      setUser(response.user);
      router.push('/dashboard');
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : 'Login failed. Please try again.';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [router]);

  /**
   * Logout function
   */
  const logout = useCallback(async () => {
    setIsLoading(true);

    try {
      await authApi.logout();
    } finally {
      setUser(null);
      setIsLoading(false);
      router.push('/');
    }
  }, [router]);

  /**
   * Register function
   */
  const register = useCallback(async (data: RegisterData) => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await authApi.register(data);
      setUser(response.user);
      router.push('/dashboard');
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : 'Registration failed. Please try again.';
      setError(message);
      throw err;
    } finally {
      setIsLoading(false);
    }
  }, [router]);

  /**
   * Update user profile
   */
  const updateUser = useCallback(async (data: Partial<User>) => {
    setError(null);

    try {
      const updatedUser = await authApi.updateCurrentUser(data);
      setUser(updatedUser);
    } catch (err) {
      const message =
        err instanceof ApiError
          ? err.message
          : 'Failed to update profile.';
      setError(message);
      throw err;
    }
  }, []);

  /**
   * Clear error
   */
  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const value: AuthContextType = {
    user,
    isAuthenticated,
    isLoading,
    error,
    login,
    logout,
    register,
    updateUser,
    clearError,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/**
 * Hook to use auth context
 */
export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}

/**
 * HOC to require authentication
 */
export function withAuth<P extends object>(Component: React.ComponentType<P>) {
  return function AuthenticatedComponent(props: P) {
    const { isAuthenticated, isLoading } = useAuth();
    const router = useRouter();

    useEffect(() => {
      if (!isLoading && !isAuthenticated) {
        router.push('/');
      }
    }, [isAuthenticated, isLoading, router]);

    if (isLoading) {
      return (
        <div className="flex h-screen items-center justify-center">
          <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        </div>
      );
    }

    if (!isAuthenticated) {
      return null;
    }

    return <Component {...props} />;
  };
}

// =============================================================================
// END OF FILE
// =============================================================================
