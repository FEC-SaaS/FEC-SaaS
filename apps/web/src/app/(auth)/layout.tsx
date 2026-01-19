// Path: apps/web/src/app/(auth)/layout.tsx
// Layout wrapper for authentication pages

import { ReactNode } from 'react';
import { Metadata } from 'next';

export const metadata: Metadata = {
  title: {
    default: 'Authentication',
    template: '%s | FEC SaaS',
  },
  description: 'Sign in to your FEC management platform',
};

interface AuthLayoutProps {
  children: ReactNode;
}

export default function AuthLayout({ children }: AuthLayoutProps) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100">
      {children}
    </div>
  );
}