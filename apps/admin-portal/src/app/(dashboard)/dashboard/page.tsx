/**
 * =============================================================================
 * FILE: (dashboard)/dashboard/page.tsx
 * PURPOSE: Main dashboard page with analytics and key metrics
 * =============================================================================
 *
 * This is the primary dashboard view that displays:
 * - Key performance indicators (KPIs) with trend indicators
 * - Revenue charts and analytics
 * - Recent booking activity
 * - Top performing venues
 * - Quick action buttons
 * - Real-time statistics
 *
 * LAYOUT:
 * - 4-column stat cards at top
 * - 2-column main content (bookings + venues)
 * - Full-width quick actions section
 * - Revenue trend chart (placeholder for future implementation)
 *
 * =============================================================================
 */

'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  Users,
  DollarSign,
  PartyPopper,
  TrendingUp,
  TrendingDown,
  Building2,
  Calendar,
  ArrowUpRight,
  ArrowRight,
  Clock,
  MapPin,
  Star,
  Zap,
  Target,
  Gift,
  Sparkles,
  ChevronRight,
  MoreHorizontal,
} from 'lucide-react';
import { cn } from '@fec-saas/ui';

/**
 * Dashboard statistics data
 */
const stats = [
  {
    title: 'Total Revenue',
    value: '$124,563',
    change: '+12.5%',
    changeType: 'positive' as const,
    icon: DollarSign,
    description: 'vs last month',
    color: 'emerald',
  },
  {
    title: 'Active Venues',
    value: '12',
    change: '+2',
    changeType: 'positive' as const,
    icon: Building2,
    description: 'new this quarter',
    color: 'blue',
  },
  {
    title: 'Party Bookings',
    value: '248',
    change: '+8.2%',
    changeType: 'positive' as const,
    icon: PartyPopper,
    description: 'vs last month',
    color: 'purple',
  },
  {
    title: 'Total Customers',
    value: '15,234',
    change: '+5.4%',
    changeType: 'positive' as const,
    icon: Users,
    description: 'vs last month',
    color: 'amber',
  },
];

/**
 * Recent bookings data
 */
const recentBookings = [
  {
    id: 'PB-001',
    customerName: 'Johnson Family',
    package: 'Ultimate Birthday Bash',
    venue: 'FunZone Downtown',
    date: 'Jan 25, 2024',
    time: '2:00 PM',
    status: 'confirmed',
    amount: 450,
    avatar: 'JF',
  },
  {
    id: 'PB-002',
    customerName: 'Smith Party',
    package: 'Classic Fun Package',
    venue: 'Adventure Park',
    date: 'Jan 26, 2024',
    time: '11:00 AM',
    status: 'pending',
    amount: 275,
    avatar: 'SP',
  },
  {
    id: 'PB-003',
    customerName: 'Williams Event',
    package: 'VIP Experience',
    venue: 'FunZone Mall',
    date: 'Jan 27, 2024',
    time: '3:00 PM',
    status: 'confirmed',
    amount: 650,
    avatar: 'WE',
  },
  {
    id: 'PB-004',
    customerName: 'Brown Celebration',
    package: 'Classic Fun Package',
    venue: 'FunZone Downtown',
    date: 'Jan 28, 2024',
    time: '10:00 AM',
    status: 'pending',
    amount: 275,
    avatar: 'BC',
  },
  {
    id: 'PB-005',
    customerName: 'Davis Birthday',
    package: 'Ultimate Birthday Bash',
    venue: 'Adventure Park',
    date: 'Jan 29, 2024',
    time: '1:00 PM',
    status: 'confirmed',
    amount: 450,
    avatar: 'DB',
  },
];

/**
 * Top venues data
 */
const topVenues = [
  {
    id: '1',
    name: 'FunZone Downtown',
    location: 'Austin, TX',
    revenue: 45230,
    bookings: 89,
    growth: 15.2,
    rating: 4.8,
    image: '🎮',
  },
  {
    id: '2',
    name: 'Adventure Park',
    location: 'Dallas, TX',
    revenue: 38750,
    bookings: 72,
    growth: 8.5,
    rating: 4.6,
    image: '🎢',
  },
  {
    id: '3',
    name: 'FunZone Mall',
    location: 'Houston, TX',
    revenue: 31200,
    bookings: 58,
    growth: 12.1,
    rating: 4.7,
    image: '🎯',
  },
  {
    id: '4',
    name: 'Kids Paradise',
    location: 'San Antonio, TX',
    revenue: 28400,
    bookings: 52,
    growth: -2.3,
    rating: 4.4,
    image: '🎪',
  },
];

/**
 * Quick actions configuration
 */
const quickActions = [
  {
    name: 'New Party Booking',
    description: 'Create a new party reservation',
    icon: PartyPopper,
    href: '/parties/new',
    color: 'from-purple-500 to-pink-500',
  },
  {
    name: 'Add New Venue',
    description: 'Register a new location',
    icon: Building2,
    href: '/venues/new',
    color: 'from-blue-500 to-cyan-500',
  },
  {
    name: 'View Customers',
    description: 'Browse customer database',
    icon: Users,
    href: '/customers',
    color: 'from-amber-500 to-orange-500',
  },
  {
    name: 'Generate Report',
    description: 'Create analytics report',
    icon: TrendingUp,
    href: '/analytics',
    color: 'from-emerald-500 to-teal-500',
  },
];

/**
 * Status badge styles
 */
const statusStyles = {
  confirmed: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
  pending: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
  completed: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  cancelled: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
};

/**
 * Stat card color styles
 */
const statColors = {
  emerald: {
    bg: 'bg-emerald-50 dark:bg-emerald-900/20',
    icon: 'bg-emerald-500',
    text: 'text-emerald-600 dark:text-emerald-400',
  },
  blue: {
    bg: 'bg-blue-50 dark:bg-blue-900/20',
    icon: 'bg-blue-500',
    text: 'text-blue-600 dark:text-blue-400',
  },
  purple: {
    bg: 'bg-purple-50 dark:bg-purple-900/20',
    icon: 'bg-purple-500',
    text: 'text-purple-600 dark:text-purple-400',
  },
  amber: {
    bg: 'bg-amber-50 dark:bg-amber-900/20',
    icon: 'bg-amber-500',
    text: 'text-amber-600 dark:text-amber-400',
  },
};

export default function DashboardPage() {
  const [selectedPeriod, setSelectedPeriod] = useState('month');

  return (
    <div className="space-y-6">
      {/* Welcome banner */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-r from-indigo-500 via-purple-500 to-pink-500 p-6 text-white shadow-xl">
        <div className="absolute inset-0 bg-black/10" />
        <div className="absolute -right-10 -top-10 h-40 w-40 rounded-full bg-white/10 blur-2xl" />
        <div className="absolute -bottom-10 -left-10 h-40 w-40 rounded-full bg-white/10 blur-2xl" />
        <div className="relative">
          <div className="flex items-start justify-between">
            <div>
              <h2 className="text-2xl font-bold">Welcome back!</h2>
              <p className="mt-1 text-white/80">
                Here&apos;s what&apos;s happening with your entertainment centers today.
              </p>
            </div>
            <div className="hidden sm:flex items-center gap-2 rounded-lg bg-white/20 px-3 py-1.5 backdrop-blur-sm">
              <Sparkles className="h-4 w-4" />
              <span className="text-sm font-medium">Pro Plan</span>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-4 text-sm">
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
              <span>All systems operational</span>
            </div>
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4" />
              <span>Last updated: Just now</span>
            </div>
          </div>
        </div>
      </div>

      {/* Period selector */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Overview</h3>
        <div className="flex rounded-lg bg-slate-100 dark:bg-slate-800 p-1">
          {['day', 'week', 'month', 'year'].map((period) => (
            <button
              key={period}
              onClick={() => setSelectedPeriod(period)}
              className={cn(
                'px-3 py-1.5 text-sm font-medium rounded-md transition-all',
                selectedPeriod === period
                  ? 'bg-white dark:bg-slate-700 text-slate-900 dark:text-white shadow-sm'
                  : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white'
              )}
            >
              {period.charAt(0).toUpperCase() + period.slice(1)}
            </button>
          ))}
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {stats.map((stat) => {
          const colors = statColors[stat.color as keyof typeof statColors];
          return (
            <div
              key={stat.title}
              className="group relative overflow-hidden rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6 shadow-sm hover:shadow-lg transition-all duration-300"
            >
              <div className="flex items-start justify-between">
                <div className={cn('rounded-xl p-3', colors.bg)}>
                  <stat.icon className={cn('h-6 w-6 text-white', colors.icon)} style={{ color: 'white' }} />
                  <div className={cn('absolute inset-0 rounded-xl', colors.icon, 'opacity-100')} style={{ padding: '12px', width: '48px', height: '48px' }}>
                    <stat.icon className="h-6 w-6 text-white" />
                  </div>
                </div>
                <div className={cn(
                  'flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
                  stat.changeType === 'positive'
                    ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400'
                    : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                )}>
                  {stat.changeType === 'positive' ? (
                    <TrendingUp className="h-3 w-3" />
                  ) : (
                    <TrendingDown className="h-3 w-3" />
                  )}
                  {stat.change}
                </div>
              </div>
              <div className="mt-4">
                <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{stat.title}</p>
                <p className="mt-1 text-3xl font-bold text-slate-900 dark:text-white">{stat.value}</p>
                <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">{stat.description}</p>
              </div>
              {/* Hover gradient */}
              <div className={cn(
                'absolute inset-0 opacity-0 group-hover:opacity-5 transition-opacity bg-gradient-to-br',
                `from-${stat.color}-500 to-${stat.color}-600`
              )} />
            </div>
          );
        })}
      </div>

      {/* Main content grid */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Recent Bookings */}
        <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-sm">
          <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-700 p-6">
            <div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Recent Bookings</h3>
              <p className="text-sm text-slate-500 dark:text-slate-400">Latest party reservations</p>
            </div>
            <Link
              href="/parties"
              className="flex items-center gap-1 text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 transition-colors"
            >
              View all
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
          <div className="divide-y divide-slate-100 dark:divide-slate-700">
            {recentBookings.map((booking) => (
              <div
                key={booking.id}
                className="flex items-center gap-4 p-4 hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors cursor-pointer"
              >
                <div className="flex h-12 w-12 items-center justify-center rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 text-white font-semibold text-sm shadow-lg shadow-indigo-500/25">
                  {booking.avatar}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="font-medium text-slate-900 dark:text-white truncate">
                      {booking.customerName}
                    </p>
                    <span className={cn(
                      'inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium',
                      statusStyles[booking.status as keyof typeof statusStyles]
                    )}>
                      {booking.status}
                    </span>
                  </div>
                  <p className="text-sm text-slate-500 dark:text-slate-400 truncate">
                    {booking.package}
                  </p>
                  <div className="flex items-center gap-3 mt-1 text-xs text-slate-400 dark:text-slate-500">
                    <span className="flex items-center gap-1">
                      <MapPin className="h-3 w-3" />
                      {booking.venue}
                    </span>
                    <span className="flex items-center gap-1">
                      <Calendar className="h-3 w-3" />
                      {booking.date}
                    </span>
                  </div>
                </div>
                <div className="text-right">
                  <p className="font-semibold text-slate-900 dark:text-white">${booking.amount}</p>
                  <p className="text-xs text-slate-400 dark:text-slate-500">{booking.time}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Top Performing Venues */}
        <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-sm">
          <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-700 p-6">
            <div>
              <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Top Venues</h3>
              <p className="text-sm text-slate-500 dark:text-slate-400">Performance this month</p>
            </div>
            <Link
              href="/venues"
              className="flex items-center gap-1 text-sm font-medium text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 transition-colors"
            >
              View all
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
          <div className="divide-y divide-slate-100 dark:divide-slate-700">
            {topVenues.map((venue, index) => (
              <div
                key={venue.id}
                className="flex items-center gap-4 p-4 hover:bg-slate-50 dark:hover:bg-slate-700/50 transition-colors cursor-pointer"
              >
                <div className="flex items-center justify-center h-12 w-12 rounded-xl bg-slate-100 dark:bg-slate-700 text-2xl">
                  {venue.image}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="flex h-5 w-5 items-center justify-center rounded-full bg-slate-200 dark:bg-slate-600 text-xs font-bold text-slate-600 dark:text-slate-300">
                      {index + 1}
                    </span>
                    <p className="font-medium text-slate-900 dark:text-white truncate">
                      {venue.name}
                    </p>
                  </div>
                  <div className="flex items-center gap-3 mt-1">
                    <span className="flex items-center gap-1 text-xs text-slate-400 dark:text-slate-500">
                      <MapPin className="h-3 w-3" />
                      {venue.location}
                    </span>
                    <span className="flex items-center gap-1 text-xs text-amber-500">
                      <Star className="h-3 w-3 fill-current" />
                      {venue.rating}
                    </span>
                  </div>
                </div>
                <div className="text-right">
                  <p className="font-semibold text-slate-900 dark:text-white">
                    ${venue.revenue.toLocaleString()}
                  </p>
                  <div className={cn(
                    'flex items-center justify-end gap-1 text-xs',
                    venue.growth >= 0 ? 'text-emerald-600' : 'text-red-600'
                  )}>
                    {venue.growth >= 0 ? (
                      <TrendingUp className="h-3 w-3" />
                    ) : (
                      <TrendingDown className="h-3 w-3" />
                    )}
                    <span>{venue.growth >= 0 ? '+' : ''}{venue.growth}%</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Quick Actions */}
      <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-sm">
        <div className="border-b border-slate-200 dark:border-slate-700 p-6">
          <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Quick Actions</h3>
          <p className="text-sm text-slate-500 dark:text-slate-400">Frequently used operations</p>
        </div>
        <div className="grid gap-4 p-6 sm:grid-cols-2 lg:grid-cols-4">
          {quickActions.map((action) => (
            <Link
              key={action.name}
              href={action.href}
              className="group relative overflow-hidden rounded-xl border border-slate-200 dark:border-slate-700 p-5 hover:border-transparent hover:shadow-lg transition-all duration-300"
            >
              <div className={cn(
                'absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity bg-gradient-to-br',
                action.color
              )} />
              <div className="relative">
                <div className={cn(
                  'inline-flex items-center justify-center h-12 w-12 rounded-xl bg-gradient-to-br text-white shadow-lg transition-transform group-hover:scale-110',
                  action.color
                )}>
                  <action.icon className="h-6 w-6" />
                </div>
                <h4 className="mt-4 font-semibold text-slate-900 dark:text-white group-hover:text-white transition-colors">
                  {action.name}
                </h4>
                <p className="mt-1 text-sm text-slate-500 dark:text-slate-400 group-hover:text-white/80 transition-colors">
                  {action.description}
                </p>
                <div className="mt-3 flex items-center text-sm font-medium text-indigo-600 dark:text-indigo-400 group-hover:text-white transition-colors">
                  <span>Get started</span>
                  <ChevronRight className="h-4 w-4 ml-1 group-hover:translate-x-1 transition-transform" />
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>

      {/* Activity summary */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Today's schedule */}
        <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-sm p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-100 dark:bg-blue-900/30">
              <Calendar className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <h4 className="font-semibold text-slate-900 dark:text-white">Today&apos;s Schedule</h4>
              <p className="text-sm text-slate-500 dark:text-slate-400">8 parties scheduled</p>
            </div>
          </div>
          <div className="space-y-3">
            {[
              { time: '10:00 AM', event: 'Birthday Party - FunZone Downtown', guests: 15 },
              { time: '2:00 PM', event: 'VIP Experience - Adventure Park', guests: 25 },
              { time: '4:00 PM', event: 'Classic Package - FunZone Mall', guests: 12 },
            ].map((item, i) => (
              <div key={i} className="flex items-center gap-3 rounded-lg bg-slate-50 dark:bg-slate-700/50 p-3">
                <div className="text-sm font-medium text-indigo-600 dark:text-indigo-400 w-20">
                  {item.time}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-700 dark:text-slate-300 truncate">
                    {item.event}
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">{item.guests} guests</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Pending tasks */}
        <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-sm p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-amber-100 dark:bg-amber-900/30">
              <Target className="h-5 w-5 text-amber-600 dark:text-amber-400" />
            </div>
            <div>
              <h4 className="font-semibold text-slate-900 dark:text-white">Pending Tasks</h4>
              <p className="text-sm text-slate-500 dark:text-slate-400">5 items need attention</p>
            </div>
          </div>
          <div className="space-y-3">
            {[
              { task: 'Confirm booking #PB-002', priority: 'high' },
              { task: 'Review venue maintenance report', priority: 'medium' },
              { task: 'Update party package pricing', priority: 'low' },
            ].map((item, i) => (
              <div key={i} className="flex items-center gap-3 rounded-lg bg-slate-50 dark:bg-slate-700/50 p-3">
                <div className={cn(
                  'h-2 w-2 rounded-full',
                  item.priority === 'high' ? 'bg-red-500' :
                  item.priority === 'medium' ? 'bg-amber-500' : 'bg-emerald-500'
                )} />
                <p className="flex-1 text-sm font-medium text-slate-700 dark:text-slate-300 truncate">
                  {item.task}
                </p>
                <button className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
                  <MoreHorizontal className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Recent activity */}
        <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 shadow-sm p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-purple-100 dark:bg-purple-900/30">
              <Zap className="h-5 w-5 text-purple-600 dark:text-purple-400" />
            </div>
            <div>
              <h4 className="font-semibold text-slate-900 dark:text-white">Recent Activity</h4>
              <p className="text-sm text-slate-500 dark:text-slate-400">Live updates</p>
            </div>
          </div>
          <div className="space-y-3">
            {[
              { action: 'New booking received', time: '2 min ago', icon: Gift },
              { action: 'Payment confirmed', time: '15 min ago', icon: DollarSign },
              { action: 'Customer registered', time: '1 hour ago', icon: Users },
            ].map((item, i) => (
              <div key={i} className="flex items-center gap-3 rounded-lg bg-slate-50 dark:bg-slate-700/50 p-3">
                <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white dark:bg-slate-600 shadow-sm">
                  <item.icon className="h-4 w-4 text-slate-600 dark:text-slate-300" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-slate-700 dark:text-slate-300 truncate">
                    {item.action}
                  </p>
                  <p className="text-xs text-slate-500 dark:text-slate-400">{item.time}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
