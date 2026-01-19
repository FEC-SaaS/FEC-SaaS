/**
 * Re-export types from @fec-saas/types for convenience
 */
export * from '@fec-saas/types';

// Additional API-specific types
export interface QueryOptions {
  enabled?: boolean;
  staleTime?: number;
  refetchOnWindowFocus?: boolean;
  refetchInterval?: number;
}

export interface MutationOptions {
  onSuccess?: () => void;
  onError?: (error: unknown) => void;
}
