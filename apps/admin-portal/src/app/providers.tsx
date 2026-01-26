/**
 * =============================================================================
 * FILE: providers.tsx
 * PURPOSE: Root providers wrapper for the admin portal
 * =============================================================================
 *
 * This component wraps the application with all necessary context providers:
 * - QueryClientProvider: React Query for server state management
 * - AuthProvider: Authentication state and actions
 * - ThemeProvider: (Optional) Theme management
 *
 * =============================================================================
 */

'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';
import { AuthProvider } from '@/contexts/auth-context';

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
            refetchOnWindowFocus: false,
            retry: 1,
          },
          mutations: {
            retry: 0,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>{children}</AuthProvider>
    </QueryClientProvider>
  );
}
