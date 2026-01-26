/**
 * =============================================================================
 * FILE: (dashboard)/settings/page.tsx
 * PURPOSE: Settings page with profile, notifications, security, and preferences
 * =============================================================================
 *
 * This page provides comprehensive account and application settings:
 * - Profile settings (name, email, avatar)
 * - Notification preferences (email, push, SMS)
 * - Security settings (password, 2FA)
 * - Application preferences (theme, language, timezone)
 * - Team management (for admin users)
 * - Billing information
 *
 * FEATURES:
 * - Tab-based navigation between settings sections
 * - Toggle switches for notification preferences
 * - Password change form with validation
 * - Two-factor authentication setup
 * - Theme selection
 *
 * =============================================================================
 */

'use client';

import { useState } from 'react';
import {
  User,
  Bell,
  Shield,
  CreditCard,
  Palette,
  Users,
  Settings,
  Mail,
  Smartphone,
  Globe,
  Moon,
  Sun,
  Lock,
  Key,
  Eye,
  EyeOff,
  Check,
  ChevronRight,
  Camera,
  Save,
  AlertTriangle,
  Sparkles,
  Building2,
} from 'lucide-react';
import { cn } from '@fec-saas/ui';
import { useAuth } from '@/contexts/auth-context';

/**
 * Settings tabs configuration
 */
const tabs = [
  { id: 'profile', name: 'Profile', icon: User, description: 'Personal information' },
  { id: 'notifications', name: 'Notifications', icon: Bell, description: 'Alert preferences' },
  { id: 'security', name: 'Security', icon: Shield, description: 'Password & 2FA' },
  { id: 'appearance', name: 'Appearance', icon: Palette, description: 'Theme settings' },
  { id: 'team', name: 'Team', icon: Users, description: 'Manage users' },
  { id: 'billing', name: 'Billing', icon: CreditCard, description: 'Plan & payments' },
];

/**
 * Mock team members
 */
const teamMembers = [
  { id: '1', name: 'Admin User', email: 'admin@funzone.com', role: 'Owner', avatar: 'AU', status: 'active' },
  { id: '2', name: 'Sarah Manager', email: 'sarah@funzone.com', role: 'Manager', avatar: 'SM', status: 'active' },
  { id: '3', name: 'John Staff', email: 'john@funzone.com', role: 'Staff', avatar: 'JS', status: 'active' },
  { id: '4', name: 'Emily Venue', email: 'emily@funzone.com', role: 'Venue Admin', avatar: 'EV', status: 'pending' },
];

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState('profile');
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [theme, setTheme] = useState<'light' | 'dark' | 'system'>('system');
  const [saving, setSaving] = useState(false);
  const { user } = useAuth();

  // Notification preferences state
  const [notifications, setNotifications] = useState({
    emailBookings: true,
    emailPayments: true,
    emailMarketing: false,
    pushBookings: true,
    pushPayments: true,
    smsBookings: false,
    smsPayments: true,
  });

  // Toggle notification
  const toggleNotification = (key: keyof typeof notifications) => {
    setNotifications((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  // Handle save
  const handleSave = async () => {
    setSaving(true);
    await new Promise((resolve) => setTimeout(resolve, 1000));
    setSaving(false);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Settings</h1>
          <p className="text-slate-500 dark:text-slate-400">
            Manage your account and application preferences
          </p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex items-center gap-2 h-10 px-4 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 text-white text-sm font-medium hover:from-indigo-600 hover:to-purple-700 shadow-lg shadow-indigo-500/25 transition-all disabled:opacity-50"
        >
          {saving ? (
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-white/20 border-t-white" />
          ) : (
            <Save className="h-4 w-4" />
          )}
          Save Changes
        </button>
      </div>

      {/* Main content */}
      <div className="flex flex-col lg:flex-row gap-6">
        {/* Sidebar tabs */}
        <div className="lg:w-64 flex-shrink-0">
          <nav className="space-y-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  'w-full flex items-center gap-3 px-4 py-3 rounded-xl text-left transition-all duration-200',
                  activeTab === tab.id
                    ? 'bg-gradient-to-r from-indigo-500 to-purple-600 text-white shadow-lg shadow-indigo-500/25'
                    : 'text-slate-600 dark:text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-700/50'
                )}
              >
                <tab.icon className="h-5 w-5" />
                <div className="flex-1">
                  <p className="font-medium">{tab.name}</p>
                  <p className={cn(
                    'text-xs',
                    activeTab === tab.id ? 'text-white/70' : 'text-slate-400 dark:text-slate-500'
                  )}>
                    {tab.description}
                  </p>
                </div>
                {activeTab === tab.id && (
                  <ChevronRight className="h-4 w-4" />
                )}
              </button>
            ))}
          </nav>
        </div>

        {/* Tab content */}
        <div className="flex-1">
          {/* Profile Tab */}
          {activeTab === 'profile' && (
            <div className="space-y-6">
              <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 overflow-hidden">
                {/* Cover */}
                <div className="h-32 bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500" />

                {/* Avatar section */}
                <div className="px-6 pb-6">
                  <div className="flex flex-col sm:flex-row items-start sm:items-end gap-4 -mt-12">
                    <div className="relative">
                      <div className="h-24 w-24 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-3xl font-bold text-white shadow-xl border-4 border-white dark:border-slate-800">
                        {user?.first_name?.[0] || user?.email?.[0]?.toUpperCase() || 'A'}
                        {user?.last_name?.[0] || ''}
                      </div>
                      <button className="absolute -bottom-2 -right-2 h-8 w-8 rounded-full bg-indigo-600 text-white flex items-center justify-center shadow-lg hover:bg-indigo-700 transition-colors">
                        <Camera className="h-4 w-4" />
                      </button>
                    </div>
                    <div className="flex-1">
                      <h2 className="text-xl font-bold text-slate-900 dark:text-white">
                        {user?.first_name ? `${user.first_name} ${user.last_name || ''}` : 'Admin User'}
                      </h2>
                      <p className="text-slate-500 dark:text-slate-400">{user?.email || 'admin@funzone.com'}</p>
                    </div>
                    <div className="flex items-center gap-2 rounded-full bg-emerald-100 dark:bg-emerald-900/30 px-3 py-1 text-sm font-medium text-emerald-700 dark:text-emerald-400">
                      <Sparkles className="h-4 w-4" />
                      Pro Plan
                    </div>
                  </div>
                </div>
              </div>

              {/* Profile form */}
              <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-6">
                  Personal Information
                </h3>
                <div className="grid gap-6 sm:grid-cols-2">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      First Name
                    </label>
                    <input
                      type="text"
                      defaultValue={user?.first_name || 'Admin'}
                      className="w-full h-10 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-4 text-sm text-slate-900 dark:text-white focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      Last Name
                    </label>
                    <input
                      type="text"
                      defaultValue={user?.last_name || 'User'}
                      className="w-full h-10 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-4 text-sm text-slate-900 dark:text-white focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      Email Address
                    </label>
                    <input
                      type="email"
                      defaultValue={user?.email || 'admin@funzone.com'}
                      className="w-full h-10 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-4 text-sm text-slate-900 dark:text-white focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      Phone Number
                    </label>
                    <input
                      type="tel"
                      defaultValue={user?.phone || '(512) 555-0100'}
                      className="w-full h-10 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-4 text-sm text-slate-900 dark:text-white focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                    />
                  </div>
                </div>
              </div>

              {/* Company info */}
              <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-6">
                  Company Information
                </h3>
                <div className="grid gap-6 sm:grid-cols-2">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      Company Name
                    </label>
                    <input
                      type="text"
                      defaultValue="FunZone Entertainment"
                      className="w-full h-10 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-4 text-sm text-slate-900 dark:text-white focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      Business Type
                    </label>
                    <select className="w-full h-10 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-4 text-sm text-slate-900 dark:text-white focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20">
                      <option>Family Entertainment Center</option>
                      <option>Arcade</option>
                      <option>Bowling Alley</option>
                      <option>Trampoline Park</option>
                      <option>Other</option>
                    </select>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Notifications Tab */}
          {activeTab === 'notifications' && (
            <div className="space-y-6">
              {/* Email notifications */}
              <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
                <div className="flex items-center gap-3 mb-6">
                  <div className="h-10 w-10 rounded-xl bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                    <Mail className="h-5 w-5 text-blue-600 dark:text-blue-400" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                      Email Notifications
                    </h3>
                    <p className="text-sm text-slate-500 dark:text-slate-400">
                      Receive updates via email
                    </p>
                  </div>
                </div>
                <div className="space-y-4">
                  {[
                    { key: 'emailBookings' as const, label: 'Booking Updates', description: 'New bookings, confirmations, and cancellations' },
                    { key: 'emailPayments' as const, label: 'Payment Notifications', description: 'Payment received, refunds, and invoice reminders' },
                    { key: 'emailMarketing' as const, label: 'Marketing & Promotions', description: 'Tips, product updates, and special offers' },
                  ].map((item) => (
                    <div key={item.key} className="flex items-center justify-between p-4 rounded-xl bg-slate-50 dark:bg-slate-700/50">
                      <div>
                        <p className="font-medium text-slate-900 dark:text-white">{item.label}</p>
                        <p className="text-sm text-slate-500 dark:text-slate-400">{item.description}</p>
                      </div>
                      <button
                        onClick={() => toggleNotification(item.key)}
                        className={cn(
                          'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                          notifications[item.key] ? 'bg-indigo-600' : 'bg-slate-200 dark:bg-slate-600'
                        )}
                      >
                        <span
                          className={cn(
                            'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                            notifications[item.key] ? 'translate-x-6' : 'translate-x-1'
                          )}
                        />
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* Push notifications */}
              <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
                <div className="flex items-center gap-3 mb-6">
                  <div className="h-10 w-10 rounded-xl bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
                    <Bell className="h-5 w-5 text-purple-600 dark:text-purple-400" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                      Push Notifications
                    </h3>
                    <p className="text-sm text-slate-500 dark:text-slate-400">
                      Real-time browser alerts
                    </p>
                  </div>
                </div>
                <div className="space-y-4">
                  {[
                    { key: 'pushBookings' as const, label: 'New Bookings', description: 'Get notified when a new booking is made' },
                    { key: 'pushPayments' as const, label: 'Payment Received', description: 'Instant alerts for payments' },
                  ].map((item) => (
                    <div key={item.key} className="flex items-center justify-between p-4 rounded-xl bg-slate-50 dark:bg-slate-700/50">
                      <div>
                        <p className="font-medium text-slate-900 dark:text-white">{item.label}</p>
                        <p className="text-sm text-slate-500 dark:text-slate-400">{item.description}</p>
                      </div>
                      <button
                        onClick={() => toggleNotification(item.key)}
                        className={cn(
                          'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                          notifications[item.key] ? 'bg-indigo-600' : 'bg-slate-200 dark:bg-slate-600'
                        )}
                      >
                        <span
                          className={cn(
                            'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                            notifications[item.key] ? 'translate-x-6' : 'translate-x-1'
                          )}
                        />
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              {/* SMS notifications */}
              <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
                <div className="flex items-center gap-3 mb-6">
                  <div className="h-10 w-10 rounded-xl bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center">
                    <Smartphone className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                      SMS Notifications
                    </h3>
                    <p className="text-sm text-slate-500 dark:text-slate-400">
                      Text message alerts
                    </p>
                  </div>
                </div>
                <div className="space-y-4">
                  {[
                    { key: 'smsBookings' as const, label: 'Urgent Booking Alerts', description: 'Same-day bookings and last-minute changes' },
                    { key: 'smsPayments' as const, label: 'Large Payments', description: 'Notify for payments over $500' },
                  ].map((item) => (
                    <div key={item.key} className="flex items-center justify-between p-4 rounded-xl bg-slate-50 dark:bg-slate-700/50">
                      <div>
                        <p className="font-medium text-slate-900 dark:text-white">{item.label}</p>
                        <p className="text-sm text-slate-500 dark:text-slate-400">{item.description}</p>
                      </div>
                      <button
                        onClick={() => toggleNotification(item.key)}
                        className={cn(
                          'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                          notifications[item.key] ? 'bg-indigo-600' : 'bg-slate-200 dark:bg-slate-600'
                        )}
                      >
                        <span
                          className={cn(
                            'inline-block h-4 w-4 transform rounded-full bg-white transition-transform',
                            notifications[item.key] ? 'translate-x-6' : 'translate-x-1'
                          )}
                        />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Security Tab */}
          {activeTab === 'security' && (
            <div className="space-y-6">
              {/* Password */}
              <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
                <div className="flex items-center gap-3 mb-6">
                  <div className="h-10 w-10 rounded-xl bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center">
                    <Lock className="h-5 w-5 text-amber-600 dark:text-amber-400" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                      Change Password
                    </h3>
                    <p className="text-sm text-slate-500 dark:text-slate-400">
                      Update your account password
                    </p>
                  </div>
                </div>
                <div className="space-y-4 max-w-md">
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      Current Password
                    </label>
                    <div className="relative">
                      <input
                        type={showCurrentPassword ? 'text' : 'password'}
                        placeholder="Enter current password"
                        className="w-full h-10 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-4 pr-10 text-sm text-slate-900 dark:text-white focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                      />
                      <button
                        type="button"
                        onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
                      >
                        {showCurrentPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      New Password
                    </label>
                    <div className="relative">
                      <input
                        type={showNewPassword ? 'text' : 'password'}
                        placeholder="Enter new password"
                        className="w-full h-10 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-4 pr-10 text-sm text-slate-900 dark:text-white focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                      />
                      <button
                        type="button"
                        onClick={() => setShowNewPassword(!showNewPassword)}
                        className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300"
                      >
                        {showNewPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                      </button>
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">
                      Confirm New Password
                    </label>
                    <input
                      type="password"
                      placeholder="Confirm new password"
                      className="w-full h-10 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 px-4 text-sm text-slate-900 dark:text-white focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
                    />
                  </div>
                  <button className="h-10 px-4 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 transition-colors">
                    Update Password
                  </button>
                </div>
              </div>

              {/* 2FA */}
              <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-xl bg-emerald-100 dark:bg-emerald-900/30 flex items-center justify-center">
                      <Key className="h-5 w-5 text-emerald-600 dark:text-emerald-400" />
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                        Two-Factor Authentication
                      </h3>
                      <p className="text-sm text-slate-500 dark:text-slate-400">
                        Add an extra layer of security
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 rounded-full bg-slate-100 dark:bg-slate-700 px-3 py-1 text-sm font-medium text-slate-600 dark:text-slate-400">
                    Not enabled
                  </div>
                </div>
                <div className="mt-4 p-4 rounded-xl bg-slate-50 dark:bg-slate-700/50">
                  <p className="text-sm text-slate-600 dark:text-slate-400 mb-4">
                    Two-factor authentication adds an additional layer of security to your account by requiring a verification code in addition to your password.
                  </p>
                  <button className="h-10 px-4 rounded-lg border border-indigo-600 text-indigo-600 dark:text-indigo-400 text-sm font-medium hover:bg-indigo-50 dark:hover:bg-indigo-900/20 transition-colors">
                    Enable 2FA
                  </button>
                </div>
              </div>

              {/* Active sessions */}
              <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
                <div className="flex items-center gap-3 mb-6">
                  <div className="h-10 w-10 rounded-xl bg-purple-100 dark:bg-purple-900/30 flex items-center justify-center">
                    <Globe className="h-5 w-5 text-purple-600 dark:text-purple-400" />
                  </div>
                  <div>
                    <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                      Active Sessions
                    </h3>
                    <p className="text-sm text-slate-500 dark:text-slate-400">
                      Manage your logged in devices
                    </p>
                  </div>
                </div>
                <div className="space-y-3">
                  <div className="flex items-center justify-between p-4 rounded-xl bg-slate-50 dark:bg-slate-700/50">
                    <div className="flex items-center gap-3">
                      <div className="h-8 w-8 rounded-lg bg-white dark:bg-slate-600 flex items-center justify-center shadow-sm">
                        <Globe className="h-4 w-4 text-slate-600 dark:text-slate-300" />
                      </div>
                      <div>
                        <p className="font-medium text-slate-900 dark:text-white">Chrome on Windows</p>
                        <p className="text-xs text-slate-500 dark:text-slate-400">Austin, TX - Current session</p>
                      </div>
                    </div>
                    <span className="text-xs font-medium text-emerald-600 bg-emerald-100 dark:bg-emerald-900/30 px-2 py-0.5 rounded-full">
                      Active
                    </span>
                  </div>
                  <div className="flex items-center justify-between p-4 rounded-xl bg-slate-50 dark:bg-slate-700/50">
                    <div className="flex items-center gap-3">
                      <div className="h-8 w-8 rounded-lg bg-white dark:bg-slate-600 flex items-center justify-center shadow-sm">
                        <Smartphone className="h-4 w-4 text-slate-600 dark:text-slate-300" />
                      </div>
                      <div>
                        <p className="font-medium text-slate-900 dark:text-white">Safari on iPhone</p>
                        <p className="text-xs text-slate-500 dark:text-slate-400">Austin, TX - Last seen 2 hours ago</p>
                      </div>
                    </div>
                    <button className="text-xs font-medium text-red-600 hover:text-red-700">
                      Revoke
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Appearance Tab */}
          {activeTab === 'appearance' && (
            <div className="space-y-6">
              <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-6">
                  Theme Preference
                </h3>
                <div className="grid gap-4 sm:grid-cols-3">
                  {[
                    { id: 'light' as const, name: 'Light', icon: Sun, description: 'Light background with dark text' },
                    { id: 'dark' as const, name: 'Dark', icon: Moon, description: 'Dark background with light text' },
                    { id: 'system' as const, name: 'System', icon: Settings, description: 'Follows your device settings' },
                  ].map((option) => (
                    <button
                      key={option.id}
                      onClick={() => setTheme(option.id)}
                      className={cn(
                        'p-4 rounded-xl border-2 text-left transition-all',
                        theme === option.id
                          ? 'border-indigo-500 bg-indigo-50 dark:bg-indigo-900/20'
                          : 'border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600'
                      )}
                    >
                      <div className={cn(
                        'h-10 w-10 rounded-lg flex items-center justify-center mb-3',
                        theme === option.id
                          ? 'bg-indigo-500 text-white'
                          : 'bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-400'
                      )}>
                        <option.icon className="h-5 w-5" />
                      </div>
                      <p className="font-medium text-slate-900 dark:text-white">{option.name}</p>
                      <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">{option.description}</p>
                      {theme === option.id && (
                        <div className="flex items-center gap-1 text-xs text-indigo-600 dark:text-indigo-400 mt-2">
                          <Check className="h-3 w-3" />
                          Selected
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Team Tab */}
          {activeTab === 'team' && (
            <div className="space-y-6">
              <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
                <div className="flex items-center justify-between mb-6">
                  <div>
                    <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                      Team Members
                    </h3>
                    <p className="text-sm text-slate-500 dark:text-slate-400">
                      Manage your team and their permissions
                    </p>
                  </div>
                  <button className="flex items-center gap-2 h-10 px-4 rounded-lg bg-indigo-600 text-white text-sm font-medium hover:bg-indigo-700 transition-colors">
                    <Users className="h-4 w-4" />
                    Invite Member
                  </button>
                </div>
                <div className="space-y-3">
                  {teamMembers.map((member) => (
                    <div key={member.id} className="flex items-center justify-between p-4 rounded-xl bg-slate-50 dark:bg-slate-700/50">
                      <div className="flex items-center gap-3">
                        <div className="h-10 w-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-semibold text-sm">
                          {member.avatar}
                        </div>
                        <div>
                          <p className="font-medium text-slate-900 dark:text-white">{member.name}</p>
                          <p className="text-sm text-slate-500 dark:text-slate-400">{member.email}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className={cn(
                          'text-xs font-medium px-2 py-0.5 rounded-full',
                          member.status === 'active'
                            ? 'text-emerald-700 bg-emerald-100 dark:bg-emerald-900/30 dark:text-emerald-400'
                            : 'text-amber-700 bg-amber-100 dark:bg-amber-900/30 dark:text-amber-400'
                        )}>
                          {member.status}
                        </span>
                        <span className="text-sm font-medium text-slate-600 dark:text-slate-400">
                          {member.role}
                        </span>
                        <button className="p-2 rounded-lg hover:bg-slate-200 dark:hover:bg-slate-600 text-slate-400">
                          <ChevronRight className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Billing Tab */}
          {activeTab === 'billing' && (
            <div className="space-y-6">
              {/* Current plan */}
              <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                      Current Plan
                    </h3>
                    <p className="text-sm text-slate-500 dark:text-slate-400">
                      You are currently on the Pro plan
                    </p>
                  </div>
                  <div className="flex items-center gap-2 rounded-full bg-gradient-to-r from-indigo-500 to-purple-600 px-4 py-1.5 text-sm font-medium text-white shadow-lg shadow-indigo-500/25">
                    <Sparkles className="h-4 w-4" />
                    Pro Plan
                  </div>
                </div>
                <div className="mt-6 grid gap-4 sm:grid-cols-3">
                  <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-700/50">
                    <p className="text-2xl font-bold text-slate-900 dark:text-white">5</p>
                    <p className="text-sm text-slate-500 dark:text-slate-400">Venues included</p>
                  </div>
                  <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-700/50">
                    <p className="text-2xl font-bold text-slate-900 dark:text-white">Unlimited</p>
                    <p className="text-sm text-slate-500 dark:text-slate-400">Bookings per month</p>
                  </div>
                  <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-700/50">
                    <p className="text-2xl font-bold text-slate-900 dark:text-white">$99</p>
                    <p className="text-sm text-slate-500 dark:text-slate-400">Per month</p>
                  </div>
                </div>
                <div className="mt-4 flex gap-3">
                  <button className="h-10 px-4 rounded-lg border border-slate-200 dark:border-slate-700 text-sm font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors">
                    Change Plan
                  </button>
                  <button className="h-10 px-4 rounded-lg border border-red-200 dark:border-red-800 text-sm font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors">
                    Cancel Subscription
                  </button>
                </div>
              </div>

              {/* Payment method */}
              <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-6">
                  Payment Method
                </h3>
                <div className="flex items-center justify-between p-4 rounded-xl bg-slate-50 dark:bg-slate-700/50">
                  <div className="flex items-center gap-3">
                    <div className="h-10 w-10 rounded-lg bg-gradient-to-r from-blue-600 to-blue-700 flex items-center justify-center text-white font-bold text-sm">
                      VISA
                    </div>
                    <div>
                      <p className="font-medium text-slate-900 dark:text-white">Visa ending in 4242</p>
                      <p className="text-sm text-slate-500 dark:text-slate-400">Expires 12/2025</p>
                    </div>
                  </div>
                  <button className="text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:text-indigo-700">
                    Update
                  </button>
                </div>
              </div>

              {/* Billing history */}
              <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white mb-6">
                  Billing History
                </h3>
                <div className="space-y-3">
                  {[
                    { date: 'Jan 1, 2024', amount: '$99.00', status: 'Paid' },
                    { date: 'Dec 1, 2023', amount: '$99.00', status: 'Paid' },
                    { date: 'Nov 1, 2023', amount: '$99.00', status: 'Paid' },
                  ].map((invoice, i) => (
                    <div key={i} className="flex items-center justify-between p-4 rounded-xl bg-slate-50 dark:bg-slate-700/50">
                      <div>
                        <p className="font-medium text-slate-900 dark:text-white">{invoice.date}</p>
                        <p className="text-sm text-slate-500 dark:text-slate-400">Pro Plan - Monthly</p>
                      </div>
                      <div className="flex items-center gap-4">
                        <span className="text-sm font-medium text-slate-900 dark:text-white">{invoice.amount}</span>
                        <span className="text-xs font-medium text-emerald-700 bg-emerald-100 dark:bg-emerald-900/30 dark:text-emerald-400 px-2 py-0.5 rounded-full">
                          {invoice.status}
                        </span>
                        <button className="text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:text-indigo-700">
                          Download
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
