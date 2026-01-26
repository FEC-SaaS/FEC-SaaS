/**
 * =============================================================================
 * FILE: (dashboard)/layout.tsx
 * PURPOSE: Enhanced dashboard layout with sidebar navigation and header
 * =============================================================================
 *
 * This is the main layout component for all authenticated dashboard pages.
 * It provides:
 * - Collapsible sidebar navigation with smooth animations
 * - Top header with user profile and notifications
 * - Responsive design (sidebar transforms to mobile menu on small screens)
 * - Integration with auth context for user data
 * - Gradient accents and modern visual styling
 *
 * LAYOUT STRUCTURE:
 * ┌─────────────────────────────────────────────────────────────┐
 * │ ┌──────────┐ ┌─────────────────────────────────────────────┐│
 * │ │          │ │              Top Header                     ││
 * │ │          │ ├─────────────────────────────────────────────┤│
 * │ │ Sidebar  │ │                                             ││
 * │ │   Nav    │ │              Main Content                   ││
 * │ │          │ │                                             ││
 * │ │          │ │                                             ││
 * │ └──────────┘ └─────────────────────────────────────────────┘│
 * └─────────────────────────────────────────────────────────────┘
 *
 * =============================================================================
 */

'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/auth-context';
import {
  LayoutDashboard,
  Building2,
  PartyPopper,
  Users,
  Calendar,
  BarChart3,
  Settings,
  Bell,
  ChevronLeft,
  ChevronRight,
  LogOut,
  Menu,
  X,
  Search,
  Moon,
  Sun,
  ChevronDown,
  User,
  HelpCircle,
} from 'lucide-react';
import { cn } from '@fec-saas/ui';

/**
 * Navigation items configuration
 */
const navigation = [
  {
    name: 'Dashboard',
    href: '/dashboard',
    icon: LayoutDashboard,
    description: 'Overview and analytics'
  },
  {
    name: 'Venues',
    href: '/venues',
    icon: Building2,
    description: 'Manage locations'
  },
  {
    name: 'Party Bookings',
    href: '/parties',
    icon: PartyPopper,
    description: 'Bookings and events'
  },
  {
    name: 'Customers',
    href: '/customers',
    icon: Users,
    description: 'Customer database'
  },
  {
    name: 'Events',
    href: '/events',
    icon: Calendar,
    description: 'Special events'
  },
  {
    name: 'Analytics',
    href: '/analytics',
    icon: BarChart3,
    description: 'Reports and insights'
  },
  {
    name: 'Settings',
    href: '/settings',
    icon: Settings,
    description: 'System settings'
  },
];

/**
 * Mock notifications for demo
 */
const notifications = [
  { id: 1, title: 'New booking received', message: 'Sarah Johnson booked a party for Jan 25', time: '5 min ago', read: false },
  { id: 2, title: 'Payment received', message: 'Deposit of $150 received for booking #PB-001', time: '1 hour ago', read: false },
  { id: 3, title: 'Venue maintenance', message: 'Kids Paradise scheduled for maintenance', time: '2 hours ago', read: true },
];

/**
 * Dashboard Layout Component
 */
export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const [darkMode, setDarkMode] = useState(false);
  const pathname = usePathname();
  const router = useRouter();
  const { user, logout, isLoading, isAuthenticated } = useAuth();

  // Redirect if not authenticated
  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      router.push('/');
    }
  }, [isLoading, isAuthenticated, router]);

  // Close dropdowns when clicking outside
  useEffect(() => {
    const handleClickOutside = () => {
      setShowNotifications(false);
      setShowUserMenu(false);
    };
    document.addEventListener('click', handleClickOutside);
    return () => document.removeEventListener('click', handleClickOutside);
  }, []);

  // Handle logout
  const handleLogout = async () => {
    await logout();
  };

  // Get current page title
  const currentPage = navigation.find((n) => pathname.startsWith(n.href))?.name || 'Dashboard';

  // Show loading while checking auth
  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
        <div className="text-center">
          <div className="h-12 w-12 mx-auto animate-spin rounded-full border-4 border-white/20 border-t-white" />
          <p className="mt-4 text-white/60">Loading...</p>
        </div>
      </div>
    );
  }

  // Get user display name
  const userDisplayName = user?.first_name
    ? `${user.first_name} ${user.last_name || ''}`.trim()
    : user?.email?.split('@')[0] || 'Admin User';

  const userInitials = user?.first_name
    ? `${user.first_name[0]}${user.last_name?.[0] || ''}`.toUpperCase()
    : user?.email?.[0]?.toUpperCase() || 'A';

  return (
    <div className="flex h-screen bg-slate-50 dark:bg-slate-900">
      {/* Mobile menu overlay */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed lg:static inset-y-0 left-0 z-50 flex h-screen flex-col border-r bg-white dark:bg-slate-800 shadow-lg lg:shadow-none transition-all duration-300 ease-in-out',
          collapsed ? 'w-20' : 'w-72',
          mobileMenuOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'
        )}
      >
        {/* Logo section */}
        <div className="flex h-16 items-center justify-between border-b border-slate-200 dark:border-slate-700 px-4">
          <Link href="/dashboard" className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 shadow-lg shadow-indigo-500/25">
              <Building2 className="h-5 w-5 text-white" />
            </div>
            {!collapsed && (
              <div className="flex flex-col">
                <span className="text-lg font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
                  FEC Admin
                </span>
                <span className="text-xs text-slate-500 dark:text-slate-400">Management Portal</span>
              </div>
            )}
          </Link>

          {/* Collapse button - desktop only */}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="hidden lg:flex h-8 w-8 items-center justify-center rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
          >
            {collapsed ? (
              <ChevronRight className="h-4 w-4 text-slate-600 dark:text-slate-400" />
            ) : (
              <ChevronLeft className="h-4 w-4 text-slate-600 dark:text-slate-400" />
            )}
          </button>

          {/* Close button - mobile only */}
          <button
            onClick={() => setMobileMenuOpen(false)}
            className="lg:hidden h-8 w-8 flex items-center justify-center rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700"
          >
            <X className="h-5 w-5 text-slate-600 dark:text-slate-400" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto p-3 space-y-1">
          {navigation.map((item) => {
            const isActive = pathname === item.href || pathname.startsWith(item.href + '/');
            return (
              <Link
                key={item.name}
                href={item.href}
                onClick={() => setMobileMenuOpen(false)}
                className={cn(
                  'group flex items-center rounded-xl px-3 py-2.5 text-sm font-medium transition-all duration-200',
                  isActive
                    ? 'bg-gradient-to-r from-indigo-500 to-purple-600 text-white shadow-lg shadow-indigo-500/25'
                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700/50 hover:text-slate-900 dark:hover:text-white',
                  collapsed ? 'justify-center' : 'gap-3'
                )}
                title={collapsed ? item.name : undefined}
              >
                <item.icon className={cn(
                  'h-5 w-5 flex-shrink-0 transition-transform group-hover:scale-110',
                  isActive && 'drop-shadow-lg'
                )} />
                {!collapsed && (
                  <div className="flex flex-col">
                    <span>{item.name}</span>
                    <span className={cn(
                      'text-xs',
                      isActive ? 'text-white/70' : 'text-slate-400 dark:text-slate-500'
                    )}>
                      {item.description}
                    </span>
                  </div>
                )}
              </Link>
            );
          })}
        </nav>

        {/* Bottom section */}
        <div className="border-t border-slate-200 dark:border-slate-700 p-3 space-y-2">
          {/* Help button */}
          <button
            className={cn(
              'flex w-full items-center rounded-xl px-3 py-2.5 text-sm font-medium text-slate-600 dark:text-slate-400 transition-colors hover:bg-slate-100 dark:hover:bg-slate-700/50',
              collapsed ? 'justify-center' : 'gap-3'
            )}
          >
            <HelpCircle className="h-5 w-5 flex-shrink-0" />
            {!collapsed && <span>Help & Support</span>}
          </button>

          {/* Logout button */}
          <button
            onClick={handleLogout}
            className={cn(
              'flex w-full items-center rounded-xl px-3 py-2.5 text-sm font-medium text-red-600 dark:text-red-400 transition-colors hover:bg-red-50 dark:hover:bg-red-900/20',
              collapsed ? 'justify-center' : 'gap-3'
            )}
          >
            <LogOut className="h-5 w-5 flex-shrink-0" />
            {!collapsed && <span>Sign Out</span>}
          </button>
        </div>
      </aside>

      {/* Main content area */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Top header */}
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-slate-200 dark:border-slate-700 bg-white/80 dark:bg-slate-800/80 backdrop-blur-lg px-4 lg:px-6">
          {/* Left side */}
          <div className="flex items-center gap-4">
            {/* Mobile menu button */}
            <button
              onClick={() => setMobileMenuOpen(true)}
              className="lg:hidden h-10 w-10 flex items-center justify-center rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700"
            >
              <Menu className="h-5 w-5 text-slate-600 dark:text-slate-400" />
            </button>

            {/* Page title */}
            <div>
              <h1 className="text-xl font-bold text-slate-900 dark:text-white">
                {currentPage}
              </h1>
              <p className="text-sm text-slate-500 dark:text-slate-400 hidden sm:block">
                {navigation.find((n) => pathname.startsWith(n.href))?.description}
              </p>
            </div>
          </div>

          {/* Right side */}
          <div className="flex items-center gap-2">
            {/* Search button */}
            <button className="h-10 w-10 flex items-center justify-center rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors">
              <Search className="h-5 w-5 text-slate-600 dark:text-slate-400" />
            </button>

            {/* Theme toggle */}
            <button
              onClick={() => setDarkMode(!darkMode)}
              className="h-10 w-10 flex items-center justify-center rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
            >
              {darkMode ? (
                <Sun className="h-5 w-5 text-slate-600 dark:text-slate-400" />
              ) : (
                <Moon className="h-5 w-5 text-slate-600 dark:text-slate-400" />
              )}
            </button>

            {/* Notifications */}
            <div className="relative">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setShowNotifications(!showNotifications);
                  setShowUserMenu(false);
                }}
                className="relative h-10 w-10 flex items-center justify-center rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
              >
                <Bell className="h-5 w-5 text-slate-600 dark:text-slate-400" />
                {notifications.some(n => !n.read) && (
                  <span className="absolute top-2 right-2 h-2 w-2 rounded-full bg-red-500 ring-2 ring-white dark:ring-slate-800" />
                )}
              </button>

              {/* Notifications dropdown */}
              {showNotifications && (
                <div
                  onClick={(e) => e.stopPropagation()}
                  className="absolute right-0 mt-2 w-80 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-xl"
                >
                  <div className="p-4 border-b border-slate-200 dark:border-slate-700">
                    <h3 className="font-semibold text-slate-900 dark:text-white">Notifications</h3>
                  </div>
                  <div className="max-h-96 overflow-y-auto">
                    {notifications.map((notification) => (
                      <div
                        key={notification.id}
                        className={cn(
                          'p-4 border-b border-slate-100 dark:border-slate-700 last:border-0 hover:bg-slate-50 dark:hover:bg-slate-700/50 cursor-pointer',
                          !notification.read && 'bg-indigo-50 dark:bg-indigo-900/20'
                        )}
                      >
                        <p className="font-medium text-sm text-slate-900 dark:text-white">
                          {notification.title}
                        </p>
                        <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                          {notification.message}
                        </p>
                        <p className="text-xs text-slate-400 dark:text-slate-500 mt-2">
                          {notification.time}
                        </p>
                      </div>
                    ))}
                  </div>
                  <div className="p-3 border-t border-slate-200 dark:border-slate-700">
                    <button className="w-full text-center text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:text-indigo-700">
                      View all notifications
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* User menu */}
            <div className="relative">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  setShowUserMenu(!showUserMenu);
                  setShowNotifications(false);
                }}
                className="flex items-center gap-3 rounded-lg pl-2 pr-3 py-1.5 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
              >
                <div className="h-8 w-8 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-medium text-sm shadow-lg shadow-indigo-500/25">
                  {userInitials}
                </div>
                <div className="hidden sm:block text-left">
                  <p className="text-sm font-medium text-slate-900 dark:text-white">
                    {userDisplayName}
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">
                    Administrator
                  </p>
                </div>
                <ChevronDown className="h-4 w-4 text-slate-400 hidden sm:block" />
              </button>

              {/* User dropdown */}
              {showUserMenu && (
                <div
                  onClick={(e) => e.stopPropagation()}
                  className="absolute right-0 mt-2 w-56 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-xl"
                >
                  <div className="p-4 border-b border-slate-200 dark:border-slate-700">
                    <p className="font-medium text-slate-900 dark:text-white">{userDisplayName}</p>
                    <p className="text-sm text-slate-500 dark:text-slate-400">{user?.email}</p>
                  </div>
                  <div className="p-2">
                    <Link
                      href="/settings"
                      className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700"
                    >
                      <User className="h-4 w-4" />
                      Profile Settings
                    </Link>
                    <button
                      onClick={handleLogout}
                      className="w-full flex items-center gap-3 px-3 py-2 rounded-lg text-sm text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20"
                    >
                      <LogOut className="h-4 w-4" />
                      Sign Out
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* Page content */}
        <div className="flex-1 overflow-y-auto">
          <div className="p-4 lg:p-6">
            {children}
          </div>
        </div>
      </main>
    </div>
  );
}
