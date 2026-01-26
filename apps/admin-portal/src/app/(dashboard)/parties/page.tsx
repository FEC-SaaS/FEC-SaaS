/**
 * =============================================================================
 * FILE: (dashboard)/parties/page.tsx
 * PURPOSE: Party bookings management with calendar, filters, and detail views
 * =============================================================================
 *
 * This page manages all party and event bookings:
 * - Overview stats (total bookings, pending, revenue)
 * - Calendar view of upcoming parties
 * - Filterable booking list
 * - Detailed booking information panel
 * - Quick actions (confirm, cancel, edit)
 *
 * FEATURES:
 * - Search by customer, booking ID, or venue
 * - Filter by status, date range, venue
 * - Booking detail slide-over panel
 * - Confirm/cancel pending bookings
 * - Export booking data
 *
 * =============================================================================
 */

'use client';

import { useState } from 'react';
import {
  Calendar,
  Clock,
  Users,
  DollarSign,
  PartyPopper,
  Search,
  Filter,
  Download,
  Eye,
  CheckCircle,
  XCircle,
  MoreHorizontal,
  MapPin,
  Phone,
  Mail,
  Gift,
  CreditCard,
  AlertCircle,
  ChevronRight,
  Plus,
  X,
  Cake,
  Sparkles,
  TrendingUp,
  CalendarDays,
} from 'lucide-react';
import { cn } from '@fec-saas/ui';

/**
 * Party booking interface
 */
interface PartyBooking {
  id: string;
  customerName: string;
  customerEmail: string;
  customerPhone: string;
  packageName: string;
  packageColor: string;
  venueName: string;
  date: string;
  startTime: string;
  endTime: string;
  guestCount: number;
  childName: string;
  childAge: number;
  status: 'pending' | 'confirmed' | 'completed' | 'cancelled';
  totalAmount: number;
  depositPaid: number;
  specialRequests?: string;
  createdAt: string;
}

/**
 * Mock party bookings data
 */
const bookings: PartyBooking[] = [
  {
    id: 'PB-001',
    customerName: 'Sarah Johnson',
    customerEmail: 'sarah.j@email.com',
    customerPhone: '(512) 555-1234',
    packageName: 'Ultimate Birthday Bash',
    packageColor: 'from-purple-500 to-pink-500',
    venueName: 'FunZone Downtown',
    date: '2024-01-25',
    startTime: '14:00',
    endTime: '17:00',
    guestCount: 20,
    childName: 'Emma',
    childAge: 8,
    status: 'confirmed',
    totalAmount: 450,
    depositPaid: 150,
    specialRequests: 'Allergy: peanuts. Please ensure all snacks are peanut-free.',
    createdAt: '2024-01-10',
  },
  {
    id: 'PB-002',
    customerName: 'Michael Smith',
    customerEmail: 'msmith@email.com',
    customerPhone: '(214) 555-5678',
    packageName: 'Classic Fun Package',
    packageColor: 'from-blue-500 to-cyan-500',
    venueName: 'Adventure Park',
    date: '2024-01-26',
    startTime: '11:00',
    endTime: '13:00',
    guestCount: 15,
    childName: 'Jake',
    childAge: 6,
    status: 'pending',
    totalAmount: 275,
    depositPaid: 0,
    createdAt: '2024-01-15',
  },
  {
    id: 'PB-003',
    customerName: 'Emily Williams',
    customerEmail: 'emily.w@email.com',
    customerPhone: '(713) 555-9012',
    packageName: 'VIP Experience',
    packageColor: 'from-amber-500 to-orange-500',
    venueName: 'FunZone Mall',
    date: '2024-01-27',
    startTime: '15:00',
    endTime: '19:00',
    guestCount: 30,
    childName: 'Lucas',
    childAge: 10,
    status: 'confirmed',
    totalAmount: 650,
    depositPaid: 250,
    specialRequests: 'Dinosaur theme decorations requested.',
    createdAt: '2024-01-08',
  },
  {
    id: 'PB-004',
    customerName: 'David Brown',
    customerEmail: 'dbrown@email.com',
    customerPhone: '(210) 555-3456',
    packageName: 'Classic Fun Package',
    packageColor: 'from-blue-500 to-cyan-500',
    venueName: 'FunZone Downtown',
    date: '2024-01-28',
    startTime: '10:00',
    endTime: '12:00',
    guestCount: 12,
    childName: 'Sophie',
    childAge: 5,
    status: 'pending',
    totalAmount: 275,
    depositPaid: 100,
    createdAt: '2024-01-18',
  },
  {
    id: 'PB-005',
    customerName: 'Lisa Anderson',
    customerEmail: 'lisa.a@email.com',
    customerPhone: '(512) 555-7890',
    packageName: 'Ultimate Birthday Bash',
    packageColor: 'from-purple-500 to-pink-500',
    venueName: 'Adventure Park',
    date: '2024-01-20',
    startTime: '13:00',
    endTime: '16:00',
    guestCount: 25,
    childName: 'Olivia',
    childAge: 9,
    status: 'completed',
    totalAmount: 450,
    depositPaid: 450,
    createdAt: '2024-01-05',
  },
  {
    id: 'PB-006',
    customerName: 'James Wilson',
    customerEmail: 'jwilson@email.com',
    customerPhone: '(713) 555-2345',
    packageName: 'Classic Fun Package',
    packageColor: 'from-blue-500 to-cyan-500',
    venueName: 'FunZone Mall',
    date: '2024-01-22',
    startTime: '16:00',
    endTime: '18:00',
    guestCount: 10,
    childName: 'Noah',
    childAge: 7,
    status: 'cancelled',
    totalAmount: 275,
    depositPaid: 100,
    createdAt: '2024-01-12',
  },
  {
    id: 'PB-007',
    customerName: 'Jennifer Lee',
    customerEmail: 'jlee@email.com',
    customerPhone: '(512) 555-4567',
    packageName: 'VIP Experience',
    packageColor: 'from-amber-500 to-orange-500',
    venueName: 'FunZone Downtown',
    date: '2024-01-29',
    startTime: '14:00',
    endTime: '18:00',
    guestCount: 35,
    childName: 'Mia',
    childAge: 8,
    status: 'confirmed',
    totalAmount: 750,
    depositPaid: 300,
    specialRequests: 'Princess theme. Gluten-free cake required.',
    createdAt: '2024-01-16',
  },
  {
    id: 'PB-008',
    customerName: 'Robert Taylor',
    customerEmail: 'rtaylor@email.com',
    customerPhone: '(214) 555-8901',
    packageName: 'Ultimate Birthday Bash',
    packageColor: 'from-purple-500 to-pink-500',
    venueName: 'Adventure Park',
    date: '2024-01-30',
    startTime: '11:00',
    endTime: '14:00',
    guestCount: 22,
    childName: 'Ethan',
    childAge: 11,
    status: 'pending',
    totalAmount: 495,
    depositPaid: 150,
    createdAt: '2024-01-19',
  },
];

/**
 * Status badge styling
 */
const statusConfig = {
  pending: {
    bg: 'bg-amber-100 dark:bg-amber-900/30',
    text: 'text-amber-700 dark:text-amber-400',
    icon: Clock,
    label: 'Pending',
  },
  confirmed: {
    bg: 'bg-emerald-100 dark:bg-emerald-900/30',
    text: 'text-emerald-700 dark:text-emerald-400',
    icon: CheckCircle,
    label: 'Confirmed',
  },
  completed: {
    bg: 'bg-blue-100 dark:bg-blue-900/30',
    text: 'text-blue-700 dark:text-blue-400',
    icon: Sparkles,
    label: 'Completed',
  },
  cancelled: {
    bg: 'bg-red-100 dark:bg-red-900/30',
    text: 'text-red-700 dark:text-red-400',
    icon: XCircle,
    label: 'Cancelled',
  },
};

/**
 * Format date to readable string
 */
const formatDate = (dateStr: string) => {
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  });
};

/**
 * Format time to readable string
 */
const formatTime = (time: string) => {
  const [hours, minutes] = time.split(':');
  const hour = parseInt(hours);
  const ampm = hour >= 12 ? 'PM' : 'AM';
  const displayHour = hour % 12 || 12;
  return `${displayHour}:${minutes} ${ampm}`;
};

export default function PartiesPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [venueFilter, setVenueFilter] = useState<string>('all');
  const [selectedBooking, setSelectedBooking] = useState<PartyBooking | null>(null);
  const [showFilters, setShowFilters] = useState(false);

  // Filter bookings
  const filteredBookings = bookings.filter((booking) => {
    const matchesSearch =
      booking.customerName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      booking.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      booking.venueName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      booking.childName.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'all' || booking.status === statusFilter;
    const matchesVenue = venueFilter === 'all' || booking.venueName === venueFilter;
    return matchesSearch && matchesStatus && matchesVenue;
  });

  // Get unique venues for filter
  const venues = [...new Set(bookings.map((b) => b.venueName))];

  // Calculate stats
  const totalBookings = bookings.length;
  const pendingBookings = bookings.filter((b) => b.status === 'pending').length;
  const confirmedThisWeek = bookings.filter((b) => b.status === 'confirmed').length;
  const totalRevenue = bookings
    .filter((b) => b.status !== 'cancelled')
    .reduce((sum, b) => sum + b.totalAmount, 0);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-slate-900 dark:text-white">Party Bookings</h1>
          <p className="text-slate-500 dark:text-slate-400">
            Manage birthday parties and event reservations
          </p>
        </div>
        <button className="inline-flex items-center gap-2 h-10 px-4 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 text-white text-sm font-medium hover:from-indigo-600 hover:to-purple-700 shadow-lg shadow-indigo-500/25 transition-all">
          <Plus className="h-4 w-4" />
          New Booking
        </button>
      </div>

      {/* Stats */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {/* Total Bookings */}
        <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
          <div className="flex items-center justify-between">
            <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center">
              <PartyPopper className="h-6 w-6 text-white" />
            </div>
            <div className="flex items-center gap-1 text-sm font-medium text-emerald-600">
              <TrendingUp className="h-4 w-4" />
              +12.5%
            </div>
          </div>
          <div className="mt-4">
            <p className="text-2xl font-bold text-slate-900 dark:text-white">{totalBookings}</p>
            <p className="text-sm text-slate-500 dark:text-slate-400">Total Bookings</p>
          </div>
        </div>

        {/* Pending Approval */}
        <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
          <div className="flex items-center justify-between">
            <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center">
              <Clock className="h-6 w-6 text-white" />
            </div>
            <span className="flex items-center gap-1 text-sm font-medium text-amber-600">
              <AlertCircle className="h-4 w-4" />
              Attention
            </span>
          </div>
          <div className="mt-4">
            <p className="text-2xl font-bold text-slate-900 dark:text-white">{pendingBookings}</p>
            <p className="text-sm text-slate-500 dark:text-slate-400">Pending Approval</p>
          </div>
        </div>

        {/* Confirmed This Week */}
        <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
          <div className="flex items-center justify-between">
            <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-emerald-500 to-teal-600 flex items-center justify-center">
              <CalendarDays className="h-6 w-6 text-white" />
            </div>
            <div className="flex items-center gap-1 text-sm font-medium text-emerald-600">
              <TrendingUp className="h-4 w-4" />
              +8.2%
            </div>
          </div>
          <div className="mt-4">
            <p className="text-2xl font-bold text-slate-900 dark:text-white">{confirmedThisWeek}</p>
            <p className="text-sm text-slate-500 dark:text-slate-400">Confirmed This Week</p>
          </div>
        </div>

        {/* Revenue */}
        <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-6">
          <div className="flex items-center justify-between">
            <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-pink-500 to-rose-600 flex items-center justify-center">
              <DollarSign className="h-6 w-6 text-white" />
            </div>
            <div className="flex items-center gap-1 text-sm font-medium text-emerald-600">
              <TrendingUp className="h-4 w-4" />
              +15.3%
            </div>
          </div>
          <div className="mt-4">
            <p className="text-2xl font-bold text-slate-900 dark:text-white">
              ${totalRevenue.toLocaleString()}
            </p>
            <p className="text-sm text-slate-500 dark:text-slate-400">Total Revenue</p>
          </div>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 p-4">
        <div className="flex flex-col lg:flex-row gap-4">
          {/* Search */}
          <div className="flex-1 relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-slate-400" />
            <input
              type="text"
              placeholder="Search by customer, booking ID, child name, or venue..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full h-10 pl-10 pr-4 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 text-sm text-slate-900 dark:text-white placeholder:text-slate-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/20"
            />
          </div>

          {/* Filter Controls */}
          <div className="flex items-center gap-3">
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="h-10 px-3 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 text-sm text-slate-900 dark:text-white focus:border-indigo-500 focus:outline-none"
            >
              <option value="all">All Statuses</option>
              <option value="pending">Pending</option>
              <option value="confirmed">Confirmed</option>
              <option value="completed">Completed</option>
              <option value="cancelled">Cancelled</option>
            </select>

            <select
              value={venueFilter}
              onChange={(e) => setVenueFilter(e.target.value)}
              className="h-10 px-3 rounded-lg border border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900 text-sm text-slate-900 dark:text-white focus:border-indigo-500 focus:outline-none"
            >
              <option value="all">All Venues</option>
              {venues.map((venue) => (
                <option key={venue} value={venue}>
                  {venue}
                </option>
              ))}
            </select>

            <button className="h-10 px-4 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors inline-flex items-center gap-2">
              <Filter className="h-4 w-4" />
              More Filters
            </button>

            <button className="h-10 px-4 rounded-lg border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 text-sm font-medium text-slate-600 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors inline-flex items-center gap-2">
              <Download className="h-4 w-4" />
              Export
            </button>
          </div>
        </div>
      </div>

      {/* Bookings List */}
      <div className="rounded-2xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 overflow-hidden">
        {/* Table Header */}
        <div className="hidden lg:grid lg:grid-cols-12 gap-4 px-6 py-3 bg-slate-50 dark:bg-slate-900 border-b border-slate-200 dark:border-slate-700 text-xs font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider">
          <div className="col-span-1">ID</div>
          <div className="col-span-2">Customer</div>
          <div className="col-span-2">Package</div>
          <div className="col-span-2">Event</div>
          <div className="col-span-2">Date & Time</div>
          <div className="col-span-1">Status</div>
          <div className="col-span-1">Amount</div>
          <div className="col-span-1"></div>
        </div>

        {/* Booking Rows */}
        <div className="divide-y divide-slate-200 dark:divide-slate-700">
          {filteredBookings.length === 0 ? (
            <div className="p-12 text-center">
              <PartyPopper className="h-12 w-12 text-slate-300 dark:text-slate-600 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-slate-900 dark:text-white mb-1">
                No bookings found
              </h3>
              <p className="text-slate-500 dark:text-slate-400">
                Try adjusting your search or filter criteria
              </p>
            </div>
          ) : (
            filteredBookings.map((booking) => {
              const status = statusConfig[booking.status];
              const StatusIcon = status.icon;

              return (
                <div
                  key={booking.id}
                  onClick={() => setSelectedBooking(booking)}
                  className="grid grid-cols-1 lg:grid-cols-12 gap-4 px-6 py-4 hover:bg-slate-50 dark:hover:bg-slate-700/50 cursor-pointer transition-colors"
                >
                  {/* ID */}
                  <div className="col-span-1 flex items-center">
                    <span className="font-mono text-sm text-slate-600 dark:text-slate-300">
                      {booking.id}
                    </span>
                  </div>

                  {/* Customer */}
                  <div className="col-span-2 flex items-center gap-3">
                    <div className="h-10 w-10 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-semibold text-sm flex-shrink-0">
                      {booking.customerName
                        .split(' ')
                        .map((n) => n[0])
                        .join('')}
                    </div>
                    <div className="min-w-0">
                      <p className="font-medium text-slate-900 dark:text-white truncate">
                        {booking.customerName}
                      </p>
                      <p className="text-sm text-slate-500 dark:text-slate-400 truncate">
                        {booking.customerEmail}
                      </p>
                    </div>
                  </div>

                  {/* Package */}
                  <div className="col-span-2 flex items-center">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <div
                          className={cn(
                            'h-2 w-2 rounded-full bg-gradient-to-r',
                            booking.packageColor
                          )}
                        />
                        <p className="font-medium text-slate-900 dark:text-white truncate">
                          {booking.packageName}
                        </p>
                      </div>
                      <p className="text-sm text-slate-500 dark:text-slate-400 truncate">
                        {booking.venueName}
                      </p>
                    </div>
                  </div>

                  {/* Event */}
                  <div className="col-span-2 flex items-center">
                    <div className="flex items-center gap-3">
                      <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-pink-100 to-rose-100 dark:from-pink-900/30 dark:to-rose-900/30 flex items-center justify-center">
                        <Cake className="h-5 w-5 text-pink-600 dark:text-pink-400" />
                      </div>
                      <div>
                        <p className="font-medium text-slate-900 dark:text-white">
                          {booking.childName}&apos;s {booking.childAge}th
                        </p>
                        <p className="text-sm text-slate-500 dark:text-slate-400">
                          {booking.guestCount} guests
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Date & Time */}
                  <div className="col-span-2 flex items-center">
                    <div>
                      <p className="font-medium text-slate-900 dark:text-white">
                        {formatDate(booking.date)}
                      </p>
                      <p className="text-sm text-slate-500 dark:text-slate-400">
                        {formatTime(booking.startTime)} - {formatTime(booking.endTime)}
                      </p>
                    </div>
                  </div>

                  {/* Status */}
                  <div className="col-span-1 flex items-center">
                    <span
                      className={cn(
                        'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium',
                        status.bg,
                        status.text
                      )}
                    >
                      <StatusIcon className="h-3.5 w-3.5" />
                      {status.label}
                    </span>
                  </div>

                  {/* Amount */}
                  <div className="col-span-1 flex items-center">
                    <div>
                      <p className="font-semibold text-slate-900 dark:text-white">
                        ${booking.totalAmount}
                      </p>
                      <p className="text-xs text-slate-500 dark:text-slate-400">
                        ${booking.depositPaid} paid
                      </p>
                    </div>
                  </div>

                  {/* Actions */}
                  <div className="col-span-1 flex items-center justify-end gap-1">
                    {booking.status === 'pending' && (
                      <>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            // Handle confirm
                          }}
                          className="p-2 rounded-lg text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-900/20 transition-colors"
                          title="Confirm"
                        >
                          <CheckCircle className="h-4 w-4" />
                        </button>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            // Handle cancel
                          }}
                          className="p-2 rounded-lg text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                          title="Cancel"
                        >
                          <XCircle className="h-4 w-4" />
                        </button>
                      </>
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedBooking(booking);
                      }}
                      className="p-2 rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                    >
                      <ChevronRight className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Booking Detail Panel */}
      {selectedBooking && (
        <div className="fixed inset-0 z-50 flex justify-end">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={() => setSelectedBooking(null)}
          />

          {/* Panel */}
          <div className="relative w-full max-w-lg bg-white dark:bg-slate-800 shadow-2xl overflow-y-auto animate-slide-in-right">
            {/* Header */}
            <div className="sticky top-0 z-10 bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 px-6 py-4">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-3">
                    <h2 className="text-lg font-semibold text-slate-900 dark:text-white">
                      Booking {selectedBooking.id}
                    </h2>
                    <span
                      className={cn(
                        'inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium',
                        statusConfig[selectedBooking.status].bg,
                        statusConfig[selectedBooking.status].text
                      )}
                    >
                      {statusConfig[selectedBooking.status].label}
                    </span>
                  </div>
                  <p className="text-sm text-slate-500 dark:text-slate-400 mt-1">
                    Created on {formatDate(selectedBooking.createdAt)}
                  </p>
                </div>
                <button
                  onClick={() => setSelectedBooking(null)}
                  className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                >
                  <X className="h-5 w-5 text-slate-400" />
                </button>
              </div>
            </div>

            {/* Content */}
            <div className="p-6 space-y-6">
              {/* Customer Info */}
              <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-4">
                <h3 className="text-sm font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-4">
                  Customer Information
                </h3>
                <div className="flex items-center gap-4 mb-4">
                  <div className="h-14 w-14 rounded-full bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white font-bold text-lg">
                    {selectedBooking.customerName
                      .split(' ')
                      .map((n) => n[0])
                      .join('')}
                  </div>
                  <div>
                    <p className="font-semibold text-slate-900 dark:text-white">
                      {selectedBooking.customerName}
                    </p>
                    <p className="text-sm text-slate-500 dark:text-slate-400">Parent/Guardian</p>
                  </div>
                </div>
                <div className="space-y-3">
                  <div className="flex items-center gap-3 text-sm">
                    <Mail className="h-4 w-4 text-slate-400" />
                    <span className="text-slate-600 dark:text-slate-300">
                      {selectedBooking.customerEmail}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-sm">
                    <Phone className="h-4 w-4 text-slate-400" />
                    <span className="text-slate-600 dark:text-slate-300">
                      {selectedBooking.customerPhone}
                    </span>
                  </div>
                </div>
              </div>

              {/* Event Details */}
              <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-4">
                <h3 className="text-sm font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-4">
                  Event Details
                </h3>
                <div className="space-y-4">
                  <div className="flex items-center gap-4">
                    <div className="h-12 w-12 rounded-xl bg-gradient-to-br from-pink-100 to-rose-100 dark:from-pink-900/30 dark:to-rose-900/30 flex items-center justify-center">
                      <Cake className="h-6 w-6 text-pink-600 dark:text-pink-400" />
                    </div>
                    <div>
                      <p className="font-semibold text-slate-900 dark:text-white">
                        {selectedBooking.childName}&apos;s {selectedBooking.childAge}th Birthday
                      </p>
                      <p className="text-sm text-slate-500 dark:text-slate-400">
                        {selectedBooking.guestCount} guests expected
                      </p>
                    </div>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-900">
                      <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400 text-xs mb-1">
                        <Gift className="h-3.5 w-3.5" />
                        Package
                      </div>
                      <p className="font-medium text-slate-900 dark:text-white text-sm">
                        {selectedBooking.packageName}
                      </p>
                    </div>
                    <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-900">
                      <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400 text-xs mb-1">
                        <MapPin className="h-3.5 w-3.5" />
                        Venue
                      </div>
                      <p className="font-medium text-slate-900 dark:text-white text-sm">
                        {selectedBooking.venueName}
                      </p>
                    </div>
                    <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-900">
                      <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400 text-xs mb-1">
                        <Calendar className="h-3.5 w-3.5" />
                        Date
                      </div>
                      <p className="font-medium text-slate-900 dark:text-white text-sm">
                        {formatDate(selectedBooking.date)}
                      </p>
                    </div>
                    <div className="p-3 rounded-lg bg-slate-50 dark:bg-slate-900">
                      <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400 text-xs mb-1">
                        <Clock className="h-3.5 w-3.5" />
                        Time
                      </div>
                      <p className="font-medium text-slate-900 dark:text-white text-sm">
                        {formatTime(selectedBooking.startTime)} -{' '}
                        {formatTime(selectedBooking.endTime)}
                      </p>
                    </div>
                  </div>
                </div>
              </div>

              {/* Payment Info */}
              <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-4">
                <h3 className="text-sm font-medium text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-4">
                  Payment Information
                </h3>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-slate-600 dark:text-slate-300">Total Amount</span>
                    <span className="font-semibold text-slate-900 dark:text-white">
                      ${selectedBooking.totalAmount}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-slate-600 dark:text-slate-300">Deposit Paid</span>
                    <span className="font-medium text-emerald-600">
                      ${selectedBooking.depositPaid}
                    </span>
                  </div>
                  <div className="border-t border-slate-200 dark:border-slate-700 pt-3 flex items-center justify-between">
                    <span className="font-medium text-slate-900 dark:text-white">Balance Due</span>
                    <span className="font-bold text-lg text-slate-900 dark:text-white">
                      ${selectedBooking.totalAmount - selectedBooking.depositPaid}
                    </span>
                  </div>
                </div>

                {selectedBooking.totalAmount > selectedBooking.depositPaid && (
                  <button className="mt-4 w-full h-10 rounded-lg bg-gradient-to-r from-emerald-500 to-teal-600 text-white text-sm font-medium hover:from-emerald-600 hover:to-teal-700 transition-all inline-flex items-center justify-center gap-2">
                    <CreditCard className="h-4 w-4" />
                    Record Payment
                  </button>
                )}
              </div>

              {/* Special Requests */}
              {selectedBooking.specialRequests && (
                <div className="rounded-xl border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-900/20 p-4">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="h-5 w-5 text-amber-600 dark:text-amber-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <h3 className="text-sm font-medium text-amber-800 dark:text-amber-300 mb-1">
                        Special Requests
                      </h3>
                      <p className="text-sm text-amber-700 dark:text-amber-400">
                        {selectedBooking.specialRequests}
                      </p>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* Footer Actions */}
            <div className="sticky bottom-0 bg-white dark:bg-slate-800 border-t border-slate-200 dark:border-slate-700 px-6 py-4">
              <div className="flex gap-3">
                {selectedBooking.status === 'pending' && (
                  <>
                    <button className="flex-1 h-10 rounded-lg bg-gradient-to-r from-emerald-500 to-teal-600 text-white text-sm font-medium hover:from-emerald-600 hover:to-teal-700 transition-all inline-flex items-center justify-center gap-2">
                      <CheckCircle className="h-4 w-4" />
                      Confirm Booking
                    </button>
                    <button className="h-10 px-4 rounded-lg border border-red-200 dark:border-red-800 text-red-600 dark:text-red-400 text-sm font-medium hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors inline-flex items-center gap-2">
                      <XCircle className="h-4 w-4" />
                      Cancel
                    </button>
                  </>
                )}
                {selectedBooking.status === 'confirmed' && (
                  <>
                    <button className="flex-1 h-10 rounded-lg bg-gradient-to-r from-indigo-500 to-purple-600 text-white text-sm font-medium hover:from-indigo-600 hover:to-purple-700 transition-all inline-flex items-center justify-center gap-2">
                      <Sparkles className="h-4 w-4" />
                      Mark Complete
                    </button>
                    <button className="h-10 px-4 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 text-sm font-medium hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors">
                      Edit
                    </button>
                  </>
                )}
                {selectedBooking.status === 'completed' && (
                  <button className="flex-1 h-10 rounded-lg border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 text-sm font-medium hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors">
                    View Invoice
                  </button>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Animation styles */}
      <style jsx>{`
        @keyframes slide-in-right {
          from {
            transform: translateX(100%);
          }
          to {
            transform: translateX(0);
          }
        }
        .animate-slide-in-right {
          animation: slide-in-right 0.3s ease-out;
        }
      `}</style>
    </div>
  );
}
